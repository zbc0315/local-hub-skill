import sys
from unittest.mock import patch, MagicMock

import pytest

from hub.remote import build_ssh_argv


def test_build_ssh_argv_uses_argv_not_shell() -> None:
    argv = build_ssh_argv(
        user="jim", host="nas.lan",
        remote_hub_cmd=["hub", "--root", "/srv/data-hub", "list", "--tag", "t"],
    )
    assert argv[0] == "ssh"
    assert "-o" in argv
    assert "jim@nas.lan" in argv
    tail = argv[argv.index("jim@nas.lan") + 1:]
    assert tail[:2] == ["env", "HUB_REMOTE_DISPATCH=1"]
    assert tail[2:] == ["hub", "--root", "/srv/data-hub", "list", "--tag", "t"]


def _fake_proc(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


def test_main_dispatches_to_ssh_when_root_is_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", "jim@nas.lan:/srv/data-hub")
    monkeypatch.delenv("HUB_REMOTE_DISPATCH", raising=False)
    monkeypatch.setattr(sys, "argv", ["hub", "list"])

    with patch("hub.remote.subprocess.run", return_value=_fake_proc(stdout=b"covid-jhu\n")) as m:
        from hub.__main__ import main
        with pytest.raises(SystemExit) as ex:
            main()
    assert ex.value.code == 0

    argv = m.call_args.args[0]
    assert argv[0] == "ssh"
    assert "jim@nas.lan" in argv
    assert "hub" in argv and "--root" in argv and "/srv/data-hub" in argv and "list" in argv
    assert m.call_args.kwargs.get("shell", False) is False


def test_main_does_not_redispatch_when_explicit_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", "jim@nas.lan:/srv/data-hub")
    monkeypatch.setattr(sys, "argv", ["hub", "--root", "/srv/data-hub", "list"])

    with patch("hub.remote.subprocess.run") as m:
        from hub.__main__ import main
        with pytest.raises(SystemExit):
            main()
    assert not m.called


def test_main_does_not_redispatch_with_env_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUB_ROOT", "jim@nas.lan:/srv/data-hub")
    monkeypatch.setenv("HUB_REMOTE_DISPATCH", "1")
    monkeypatch.setattr(sys, "argv", ["hub", "list"])

    with patch("hub.remote.subprocess.run") as m:
        from hub.__main__ import main
        with pytest.raises(SystemExit):
            main()
    assert not m.called


def test_main_pull_is_never_remote_dispatched(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("HUB_ROOT", "jim@nas.lan:/srv/data-hub")
    monkeypatch.setattr(sys, "argv", ["hub", "pull", "tiny", str(tmp_path)])

    with patch("hub.remote.subprocess.run") as m:
        from hub.__main__ import main
        with pytest.raises(SystemExit):
            main()
    for call in m.call_args_list:
        argv = call.args[0] if call.args else call.kwargs.get("args", [])
        assert argv[0] != "ssh", f"pull was dispatched via ssh: {argv}"
