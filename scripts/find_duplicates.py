#!/usr/bin/env python3
"""Find simple duplicates in Prompt Genius catalog JSON files."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().split())


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python find_duplicates.py <catalog_dir>")
        return 2

    root = Path(sys.argv[1])
    ids: dict[str, Path] = {}
    names: defaultdict[str, list[Path]] = defaultdict(list)
    generic_fragments: defaultdict[str, list[Path]] = defaultdict(list)
    duplicates_found = False

    for path in sorted(root.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        item_id = data.get("id")
        if item_id:
            if item_id in ids:
                duplicates_found = True
                print(f"Duplicate ID: {item_id}")
                print(f"  {ids[item_id]}")
                print(f"  {path}")
            else:
                ids[item_id] = path

        name = data.get("name")
        if name:
            names[normalize_text(name)].append(path)

        generic = (data.get("prompt_fragments") or {}).get("generic")
        if generic:
            generic_fragments[normalize_text(generic)].append(path)

    for name, paths in names.items():
        if len(paths) > 1:
            duplicates_found = True
            print(f"\nDuplicate or very similar name: {name}")
            for path in paths:
                print(f"  {path}")

    for fragment, paths in generic_fragments.items():
        if len(paths) > 1:
            duplicates_found = True
            print(f"\nDuplicate generic prompt fragment: {fragment[:120]}")
            for path in paths:
                print(f"  {path}")

    if not duplicates_found:
        print("No simple duplicates found.")

    return 1 if duplicates_found else 0


if __name__ == "__main__":
    raise SystemExit(main())
