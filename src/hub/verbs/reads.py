from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from ..config import load_config
from ..metadata import parse_readme
from ..paths import RootPath
from ..validators import validate_slug


def _local_root() -> Path:
    cfg = load_config()
    rp = RootPath.parse(cfg.root)
    if rp.is_remote:
        # Remote dispatch is wired in a later task; for now, fail explicitly.
        raise click.ClickException("remote root not yet supported by this verb")
    return Path(rp.local_path)


@click.command("list")
@click.option("--tag", default=None, help="filter by tag substring")
def list_(tag: str | None) -> None:
    """Print INDEX.md, optionally filtering rows by tag."""
    root = _local_root()
    index = (root / "INDEX.md")
    if not index.exists():
        raise click.ClickException(f"no INDEX.md at {index}")
    text = index.read_text()
    if tag is None:
        click.echo(text, nl=False)
        return
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        if line.startswith("|") and "|" in line[1:]:
            # Keep header rows + rows that match tag
            if "---" in line or tag.lower() in line.lower():
                out.append(line)
        else:
            out.append(line)
    click.echo("\n".join(out))


@click.command("show")
@click.argument("slug")
def show(slug: str) -> None:
    """Print a dataset's README (frontmatter + body)."""
    validate_slug(slug)
    root = _local_root()
    readme = root / "datasets" / slug / "README.md"
    if not readme.exists():
        raise click.ClickException(f"no dataset {slug!r}")
    click.echo(readme.read_text(), nl=False)


@click.command("search")
@click.argument("query")
def search(query: str) -> None:
    """Fuzzy substring match over INDEX + all READMEs."""
    root = _local_root()
    hits: list[str] = []
    q = query.lower()

    index = root / "INDEX.md"
    if index.exists():
        for line in index.read_text().splitlines():
            if line.startswith("|") and "---" not in line and q in line.lower():
                hits.append(line)

    datasets_dir = root / "datasets"
    if datasets_dir.is_dir():
        for ds in sorted(datasets_dir.iterdir()):
            readme = ds / "README.md"
            if not readme.is_file():
                continue
            try:
                fm, body = parse_readme(readme)
            except Exception:
                continue
            haystack = " ".join([
                fm.slug, fm.title, fm.summary, " ".join(fm.tags),
                json.dumps(fm.source), body[:2000],
            ]).lower()
            if q in haystack and not any(fm.slug in h for h in hits):
                hits.append(f"{fm.slug}: {fm.title} — {fm.summary}")

    if not hits:
        click.echo("(no matches)")
        return
    click.echo("\n".join(hits))


@click.command("plan-add")
@click.argument("query_or_url")
def plan_add(query_or_url: str) -> None:
    """Emit JSON candidate list.

    MVP behavior: if argument looks like a URL, echo it as a single candidate.
    Otherwise, emit empty list — caller must provide a URL.
    """
    if query_or_url.startswith(("http://", "https://", "s3://")):
        candidates = [{
            "source_type": "url",
            "url": query_or_url,
            "license": "unknown",
            "size_bytes": None,
        }]
    else:
        candidates = []
    click.echo(json.dumps(candidates))
