from __future__ import annotations

import shlex
import subprocess
from typing import Sequence

SSH_OPTS = [
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=10",
]


def build_ssh_argv(*, user: str, host: str, remote_hub_cmd: Sequence[str]) -> list[str]:
    # OpenSSH joins the remote-command argv into a single shell string for the
    # server-side login shell (`sh -c "<joined>"`), so any space/paren/quote in
    # a value would be re-parsed remotely and break argv boundaries. Apply
    # `shlex.quote` to every element of the hub command before shipping.
    # The `env HUB_REMOTE_DISPATCH=1` prefix is our own fixed constant and
    # does not need quoting.
    quoted = [shlex.quote(a) for a in remote_hub_cmd]
    remote = ["env", "HUB_REMOTE_DISPATCH=1", *quoted]
    return ["ssh", *SSH_OPTS, f"{user}@{host}", *remote]


def run_remote_captured(*, user: str, host: str, remote_path: str,
                        subcommand: Sequence[str]) -> tuple[int, str, str]:
    """Run `hub --root <remote_path> <subcommand...>` on `user@host`.

    Returns (returncode, stdout, stderr). Never raises on SSH failure.

    No timeout is enforced — remote writes (`download`, `add-version`, `verify`
    on a hashed big dataset) can legitimately take minutes to hours. A 30-second
    timeout was the original behavior and broke any non-trivial operation. If
    the user needs to abort, Ctrl-C kills the local ssh process, which sends
    SIGHUP to the remote command.
    """
    argv = build_ssh_argv(user=user, host=host,
                          remote_hub_cmd=["hub", "--root", remote_path, *subcommand])
    try:
        proc = subprocess.run(argv, shell=False, capture_output=True, timeout=None)
    except subprocess.TimeoutExpired:  # pragma: no cover — unreachable with timeout=None
        return 255, "", "ssh timed out\n"
    return proc.returncode, proc.stdout.decode(), proc.stderr.decode()
