from pathlib import Path

import pytest
from click.testing import CliRunner

from hub.__main__ import cli


def test_rm_requires_yes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    CliRunner().invoke(cli, ["add", "tiny", "--source", "https://e.com/x",
                             "--title", "T", "--license", "CC0-1.0"])
    result = CliRunner().invoke(cli, ["rm", "tiny"])
    assert result.exit_code != 0
    assert (tmp_path / "datasets" / "tiny").exists()


def test_rm_removes_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    CliRunner().invoke(cli, ["add", "tiny", "--source", "https://e.com/x",
                             "--title", "T", "--license", "CC0-1.0"])
    result = CliRunner().invoke(cli, ["rm", "tiny", "--yes"])
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "datasets" / "tiny").exists()
    assert not (tmp_path / "datasets" / "tiny.deleting").exists()

    idx = (tmp_path / "INDEX.md").read_text()
    assert "tiny" not in idx
