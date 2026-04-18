"""Structure tests for the Claude Code marketplace + plugin layout."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_JSON = REPO_ROOT / "plugins" / "local-data-hub" / ".claude-plugin" / "plugin.json"
SKILL_MD = REPO_ROOT / "plugins" / "local-data-hub" / "skills" / "local-data-hub" / "SKILL.md"
ADD_ROOT_MD = REPO_ROOT / "plugins" / "local-data-hub" / "commands" / "add-root.md"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"


def _frontmatter(path: Path) -> dict[str, object]:
    """Parse YAML frontmatter from a markdown file. Returns {} if absent."""
    import yaml
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


def _body_after_frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n.*?\n---\n(.*)$", text, re.DOTALL)
    return m.group(1) if m else text


# --- marketplace.json ---------------------------------------------------------

def test_marketplace_json_parses() -> None:
    assert MARKETPLACE_JSON.exists(), f"missing {MARKETPLACE_JSON}"
    data = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    assert data["name"] == "local-hub-skill"
    assert "description" in data and data["description"]
    assert "owner" in data and data["owner"].get("name")
    assert isinstance(data["plugins"], list) and len(data["plugins"]) == 1


def test_marketplace_lists_local_data_hub_plugin() -> None:
    data = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    entry = data["plugins"][0]
    assert entry["name"] == "local-data-hub"
    assert entry["source"] == "./plugins/local-data-hub"
    assert "homepage" in entry


# --- plugin.json --------------------------------------------------------------

def test_plugin_json_parses() -> None:
    assert PLUGIN_JSON.exists(), f"missing {PLUGIN_JSON}"
    data = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    for key in ("name", "version", "description", "author", "license", "repository"):
        assert key in data, f"plugin.json missing {key!r}"
    assert data["name"] == "local-data-hub"
    assert re.match(r"^\d+\.\d+\.\d+$", data["version"]), "version must be semver"


def test_plugin_version_matches_pyproject() -> None:
    """Prevent drift between plugin.json and pyproject.toml versions."""
    plugin_v = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))["version"]
    pyproj = tomllib.loads(PYPROJECT_TOML.read_text(encoding="utf-8"))
    pyproj_v = pyproj["project"]["version"]
    assert plugin_v == pyproj_v, (
        f"plugin.json version {plugin_v!r} != pyproject.toml version {pyproj_v!r}"
    )


# --- skill SKILL.md -----------------------------------------------------------

def test_skill_md_has_required_frontmatter() -> None:
    assert SKILL_MD.exists(), f"missing {SKILL_MD}"
    fm = _frontmatter(SKILL_MD)
    assert fm.get("name") == "local-data-hub"
    assert isinstance(fm.get("description"), str) and len(fm["description"]) > 40


# --- commands/add-root.md -----------------------------------------------------

def test_add_root_command_has_required_frontmatter() -> None:
    assert ADD_ROOT_MD.exists(), f"missing {ADD_ROOT_MD}"
    fm = _frontmatter(ADD_ROOT_MD)
    assert isinstance(fm.get("description"), str) and fm["description"]
    assert "allowed-tools" in fm
    # allowed-tools may be a string (comma-separated) or a list; accept either
    at = fm["allowed-tools"]
    at_str = at if isinstance(at, str) else ",".join(at)
    assert "AskUserQuestion" in at_str
    assert "Agent" in at_str


def test_add_root_command_body_is_substantial() -> None:
    body = _body_after_frontmatter(ADD_ROOT_MD)
    assert len(body) > 2000, (
        f"add-root.md body too short ({len(body)} chars); "
        "the 7-phase flow should be thoroughly specified"
    )
    # Sanity: the phases must appear
    for phase_marker in ("Phase 0", "Phase 1", "Phase 2", "Phase 3",
                         "Phase 4", "Phase 5", "Phase 6", "Phase 7"):
        assert phase_marker in body, f"add-root.md missing {phase_marker}"


# --- claude plugin validate (loopback) ----------------------------------------

import shutil
import subprocess


def test_claude_plugin_validate() -> None:
    """Run `claude plugin validate` on the plugin dir. Skip if `claude` not on PATH."""
    claude = shutil.which("claude")
    if not claude:
        pytest.skip("`claude` CLI not available")
    plugin_dir = REPO_ROOT / "plugins" / "local-data-hub"
    r = subprocess.run(
        [claude, "plugin", "validate", str(plugin_dir)],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, (
        f"claude plugin validate failed\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    )
