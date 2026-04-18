from pathlib import Path

import pytest

from hub.config import Config, load_config


def test_load_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / ".config" / "hub"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.toml").write_text(
        'root = "/srv/data-hub"\n'
        "confirm_download_above = 524288000\n"
        "script_timeout = 7200\n"
        'log_level = "info"\n'
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)

    cfg = load_config()
    assert cfg.root == "/srv/data-hub"
    assert cfg.confirm_download_above == 524288000
    assert cfg.script_timeout == 7200
    assert cfg.log_level == "info"


def test_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / ".config" / "hub"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.toml").write_text('root = "/srv/data-hub"\n')
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HUB_ROOT", "user@host:/other/path")

    cfg = load_config()
    assert cfg.root == "user@host:/other/path"


def test_defaults_when_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HUB_ROOT", "/tmp/hub")

    cfg = load_config()
    assert cfg.root == "/tmp/hub"
    assert cfg.confirm_download_above == 500 * 1024 * 1024
    assert cfg.script_timeout == 7200
    assert cfg.log_level == "info"


def test_missing_root_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("HUB_ROOT", raising=False)

    with pytest.raises(Config.MissingRoot):
        load_config()
