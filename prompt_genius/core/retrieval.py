"""Pluggable retrieval backends + diversity reranker.

Available backends:

* :class:`TfidfBackend` — pure stdlib TF-IDF (default fallback).
* :class:`Bm25Backend`  — stdlib Okapi BM25 (sparse, lexical, no deps).
* :class:`SentenceTransformerBackend` — dense embeddings via
  ``sentence-transformers`` (``[embeddings]`` extra). Cached to disk so the
  model only loads once per session.
* :class:`HybridBackend` — BM25 + dense fused with Reciprocal Rank Fusion.

:class:`Retriever` exposes a uniform ``score`` + ``mmr`` API used by
``core/catalog.py`` regardless of which backend is selected.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol

from prompt_genius.core.embeddings import TfidfIndex, _item_text
from prompt_genius.core.models import CatalogItem


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


class _Backend(Protocol):
    def score(self, query: str, items: Iterable[CatalogItem]) -> dict[str, float]: ...
    def vector(self, item_id: str) -> list[float] | None: ...
    def query_vector(self, query: str) -> list[float]: ...


@dataclass(slots=True)
class TfidfBackend:
    index: TfidfIndex

    @classmethod
    def from_items(cls, items: Iterable[CatalogItem]) -> "TfidfBackend":
        return cls(index=TfidfIndex.from_items(items))

    def score(self, query: str, items: Iterable[CatalogItem]) -> dict[str, float]:
        qv = self.index.query_vector(query)
        return {item.id: self.index.cosine(qv, item.id) for item in items}

    def vector(self, item_id: str) -> list[float] | None:
        vec = self.index.doc_vectors.get(item_id)
        if vec is None:
            return None
        # Pack into a fixed key order so MMR similarity is comparable across items.
        return [vec.get(key, 0.0) for key in sorted(vec)]

    def query_vector(self, query: str) -> list[float]:
        qv = self.index.query_vector(query)
        return [qv[key] for key in sorted(qv)]


@dataclass(slots=True)
class Bm25Backend:
    """Okapi BM25 over the same per-item text TF-IDF uses.

    Pure stdlib, no extra dep. Returns a dense ``{item_id: score}`` mapping;
    scores are normalized to ``[0, 1]`` by the max BM25 score for each query so
    they can be fused with cosine scores.
    """

    item_ids: list[str]
    item_tokens: dict[str, list[str]]
    doc_freq: Counter[str]
    avg_doc_len: float
    doc_lengths: dict[str, int]
    _vocab_cache: list[str] | None = None
    _idf_cache: dict[str, float] | None = None
    _term_freqs: dict[str, Counter[str]] | None = None
    _postings: dict[str, list[str]] | None = None        # term → list of item_ids containing it
    k1: float = 1.5
    b: float = 0.75

    @classmethod
    def from_items(
        cls,
        items: Iterable[CatalogItem],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> "Bm25Backend":
        items_list = list(items)
        item_ids: list[str] = []
        item_tokens: dict[str, list[str]] = {}
        doc_freq: Counter[str] = Counter()
        doc_lengths: dict[str, int] = {}

        for item in items_list:
            tokens = _tokenize(_item_text(item))
            item_ids.append(item.id)
            item_tokens[item.id] = tokens
            doc_lengths[item.id] = len(tokens)
            for term in set(tokens):
                doc_freq[term] += 1

        total_length = sum(doc_lengths.values())
        avg_doc_len = (total_length / len(items_list)) if items_list else 0.0
        return cls(
            item_ids=item_ids,
            item_tokens=item_tokens,
            doc_freq=doc_freq,
            avg_doc_len=avg_doc_len,
            doc_lengths=doc_lengths,
            k1=k1,
            b=b,
        )

    def _ensure_indexes(self) -> None:
        if self._idf_cache is None:
            n = len(self.item_ids)
            self._idf_cache = {
                term: math.log(1 + (n - df + 0.5) / (df + 0.5))
                for term, df in self.doc_freq.items()
            }
        if self._term_freqs is None:
            self._term_freqs = {
                item_id: Counter(tokens)
                for item_id, tokens in self.item_tokens.items()
            }
        if self._postings is None:
            postings: dict[str, list[str]] = {}
            for item_id, tokens in self.item_tokens.items():
                for term in set(tokens):
                    postings.setdefault(term, []).append(item_id)
            self._postings = postings

    def _idf(self, term: str) -> float:
        self._ensure_indexes()
        return self._idf_cache.get(term, 0.0)

    def _raw_score(self, query_tokens: list[str], item_id: str) -> float:
        if not query_tokens:
            return 0.0
        self._ensure_indexes()
        term_freqs = self._term_freqs.get(item_id)
        if term_freqs is None:
            return 0.0
        doc_len = self.doc_lengths.get(item_id, 0)
        if doc_len == 0 or self.avg_doc_len == 0:
            return 0.0
        k1 = self.k1
        b = self.b
        length_norm = (1 - b + b * doc_len / self.avg_doc_len)
        score = 0.0
        idfs = self._idf_cache
        for term in query_tokens:
            tf = term_freqs.get(term, 0)
            if tf == 0:
                continue
            idf = idfs.get(term, 0.0)
            denom = tf + k1 * length_norm
            score += idf * (tf * (k1 + 1)) / denom
        return score

    def candidate_ids(self, query_tokens: list[str]) -> set[str]:
        """Return only docs that contain at least one query token."""

        self._ensure_indexes()
        out: set[str] = set()
        for term in query_tokens:
            posting = self._postings.get(term)
            if posting:
                out.update(posting)
        return out

    def score(self, query: str, items: Iterable[CatalogItem]) -> dict[str, float]:
        query_tokens = _tokenize(query)
        raw: dict[str, float] = {}
        target_ids = {item.id for item in items}
        for item_id in self.item_ids:
            if item_id not in target_ids:
                continue
            raw[item_id] = self._raw_score(query_tokens, item_id)
        if not raw:
            return raw
        peak = max(raw.values())
        if peak <= 0:
            return raw
        return {item_id: value / peak for item_id, value in raw.items()}

    def _ensure_vocab(self) -> list[str]:
        if self._vocab_cache is None:
            self._vocab_cache = sorted(self.doc_freq)
        return self._vocab_cache

    def vector(self, item_id: str) -> list[float] | None:
        tokens = self.item_tokens.get(item_id)
        if not tokens:
            return None
        counts = Counter(tokens)
        vocab = self._ensure_vocab()
        return [counts.get(term, 0.0) for term in vocab]

    def query_vector(self, query: str) -> list[float]:
        counts = Counter(_tokenize(query))
        vocab = self._ensure_vocab()
        return [counts.get(term, 0.0) for term in vocab]


@dataclass(slots=True)
class HybridBackend:
    """BM25 + dense embeddings fused with Reciprocal Rank Fusion.

    RRF score per item: ``sum(1 / (rrf_k + rank))`` across both rankings. The
    fused score is normalized to ``[0, 1]`` for downstream cosine-weight reuse.
    """

    sparse: Bm25Backend
    dense: "SentenceTransformerBackend"
    rrf_k: int = 60

    @classmethod
    def from_items(
        cls,
        items: Iterable[CatalogItem],
        *,
        model_name: str = "all-MiniLM-L6-v2",
        cache_dir: str | Path = ".cache/embeddings",
        rrf_k: int = 60,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> "HybridBackend":
        items_list = list(items)
        sparse = Bm25Backend.from_items(items_list, k1=k1, b=b)
        dense = SentenceTransformerBackend.from_items(
            items_list, model_name=model_name, cache_dir=cache_dir,
        )
        return cls(sparse=sparse, dense=dense, rrf_k=rrf_k)

    def score(self, query: str, items: Iterable[CatalogItem]) -> dict[str, float]:
        target = list(items)
        sparse_scores = self.sparse.score(query, target)
        dense_scores = self.dense.score(query, target)
        sparse_rank = _rank_map(sparse_scores)
        dense_rank = _rank_map(dense_scores)
        fused: dict[str, float] = {}
        for item in target:
            rrf = 0.0
            sr = sparse_rank.get(item.id)
            dr = dense_rank.get(item.id)
            if sr is not None:
                rrf += 1.0 / (self.rrf_k + sr)
            if dr is not None:
                rrf += 1.0 / (self.rrf_k + dr)
            fused[item.id] = rrf
        if not fused:
            return fused
        peak = max(fused.values()) or 1.0
        return {item_id: value / peak for item_id, value in fused.items()}

    def vector(self, item_id: str) -> list[float] | None:
        return self.dense.vector(item_id)

    def query_vector(self, query: str) -> list[float]:
        return self.dense.query_vector(query)


def _rank_map(scores: dict[str, float]) -> dict[str, int]:
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return {item_id: rank for rank, (item_id, _) in enumerate(ranked, start=1)}


@dataclass(slots=True)
class SentenceTransformerBackend:
    """Dense-embedding backend. Lazily loaded; cached to disk."""

    model_name: str
    cache_dir: Path
    item_ids: list[str]
    item_vectors: list[list[float]]
    _model: object = None                # lazily holds the SentenceTransformer
    _query_cache: dict = None            # query string → vector (LRU-ish)
    _id_index: dict = None               # item_id → index into item_vectors

    @classmethod
    def from_items(
        cls,
        items: Iterable[CatalogItem],
        *,
        model_name: str = "all-MiniLM-L6-v2",
        cache_dir: str | Path = ".cache/embeddings",
    ) -> "SentenceTransformerBackend":
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install the embeddings extra: pip install -e \".[embeddings]\""
            ) from exc

        items_list = list(items)
        cache_root = Path(cache_dir)
        cache_root.mkdir(parents=True, exist_ok=True)
        cache_file = cache_root / cls._cache_filename(model_name, items_list)

        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            backend = cls(
                model_name=model_name,
                cache_dir=cache_root,
                item_ids=list(data["ids"]),
                item_vectors=[list(v) for v in data["vectors"]],
            )
            return backend

        model = SentenceTransformer(_resolve_st_model(model_name))
        texts = [_item_text(item) for item in items_list]
        vectors = model.encode(texts, normalize_embeddings=True).tolist()
        cache_file.write_text(
            json.dumps({"ids": [i.id for i in items_list], "vectors": vectors}),
            encoding="utf-8",
        )
        backend = cls(
            model_name=model_name,
            cache_dir=cache_root,
            item_ids=[i.id for i in items_list],
            item_vectors=vectors,
        )
        backend._model = model
        return backend

    @staticmethod
    def _cache_filename(model_name: str, items: list[CatalogItem]) -> str:
        signature = hashlib.sha256()
        signature.update(model_name.encode("utf-8"))
        for item in items:
            signature.update(item.id.encode("utf-8"))
            signature.update(_item_text(item).encode("utf-8"))
        return f"{model_name.replace('/', '_')}-{signature.hexdigest()[:16]}.json"

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(_resolve_st_model(self.model_name))

    def _ensure_caches(self) -> None:
        if self._query_cache is None:
            self._query_cache = {}
        if self._id_index is None:
            self._id_index = {item_id: i for i, item_id in enumerate(self.item_ids)}

    def query_vector(self, query: str) -> list[float]:
        self._ensure_caches()
        cache = self._query_cache
        # Bound the cache so very long-running sessions don't grow unbounded.
        cached = cache.get(query)
        if cached is not None:
            return cached
        self._ensure_model()
        assert self._model is not None
        vec = self._model.encode([query], normalize_embeddings=True)[0]
        result = vec.tolist() if hasattr(vec, "tolist") else list(vec)
        if len(cache) >= 256:
            # Drop one arbitrary entry; cheap rough LRU.
            cache.pop(next(iter(cache)))
        cache[query] = result
        return result

    def vector(self, item_id: str) -> list[float] | None:
        self._ensure_caches()
        idx = self._id_index.get(item_id)
        if idx is None:
            return None
        return self.item_vectors[idx]  # returned by reference — read-only consumers

    def score(self, query: str, items: Iterable[CatalogItem]) -> dict[str, float]:
        qv = self.query_vector(query)
        self._ensure_caches()
        idx_map = self._id_index
        vectors = self.item_vectors
        out: dict[str, float] = {}
        for item in items:
            i = idx_map.get(item.id)
            if i is None:
                out[item.id] = 0.0
                continue
            out[item.id] = _cosine(qv, vectors[i])
        return out


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass(slots=True)
class Retriever:
    """Backend wrapper + Maximal-Marginal-Relevance reranker."""

    backend: _Backend

    @classmethod
    def from_items(
        cls,
        items: Iterable[CatalogItem],
        *,
        backend: str = "tfidf",
        prefer_dense: bool = False,  # kept for backward compat
        model_name: str | None = None,
        cache_dir: str | Path = ".cache/embeddings",
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
        rrf_k: int = 60,
    ) -> "Retriever":
        """Build a :class:`Retriever`. ``backend`` ∈ {tfidf, bm25, dense, hybrid}."""

        # Back-compat shim
        if prefer_dense and backend == "tfidf":
            backend = "dense"

        items_list = list(items)

        if backend == "dense":
            try:
                return cls(
                    backend=SentenceTransformerBackend.from_items(
                        items_list,
                        model_name=model_name or "all-MiniLM-L6-v2",
                        cache_dir=cache_dir,
                    )
                )
            except ImportError:
                backend = "bm25"

        if backend == "hybrid":
            try:
                return cls(
                    backend=HybridBackend.from_items(
                        items_list,
                        model_name=model_name or "all-MiniLM-L6-v2",
                        cache_dir=cache_dir,
                        rrf_k=rrf_k,
                        k1=bm25_k1,
                        b=bm25_b,
                    )
                )
            except ImportError:
                backend = "bm25"

        if backend == "bm25":
            return cls(backend=Bm25Backend.from_items(items_list, k1=bm25_k1, b=bm25_b))

        return cls(backend=TfidfBackend.from_items(items_list))

    def score(self, query: str, items: Iterable[CatalogItem]) -> dict[str, float]:
        return self.backend.score(query, items)

    def mmr(
        self,
        query: str,
        scored_items: list[tuple[CatalogItem, float]],
        *,
        k: int,
        diversity: float = 0.4,
    ) -> list[tuple[CatalogItem, float]]:
        """Maximal Marginal Relevance — picks ``k`` items balancing relevance and diversity."""

        if not scored_items or k <= 0:
            return []
        remaining = list(scored_items)
        picked: list[tuple[CatalogItem, float]] = []
        # Encode the query exactly once per mmr() call and cache item vectors.
        query_vec = self.backend.query_vector(query)
        item_vec_cache: dict[str, list[float]] = {}

        def vec(item: CatalogItem) -> list[float]:
            cached = item_vec_cache.get(item.id)
            if cached is not None:
                return cached
            v = self.backend.vector(item.id) or []
            item_vec_cache[item.id] = v
            return v

        def rel(item: CatalogItem, base: float) -> float:
            return 0.5 * base + 0.5 * _cosine(query_vec, vec(item))

        while remaining and len(picked) < k:
            best_index = 0
            best_score = -math.inf
            for index, (candidate, base_score) in enumerate(remaining):
                relevance = rel(candidate, base_score)
                if picked:
                    cv = vec(candidate)
                    max_sim = max(_cosine(cv, vec(chosen)) for chosen, _ in picked)
                else:
                    max_sim = 0.0
                mmr_score = (1 - diversity) * relevance - diversity * max_sim
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_index = index
            picked.append(remaining.pop(best_index))
            _ = query_vec  # quiet linter; query_vec used implicitly via backend
        return picked


def _resolve_st_model(model_name: str) -> str:
    """Prefer a bundled sentence-transformers model dir if present.

    When the .app is built with ``packaging/prepare_assets.sh``, the model
    files are unpacked to ``<resource_root>/models/sentence-transformers/<name>``.
    Loading from a local path avoids the first-launch HuggingFace download.
    """

    try:
        from prompt_genius.core.resources import resource_path
        # Try the flat name first (what we store under packaging/models)
        candidate = resource_path(f"models/sentence-transformers/{model_name.replace('/', '_')}")
        if candidate.exists() and (candidate / "config.json").exists():
            return str(candidate)
    except ImportError:
        pass
    return model_name
