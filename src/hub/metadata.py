from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .atomic import write_atomic_text, write_atomic_json
from .validators import validate_slug

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass
class Frontmatter:
    slug: str
    title: str
    tags: list[str]
    summary: str
    source: dict[str, Any]
    raw: dict[str, Any]
    versions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "tags": self.tags,
            "summary": self.summary,
            "source": self.source,
            "raw": self.raw,
            "versions": self.versions,
        }


def parse_readme(path: Path) -> tuple[Frontmatter, str]:
    text = path.read_text()
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{path} has no YAML frontmatter")
    data = yaml.safe_load(m.group(1)) or {}
    slug = validate_slug(data["slug"])
    source = dict(data.get("source", {}))
    # PyYAML parses ISO dates into datetime.date — coerce back to string so
    # downstream json.dumps / INDEX rendering never breaks on date objects.
    if "retrieved_at" in source and not isinstance(source["retrieved_at"], str):
        source["retrieved_at"] = source["retrieved_at"].isoformat()
    fm = Frontmatter(
        slug=slug,
        title=data["title"],
        tags=list(data.get("tags", [])),
        summary=data.get("summary", ""),
        source=source,
        raw=dict(data.get("raw", {"path": "raw/", "files": []})),
        versions=list(data.get("versions", [])),
    )
    return fm, m.group(2)


def write_readme(path: Path, fm: Frontmatter, body: str) -> None:
    validate_slug(fm.slug)
    front = yaml.safe_dump(fm.to_dict(), sort_keys=False, default_flow_style=False)
    text = f"---\n{front}---\n{body}"
    if not text.endswith("\n"):
        text += "\n"
    write_atomic_text(path, text)


def read_manifest(path: Path) -> dict[str, Any]:
    import json
    return json.loads(path.read_text())


def write_manifest(path: Path, data: dict[str, Any]) -> None:
    write_atomic_json(path, data)
