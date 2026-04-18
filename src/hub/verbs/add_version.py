from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import click

from ..atomic import write_atomic_text, write_atomic_json
from ..config import load_config
from ..index import rebuild_index
from ..locks import slug_lock, index_lock
from ..metadata import parse_readme, write_readme
from ..paths import RootPath
from ..script_runner import run_script, ScriptFailed, ScriptTimeout
from ..validators import validate_slug, validate_version_name


def _local_root() -> tuple[Path, int]:
    cfg = load_config()
    rp = RootPath.parse(cfg.root)
    if rp.is_remote:
        raise click.ClickException(
            "hub add-version cannot be used with a remote HUB_ROOT — "
            "the script file must live on the same machine as the hub. "
            "Copy the script to the server and run `hub add-version` there."
        )
    return Path(rp.local_path), cfg.script_timeout


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_outputs(data_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for p in sorted(data_dir.rglob("*")):
        if p.is_file():
            rows.append({
                "name": str(p.relative_to(data_dir.parent)),
                "sha256": _sha256_of_file(p),
                "size_bytes": p.stat().st_size,
            })
    return rows


@click.command("add-version")
@click.argument("slug")
@click.argument("version_name")
@click.option("--script", "script_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--input", "input_version", required=True, help='"raw" or an existing version name')
def add_version(slug: str, version_name: str, script_path: str, input_version: str) -> None:
    """Produce a new named version by running a user script over an input version."""
    validate_slug(slug)
    validate_version_name(version_name)
    if input_version != "raw":
        validate_version_name(input_version)

    root, timeout = _local_root()
    ds = root / "datasets" / slug
    if not ds.is_dir():
        raise click.ClickException(f"no dataset {slug!r}")

    final = ds / "versions" / version_name
    partial = ds / "versions" / f"{version_name}.partial"

    with slug_lock(root, slug):
        if final.exists():
            raise click.ClickException(f"version {version_name!r} already exists")

        # 1. Determine input dir
        if input_version == "raw":
            input_dir = ds / "raw"
        else:
            input_dir = ds / "versions" / input_version / "data"
            if not input_dir.is_dir():
                raise click.ClickException(f"input version {input_version!r} has no data/")

        # 2. Stage: copy script, prepare data dir
        partial.mkdir(parents=True)
        (partial / "data").mkdir()
        staged_script = partial / "script.py"
        shutil.copy(script_path, staged_script)
        script_sha = _sha256_of_file(staged_script)

        try:
            # 3. Run the script
            run_script(staged_script, input_dir=input_dir, output_dir=partial / "data", timeout=timeout)
        except (ScriptFailed, ScriptTimeout) as e:
            shutil.rmtree(partial)
            raise click.ClickException(f"script failed: {e}")

        # 4. Read schema.json (optional)
        schema_path = partial / "data" / "schema.json"
        if schema_path.exists():
            schema = json.loads(schema_path.read_text())
            schema_path.unlink()  # don't ship schema.json alongside data
        else:
            schema = []
            click.echo("warning: script did not write schema.json; schema recorded as empty", err=True)

        # 5. Write manifest.json
        output_files = _hash_outputs(partial / "data")
        manifest = {
            "name": version_name,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "input_version": input_version,
            "script_sha256": script_sha,
            "output_files": output_files,
            "schema": schema,
        }
        write_atomic_json(partial / "manifest.json", manifest)

        # 6. Atomic install
        import os
        os.rename(partial, final)

        # 7. Update README frontmatter
        readme = ds / "README.md"
        fm, body = parse_readme(readme)
        fm.versions.append({
            "name": version_name,
            "path": f"versions/{version_name}/",
            "created_at": manifest["created_at"],
            "input_version": input_version,
            "script": f"versions/{version_name}/script.py",
            "script_sha256": script_sha,
            "schema": schema,
        })
        write_readme(readme, fm, body)

        # 8. Reindex
        with index_lock(root):
            rebuild_index(root)

    click.echo(f"created version {version_name}")
