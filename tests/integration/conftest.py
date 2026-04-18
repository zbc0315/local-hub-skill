import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _ssh_localhost_available() -> bool:
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
         "localhost", "true"],
        capture_output=True,
    )
    return r.returncode == 0


SSH_OK = _ssh_localhost_available()
USERNAME = os.environ.get("USER", "user")


@pytest.fixture()
def local_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture()
def remote_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    if not SSH_OK:
        pytest.skip("ssh localhost unavailable")
    monkeypatch.setenv("HUB_ROOT", f"{USERNAME}@localhost:{tmp_path}")
    return tmp_path
