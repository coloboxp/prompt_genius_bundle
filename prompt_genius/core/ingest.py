"""CSV corpus ingestion.

Designers receive prompt datasets periodically — sometimes as full re-exports
of an existing model, sometimes from new models entirely, sometimes in
slightly different column shapes from different providers. This module:

* Detects the schema of an incoming CSV and maps it to our canonical columns.
* Computes the delta against the current raw corpus (by ``sha256(content)``).
* Optionally writes the surviving new rows into ``raw_corpus/`` as a clean,
  canonical CSV, then invalidates the vocab + embeddings caches so the next
  app launch rebuilds against the new data.
* Suggests creating a stub adapter when an entirely new model id appears.

Original files in ``raw_corpus/`` are never mutated — new rows are written to
a fresh ``<source>-<date>.csv`` so a ``git diff`` cleanly shows what landed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


csv.field_size_limit(sys.maxsize)


# Canonical columns the rest of the codebase expects.
CANONICAL_COLUMNS: tuple[str, ...] = (
    "id",
    "title",
    "description",
    "content",
    "sourceLink",
    "sourcePublishedAt",
    "author",
    "sourceMedia",
    "sourceReferenceImages",
    "sourceVideos",
)

# Heuristic synonyms — when an incoming CSV uses a different header we still
# know what each column means. Add freely; first hit wins.
_SYNONYMS: dict[str, tuple[str, ...]] = {
    "id": ("id", "uuid", "prompt_id"),
    "title": ("title", "name", "headline"),
    "description": ("description", "summary", "subtitle"),
    "content": ("content", "prompt", "text", "body"),
    "sourceLink": ("sourceLink", "source_url", "url", "link"),
    "sourcePublishedAt": ("sourcePublishedAt", "published_at", "publishedAt", "created_at"),
    "author": ("author", "author_name", "creator"),
    "sourceMedia": ("sourceMedia", "media", "preview_images"),
    "sourceReferenceImages": ("sourceReferenceImages", "reference_images", "refs"),
    "sourceVideos": ("sourceVideos", "preview_videos", "videos"),
}


@dataclass(slots=True)
class IngestFormat:
    """Detected column mapping for one incoming CSV."""

    path: Path
    detected_columns: list[str]
    mapping: dict[str, str]            # canonical → source column
    missing_required: list[str]        # canonical fields nothing maps to
    model_id: str                      # inferred model id (from file stem)


@dataclass(slots=True)
class IngestRow:
    """One canonical row ready to write or skip."""

    canonical: dict[str, str]
    content_hash: str


@dataclass(slots=True)
class IngestPlan:
    """The outcome of comparing an incoming CSV against the current corpus."""

    fmt: IngestFormat
    new_rows: list[IngestRow] = field(default_factory=list)
    duplicate_rows: int = 0
    invalid_rows: int = 0
    seen_hashes: set[str] = field(default_factory=set)
    target_filename: str = ""

    @property
    def total_input(self) -> int:
        return len(self.new_rows) + self.duplicate_rows + self.invalid_rows

    def summary(self) -> dict[str, object]:
        return {
            "source": str(self.fmt.path),
            "model_id": self.fmt.model_id,
            "mapping": self.fmt.mapping,
            "missing_required": list(self.fmt.missing_required),
            "rows_input": self.total_input,
            "rows_new": len(self.new_rows),
            "rows_duplicate": self.duplicate_rows,
            "rows_invalid": self.invalid_rows,
            "target_filename": self.target_filename,
        }


# ---------------------------------------------------------------- detection


def detect_format(path: str | Path) -> IngestFormat:
    """Inspect a CSV header and return a canonical → source column mapping."""

    csv_path = Path(path)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        cols = list(reader.fieldnames or [])
    cols_lower = {c.lower(): c for c in cols}
    mapping: dict[str, str] = {}
    for canonical, synonyms in _SYNONYMS.items():
        for synonym in synonyms:
            actual = cols_lower.get(synonym.lower())
            if actual:
                mapping[canonical] = actual
                break
    required = ("id", "title", "content")
    missing = [r for r in required if r not in mapping]
    return IngestFormat(
        path=csv_path,
        detected_columns=cols,
        mapping=mapping,
        missing_required=missing,
        model_id=_infer_model_id(csv_path.name),
    )


def _infer_model_id(filename: str) -> str:
    stem = Path(filename).stem.lower()
    # strip trailing -YYYYMMDD or -YYYY-MM-DD style date suffixes
    stem = re.sub(r"[-_]?\d{8}$", "", stem)
    stem = re.sub(r"[-_]?\d{4}-?\d{2}-?\d{2}$", "", stem)
    stem = re.sub(r"[-_]?prompts$", "", stem)
    return stem.replace("-", "_").strip("_") or "unknown_model"


# ---------------------------------------------------------------- delta


def _content_hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().encode("utf-8", errors="ignore")).hexdigest()


def existing_content_hashes(raw_corpus_dir: str | Path) -> set[str]:
    """Hash every existing prompt's ``content`` so we can dedupe incoming rows."""

    hashes: set[str] = set()
    root = Path(raw_corpus_dir)
    if not root.exists():
        return hashes
    for csv_path in sorted(root.glob("*.csv")):
        try:
            with csv_path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    content = (row.get("content") or "").strip()
                    if content:
                        hashes.add(_content_hash(content))
        except (OSError, csv.Error):
            continue
    return hashes


