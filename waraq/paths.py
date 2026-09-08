from __future__ import annotations

import os
import sys
from pathlib import Path


def application_data_dir() -> Path:
    """Return Warraq's private desktop data directory."""
    override = os.environ.get("WARRAQ_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Warraq"
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Warraq"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "waraq"


def resource_path(*parts: str) -> Path:
    return Path(__file__).resolve().parent.joinpath(*parts)
