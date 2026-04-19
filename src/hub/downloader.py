from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse

import requests

_CD_FILENAME_STAR_RE = re.compile(
    r"filename\*\s*=\s*([^']*)'[^']*'([^;]+)",
    re.IGNORECASE,
)
_CD_FILENAME_RE = re.compile(
    r'filename\s*=\s*("([^"]*)"|\'([^\']*)\'|([^;]+))',
    re.IGNORECASE,
)


def filename_from_url(url: str) -> str:
    name = Path(urlparse(url).path).name
    if not name:
        raise ValueError(f"cannot infer filename from URL {url!r}")
    return name


def _filename_from_content_disposition(header: str) -> str | None:
    """Extract the filename parameter from a Content-Disposition header.

    Handles both plain `filename="foo.zip"` and RFC5987 `filename*=UTF-8''foo.zip`
    forms. Prefers the `filename*` variant when present (RFC 6266 §4.3).
    Returns None if no usable filename is found.
    """
    if not header:
        return None
    # RFC 5987: filename*=charset'language'percent-encoded-value
    m = _CD_FILENAME_STAR_RE.search(header)
    if m:
        charset = (m.group(1) or "utf-8").strip()
        value = m.group(2).strip()
        try:
            return unquote(value, encoding=charset)
        except Exception:
            pass
    m = _CD_FILENAME_RE.search(header)
    if m:
        # groups: 2=double-quoted content, 3=single-quoted content, 4=unquoted
        return (m.group(2) or m.group(3) or m.group(4) or "").strip()
    return None


def download_and_stage(
    url: str,
    raw_dir: Path,
    *,
    confirm_threshold: int | None = None,
    confirm_fn: Callable[[int], bool] | None = None,
) -> tuple[str, str, int]:
    """Fetch `url` into raw_dir. Returns (filename, sha256, size_bytes).

    Uses raw_dir/.partial/<filename> as staging; atomically renames on success.
    The filename is taken from the response's Content-Disposition header when
    present, falling back to the URL's last path segment.

    If `confirm_threshold` is given and the HTTP Content-Length exceeds it, calls
    `confirm_fn(size)` and aborts with RuntimeError if it returns False.
    """
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()

        name = (
            _filename_from_content_disposition(resp.headers.get("content-disposition", ""))
            or filename_from_url(url)
        )
        partial_dir = raw_dir / ".partial"
        partial_dir.mkdir(parents=True, exist_ok=True)
        staging = partial_dir / name
        final = raw_dir / name

        if final.exists():
            raise FileExistsError(f"{final} already exists; remove it first")

        if confirm_threshold is not None and confirm_fn is not None:
            content_length = resp.headers.get("content-length")
            if content_length and int(content_length) > confirm_threshold:
                if not confirm_fn(int(content_length)):
                    raise RuntimeError(
                        f"user declined large download ({content_length} bytes)"
                    )

        h = hashlib.sha256()
        size = 0
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
