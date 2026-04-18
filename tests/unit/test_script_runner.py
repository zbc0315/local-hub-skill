import json
import os
import sys
from pathlib import Path

import pytest

from hub.script_runner import run_script, ScriptFailed, ScriptTimeout


def _write_script(path: Path, body: str) -> None:
    path.write_text("#!" + sys.executable + "\n" + body)
    path.chmod(0o755)


def test_run_script_success(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "source.txt").write_text("hello")
    out_dir = tmp_path / "out.partial"
    out_dir.mkdir()

    script = tmp_path / "s.py"
    _write_script(script, (
        "import os, json, shutil\n"
        "shutil.copy(os.path.join(os.environ['HUB_INPUT_DIR'], 'source.txt'),\n"
        "            os.path.join(os.environ['HUB_OUTPUT_DIR'], 'out.txt'))\n"
        "json.dump([{'name': 'x', 'type': 'string'}],\n"
        "          open(os.path.join(os.environ['HUB_OUTPUT_DIR'], 'schema.json'), 'w'))\n"
    ))

    run_script(script, input_dir=in_dir, output_dir=out_dir, timeout=10)
    assert (out_dir / "out.txt").read_text() == "hello"
    assert json.loads((out_dir / "schema.json").read_text()) == [{"name": "x", "type": "string"}]


def test_run_script_failure_raises(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"; in_dir.mkdir()
    out_dir = tmp_path / "out.partial"; out_dir.mkdir()
    script = tmp_path / "s.py"
    _write_script(script, "import sys; sys.exit(3)\n")

    with pytest.raises(ScriptFailed):
        run_script(script, input_dir=in_dir, output_dir=out_dir, timeout=10)


def test_run_script_timeout_kills(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"; in_dir.mkdir()
    out_dir = tmp_path / "out.partial"; out_dir.mkdir()
    script = tmp_path / "s.py"
    _write_script(script, "import time; time.sleep(30)\n")

    with pytest.raises(ScriptTimeout):
        run_script(script, input_dir=in_dir, output_dir=out_dir, timeout=1)


def test_run_script_cwd_is_tempdir_outside_out_dir(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"; in_dir.mkdir()
    out_dir = tmp_path / "out.partial"; out_dir.mkdir()
    script = tmp_path / "s.py"
    _write_script(script, (
        "import os, json\n"
        "cwd = os.getcwd()\n"
        "out = os.environ['HUB_OUTPUT_DIR']\n"
        "assert not cwd.startswith(out), f'cwd={cwd} is under out={out}'\n"
        "with open(os.path.join(out, 'schema.json'), 'w') as f: json.dump([], f)\n"
    ))
    run_script(script, input_dir=in_dir, output_dir=out_dir, timeout=10)
