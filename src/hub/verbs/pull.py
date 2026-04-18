from __future__ import annotations

import subprocess
from pathlib import Path

import click

from ..config import load_config
from ..paths import RootPath
from ..validators import validate_slug, validate_version_name


@click.command("pull")
@click.argument("slug")
@click.option("--version", "version_name", default=None)
@click.argument("dest")
def pull(slug: str, version_name: str | None, dest: str) -> None:
    """rsync a dataset's raw or a named version directory into `dest`."""
    validate_slug(slug)
    if version_name is not None:
        validate_version_name(version_name)

    cfg = load_config()
    rp = RootPath.parse(cfg.root)

    if version_name is None:
        src_subpath = f"datasets/{slug}/raw/"
        dest_dir = Path(dest) / "raw"
    else:
        src_subpath = f"datasets/{slug}/versions/{version_name}/data/"
        dest_dir = Path(dest)

    if rp.is_remote:
        src = f"{rp.user}@{rp.host}:{rp.path}/{src_subpath}"
    else:
        src = f"{rp.path}/{src_subpath}"
        if not Path(src).is_dir():
            raise click.ClickException(f"source not found: {src}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    argv = ["rsync", "-a", src, str(dest_dir) + "/"]
    proc = subprocess.run(argv, shell=False)
    if proc.returncode != 0:
        raise click.ClickException(f"rsync failed (exit {proc.returncode})")
    click.echo(f"pulled into {dest_dir}")
