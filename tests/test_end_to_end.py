"""End-to-end: generate_cards facade."""

from __future__ import annotations

import re
from pathlib import Path

from prompt_genius.core.generate import generate_cards


def test_generate_static_image_returns_n_diverse_cards(
    catalog_dir: Path, adapters_dir: Path
) -> None:
    cards = generate_cards(
        "Premium enterprise hero image for biometric onboarding, avoid cyberpunk",
        mode="static_image",
        target_model=None,
        n=5,
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        allow_drafts=True,
    )
    assert len(cards) == 5
    keys = {tuple(c.selected_patterns) for c in cards}
    assert len(keys) == 5, "cards should be diverse"


def test_generate_text_to_video_includes_video_fields(
    catalog_dir: Path, adapters_dir: Path
) -> None:
    cards = generate_cards(
        "6-second product launch teaser, calm pacing",
        mode="text_to_video",
        target_model=None,
        n=2,
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        allow_drafts=True,
    )
    assert len(cards) == 2
    for card in cards:
        params = card.structured.video_parameters or {}
        assert "duration_seconds" in params
        assert "camera_motion" in params
        assert "pacing" in params
        assert "continuity" in params


def test_generate_storyboard_returns_multiple_shots(
    catalog_dir: Path, adapters_dir: Path
) -> None:
    cards = generate_cards(
        "15-second identity verification storyboard",
        mode="storyboard",
        target_model="seedance_2_0",
        n=1,
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        allow_drafts=True,
    )
    assert len(cards) == 1
    card = cards[0]
    assert isinstance(card.structured, list)
    assert 3 <= len(card.structured) <= 5
    assert isinstance(card.compiled, list)
    timings = [c.text for c in card.compiled]
    assert any(re.search(r"（\d+-\d+秒）", t) for t in timings)


def test_generate_keyframe_returns_start_keyframe_end(
    catalog_dir: Path, adapters_dir: Path
) -> None:
    cards = generate_cards(
        "Animate a product visual with calm push-in motion",
        mode="keyframe",
        target_model=None,
        n=1,
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        allow_drafts=True,
    )
    assert len(cards) == 1
    structured = cards[0].structured
    assert isinstance(structured, list)
    roles = [s.frame_role for s in structured]
    assert roles[0] == "start" and roles[-1] == "end"
