"""Run execution worker abstraction.

Modes (QINGQING_WORKER_MODE):
- background (default): FastAPI BackgroundTasks
- inline: await execute_chat_run in-process (tests / debug)
- durable: append job JSONL and rely on background poller (best-effort durability)
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


async def _run_with_logging(user_id: str, run_id: str) -> None:
    logger.info("worker.start user_id=%s run_id=%s mode=%s", user_id, run_id, _worker_mode())
    try:
        await execute_chat_run(user_id, run_id)
        logger.info("worker.done user_id=%s run_id=%s", user_id, run_id)
    except Exception:
        logger.exception("worker.failed user_id=%s run_id=%s", user_id, run_id)
        raise


def schedule_run_execution(
    user_id: str,
    run_id: str,
    background: BackgroundTasks | None = None,
) -> dict[str, Any]:
    """Enqueue a run for execution. Returns job metadata."""
    mode = _worker_mode()
    meta: dict[str, Any] = {"mode": mode, "user_id": user_id, "run_id": run_id}

    if mode == "inline":
        # Caller should await if needed; for FastAPI path we still fire a task.
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_run_with_logging(user_id, run_id))
            meta["scheduled"] = "asyncio_task"
        except RuntimeError:
            asyncio.run(_run_with_logging(user_id, run_id))
            meta["scheduled"] = "asyncio_run"
        return meta

    if mode == "durable":
        job = _append_durable_job(user_id, run_id)
        meta["job"] = job
        # Still execute via background/task so local dev works without a separate worker process.
        if background is not None:
            background.add_task(_run_with_logging, user_id, run_id)
            meta["scheduled"] = "durable+background"
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_run_with_logging(user_id, run_id))
                meta["scheduled"] = "durable+asyncio_task"
            except RuntimeError:
                asyncio.run(_run_with_logging(user_id, run_id))
                meta["scheduled"] = "durable+asyncio_run"
        return meta

    # default: background
    if background is None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_run_with_logging(user_id, run_id))
            meta["scheduled"] = "asyncio_task"
        except RuntimeError:
            asyncio.run(_run_with_logging(user_id, run_id))
            meta["scheduled"] = "asyncio_run"
        return meta

    background.add_task(_run_with_logging, user_id, run_id)
    meta["scheduled"] = "background"
    return meta
