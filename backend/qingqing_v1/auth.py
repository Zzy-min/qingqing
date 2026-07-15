import base64, hashlib, hmac, json, os, time

def _b64(data: bytes) -> str: return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
def _decode(value: str) -> bytes: return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def create_session_token(user_id: str, expires_in: int = 3600) -> str:
    payload = _b64(json.dumps({"sub": user_id, "exp": int(time.time()) + expires_in}, separators=(",", ":")).encode())
    secret = os.environ.get("QINGQING_SESSION_SECRET", "")
    if len(secret) < 16: raise RuntimeError("QINGQING_SESSION_SECRET must be at least 16 characters")
    return payload + "." + _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())

def verify_session_token(token: str) -> dict:
    try:
        payload, signature = token.split(".", 1)
        secret = os.environ.get("QINGQING_SESSION_SECRET", "")
        if len(secret) < 16:
            raise ValueError("session secret is not configured")
        expected = _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected): raise ValueError("invalid signature")
        claims = json.loads(_decode(payload))
        if claims["exp"] <= time.time(): raise ValueError("expired")
        return claims
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid session token") from exc


def hash_login_code(email: str, code: str) -> str:
    secret = os.environ.get("QINGQING_SESSION_SECRET", "")
    if len(secret) < 16: raise RuntimeError("QINGQING_SESSION_SECRET must be at least 16 characters")
    return hmac.new(secret.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()
