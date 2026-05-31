#!/usr/bin/env python3
"""Inventory Prompt Genius catalog JSON files."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python inventory_catalog.py <catalog_dir>")
        return 2

    root = Path(sys.argv[1])
    if not root.exists():
        print(f"Directory not found: {root}")
        return 2

    files = sorted(root.rglob("*.json"))
    type_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    invalid = []

    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            invalid.append((path, str(exc)))
            continue

        type_counts[str(data.get("type", "<missing>"))] += 1
        status_counts[str(data.get("status", "<missing>"))] += 1
        for tag in data.get("tags", []) or []:
            tag_counts[str(tag)] += 1

    print(f"Catalog directory: {root}")
    print(f"JSON files: {len(files)}")
    print(f"Invalid JSON files: {len(invalid)}")
    print("\nCounts by type:")
    for key, value in type_counts.most_common():
        print(f"  {key}: {value}")

    print("\nCounts by status:")
    for key, value in status_counts.most_common():
        print(f"  {key}: {value}")

    print("\nTop tags:")
    for key, value in tag_counts.most_common(20):
        print(f"  {key}: {value}")

    if invalid:
        print("\nInvalid files:")
        for path, error in invalid:
            print(f"  {path}: {error}")

    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
