---
description: Interactively configure HUB_ROOT (local directory or remote SSH server) and install hub-cli where needed
allowed-tools: Read, Write, Edit, AskUserQuestion, Agent, Bash(ssh:*), Bash(scp:*), Bash(tar:*), Bash(mkdir:*), Bash(cat:*), Bash(cp:*), Bash(rm:*), Bash(which:*), Bash(hub:*), Bash(python3:*), Bash(pipx:*), Bash(test:*), Bash(ls:*), Bash(chmod:*), Bash(touch:*)
---

# `/local-data-hub:add-root` — Interactive Hub Setup

You are configuring a new `HUB_ROOT` for the `hub-cli` tool — either a local directory or a remote SSH server. Follow the 7 phases below **strictly in order**. Each phase either succeeds and the flow continues, or halts with an actionable error message for the user.

## Overall principles

- **Information gathering is batched.** Use a single `AskUserQuestion` call for related inputs rather than four sequential prompts.
- **Confirmation gates every destructive or impactful action** — writing `~/.ssh/config`, overwriting the hub config, installing software on a server, deleting the legacy loose-skill directory.
- **Detection is automatic.** Use subagents or direct `Bash` probes to determine environment state; do not ask the user about things you can observe.
- **Fail fast.** On a hard error, halt and report the raw error plus a suggested next step. Do not retry automatically, do not attempt "cleanup" of partial work.
- **Idempotency.** Re-running the command should detect existing state and either skip (reuse existing SSH alias) or explicitly ask the user before overwriting (config file).
- **Argv discipline.** Any `Bash` invocation of `ssh`/`scp`/`tar` must use argv form, not shell-string concatenation, so user-supplied host/user/path/alias values cannot inject shell syntax.

## Phase 0 — Diagnose current state

Run these reads (no user prompt yet):

1. `cat ~/.config/hub/config.toml` (expect either an existing `root = "..."` line or a "no such file" error).
2. `which hub` — records whether `hub-cli` is on the local `PATH`.
3. `test -d ~/.claude/skills/local-data-hub && echo legacy-skill-present` — detects a pre-plugin loose-skill install.

Report the findings to the user in a short paragraph. Then:

- **If a `root = "..."` already exists in config.toml**, ask via `AskUserQuestion`:
  > "An existing HUB_ROOT is set to `<value>`. What would you like to do?"
  > Options: `overwrite` (default: No), `abort`.
  If `abort`, halt cleanly.

- **If `hub` is not on PATH**, inform the user it will be installed at the end (Phase 7 pre-check).

- **If the legacy loose-skill directory exists**, ask via `AskUserQuestion`:
  > "A legacy loose-skill install at `~/.claude/skills/local-data-hub/` was detected. Delete it to avoid conflicts with the plugin version?"
  > Options: `yes`, `no` (default).
  If `yes`, run `rm -rf ~/.claude/skills/local-data-hub/` and note it for the Phase 7 summary.
  If `no`, warn: "Both may coexist in this session; restart Claude Code after setup to avoid ambiguity."

## Phase 1 — Local or remote

Ask via `AskUserQuestion`:
> "Where should the hub live?"
> Options:
>   - `local`: a directory on this machine
>   - `remote`: a directory on an SSH-reachable server

If `local`: skip Phases 2–5 (no SSH work). Proceed to Phase 6 with the user-supplied local path.
If `remote`: proceed to Phase 2.

## Phase 2 — Collect SSH target (remote only)

Ask via `AskUserQuestion` — all four inputs in one question with structured fields:

- `host`: hostname or IP (non-empty, no whitespace, no shell metacharacters)
- `port`: SSH port (integer 1–65535, default 22)
- `user`: SSH username (must match regex `^[a-zA-Z_][a-zA-Z0-9._-]*$`)
- `remote_path`: absolute path on the server where the hub root should live (must start with `/`)

Validate the four values against the rules above. If any fails, re-ask just that one field with a clear error message.

## Phase 3 — Probe server via subagent

Dispatch an `Agent` (general-purpose subagent) to run a single SSH probe and return structured JSON. The subagent's prompt:

