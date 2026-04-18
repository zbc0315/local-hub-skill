import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner


def _hub_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HUB_ROOT"] = str(root)
    return env


@pytest.mark.integration
def test_two_adds_on_different_slugs_both_succeed(local_root: Path) -> None:
    """Two `hub add` subprocess invocations on different slugs both succeed.
    INDEX.md contains both entries after the race resolves."""
    env = _hub_env(local_root)
    def _popen(slug: str) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-m", "hub", "add", slug,
             "--source", "https://e.com/x",
             "--title", slug, "--license", "CC0-1.0"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    p1 = _popen("one"); p2 = _popen("two")
    out1, err1 = p1.communicate(timeout=30)
    out2, err2 = p2.communicate(timeout=30)
    assert p1.returncode == 0, err1.decode()
    assert p2.returncode == 0, err2.decode()

    idx = (local_root / "INDEX.md").read_text()
    assert "one" in idx
    assert "two" in idx


@pytest.mark.integration
def test_pull_during_add_version_reads_prior_version(local_root: Path) -> None:
    """pull of version v1 must not see mid-build partial state of v2."""
    from hub.__main__ import cli

    class FakeResp:
        def __init__(self, body: bytes) -> None:
            self._b = body
            self.headers: dict[str, str] = {}
        def iter_content(self, chunk_size: int = 8192):
            yield self._b
        def raise_for_status(self) -> None: ...
        def __enter__(self): return self
        def __exit__(self, *a: object) -> None: ...

    with patch("hub.downloader.requests.get", return_value=FakeResp(b"col\n1\n")):
        assert CliRunner().invoke(cli, [
            "add", "tiny", "--source", "https://e.com/x.csv",
            "--title", "T", "--license", "CC0-1.0",
        ]).exit_code == 0
        assert CliRunner().invoke(cli, [
            "download", "tiny", "--file", "https://e.com/x.csv",
        ]).exit_code == 0

    noop = local_root / "noop.py"
    noop.write_text(
        "#!" + sys.executable + "\n"
        "import os, json, shutil\n"
        "src = os.path.join(os.environ['HUB_INPUT_DIR'], 'x.csv')\n"
        "dst = os.path.join(os.environ['HUB_OUTPUT_DIR'], 'x.csv')\n"
        "shutil.copy(src, dst)\n"
        "json.dump([], open(os.path.join(os.environ['HUB_OUTPUT_DIR'], 'schema.json'), 'w'))\n"
    )
    noop.chmod(0o755)
    assert CliRunner().invoke(cli, [
        "add-version", "tiny", "v1",
        "--script", str(noop), "--input", "raw",
    ]).exit_code == 0

    sentinel = local_root / "v2-started"
    slow = local_root / "slow.py"
    slow.write_text(
        "#!" + sys.executable + "\n"
        "import os, time, json\n"
        f"open(r'{sentinel}', 'w').write('1')\n"
        "time.sleep(5)\n"
        "open(os.path.join(os.environ['HUB_OUTPUT_DIR'], 'out.csv'), 'w').write('x\\n')\n"
        "json.dump([], open(os.path.join(os.environ['HUB_OUTPUT_DIR'], 'schema.json'), 'w'))\n"
    )
    slow.chmod(0o755)

    env = _hub_env(local_root)
    v2 = subprocess.Popen(
        [sys.executable, "-m", "hub", "add-version", "tiny", "v2",
         "--script", str(slow), "--input", "raw"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 15
        while not sentinel.exists():
            if v2.poll() is not None:
                raise RuntimeError(
                    f"v2 subprocess exited early: {v2.stderr.read().decode()}"
                )
            if time.monotonic() > deadline:
                raise RuntimeError("v2 never wrote sentinel")
            time.sleep(0.05)

        dest = local_root / "workspace"
        pull = subprocess.run(
            [sys.executable, "-m", "hub", "pull", "tiny", "--version", "v1", str(dest)],
            env=env, capture_output=True, timeout=30,
        )
        assert pull.returncode == 0, pull.stderr.decode()
        assert (dest / "x.csv").read_text() == "col\n1\n"
    finally:
        v2.wait(timeout=30)
    assert v2.returncode == 0, v2.stderr.read().decode()


@pytest.mark.integration
def test_verify_waits_for_concurrent_write_on_same_slug(local_root: Path) -> None:
    """verify and add-version/download both take exclusive slug_lock.
    verify must block until the concurrent writer releases the lock, then succeed."""
    from hub.__main__ import cli

    class FakeResp:
        def __init__(self, body: bytes) -> None:
            self._b = body
            self.headers: dict[str, str] = {}
        def iter_content(self, chunk_size: int = 8192):
            yield self._b
        def raise_for_status(self) -> None: ...
        def __enter__(self): return self
        def __exit__(self, *a: object) -> None: ...

    # Seed: add + download so we have recorded sha256 for verify to check.
    with patch("hub.downloader.requests.get", return_value=FakeResp(b"col\n1\n")):
        assert CliRunner().invoke(cli, [
            "add", "tiny", "--source", "https://e.com/x.csv",
            "--title", "T", "--license", "CC0-1.0",
        ]).exit_code == 0
        assert CliRunner().invoke(cli, [
            "download", "tiny", "--file", "https://e.com/x.csv",
        ]).exit_code == 0

    sentinel = local_root / "slow-started"
    slow = local_root / "slow.py"
    slow.write_text(
        "#!" + sys.executable + "\n"
        "import os, time, json\n"
        f"open(r'{sentinel}', 'w').write('1')\n"
        "time.sleep(3)\n"
        "open(os.path.join(os.environ['HUB_OUTPUT_DIR'], 'out.csv'), 'w').write('x\\n')\n"
        "json.dump([], open(os.path.join(os.environ['HUB_OUTPUT_DIR'], 'schema.json'), 'w'))\n"
    )
    slow.chmod(0o755)

    env = _hub_env(local_root)

    # Start slow writer that takes slug_lock for ~3s.
    writer = subprocess.Popen(
        [sys.executable, "-m", "hub", "add-version", "tiny", "v1",
         "--script", str(slow), "--input", "raw"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 15
        while not sentinel.exists():
            if writer.poll() is not None:
                raise RuntimeError(
                    f"writer exited early: {writer.stderr.read().decode()}"
                )
            if time.monotonic() > deadline:
                raise RuntimeError("writer never wrote sentinel")
            time.sleep(0.05)

        # writer holds the slug lock now. verify must wait.
        t0 = time.monotonic()
        verify = subprocess.run(
            [sys.executable, "-m", "hub", "verify", "tiny"],
            env=env, capture_output=True, timeout=30,
        )
        elapsed = time.monotonic() - t0
        assert verify.returncode == 0, verify.stderr.decode()
        # verify started while writer held lock; it must have waited >= 1s
        # (writer sleeps 3s total, we entered maybe ~0.5s in).
        assert elapsed >= 1.0, f"verify did not wait for slug lock (elapsed {elapsed}s)"
    finally:
        writer.wait(timeout=30)
    assert writer.returncode == 0, writer.stderr.read().decode()
