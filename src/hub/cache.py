from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .atomic import write_atomic_text


def hub_id(root_raw: str) -> str:
    return hashlib.sha1(root_raw.encode()).hexdigest()


def cache_dir_for(root_raw: str) -> Path:
    home = Path(os.environ.get("HOME", os.path.expanduser("~")))
    d = home / ".cache" / "hub" / hub_id(root_raw)
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_cached_index(root_raw: str) -> str | None:
    p = cache_dir_for(root_raw) / "INDEX.md"
    if p.exists():
        return p.read_text()
    return None


def write_cached_index(root_raw: str, content: str) -> None:
    write_atomic_text(cache_dir_for(root_raw) / "INDEX.md", content)
