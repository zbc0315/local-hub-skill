from pathlib import Path

import pytest

from hub.atomic import (
    write_atomic_text,
    write_atomic_json,
    stage_and_rename,
    sweep_orphans,
)


def test_write_atomic_text_writes_file(tmp_path: Path) -> None:
    target = tmp_path / "INDEX.md"
    write_atomic_text(target, "hello\n")
    assert target.read_text() == "hello\n"
    # no leftover .tmp
    assert not (tmp_path / "INDEX.md.tmp").exists()


def test_write_atomic_text_never_leaves_half(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "INDEX.md"
    target.write_text("OLD CONTENT\n")

    # Simulate crash after tmp write but before rename
    import os
    orig_rename = os.rename

    def boom(*a: object, **k: object) -> None:
        raise RuntimeError("crash")

    monkeypatch.setattr(os, "rename", boom)
    with pytest.raises(RuntimeError):
        write_atomic_text(target, "NEW CONTENT\n")
    # Original still intact, tmp file absent
    assert target.read_text() == "OLD CONTENT\n"
    assert not (tmp_path / "INDEX.md.tmp").exists()


def test_write_atomic_json(tmp_path: Path) -> None:
    target = tmp_path / "manifest.json"
    write_atomic_json(target, {"a": 1})
    assert target.read_text() == '{"a": 1}'


def test_stage_and_rename_moves_dir(tmp_path: Path) -> None:
    staging = tmp_path / "versions" / "v1.partial"
    staging.mkdir(parents=True)
    (staging / "data").mkdir()
    (staging / "data" / "file.txt").write_text("x")

    final = tmp_path / "versions" / "v1"
    stage_and_rename(staging, final)
    assert not staging.exists()
    assert (final / "data" / "file.txt").read_text() == "x"


def test_sweep_orphans_removes_partials(tmp_path: Path) -> None:
    (tmp_path / "datasets" / "tiny" / "versions" / "v1.partial").mkdir(parents=True)
    (tmp_path / "datasets" / "tiny" / "versions" / "v1.partial" / "junk").write_text("x")
    (tmp_path / "datasets" / "tiny" / "raw" / ".partial").mkdir(parents=True)
    (tmp_path / "datasets" / "tiny" / "raw" / ".partial" / "junk.csv").write_text("y")

    sweep_orphans(tmp_path, "tiny")

    ds = tmp_path / "datasets" / "tiny"
    assert not (ds / "versions" / "v1.partial").exists()
    assert not (ds / "raw" / ".partial").exists()


def test_sweep_orphans_removes_deleting_at_parent(tmp_path: Path) -> None:
    (tmp_path / "datasets" / "tiny.deleting").mkdir(parents=True)
    (tmp_path / "datasets" / "tiny.deleting" / "leftover").write_text("x")

    sweep_orphans(tmp_path, "tiny")

    assert not (tmp_path / "datasets" / "tiny.deleting").exists()


def test_sweep_orphans_noop_if_clean(tmp_path: Path) -> None:
    ds = tmp_path / "datasets" / "tiny"
    (ds / "raw").mkdir(parents=True)
    (ds / "raw" / "real.csv").write_text("z")
    sweep_orphans(tmp_path, "tiny")
    assert (ds / "raw" / "real.csv").exists()


def test_sweep_orphans_handles_missing_dataset(tmp_path: Path) -> None:
    # No dataset dir at all — should not raise.
    sweep_orphans(tmp_path, "never-existed")
