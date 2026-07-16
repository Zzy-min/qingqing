from pathlib import Path

import pytest

import main


def _write_index(root: Path, relative: str, content: str = "index") -> Path:
    target = root / relative
    target.mkdir(parents=True)
    (target / "index.html").write_text(content, encoding="utf-8")
    return target


def test_flutter_is_the_default_and_never_falls_back_to_react(tmp_path, monkeypatch):
    react = _write_index(tmp_path, "frontend/dist")
    monkeypatch.delenv("QINGQING_WEB_CLIENT", raising=False)

    assert main._resolve_static_path(tmp_path) is None

    flutter = _write_index(tmp_path, "apps/qingqing_flutter/build/web")
    assert main._resolve_static_path(tmp_path) == str(flutter)
    assert main._resolve_static_path(tmp_path) != str(react)


def test_react_workbench_requires_explicit_selection(tmp_path, monkeypatch):
    react = _write_index(tmp_path, "frontend/dist")
    _write_index(tmp_path, "apps/qingqing_flutter/build/web")
    monkeypatch.setenv("QINGQING_WEB_CLIENT", "react")

    assert main._resolve_static_path(tmp_path) == str(react)


def test_none_disables_static_web_serving(tmp_path, monkeypatch):
    _write_index(tmp_path, "apps/qingqing_flutter/build/web")
    monkeypatch.setenv("QINGQING_WEB_CLIENT", "none")

    assert main._resolve_static_path(tmp_path) is None


def test_invalid_web_client_fails_fast(tmp_path, monkeypatch):
    monkeypatch.setenv("QINGQING_WEB_CLIENT", "newest")

    with pytest.raises(RuntimeError, match="QINGQING_WEB_CLIENT"):
        main._resolve_static_path(tmp_path)
