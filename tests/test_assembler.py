"""Assembler — StructuredPrompt construction for each mode."""

from __future__ import annotations

from pathlib import Path

import pytest

from prompt_genius.core.adapters import load_adapters, resolve_adapter
from prompt_genius.core.assembler import assemble
from prompt_genius.core.brief import parse_brief
from prompt_genius.core.catalog import load_catalog, search
from prompt_genius.core.models import StructuredPrompt

_BRIEF_IMAGE = "Premium enterprise hero image for biometric onboarding, avoid cyberpunk"
_BRIEF_VIDEO = "6-second LinkedIn product teaser, calm premium pacing"
_BRIEF_STORY = "15-second identity verification storyboard"


@pytest.mark.parametrize(
    "mode,brief",
    [
        ("static_image", _BRIEF_IMAGE),
        ("image_editing", _BRIEF_IMAGE),
        ("text_to_video", _BRIEF_VIDEO),
        ("image_to_video", _BRIEF_VIDEO),
    ],
)
def test_single_modes_produce_one_prompt(
    catalog_dir: Path, adapters_dir: Path, mode: str, brief: str
) -> None:
    adapter = resolve_adapter(load_adapters(adapters_dir), None)
    catalog = load_catalog(catalog_dir)
    intent = parse_brief(brief)
    matches = search(catalog, intent, mode, allow_drafts=True)
    structured = assemble(intent, matches, adapter, mode)
    assert isinstance(structured, StructuredPrompt)
    assert structured.mode == mode
    assert structured.target_model == "generic"
    assert structured.selected_patterns, "should have selected at least one pattern"


def test_storyboard_returns_list(catalog_dir: Path, adapters_dir: Path) -> None:
    adapter = resolve_adapter(load_adapters(adapters_dir), None)
    catalog = load_catalog(catalog_dir)
    intent = parse_brief(_BRIEF_STORY)
    matches = search(catalog, intent, "storyboard", allow_drafts=True)
    structured = assemble(intent, matches, adapter, "storyboard", shot_count=4)
    assert isinstance(structured, list)
    assert len(structured) == 4
    assert all(s.mode == "storyboard" for s in structured)
    assert all(s.duration_seconds and s.duration_seconds > 0 for s in structured)
    assert [s.shot_number for s in structured] == [1, 2, 3, 4]


def test_keyframe_returns_list(catalog_dir: Path, adapters_dir: Path) -> None:
    adapter = resolve_adapter(load_adapters(adapters_dir), None)
    catalog = load_catalog(catalog_dir)
    intent = parse_brief(_BRIEF_VIDEO)
    matches = search(catalog, intent, "keyframe", allow_drafts=True)
    structured = assemble(intent, matches, adapter, "keyframe", keyframe_count=3)
    assert isinstance(structured, list)
    assert [s.frame_role for s in structured] == ["start", "keyframe", "end"]
