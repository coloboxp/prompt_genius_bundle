"""Brief-parser backends."""

from __future__ import annotations

from prompt_genius.core.brief_parsers import (
    ClaudeCliBriefParser,
    CodexCliBriefParser,
    HeuristicBriefParser,
    make_parser,
    make_parser_from_config,
)
from prompt_genius.core.config import Config


def test_heuristic_default_when_unknown_backend_auto(monkeypatch) -> None:
    # Pretend neither CLI is on PATH.
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    parser = make_parser(backend="auto")
    assert isinstance(parser, HeuristicBriefParser)


def test_explicit_claude_returns_claude_cli_parser() -> None:
    parser = make_parser(backend="claude")
    assert isinstance(parser, ClaudeCliBriefParser)


def test_explicit_codex_returns_codex_cli_parser() -> None:
    parser = make_parser(backend="codex")
    assert isinstance(parser, CodexCliBriefParser)


def test_unknown_backend_raises() -> None:
    import pytest
    with pytest.raises(ValueError):
        make_parser(backend="totally-fake")


def test_cli_parser_falls_back_when_binary_missing(monkeypatch) -> None:
    # Force shutil.which to return None so _run() short-circuits.
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    parser = ClaudeCliBriefParser(fallback=HeuristicBriefParser())
    intent = parser.parse("Premium enterprise hero image")
    assert intent.raw_brief == "Premium enterprise hero image"
    # heuristic should extract "premium" mood
    assert "premium" in intent.mood


def test_make_parser_from_config_returns_matching_type() -> None:
    cfg = Config.default()
    cfg.llm.backend = "codex"
    parser = make_parser_from_config(cfg.llm)
    assert isinstance(parser, CodexCliBriefParser)
