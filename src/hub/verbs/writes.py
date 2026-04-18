from __future__ import annotations

from pathlib import Path

import click

from ..config import load_config
from ..index import rebuild_index
from ..locks import index_lock
from ..paths import RootPath


def _local_root() -> Path:
    cfg = load_config()
    rp = RootPath.parse(cfg.root)
    if rp.is_remote:
        raise click.ClickException("remote root not yet supported by this verb")
    return Path(rp.local_path)


@click.command("reindex")
def reindex() -> None:
    """Rebuild INDEX.md from all dataset READMEs."""
    root = _local_root()
    with index_lock(root):
        rebuild_index(root)
    click.echo("ok")
