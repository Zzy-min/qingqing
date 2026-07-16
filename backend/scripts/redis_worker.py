"""Dedicated reliable worker for Redis or filesystem durable mode.

Usage:
  set QINGQING_REDIS_URL=redis://127.0.0.1:6379/0
  set QINGQING_WORKER_MODE=redis
  python -m scripts.redis_worker

Or from backend/:
  python scripts/redis_worker.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("qingqing.redis_worker")


async def main() -> None:
    from qingqing_v1.worker import (
        ack_durable_job,
        ack_redis_job,
        consume_durable_job,
        consume_redis_job,
        fail_durable_job,
        fail_redis_job,
        process_job,
    )

    mode = (os.environ.get("QINGQING_WORKER_MODE") or "redis").strip().lower()
    if mode not in {"redis", "durable"}:
        raise RuntimeError("worker process requires QINGQING_WORKER_MODE=redis or durable")
    logger.info("worker started mode=%s", mode)
    while True:
        if mode == "redis":
            job = await asyncio.to_thread(consume_redis_job, timeout=5)
        else:
            job = await asyncio.to_thread(consume_durable_job)
        if not job:
            if mode == "durable":
                await asyncio.sleep(1)
            continue
        logger.info("picked job=%s run=%s", job.get("id"), job.get("run_id"))
        try:
            await process_job(job)
            if mode == "redis":
                await asyncio.to_thread(ack_redis_job, job)
            else:
                await asyncio.to_thread(ack_durable_job, job)
        except Exception as exc:
            logger.exception("job failed id=%s", job.get("id"))
            if mode == "redis":
                outcome = await asyncio.to_thread(fail_redis_job, job, type(exc).__name__)
            else:
                outcome = await asyncio.to_thread(fail_durable_job, job, type(exc).__name__)
            logger.warning("job failure handled id=%s outcome=%s", job.get("id"), outcome)


if __name__ == "__main__":
    asyncio.run(main())
