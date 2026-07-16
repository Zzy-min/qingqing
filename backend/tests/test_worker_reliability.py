import os
import shutil
import sys
import time
from pathlib import Path
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


class FakeRedis:
    def __init__(self):
        self.lists = {}
        self.hashes = {}

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    def brpoplpush(self, source, destination, timeout=0):
        values = self.lists.setdefault(source, [])
        if not values:
            return None
        value = values.pop()
        self.lists.setdefault(destination, []).insert(0, value)
        return value

    def lrange(self, key, start, end):
        return list(self.lists.get(key, []))

    def lrem(self, key, count, value):
        values = self.lists.setdefault(key, [])
        try:
            values.remove(value)
            return 1
        except ValueError:
            return 0

    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = str(value)

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    def hdel(self, key, field):
        self.hashes.get(key, {}).pop(field, None)


def test_redis_job_is_acknowledged_only_after_success(monkeypatch):
    from qingqing_v1 import worker

    redis = FakeRedis()
    monkeypatch.setattr(worker, "_redis_client", lambda: redis)
    monkeypatch.setenv("QINGQING_REDIS_QUEUE_KEY", "test:jobs")

    worker._enqueue_redis_job("user", "run")
    job = worker.consume_redis_job(timeout=0)

    assert job and job["run_id"] == "run"
    assert redis.lists["test:jobs:processing"]
    worker.ack_redis_job(job)
    assert redis.lists["test:jobs:processing"] == []


def test_redis_job_retries_then_moves_to_dead_letter(monkeypatch):
    from qingqing_v1 import worker

    redis = FakeRedis()
    monkeypatch.setattr(worker, "_redis_client", lambda: redis)
    monkeypatch.setenv("QINGQING_REDIS_QUEUE_KEY", "test:retry")
    monkeypatch.setenv("QINGQING_JOB_MAX_ATTEMPTS", "1")

    worker._enqueue_redis_job("user", "run")
    first = worker.consume_redis_job(timeout=0)
    assert worker.fail_redis_job(first, "provider failed") == "retried"
    second = worker.consume_redis_job(timeout=0)
    assert second["attempts"] == 1
    assert worker.fail_redis_job(second, "provider failed") == "dead"
    assert len(redis.lists["test:retry:dead"]) == 1


def test_stale_redis_job_is_recovered(monkeypatch):
    from qingqing_v1 import worker

    redis = FakeRedis()
    monkeypatch.setattr(worker, "_redis_client", lambda: redis)
    monkeypatch.setenv("QINGQING_REDIS_QUEUE_KEY", "test:stale")
    monkeypatch.setenv("QINGQING_JOB_VISIBILITY_TIMEOUT", "1")

    worker._enqueue_redis_job("user", "run")
    job = worker.consume_redis_job(timeout=0)
    redis.hset("test:stale:leases", job["id"], time.time() - 10)

    assert worker.recover_stale_redis_jobs() == 1
    assert redis.lists["test:stale:processing"] == []
    assert len(redis.lists["test:stale"]) == 1


def test_durable_job_survives_until_ack_and_has_dead_letter(monkeypatch):
    from qingqing_v1 import worker

    queue_dir = BACKEND / ".test-tmp" / f"durable-{uuid4().hex}"
    monkeypatch.setenv("QINGQING_DURABLE_QUEUE_DIR", str(queue_dir))
    monkeypatch.setenv("QINGQING_JOB_MAX_ATTEMPTS", "1")
    try:
        worker._enqueue_durable_job("user", "run")
        first = worker.consume_durable_job()
        assert first and first["run_id"] == "run"
        assert worker.fail_durable_job(first, "failed") == "retried"

        second = worker.consume_durable_job()
        assert second and second["attempts"] == 1
        assert worker.fail_durable_job(second, "failed") == "dead"
        assert len(list(queue_dir.glob("*.dead.json"))) == 1

        worker._enqueue_durable_job("user", "run-2")
        successful = worker.consume_durable_job()
        worker.ack_durable_job(successful)
        assert not list(queue_dir.glob("*.running.json"))
    finally:
        shutil.rmtree(queue_dir, ignore_errors=True)


def test_stale_durable_job_is_requeued(monkeypatch):
    from qingqing_v1 import worker

    queue_dir = BACKEND / ".test-tmp" / f"durable-stale-{uuid4().hex}"
    monkeypatch.setenv("QINGQING_DURABLE_QUEUE_DIR", str(queue_dir))
    monkeypatch.setenv("QINGQING_JOB_VISIBILITY_TIMEOUT", "1")
    try:
        worker._enqueue_durable_job("user", "run")
        job = worker.consume_durable_job()
        running = Path(job["_queue_file"])
        old = time.time() - 10
        os.utime(running, (old, old))
        assert worker.recover_stale_durable_jobs() == 1
        assert len(list(queue_dir.glob("*.queued.json"))) == 1
    finally:
        shutil.rmtree(queue_dir, ignore_errors=True)
