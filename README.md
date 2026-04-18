# hub-cli

A shared, single-user ledger for open-source datasets — a small CLI plus a companion Claude Code Skill that together prevent multiple projects from re-downloading, re-cleaning, or diverging on the same public data.

**One user, many projects, one cached copy of every public dataset.** Each dataset has a versioned directory tree, a YAML-frontmatter README that serves as authoritative metadata, and optional named "versions" that record reusable preprocessing (script + sha256 + schema).

---

## Table of contents

- [Why](#why)
- [How it works](#how-it-works)
- [Install](#install)
- [Configure](#configure)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Processing versions with `add-version`](#processing-versions-with-add-version)
- [Directory layout](#directory-layout)
- [Remote hub over SSH](#remote-hub-over-ssh)
- [Offline use](#offline-use)
- [Companion Claude Code Skill](#companion-claude-code-skill)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## Why

If you run several projects that each need, say, the JHU COVID time series or an IMDB reviews corpus, you probably download it per-project and clean it per-project. That wastes disk, bandwidth, and — worse — diverges on preprocessing so two projects compute different "same" numbers.

`hub-cli` gives all projects one shared directory, keyed by slug, with:

- A top-level `INDEX.md` listing every dataset (auto-generated).
- Per-dataset `README.md` with YAML frontmatter: source, license, sha256, size, preprocessing versions.
- `raw/` holding the original downloaded files (read-only by convention).
- `versions/<name>/` holding named preprocessing outputs, each with a snapshot of the generating script and a `manifest.json`.

All writes are atomic (stage → `rename(2)`) and serialized by POSIX file locks, so multiple concurrent LLM sessions can safely add/download against the same hub.

## How it works

```
┌─────────────────────────────────────────────────────────┐
│               $HUB_ROOT (local or SSH)                  │
│  ┌────────────────┐                                     │
│  │   INDEX.md     │  ← auto-generated, one-line summary │
│  └────────────────┘                                     │
│                                                         │
│  datasets/<slug>/                                       │
│    README.md              ← authoritative frontmatter   │
│    raw/<files>            ← original downloads          │
│    versions/<name>/                                     │
│      data/<outputs>                                     │
│      script.py            ← snapshot of generator       │
│      manifest.json        ← reproducibility record      │
└─────────────────────────────────────────────────────────┘
           ▲
           │  read: cat/grep directly
           │  write: `hub` CLI (takes slug lock)
           │
       your project / LLM session
```

- **Reads are lock-free.** LLMs can `cat $HUB_ROOT/INDEX.md`, `grep` across READMEs, and consume files directly.
- **Writes go through `hub`** — `hub add`, `hub download`, `hub add-version`, `hub rm`, `hub verify`, `hub reindex`. Each takes an exclusive lock on `$HUB_ROOT/.hub/locks/<slug>.lock`.
- **Remote transparency.** If `HUB_ROOT` is `user@host:/path`, writes run server-side via `ssh host hub --root /path <cmd> ...` and reads are cached locally.

## Install

### Prerequisites

- Python 3.11 or newer (for `tomllib` in stdlib).
- `rsync` on `$PATH` (ships with macOS; on Linux `apt install rsync` / `dnf install rsync`).
- `ssh` client on `$PATH` if you use a remote hub root.
- [pipx](https://pipx.pypa.io/) recommended for isolated installs: `brew install pipx` or `python -m pip install --user pipx`.

### From this repository

```bash
git clone <this repo> local-hub-skill
cd local-hub-skill
pipx install -e .
hub --help
```

The editable install means code changes take effect without re-installing.

If you prefer a plain venv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
hub --help
```

> **macOS note:** if your global `~/.npmrc` has `omit=dev`, that's for `npm` only and does not affect `pip`. The `.[dev]` extra installs `pytest` correctly.

### On a remote SSH hub server

If your `HUB_ROOT` is `user@host:/path`, also install `hub-cli` on the server:

```bash
ssh user@host
# on the server:
pipx install git+https://your-internal-git/local-hub-skill.git
# or copy the source and:
pipx install -e /path/to/local-hub-skill
```

The server side only needs `hub` on its `$PATH` — the client will invoke it as `env HUB_REMOTE_DISPATCH=1 hub --root /path …` over SSH.

## Configure

Configuration lives at `~/.config/hub/config.toml`:

```toml
# Where the hub lives. Either an absolute local path or user@host:/path.
root = "/Users/tom/data-hub"

# Downloads larger than this prompt for y/n confirmation. Default 500 MB.
confirm_download_above = 524288000

# Max wall-clock time (seconds) for an `add-version` user script.
# Default 7200 (2 hours). Override per-invocation would require a flag (not MVP).
script_timeout = 7200

# Log level; currently informational only.
log_level = "info"
```

**Environment override.** `$HUB_ROOT` always wins over the config file's `root =`. Useful for CI or quick one-offs:

```bash
HUB_ROOT=/tmp/scratch-hub hub list
```

**Remote root example:**

```toml
root = "jim@nas.lan:/srv/data-hub"
```

## Quick start

Set up a hub at `~/data-hub` and walk through the happy path:

```bash
# 0. One-time: point HUB_ROOT at a directory you own.
mkdir -p ~/data-hub
mkdir -p ~/.config/hub
cat > ~/.config/hub/config.toml <<'EOF'
root = "/Users/tom/data-hub"
EOF

# 1. Register a new dataset.
hub add iris \
    --source https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data \
    --title "Iris flower dataset" \
    --tags classification,tabular,small \
    --license "public-domain"

# 2. Download the raw file.
hub download iris --file https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data

# 3. See what's in the hub.
hub list
hub show iris

# 4. Pull raw data into a project workspace.
mkdir -p ~/projects/iris-analysis
hub pull iris ~/projects/iris-analysis

# 5. Later, from another project that needs the same data:
hub search iris
hub pull iris ~/projects/other-project
```

After step 4, `~/projects/iris-analysis/raw/iris.data` is the downloaded file.

## Commands

All 11 verbs. Read verbs are lock-free; write verbs hold per-slug exclusive locks.

### Read

| Command | Purpose |
|---|---|
| `hub list [--tag T]` | Print `INDEX.md`. `--tag` filters rows by substring. |
| `hub show <slug>` | Print the dataset's full `README.md` (frontmatter + body). |
| `hub search <query>` | Fuzzy substring match over INDEX + all READMEs (frontmatter + body). |
| `hub plan-add <query-or-url>` | Emit JSON candidate list. If arg is a URL, returns it as the single candidate; otherwise returns `[]`. |

### Write

| Command | Purpose |
|---|---|
| `hub add <slug> --source <url> --title "<t>" [--tags a,b] [--license L]` | Register a new dataset directory + stub README. No data is fetched. |
| `hub download <slug> --file <url>` | Fetch a file into `raw/`. Stages at `raw/.partial/<name>` and atomically renames on sha256 verification. Records sha256 + size in README. Prompts if size exceeds `confirm_download_above`. |
| `hub add-version <slug> <version-name> --script <path> --input raw\|<ver>` | Produce a named processed version. See [next section](#processing-versions-with-add-version). |
| `hub pull <slug> [--version <name>] <dest>` | `rsync -a` the dataset's `raw/` (or the named version's `data/`) into `<dest>`. Safe against concurrent writers thanks to atomic rename discipline. |
| `hub reindex` | Rebuild `INDEX.md` from all READMEs. Usually not needed — writes auto-reindex. |
| `hub verify [<slug>]` | Re-hash every recorded file and compare to frontmatter/manifest. Takes exclusive `<slug>.lock`, so blocks concurrent writers on the same slug. Runs on all datasets if `<slug>` is omitted. |
| `hub rm <slug> --yes` | Remove a dataset. Atomic: renames to `<slug>.deleting` under lock, then `rm -rf`. `--yes` is required. |

### Global flags

| Flag | Purpose |
|---|---|
| `--root <path>` | Override `$HUB_ROOT` for this invocation. Bypasses remote dispatch (tells `main()` "we are already on the target filesystem"). Used internally by the SSH dispatcher; rarely needed by users. |
| `--version` | Print version. |
| `--help`, `-h` | Help text. |

## Processing versions with `add-version`

`hub add-version <slug> <version-name> --script <path> --input <raw|<ver>>` runs your script on the dataset's raw data (or on an upstream version) and installs the outputs atomically under `versions/<version-name>/`.

**Your script runs with these env vars:**

- `HUB_INPUT_DIR` — absolute path to the input directory (`raw/` or `versions/<other>/data/`). Treat as read-only.
- `HUB_OUTPUT_DIR` — absolute path to the directory you must write outputs into. This is a `.partial` staging directory; the CLI renames it to the final location only after your script succeeds.

**Your script must also write `schema.json` into `HUB_OUTPUT_DIR`** — a JSON list of `{name, type}` entries describing the output schema. If absent, the version is recorded with an empty schema and a warning is logged.

**Execution environment:**

- Your script's cwd is a per-run temp directory outside `$HUB_ROOT`.
- `script_timeout` (default 2 hours, set in `config.toml`) applies per invocation. On timeout the process is killed and the partial directory is removed.
- The runner is **not a sandbox**. Scripts execute with the hub user's full privileges. The trust model assumes you wrote the script yourself. Do not use `add-version` to run third-party code.

**Example: clean Iris into a tidy Parquet**

```python
# ~/scripts/iris-clean.py
import os, json
from pathlib import Path

import pandas as pd

src = Path(os.environ["HUB_INPUT_DIR"]) / "iris.data"
df = pd.read_csv(src, header=None, names=[
    "sepal_length", "sepal_width", "petal_length", "petal_width", "species"
]).dropna()

out = Path(os.environ["HUB_OUTPUT_DIR"])
df.to_parquet(out / "iris.parquet", index=False)

schema = [
    {"name": "sepal_length", "type": "float64"},
    {"name": "sepal_width",  "type": "float64"},
    {"name": "petal_length", "type": "float64"},
    {"name": "petal_width",  "type": "float64"},
    {"name": "species",      "type": "string"},
]
(out / "schema.json").write_text(json.dumps(schema))
```

Run it:

```bash
hub add-version iris cleaned-v1 --script ~/scripts/iris-clean.py --input raw
hub pull iris --version cleaned-v1 ~/projects/iris-analysis
```

The snapshot of your script is preserved at `$HUB_ROOT/datasets/iris/versions/cleaned-v1/script.py` together with its sha256 — any project that pulls this version knows exactly how the outputs were produced.

**Atomic install sequence** (all inside the slug lock, in order):

1. Refuse if `versions/<name>/` already exists.
2. Copy script to `versions/<name>.partial/script.py`; compute script sha256.
3. Run the script with `HUB_OUTPUT_DIR` pointing at `versions/<name>.partial/data/`.
4. Read `schema.json` from the output directory.
5. Write `manifest.json` (write-to-tmp + rename) inside the partial directory.
6. `rename(2)` `versions/<name>.partial/` → `versions/<name>/` — this is the atomic install point.
7. Update README frontmatter.
8. Acquire `index.lock`, rebuild `INDEX.md`.

Any failure between steps deletes the `.partial` directory. `README.md` and any prior `versions/<name>/` are never modified on failure.

**Note on remote hubs.** `add-version` cannot run against a remote `HUB_ROOT`. The script file has to live on the same machine as the hub. Copy your script to the server and run `hub add-version` there.

## Directory layout

```
$HUB_ROOT/
├── INDEX.md                          # AUTO-GENERATED, do not edit
├── .hub/
│   ├── config.toml                   # optional server-side config
│   └── locks/                        # POSIX file locks
│       ├── <slug>.lock
│       └── index.lock
└── datasets/
    └── <slug>/
        ├── README.md                 # YAML frontmatter + markdown body
        ├── raw/
        │   └── <downloaded files>
        └── versions/
            └── <version-name>/
                ├── data/             # script outputs
                │   └── <files>
                ├── script.py         # snapshot of generator
                └── manifest.json     # machine-readable provenance
```

The authoritative metadata is **always** `datasets/<slug>/README.md`. `INDEX.md` and each `manifest.json` are derived/cached from it.

### README frontmatter

```yaml
---
slug: iris
title: Iris flower dataset
tags: [classification, tabular, small]
summary: 150 flowers, 4 measurements, 3 species.
source:
  type: url                       # enum: github | hf | kaggle | url | manual
  url: https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data
  license: public-domain
  retrieved_at: 2026-04-18
  retrieved_by: hub-cli/0.1
raw:
  path: raw/
  files:
    - name: iris.data
      sha256: <64 hex>
      size_bytes: 4551
versions:
  - name: cleaned-v1
    path: versions/cleaned-v1/
    created_at: 2026-04-18T12:03:14Z
    input_version: raw
    script: versions/cleaned-v1/script.py
    script_sha256: <64 hex>
    schema:
      - {name: sepal_length, type: float64}
      # ...
---

# Iris flower dataset

Free-form markdown below the frontmatter. Use this for descriptions,
known issues, usage notes, etc.
```

**Slug rules:** `^[a-z0-9][a-z0-9-]{0,62}$` — lowercase, kebab-case, 1–63 chars. Enforced on every CLI call that takes a slug. Version names follow the same regex.

## Remote hub over SSH

### Setup

1. Pick a server reachable over SSH with passwordless key-based auth:
   ```bash
   ssh-copy-id user@nas.lan          # one-time
   ssh -o BatchMode=yes user@nas.lan true   # must succeed silently
   ```

2. Install `hub-cli` on both the client and the server (see [Install](#install)).

3. On the server, create the hub directory and make sure the SSH user owns it:
   ```bash
   ssh user@nas.lan 'mkdir -p /srv/data-hub && chown $(whoami) /srv/data-hub'
   ```

4. On the client, configure the remote root:
   ```toml
   # ~/.config/hub/config.toml
   root = "user@nas.lan:/srv/data-hub"
   ```

5. Verify:
   ```bash
   hub list     # first call goes via ssh; prints the (empty) index
   ```

### What runs where

| Command | Where it runs |
|---|---|
| `list`, `show`, `search` | Server (via ssh). Results streamed to your terminal; INDEX is cached locally. |
| `add`, `download`, `add-version`, `reindex`, `rm`, `verify` | Server (via ssh). Locks live on the server filesystem. |
| `pull` | Client — uses `rsync -a user@host:/srv/data-hub/datasets/<slug>/...`. Never SSH-wraps `hub`. |

The wrapper sets `HUB_REMOTE_DISPATCH=1` on the remote command so the server-side `hub` doesn't recursively re-dispatch. A manual `ssh user@host hub --root /srv/data-hub list` works because `--root` is also treated as an "already on target filesystem" signal.

### Argv safety

All `ssh` and `rsync` invocations use `subprocess.run([...], shell=False)` — no shell interpolation. Slugs and version names are regex-validated before being passed to any shell-adjacent command on either the client or the server.

## Offline use

When the remote server is unreachable, read commands degrade gracefully:

| Command | Offline behavior |
|---|---|
| `hub list` | Prints the cached `INDEX.md` from `~/.cache/hub/<sha1-of-root>/INDEX.md` with a staleness warning on stderr (shows cache mtime). |
| `hub search <q>` | Grep against the cached INDEX's data rows (header/separator lines filtered). Cannot search READMEs offline. |
| `hub show <slug>` | Fails — READMEs are not cached. Run `hub list` online first to refresh the cache, or log in to the server directly. |
| `hub list --tag X` | Does not *populate* the cache (filtered output would corrupt it). Returns filtered output but cache is unchanged. |
| Any write | Fails fast with the ssh error. |

The cache is refreshed automatically on every successful unfiltered `hub list`.

## Companion Claude Code Skill

When used with Claude Code, install the `local-data-hub` Skill so the LLM knows to check the hub before hitting the internet.

```bash
skill/scripts/install-hub.sh
```

This:

1. Installs `hub-cli` via `pipx` from this repo root.
2. Copies `skill/SKILL.md` and `skill/references/` into `~/.claude/skills/local-data-hub/`.

The Skill teaches the LLM to:

- `hub search <keywords>` before falling back to WebSearch / download.
- Use `hub plan-add <url>` to show candidates and wait for user confirmation.
- Register with `hub add`, fetch with `hub download`, process with `hub add-version` only when the result is reusable across projects.
- Never edit `INDEX.md` by hand, never `add-version` for one-off project-private derivations, never add datasets with unknown licenses without asking the user.

See `skill/SKILL.md` for the exact trigger description and decision tree.

## Development

```bash
# Set up
git clone <this repo>
cd local-hub-skill
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Run tests
pytest                                     # ~99 tests, ~12 seconds
pytest -q                                  # quiet
pytest tests/unit                          # unit only
pytest -m integration tests/integration    # concurrency + ssh-localhost

# See what hub thinks
HUB_ROOT=/tmp/hub-playground hub --help
```

### Integration tests

- `tests/integration/test_concurrency.py` — three scenarios covering concurrent add-on-different-slugs, pull-during-add-version, and verify-waits-for-concurrent-write.
- `tests/integration/test_smoke.py` — one end-to-end test that ssh-wraps a local hub. Skipped if `ssh localhost true` fails. On macOS, enable *System Settings → Sharing → Remote Login* to run it; on Linux, ensure `sshd` is listening and your key is in `~/.ssh/authorized_keys`.

### Project structure

```
src/hub/
├── __init__.py
├── __main__.py           # click entry + remote dispatch + offline cache routing
├── validators.py         # slug/version regex
├── config.py             # ~/.config/hub/config.toml + HUB_ROOT
├── paths.py              # RootPath (local vs ssh://user@host:/path)
├── atomic.py             # write_atomic_text, stage_and_rename, sweep_orphans
├── locks.py              # slug_lock, index_lock with ordering guard
├── metadata.py           # Frontmatter parse/write, manifest I/O
├── index.py              # INDEX.md rebuild
├── downloader.py         # HTTP download with staging + sha256
├── script_runner.py      # add-version user-script execution
├── remote.py             # ssh argv builder, run_remote_captured
├── cache.py              # ~/.cache/hub/<hub-id>/ offline index cache
└── verbs/
    ├── reads.py          # list, show, search, plan-add
    ├── writes.py         # add, download, reindex, verify, rm
    ├── pull.py           # pull (rsync wrapper)
    └── add_version.py    # the complex one
```

### Design docs

The full design spec and implementation plan live under `docs/superpowers/` (which is gitignored — they're development artifacts, not part of the public API). If you want the architectural rationale, look there.

## Troubleshooting

### `hub --version` prints `hub, version unknown`

You haven't installed the package, or you're running from a checkout without `pip install -e .`. Run the install command and try again.

### `ssh: connect to host localhost port 22: Connection refused`

The ssh-localhost integration test needs a running sshd. On macOS, enable *System Settings → Sharing → Remote Login* and make sure your public key is in `~/.ssh/authorized_keys`.

### `rsync: command not found`

`hub pull` shells out to `rsync`. Install it (`brew install rsync` on macOS, though macOS ships one; `apt install rsync` on Debian/Ubuntu).

### `error: HUB_ROOT not set`

Set `$HUB_ROOT` or create `~/.config/hub/config.toml` with a `root = "…"` line.

### Lock file seems stuck

File locks are released on process exit. If a crashed process left a stale lock, check `$HUB_ROOT/.hub/locks/`: the files are `filelock`-managed (POSIX `fcntl`). Deleting them is safe iff no `hub` process is running. `hub verify` and `hub reindex` re-acquire cleanly.

### "dataset already exists" on `hub add`

Intentional — `hub add` refuses to overwrite. To replace a dataset, `hub rm <slug> --yes` first.

### `warning: script did not write schema.json`

Your `add-version` script didn't write `schema.json` in `HUB_OUTPUT_DIR`. The version is still created, but with an empty schema. Add a two-line `json.dump([...], open(...))` at the end of your script.

### Large download without confirmation prompt

`confirm_download_above` applies only when the server sends a `Content-Length` header. Chunked-transfer-encoded responses (no content-length) don't trigger the prompt. This is intentional — unknown sizes can't be judged in advance.

### `hub add-version` with a remote hub root

Not supported — the script file has to live on the same filesystem as the hub. Copy the script to the server, SSH in, and run `hub add-version` there (where `HUB_ROOT` is a local path).
