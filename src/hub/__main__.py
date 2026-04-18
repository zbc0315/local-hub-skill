from __future__ import annotations

import os
import sys

import click

from hub.config import load_config, Config
from hub.paths import RootPath
from hub.remote import run_remote
from hub.verbs.reads import list_, show, search, plan_add
from hub.verbs.writes import reindex, add, download, verify, rm
from hub.verbs.add_version import add_version
from hub.verbs.pull import pull


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--root", "root_override", default=None,
              help="override HUB_ROOT (used internally by the remote dispatcher)")
@click.version_option(package_name="hub-cli")
def cli(root_override: str | None) -> None:
    """Local/LAN open-source dataset ledger."""
    if root_override:
        os.environ["HUB_ROOT"] = root_override


cli.add_command(list_); cli.add_command(show); cli.add_command(search); cli.add_command(plan_add)
cli.add_command(reindex); cli.add_command(add); cli.add_command(download)
cli.add_command(verify); cli.add_command(rm)
cli.add_command(add_version); cli.add_command(pull)


_NEVER_REMOTE = {"pull"}
_VALUE_OPTIONS = {"--root"}


def _extract_subcommand(args: list[str]) -> str | None:
    """Return the subcommand name from raw argv (after the program name)."""
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--help", "-h", "--version"):
            return None
        if a in _VALUE_OPTIONS:
            i += 2
            continue
        if a.startswith("--") and "=" in a:
            i += 1
            continue
        if a.startswith("-"):
            i += 1
            continue
        return a
    return None


def _should_dispatch_remote(args: list[str]) -> bool:
    """True iff main() must re-invoke this command via ssh on the remote host."""
    if os.environ.get("HUB_REMOTE_DISPATCH") == "1":
        return False
    if "--root" in args or any(a.startswith("--root=") for a in args):
        return False
    sub = _extract_subcommand(args)
    if sub is None or sub in _NEVER_REMOTE:
        return False
    try:
        cfg = load_config()
    except Config.MissingRoot:
        return False
    rp = RootPath.parse(cfg.root)
    return rp.is_remote


def main() -> None:
    args = sys.argv[1:]
    if _should_dispatch_remote(args):
        cfg = load_config()
        rp = RootPath.parse(cfg.root)
        code = run_remote(user=rp.user, host=rp.host, remote_path=rp.path, subcommand=args)
        sys.exit(code)
    cli()


if __name__ == "__main__":
    main()
