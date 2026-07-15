"""Dedicated Redis worker process for QINGQING_WORKER_MODE=redis.

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
    from qingqing_v1.worker import consume_redis_job, process_job

    logger.info("redis worker started url=%s", os.environ.get("QINGQING_REDIS_URL"))
    while True:
        job = await asyncio.to_thread(consume_redis_job, timeout=5)
        if not job:
            continue
        logger.info("picked job=%s run=%s", job.get("id"), job.get("run_id"))
        try:
            await process_job(job)
        except Exception:
            logger.exception("job failed id=%s", job.get("id"))


if __name__ == "__main__":
    asyncio.run(main())
