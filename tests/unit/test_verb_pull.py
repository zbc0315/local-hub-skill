from pathlib import Path

import pytest
from click.testing import CliRunner

from hub.__main__ import cli


def _seed_with_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    ds = tmp_path / "datasets" / "tiny"
    (ds / "raw").mkdir(parents=True)
    (ds / "raw" / "src.csv").write_text("a,b\n1,2\n")
    (ds / "versions" / "v1" / "data").mkdir(parents=True)
    (ds / "versions" / "v1" / "data" / "out.csv").write_text("x\n1\n")
    (ds / "README.md").write_text("---\nslug: tiny\ntitle: T\ntags: []\nsummary: s\n"
                                  "source: {type: manual, url: '', license: unknown, retrieved_at: 2026-04-18, retrieved_by: t}\n"
                                  "raw: {path: raw/, files: []}\nversions: []\n---\n")
    return tmp_path


def test_pull_raw_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seed_with_version(tmp_path, monkeypatch)
    dest = tmp_path / "work"
    result = CliRunner().invoke(cli, ["pull", "tiny", str(dest)])
    assert result.exit_code == 0, result.output
    assert (dest / "raw" / "src.csv").read_text() == "a,b\n1,2\n"


def test_pull_version_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seed_with_version(tmp_path, monkeypatch)
    dest = tmp_path / "work"
    result = CliRunner().invoke(cli, ["pull", "tiny", "--version", "v1", str(dest)])
    assert result.exit_code == 0, result.output
    assert (dest / "out.csv").read_text() == "x\n1\n"


def test_pull_unknown_version_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seed_with_version(tmp_path, monkeypatch)
    result = CliRunner().invoke(cli, ["pull", "tiny", "--version", "nope", str(tmp_path / "w")])
    assert result.exit_code != 0
