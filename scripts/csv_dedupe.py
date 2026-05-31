#!/usr/bin/env python3
"""Detect duplicate and near-duplicate prompt rows in raw_corpus/ CSVs.

Exact dupes by sha256(content). Near-dupes by case-folded title Levenshtein
within a first-4-chars bucket (cheap proxy to avoid O(n^2) on 301k rows).

Writes one report per CSV: audit/<basename>_duplicates.csv with columns
id_a,id_b,reason.

Usage:
    python scripts/csv_dedupe.py raw_corpus/ audit/
"""

from __future__ import annotations

import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def levenshtein(a: str, b: str, cutoff: int) -> int:
    if a == b:
        return 0
    if abs(len(a) - len(b)) > cutoff:
        return cutoff + 1
    if len(a) > len(b):
        a, b = b, a

    previous = list(range(len(a) + 1))
    for j, cb in enumerate(b, start=1):
        current = [j] + [0] * len(a)
        row_min = current[0]
        for i, ca in enumerate(a, start=1):
            cost = 0 if ca == cb else 1
            current[i] = min(
                current[i - 1] + 1,
                previous[i] + 1,
                previous[i - 1] + cost,
            )
            if current[i] < row_min:
                row_min = current[i]
        if row_min > cutoff:
            return cutoff + 1
        previous = current
    return previous[-1]


def dedupe_file(path: Path, out_dir: Path) -> None:
    print(f"\n=== {path.name} ===")
    exact_buckets: dict[str, list[str]] = defaultdict(list)
    title_buckets: dict[str, list[tuple[str, str]]] = defaultdict(list)

    csv.field_size_limit(sys.maxsize)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_id = (row.get("id") or "").strip()
            content = (row.get("content") or "").strip()
            title = (row.get("title") or "").strip().casefold()
            if not row_id:
                continue
            if content:
                exact_buckets[sha256_hex(content)].append(row_id)
            if title:
                key = title[:4]
                title_buckets[key].append((row_id, title))

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{path.stem}_duplicates.csv"
    rows_written = 0
    cutoff = 3
    with out_path.open("w", encoding="utf-8", newline="") as out_handle:
        writer = csv.writer(out_handle)
        writer.writerow(["id_a", "id_b", "reason"])

        for ids in exact_buckets.values():
            if len(ids) > 1:
                anchor = ids[0]
                for other in ids[1:]:
                    writer.writerow([anchor, other, "exact_content_sha256"])
                    rows_written += 1

        for bucket in title_buckets.values():
            n = len(bucket)
            if n < 2 or n > 500:
                continue
            for i in range(n):
                id_a, title_a = bucket[i]
                for j in range(i + 1, n):
                    id_b, title_b = bucket[j]
                    if title_a == title_b:
                        writer.writerow([id_a, id_b, "exact_title"])
                        rows_written += 1
                        continue
                    distance = levenshtein(title_a, title_b, cutoff)
                    if distance <= cutoff:
                        writer.writerow([id_a, id_b, f"near_title_lev{distance}"])
                        rows_written += 1

    exact_dupes = sum(len(ids) - 1 for ids in exact_buckets.values() if len(ids) > 1)
    print(f"  exact content duplicates (extras): {exact_dupes}")
    print(f"  total pairs written: {rows_written}")
    print(f"  report: {out_path}")


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python csv_dedupe.py <raw_corpus_dir> <audit_out_dir>")
        return 2
    root = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    if not root.exists():
        print(f"Directory not found: {root}")
        return 2

    csvs = sorted(root.glob("*.csv"))
    if not csvs:
        print(f"No CSV files in {root}")
        return 1

    for path in csvs:
        dedupe_file(path, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
