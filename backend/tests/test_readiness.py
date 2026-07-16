def test_production_readiness_requires_secrets_smtp_cors_and_durable_worker(monkeypatch):
    from qingqing_v1 import readiness

    monkeypatch.setenv("QINGQING_ENVIRONMENT", "production")
    for key in (
        "QINGQING_SESSION_SECRET",
        "QINGQING_CREDENTIAL_KEY",
        "QINGQING_SMTP_HOST",
        "CORS_ORIGINS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("QINGQING_WORKER_MODE", "background")
    monkeypatch.setattr(readiness, "_database_check", lambda: (True, "sqlite"))
    monkeypatch.setattr(readiness, "_artifact_check", lambda: (True, "local"))

    report = readiness.readiness_report()

    assert report["ready"] is False
    assert report["checks"]["session_secret"]["ok"] is False
    assert report["checks"]["credential_key"]["ok"] is False
    assert report["checks"]["smtp"]["ok"] is False
    assert report["checks"]["cors"]["ok"] is False
    assert report["checks"]["worker"]["ok"] is False


def test_readiness_is_true_when_all_required_checks_pass(monkeypatch):
    from qingqing_v1 import readiness

    monkeypatch.setenv("QINGQING_ENVIRONMENT", "production")
    monkeypatch.setenv("QINGQING_SESSION_SECRET", "s" * 32)
    monkeypatch.setenv("QINGQING_CREDENTIAL_KEY", "c" * 32)
    monkeypatch.setenv("QINGQING_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("QINGQING_WORKER_MODE", "redis")
    monkeypatch.setenv("QINGQING_ALLOW_LOCAL_USER", "false")
    monkeypatch.setattr(readiness, "_database_check", lambda: (True, "postgresql"))
    monkeypatch.setattr(readiness, "_artifact_check", lambda: (True, "s3"))
    monkeypatch.setattr(readiness, "_worker_check", lambda *_: (True, "redis"))

    report = readiness.readiness_report()

    assert report["ready"] is True
    assert all(item["ok"] for item in report["checks"].values())
