#!/usr/bin/env python3
"""Validate Prompt Genius catalog JSON files.

Uses jsonschema if available. Falls back to basic checks otherwise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = [
    "id", "type", "category", "name", "description", "applies_to",
    "not_recommended_for", "prompt_fragments", "parameters", "compatible_with",
    "avoid_with", "tags", "quality_score", "status", "version"
]

VALID_STATUSES = {"draft", "active", "deprecated", "archived"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def basic_validate(data: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    status = data.get("status")
    if status is not None and status not in VALID_STATUSES:
        errors.append(f"invalid status: {status}")

    score = data.get("quality_score")
    if score is not None:
        if not isinstance(score, (int, float)) or score < 0 or score > 1:
            errors.append(f"quality_score must be number between 0 and 1: {score}")

    tags = data.get("tags")
    if not isinstance(tags, list) or not tags:
        errors.append("tags must be a non-empty list")

    fragments = data.get("prompt_fragments")
    if not isinstance(fragments, dict) or not fragments.get("generic"):
        errors.append("prompt_fragments.generic is required")

    return errors


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python validate_catalog.py <catalog_dir> <schema_path>")
        return 2

    catalog_dir = Path(sys.argv[1])
    schema_path = Path(sys.argv[2])

    try:
        import jsonschema  # type: ignore
        schema = load_json(schema_path)
        use_jsonschema = True
    except Exception:
        schema = None
        use_jsonschema = False
        print("jsonschema not available or schema could not be loaded. Using basic validation.")

    files = sorted(catalog_dir.rglob("*.json"))
    all_errors: list[str] = []
    seen_ids: dict[str, Path] = {}

    for path in files:
        try:
            data = load_json(path)
        except Exception as exc:
            all_errors.append(f"{path}: invalid JSON: {exc}")
            continue

        item_id = data.get("id")
        if item_id:
            if item_id in seen_ids:
                all_errors.append(f"{path}: duplicate id {item_id}; first seen in {seen_ids[item_id]}")
            else:
                seen_ids[item_id] = path

        if use_jsonschema:
            try:
                jsonschema.validate(instance=data, schema=schema)
            except Exception as exc:
                all_errors.append(f"{path}: schema error: {exc}")
        else:
            for error in basic_validate(data, path):
                all_errors.append(f"{path}: {error}")

    if all_errors:
        print("Validation failed:")
        for error in all_errors:
            print(f"  {error}")
        return 1

    print(f"Validation passed for {len(files)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
