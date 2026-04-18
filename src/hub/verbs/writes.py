from __future__ import annotations

import hashlib
import os
import shutil
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
    cfg = load_config()
    root = _local_root()
    ds = root / "datasets" / slug
    if not ds.is_dir():
        raise click.ClickException(f"no dataset {slug!r}; run `hub add` first")

    def _confirm(size_bytes: int) -> bool:
        mb = size_bytes / (1024 * 1024)
        threshold_mb = cfg.confirm_download_above / (1024 * 1024)
        return click.confirm(
            f"download is {mb:.1f} MB (threshold {threshold_mb:.0f} MB). Continue?",
            default=False,
        )

    with slug_lock(root, slug):
        try:
            name, sha, size = download_and_stage(
                file_url, ds / "raw",
                confirm_threshold=cfg.confirm_download_above,
                confirm_fn=_confirm,
            )
        except RuntimeError as e:
            raise click.ClickException(str(e))
        readme = ds / "README.md"
        fm, body = parse_readme(readme)
        fm.raw.setdefault("files", [])
        fm.raw["files"].append({"name": name, "sha256": sha, "size_bytes": size})
        write_readme(readme, fm, body)
        with index_lock(root):
            rebuild_index(root)
    click.echo(f"downloaded {name} ({size} bytes)")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_one(root: Path, slug: str) -> list[str]:
    """Return a list of failure messages. Empty list means OK."""
    failures: list[str] = []
    ds = root / "datasets" / slug
    fm, _ = parse_readme(ds / "README.md")
    for rec in fm.raw.get("files", []):
        p = ds / "raw" / rec["name"]
        if not p.exists():
            failures.append(f"{slug}/raw/{rec['name']}: missing")
            continue
        actual = _sha256_file(p)
        if actual != rec["sha256"]:
            failures.append(f"{slug}/raw/{rec['name']}: sha256 mismatch")
        if p.stat().st_size != rec["size_bytes"]:
            failures.append(f"{slug}/raw/{rec['name']}: size mismatch")
    for v in fm.versions:
        vdir = ds / "versions" / v["name"]
        manifest_path = vdir / "manifest.json"
        if not manifest_path.exists():
            failures.append(f"{slug}/versions/{v['name']}: missing manifest.json")
            continue
        import json
        m = json.loads(manifest_path.read_text())
        for of in m.get("output_files", []):
            p = vdir / of["name"]
            if not p.exists():
                failures.append(f"{slug}/versions/{v['name']}/{of['name']}: missing")
                continue
            if _sha256_file(p) != of["sha256"]:
                failures.append(f"{slug}/versions/{v['name']}/{of['name']}: sha256 mismatch")
            if p.stat().st_size != of["size_bytes"]:
                failures.append(f"{slug}/versions/{v['name']}/{of['name']}: size mismatch")
    return failures


@click.command("verify")
@click.argument("slug", required=False)
def verify(slug: str | None) -> None:
    """Rehash files and compare to recorded sha256 / size."""
    root = _local_root()
    if slug is not None:
        validate_slug(slug)
        targets = [slug]
    else:
        datasets_dir = root / "datasets"
        if not datasets_dir.is_dir():
            click.echo("ok (0 dataset(s))")
            return
        targets = sorted(p.name for p in datasets_dir.iterdir() if p.is_dir())

    all_failures: list[str] = []
    for t in targets:
        with slug_lock(root, t):
            all_failures.extend(_verify_one(root, t))

    if all_failures:
        for f in all_failures:
            click.echo(f, err=True)
        raise click.ClickException(f"{len(all_failures)} verification failure(s)")
    click.echo(f"ok ({len(targets)} dataset(s))")


@click.command("rm")
@click.argument("slug")
@click.option("--yes", is_flag=True, help="required confirmation")
def rm(slug: str, yes: bool) -> None:
    """Delete a dataset directory. Requires --yes."""
    validate_slug(slug)
    if not yes:
        raise click.ClickException("refusing to delete without --yes")
    root = _local_root()
    ds = root / "datasets" / slug
    if not ds.is_dir():
        raise click.ClickException(f"no dataset {slug!r}")

    deleting = root / "datasets" / f"{slug}.deleting"
    with slug_lock(root, slug):
        os.rename(ds, deleting)
        shutil.rmtree(deleting)
        with index_lock(root):
            rebuild_index(root)
    click.echo(f"removed {slug}")
