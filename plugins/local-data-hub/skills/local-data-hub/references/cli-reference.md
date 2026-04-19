# `hub` CLI reference

## Read verbs (no lock)

### `hub list [--tag T]`
Prints `INDEX.md`; `--tag` filters rows.

### `hub search <query>`
Fuzzy substring match over INDEX summaries + all README frontmatter/bodies.

### `hub show <slug>`
Prints the full `datasets/<slug>/README.md` (frontmatter + body).

### `hub plan-add <query-or-url>`
MVP: if the argument is a URL, emits it as a single JSON candidate. Otherwise emits `[]`.
Output is JSON to stdout — designed for programmatic consumption.

## Write verbs

### `hub add <slug> --source <url> --title <t> [--tags a,b] [--license L]`
Registers a new dataset (creates directory + stub README). Triggers reindex.

### `hub download <slug> --file <path-or-url>`
Fetches a file into `raw/`. Stages at `raw/.partial/<name>`, renames on sha256 verification.
The filename is taken from the response's `Content-Disposition` header when present (so
figshare-style `ndownloader/files/<id>` URLs save with their real name), falling back to
the URL path's last segment. Records sha256 + size in README. Triggers reindex.

### `hub import-file <slug> <local-path> [--as <name>]`
Copy an **existing local file** into a dataset's `raw/` directory — the manual-import
counterpart to `hub download`. Same atomic semantics (stage → sha256 → rename → update
README → reindex). Use when the hub machine can't fetch from the URL directly (e.g.
GitHub raw blocked from server network, Box/Drive session-only links): `scp` the file
to the hub host, then `hub import-file <slug> /path/to/file`. Use `--as <name>` to
override the stored filename (e.g. when source is a figshare numeric-ID path).
Only works with a **local** `HUB_ROOT` — remote hubs require `ssh <host> hub import-file ...`
run on the server itself.

### `hub add-version <slug> <version-name> --script <path> --input <raw|<ver>>`
Runs the script over the input version. See "Script convention" below.

### `hub pull <slug> [--version <name>] <dest>`
rsync the dataset's raw (or a named version's data) into `<dest>`. Read-only.

### `hub reindex`
Rebuild `INDEX.md` from all READMEs.

### `hub verify [<slug>]`
Re-hash every recorded file and compare to frontmatter/manifest. Takes exclusive `<slug>.lock`.

### `hub rm <slug> --yes`
Rename to `<slug>.deleting`, then `rm -rf`. Triggers reindex.

## Script convention for `add-version`

Env vars set for the script:
- `HUB_INPUT_DIR` — input directory (`raw/` or another version's `data/`). Read-only by convention.
- `HUB_OUTPUT_DIR` — output directory. Write your outputs here.

The script must write `schema.json` in `HUB_OUTPUT_DIR` as a list of `{name, type}`. If absent, schema is recorded as empty and a warning is logged.

- cwd is a temp directory outside `$HUB_ROOT`.
- Default timeout 2h (configurable via `script_timeout` in `~/.config/hub/config.toml`).
- Trust model: single-user; NOT a sandbox. Do not use `add-version` for third-party code.

## Lock semantics

- Exclusive file locks on `$HUB_ROOT/.hub/locks/<slug>.lock` and `.../index.lock`.
- Acquisition order: `<slug>.lock` before `index.lock`, never nested `<slug>.lock`s.
- All reads are lock-free.

## Remote transport

When `HUB_ROOT` = `user@host:/path`:
- Reads and writes execute server-side via `ssh host hub --root /path <verb> ...`
- `pull` uses `rsync -a`.
- Offline read fallback: `~/.cache/hub/<sha1-of-root>/INDEX.md`.
