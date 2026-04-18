from __future__ import annotations

import subprocess
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


def run_remote_captured(*, user: str, host: str, remote_path: str,
                        subcommand: Sequence[str]) -> tuple[int, str, str]:
    """Run `hub --root <remote_path> <subcommand...>` on `user@host`.

    Returns (returncode, stdout, stderr). Never raises on SSH failure.
    """
    argv = build_ssh_argv(user=user, host=host,
                          remote_hub_cmd=["hub", "--root", remote_path, *subcommand])
    try:
        proc = subprocess.run(argv, shell=False, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        return 255, "", "ssh timed out\n"
    return proc.returncode, proc.stdout.decode(), proc.stderr.decode()
