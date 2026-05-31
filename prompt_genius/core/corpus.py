"""Raw-corpus index.

Loads the source CSVs in ``raw_corpus/`` and exposes a BM25 search over their
``content`` columns so the LLM card proposer can pull real-world exemplars to
inspire pattern selection and parameter values.

Filter knobs let the GUI restrict by source file (nano-banana-pro vs seedance),
language (latin / cjk / mixed), and minimum content length.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from prompt_genius.core.retrieval import Bm25Backend, _tokenize


csv.field_size_limit(sys.maxsize)

_CJK_RE = re.compile(r"[　-〿぀-ゟ゠-ヿ一-鿿＀-￯]")


@dataclass(slots=True)
class CorpusRow:
    id: str                     # "<filename>::<row_id>"
    source_file: str            # CSV filename
    source_id: str              # original id column
    title: str
    description: str
    content: str
    source_link: str
    author_name: str | None
    published_at: str
    language: str               # "latin" | "cjk" | "mixed"
    content_length: int
    tokens: list[str] = field(default_factory=list)


def _detect_language(text: str) -> str:
    cjk = sum(1 for ch in text if _CJK_RE.match(ch))
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    if latin == 0 and cjk == 0:
        return "latin"
    if cjk == 0:
        return "latin"
    if latin == 0:
        return "cjk"
    ratio = cjk / max(cjk + latin, 1)
    if ratio > 0.6:
        return "cjk"
    if ratio < 0.1:
        return "latin"
    return "mixed"


def _parse_author(raw: str) -> str | None:
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            name = obj.get("name")
            return name or None
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def iter_rows(
    corpus_dir: str | Path,
    *,
    min_length: int = 40,
) -> Iterator[CorpusRow]:
    """Yield :class:`CorpusRow` for every usable row across the corpus CSVs."""

    root = Path(corpus_dir)
    if not root.exists():
        return
    for path in sorted(root.glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                continue
            for row in reader:
                content = (row.get("content") or "").strip()
                if len(content) < min_length:
                    continue
                source_id = (row.get("id") or "").strip()
                if not source_id:
                    continue
                language = _detect_language(content)
                tokens = _tokenize(content)
                yield CorpusRow(
                    id=f"{path.name}::{source_id}",
                    source_file=path.name,
                    source_id=source_id,
                    title=(row.get("title") or "").strip(),
                    description=(row.get("description") or "").strip(),
                    content=content,
                    source_link=(row.get("sourceLink") or "").strip(),
                    author_name=_parse_author(row.get("author") or ""),
                    published_at=(row.get("sourcePublishedAt") or "").strip(),
                    language=language,
                    content_length=len(content),
                    tokens=tokens,
                )


_CORPUS_CACHE_VERSION = 2


def _corpus_signature(corpus_dir: Path) -> str:
    """Deterministic signature for the set of source CSVs (name + size + mtime)."""

    import hashlib
    parts: list[str] = [str(_CORPUS_CACHE_VERSION)]
    if not corpus_dir.exists():
        return "missing"
    for path in sorted(corpus_dir.glob("*.csv")):
        stat = path.stat()
        parts.append(f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}")
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class CorpusIndex:
    """In-memory BM25 index over raw-corpus rows."""

    rows: dict[str, CorpusRow] = field(default_factory=dict)
    bm25: Bm25Backend | None = None

    @classmethod
    def from_dir(
        cls,
        corpus_dir: str | Path,
        *,
        max_rows: int | None = None,
        languages: Iterable[str] | None = None,
        sources: Iterable[str] | None = None,
        min_length: int = 40,
        dedupe_by_content: bool = True,
    ) -> "CorpusIndex":
        import hashlib

        rows: dict[str, CorpusRow] = {}
        seen_content: set[str] = set()
        wanted_langs = set(languages) if languages else None
        wanted_sources = set(sources) if sources else None
        for row in iter_rows(corpus_dir, min_length=min_length):
            if wanted_langs and row.language not in wanted_langs:
                continue
            if wanted_sources and row.source_file not in wanted_sources:
                continue
            if dedupe_by_content:
                digest = hashlib.sha256(
                    row.content.strip().encode("utf-8", errors="ignore")
                ).hexdigest()
                if digest in seen_content:
                    continue
                seen_content.add(digest)
            rows[row.id] = row
            if max_rows is not None and len(rows) >= max_rows:
                break
        index = cls(rows=rows)
        index._build_bm25()
        return index

    def _build_bm25(self) -> None:
        # Adapt CorpusRow → tokens for Bm25Backend by building it manually.
        item_ids = list(self.rows)
        item_tokens = {rid: list(self.rows[rid].tokens) for rid in item_ids}
        doc_freq: Counter[str] = Counter()
        doc_lengths: dict[str, int] = {}
        for rid, toks in item_tokens.items():
            doc_lengths[rid] = len(toks)
            for term in set(toks):
                doc_freq[term] += 1
        total_length = sum(doc_lengths.values())
        avg_doc_len = (total_length / max(len(item_ids), 1))
        self.bm25 = Bm25Backend(
            item_ids=item_ids,
            item_tokens=item_tokens,
            doc_freq=doc_freq,
            avg_doc_len=avg_doc_len,
            doc_lengths=doc_lengths,
        )

    def search(self, query: str, *, k: int = 5) -> list[tuple[CorpusRow, float]]:
        if not self.bm25 or not query.strip():
            return []
        query_tokens = _tokenize(query)
        raw: list[tuple[str, float]] = []
        for rid in self.bm25.item_ids:
            score = self.bm25._raw_score(query_tokens, rid)
            if score > 0:
                raw.append((rid, score))
        raw.sort(key=lambda kv: -kv[1])
        return [(self.rows[rid], score) for rid, score in raw[:k]]

    def __len__(self) -> int:
        return len(self.rows)

    # ---------------------------------------------------------- disk cache

    def to_cache(self, cache_path: str | Path) -> None:
        path = Path(cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _CORPUS_CACHE_VERSION,
            "rows": [
                {
                    "id": r.id,
                    "source_file": r.source_file,
                    "source_id": r.source_id,
                    "title": r.title,
                    "description": r.description,
                    "content": r.content,
                    "source_link": r.source_link,
                    "author_name": r.author_name,
                    "published_at": r.published_at,
                    "language": r.language,
                    "content_length": r.content_length,
                    "tokens": r.tokens,
                }
                for r in self.rows.values()
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def from_cache(cls, cache_path: str | Path) -> "CorpusIndex | None":
        path = Path(cache_path)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if payload.get("version") != _CORPUS_CACHE_VERSION:
            return None
        rows: dict[str, CorpusRow] = {}
        for entry in payload.get("rows", []):
            rows[entry["id"]] = CorpusRow(
                id=entry["id"],
                source_file=entry["source_file"],
                source_id=entry["source_id"],
                title=entry["title"],
                description=entry["description"],
                content=entry["content"],
                source_link=entry["source_link"],
                author_name=entry.get("author_name"),
                published_at=entry.get("published_at", ""),
                language=entry["language"],
                content_length=entry["content_length"],
                tokens=list(entry.get("tokens") or []),
            )
        index = cls(rows=rows)
        index._build_bm25()
        return index


def load_or_build_corpus_index(
    corpus_dir: str | Path,
    cache_dir: str | Path = ".cache/corpus",
    *,
    rebuild: bool = False,
) -> CorpusIndex:
    """Disk-cached :class:`CorpusIndex`. Rebuilds when the source CSV set changes."""

    corpus_root = Path(corpus_dir)
    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    signature = _corpus_signature(corpus_root)
    cache_path = cache_root / f"corpus_index-{signature}.json"
    if not rebuild:
        cached = CorpusIndex.from_cache(cache_path)
        if cached is not None:
            return cached
    index = CorpusIndex.from_dir(corpus_root)
    try:
        index.to_cache(cache_path)
    except OSError:
        pass
    return index
