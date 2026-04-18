from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from ..config import load_config
from ..downloader import download_and_stage
from ..index import rebuild_index
from ..locks import index_lock, slug_lock
from ..metadata import Frontmatter, parse_readme, write_readme
from ..paths import RootPath
from ..validators import validate_slug


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


@click.command("add")
@click.argument("slug")
@click.option("--source", "source_url", required=True)
@click.option("--title", required=True)
@click.option("--tags", default="", help="comma-separated")
@click.option("--license", "license_", default="unknown")
def add(slug: str, source_url: str, title: str, tags: str, license_: str) -> None:
    """Register a new (empty) dataset."""
    validate_slug(slug)
    root = _local_root()
    ds = root / "datasets" / slug

    with slug_lock(root, slug):
        if ds.exists():
            raise click.ClickException(f"dataset {slug!r} already exists at {ds}")

        ds.mkdir(parents=True)
        (ds / "raw").mkdir()
        (ds / "versions").mkdir()

        fm = Frontmatter(
            slug=slug,
            title=title,
            tags=[t.strip().lower() for t in tags.split(",") if t.strip()],
            summary="",
            source={
                "type": "url",
                "url": source_url,
                "license": license_,
                "retrieved_at": date.today().isoformat(),
                "retrieved_by": "hub-cli/0.1",
            },
            raw={"path": "raw/", "files": []},
            versions=[],
        )
        write_readme(ds / "README.md", fm, body=f"# {title}\n")

        if license_ == "unknown":
            click.echo(f"warning: license unknown for {slug!r}", err=True)

        with index_lock(root):
            rebuild_index(root)

    click.echo(f"added {slug}")


@click.command("download")
@click.argument("slug")
@click.option("--file", "file_url", required=True, help="URL of the file to download")
def download(slug: str, file_url: str) -> None:
    """Download a file into the dataset's raw/ directory."""
    validate_slug(slug)
    root = _local_root()
    ds = root / "datasets" / slug
    if not ds.is_dir():
        raise click.ClickException(f"no dataset {slug!r}; run `hub add` first")

    with slug_lock(root, slug):
        name, sha, size = download_and_stage(file_url, ds / "raw")
        readme = ds / "README.md"
        fm, body = parse_readme(readme)
        fm.raw.setdefault("files", [])
        fm.raw["files"].append({"name": name, "sha256": sha, "size_bytes": size})
        write_readme(readme, fm, body)
        with index_lock(root):
            rebuild_index(root)
    click.echo(f"downloaded {name} ({size} bytes)")
