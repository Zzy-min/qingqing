"""Artifact storage backends and remote content proxy helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import httpx

from .security import fetch_public_https_bytes, validate_public_https_url


class ArtifactStorage(Protocol):
    def write_bytes(self, kind: str, extension: str, content: bytes) -> dict: ...
    def resolve_local_path(self, file_path: str) -> Path | None: ...


class LocalArtifactStorage:
    def __init__(self, root: Path | None = None):
        configured = os.environ.get("QINGQING_ARTIFACT_ROOT")
        self.root = Path(configured) if configured else (root or Path(__file__).resolve().parents[1] / "artifacts")
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, kind: str, extension: str, content: bytes) -> dict:
        artifact_id = str(uuid4())
        path = (self.root / f"{artifact_id}.{extension}").resolve()
        if self.root.resolve() not in path.parents and path.parent != self.root.resolve():
            raise RuntimeError("invalid artifact path")
        path.write_bytes(content)
        return {
            "id": artifact_id,
            "kind": kind,
            "storage": "local",
            "file_path": str(path),
            "size": len(content),
        }

    def resolve_local_path(self, file_path: str) -> Path | None:
        path = Path(file_path).resolve()
        root = self.root.resolve()
        if root not in path.parents and path.parent != root:
            return None
        if not path.is_file():
            return None
        return path


def get_artifact_storage() -> LocalArtifactStorage:
    return LocalArtifactStorage()


async def fetch_remote_artifact_bytes(url: str, *, max_bytes: int = 20 * 1024 * 1024) -> bytes:
    """Download a public HTTPS artifact with SSRF checks and size limits."""
    safe_url = validate_public_https_url(url)
    return await fetch_public_https_bytes(safe_url, max_bytes=max_bytes)
