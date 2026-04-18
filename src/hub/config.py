from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    root: str
    confirm_download_above: int
    script_timeout: int
    log_level: str

    class MissingRoot(RuntimeError):
        pass


DEFAULTS = {
    "confirm_download_above": 500 * 1024 * 1024,
    "script_timeout": 7200,
    "log_level": "info",
}


def load_config() -> Config:
    home = Path(os.environ.get("HOME", os.path.expanduser("~")))
    path = home / ".config" / "hub" / "config.toml"
    data: dict[str, object] = {}
    if path.exists():
        data = tomllib.loads(path.read_text())

    env_root = os.environ.get("HUB_ROOT")
    root = env_root if env_root else data.get("root")
    if not root:
        raise Config.MissingRoot(
            f"no HUB_ROOT env var and no 'root' in {path}"
        )
    return Config(
        root=str(root),
        confirm_download_above=int(data.get("confirm_download_above", DEFAULTS["confirm_download_above"])),
        script_timeout=int(data.get("script_timeout", DEFAULTS["script_timeout"])),
        log_level=str(data.get("log_level", DEFAULTS["log_level"])),
    )
