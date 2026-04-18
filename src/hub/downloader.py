from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import requests


def filename_from_url(url: str) -> str:
    name = Path(urlparse(url).path).name
    if not name:
        raise ValueError(f"cannot infer filename from URL {url!r}")
    return name


def download_and_stage(url: str, raw_dir: Path) -> tuple[str, str, int]:
    """Fetch `url` into raw_dir. Returns (filename, sha256, size_bytes).

    Uses raw_dir/.partial/<filename> as staging; atomically renames on success.
    """
    name = filename_from_url(url)
    partial_dir = raw_dir / ".partial"
    partial_dir.mkdir(parents=True, exist_ok=True)
    staging = partial_dir / name
    final = raw_dir / name

    if final.exists():
        raise FileExistsError(f"{final} already exists; remove it first")

    h = hashlib.sha256()
    size = 0
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(staging, "wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                h.update(chunk)
                f.write(chunk)
                size += len(chunk)

    import os
    os.rename(staging, final)
    if not any(partial_dir.iterdir()):
        partial_dir.rmdir()
    return name, h.hexdigest(), size
