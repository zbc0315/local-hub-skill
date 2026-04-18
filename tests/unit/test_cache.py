import hashlib
from pathlib import Path

import pytest

from hub.cache import hub_id, cache_dir_for, read_cached_index, write_cached_index


def test_hub_id_is_sha1_of_root() -> None:
    assert hub_id("jim@host:/a") == hashlib.sha1(b"jim@host:/a").hexdigest()


def test_cache_dir_includes_hub_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    d = cache_dir_for("jim@host:/a")
    assert str(d).startswith(str(tmp_path / ".cache" / "hub"))


def test_write_and_read_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    write_cached_index("jim@host:/a", "INDEX CONTENT\n")
    got = read_cached_index("jim@host:/a")
    assert got == "INDEX CONTENT\n"


def test_read_cache_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert read_cached_index("unknown") is None


import sys
from unittest.mock import patch, MagicMock


def test_list_falls_back_to_cache_on_ssh_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HUB_ROOT", "jim@host:/srv")
    monkeypatch.delenv("HUB_REMOTE_DISPATCH", raising=False)
    write_cached_index("jim@host:/srv", "CACHED INDEX\n")

    monkeypatch.setattr(sys, "argv", ["hub", "list"])
    fake = MagicMock()
    fake.returncode = 255
    fake.stdout = b""
    fake.stderr = b"ssh: connect error\n"
    with patch("hub.remote.subprocess.run", return_value=fake):
        from hub.__main__ import main
        with pytest.raises(SystemExit) as ex:
            main()
    assert ex.value.code == 0
    captured = capsys.readouterr()
    assert "CACHED INDEX" in captured.out
    assert "offline" in captured.err.lower()


def test_list_filtered_by_tag_is_not_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`hub list --tag X` output must NOT overwrite the full cached INDEX."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HUB_ROOT", "jim@host:/srv")
    monkeypatch.delenv("HUB_REMOTE_DISPATCH", raising=False)
    write_cached_index("jim@host:/srv", "FULL INDEX\n")

    monkeypatch.setattr(sys, "argv", ["hub", "list", "--tag", "nlp"])
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = b"FILTERED\n"
    fake.stderr = b""
    with patch("hub.remote.subprocess.run", return_value=fake):
        from hub.__main__ import main
        with pytest.raises(SystemExit):
            main()

    assert read_cached_index("jim@host:/srv") == "FULL INDEX\n"


def test_show_fails_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HUB_ROOT", "jim@host:/srv")
    monkeypatch.delenv("HUB_REMOTE_DISPATCH", raising=False)

    monkeypatch.setattr(sys, "argv", ["hub", "show", "covid-jhu"])
    fake = MagicMock()
    fake.returncode = 255
    fake.stdout = b""
    fake.stderr = b"ssh: connect error\n"
    with patch("hub.remote.subprocess.run", return_value=fake):
        from hub.__main__ import main
        with pytest.raises(SystemExit) as ex:
            main()
    assert ex.value.code != 0
    assert "offline" in capsys.readouterr().err.lower()
