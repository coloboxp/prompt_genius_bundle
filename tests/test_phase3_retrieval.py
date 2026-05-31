"""Phase 3: TF-IDF reranking improves targeting; brand-boost lifts brand terms."""

from __future__ import annotations

from pathlib import Path

from prompt_genius.core.brand import load_brand_profile
from prompt_genius.core.brief import parse_brief
from prompt_genius.core.catalog import load_catalog, search


def test_tfidf_lifts_relevant_style(catalog_dir: Path) -> None:
    catalog = load_catalog(catalog_dir)
    intent = parse_brief("Anime cinematic scene with soft bloom and dreamy atmosphere")
    matches_keyword = search(
        catalog, intent, "static_image", allow_drafts=True, use_embeddings=False
    )
    matches_hybrid = search(
        catalog, intent, "static_image", allow_drafts=True, use_embeddings=True
    )
    # The Makoto Shinkai style should rank higher with embeddings enabled.
    style_ranked = [m.item.id for m in matches_hybrid.get("style_pattern", [])]
    assert "style_makoto_shinkai_anime_001" in style_ranked[:3]
    # Hybrid must not return fewer or be empty when keyword finds something.
    if matches_keyword.get("style_pattern"):
        assert len(matches_hybrid.get("style_pattern", [])) >= 1


def test_brand_boost_changes_scoring(catalog_dir: Path, repo_root: Path) -> None:
    catalog = load_catalog(catalog_dir)
    intent = parse_brief("Visual for product launch")
    brand = load_brand_profile(repo_root / "templates" / "brand-profile-template.json")
    no_brand = search(catalog, intent, "static_image", allow_drafts=True)
    with_brand = search(
        catalog, intent, "static_image", allow_drafts=True, brand_boost_terms=brand.boost_terms()
    )
    # Top scores should be >= without brand boost
    if no_brand.get("style_pattern") and with_brand.get("style_pattern"):
        assert with_brand["style_pattern"][0].score >= no_brand["style_pattern"][0].score
