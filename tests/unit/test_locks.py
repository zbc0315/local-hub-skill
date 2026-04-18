from pathlib import Path

import pytest

from hub.locks import slug_lock, index_lock, LockOrderError


def _make_root(tmp_path: Path, slug: str = "covid-jhu") -> Path:
    (tmp_path / ".hub" / "locks").mkdir(parents=True, exist_ok=True)
    ds = tmp_path / "datasets" / slug
    ds.mkdir(parents=True)
    (ds / "raw" / ".partial").mkdir(parents=True)
    (ds / "raw" / ".partial" / "leftover").write_text("x")
    return tmp_path


def test_slug_lock_sweeps_orphans(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    with slug_lock(root, "covid-jhu"):
        assert not (root / "datasets" / "covid-jhu" / "raw" / ".partial").exists()


def test_lock_file_created_in_hub_locks(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    with slug_lock(root, "covid-jhu"):
        assert (root / ".hub" / "locks" / "covid-jhu.lock").exists()


def test_two_slug_locks_in_same_process_fail(tmp_path: Path) -> None:
    root = _make_root(tmp_path, "a")
    _make_root(tmp_path, "b")
    with slug_lock(root, "a"):
        with pytest.raises(LockOrderError):
            with slug_lock(root, "b"):
                pass


def test_index_lock_after_slug_ok(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    with slug_lock(root, "covid-jhu"):
        with index_lock(root):
            pass


def test_slug_lock_while_holding_index_fails(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    with index_lock(root):
        with pytest.raises(LockOrderError):
            with slug_lock(root, "covid-jhu"):
                pass


def test_slug_lock_excludes_concurrent(tmp_path: Path) -> None:
    """filelock actually blocks — use a subprocess to verify."""
    import subprocess, sys, textwrap
    root = _make_root(tmp_path)

    # Child writes a sentinel file once it holds the lock, so we don't race sleep().
    sentinel = tmp_path / "child-has-lock"
    child = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(f"""
            import time
            from pathlib import Path
            from hub.locks import slug_lock
            with slug_lock(r"{root}", "covid-jhu"):
                Path(r"{sentinel}").write_text("1")
                time.sleep(10)
        """)]
    )
    try:
        import time
        deadline = time.monotonic() + 5
        while not sentinel.exists():
            if time.monotonic() > deadline:
                raise RuntimeError("child never acquired lock")
            time.sleep(0.05)
        from filelock import Timeout, FileLock
        lock_path = root / ".hub" / "locks" / "covid-jhu.lock"
        with pytest.raises(Timeout):
            with FileLock(str(lock_path), timeout=0.2):
                pass
    finally:
        child.terminate()
        child.wait(timeout=5)
