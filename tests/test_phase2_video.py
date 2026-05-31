"""Phase 2: static→video convert + brand-aware generation + exporters."""

from __future__ import annotations

from pathlib import Path

from prompt_genius.core.adapters import load_adapters, resolve_adapter
from prompt_genius.core.catalog import load_catalog
from prompt_genius.core.convert import static_to_video
from prompt_genius.core.export import export_card, list_exporters
from prompt_genius.core.generate import card_to_card_dict, generate_cards


def test_static_to_video(catalog_dir: Path, adapters_dir: Path) -> None:
    cards = generate_cards(
        "Premium enterprise hero image",
        mode="static_image",
        target_model=None,
        n=1,
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        allow_drafts=True,
    )
    card_dict = card_to_card_dict(cards[0])
    adapter = resolve_adapter(load_adapters(adapters_dir), "seedance_2_0")
    catalog = load_catalog(catalog_dir)
    structured, compiled = static_to_video(
        card_dict, target_mode="image_to_video", adapter=adapter, catalog=catalog,
    )
    assert structured is not None
    assert compiled is not None


def test_brand_profile_biases_search(catalog_dir: Path, adapters_dir: Path, repo_root: Path) -> None:
    brand_path = repo_root / "templates" / "brand-profile-template.json"
    cards = generate_cards(
        "Hero visual for a product launch",
        mode="static_image",
        target_model=None,
        n=3,
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        allow_drafts=True,
        brand_profile=brand_path,
    )
    assert cards
    # brand profile avoid includes "cyberpunk" — no card should mention it
    for card in cards:
        text = ((card.compiled if not isinstance(card.compiled, list) else card.compiled[0]).text).lower()
        assert "premium" in text or "clean" in text or "enterprise" in text or "trustworthy" in text


def test_exporters_available_and_emit_text(catalog_dir: Path, adapters_dir: Path) -> None:
    cards = generate_cards(
        "Hero image",
        mode="static_image",
        target_model=None,
        n=1,
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        allow_drafts=True,
    )
    card_dict = card_to_card_dict(cards[0])
    assert {"plain", "markdown", "json"}.issubset(set(list_exporters()))
    for fmt in ("plain", "markdown", "json"):
        suffix, text = export_card(card_dict, fmt)
        assert suffix.startswith(".") and text
