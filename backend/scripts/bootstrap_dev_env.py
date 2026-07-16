"""Create the missing local-only QingQing settings without overwriting secrets.

Run from the repository root or backend directory:
    python backend/scripts/bootstrap_dev_env.py
"""

from __future__ import annotations

import secrets
from pathlib import Path


DEV_DEFAULTS = {
    "QINGQING_ALLOW_LOCAL_USER": "true",
    "QINGQING_ENABLE_LEGACY_API": "false",
    "QINGQING_WORKER_MODE": "background",
    "QINGQING_ARTIFACT_BACKEND": "local",
    "QINGQING_SMTP_HOST": "127.0.0.1",
    "QINGQING_SMTP_PORT": "1025",
    "QINGQING_SMTP_TLS": "none",
    "QINGQING_SMTP_FROM": "noreply@qingqing.local",
    "CORS_ORIGINS": (
        "http://127.0.0.1:3001,http://localhost:3001,"
        "http://127.0.0.1:5173,http://localhost:5173"
    ),
}

SECRET_KEYS = (
    "QINGQING_SESSION_SECRET",
    "QINGQING_CREDENTIAL_KEY",
)


def _configured_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() and value.strip():
            keys.add(key.strip())
    return keys


def ensure_dev_environment(path: Path) -> list[str]:
    """Append only missing values and return the names that were added."""
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    configured = _configured_keys(original)
    additions: dict[str, str] = {}

    for key in SECRET_KEYS:
        if key not in configured:
            additions[key] = secrets.token_urlsafe(48)
    for key, value in DEV_DEFAULTS.items():
        if key not in configured:
            additions[key] = value

    if not additions:
        return []

    separator = "" if not original or original.endswith("\n") else "\n"
    block = ["", "# QingQing local development (generated; never commit .env)"]
    block.extend(f"{key}={value}" for key, value in additions.items())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(original + separator + "\n".join(block) + "\n", encoding="utf-8")
    return list(additions)


def main() -> int:
    backend_dir = Path(__file__).resolve().parents[1]
    path = backend_dir / ".env"
    added = ensure_dev_environment(path)
    if added:
        print("Configured local development keys: " + ", ".join(added))
    else:
        print("Local development environment is already configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
