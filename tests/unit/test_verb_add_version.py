import hashlib
import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from hub.__main__ import cli
from hub.metadata import parse_readme, read_manifest


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
    def iter_content(self, chunk_size: int = 8192):
        i = 0
        while i < len(self._body):
            yield self._body[i:i + chunk_size]; i += chunk_size
    def raise_for_status(self) -> None: ...
    def __enter__(self) -> "FakeResponse": return self
    def __exit__(self, *a: object) -> None: ...


def _seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    CliRunner().invoke(cli, [
        "add", "tiny", "--source", "https://e.com/tiny.csv",
        "--title", "Tiny", "--license", "CC0-1.0",
    ])
    body = b"col1\n1\n2\n"
    with patch("hub.downloader.requests.get", return_value=FakeResponse(body)):
        CliRunner().invoke(cli, [
            "download", "tiny", "--file", "https://e.com/tiny.csv",
        ])
    return tmp_path


def _write_script(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "script.py"
    p.write_text("#!" + sys.executable + "\n" + body)
    p.chmod(0o755)
    return p


def test_add_version_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path, monkeypatch)

    script = _write_script(tmp_path, (
        "import os, json, shutil\n"
        "src = os.path.join(os.environ['HUB_INPUT_DIR'], 'tiny.csv')\n"
        "dst = os.path.join(os.environ['HUB_OUTPUT_DIR'], 'cleaned.csv')\n"
        "shutil.copy(src, dst)\n"
        "json.dump([{'name':'col1','type':'int64'}], open(os.path.join(os.environ['HUB_OUTPUT_DIR'], 'schema.json'),'w'))\n"
    ))

    result = CliRunner().invoke(cli, [
        "add-version", "tiny", "cleaned-2026-04",
        "--script", str(script), "--input", "raw",
    ])
    assert result.exit_code == 0, result.output

    ds = tmp_path / "datasets" / "tiny"
    vdir = ds / "versions" / "cleaned-2026-04"
    assert (vdir / "data" / "cleaned.csv").exists()
    assert (vdir / "script.py").exists()
    manifest = read_manifest(vdir / "manifest.json")
    assert manifest["name"] == "cleaned-2026-04"
    assert manifest["input_version"] == "raw"
    assert manifest["schema"] == [{"name": "col1", "type": "int64"}]

    assert not (ds / "versions" / "cleaned-2026-04.partial").exists()

    fm, _ = parse_readme(ds / "README.md")
    names = [v["name"] for v in fm.versions]
    assert "cleaned-2026-04" in names


def test_add_version_script_failure_leaves_no_partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path, monkeypatch)
    script = _write_script(tmp_path, "import sys; sys.exit(2)\n")
    result = CliRunner().invoke(cli, [
        "add-version", "tiny", "bad", "--script", str(script), "--input", "raw",
    ])
    assert result.exit_code != 0
    ds = tmp_path / "datasets" / "tiny"
    assert not (ds / "versions" / "bad").exists()
    assert not (ds / "versions" / "bad.partial").exists()


def test_add_version_refuses_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path, monkeypatch)
    script = _write_script(tmp_path, (
        "import os, json\n"
        "open(os.path.join(os.environ['HUB_OUTPUT_DIR'], 'x.txt'), 'w').write('x')\n"
        "json.dump([], open(os.path.join(os.environ['HUB_OUTPUT_DIR'], 'schema.json'),'w'))\n"
    ))
    runner = CliRunner()
    first = runner.invoke(cli, [
        "add-version", "tiny", "v1", "--script", str(script), "--input", "raw",
    ])
    assert first.exit_code == 0, first.output
    second = runner.invoke(cli, [
        "add-version", "tiny", "v1", "--script", str(script), "--input", "raw",
    ])
    assert second.exit_code != 0
    assert "already exists" in second.output.lower()
