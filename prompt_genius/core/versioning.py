"""Prompt version history + side-by-side diff.

Each refinement of a card is appended to a JSONL log so a designer can review
how a prompt evolved. ``diff_cards`` is a coarse text-diff helper for the
CLI / GUI.
"""

from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def save_version(
    card: dict[str, Any],
    jsonl_path: str | Path,
    *,
    change_summary: str | None = None,
) -> Path:
    """Append a snapshot of ``card`` to a JSONL version log."""

    path = Path(jsonl_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "card_id": card.get("id"),
        "title": card.get("title"),
        "target_model": card.get("target_model"),
        "mode": card.get("mode"),
        "change_summary": change_summary,
        "card": card,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def diff_cards(
    card_a: dict[str, Any], card_b: dict[str, Any], *, field: str = "prompt"
) -> str:
    """Return a unified text diff between the ``field`` text of two cards.

    ``field`` may be ``"prompt"`` (compiled text), ``"negative"``
    (compiled negative text), ``"why"`` (why_this_works), or
    ``"patterns"`` (selected_patterns).
    """

    a = _extract_field(card_a, field)
    b = _extract_field(card_b, field)
    diff = difflib.unified_diff(
        a.splitlines(keepends=False),
        b.splitlines(keepends=False),
        fromfile=card_a.get("id", "a"),
        tofile=card_b.get("id", "b"),
        lineterm="",
    )
    return "\n".join(diff)


def _extract_field(card: dict[str, Any], field: str) -> str:
    if field == "why":
        return str(card.get("why_this_works") or "")
    if field == "patterns":
        return "\n".join(card.get("selected_patterns") or [])
    compiled = card.get("compiled")
    if isinstance(compiled, list):
        if field == "negative":
            return "\n\n".join(c.get("negative_text", "") for c in compiled)
        return "\n\n".join(c.get("text", "") for c in compiled)
    compiled = compiled or {}
    if field == "negative":
        return str(compiled.get("negative_text") or "")
    return str(compiled.get("text") or "")
