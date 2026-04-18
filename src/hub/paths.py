from __future__ import annotations

import re
from dataclasses import dataclass

from .validators import validate_slug

REMOTE_RE = re.compile(r"^([^@:]+)@([^:]+):(/.+)$")


@dataclass(frozen=True)
class RootPath:
    raw: str
    user: str | None
    host: str | None
    path: str  # absolute path on the target filesystem (local or remote)

    @property
    def is_remote(self) -> bool:
        return self.host is not None

    @property
    def local_path(self) -> str:
        if self.is_remote:
            raise RuntimeError("not a local root")
        return self.path

    @property
    def remote_path(self) -> str:
        if not self.is_remote:
            raise RuntimeError("not a remote root")
        return self.path

    @classmethod
    def parse(cls, raw: str) -> "RootPath":
        m = REMOTE_RE.match(raw)
        if m:
            user, host, path = m.group(1), m.group(2), m.group(3)
            return cls(raw=raw, user=user, host=host, path=path)
        if raw.startswith("/"):
            return cls(raw=raw, user=None, host=None, path=raw)
        raise ValueError(
            f"invalid HUB_ROOT {raw!r}: must be an absolute path or user@host:/path"
        )

    def dataset_path(self, slug: str) -> str:
        """Path usable by rsync/scp (includes user@host: for remote)."""
        validate_slug(slug)
        if self.is_remote:
            return f"{self.user}@{self.host}:{self.path}/datasets/{slug}"
        return f"{self.path}/datasets/{slug}"

    def server_dataset_path(self, slug: str) -> str:
        """Path on the server-side filesystem (never includes user@host:)."""
        validate_slug(slug)
        return f"{self.path}/datasets/{slug}"
