"""Resolve paths for read-only resources (catalog, adapters, schemas, raw_corpus)
vs writable per-user data (history, feedback, cache) — regardless of whether
the app is running from a git checkout or from a PyInstaller-frozen ``.app``.

In source-tree mode: resources live next to the working directory, writables
go under ``./data/`` and ``./.cache/`` (current behavior).

In frozen mode (``sys.frozen`` is set by PyInstaller): resources are unpacked
to ``sys._MEIPASS``; writables go under platform-conventional user dirs
(``~/Library/Application Support/PromptGenius`` on macOS).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


_APP_NAME = "PromptGenius"


def is_bundled() -> bool:
    """True when running inside a PyInstaller-built executable."""

    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def bundled_root() -> Path:
    """Directory where PyInstaller unpacked the read-only resources."""

    if is_bundled():
        return Path(sys._MEIPASS)
    # In source mode, callers should fall back to the cwd / repo root.
    return Path.cwd()


def resource_path(name: str) -> Path:
    """Path to a bundled read-only resource (catalog/, schemas/, etc).

    Tries the bundled root first; falls back to the source-tree cwd path so
    source-mode runs keep working unchanged.
    """

    if is_bundled():
        candidate = bundled_root() / name
        if candidate.exists():
            return candidate
    # Source mode (or bundled resource that got moved): try cwd.
    return Path(name)


def user_data_dir() -> Path:
    """Writable per-user data dir for history, feedback, versions, usage."""

    if is_bundled():
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / _APP_NAME
        if sys.platform.startswith("win"):
            base = os.environ.get("APPDATA") or str(Path.home())
            return Path(base) / _APP_NAME
        return Path(
            os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"),
        ) / _APP_NAME
    # Source mode keeps the original relative ``data/`` for git-friendliness.
    return Path("data")


def user_cache_dir() -> Path:
    """Writable per-user cache dir for embeddings / vocab / corpus indexes."""

    if is_bundled():
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Caches" / _APP_NAME
        if sys.platform.startswith("win"):
            base = os.environ.get("LOCALAPPDATA") or str(Path.home())
            return Path(base) / _APP_NAME / "Cache"
        return Path(
            os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache"),
        ) / _APP_NAME
    return Path(".cache")


def user_brands_dir() -> Path:
    """Writable per-user dir for brand profile JSON files.

    Inside the .app the templates/ tree is read-only, so brand profiles can't
    live next to the templates. Use the platform user-data dir instead so
    profiles survive app updates and stay editable.
    """

    base = user_data_dir() if is_bundled() else Path("data")
    return base / "brands"


def user_config_path() -> Path:
    """Where the persisted Config lives (~/.prompt-genius/config.json in source,
    inside user_data_dir() when bundled)."""

    if is_bundled():
        return user_data_dir() / "config.json"
    return Path.home() / ".prompt-genius" / "config.json"
