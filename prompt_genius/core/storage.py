"""JSON / JSONL persistence for cards and feedback.

Pure I/O — no logging, no printing. The CLI or GUI decides what to do on
success or failure.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def save_card(card: dict[str, Any], directory: str | Path) -> Path:
    """Save a card to ``directory/<card_id>.json``. Returns the written path."""

    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    card_id = card.get("id") or datetime.now(timezone.utc).strftime("card_%Y%m%dT%H%M%SZ")
    path = root / f"{card_id}.json"
    path.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def save_feedback(
    feedback: dict[str, Any], jsonl_path: str | Path
) -> Path:
    """Append a feedback record as one JSON line to ``jsonl_path``."""

    path = Path(jsonl_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(feedback)
    record.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
