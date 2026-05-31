"""Phase 4: campaign mode emits a coordinated set of cards."""

from __future__ import annotations

from pathlib import Path

from prompt_genius.core.generate import generate_campaign


def test_campaign_returns_multiple_roles(catalog_dir: Path, adapters_dir: Path) -> None:
    pack = generate_campaign(
        "Premium product launch",
        image_target=None,
        video_target=None,
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        allow_drafts=True,
    )
    assert "hero_static" in pack and pack["hero_static"]
    assert "storyboard" in pack and pack["storyboard"]
    assert any(role.startswith("hero") for role in pack)


def test_campaign_image_video_target_independent(catalog_dir: Path, adapters_dir: Path) -> None:
    pack = generate_campaign(
        "Product teaser",
        image_target="nano_banana_pro",
        video_target="seedance_2_0",
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        allow_drafts=True,
    )
    hero_static = pack.get("hero_static") or []
    storyboard = pack.get("storyboard") or []
    if hero_static:
        assert hero_static[0].target_model == "nano_banana_pro"
    if storyboard:
        assert storyboard[0].target_model == "seedance_2_0"
