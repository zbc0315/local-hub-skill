#!/usr/bin/env bash
set -euo pipefail

# Install hub-cli locally via pipx and copy this Skill to ~/.claude/skills/local-data-hub/.

if ! command -v pipx >/dev/null 2>&1; then
    echo "error: pipx not found. Install it first (e.g. 'brew install pipx' or 'python -m pip install --user pipx')." >&2
    exit 1
fi

# Install from the repo root (this script is in skill/scripts/, so repo root is ../../)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "==> Installing hub-cli via pipx from $REPO_ROOT"
pipx install --force "$REPO_ROOT"

SKILL_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DST="$HOME/.claude/skills/local-data-hub"

echo "==> Copying skill to $SKILL_DST"
mkdir -p "$SKILL_DST"
cp -R "$SKILL_SRC/SKILL.md" "$SKILL_SRC/references" "$SKILL_DST/"

echo ""
echo "Done. To enable the server side (if using an SSH hub root):"
echo "   ssh <host> 'pipx install <hub-cli wheel or git URL>'"
echo ""
echo "Configure ~/.config/hub/config.toml with your 'root' setting."
