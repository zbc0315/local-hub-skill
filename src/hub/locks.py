from __future__ import annotations

import contextvars
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from filelock import FileLock

from .atomic import sweep_orphans
from .validators import validate_slug


class LockOrderError(RuntimeError):
    """Raised when lock acquisition violates the defined ordering."""


_held_slug: contextvars.ContextVar[str | None] = contextvars.ContextVar("held_slug", default=None)
_held_index: contextvars.ContextVar[bool] = contextvars.ContextVar("held_index", default=False)


def _locks_dir(root: Path) -> Path:
    d = root / ".hub" / "locks"
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def slug_lock(root: str | Path, slug: str) -> Iterator[None]:
    validate_slug(slug)
    root = Path(root)
    if _held_index.get():
        raise LockOrderError("cannot acquire slug_lock while holding index_lock")
    if _held_slug.get() is not None:
        raise LockOrderError(
            f"already holding slug_lock for {_held_slug.get()!r}; cannot nest"
        )
    lock = FileLock(str(_locks_dir(root) / f"{slug}.lock"))
    with lock:
        token = _held_slug.set(slug)
        try:
            # Sweep orphan staging directories from prior crashes on acquire.
            sweep_orphans(root, slug)
            yield
        finally:
            _held_slug.reset(token)


@contextmanager
def index_lock(root: str | Path) -> Iterator[None]:
    root = Path(root)
    lock = FileLock(str(_locks_dir(root) / "index.lock"))
    with lock:
        token = _held_index.set(True)
        try:
            yield
        finally:
            _held_index.reset(token)
