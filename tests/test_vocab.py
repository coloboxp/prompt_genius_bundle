"""Corpus vocabulary extractor."""

from __future__ import annotations

from pathlib import Path

from prompt_genius.core.vocab import (
    CorpusVocab,
    extract_vocab,
    load_or_build_vocab,
    merge_vocab_lists,
)


def test_extract_vocab_runs_over_real_corpus(repo_root: Path) -> None:
    vocab = load_or_build_vocab(repo_root / "raw_corpus")
    # The corpus is sizeable; assert we mined more than the hardcoded 6 per category.
    assert vocab.sample_size > 5_000
    for category in ("lens", "lighting", "camera_motion", "style", "mood"):
        assert len(vocab.by_category.get(category, [])) >= 5, f"{category} too thin"


def test_top_returns_frequency_sorted(repo_root: Path) -> None:
    vocab = load_or_build_vocab(repo_root / "raw_corpus")
    top_lenses = vocab.top("lens", n=3)
    assert len(top_lenses) == 3
    # 85mm is the dominant lens in the NBP corpus by a wide margin.
    assert top_lenses[0] in {"85mm", "35mm"}, top_lenses


def test_merge_keeps_catalog_first_then_corpus(repo_root: Path) -> None:
    vocab = load_or_build_vocab(repo_root / "raw_corpus")
    catalog_vocab = {"lens": ["85mm", "50mm", "macro"]}
    merged = merge_vocab_lists(catalog_vocab, vocab, per_category_cap=15)
    # Catalog entries kept and stay first
    assert merged["lens"][:3] == ["85mm", "50mm", "macro"]
    # Corpus additions appear after — must include at least one entry not in catalog
    assert any(v.lower() not in {"85mm", "50mm", "macro"} for v in merged["lens"])
    assert len(merged["lens"]) <= 15


def test_build_full_vocab_terminates(repo_root: Path) -> None:
    """Regression: an earlier rename caused build_full_vocab to recurse forever."""

    import pytest
    pytest.importorskip("PySide6")
    from prompt_genius.core.catalog import load_catalog
    from prompt_genius.gui.json_editor import build_full_vocab

    catalog = load_catalog(repo_root / "catalog")
    merged = build_full_vocab(catalog, corpus_dir=str(repo_root / "raw_corpus"))
    assert "lens" in merged
    assert len(merged["lens"]) >= 6


def test_round_trip_serializes(tmp_path: Path) -> None:
    sample = CorpusVocab(
        by_category={"lens": [("85mm", 100), ("35mm", 80)]},
        sample_size=180,
    )
    data = sample.to_dict()
    reloaded = CorpusVocab.from_dict(data)
    assert reloaded.sample_size == 180
    assert reloaded.top("lens", n=1) == ["85mm"]
