import asyncio
import http.client
import hashlib
import ipaddress
import json
import os
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException


def _fernet_from_material(material: str) -> Fernet:
    import base64

    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode()).digest())
    return Fernet(key)


def _fernet() -> Fernet:
    material = os.environ.get("QINGQING_CREDENTIAL_KEY")
    if not material:
        raise RuntimeError("QINGQING_CREDENTIAL_KEY is required")
    return _fernet_from_material(material)


def _fernet_candidates() -> list[Fernet]:
    """Primary + optional previous keys for rotation (comma-separated PREVIOUS)."""
    keys: list[Fernet] = []
    primary = os.environ.get("QINGQING_CREDENTIAL_KEY")
    if primary:
        keys.append(_fernet_from_material(primary))
    previous = os.environ.get("QINGQING_CREDENTIAL_KEY_PREVIOUS", "")
    for part in previous.split(","):
        material = part.strip()
        if material:
            keys.append(_fernet_from_material(material))
    if not keys:
        raise RuntimeError("QINGQING_CREDENTIAL_KEY is required")
    return keys


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    last_error: Exception | None = None
    for fernet in _fernet_candidates():
        try:
            return fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            last_error = exc
            continue
    raise InvalidToken("unable to decrypt with current or previous keys") from last_error


@dataclass(frozen=True)
class SafeHttpResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.content)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection that pins the checked IP while preserving SNI/cert host."""

    def __init__(self, hostname: str, port: int, pinned_ip: str, timeout: float):
        super().__init__(hostname, port=port, timeout=timeout, context=ssl.create_default_context())
        self._pinned_ip = pinned_ip

    def connect(self):
        raw = socket.create_connection(
            (self._pinned_ip, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def _resolve_public_https_target(value: str):
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(422, "Base URL must be a credential-free HTTPS URL")
    port = parsed.port or 443
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        }
    except OSError:
        raise HTTPException(422, "Base URL host cannot be resolved")
    if not addresses:
        raise HTTPException(422, "Base URL host cannot be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise HTTPException(422, "Base URL must resolve only to public addresses")
    return parsed, port, sorted(addresses)[0]


def validate_public_https_url(value: str) -> str:
    _resolve_public_https_target(value)
    return value.rstrip("/")


def request_public_https(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body=None,
    max_bytes: int = 10 * 1024 * 1024,
    timeout: float = 30.0,
) -> SafeHttpResponse:
    """Send one HTTPS request to the exact public IP checked immediately above."""
    parsed, port, pinned_ip = _resolve_public_https_target(url)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    request_headers = {}
    for name, value in (headers or {}).items():
        if name.lower() == "host":
            continue
        if any(char in str(name) + str(value) for char in "\r\n\0"):
            raise HTTPException(422, "Invalid outbound header")
        request_headers[str(name)] = str(value)
    request_headers["Host"] = parsed.hostname if port == 443 else f"{parsed.hostname}:{port}"
    body = None
    if json_body is not None:
        body = json.dumps(json_body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request_headers.setdefault("Accept", "application/json")

    connection = _PinnedHTTPSConnection(parsed.hostname, port, pinned_ip, timeout)
    try:
        connection.request(method.upper(), path, body=body, headers=request_headers)
        upstream = connection.getresponse()
        if 300 <= upstream.status < 400:
            raise HTTPException(502, "Redirect refused for outbound request")
        if upstream.status >= 400:
            raise HTTPException(502, f"Remote server returned HTTP {upstream.status}")
        content = bytearray()
        while True:
            chunk = upstream.read(min(64 * 1024, max_bytes + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > max_bytes:
                raise HTTPException(413, f"Remote response exceeds {max_bytes} bytes")
        return SafeHttpResponse(
            status_code=upstream.status,
            headers={str(key).lower(): str(value) for key, value in upstream.headers.items()},
            content=bytes(content),
        )
    finally:
        connection.close()


async def request_public_https_async(*args, **kwargs) -> SafeHttpResponse:
    return await asyncio.to_thread(request_public_https, *args, **kwargs)


async def fetch_public_https_bytes(url: str, *, max_bytes: int = 20 * 1024 * 1024, timeout: float = 30.0) -> bytes:
    """GET public HTTPS content with DNS pinning, no redirects and a read cap."""
    response = await request_public_https_async(
        "GET",
        url,
        max_bytes=max_bytes,
        timeout=timeout,
    )
    return response.content