> You are probing an SSH-reachable server for a setup flow. Run exactly one SSH command via argv (no shell-string concatenation of host/user/port). Use `Bash` tool equivalent of:
>
> ```
> ssh -o BatchMode=yes -o ConnectTimeout=10 -p <PORT> <USER>@<HOST> <PROBE_SCRIPT>
> ```
>
> where `<PROBE_SCRIPT>` is the single-quoted shell body:
>
> ```bash
> set -e
> echo "python3:";            python3 --version 2>&1 || true
> echo "pipx:";                command -v pipx || true
> echo "hub:";                 command -v hub || true
> echo "os:";                  uname -a
> echo "home:";                echo "$HOME"
> echo "path_has_local_bin:";  case ":$PATH:" in *":$HOME/.local/bin:"*) echo yes;; *) echo no;; esac
> echo "python3_is_conda:";    python3 -c "import sys,os; print('yes' if 'conda' in sys.prefix or '/opt/conda' in sys.prefix or 'miniconda' in sys.prefix else 'no')" 2>/dev/null || echo unknown
> echo "pip_user_base:";       python3 -m site --user-base 2>/dev/null || echo unknown
> ```
>
> Parse the output (each line is `key: value` or `key:` followed by the value on the same line) and return JSON:
> ```json
> {
>   "ssh_ok": true,
>   "python_version": "3.13.5",
>   "python_ok": true,
>   "has_pipx": false,
>   "has_hub": false,
>   "os_line": "Linux ...",
>   "home": "/home/...",
>   "path_has_local_bin": false,
>   "python3_is_conda": true,
>   "pip_user_base": "/home/.../.local"
> }
> ```
>
> On ssh failure (non-zero exit before the probe runs), return `{"ssh_ok": false, "error": "<stderr>"}`. Do NOT retry. Report in under 200 words.

Act on the probe result:

- **`ssh_ok == false`**: halt. Show the stderr and advise: "Most likely the server's SSH key authentication isn't set up. Run `ssh-copy-id -p <port> <user>@<host>` and retry. This command will not ssh-copy-id for you."

- **`python_ok == false`** (version < 3.11): halt. "Server needs Python 3.11+. Install Python first (via your package manager or conda); this command will not install Python for you."

- Otherwise, record all fields for use in Phase 5.

## Phase 4 — Manage `~/.ssh/config` (remote only, always)

1. Read `~/.ssh/config`. If it doesn't exist, create it with mode 0600:
   ```bash
   (umask 0177 && : > ~/.ssh/config)
   ```
   (`umask 0177` masks group/other bits so the new file is 0600; `: >` truncates to empty. Equivalent `touch ~/.ssh/config && chmod 0600 ~/.ssh/config` also works.)
2. Parse for any `Host <alias>` block where `HostName` matches the Phase-2 host, `Port` matches the port (22 if unset), and `User` matches the user.
   - **Match found** (existing alias already points at the target): announce "Using existing alias `<alias>` from ~/.ssh/config". Record the alias. No edit, no confirmation. Continue.
   - **No match**: proceed to add a new block. Ask via `AskUserQuestion`:
     > "Pick an alias for this server (will be added to ~/.ssh/config)"
     > Default: `datahub`.
     If the chosen alias already exists in `~/.ssh/config` but with different target, show the existing block and ask: `overwrite` / `pick another alias` / `abort`.
3. Show the exact lines to be appended:
   ```
   Host <alias>
       HostName <host>
       Port <port>
       User <user>
   ```
   Confirm via `AskUserQuestion`. On yes, append to `~/.ssh/config` and re-assert mode (`chmod 0600 ~/.ssh/config`) in case a prior tool loosened it.
4. Record the effective alias for Phase 5 and the final config.

## Phase 5 — Server-side install of `hub-cli` (remote only, if `has_hub == false`)

All shell calls use argv form. The local tarball and the remote staging directory are both ephemeral (`mktemp`).

1. Announce the plan to the user and request confirmation via `AskUserQuestion`:
   > "Install hub-cli on the server? This will: (1) tar the current repo source, (2) scp it to `~/` on the server, (3) run `pipx install ./local-hub-skill` (or `pip install --user`) there. Proceed?"
   > Options: `yes`, `no` (default no → abort).

2. Build the tarball locally (argv). Use the portable `mktemp PATTERN` form (both BSD/macOS and GNU/Linux accept a full template ending in `XXXXXX`); the `-t` flag has inconsistent semantics across BSD and GNU:
   ```
   LOCAL_TARBALL=$(mktemp "${TMPDIR:-/tmp}/hub-cli.XXXXXX.tar.gz")
   tar czf "$LOCAL_TARBALL" --exclude='.venv' --exclude='__pycache__' \
       --exclude='.git' --exclude='docs' \
       -C <repo-parent> local-hub-skill
   ```
   where `<repo-parent>` is the parent directory of the current repo (derive with `dirname` on the repo path).