def plan_ingest(
    csv_path: str | Path,
    raw_corpus_dir: str | Path,
    *,
    target_filename: str | None = None,
) -> IngestPlan:
    """Detect format + walk every row + compare against the corpus."""

    fmt = detect_format(csv_path)
    seen = existing_content_hashes(raw_corpus_dir)
    plan = IngestPlan(fmt=fmt, seen_hashes=seen)
    plan.target_filename = target_filename or fmt.path.name

    if fmt.missing_required:
        # Refuse to plan when required columns can't be located.
        return plan

    with fmt.path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            canonical = _map_row(row, fmt.mapping)
            content = canonical.get("content", "").strip()
            if not content or not canonical.get("id", "").strip():
                plan.invalid_rows += 1
                continue
            digest = _content_hash(content)
            if digest in seen:
                plan.duplicate_rows += 1
                continue
            seen.add(digest)
            plan.new_rows.append(IngestRow(canonical=canonical, content_hash=digest))
    return plan


def _map_row(row: dict[str, str], mapping: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for canonical in CANONICAL_COLUMNS:
        src = mapping.get(canonical)
        out[canonical] = (row.get(src) or "") if src else ""
    return out


# ---------------------------------------------------------------- apply


def apply_plan(
    plan: IngestPlan,
    raw_corpus_dir: str | Path,
    *,
    cache_dirs: Iterable[str | Path] = (".cache/vocab", ".cache/embeddings", ".cache/corpus"),
    write_if_zero_new: bool = False,
) -> Path | None:
    """Write the new rows to ``raw_corpus/`` and invalidate caches.

    Returns the written file path, or ``None`` when nothing was written.
    """

    if plan.fmt.missing_required:
        raise ValueError(
            f"Cannot ingest {plan.fmt.path.name}: missing required columns "
            f"{plan.fmt.missing_required}. "
            f"Detected: {plan.fmt.detected_columns}"
        )
    if not plan.new_rows and not write_if_zero_new:
        return None

    target_dir = Path(raw_corpus_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / plan.target_filename
    if target_path.exists():
        # Don't clobber existing source files — write a deduped sibling.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target_path = target_dir / f"{Path(plan.target_filename).stem}-ingest-{stamp}.csv"

    with target_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CANONICAL_COLUMNS))
        writer.writeheader()
        for entry in plan.new_rows:
            writer.writerow(entry.canonical)

    _invalidate_caches(cache_dirs)
    # Also drop any in-process catalog / corpus caches so the next call rebuilds.
    try:
        from prompt_genius.core.generate import invalidate_catalog_cache, _CORPUS_CACHE
        invalidate_catalog_cache()
        _CORPUS_CACHE.clear()
    except ImportError:
        pass
    return target_path


def _invalidate_caches(cache_dirs: Iterable[str | Path]) -> None:
    for cache in cache_dirs:
        path = Path(cache)
        if not path.exists():
            continue
        try:
            shutil.rmtree(path)
        except OSError:
            pass


# ----------------------------------------------------- stub-adapter helper


def propose_stub_adapter(model_id: str) -> dict:
    """Generate a minimal stub adapter JSON for a brand-new model id."""

    return {
        "model_id": model_id,
        "display_name": model_id.replace("_", " ").title(),
        "adapter_status": "stub_unverified",
        "supports": {
            "static_image": True,
            "image_editing": True,
            "text_to_video": True,
            "image_to_video": True,
            "storyboard": True,
            "keyframe": True,
        },
        "parameters": {
            "aspect_ratio": {"supported": True, "syntax": "aspect ratio: {value}"},
            "negative_prompt": {"supported": True, "syntax": "avoid: {value}"},
            "reference_image": {"supported": True, "syntax": "reference: {value}"},
        },
        "prompt_style": "detailed_natural_language",
        "negative_prompt_behavior": "append_avoid_sentence",
        "unsupported_fields_behavior": "drop",
        "language": "english_preferred",
        "notes": (
            f"Auto-generated stub adapter created during ingest of {model_id!r} "
            "prompts. Tighten the parameter whitelist and prompt_style after "
            "confirming the model's real grammar."
        ),
    }


def write_stub_adapter_if_missing(model_id: str, adapters_dir: str | Path) -> Path | None:
    """Create a stub adapter for ``model_id`` when none exists. Returns its path."""

    target = Path(adapters_dir) / f"{model_id}_adapter.json"
    if target.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(propose_stub_adapter(model_id), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target
