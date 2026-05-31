"""JSON-schema validation for generated cards.

Loads the appropriate schema based on the card's mode and returns a list of
:class:`ValidationError` objects. An empty list means valid.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from prompt_genius.core.models import ValidationError

_SCHEMA_FOR_MODE = {
    "static_image": "generated-prompt.schema.json",
    "image_editing": "generated-prompt.schema.json",
    "text_to_video": "video-prompt.schema.json",
    "image_to_video": "video-prompt.schema.json",
    "storyboard": "storyboard.schema.json",
    "keyframe": "storyboard.schema.json",
}


def _load(schema_dir: Path, name: str) -> dict[str, Any]:
    with (schema_dir / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_card(card: dict[str, Any], schema_dir: str | Path) -> list[ValidationError]:
    """Validate a card dict against the schema for its mode."""

    mode = card.get("mode")
    schema_name = _SCHEMA_FOR_MODE.get(mode or "")
    if not schema_name:
        return [ValidationError(path="mode", message=f"Unknown mode: {mode!r}")]

    schema_root = Path(schema_dir)
    schema = _load(schema_root, schema_name)
    validator = Draft202012Validator(schema)
    errors: list[ValidationError] = []
    for err in sorted(validator.iter_errors(card), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(ValidationError(path=path, message=err.message))
    return errors
