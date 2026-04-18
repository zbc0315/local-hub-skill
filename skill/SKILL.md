---
name: local-data-hub
description: Use when the task needs a public/open-source dataset — benchmark data, reference corpora, research datasets, tabular data from public sources, CSV/Parquet/JSON from GitHub/HuggingFace/Kaggle/official sites. Before using WebSearch or downloading from the internet, check the local data hub (`hub list` / `hub search`) for a cached copy. If present, `hub pull` it into the working directory. If absent, use `hub plan-add` to surface candidate sources, confirm with the user, then `hub add` + `hub download`.
---

# Local Data Hub

You have access to a shared dataset ledger managed by the `hub` CLI. All public/open-source data used across projects lives there. Consult it before downloading anything from the internet.

## Does NOT apply to
- Project-generated data
- User-provided one-off files
- Private business data
- Ad-hoc web scraping

## Decision tree

```
Need data?
├── Is it public / reusable? (benchmark, research dataset, open-gov, etc.)
│   ├── No → skill does not apply.
│   └── Yes → continue.
├── hub search <keywords> → any hits?
│   ├── Yes → hub show <slug>; decide raw vs a version; hub pull → use.
│   └── No →
│       ├── hub plan-add <query-or-url> → present candidates to user.
│       ├── Wait for user to pick one candidate OR provide a URL.
│       ├── hub add <slug> --source <url> --title "..." --tags ...
│       ├── hub download <slug> --file <url>    (>500 MB triggers confirm)
│       ├── If preprocessing is needed AND reusable across projects:
│       │     write script → hub add-version <slug> <ver> --script ... --input raw
│       └── hub pull into the workspace → use.
```

## Command cheatsheet

| Read | Purpose |
|---|---|
| `hub list [--tag T]` | overview of all datasets |
| `hub search <q>`     | fuzzy substring search |
| `hub show <slug>`    | frontmatter + description of one dataset |

| Write | Purpose |
|---|---|
| `hub plan-add <query-or-url>` | JSON candidate list — does NOT download |
| `hub add <slug> --source <url> --title ...` | register a new dataset (stub) |
| `hub download <slug> --file <url>` | fetch into `raw/` |
| `hub add-version <slug> <ver> --script <path> --input raw\|<ver>` | create a processed version |
| `hub pull <slug> [--version <ver>] <dest>` | rsync into your project workspace |
| `hub reindex` | rebuild INDEX.md |
| `hub verify [<slug>]` | rehash and compare |
| `hub rm <slug> --yes` | delete |

Full CLI reference: [`references/cli-reference.md`](references/cli-reference.md).
Full schema reference: [`references/metadata-schema.md`](references/metadata-schema.md).

## Red-flag guardrails

- **Do not** skip `hub search` and go straight to downloading, even when "it feels like it won't hit."
- **Do not** `hub add-version` for project-private derivations — only reusable preprocessing belongs in the hub.
- **Do not** use `hub add-version` to run third-party or untrusted scripts. The runner is not a sandbox; scripts execute with the SSH user's privileges.
- **Do not** edit `INDEX.md` by hand — it is generated.
- **Do not** `hub add` when the license is unknown — ask the user first.
- **Always** surface the `hub plan-add` candidates to the user before `hub download`.
