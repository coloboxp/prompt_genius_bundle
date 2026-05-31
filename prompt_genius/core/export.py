"""Exporters: render a card in formats designers can paste into target tools.

Each exporter is a pure function returning ``(filename_suffix, text)``. The
CLI writes the file; the GUI can offer "copy to clipboard".
"""

from __future__ import annotations

from typing import Any


def export_plain(card: dict[str, Any]) -> tuple[str, str]:
    """Single-block plain text suited for any model."""

    compiled = card.get("compiled")
    if isinstance(compiled, list):
        body = "\n\n".join(
            _shot_block(idx, item) for idx, item in enumerate(compiled, start=1)
        )
    else:
        body = _single_block(compiled or {})
    header = f"# {card.get('title', '')} [{card.get('target_model')}]\n"
    return ".txt", header + body


def export_markdown(card: dict[str, Any]) -> tuple[str, str]:
    """Slack / Notion-friendly markdown."""

    compiled = card.get("compiled")
    parts: list[str] = [f"### {card.get('title', '')} ({card.get('target_model')})"]
    parts.append("")
    if isinstance(compiled, list):
        for index, item in enumerate(compiled, start=1):
            parts.append(f"**Shot {index}**")
            parts.append("```")
            parts.append(item.get("text", ""))
            if item.get("negative_text"):
                parts.append("")
                parts.append(item["negative_text"])
            parts.append("```")
            parts.append("")
    else:
        item = compiled or {}
        parts.append("```")
        parts.append(item.get("text", ""))
        if item.get("negative_text"):
            parts.append("")
            parts.append(item["negative_text"])
        parts.append("```")
    if card.get("why_this_works"):
        parts.append("")
        parts.append(f"_why:_ {card['why_this_works']}")
    return ".md", "\n".join(parts)


def export_json(card: dict[str, Any]) -> tuple[str, str]:
    import json

    return ".json", json.dumps(card, indent=2, ensure_ascii=False)


EXPORTERS = {
    "plain": export_plain,
    "markdown": export_markdown,
    "json": export_json,
}


def list_exporters() -> list[str]:
    return sorted(EXPORTERS)


def export_card(card: dict[str, Any], fmt: str) -> tuple[str, str]:
    if fmt not in EXPORTERS:
        raise KeyError(f"Unknown export format: {fmt!r}. Known: {sorted(EXPORTERS)}")
    return EXPORTERS[fmt](card)


def _single_block(compiled: dict[str, Any]) -> str:
    parts = [compiled.get("text", "")]
    if compiled.get("negative_text"):
        parts.append("")
        parts.append(compiled["negative_text"])
    params = compiled.get("parameters") or {}
    if params:
        parts.append("")
        for key, value in params.items():
            parts.append(f"{key}: {value}")
    return "\n".join(parts)


def _shot_block(index: int, compiled: dict[str, Any]) -> str:
    header = f"## shot {index}"
    return header + "\n" + _single_block(compiled)
