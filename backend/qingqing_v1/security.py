import hashlib
import ipaddress
import os
import socket
from urllib.parse import urlparse

import httpx
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


def validate_public_https_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(422, "Base URL must be a credential-free HTTPS URL")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)}
    except OSError:
        raise HTTPException(422, "Base URL host cannot be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise HTTPException(422, "Base URL must resolve only to public addresses")
    return value.rstrip("/")


async def fetch_public_https_bytes(url: str, *, max_bytes: int = 20 * 1024 * 1024, timeout: float = 30.0) -> bytes:
    """GET public HTTPS content with redirect disabled and body size cap."""
    safe = validate_public_https_url(url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await client.get(safe)
        if 300 <= response.status_code < 400:
            raise HTTPException(502, "Redirect refused for remote artifact")
        response.raise_for_status()
        content = response.content
        if len(content) > max_bytes:
            raise HTTPException(413, f"Remote artifact exceeds {max_bytes} bytes")
        return content
