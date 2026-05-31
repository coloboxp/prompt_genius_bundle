#!/usr/bin/env python3
"""Inventory raw_corpus/ CSV files for Prompt Genius.

Reports per-file: row count, column null counts, content length distribution,
language ratio (latin vs CJK), unique author count, and date range.

Usage:
    python scripts/csv_inventory.py raw_corpus/
"""

from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

CJK_RE = re.compile(r"[　-〿぀-ゟ゠-ヿ一-鿿＀-￯]")


def lang_ratio(text: str) -> tuple[float, float]:
    if not text:
        return (0.0, 0.0)
    cjk = sum(1 for ch in text if CJK_RE.match(ch))
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    total = max(cjk + latin, 1)
    return (latin / total, cjk / total)


def parse_author(raw: str) -> str | None:
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        name = obj.get("name") if isinstance(obj, dict) else None
        return name or None
    except (json.JSONDecodeError, AttributeError):
        return None


def percentiles(values: list[int], pcts: Iterable[int]) -> dict[int, int]:
    if not values:
        return {p: 0 for p in pcts}
    sorted_values = sorted(values)
    out = {}
    for p in pcts:
        idx = max(0, min(len(sorted_values) - 1, int(round((p / 100) * (len(sorted_values) - 1)))))
        out[p] = sorted_values[idx]
    return out


def inventory_file(path: Path) -> None:
    print(f"\n=== {path.name} ===")
    rows = 0
    null_counts: Counter[str] = Counter()
    content_lengths: list[int] = []
    latin_rows = 0
    cjk_rows = 0
    mixed_rows = 0
    authors: Counter[str] = Counter()
    dates: list[str] = []
    bad_author_json = 0
    bad_media_json = 0

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            print("  (empty)")
            return
        columns = list(reader.fieldnames)
        for row in reader:
            rows += 1
            for col in columns:
                if not (row.get(col) or "").strip():
                    null_counts[col] += 1

            content = row.get("content") or ""
            content_lengths.append(len(content))
            latin, cjk = lang_ratio(content)
            if latin > 0.8:
                latin_rows += 1
            elif cjk > 0.5:
                cjk_rows += 1
            elif latin > 0 and cjk > 0:
                mixed_rows += 1

            author_name = parse_author(row.get("author") or "")
            if author_name:
                authors[author_name] += 1
            elif (row.get("author") or "").strip():
                bad_author_json += 1

            media_raw = (row.get("sourceMedia") or "").strip()
            if media_raw:
                try:
                    json.loads(media_raw)
                except json.JSONDecodeError:
                    bad_media_json += 1

            published = (row.get("sourcePublishedAt") or "").strip()
            if published:
                dates.append(published)

    print(f"  rows: {rows}")
    print(f"  columns: {', '.join(columns)}")
    print("  empty/null counts:")
    for col in columns:
        print(f"    {col}: {null_counts[col]}")

    if content_lengths:
        pcts = percentiles(content_lengths, [50, 90, 95, 99])
        print("  content length:")
        print(f"    min: {min(content_lengths)}")
        print(f"    p50: {pcts[50]}  p90: {pcts[90]}  p95: {pcts[95]}  p99: {pcts[99]}")
        print(f"    max: {max(content_lengths)}")
        print(f"    mean: {int(statistics.mean(content_lengths))}")

    print("  language (content):")
    print(f"    latin-dominant: {latin_rows}")
    print(f"    cjk-dominant: {cjk_rows}")
    print(f"    mixed: {mixed_rows}")

    print(f"  unique authors: {len(authors)}")
    print("  top 5 authors:")
    for name, count in authors.most_common(5):
        print(f"    {name}: {count}")

    print(f"  malformed author JSON: {bad_author_json}")
    print(f"  malformed sourceMedia JSON: {bad_media_json}")

    if dates:
        print(f"  date range: {min(dates)} → {max(dates)}")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python csv_inventory.py <raw_corpus_dir>")
        return 2
    root = Path(sys.argv[1])
    if not root.exists():
        print(f"Directory not found: {root}")
        return 2

    csvs = sorted(root.glob("*.csv"))
    if not csvs:
        print(f"No CSV files in {root}")
        return 1

    csv.field_size_limit(sys.maxsize)
    for path in csvs:
        inventory_file(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
