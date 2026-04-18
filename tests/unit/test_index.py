from pathlib import Path

import pytest

from hub.index import rebuild_index
from hub.metadata import Frontmatter, write_readme


def _seed(root: Path, slug: str, title: str, tags: list[str], summary: str) -> None:
    ds = root / "datasets" / slug
    ds.mkdir(parents=True)
    fm = Frontmatter(
        slug=slug, title=title, tags=tags, summary=summary,
        source={"type": "manual", "url": "", "license": "unknown",
                "retrieved_at": "2026-04-18", "retrieved_by": "test"},
        raw={"path": "raw/", "files": []},
        versions=[],
    )
    write_readme(ds / "README.md", fm, body="")


def test_rebuild_index_writes_table(tmp_path: Path) -> None:
    _seed(tmp_path, "covid-jhu", "JHU COVID", ["timeseries", "health"], "daily")
    _seed(tmp_path, "imdb-reviews", "IMDB Reviews", ["text", "nlp"], "50k")

    rebuild_index(tmp_path)

    content = (tmp_path / "INDEX.md").read_text()
    assert "<!-- AUTO-GENERATED" in content
    assert "# Data Hub Index" in content
    assert "| covid-jhu | JHU COVID | timeseries, health | daily | datasets/covid-jhu |" in content
    assert "| imdb-reviews | IMDB Reviews | text, nlp | 50k | datasets/imdb-reviews |" in content


def test_rebuild_empty(tmp_path: Path) -> None:
    (tmp_path / "datasets").mkdir()
    rebuild_index(tmp_path)
    content = (tmp_path / "INDEX.md").read_text()
    assert "| slug | title |" in content  # header still present