3. Ship it (argv):
   ```
   scp "$LOCAL_TARBALL" <alias>:~/
   ```
   (Use `~` not `/tmp` so a full `/tmp` doesn't block install.)

4. Install on the server. The remote script makes its own staging directory via `mktemp -d`. The tarball filename is passed as a remote-shell variable via the `VAR=val cmd` prefix form — no `env` wrapper needed, no dead-code comments:

   ```
   TARBALL_BASENAME=$(basename "$LOCAL_TARBALL")
   ssh <alias> "HUB_TARBALL='$TARBALL_BASENAME' bash -s" <<'REMOTE_EOF'
   set -e
   : "${HUB_TARBALL:?}"
   STAGE=$(mktemp -d)
   trap 'rm -rf "$STAGE" "$HOME/$HUB_TARBALL"' EXIT
   tar xzf "$HOME/$HUB_TARBALL" -C "$STAGE"
   cd "$STAGE/local-hub-skill"
   if command -v pipx >/dev/null 2>&1; then
       pipx install --force .
       echo "installed_via=pipx"
   else
       python3 -m pip install --user --force-reinstall .
       echo "installed_via=pip_user"
   fi
   REMOTE_EOF
   ```

   Why this shape works: the outer double-quotes let the local shell expand `$TARBALL_BASENAME` into the ssh argv; the single-quoted heredoc body (`<<'REMOTE_EOF'`) is shipped verbatim so `$HUB_TARBALL` / `$HOME` / `$STAGE` are all expanded by the *remote* bash. The `VAR=val cmd` prefix is POSIX shell builtin, no external `env` needed.

5. Determine the expected `hub` absolute path based on probe output and install method:
   - `installed_via=pipx` → `<home>/.local/bin/hub` (pipx default).
   - `installed_via=pip_user` → `<pip_user_base>/bin/hub`.

6. Verify (argv):
   ```
   ssh <alias> <ABSOLUTE_HUB_PATH> --version
   ```
   Expect exit 0 and stdout starting with `hub,`. On failure, halt with the raw stderr and a note: "Server install appeared to succeed but `hub` is not executable at the expected absolute path. Check the server's Python environment."

7. Delete the local tarball after the remote install completes. (The remote trap cleans up its side.)

8. If `path_has_local_bin == false`, print this advisory after success (do NOT modify any rc file):
   > "NOTE: Your server's non-interactive `$PATH` does not include `<pip_user_base>/bin`. For interactive shells on that server to find `hub`, add this line to `~/.bashrc` or `~/.zshrc`:
   >
   > ```
   > export PATH="<pip_user_base>/bin:$PATH"
   > ```
   >
   > This command will NOT edit those files."

## Phase 6 — Create the hub root directory

- **Local** (from Phase 1): `mkdir -p <local_path>`.
- **Remote**: `ssh <alias> mkdir -p <remote_path>`.

No confirmation needed; creating empty directories is non-destructive.

## Phase 7 — Write local `~/.config/hub/config.toml` and verify

1. **Pre-check: is `hub` installed locally?**
   Run `which hub`. If absent:
   - Ask via `AskUserQuestion`: "`hub` is not installed locally. Install via `pipx install git+https://github.com/zbc0315/local-hub-skill.git` now?" Options: `yes` (default), `no`.
   - On yes, run the pipx command. On failure (no pipx), halt with: "Install pipx first: `brew install pipx` or `python -m pip install --user pipx`, then re-run this command."
   - On no, halt: "Cannot verify without `hub` on PATH. Install it and re-run."

2. **Back up any existing config**:
   - If `~/.config/hub/config.toml` exists, `cp` it to `~/.config/hub/config.toml.bak.YYYYMMDD-HHMMSS` (local time, fixed format).
   - After writing the new config (Step 3), trim backups: keep the three most recent `config.toml.bak.*` files, `rm` the rest.

3. **Write the new config** at `~/.config/hub/config.toml`:
   - Ensure the directory exists first: `mkdir -p ~/.config/hub`.
   - Write:
     ```toml
     root = "<final-root-value>"
     ```
     where `<final-root-value>` is either the local absolute path (Phase 1 `local` branch) or `<alias>:<remote_path>` (remote branch, using the alias from Phase 4).

4. **Verify end-to-end** by running `hub list` locally (argv: `hub list`). The local `hub` reads the config, sees a remote root if applicable, and dispatches to the server via SSH automatically. First call on a fresh hub initializes `INDEX.md` and prints an empty table.

5. **On success**, print a summary:
   ```
   ✓ HUB_ROOT is now: <final-root-value>
   ✓ SSH alias: <alias> (new | reused)      [remote only]
   ✓ Server hub-cli install: yes (pipx | pip_user) | already-present | n/a
   ✓ Remote hub directory created: <remote_path>        [remote only]
   ✓ Local config: ~/.config/hub/config.toml
     Backed up previous config to: <bak-path>            [if applicable]
   ✓ Legacy loose-skill removed: yes | no | n/a

   NEXT STEPS:
     - If you deleted the legacy loose skill, restart Claude Code
       (or run /reload-plugins) so the plugin-form skill is loaded.
     - Try: `hub search <keyword>` to explore the hub.
   ```

6. **On failure**, print a partial-state inventory so the user can undo manually:
   ```
   ✗ Setup failed at: <phase name>
     Raw error: <stderr>

   State at time of failure — undo manually if needed:
     - SSH alias `<alias>` written to ~/.ssh/config? [yes|no]
     - Server-side hub-cli installed?               [yes|no|n/a]
     - Remote hub directory <remote_path> created?  [yes|no|n/a]
     - Local ~/.config/hub/config.toml written?     [yes|no]
     - Previous config backed up to?                <bak-path|none>
     - Legacy loose skill deleted?                  [yes|no|n/a]

   Suggested next step: <specific action>
   ```
   Do NOT attempt automated rollback.

---

End of flow.
