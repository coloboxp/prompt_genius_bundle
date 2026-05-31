"""In-process catalog cache + dense default + invalidation on ingest."""

from __future__ import annotations

import csv
from pathlib import Path

from prompt_genius.core.config import Config, EmbeddingsConfig
from prompt_genius.core.generate import (
    _CATALOG_CACHE,
    get_or_load_catalog,
    invalidate_catalog_cache,
)


def test_dense_is_default() -> None:
    cfg = EmbeddingsConfig()
    assert cfg.backend == "dense"
    assert cfg.prefer_dense is True
    assert cfg.prewarm_on_launch is True


def test_cache_returns_same_instance(catalog_dir: Path) -> None:
    invalidate_catalog_cache()
    first = get_or_load_catalog(catalog_dir, backend="tfidf")
    second = get_or_load_catalog(catalog_dir, backend="tfidf")
    assert first is second


def test_different_backend_keeps_separate_entry(catalog_dir: Path) -> None:
    invalidate_catalog_cache()
    tfidf = get_or_load_catalog(catalog_dir, backend="tfidf")
    bm25 = get_or_load_catalog(catalog_dir, backend="bm25")
    assert tfidf is not bm25
    assert len(_CATALOG_CACHE) >= 2


def test_invalidate_drops_everything(catalog_dir: Path) -> None:
    invalidate_catalog_cache()
    get_or_load_catalog(catalog_dir, backend="tfidf")
    assert _CATALOG_CACHE, "cache should have one entry"
    invalidate_catalog_cache()
    assert not _CATALOG_CACHE


def test_ingest_invalidates_in_process_cache(tmp_path: Path, catalog_dir: Path) -> None:
    from prompt_genius.core.ingest import apply_plan, plan_ingest

    corpus = tmp_path / "raw"; corpus.mkdir()
    with (corpus / "seed.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "title", "description", "content", "sourceLink",
            "sourcePublishedAt", "author", "sourceMedia",
        ])
        writer.writeheader()
        writer.writerow({"id": "1", "title": "t", "description": "",
                         "content": "existing prompt one", "sourceLink": "",
                         "sourcePublishedAt": "", "author": "", "sourceMedia": ""})

    new_csv = tmp_path / "new.csv"
    with new_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "title", "description", "content", "sourceLink",
            "sourcePublishedAt", "author", "sourceMedia",
        ])
        writer.writeheader()
        writer.writerow({"id": "2", "title": "t2", "description": "",
                         "content": "totally new prompt", "sourceLink": "",
                         "sourcePublishedAt": "", "author": "", "sourceMedia": ""})

    invalidate_catalog_cache()
    get_or_load_catalog(catalog_dir, backend="tfidf")
    assert _CATALOG_CACHE
    plan = plan_ingest(new_csv, corpus)
    apply_plan(plan, corpus)
    assert not _CATALOG_CACHE, "ingest should invalidate the in-process cache"
