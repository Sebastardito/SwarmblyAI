"""Per-OS user data directories.

The repository contains code only. All user data (documents, wiki, outputs,
database, identity, logs) lives in a data directory chosen per platform and
created on first run. Everything here is configurable at runtime, but these
defaults are the documented, reproducible layout.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "Swarmbly"


def default_data_dir() -> Path:
    """Platform default, following each OS's conventions."""
    override = os.environ.get("SWARMBLY_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / APP_DIR_NAME
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME.lower()


class DataDirs:
    """The logical ``output/`` directory layout plus LCE data directories.

    Every subdirectory below is created on demand by :meth:`ensure`.
    """

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else default_data_dir()

    # -- layout -------------------------------------------------------------
    @property
    def identity(self) -> Path:
        return self.root / "identity"

    @property
    def sources(self) -> Path:
        """LCE layer 0: the user's raw, immutable documents."""
        return self.root / "sources"

    @property
    def wiki(self) -> Path:
        """LCE layer 1: anchored wiki state (JSON + git history)."""
        return self.root / "wiki"

    @property
    def adapters(self) -> Path:
        """LCE layer 2 (later phases). Never shared with the network."""
        return self.root / "adapters"

    @property
    def capsules(self) -> Path:
        """LCE layer 3 social capsules (pull-only)."""
        return self.root / "capsules"

    @property
    def output(self) -> Path:
        """Logical default output directory."""
        return self.root / "output"

    @property
    def exports(self) -> Path:
        return self.output / "exports"

    @property
    def reports(self) -> Path:
        return self.output / "reports"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    def db_path(self) -> Path:
        return self.root / "app.db"

    def config_path(self) -> Path:
        return self.root / "config.json"

    def identity_key_path(self) -> Path:
        return self.identity / "node_key"

    def all(self) -> list[Path]:
        return [
            self.root,
            self.identity,
            self.sources,
            self.wiki,
            self.adapters,
            self.capsules,
            self.output,
            self.exports,
            self.reports,
            self.logs,
            self.cache,
        ]

    def ensure(self) -> None:
        for path in self.all():
            path.mkdir(parents=True, exist_ok=True)

    def as_dict(self) -> dict[str, str]:
        return {name: str(getattr(self, name)) for name in
                ("root", "identity", "sources", "wiki", "adapters", "capsules",
                 "output", "exports", "reports", "logs", "cache")}
