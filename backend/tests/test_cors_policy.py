import pytest

from main import LOCAL_CORS_ORIGINS, resolve_cors_origins


def test_development_uses_local_origins_when_not_configured():
    assert resolve_cors_origins("development", None) == LOCAL_CORS_ORIGINS


def test_production_has_no_implicit_localhost_origins():
    assert resolve_cors_origins("production", None) == []


def test_configured_origins_replace_defaults_and_are_deduplicated():
    assert resolve_cors_origins(
        "production",
        "https://app.qingqing.example,https://app.qingqing.example/",
    ) == ["https://app.qingqing.example"]


def test_configured_origin_rejects_paths():
    with pytest.raises(RuntimeError, match="Invalid CORS origin"):
        resolve_cors_origins("production", "https://app.qingqing.example/path")
