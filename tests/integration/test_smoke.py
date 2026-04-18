import subprocess
import sys

import pytest


@pytest.mark.integration
def test_remote_list_via_ssh_localhost(remote_root):
    from hub.metadata import Frontmatter, write_readme
    from hub.index import rebuild_index
    ds = remote_root / "datasets" / "tiny"
    ds.mkdir(parents=True)
    fm = Frontmatter(
        slug="tiny", title="Tiny", tags=["demo"], summary="a demo",
        source={"type": "manual", "url": "", "license": "unknown",
                "retrieved_at": "2026-04-18", "retrieved_by": "t"},
        raw={"path": "raw/", "files": []}, versions=[],
    )
    write_readme(ds / "README.md", fm, body="")
    rebuild_index(remote_root)

    r = subprocess.run([sys.executable, "-m", "hub", "list"], capture_output=True)
    assert r.returncode == 0, r.stderr.decode()
    assert b"tiny" in r.stdout
