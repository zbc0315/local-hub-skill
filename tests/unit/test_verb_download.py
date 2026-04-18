import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from hub.__main__ import cli


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.headers = {"content-length": str(len(body))}
        self.status_code = 200

    def iter_content(self, chunk_size: int = 8192):
        i = 0
        while i < len(self._body):
            yield self._body[i:i + chunk_size]
            i += chunk_size

    def raise_for_status(self) -> None:
        pass

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *a: object) -> None:
        pass


@pytest.fixture()
def added_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    CliRunner().invoke(cli, [
        "add", "tiny",
        "--source", "https://example.com/tiny.csv",
        "--title", "Tiny", "--license", "CC0-1.0",
    ])
    return tmp_path


def test_download_stages_and_commits(added_slug: Path) -> None:
    body = b"col1,col2\n1,2\n"
    with patch("hub.downloader.requests.get", return_value=FakeResponse(body)):
        result = CliRunner().invoke(cli, [
            "download", "tiny",
            "--file", "https://example.com/tiny.csv",
        ])
    assert result.exit_code == 0, result.output

    ds = added_slug / "datasets" / "tiny"
    assert (ds / "raw" / "tiny.csv").read_bytes() == body
    assert not (ds / "raw" / ".partial").exists()

    from hub.metadata import parse_readme
    fm, _ = parse_readme(ds / "README.md")
    assert fm.raw["files"] == [{
        "name": "tiny.csv",
        "sha256": hashlib.sha256(body).hexdigest(),
        "size_bytes": len(body),
    }]


def test_download_rejects_unknown_slug(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    result = CliRunner().invoke(cli, [
        "download", "missing", "--file", "https://e.com/x.csv",
    ])
    assert result.exit_code != 0


def test_download_prompts_over_threshold_and_aborts_when_declined(
    added_slug: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If size > threshold and user declines, download must not happen."""
    monkeypatch.setenv("HUB_ROOT", str(added_slug))
    # Config default is 500 MB. Override via a test config file so any small body triggers.
    cfg_dir = added_slug / ".config" / "hub"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.toml").write_text(
        f'root = "{added_slug}"\nconfirm_download_above = 5\n'
    )
    monkeypatch.setenv("HOME", str(added_slug))
    body = b"col1,col2\n1,2\n"
    with patch("hub.downloader.requests.get", return_value=FakeResponse(body)):
        result = CliRunner().invoke(cli, [
            "download", "tiny",
            "--file", "https://example.com/tiny.csv",
        ], input="n\n")
    assert result.exit_code != 0
    ds = added_slug / "datasets" / "tiny"
    assert not (ds / "raw" / "tiny.csv").exists()


def test_download_prompts_over_threshold_and_proceeds_when_accepted(
    added_slug: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_dir = added_slug / ".config" / "hub"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.toml").write_text(
        f'root = "{added_slug}"\nconfirm_download_above = 5\n'
    )
    monkeypatch.setenv("HOME", str(added_slug))
    monkeypatch.setenv("HUB_ROOT", str(added_slug))
    body = b"col1,col2\n1,2\n"
    with patch("hub.downloader.requests.get", return_value=FakeResponse(body)):
        result = CliRunner().invoke(cli, [
            "download", "tiny",
            "--file", "https://example.com/tiny.csv",
        ], input="y\n")
    assert result.exit_code == 0, result.output
    ds = added_slug / "datasets" / "tiny"
    assert (ds / "raw" / "tiny.csv").read_bytes() == body
