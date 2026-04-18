from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner

from hub.__main__ import cli
from hub.metadata import parse_readme


def test_add_creates_stub_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))

    result = CliRunner().invoke(cli, [
        "add", "covid-jhu",
        "--source", "https://example.com/x",
        "--title", "JHU COVID",
        "--tags", "timeseries,health",
        "--license", "CC-BY-4.0",
    ])
    assert result.exit_code == 0, result.output

    ds = tmp_path / "datasets" / "covid-jhu"
    assert ds.is_dir()
    assert (ds / "raw").is_dir()
    assert (ds / "versions").is_dir()

    fm, body = parse_readme(ds / "README.md")
    assert fm.slug == "covid-jhu"
    assert fm.title == "JHU COVID"
    assert fm.tags == ["timeseries", "health"]
    assert fm.source["type"] == "url"
    assert fm.source["url"] == "https://example.com/x"
    assert fm.source["license"] == "CC-BY-4.0"
    assert fm.raw["files"] == []
    assert fm.versions == []

    idx = (tmp_path / "INDEX.md").read_text()
    assert "covid-jhu" in idx


def test_add_rejects_duplicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    runner = CliRunner()
    runner.invoke(cli, ["add", "x", "--source", "https://e.com", "--title", "X"])
    result = runner.invoke(cli, ["add", "x", "--source", "https://e.com", "--title", "X"])
    assert result.exit_code != 0
    assert "already exists" in result.output.lower()


def test_add_unknown_license_warns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """License=unknown must produce a warning on stderr (not just anywhere)."""
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, [
        "add", "x", "--source", "https://e.com", "--title", "X",
    ], catch_exceptions=False)
    assert result.exit_code == 0
    # Check that a warning about unknown license was printed
    output = result.output.lower()
    assert "warning" in output
    assert "license" in output


def test_add_known_license_no_warn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, [
        "add", "y", "--source", "https://e.com", "--title", "Y",
        "--license", "CC-BY-4.0",
    ], catch_exceptions=False)
    assert result.exit_code == 0
    assert "warning" not in result.output.lower()


def test_add_invalid_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    result = CliRunner().invoke(cli, [
        "add", "BAD SLUG", "--source", "https://e.com", "--title", "X",
    ])
    assert result.exit_code != 0
