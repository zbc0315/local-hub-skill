from __future__ import annotations

import subprocess
import sys
from typing import Sequence

SSH_OPTS = [
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=10",
]


def build_ssh_argv(*, user: str, host: str, remote_hub_cmd: Sequence[str]) -> list[str]:
    # Wrap the remote command in `env HUB_REMOTE_DISPATCH=1 <cmd>` so the
    # server-side hub knows not to re-dispatch. Each element is a separate
    # argv item — no shell string interpolation.
    remote = ["env", "HUB_REMOTE_DISPATCH=1", *remote_hub_cmd]
    return ["ssh", *SSH_OPTS, f"{user}@{host}", *remote]


def run_remote(user: str, host: str, remote_path: str, subcommand: Sequence[str]) -> int:
    """Run `hub --root <remote_path> <subcommand...>` on the remote host.

    Streams stdout/stderr back to this process's stdout/stderr. Returns exit code.
    """
    argv = build_ssh_argv(
        user=user,
        host=host,
        remote_hub_cmd=["hub", "--root", remote_path, *subcommand],
    )
    proc = subprocess.run(argv, shell=False, capture_output=True)
    sys.stdout.write(proc.stdout.decode())
    sys.stderr.write(proc.stderr.decode())
    return proc.returncode
