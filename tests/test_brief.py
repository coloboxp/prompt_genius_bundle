"""Heuristic brief parser."""

from __future__ import annotations

from prompt_genius.core.brief import parse_brief


def test_extracts_subject_after_verb() -> None:
    intent = parse_brief("Create a premium enterprise hero image for biometric onboarding")
    assert intent.subject is not None
    assert "premium" in intent.mood
    assert "enterprise" in intent.audience or "" if intent.audience else True


def test_extracts_avoid_clauses() -> None:
    intent = parse_brief("LinkedIn product teaser, avoid cyberpunk, no fake text")
    avoids = " ".join(intent.avoid)
    assert "cyberpunk" in avoids
    assert "fake text" in avoids


def test_extracts_format_hint() -> None:
    intent = parse_brief("Hero image 16:9 for landing page")
    assert "16:9" in intent.format_hints


def test_extracts_style_hints() -> None:
    intent = parse_brief("Cinematic editorial portrait, soft natural mood")
    assert "cinematic" in intent.style_hints or "editorial" in intent.style_hints


def test_empty_brief_returns_empty_intent() -> None:
    intent = parse_brief("")
    assert intent.raw_brief == ""
    assert intent.subject is None
    assert intent.avoid == []
