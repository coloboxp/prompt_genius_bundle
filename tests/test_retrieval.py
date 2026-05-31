"""Retriever + MMR diversity behavior."""

from __future__ import annotations

from pathlib import Path

from prompt_genius.core.catalog import load_catalog


def test_default_load_uses_tfidf_backend(catalog_dir: Path) -> None:
    catalog = load_catalog(catalog_dir)
    assert catalog.retriever is not None
    # TF-IDF backend supplies vectors for every item.
    a_pattern = next(iter(catalog.items))
    vec = catalog.retriever.backend.vector(a_pattern)
    assert vec is not None and len(vec) > 0


def test_mmr_returns_diverse_subset(catalog_dir: Path) -> None:
    catalog = load_catalog(catalog_dir)
    items = list(catalog.items.values())
    scored = [(item, float(item.quality_score)) for item in items]
    picks = catalog.retriever.mmr("premium hero", scored, k=5, diversity=0.5)
    assert len(picks) == 5
    ids = [item.id for item, _ in picks]
    assert len(set(ids)) == 5
