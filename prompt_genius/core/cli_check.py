"""Detect whether an LLM CLI backend is installed + provide install URLs.

Used by the GUI Settings dialog and the generation worker to guide the user
to install whatever they pick (instead of silently falling back to heuristic).
"""

from __future__ import annotations

import shutil


# Human-readable display name + install URL per backend id.
_BACKENDS: dict[str, dict[str, str]] = {
    "claude": {
        "display_name": "Claude CLI",
        "install_command": "npm install -g @anthropic-ai/claude-code",
        "install_url": "https://docs.claude.com/en/docs/claude-code/setup",
        "homepage": "https://claude.com/claude-code",
    },
    "codex": {
        "display_name": "OpenAI Codex CLI",
        "install_command": "npm install -g @openai/codex",
        "install_url": "https://github.com/openai/codex#installation",
        "homepage": "https://github.com/openai/codex",
    },
    "mlx": {
        "display_name": "MLX-LM (Apple Silicon on-device)",
        "install_command": "pip install -e \".[mlx]\"",
        "install_url": "https://github.com/ml-explore/mlx-lm",
        "homepage": "https://github.com/ml-explore/mlx-lm",
    },
}


def is_backend_installed(backend: str) -> bool:
    """Return True when the chosen LLM backend can actually run on this machine."""

    if backend in ("heuristic", "auto"):
        return True
    if backend == "claude":
        return shutil.which("claude") is not None
    if backend == "codex":
        return shutil.which("codex") is not None
    if backend == "mlx":
        try:
            import mlx_lm  # noqa: F401
        except ImportError:
            return False
        return True
    return False


def backend_meta(backend: str) -> dict[str, str]:
    """Return display info for the backend. Empty dict for unknown ids."""

    return dict(_BACKENDS.get(backend, {}))


def known_backends() -> list[str]:
    return list(_BACKENDS)
