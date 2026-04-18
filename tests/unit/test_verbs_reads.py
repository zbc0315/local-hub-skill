import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from hub.__main__ import cli
from hub.metadata import Frontmatter, write_readme


@pytest.fixture()
def seeded_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ds = tmp_path / "datasets" / "covid-jhu"
    ds.mkdir(parents=True)
    fm = Frontmatter(
        slug="covid-jhu",
        title="JHU COVID",
        tags=["timeseries", "health"],
        summary="daily case counts",
        source={"type": "manual", "url": "", "license": "unknown",
                "retrieved_at": "2026-04-18", "retrieved_by": "t"},
        raw={"path": "raw/", "files": []},
        versions=[],
    )
    write_readme(ds / "README.md", fm, body="# JHU COVID\n\nBody.\n")
    (tmp_path / "INDEX.md").write_text(
        "<!-- AUTO-GENERATED -->\n# Data Hub Index\n\n"
        "| slug | title | tags | summary | path |\n|---|---|---|---|---|\n"
        "| covid-jhu | JHU COVID | timeseries, health | daily case counts | datasets/covid-jhu |\n"
    )
    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    return tmp_path


def test_list(seeded_root: Path) -> None:
    result = CliRunner().invoke(cli, ["list"])
    assert result.exit_code == 0, result.output
    assert "covid-jhu" in result.output
    assert "JHU COVID" in result.output


def test_list_filter_tag(seeded_root: Path) -> None:
    result = CliRunner().invoke(cli, ["list", "--tag", "timeseries"])
    assert "covid-jhu" in result.output
    result2 = CliRunner().invoke(cli, ["list", "--tag", "nothing"])
    assert "covid-jhu" not in result2.output


def test_show(seeded_root: Path) -> None:
    result = CliRunner().invoke(cli, ["show", "covid-jhu"])
    assert result.exit_code == 0, result.output
    assert "slug: covid-jhu" in result.output
    assert "Body." in result.output


def test_show_unknown(seeded_root: Path) -> None:
    result = CliRunner().invoke(cli, ["show", "no-such-slug"])
    assert result.exit_code != 0


def test_search_hits_summary(seeded_root: Path) -> None:
    result = CliRunner().invoke(cli, ["search", "daily"])
    assert result.exit_code == 0
    assert "covid-jhu" in result.output


def test_plan_add_echoes_url(seeded_root: Path) -> None:
    result = CliRunner().invoke(cli, ["plan-add", "https://example.com/data.csv"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out == [{"source_type": "url", "url": "https://example.com/data.csv",
                    "license": "unknown", "size_bytes": None}]


def test_plan_add_non_url_empty(seeded_root: Path) -> None:
    """MVP: non-URL queries yield empty candidate list; caller must supply URL."""
    result = CliRunner().invoke(cli, ["plan-add", "some dataset keywords"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []
