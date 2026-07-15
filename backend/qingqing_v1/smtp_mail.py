"""SMTP delivery for login verification codes."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

from fastapi import HTTPException


def smtp_configured() -> bool:
    return bool((os.environ.get("QINGQING_SMTP_HOST") or "").strip())


def build_login_message(email: str, code: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = os.environ.get("QINGQING_SMTP_SUBJECT", "轻青登录验证码")
    message["From"] = os.environ.get("QINGQING_SMTP_FROM", "noreply@qingqing.local")
    message["To"] = email
    message.set_content(
        f"你的轻青登录验证码是 {code}，10 分钟内有效。请勿转发给他人。\n\n"
        f"如果不是你本人操作，请忽略此邮件。"
    )
    return message


def send_login_email(email: str, code: str) -> dict:
    """Send verification code via SMTP.

    Env:
      QINGQING_SMTP_HOST (required to send)
      QINGQING_SMTP_PORT (default 587)
      QINGQING_SMTP_USERNAME / QINGQING_SMTP_PASSWORD (optional)
      QINGQING_SMTP_FROM
      QINGQING_SMTP_TLS: starttls | ssl | none  (default: starttls; port 465 -> ssl if unset)
    """
    host = (os.environ.get("QINGQING_SMTP_HOST") or "").strip()
    if not host:
        if os.environ.get("QINGQING_ALLOW_LOCAL_USER", "false").lower() == "true":
            return {"delivered": False, "mode": "local_skip"}
        raise HTTPException(503, "Email service is not configured")

    port = int(os.environ.get("QINGQING_SMTP_PORT", "587"))
    tls_mode = (os.environ.get("QINGQING_SMTP_TLS") or "").strip().lower()
    if not tls_mode:
        tls_mode = "ssl" if port == 465 else ("none" if port in {25, 1025, 2525} else "starttls")

    message = build_login_message(email, code)
    username = os.environ.get("QINGQING_SMTP_USERNAME")
    password = os.environ.get("QINGQING_SMTP_PASSWORD")

    try:
        if tls_mode == "ssl":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as client:
                if username and password:
                    client.login(username, password)
                client.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=15) as client:
                client.ehlo()
                if tls_mode == "starttls":
                    context = ssl.create_default_context()
                    client.starttls(context=context)
                    client.ehlo()
                if username and password:
                    client.login(username, password)
                client.send_message(message)
    except Exception as exc:
        # Do not leak SMTP credentials or raw stack to clients.
        raise HTTPException(502, f"Email delivery failed: {type(exc).__name__}") from exc

    return {"delivered": True, "mode": tls_mode, "host": host, "port": port}
