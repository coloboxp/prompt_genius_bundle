"""Lightweight stdlib TF-IDF embeddings for catalog reranking.

No external dependencies. Phase 3 acceptance only asks for "better targeted
results than simple keyword search"; a TF-IDF + cosine pass over the catalog
delivers that without sentence-transformers or a vector DB.

A future swap to sentence-transformers / a vector DB happens behind the same
:func:`score_items` signature.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from prompt_genius.core.models import CatalogItem

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _item_text(item: CatalogItem) -> str:
    parts = [
        item.name,
        item.description,
        " ".join(item.tags),
        " ".join(item.compatible_with),
        " ".join(item.prompt_fragments.values()),
    ]
    return " ".join(parts)


@dataclass(slots=True)
class TfidfIndex:
    """Precomputed TF-IDF index over a catalog."""

    doc_freq: Counter
    doc_count: int
    doc_vectors: dict[str, dict[str, float]]
    doc_norms: dict[str, float]

    @classmethod
    def from_items(cls, items: Iterable[CatalogItem]) -> "TfidfIndex":
        items_list = list(items)
        doc_freq: Counter = Counter()
        per_doc_tokens: dict[str, Counter] = {}
        for item in items_list:
            tokens = _tokenize(_item_text(item))
            counts = Counter(tokens)
            per_doc_tokens[item.id] = counts
            for token in counts:
                doc_freq[token] += 1

        doc_count = max(len(items_list), 1)
        doc_vectors: dict[str, dict[str, float]] = {}
        doc_norms: dict[str, float] = {}
        for item_id, counts in per_doc_tokens.items():
            vector = {
                token: (count / sum(counts.values()))
                * math.log((doc_count + 1) / (doc_freq[token] + 1))
                + 1e-9
                for token, count in counts.items()
            }
            doc_vectors[item_id] = vector
            doc_norms[item_id] = math.sqrt(sum(value * value for value in vector.values()))

        return cls(
            doc_freq=doc_freq,
            doc_count=doc_count,
            doc_vectors=doc_vectors,
            doc_norms=doc_norms,
        )

    def query_vector(self, text: str) -> dict[str, float]:
        tokens = _tokenize(text)
        if not tokens:
            return {}
        counts = Counter(tokens)
        total = sum(counts.values())
        return {
            token: (count / total)
            * math.log((self.doc_count + 1) / (self.doc_freq.get(token, 0) + 1))
            + 1e-9
            for token, count in counts.items()
        }

    def cosine(self, query: dict[str, float], item_id: str) -> float:
        if not query or item_id not in self.doc_vectors:
            return 0.0
        doc = self.doc_vectors[item_id]
        common = set(query) & set(doc)
        if not common:
            return 0.0
        dot = sum(query[token] * doc[token] for token in common)
        q_norm = math.sqrt(sum(v * v for v in query.values()))
        d_norm = self.doc_norms.get(item_id, 1e-9)
        return dot / (q_norm * d_norm + 1e-9)


def score_items(
    index: TfidfIndex, query_text: str, items: Iterable[CatalogItem]
) -> dict[str, float]:
    """Return ``{item_id: cosine_score}`` for the given items."""

    query = index.query_vector(query_text)
    return {item.id: index.cosine(query, item.id) for item in items}
