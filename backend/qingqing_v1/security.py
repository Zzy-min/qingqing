import hashlib
import ipaddress
import os
import socket
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from fastapi import HTTPException


def _fernet() -> Fernet:
    material = os.environ.get("QINGQING_CREDENTIAL_KEY")
    if not material:
        raise RuntimeError("QINGQING_CREDENTIAL_KEY is required")
    import base64
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


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
