"""CLI install detection + backend metadata."""

from __future__ import annotations

import pytest

from prompt_genius.core.cli_check import (
    backend_meta,
    is_backend_installed,
    known_backends,
)


def test_heuristic_always_available() -> None:
    assert is_backend_installed("heuristic") is True
    assert is_backend_installed("auto") is True


def test_unknown_backend_returns_false() -> None:
    assert is_backend_installed("totally-fake-backend") is False


def test_claude_detection_matches_path(monkeypatch) -> None:
    from prompt_genius.runtime import cli_resolver

    monkeypatch.setattr(
        cli_resolver,
        "resolve_cli_binary",
        lambda name: "/fake/claude" if name == "claude" else None,
    )
    assert is_backend_installed("claude") is True
    assert is_backend_installed("codex") is False


def test_detection_uses_configured_binary(monkeypatch) -> None:
    from prompt_genius.runtime import cli_resolver

    monkeypatch.setattr(
        cli_resolver,
        "resolve_cli_binary",
        lambda name: "/custom/bin/codex" if name == "/custom/bin/codex" else None,
    )
    assert is_backend_installed("codex", codex_binary="/custom/bin/codex") is True


def test_backend_meta_has_install_info() -> None:
    for backend in ("claude", "codex", "mlx"):
        meta = backend_meta(backend)
        assert meta["display_name"]
        assert meta["install_command"]
        assert meta["install_url"].startswith("http")
        assert meta["homepage"].startswith("http")


def test_known_backends_listed() -> None:
    assert {"claude", "codex", "mlx"}.issubset(set(known_backends()))


def test_meta_for_unknown_is_empty() -> None:
    assert backend_meta("totally-fake") == {}
