"""Deepening features: store factory, redis/s3 fallbacks, memory scoring, mcp gates."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("QINGQING_CREDENTIAL_KEY", "test-only-key-material")
os.environ["QINGQING_ALLOW_LOCAL_USER"] = "true"


def test_is_postgres_url():
    from qingqing_v1.postgres_store import is_postgres_url

    assert is_postgres_url("postgresql://user:pass@localhost:5432/qq")
    assert is_postgres_url("postgres://localhost/qq")
    assert not is_postgres_url("sqlite:///tmp.db")
    assert not is_postgres_url("")


def test_create_store_defaults_to_sqlite(monkeypatch):
    folder = BACKEND / ".test-tmp"
    folder.mkdir(exist_ok=True)
    db_path = folder / "deepen-store.db"
    monkeypatch.delenv("QINGQING_DATABASE_URL", raising=False)
    monkeypatch.setenv("QINGQING_DATABASE_PATH", str(db_path))
    from qingqing_v1.store import SqliteStore, create_store

    s = create_store()
    assert isinstance(s, SqliteStore)
    s.ensure_user("u1")
    assert s.get_user("u1")["id"] == "u1"
    s.db.close()
    db_path.unlink(missing_ok=True)


def test_redis_enqueue_uses_client(monkeypatch):
    from qingqing_v1 import worker

    fake_client = MagicMock()
    fake_client.lpush = MagicMock(return_value=1)
    fake_mod = MagicMock()
    fake_mod.Redis.from_url = MagicMock(return_value=fake_client)
    monkeypatch.setenv("QINGQING_REDIS_URL", "redis://example:6379/0")
    monkeypatch.setitem(sys.modules, "redis", fake_mod)
    job = worker._enqueue_redis_job("user-a", "run-a")
    assert job["run_id"] == "run-a"
    fake_client.lpush.assert_called()


def test_schedule_redis_falls_back_without_redis(monkeypatch):
    from qingqing_v1.worker import schedule_run_execution

    monkeypatch.setenv("QINGQING_WORKER_MODE", "redis")

    def boom(*a, **k):
        raise RuntimeError("no redis")

    async def noop(*a, **k):
        return None

    monkeypatch.setattr("qingqing_v1.worker._enqueue_redis_job", boom)
    monkeypatch.setattr("qingqing_v1.worker._run_with_logging", noop)
    meta = schedule_run_execution("u", "r", background=None)
    assert meta["mode"] in {"redis", "background"}
    assert "scheduled" in meta


def test_s3_storage_write_read(monkeypatch):
    from qingqing_v1.storage import S3ArtifactStorage

    put = MagicMock()
    get = MagicMock(return_value={"Body": MagicMock(read=MagicMock(return_value=b"abc"))})
    client = MagicMock(put_object=put, get_object=get)
    boto3 = MagicMock(client=MagicMock(return_value=client))
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.setenv("QINGQING_S3_BUCKET", "bucket")
    monkeypatch.setenv("QINGQING_S3_ACCESS_KEY", "ak")
    monkeypatch.setenv("QINGQING_S3_SECRET_KEY", "sk")
    storage = S3ArtifactStorage()
    meta = storage.write_bytes("image", "png", b"abc")
    assert meta["storage"] == "s3"
    assert meta["s3_key"]
    put.assert_called()
    data = storage.read_bytes(meta)
    assert data == b"abc"


def test_memory_chinese_bigram_search():
    from qingqing_v1.store import store
    from qingqing_v1 import memory

    store.reset()
    store.ensure_user("local-user")
    memory.add_note("local-user", "用户偏好浅青配色与大量留白")
    memory.add_note("local-user", " unrelated english note about cats")
    hits = memory.list_memory("local-user", query="浅青", limit=10)
    assert hits
    assert any("浅青" in h["content"] for h in hits)


def test_mcp_invoke_requires_enabled_allowlist(monkeypatch):
    from qingqing_v1.store import store
    from qingqing_v1 import tools

    store.reset()
    store.ensure_user("local-user")
    monkeypatch.setenv(
        "QINGQING_MCP_SERVERS",
        json.dumps(
            [
                {
                    "name": "demo",
                    "url": "https://example.com/mcp",
                    "enabled": True,
                    "allowed_tools": ["echo"],
                }
            ]
        ),
    )
    monkeypatch.setattr("qingqing_v1.tools.validate_public_https_url", lambda u: u.rstrip("/"))

    class Resp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"ok": True, "echo": "hi"}

    class Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def post(self, url, json=None, headers=None):
            assert url.endswith("/tools/call")
            assert json["name"] == "echo"
            return Resp()

    monkeypatch.setattr(tools.httpx, "Client", Client)
    out = tools.invoke_tool("local-user", "mcp_invoke", {"server": "demo", "tool": "echo", "arguments": {"x": 1}})
    assert out["status"] == "completed"
    assert out["result"]["response"]["ok"] is True

    with pytest.raises(Exception):
        tools.invoke_tool("local-user", "mcp_invoke", {"server": "demo", "tool": "blocked"})


def test_local_storage_path_traversal_blocked(monkeypatch):
    from qingqing_v1.storage import LocalArtifactStorage

    folder = BACKEND / ".test-tmp" / "artifacts-deepen"
    folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("QINGQING_ARTIFACT_ROOT", str(folder))
    storage = LocalArtifactStorage()
    meta = storage.write_bytes("audio", "mp3", b"1234")
    assert storage.resolve_local_path(meta["file_path"]) is not None
    assert storage.resolve_local_path(str(folder / ".." / "etc" / "passwd")) is None
