from pathlib import Path

import pytest

from hub.metadata import parse_readme, write_readme, read_manifest, write_manifest, Frontmatter


SAMPLE = """\
---
slug: covid-jhu
title: JHU COVID
tags: [timeseries, health]
summary: daily case counts
source:
  type: github
  url: https://example.com/x
  license: CC-BY-4.0
  retrieved_at: 2026-04-18
  retrieved_by: hub-cli/0.1
raw:
  path: raw/
  files: []
versions: []
---

# JHU COVID

Body here.
"""


def test_parse_readme(tmp_path: Path) -> None:
    p = tmp_path / "README.md"
    p.write_text(SAMPLE)
    fm, body = parse_readme(p)
    assert fm.slug == "covid-jhu"
    assert fm.title == "JHU COVID"
    assert fm.tags == ["timeseries", "health"]
    assert fm.source["type"] == "github"
    assert fm.raw["files"] == []
    assert fm.versions == []
    assert "Body here." in body


def test_write_readme_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "README.md"
    fm = Frontmatter(
        slug="covid-jhu",
        title="JHU COVID",
        tags=["timeseries", "health"],
        summary="daily case counts",
        source={"type": "github", "url": "https://e.com", "license": "CC-BY-4.0",
                "retrieved_at": "2026-04-18", "retrieved_by": "hub-cli/0.1"},
        raw={"path": "raw/", "files": []},
        versions=[],
    )
    write_readme(p, fm, body="# JHU COVID\n\nBody here.\n")
    fm2, body = parse_readme(p)
    assert fm2 == fm
    assert body.strip() == "# JHU COVID\n\nBody here.".strip()


def test_parse_readme_invalid_slug_rejected(tmp_path: Path) -> None:
    p = tmp_path / "README.md"
    p.write_text(SAMPLE.replace("slug: covid-jhu", "slug: BAD SLUG"))
    with pytest.raises(ValueError):
        parse_readme(p)


def test_parse_readme_coerces_retrieved_at_to_string(tmp_path: Path) -> None:
    """PyYAML auto-parses ISO dates; we need string so json.dumps etc. works."""
    p = tmp_path / "README.md"
    p.write_text(SAMPLE)  # retrieved_at: 2026-04-18 is a bare YAML date
    fm, _ = parse_readme(p)
    assert isinstance(fm.source["retrieved_at"], str)
    assert fm.source["retrieved_at"] == "2026-04-18"

    import json
    json.dumps(fm.source)  # must not raise


def test_manifest_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "manifest.json"
    data = {
        "name": "cleaned-2026-04",
        "created_at": "2026-04-18T12:03:14Z",
        "input_version": "raw",
        "script_sha256": "a" * 64,
        "output_files": [],
        "schema": [],
    }
    write_manifest(p, data)
    assert read_manifest(p) == data
