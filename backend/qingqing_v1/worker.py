"""Run execution workers with explicit acknowledgement and retry semantics.

Modes (QINGQING_WORKER_MODE):
- background (default): FastAPI BackgroundTasks, intended for local development
- inline: current event loop, intended for tests or debugging
- durable: filesystem spool consumed by ``scripts/redis_worker.py``
- redis: reliable Redis list with processing, lease, retry and dead-letter queues
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks

from .execution import execute_chat_run

logger = logging.getLogger("qingqing.worker")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _worker_mode() -> str:
    return (os.environ.get("QINGQING_WORKER_MODE") or "background").strip().lower()


def _max_attempts() -> int:
    return max(0, int(os.environ.get("QINGQING_JOB_MAX_ATTEMPTS") or "3"))


def _visibility_timeout() -> int:
    return max(1, int(os.environ.get("QINGQING_JOB_VISIBILITY_TIMEOUT") or "300"))


def _new_job(user_id: str, run_id: str) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "user_id": user_id,
        "run_id": run_id,
        "status": "queued",
        "attempts": 0,
        "created_at": _now(),
    }


def _safe_error(error: str) -> str:
    return str(error).replace("\r", " ").replace("\n", " ")[:160]


# Redis reliable queue -----------------------------------------------------


def _redis_url() -> str:
    return (os.environ.get("QINGQING_REDIS_URL") or "redis://127.0.0.1:6379/0").strip()


def _redis_queue_key() -> str:
    return (os.environ.get("QINGQING_REDIS_QUEUE_KEY") or "qingqing:run_jobs").strip()


def _redis_processing_key() -> str:
    return f"{_redis_queue_key()}:processing"


def _redis_dead_key() -> str:
    return f"{_redis_queue_key()}:dead"


def _redis_lease_key() -> str:
    return f"{_redis_queue_key()}:leases"


def _redis_client():
    try:
        import redis
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("redis package required for QINGQING_WORKER_MODE=redis") from exc
    return redis.Redis.from_url(_redis_url(), decode_responses=True)


def _encode_job(job: dict[str, Any]) -> str:
    public = {key: value for key, value in job.items() if not key.startswith("_queue_")}
    return json.dumps(public, ensure_ascii=False, separators=(",", ":"))


def _enqueue_redis_job(user_id: str, run_id: str) -> dict[str, Any]:
    job = _new_job(user_id, run_id)
    _redis_client().lpush(_redis_queue_key(), _encode_job(job))
    return job


def recover_stale_redis_jobs(*, client=None) -> int:
    client = client or _redis_client()
    recovered = 0
    cutoff = time.time() - _visibility_timeout()
    for payload in client.lrange(_redis_processing_key(), 0, -1):
        try:
            job = json.loads(payload)
            lease = client.hget(_redis_lease_key(), job["id"])
            stale = lease is None or float(lease) <= cutoff
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            stale = True
            job = {"id": "invalid", "status": "queued"}
        if not stale:
            continue
        if client.lrem(_redis_processing_key(), 1, payload) != 1:
            continue
        client.hdel(_redis_lease_key(), job.get("id", "invalid"))
        job.update({"status": "queued", "recovered_at": _now()})
        client.lpush(_redis_queue_key(), _encode_job(job))
        recovered += 1
    return recovered


def consume_redis_job(*, timeout: int = 5) -> dict[str, Any] | None:
    client = _redis_client()
    recover_stale_redis_jobs(client=client)
    payload = client.brpoplpush(_redis_queue_key(), _redis_processing_key(), timeout=timeout)
    if not payload:
        return None
    try:
        job = json.loads(payload)
    except json.JSONDecodeError:
        client.lrem(_redis_processing_key(), 1, payload)
        client.lpush(_redis_dead_key(), payload)
        return None
    client.hset(_redis_lease_key(), job["id"], time.time())
    return {**job, "status": "processing", "_queue_payload": payload}


def ack_redis_job(job: dict[str, Any]) -> None:
    client = _redis_client()
    payload = job.get("_queue_payload") or _encode_job(job)
    client.lrem(_redis_processing_key(), 1, payload)
    client.hdel(_redis_lease_key(), job["id"])


def fail_redis_job(job: dict[str, Any], error: str) -> str:
    client = _redis_client()
    payload = job.get("_queue_payload") or _encode_job(job)
    client.lrem(_redis_processing_key(), 1, payload)
    client.hdel(_redis_lease_key(), job["id"])
    failed = {
        **{key: value for key, value in job.items() if not key.startswith("_queue_")},
        "attempts": int(job.get("attempts", 0)) + 1,
        "last_error": _safe_error(error),
        "updated_at": _now(),
    }
    if failed["attempts"] <= _max_attempts():
        failed["status"] = "queued"
        client.lpush(_redis_queue_key(), _encode_job(failed))
        return "retried"
    failed["status"] = "dead"
    client.lpush(_redis_dead_key(), _encode_job(failed))
    return "dead"


# Filesystem durable queue ------------------------------------------------


def _durable_queue_dir() -> Path:
    configured = os.environ.get("QINGQING_DURABLE_QUEUE_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "artifacts" / "worker_jobs"


def _durable_path(job_id: str, state: str) -> Path:
    return _durable_queue_dir() / f"{job_id}.{state}.json"


def _write_job_atomic(path: Path, job: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(_encode_job(job), encoding="utf-8")
    temp.replace(path)


def _enqueue_durable_job(user_id: str, run_id: str) -> dict[str, Any]:
    job = _new_job(user_id, run_id)
    _write_job_atomic(_durable_path(job["id"], "queued"), job)
    return job


def recover_stale_durable_jobs() -> int:
    queue_dir = _durable_queue_dir()
    if not queue_dir.exists():
        return 0
    recovered = 0
    cutoff = time.time() - _visibility_timeout()
    for running in queue_dir.glob("*.running.json"):
        try:
            if running.stat().st_mtime > cutoff:
                continue
            job_id = running.name.removesuffix(".running.json")
            running.replace(_durable_path(job_id, "queued"))
            recovered += 1
        except FileNotFoundError:
            continue
    return recovered


def consume_durable_job() -> dict[str, Any] | None:
    recover_stale_durable_jobs()
    queue_dir = _durable_queue_dir()
    if not queue_dir.exists():
        return None
    for queued in sorted(queue_dir.glob("*.queued.json")):
        job_id = queued.name.removesuffix(".queued.json")
        running = _durable_path(job_id, "running")
        try:
            queued.replace(running)
        except FileNotFoundError:
            continue
        try:
            job = json.loads(running.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            running.replace(_durable_path(job_id, "dead"))
            continue
        job.update({"status": "processing", "reserved_at": _now()})
        _write_job_atomic(running, job)
        return {**job, "_queue_file": str(running)}
    return None


def ack_durable_job(job: dict[str, Any]) -> None:
    Path(job["_queue_file"]).unlink(missing_ok=True)


def fail_durable_job(job: dict[str, Any], error: str) -> str:
    running = Path(job["_queue_file"])
    failed = {
        **{key: value for key, value in job.items() if not key.startswith("_queue_")},
        "attempts": int(job.get("attempts", 0)) + 1,
        "last_error": _safe_error(error),
        "updated_at": _now(),
    }
    state = "queued" if failed["attempts"] <= _max_attempts() else "dead"
    failed["status"] = state
    target = _durable_path(failed["id"], state)
    _write_job_atomic(target, failed)
    running.unlink(missing_ok=True)
    return "retried" if state == "queued" else "dead"


# Execution and scheduling ------------------------------------------------


async def process_job(job: dict[str, Any]) -> None:
    await _run_with_logging(job["user_id"], job["run_id"])


async def _run_with_logging(user_id: str, run_id: str) -> None:
    logger.info("worker.start user_id=%s run_id=%s mode=%s", user_id, run_id, _worker_mode())
    try:
        await execute_chat_run(user_id, run_id)
        logger.info("worker.done user_id=%s run_id=%s", user_id, run_id)
    except Exception:
        logger.exception("worker.failed user_id=%s run_id=%s", user_id, run_id)
        raise


def _spawn_async(user_id: str, run_id: str) -> str:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run_with_logging(user_id, run_id))
        return "asyncio_task"
    except RuntimeError:
        asyncio.run(_run_with_logging(user_id, run_id))
        return "asyncio_run"


def schedule_run_execution(
    user_id: str,
    run_id: str,
    background: BackgroundTasks | None = None,
) -> dict[str, Any]:
    """Schedule a run and return non-sensitive job metadata."""
    mode = _worker_mode()
    meta: dict[str, Any] = {"mode": mode, "user_id": user_id, "run_id": run_id}

    if mode == "inline":
        meta["scheduled"] = _spawn_async(user_id, run_id)
        return meta

    if mode == "redis":
        try:
            job = _enqueue_redis_job(user_id, run_id)
            return {**meta, "job_id": job["id"], "scheduled": "redis_queue"}
        except Exception:
            logger.exception("redis enqueue failed")
            if (os.environ.get("QINGQING_WORKER_FALLBACK_TO_BACKGROUND") or "").lower() != "true":
                raise RuntimeError("worker queue unavailable")
            mode = "background"
            meta = {**meta, "mode": mode, "degraded": True}

    if mode == "durable":
        job = _enqueue_durable_job(user_id, run_id)
        return {**meta, "job_id": job["id"], "scheduled": "durable_queue"}

    if background is None:
        meta["scheduled"] = _spawn_async(user_id, run_id)
        return meta
    background.add_task(_run_with_logging, user_id, run_id)
    meta["scheduled"] = "background"
    return meta
