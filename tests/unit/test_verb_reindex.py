from pathlib import Path

import pytest
from click.testing import CliRunner

from hub.__main__ import cli
from hub.metadata import Frontmatter, write_readme


def test_reindex_rewrites_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ds = tmp_path / "datasets" / "covid-jhu"
    ds.mkdir(parents=True)
    fm = Frontmatter(
        slug="covid-jhu", title="JHU", tags=["t"], summary="s",
        source={"type": "manual", "url": "", "license": "unknown",
                "retrieved_at": "2026-04-18", "retrieved_by": "t"},
        raw={"path": "raw/", "files": []}, versions=[],
    )
    write_readme(ds / "README.md", fm, body="")
    (tmp_path / "INDEX.md").write_text("WRONG\n")

    monkeypatch.setenv("HUB_ROOT", str(tmp_path))
    result = CliRunner().invoke(cli, ["reindex"])
    assert result.exit_code == 0, result.output

    content = (tmp_path / "INDEX.md").read_text()
    assert "covid-jhu" in content
    assert "WRONG" not in content
