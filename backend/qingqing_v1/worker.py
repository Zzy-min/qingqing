"""Run execution worker abstraction.

Modes (QINGQING_WORKER_MODE):
- background (default): FastAPI BackgroundTasks
- inline: asyncio task / run
- durable: JSONL queue + execute
- redis: LPUSH/BRPOP queue (requires redis package + QINGQING_REDIS_URL)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks

from .execution import execute_chat_run

logger = logging.getLogger("qingqing.worker")


def _worker_mode() -> str:
    return (os.environ.get("QINGQING_WORKER_MODE") or "background").strip().lower()


def _queue_path() -> Path:
    configured = os.environ.get("QINGQING_WORKER_QUEUE_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "artifacts" / "worker_queue.jsonl"


def _redis_url() -> str:
    return (os.environ.get("QINGQING_REDIS_URL") or "redis://127.0.0.1:6379/0").strip()


def _redis_queue_key() -> str:
    return (os.environ.get("QINGQING_REDIS_QUEUE_KEY") or "qingqing:run_jobs").strip()


def _append_durable_job(user_id: str, run_id: str) -> dict[str, Any]:
    path = _queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    job = {
        "id": str(uuid4()),
        "user_id": user_id,
        "run_id": run_id,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(job, ensure_ascii=False) + "\n")
    return job


def _enqueue_redis_job(user_id: str, run_id: str) -> dict[str, Any]:
    try:
        import redis
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("redis package required for QINGQING_WORKER_MODE=redis") from exc
    client = redis.Redis.from_url(_redis_url(), decode_responses=True)
    job = {
        "id": str(uuid4()),
        "user_id": user_id,
        "run_id": run_id,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    client.lpush(_redis_queue_key(), json.dumps(job, ensure_ascii=False))
    return job


def consume_redis_job(*, timeout: int = 5) -> dict[str, Any] | None:
    """Blocking pop for a dedicated worker process. Returns None on timeout."""
    try:
        import redis
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("redis package required") from exc
    client = redis.Redis.from_url(_redis_url(), decode_responses=True)
    item = client.brpop(_redis_queue_key(), timeout=timeout)
    if not item:
        return None
    _, payload = item
    return json.loads(payload)


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
    """Enqueue a run for execution. Returns job metadata."""
    mode = _worker_mode()
    meta: dict[str, Any] = {"mode": mode, "user_id": user_id, "run_id": run_id}

    if mode == "inline":
        meta["scheduled"] = _spawn_async(user_id, run_id)
        return meta

    if mode == "redis":
        try:
            job = _enqueue_redis_job(user_id, run_id)
            meta["job"] = job
            meta["scheduled"] = "redis_queue"
            # Optionally also execute locally if QINGQING_REDIS_EXECUTE_INLINE=true (dev helper)
            if (os.environ.get("QINGQING_REDIS_EXECUTE_INLINE") or "").lower() == "true":
                if background is not None:
                    background.add_task(_run_with_logging, user_id, run_id)
                    meta["scheduled"] = "redis_queue+background"
                else:
                    meta["scheduled"] = "redis_queue+" + _spawn_async(user_id, run_id)
            return meta
        except Exception as exc:
            logger.warning("redis enqueue failed, falling back to background: %s", exc)
            meta["redis_error"] = str(exc)[:200]
            mode = "background"

    if mode == "durable":
        job = _append_durable_job(user_id, run_id)
        meta["job"] = job
        if background is not None:
            background.add_task(_run_with_logging, user_id, run_id)
            meta["scheduled"] = "durable+background"
        else:
            meta["scheduled"] = "durable+" + _spawn_async(user_id, run_id)
        return meta

    # default / fallback: background
    if background is None:
        meta["scheduled"] = _spawn_async(user_id, run_id)
        return meta

    background.add_task(_run_with_logging, user_id, run_id)
    meta["scheduled"] = "background"
    return meta
