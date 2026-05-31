"""Pattern usage ledger.

Every time a card is generated, saved, or exported, the cards's selected
catalog patterns get an entry in ``data/usage.jsonl``. The quality recompute
reads this ledger to derive reuse and export rates and to age stale signals.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_ALLOWED_EVENTS: frozenset[str] = frozenset({"generated", "selected", "saved", "exported"})


def record_usage(
    pattern_ids: list[str],
    *,
    event: str,
    card_id: str | None = None,
    ledger_path: str | Path = "data/usage.jsonl",
) -> Path:
    """Append one row per pattern to the usage ledger.

    ``event`` ∈ {generated, selected, saved, exported}. Other values raise.
    """

    if event not in _ALLOWED_EVENTS:
        raise ValueError(f"unknown usage event: {event!r}")

    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        for pid in pattern_ids:
            handle.write(
                json.dumps(
                    {
                        "ts": timestamp,
                        "event": event,
                        "pattern_id": pid,
                        "card_id": card_id,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return path


def read_usage(ledger_path: str | Path) -> list[dict]:
    path = Path(ledger_path)
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out
