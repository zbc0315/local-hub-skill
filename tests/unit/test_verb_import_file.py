"""Tests for `hub import-file` — copy an existing local file into a dataset's raw/."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from click.testing import CliRunner

from hub.__main__ import cli
from hub.metadata import parse_readme


@pytest.fixture()
def seeded_hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A hub with one empty dataset slug already registered."""
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    result = CliRunner().invoke(cli, [
        "add", "iris",
        "--source", "https://example.com/iris",
        "--title", "Iris",
        "--license", "public-domain",
    ])
    assert result.exit_code == 0, result.output
    return tmp_path


def test_import_file_copies_and_records(seeded_hub: Path, tmp_path: Path) -> None:
    """File is copied into raw/ and recorded in README frontmatter with sha256+size."""
    src = tmp_path / "iris.data"
    body = b"5.1,3.5,1.4,0.2,Iris-setosa\n"
    src.write_bytes(body)

    result = CliRunner().invoke(cli, ["import-file", "iris", str(src)])
    assert result.exit_code == 0, result.output

    final = seeded_hub / "datasets" / "iris" / "raw" / "iris.data"
    assert final.exists()
    assert final.read_bytes() == body
    assert not (seeded_hub / "datasets" / "iris" / "raw" / ".partial").exists()

    fm, _ = parse_readme(seeded_hub / "datasets" / "iris" / "README.md")
    assert fm.raw["files"] == [{
        "name": "iris.data",
        "sha256": hashlib.sha256(body).hexdigest(),
        "size_bytes": len(body),
    }]


def test_import_file_triggers_reindex(seeded_hub: Path, tmp_path: Path) -> None:
    """INDEX.md mentions the slug after import (reindex was called)."""
    src = tmp_path / "iris.data"
    src.write_bytes(b"x")
    CliRunner().invoke(cli, ["import-file", "iris", str(src)])
    idx = (seeded_hub / "INDEX.md").read_text(encoding="utf-8")
    assert "iris" in idx


def test_import_file_rejects_missing_source(seeded_hub: Path, tmp_path: Path) -> None:
    """Source that doesn't exist ⇒ click refuses at the Path type check."""
    result = CliRunner().invoke(cli, [
        "import-file", "iris", str(tmp_path / "does-not-exist.txt"),
    ])
    assert result.exit_code != 0


def test_import_file_rejects_directory_source(seeded_hub: Path, tmp_path: Path) -> None:
    """Source that's a directory ⇒ refused."""
    src_dir = tmp_path / "somedir"
    src_dir.mkdir()
    result = CliRunner().invoke(cli, ["import-file", "iris", str(src_dir)])
    assert result.exit_code != 0


def test_import_file_rejects_unknown_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Slug not registered ⇒ clear error."""
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    src = tmp_path / "file.txt"
    src.write_bytes(b"x")
    result = CliRunner().invoke(cli, ["import-file", "no-such-slug", str(src)])
    assert result.exit_code != 0
    assert "no-such-slug" in result.output.lower() or "no dataset" in result.output.lower()


def test_import_file_refuses_duplicate_name(seeded_hub: Path, tmp_path: Path) -> None:
    """Re-importing a file with the same target name ⇒ error (no silent overwrite)."""
    src = tmp_path / "iris.data"
    src.write_bytes(b"v1")
    runner = CliRunner()
    first = runner.invoke(cli, ["import-file", "iris", str(src)])
    assert first.exit_code == 0
    src.write_bytes(b"v2-different")
    second = runner.invoke(cli, ["import-file", "iris", str(src)])
    assert second.exit_code != 0
    assert "already exists" in second.output.lower()


def test_import_file_as_renames_target(seeded_hub: Path, tmp_path: Path) -> None:
    """`--as <name>` overrides the filename used in the raw/ directory."""
    src = tmp_path / "8664388"  # figshare-style numeric-id source name
    src.write_bytes(b"<xml?><schema/>")
    result = CliRunner().invoke(cli, [
        "import-file", "iris", str(src), "--as", "cml_xsd.zip",
    ])
    assert result.exit_code == 0, result.output
    assert (seeded_hub / "datasets" / "iris" / "raw" / "cml_xsd.zip").exists()
    assert not (seeded_hub / "datasets" / "iris" / "raw" / "8664388").exists()

    fm, _ = parse_readme(seeded_hub / "datasets" / "iris" / "README.md")
    assert fm.raw["files"][0]["name"] == "cml_xsd.zip"


def test_import_file_rejects_remote_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With a remote HUB_ROOT, import-file refuses — file paths on client aren't on server."""
    monkeypatch.setenv("HUB_ROOT", "jim@nas.lan:/srv/data-hub")
    monkeypatch.setenv("HUB_REMOTE_DISPATCH", "1")  # prevent ssh dispatch attempt
    src = tmp_path / "f.txt"
    src.write_bytes(b"x")
    result = CliRunner().invoke(cli, ["import-file", "anything", str(src)])
    assert result.exit_code != 0
    assert "remote" in result.output.lower()
