"""Resolve external LLM CLI binaries in shell and macOS GUI launches.

Finder-launched macOS apps do not inherit the user's interactive shell PATH.
That makes plain ``shutil.which("claude")`` unreliable even when the CLI is
installed and works from Terminal.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path


_COMMON_BIN_DIRS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
    str(Path.home() / ".local" / "bin"),
)


def resolve_cli_binary(binary: str) -> str | None:
    """Return an executable path for ``binary`` or ``None`` when not found.

    ``binary`` may be a command name or an absolute/relative path from settings.
    The search checks the current PATH, common macOS package-manager locations,
    npm's global bin, and finally a login shell's PATH.
    """

    binary = (binary or "").strip()
    if not binary:
        return None

    candidate = Path(binary).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        return str(candidate) if _is_executable(candidate) else None

    found = shutil.which(binary)
    if found:
        return found

    extra_path = os.pathsep.join(_candidate_dirs())
    found = shutil.which(binary, path=extra_path)
    if found:
        return found
    return None


def cli_exists(binary: str) -> bool:
    """Return True when ``binary`` resolves to an executable."""

    return resolve_cli_binary(binary) is not None


def cli_env() -> dict[str, str]:
    """Environment for subprocesses that need GUI-safe CLI lookup."""

    env = os.environ.copy()
    path_parts = [env.get("PATH", ""), *_candidate_dirs()]
    env["PATH"] = os.pathsep.join(part for part in path_parts if part)
    return env


def _is_executable(path: Path) -> bool:
    try:
        return path.is_file() and os.access(path, os.X_OK)
    except OSError:
        return False


def _candidate_dirs() -> tuple[str, ...]:
    dirs: list[str] = []
    dirs.extend(_COMMON_BIN_DIRS)
    npm_bin = _npm_global_bin()
    if npm_bin:
        dirs.append(npm_bin)
    dirs.extend(_login_shell_path())
    return tuple(dict.fromkeys(dirs))


@lru_cache(maxsize=1)
def _npm_global_bin() -> str:
    npm = shutil.which("npm", path=os.pathsep.join(_COMMON_BIN_DIRS)) or shutil.which("npm")
    if not npm:
        return ""
    try:
        result = subprocess.run(
            [npm, "bin", "-g"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
            env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


@lru_cache(maxsize=1)
def _login_shell_path() -> tuple[str, ...]:
    shell = os.environ.get("SHELL") or "/bin/zsh"
    try:
        result = subprocess.run(
            [shell, "-lc", "printf %s \"$PATH\""],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
            env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()
    if result.returncode != 0:
        return ()
    return tuple(part for part in result.stdout.split(os.pathsep) if part)
