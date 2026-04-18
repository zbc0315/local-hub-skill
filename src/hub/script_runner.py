from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


class ScriptFailed(RuntimeError):
    pass


class ScriptTimeout(RuntimeError):
    pass


def run_script(
    script: Path,
    *,
    input_dir: Path,
    output_dir: Path,
    timeout: int,
) -> None:
    """Execute `script` with HUB_INPUT_DIR / HUB_OUTPUT_DIR env vars.

    - cwd is a temp dir *outside* output_dir (not a hub subdirectory).
    - Timeout kills the process group.
    """
    env = os.environ.copy()
    env["HUB_INPUT_DIR"] = str(input_dir.resolve())
    env["HUB_OUTPUT_DIR"] = str(output_dir.resolve())

    with tempfile.TemporaryDirectory(prefix="hub-script-") as cwd:
        try:
            subprocess.run(
                [sys.executable, str(script)],
                cwd=cwd,
                env=env,
                timeout=timeout,
                check=True,
                start_new_session=True,
            )
        except subprocess.TimeoutExpired as e:
            raise ScriptTimeout(f"script exceeded {timeout}s timeout") from e
        except subprocess.CalledProcessError as e:
            raise ScriptFailed(f"script exited with code {e.returncode}") from e
