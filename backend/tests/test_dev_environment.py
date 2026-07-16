from pathlib import Path

from scripts.bootstrap_dev_env import DEV_DEFAULTS, SECRET_KEYS, ensure_dev_environment


def test_bootstrap_adds_missing_values_without_overwriting_existing_secret(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("MINIMAX_API_KEY=keep-me\nQINGQING_SESSION_SECRET=existing\n", encoding="utf-8")

    added = ensure_dev_environment(env_file)
    content = env_file.read_text(encoding="utf-8")

    assert "MINIMAX_API_KEY=keep-me" in content
    assert content.count("QINGQING_SESSION_SECRET=") == 1
    assert "QINGQING_SESSION_SECRET=existing" in content
    assert "QINGQING_CREDENTIAL_KEY" in added
    assert all(key in content for key in DEV_DEFAULTS)


def test_bootstrap_is_idempotent(tmp_path: Path):
    env_file = tmp_path / ".env"

    first = ensure_dev_environment(env_file)
    first_content = env_file.read_text(encoding="utf-8")
    second = ensure_dev_environment(env_file)

    assert set(SECRET_KEYS).issubset(first)
    assert second == []
    assert env_file.read_text(encoding="utf-8") == first_content
