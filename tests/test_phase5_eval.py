"""Phase 5: versioning, diffing, brand fit, quality recompute."""

from __future__ import annotations

import json
from pathlib import Path

from prompt_genius.core.brand import brand_fit_score, load_brand_profile
from prompt_genius.core.generate import card_to_card_dict, generate_cards
from prompt_genius.core.quality import recompute_quality_scores
from prompt_genius.core.versioning import diff_cards, save_version


def _make_card(catalog_dir: Path, adapters_dir: Path, brief: str) -> dict:
    cards = generate_cards(
        brief,
        mode="static_image",
        target_model=None,
        n=1,
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        allow_drafts=True,
    )
    return card_to_card_dict(cards[0])


def test_save_version_writes_jsonl(catalog_dir: Path, adapters_dir: Path, tmp_path: Path) -> None:
    card = _make_card(catalog_dir, adapters_dir, "Hero")
    path = save_version(card, tmp_path / "v.jsonl", change_summary="initial")
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines and lines[0]["card"]["id"] == card["id"]


def test_diff_detects_change(catalog_dir: Path, adapters_dir: Path) -> None:
    a = _make_card(catalog_dir, adapters_dir, "Premium enterprise hero image")
    b = _make_card(catalog_dir, adapters_dir, "Bold playful campaign visual")
    out = diff_cards(a, b, field="prompt")
    assert out, "expected a non-empty diff between two different briefs"


def test_brand_fit_score_in_range(catalog_dir: Path, adapters_dir: Path, repo_root: Path) -> None:
    card = _make_card(catalog_dir, adapters_dir, "Premium enterprise hero image")
    brand = load_brand_profile(repo_root / "templates" / "brand-profile-template.json")
    score = brand_fit_score(card, brand)
    assert 0.0 <= score <= 1.0


def test_quality_dry_run_returns_scores(tmp_path: Path, catalog_dir: Path) -> None:
    feedback = tmp_path / "feedback.jsonl"
    feedback.write_text("")  # empty
    history = tmp_path / "history"
    history.mkdir()
    scores = recompute_quality_scores(catalog_dir, feedback, history, apply=False)
    assert scores, "expected at least one pattern score"
    assert all(0.0 <= s <= 1.0 for s in scores.values())
