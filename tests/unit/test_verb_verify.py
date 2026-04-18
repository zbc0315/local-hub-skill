import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from hub.__main__ import cli


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
    def iter_content(self, chunk_size: int = 8192):
        i = 0
        while i < len(self._body):
            yield self._body[i:i + chunk_size]; i += chunk_size
    def raise_for_status(self) -> None: ...
    def __enter__(self): return self
    def __exit__(self, *a): ...


def _seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    CliRunner().invoke(cli, ["add", "tiny", "--source", "https://e.com/x.csv",
                             "--title", "T", "--license", "CC0-1.0"])
    body = b"col\n1\n"
    with patch("hub.downloader.requests.get", return_value=FakeResponse(body)):
        CliRunner().invoke(cli, ["download", "tiny", "--file", "https://e.com/x.csv"])
    return tmp_path


def test_verify_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path, monkeypatch)
    result = CliRunner().invoke(cli, ["verify", "tiny"])
    assert result.exit_code == 0, result.output
    assert "ok" in result.output.lower()


def test_verify_detects_tampering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seed(tmp_path, monkeypatch)
    target = root / "datasets" / "tiny" / "raw" / "x.csv"
    target.write_text("TAMPERED")
    result = CliRunner().invoke(cli, ["verify", "tiny"])
    assert result.exit_code != 0
    assert "x.csv" in result.output


def test_verify_all_slugs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path, monkeypatch)
    result = CliRunner().invoke(cli, ["verify"])
    assert result.exit_code == 0, result.output
