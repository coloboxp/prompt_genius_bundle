"""Catalog loading and search.

A :class:`Catalog` is an in-memory snapshot of normalized catalog items loaded
from a directory of JSON files. Search uses simple tag/keyword scoring; this is
the documented Phase 1 retrieval strategy. Phase 3 swaps in embeddings without
changing the public interface.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from prompt_genius.core.config import Config, RetrievalWeights
from prompt_genius.core.embeddings import TfidfIndex
from prompt_genius.core.models import CatalogItem, Intent, Match
from prompt_genius.core.retrieval import Retriever

_ACTIVE_DEFAULT_STATUSES: frozenset[str] = frozenset({"active"})


@dataclass(slots=True)
class Catalog:
    """An in-memory catalog of normalized items, indexed by id and type."""

    items: dict[str, CatalogItem] = field(default_factory=dict)
    by_type: dict[str, list[CatalogItem]] = field(default_factory=lambda: defaultdict(list))
    tfidf: TfidfIndex | None = None
    retriever: Retriever | None = None

    def all(self) -> list[CatalogItem]:
        return list(self.items.values())

    def of_type(self, type_name: str) -> list[CatalogItem]:
        return list(self.by_type.get(type_name, []))

    def build_index(
        self,
        *,
        backend: str = "tfidf",
        prefer_dense: bool = False,
        model_name: str | None = None,
        cache_dir: str | Path = ".cache/embeddings",
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
        rrf_k: int = 60,
    ) -> None:
        self.tfidf = TfidfIndex.from_items(self.items.values())
        self.retriever = Retriever.from_items(
            self.items.values(),
            backend=backend,
            prefer_dense=prefer_dense,
            model_name=model_name,
            cache_dir=cache_dir,
            bm25_k1=bm25_k1,
            bm25_b=bm25_b,
            rrf_k=rrf_k,
        )


def load_catalog(
    catalog_dir: str | Path,
    *,
    backend: str = "tfidf",
    prefer_dense: bool = False,
    model_name: str | None = None,
    cache_dir: str | Path = ".cache/embeddings",
    bm25_k1: float = 1.5,
    bm25_b: float = 0.75,
    rrf_k: int = 60,
) -> Catalog:
    """Load every ``*.json`` under ``catalog_dir`` into a :class:`Catalog`.

    Silently skips files that are not valid catalog item JSON. Use
    :mod:`prompt_genius.core.validator` for strict validation.
    """

    root = Path(catalog_dir)
    catalog = Catalog()
    if not root.exists():
        return catalog

    for path in sorted(root.rglob("*.json")):
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or "id" not in data or "type" not in data:
            continue
        try:
            item = CatalogItem.from_dict(data)
        except (KeyError, TypeError, ValueError):
            continue
        catalog.items[item.id] = item
        catalog.by_type[item.type].append(item)
    catalog.build_index(
        backend=backend,
        prefer_dense=prefer_dense,
        model_name=model_name,
        cache_dir=cache_dir,
        bm25_k1=bm25_k1,
        bm25_b=bm25_b,
        rrf_k=rrf_k,
    )
    return catalog


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _intent_tokens(intent: Intent) -> set[str]:
    tokens: set[str] = set()
    tokens.update(_tokens(intent.raw_brief))
    for value in (intent.subject, intent.audience):
        if value:
            tokens.update(_tokens(value))
    for collection in (intent.mood, intent.style_hints, intent.format_hints):
        for value in collection:
            tokens.update(_tokens(value))
    return tokens


def _intent_avoid_tokens(intent: Intent) -> set[str]:
    tokens: set[str] = set()
    for value in intent.avoid:
        tokens.update(_tokens(value))
    return tokens


def _score_item(
    item: CatalogItem,
    intent_tokens: set[str],
    avoid_tokens: set[str],
    weights: RetrievalWeights,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0

    tag_hits = intent_tokens.intersection(_tokens(" ".join(item.tags)))
    if tag_hits:
        score += weights.tag_weight * len(tag_hits)
        reasons.append(f"tag match: {sorted(tag_hits)}")

    text_hits = intent_tokens.intersection(_tokens(f"{item.name} {item.description}"))
    if text_hits:
        score += weights.text_weight * len(text_hits)
        reasons.append(f"text match: {sorted(text_hits)}")

    compat_hits = intent_tokens.intersection(_tokens(" ".join(item.compatible_with)))
    if compat_hits:
        score += weights.compatible_with_weight * len(compat_hits)
        reasons.append(f"compatible_with: {sorted(compat_hits)}")

    avoid_with_hits = intent_tokens.intersection(_tokens(" ".join(item.avoid_with)))
    if avoid_with_hits:
        score -= weights.avoid_with_penalty * len(avoid_with_hits)
        reasons.append(f"avoid_with conflict: {sorted(avoid_with_hits)}")

    if avoid_tokens:
        intent_avoid_match = avoid_tokens.intersection(
            _tokens(" ".join(item.tags) + " " + item.name + " " + item.description)
        )
        if intent_avoid_match:
            score -= weights.intent_avoid_penalty * len(intent_avoid_match)
            reasons.append(f"intent avoid hit: {sorted(intent_avoid_match)}")

    score += item.quality_score
    return score, reasons


def _passes_status_filter(item: CatalogItem, allow_drafts: bool) -> bool:
    if item.status in {"deprecated", "archived"}:
        return False
    if item.status == "draft" and not allow_drafts:
        return False
    if item.status not in _ACTIVE_DEFAULT_STATUSES and not allow_drafts:
        return False
    return True


def search(
    catalog: Catalog,
    intent: Intent,
    mode: str,
    *,
    types: Iterable[str] | None = None,
    per_type_limit: int = 5,
    allow_drafts: bool = False,
    brand_boost_terms: Iterable[str] | None = None,
    use_embeddings: bool = True,
    config: Config | None = None,
) -> dict[str, list[Match]]:
    """Search the catalog for items that fit the intent and mode.

    Hybrid scoring: keyword/tag signals + TF-IDF cosine over a query built from
    the brief. ``brand_boost_terms`` add an extra additive boost so brand-aligned
    patterns rank higher.
    """

    cfg = config or Config.default()
    weights = cfg.retrieval
    intent_tokens = _intent_tokens(intent)
    avoid_tokens = _intent_avoid_tokens(intent)
    brand_tokens: set[str] = set()
    if brand_boost_terms:
        for term in brand_boost_terms:
            brand_tokens.update(_tokens(term))

    query_text = " ".join(
        [
            intent.raw_brief or "",
            intent.subject or "",
            intent.audience or "",
            " ".join(intent.mood),
            " ".join(intent.style_hints),
        ]
    ).strip()

    use_embed = use_embeddings and (catalog.retriever is not None or catalog.tfidf is not None) and bool(query_text)
    cosine_scores: dict[str, float] = {}
    if use_embed:
        if catalog.retriever is not None:
            cosine_scores = catalog.retriever.score(query_text, catalog.all())
        elif catalog.tfidf is not None:
            qv = catalog.tfidf.query_vector(query_text)
            cosine_scores = {it.id: catalog.tfidf.cosine(qv, it.id) for it in catalog.all()}

    by_type: dict[str, list[Match]] = defaultdict(list)
    candidates = (
        [item for type_name in types for item in catalog.of_type(type_name)]
        if types
        else catalog.all()
    )

    for item in candidates:
        if mode not in item.applies_to:
            continue
        if not _passes_status_filter(item, allow_drafts):
            continue
        score, reasons = _score_item(item, intent_tokens, avoid_tokens, weights)

        if use_embed:
            cosine = cosine_scores.get(item.id, 0.0)
            if cosine > 0:
                score += weights.cosine_weight * cosine
                reasons.append(f"embed cosine: {cosine:.2f}")

        if brand_tokens:
            item_tokens = _tokens(
                " ".join(item.tags) + " " + item.name + " " + item.description
            )
            brand_hits = brand_tokens.intersection(item_tokens)
            if brand_hits:
                score += weights.brand_boost_weight * len(brand_hits)
                reasons.append(f"brand boost: {sorted(brand_hits)}")

        if score <= 0 and not reasons:
            continue
        by_type[item.type].append(Match(item=item, score=score, reasons=reasons))

    # MMR diversity rerank per type, when the retriever can supply vectors.
    for type_name in list(by_type.keys()):
        bucket = by_type[type_name]
        bucket.sort(key=lambda m: (-m.score, m.item.id))
        if use_embed and catalog.retriever is not None and len(bucket) > per_type_limit:
            mmr_pairs = catalog.retriever.mmr(
                query_text,
                [(m.item, m.score) for m in bucket],
                k=per_type_limit,
            )
            picked_ids = {item.id for item, _ in mmr_pairs}
            bucket = [m for m in bucket if m.item.id in picked_ids]
        by_type[type_name] = bucket[:per_type_limit]
    return dict(by_type)
