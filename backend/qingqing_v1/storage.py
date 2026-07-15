"""Artifact storage backends: local filesystem and optional S3/MinIO."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .security import fetch_public_https_bytes, validate_public_https_url


class ArtifactStorage(Protocol):
    def write_bytes(self, kind: str, extension: str, content: bytes) -> dict: ...
    def resolve_local_path(self, file_path: str) -> Path | None: ...
    def read_bytes(self, artifact: dict) -> bytes | None: ...


class LocalArtifactStorage:
    def __init__(self, root: Path | None = None):
        configured = os.environ.get("QINGQING_ARTIFACT_ROOT")
        self.root = Path(configured) if configured else (root or Path(__file__).resolve().parents[1] / "artifacts")
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, kind: str, extension: str, content: bytes) -> dict:
        artifact_id = str(uuid4())
        path = (self.root / f"{artifact_id}.{extension}").resolve()
        root = self.root.resolve()
        if path.parent != root and root not in path.parents:
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
        if path.parent != root and root not in path.parents:
            return None
        if not path.is_file():
            return None
        return path

    def read_bytes(self, artifact: dict) -> bytes | None:
        path = self.resolve_local_path(artifact.get("file_path") or "")
        return path.read_bytes() if path else None


class S3ArtifactStorage:
    """S3-compatible storage (AWS S3 or MinIO) via boto3."""

    def __init__(self):
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("boto3 is required for S3 storage: pip install boto3") from exc
        self.bucket = os.environ.get("QINGQING_S3_BUCKET") or ""
        if not self.bucket:
            raise RuntimeError("QINGQING_S3_BUCKET is required for S3 storage")
        endpoint = os.environ.get("QINGQING_S3_ENDPOINT") or None
        region = os.environ.get("QINGQING_S3_REGION") or "us-east-1"
        access_key = os.environ.get("QINGQING_S3_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("QINGQING_S3_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
        self.prefix = (os.environ.get("QINGQING_S3_PREFIX") or "qingqing/artifacts").strip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    def write_bytes(self, kind: str, extension: str, content: bytes) -> dict:
        artifact_id = str(uuid4())
        key = f"{self.prefix}/{artifact_id}.{extension}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType="application/octet-stream")
        return {
            "id": artifact_id,
            "kind": kind,
            "storage": "s3",
            "s3_bucket": self.bucket,
            "s3_key": key,
            "size": len(content),
        }

    def resolve_local_path(self, file_path: str) -> Path | None:
        return None

    def read_bytes(self, artifact: dict) -> bytes | None:
        key = artifact.get("s3_key")
        bucket = artifact.get("s3_bucket") or self.bucket
        if not key:
            return None
        obj = self.client.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()


def get_artifact_storage() -> LocalArtifactStorage | S3ArtifactStorage:
    backend = (os.environ.get("QINGQING_ARTIFACT_BACKEND") or "local").strip().lower()
    if backend in {"s3", "minio"}:
        return S3ArtifactStorage()
    return LocalArtifactStorage()


async def fetch_remote_artifact_bytes(url: str, *, max_bytes: int = 20 * 1024 * 1024) -> bytes:
    """Download a public HTTPS artifact with SSRF checks and size limits."""
    safe_url = validate_public_https_url(url)
    return await fetch_public_https_bytes(safe_url, max_bytes=max_bytes)
