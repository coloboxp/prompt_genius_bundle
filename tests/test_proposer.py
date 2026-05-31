"""LLM card proposer + corpus index."""

from __future__ import annotations

from pathlib import Path

from prompt_genius.core.adapters import load_adapters, resolve_adapter
from prompt_genius.core.brief import parse_brief
from prompt_genius.core.catalog import load_catalog, search
from prompt_genius.core.corpus import CorpusIndex
from prompt_genius.core.proposer import (
    HeuristicProposer,
    ProposedCard,
    make_proposer_from_config,
)
from prompt_genius.core.config import Config


def test_corpus_index_finds_anime_exemplar(repo_root: Path) -> None:
    index = CorpusIndex.from_dir(repo_root / "raw_corpus")
    assert len(index) > 1000
    hits = index.search("anime cinematic dreamy", k=5)
    assert hits
    top_title = hits[0][0].title.lower()
    assert "anime" in top_title or "cinematic" in top_title or "dreamy" in top_title


def test_heuristic_proposer_returns_n_proposals(catalog_dir: Path, adapters_dir: Path) -> None:
    catalog = load_catalog(catalog_dir)
    adapter = resolve_adapter(load_adapters(adapters_dir), None)
    intent = parse_brief("Premium enterprise hero image")
    matches = search(catalog, intent, "static_image", allow_drafts=True)
    proposer = HeuristicProposer()
    proposals = proposer.propose(
        intent=intent, adapter=adapter, catalog=catalog,
        matches=matches, exemplars=[], n=3, mode="static_image",
    )
    assert len(proposals) == 3
    for p in proposals:
        assert isinstance(p, ProposedCard)
        assert p.selected_pattern_ids


def test_make_proposer_from_config_defaults_heuristic_for_unknown_path(monkeypatch) -> None:
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    cfg = Config.default()
    cfg.llm.backend = "auto"
    proposer = make_proposer_from_config(cfg.llm)
    assert isinstance(proposer, HeuristicProposer)
