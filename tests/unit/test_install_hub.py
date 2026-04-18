import os
import subprocess
from pathlib import Path

import pytest


def test_install_hub_copies_skill(tmp_path: Path) -> None:
    """Run install-hub.sh against a tmp HOME with a stub pipx; verify file copy."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "pipx").write_text("#!/usr/bin/env bash\nexit 0\n")
    (bin_dir / "pipx").chmod(0o755)

    repo_root = Path(__file__).resolve().parent.parent.parent
    script = repo_root / "skill" / "scripts" / "install-hub.sh"
    assert script.exists(), f"missing {script}"

    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(script)], env=env, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode()

    skill_dst = tmp_path / ".claude" / "skills" / "local-data-hub"
    assert (skill_dst / "SKILL.md").exists()
    assert (skill_dst / "references" / "metadata-schema.md").exists()
    assert (skill_dst / "references" / "cli-reference.md").exists()

    skill_md = (skill_dst / "SKILL.md").read_text()
    assert "name: local-data-hub" in skill_md


def test_install_hub_syntax_valid() -> None:
    """`bash -n` catches obvious shell syntax errors."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    script = repo_root / "skill" / "scripts" / "install-hub.sh"
    r = subprocess.run(["bash", "-n", str(script)], capture_output=True)
    assert r.returncode == 0, r.stderr.decode()
