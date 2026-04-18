# Metadata schema

README frontmatter is the single source of truth. `INDEX.md` and `manifest.json` are derived by `hub reindex`.

## `datasets/<slug>/README.md` frontmatter

```yaml
---
slug: covid-jhu
title: JHU COVID-19 Time Series
tags: [timeseries, health, covid]
summary: Daily global case/death counts by country, 2020-2023.
source:
  type: github              # Enum: github | hf | kaggle | url | manual
  url: https://github.com/CSSEGISandData/COVID-19
  license: CC-BY-4.0
  retrieved_at: 2026-04-18
  retrieved_by: hub-cli/0.1
raw:
  path: raw/
  files:
    - name: time_series_covid19_confirmed_global.csv
      sha256: <64 hex>
      size_bytes: 2458112
versions:
  - name: cleaned-2026-04
    path: versions/cleaned-2026-04/
    created_at: 2026-04-18
    input_version: raw           # "raw" or another version name
    script: versions/cleaned-2026-04/script.py
    script_sha256: <64 hex>
    schema:
      - {name: date, type: date}
      - {name: country, type: string}
      - {name: confirmed, type: int64}
    notes: ...
---
```

## Field rules

- `slug`: `^[a-z0-9][a-z0-9-]{0,62}$`. Enforced at every CLI entry point.
- Version names follow the same regex.
- `tags`: free-form, lowercase. Convention: domain + data type + topic.
- `source.type`: closed enum `github | hf | kaggle | url | manual`.
- `source.license`: SPDX id preferred; `unknown` allowed but warned.
- `raw.files[].sha256`: computed by `hub download`; never hand-edited.
- `versions[].input_version`: upstream version name or `raw`.
- `versions[].script_sha256`: sha256 of the snapshot in `versions/<name>/script.py`.
- `versions[].schema`: declared by the script (via `schema.json`), recorded by the CLI.

## `versions/<name>/manifest.json`

```json
{
  "name": "cleaned-2026-04",
  "created_at": "2026-04-18T12:03:14Z",
  "input_version": "raw",
  "script_sha256": "<64 hex>",
  "output_files": [
    {"name": "data/covid.parquet", "sha256": "<64 hex>", "size_bytes": 4128000}
  ],
  "schema": [...]
}
```
