"""BM25 backend + Hybrid (BM25 + dense) RRF fusion."""

from __future__ import annotations

from pathlib import Path

import pytest

from prompt_genius.core.catalog import load_catalog
from prompt_genius.core.retrieval import (
    Bm25Backend,
    HybridBackend,
    SentenceTransformerBackend,
    TfidfBackend,
)


def test_bm25_backend_finds_lexical_match(catalog_dir: Path) -> None:
    catalog = load_catalog(catalog_dir, backend="bm25")
    assert isinstance(catalog.retriever.backend, Bm25Backend)

    items = list(catalog.items.values())
    scores = catalog.retriever.score("anime cinematic dreamy", items)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top = [pid for pid, score in ranked if score > 0][:5]
    assert "style_makoto_shinkai_anime_001" in top


def test_bm25_scores_are_normalized_to_unit(catalog_dir: Path) -> None:
    catalog = load_catalog(catalog_dir, backend="bm25")
    items = list(catalog.items.values())
    scores = catalog.retriever.score("hero image enterprise", items)
    if any(value > 0 for value in scores.values()):
        assert max(scores.values()) <= 1.0001


def test_bm25_load_via_search_keeps_quality(catalog_dir: Path) -> None:
    catalog = load_catalog(catalog_dir, backend="bm25")
    from prompt_genius.core.brief import parse_brief
    from prompt_genius.core.catalog import search

    intent = parse_brief("Premium enterprise hero image for biometric onboarding")
    matches = search(catalog, intent, "static_image", allow_drafts=True)
    style_ranked = [m.item.id for m in matches.get("style_pattern", [])]
    assert "style_premium_enterprise_001" in style_ranked[:3]


def test_hybrid_backend_combines_signals(catalog_dir: Path) -> None:
    pytest.importorskip("sentence_transformers")
    catalog = load_catalog(catalog_dir, backend="hybrid")
    assert isinstance(catalog.retriever.backend, HybridBackend)
    items = list(catalog.items.values())
    scores = catalog.retriever.score("calm enterprise hero", items)
    assert scores
    assert max(scores.values()) <= 1.0001


def test_dense_backend_loads_and_scores(catalog_dir: Path) -> None:
    pytest.importorskip("sentence_transformers")
    catalog = load_catalog(catalog_dir, backend="dense")
    assert isinstance(catalog.retriever.backend, SentenceTransformerBackend)
    items = list(catalog.items.values())
    scores = catalog.retriever.score("anime cinematic dreamy", items)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    assert ranked[0][0] == "style_makoto_shinkai_anime_001"


def test_tfidf_remains_default(catalog_dir: Path) -> None:
    catalog = load_catalog(catalog_dir)  # backend defaults to tfidf
    assert isinstance(catalog.retriever.backend, TfidfBackend)
