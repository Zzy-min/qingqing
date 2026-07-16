"""Dependency-aware readiness checks without exposing secrets or topology."""

from __future__ import annotations

import os
from pathlib import Path

from .smtp_mail import smtp_configured
from .storage import LocalArtifactStorage, S3ArtifactStorage, get_artifact_storage
from .store import store
from .worker import _durable_queue_dir, _redis_client


def _database_check() -> tuple[bool, str]:
    try:
        if hasattr(store, "db"):
            store.db.execute("SELECT 1").fetchone()
            return True, "sqlite"
        store.conn.execute("SELECT 1").fetchone()
        return True, "postgresql"
    except Exception:
        return False, "unavailable"


def _worker_check(environment: str, mode: str) -> tuple[bool, str]:
    if mode in {"background", "inline"}:
        return environment != "production", mode
    if mode == "redis":
        try:
            return bool(_redis_client().ping()), "redis"
        except Exception:
            return False, "redis"
    if mode == "durable":
        path = _durable_queue_dir()
        probe = path if path.exists() else path.parent
        return probe.exists() and os.access(probe, os.W_OK), "durable"
    return False, "unknown"


def _artifact_check() -> tuple[bool, str]:
    try:
        storage = get_artifact_storage()
        if isinstance(storage, LocalArtifactStorage):
            return storage.root.exists() and os.access(storage.root, os.W_OK), "local"
        if isinstance(storage, S3ArtifactStorage):
            storage.client.head_bucket(Bucket=storage.bucket)
            return True, "s3"
    except Exception:
        return False, "unavailable"
    return False, "unknown"


def _check(ok: bool, detail: str) -> dict:
    return {"ok": bool(ok), "detail": detail}


def readiness_report() -> dict:
    environment = (os.environ.get("QINGQING_ENVIRONMENT") or "development").strip().lower()
    production = environment == "production"
    session_secret = os.environ.get("QINGQING_SESSION_SECRET") or ""
    credential_key = os.environ.get("QINGQING_CREDENTIAL_KEY") or ""
    cors = os.environ.get("CORS_ORIGINS") or ""
    local_user = (os.environ.get("QINGQING_ALLOW_LOCAL_USER") or "false").lower() == "true"
    worker_mode = (os.environ.get("QINGQING_WORKER_MODE") or "background").strip().lower()

    database_ok, database_kind = _database_check()
    worker_ok, worker_kind = _worker_check(environment, worker_mode)
    artifact_ok, artifact_kind = _artifact_check()
    smtp_ok = smtp_configured() or (not production and local_user)
    checks = {
        "database": _check(database_ok, database_kind),
        "worker": _check(worker_ok, worker_kind),
        "artifact_storage": _check(artifact_ok, artifact_kind),
        "session_secret": _check(len(session_secret) >= 16, "configured" if len(session_secret) >= 16 else "missing"),
        "credential_key": _check(len(credential_key) >= 16, "configured" if len(credential_key) >= 16 else "missing"),
        "smtp": _check(smtp_ok, "configured" if smtp_configured() else "local_dev" if smtp_ok else "missing"),
        "cors": _check(bool(cors.strip()) or not production, "configured" if cors.strip() else "development_default" if not production else "missing"),
        "local_user_disabled": _check(not production or not local_user, "disabled" if not local_user else "development_only"),
    }
    return {
        "ready": all(item["ok"] for item in checks.values()),
        "environment": environment,
        "checks": checks,
    }
