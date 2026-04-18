from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import requests


def filename_from_url(url: str) -> str:
    name = Path(urlparse(url).path).name
    if not name:
        raise ValueError(f"cannot infer filename from URL {url!r}")
    return name


def download_and_stage(
    url: str,
    raw_dir: Path,
    *,
    confirm_threshold: int | None = None,
    confirm_fn: Callable[[int], bool] | None = None,
) -> tuple[str, str, int]:
    """Fetch `url` into raw_dir. Returns (filename, sha256, size_bytes).

    Uses raw_dir/.partial/<filename> as staging; atomically renames on success.

    If `confirm_threshold` is given and the HTTP Content-Length exceeds it, calls
    `confirm_fn(size)` and aborts with RuntimeError if it returns False.
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
        if confirm_threshold is not None and confirm_fn is not None:
            content_length = resp.headers.get("content-length")
            if content_length and int(content_length) > confirm_threshold:
                if not confirm_fn(int(content_length)):
                    raise RuntimeError(
                        f"user declined large download ({content_length} bytes)"
                    )
        with open(staging, "wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                h.update(chunk)
                f.write(chunk)
                size += len(chunk)

    os.rename(staging, final)
    if not any(partial_dir.iterdir()):
        partial_dir.rmdir()
    return name, h.hexdigest(), size
