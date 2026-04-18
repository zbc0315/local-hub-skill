from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def write_atomic_text(target: Path, content: str) -> None:
    """Write `content` to `target` atomically via a sibling `.tmp` file + rename."""
    tmp = target.with_name(target.name + ".tmp")
    try:
        tmp.write_text(content)
        os.rename(tmp, target)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise


def write_atomic_json(target: Path, data: object) -> None:
    write_atomic_text(target, json.dumps(data))


def stage_and_rename(staging: Path, final: Path) -> None:
    """Rename a staging directory to its final name. Both must be on the same fs."""
    if final.exists():
        raise FileExistsError(f"{final} already exists")
    os.rename(staging, final)


def sweep_orphans(root: Path, slug: str) -> None:
    """Remove known orphan staging paths for `slug` under `root`.

    Removes:
      - datasets/<slug>/versions/*.partial/  (from crashed add-version)
      - datasets/<slug>/raw/.partial/        (from crashed download)
      - datasets/<slug>.deleting/            (from crashed rm)

    Only touches paths it explicitly recognizes. Noop if dataset dir missing.
    """
    dataset_dir = root / "datasets" / slug
    if dataset_dir.is_dir():
        versions = dataset_dir / "versions"
        if versions.is_dir():
            for child in versions.iterdir():
                if child.is_dir() and child.name.endswith(".partial"):
                    shutil.rmtree(child)
        raw_partial = dataset_dir / "raw" / ".partial"
        if raw_partial.is_dir():
            shutil.rmtree(raw_partial)

    deleting = root / "datasets" / f"{slug}.deleting"
    if deleting.is_dir():
        shutil.rmtree(deleting)
