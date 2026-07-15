"""Optional live integration checks. Skipped when services are unreachable.

Enable by starting docker compose and installing optional deps:
  docker compose up -d
  pip install "psycopg[binary]" redis boto3
  set QINGQING_RUN_INTEGRATION=1
  pytest tests/test_optional_integration.py -q
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

RUN = (os.environ.get("QINGQING_RUN_INTEGRATION") or "").lower() in {"1", "true", "yes"}


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not RUN, reason="set QINGQING_RUN_INTEGRATION=1 to run live checks")
def test_postgres_roundtrip_if_available():
    if not _port_open("127.0.0.1", 5432):
        pytest.skip("postgres not listening on 5432")
    pytest.importorskip("psycopg")
    from qingqing_v1.postgres_store import PostgresStore

    dsn = os.environ.get(
        "QINGQING_DATABASE_URL",
        "postgresql://qingqing:qingqing@127.0.0.1:5432/qingqing",
    )
    store = PostgresStore(dsn)
    try:
        store.reset()
        store.ensure_user("it-user", "free")
        store.save_preferences("it-user", {"memory_enabled": True, "style_notes": "it"})
        assert store.get_preferences("it-user")["style_notes"] == "it"
        ok = store.create_run_once(
            "it-user",
            {"id": "run-it-1", "goal": "g", "status": "planned", "idempotency_key": "it-1"},
        )
        assert ok is True
        claimed = store.claim_run_status("it-user", "run-it-1", "planned", {"status": "running"})
        assert claimed and claimed["status"] == "running"
    finally:
        store.conn.close()


@pytest.mark.skipif(not RUN, reason="set QINGQING_RUN_INTEGRATION=1 to run live checks")
def test_redis_enqueue_if_available(monkeypatch):
    if not _port_open("127.0.0.1", 6379):
        pytest.skip("redis not listening on 6379")
    pytest.importorskip("redis")
    monkeypatch.setenv("QINGQING_REDIS_URL", os.environ.get("QINGQING_REDIS_URL", "redis://127.0.0.1:6379/0"))
    monkeypatch.setenv("QINGQING_REDIS_QUEUE_KEY", "qingqing:test_jobs")
    from qingqing_v1.worker import _enqueue_redis_job, consume_redis_job

    job = _enqueue_redis_job("u-it", "run-it")
    assert job["run_id"] == "run-it"
    # drain queue quickly
    got = consume_redis_job(timeout=1)
    assert got is not None
    assert got["run_id"] == "run-it"


@pytest.mark.skipif(not RUN, reason="set QINGQING_RUN_INTEGRATION=1 to run live checks")
def test_minio_s3_if_available(monkeypatch):
    if not _port_open("127.0.0.1", 9000):
        pytest.skip("minio not listening on 9000")
    pytest.importorskip("boto3")
    monkeypatch.setenv("QINGQING_ARTIFACT_BACKEND", "s3")
    monkeypatch.setenv("QINGQING_S3_BUCKET", "qingqing")
    monkeypatch.setenv("QINGQING_S3_ENDPOINT", "http://127.0.0.1:9000")
    monkeypatch.setenv("QINGQING_S3_ACCESS_KEY", "minioadmin")
    monkeypatch.setenv("QINGQING_S3_SECRET_KEY", "minioadmin")
    monkeypatch.setenv("QINGQING_S3_REGION", "us-east-1")
    from qingqing_v1.storage import S3ArtifactStorage

    storage = S3ArtifactStorage()
    meta = storage.write_bytes("image", "bin", b"hello-minio")
    assert meta["storage"] == "s3"
    data = storage.read_bytes(meta)
    assert data == b"hello-minio"
