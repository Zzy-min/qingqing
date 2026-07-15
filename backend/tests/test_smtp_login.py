"""SMTP mailer unit tests + optional MailHog closed-loop."""

from __future__ import annotations

import base64
import os
import quopri
import re
import socket
import sys
import time
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("QINGQING_CREDENTIAL_KEY", "test-only-key-material-for-smtp")
os.environ.setdefault("QINGQING_SESSION_SECRET", "test-session-secret-16+")
os.environ["QINGQING_ALLOW_LOCAL_USER"] = "true"

from test_qingqing_v1 import client as client_fixture  # noqa: E402
from qingqing_v1.store import store  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    store.reset()


def test_smtp_send_login_email_none_tls(monkeypatch):
    from qingqing_v1 import smtp_mail

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=15):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def ehlo(self):
            pass

        def starttls(self, context=None):
            raise AssertionError("starttls should not run for tls=none")

        def login(self, u, p):
            sent["login"] = (u, p)

        def send_message(self, message):
            sent["to"] = message["To"]
            sent["body"] = message.get_content()

    monkeypatch.setenv("QINGQING_SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("QINGQING_SMTP_PORT", "1025")
    monkeypatch.setenv("QINGQING_SMTP_TLS", "none")
    monkeypatch.setattr(smtp_mail.smtplib, "SMTP", FakeSMTP)
    result = smtp_mail.send_login_email("user@example.com", "123456")
    assert result["delivered"] is True
    assert result["mode"] == "none"
    assert sent["to"] == "user@example.com"
    assert "123456" in sent["body"]


def test_request_code_delivery_metadata_local(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    monkeypatch.delenv("QINGQING_SMTP_HOST", raising=False)
    resp = client_fixture.post("/api/v1/auth/email/request-code", json={"email": "Creator@Example.com"})
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] is True
    assert body["delivery"]["delivered"] is False
    assert body["delivery"]["mode"] == "local_skip"
    assert re.fullmatch(r"\d{6}", body["dev_code"])


def test_login_closed_loop_with_dev_code(client_fixture, monkeypatch):
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    monkeypatch.setenv("QINGQING_SESSION_SECRET", "test-session-secret-16+")
    monkeypatch.delenv("QINGQING_SMTP_HOST", raising=False)
    requested = client_fixture.post("/api/v1/auth/email/request-code", json={"email": "loop@example.com"})
    code = requested.json()["dev_code"]
    verified = client_fixture.post(
        "/api/v1/auth/email/verify",
        json={"email": "loop@example.com", "code": code},
    )
    assert verified.status_code == 200
    token = verified.json()["access_token"]
    models = client_fixture.get("/api/v1/models", headers={"Authorization": f"Bearer {token}"})
    assert models.status_code == 200
    assert "models" in models.json()


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _decode_mailhog_body(content: dict) -> str:
    """MailHog returns raw transfer-encoded Body; decode base64 / QP for assertions."""
    raw = content.get("Body") or ""
    headers = content.get("Headers") or {}
    cte = " ".join(headers.get("Content-Transfer-Encoding") or ["7bit"]).lower()
    if "base64" in cte:
        compact = re.sub(r"\s+", "", raw)
        try:
            return base64.b64decode(compact).decode("utf-8", errors="replace")
        except Exception:
            return raw
    if "quoted-printable" in cte:
        try:
            return quopri.decodestring(raw.encode("utf-8", errors="replace")).decode(
                "utf-8", errors="replace"
            )
        except Exception:
            return raw
    return raw


def _extract_login_code_from_mailhog(item: dict, email: str) -> str | None:
    content = item.get("Content") or {}
    headers = content.get("Headers") or {}
    to_list = headers.get("To") or []
    raw_to = ((item.get("Raw") or {}).get("To")) or []
    recipients = [str(t) for t in (*to_list, *raw_to)]
    if not any(email in t for t in recipients):
        return None
    text = _decode_mailhog_body(content)
    # Prefer explicit phrase, then any 6-digit token.
    m = re.search(r"验证码是\s*(\d{6})", text) or re.search(r"(?<!\d)(\d{6})(?!\d)", text)
    return m.group(1) if m else None


@pytest.mark.skipif(
    (os.environ.get("QINGQING_RUN_INTEGRATION") or "").lower() not in {"1", "true", "yes"},
    reason="set QINGQING_RUN_INTEGRATION=1",
)
def test_mailhog_smtp_closed_loop(client_fixture, monkeypatch):
    """Full SMTP path: send via MailHog -> read API -> verify -> auth API."""
    if not _port_open("127.0.0.1", 1025) or not _port_open("127.0.0.1", 8025):
        pytest.skip("MailHog not running on 1025/8025")

    import httpx

    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "true")
    monkeypatch.setenv("QINGQING_SESSION_SECRET", "test-session-secret-16+")
    monkeypatch.setenv("QINGQING_SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("QINGQING_SMTP_PORT", "1025")
    monkeypatch.setenv("QINGQING_SMTP_TLS", "none")
    monkeypatch.setenv("QINGQING_SMTP_FROM", "noreply@qingqing.local")

    # Clear MailHog inbox
    httpx.delete("http://127.0.0.1:8025/api/v1/messages", timeout=5)

    email = f"smtp-loop-{int(time.time())}@example.com"
    requested = client_fixture.post("/api/v1/auth/email/request-code", json={"email": email})
    assert requested.status_code == 202
    body = requested.json()
    assert body["delivery"]["delivered"] is True
    assert body["delivery"]["mode"] == "none"
    # Must not rely on dev_code for this proof — but it may still be present on loopback.
    dev_code = body.get("dev_code")

    # Pull code from MailHog (not from dev_code — prove real SMTP path)
    code = None
    for _ in range(20):
        inbox = httpx.get("http://127.0.0.1:8025/api/v2/messages", timeout=5).json()
        for item in inbox.get("items") or []:
            code = _extract_login_code_from_mailhog(item, email)
            if code:
                break
        if code:
            break
        time.sleep(0.25)
    assert code, "verification code not found in MailHog (decoded body)"
    if dev_code:
        assert code == dev_code, "MailHog code must match issued code"

    verified = client_fixture.post("/api/v1/auth/email/verify", json={"email": email, "code": code})
    assert verified.status_code == 200
    token = verified.json()["access_token"]
    me = client_fixture.get("/api/v1/me/entitlements", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["plan"] in {"free", "vip"}
