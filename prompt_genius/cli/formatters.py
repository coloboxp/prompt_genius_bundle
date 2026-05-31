"""Plain-text renderers for prompt cards.

Pure functions returning strings. The CLI prints them; the future GUI ignores
these and renders the dataclasses directly. Do not import from these
formatters in ``prompt_genius.core``.
"""

from __future__ import annotations

import json
from typing import Any

from prompt_genius.core.models import PromptCard, to_dict


def card_summary(card: PromptCard) -> str:
    """One-card human-readable summary suitable for a terminal."""

    lines: list[str] = []
    lines.append(f"── {card.title} ──")
    lines.append(f"id: {card.id}")
    lines.append(f"mode: {card.mode}   target: {card.target_model}   risk: {card.risk_level}")
    lines.append(f"patterns: {', '.join(card.selected_patterns) or '(none)'}")
    lines.append(f"why: {card.why_this_works}")
    if isinstance(card.compiled, list):
        for index, compiled in enumerate(card.compiled, start=1):
            lines.append(f"  ── shot/frame {index} ──")
            lines.append(_indent(compiled.text, 4))
            if compiled.negative_text:
                lines.append(_indent(compiled.negative_text, 4))
    else:
        lines.append("prompt:")
        lines.append(_indent(card.compiled.text, 2))
        if card.compiled.negative_text:
            lines.append("negative:")
            lines.append(_indent(card.compiled.negative_text, 2))
    for warning in card.warnings:
        lines.append(f"⚠ {warning.code}: {warning.message}")
    return "\n".join(lines)


def cards_summary(cards: list[PromptCard]) -> str:
    return "\n\n".join(card_summary(c) for c in cards)


def cards_as_json(cards: list[PromptCard]) -> str:
    return json.dumps([to_dict(c) for c in cards], indent=2, ensure_ascii=False)


def adapter_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no adapters)"
    headers = ["model_id", "display_name", "adapter_status", "modes"]
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(_stringify(row.get(h))))
    line = " ".join(h.ljust(widths[h]) for h in headers)
    sep = "-" * len(line)
    out = [line, sep]
    for row in rows:
        out.append(" ".join(_stringify(row.get(h)).ljust(widths[h]) for h in headers))
    return "\n".join(out)


def _stringify(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return "" if value is None else str(value)


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.splitlines() or [""])
