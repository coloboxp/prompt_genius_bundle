"""Adapter-driven prompt compilation.

Reduces a model-neutral :class:`StructuredPrompt` to text + parameters that
respect the chosen adapter's whitelist. No model-specific code lives here;
behavior is driven entirely by adapter JSON.
"""

from __future__ import annotations

from typing import Any

from prompt_genius.core.adapters import Adapter
from prompt_genius.core.catalog import Catalog
from prompt_genius.core.models import (
    CatalogItem,
    CompiledPrompt,
    StructuredPrompt,
    Warning,
)

_DEFAULT_NEG_BEHAVIOR = "append_avoid_sentence"


def _fragment_for(item: CatalogItem, adapter_id: str) -> str:
    """Return the per-adapter fragment if present, else the generic fragment."""

    fragments = item.prompt_fragments
    if adapter_id in fragments:
        return fragments[adapter_id]
    return fragments.get("generic", "")


def _fragments(
    structured: StructuredPrompt, catalog: Catalog, adapter: Adapter
) -> list[str]:
    fragments: list[str] = []
    for item_id in structured.selected_patterns:
        # LLM-proposed inline fragments are stored as "llm:<text>".
        if item_id.startswith("llm:"):
            fragments.append(item_id[len("llm:"):].strip())
            continue
        item = catalog.items.get(item_id)
        if not item:
            continue
        if item.type == "negative_pattern":
            # negatives are handled separately
            continue
        text = _fragment_for(item, adapter.model_id)
        if text and text.strip().lower() not in {"not applicable", "n/a"}:
            fragments.append(text.strip())
    return fragments


def _allowed_params(structured: StructuredPrompt, adapter: Adapter) -> dict[str, Any]:
    supported = adapter.supported_parameters()
    raw: dict[str, Any] = {}
    raw.update(structured.visual_parameters or {})
    raw.update(structured.video_parameters or {})
    return {key: value for key, value in raw.items() if key in supported}


def _join_prompt(fragments: list[str], style: str, params: dict[str, Any]) -> str:
    body = ""
    if style == "compact_descriptive":
        body = ", ".join(fragments)
    elif style == "shot_structured_natural_language":
        body = ". ".join(fragments)
    elif style == "conversational_natural_language":
        body = "Please generate: " + " ".join(fragments)
    elif style == "concise_descriptive":
        body = ". ".join(fragments[:3])
    elif style == "natural_language_motion":
        body = " ".join(fragments)
    elif style == "structured_natural_language":
        param_lines = "\n".join(f"{k}: {v}" for k, v in params.items())
        body = ". ".join(fragments)
        if param_lines:
            body = f"{body}\n\n{param_lines}"
    else:  # detailed_natural_language and unknown fallback
        body = ". ".join(fragments)
    return body.strip()


def _shot_timing(adapter: Adapter, structured: StructuredPrompt) -> str | None:
    duration_spec = adapter.parameters.get("duration_seconds") or {}
    shot_syntax = duration_spec.get("shot_timing_syntax")
    if not shot_syntax:
        return None
    if structured.duration_seconds is None:
        return None
    start = 0
    end = int(round(structured.duration_seconds))
    try:
        return shot_syntax.format(start=start, end=end)
    except (KeyError, IndexError):
        return None


def _format_negative(behavior: str, negatives: list[str]) -> str:
    if not negatives:
        return ""
    phrases: list[str] = []
    seen: set[str] = set()
    for fragment in negatives:
        if not fragment:
            continue
        body = fragment.strip()
        # strip leading "avoid:" / "avoid " / "no " — they're prefixes the
        # negative_pattern fragments use that would otherwise stack.
        for prefix in ("avoid:", "avoid ", "no:"):
            if body.lower().startswith(prefix):
                body = body[len(prefix):].strip()
                break
        # split into individual phrases by comma / semicolon, keep order, dedupe.
        for part in [p.strip(" .;") for p in body.split(",")]:
            part = part.strip()
            # drop any internal leading "avoid"/"no " from phrase
            for prefix in ("avoid ", "no "):
                if part.lower().startswith(prefix):
                    part = part[len(prefix):].strip()
            if not part:
                continue
            key = part.lower()
            if key in seen:
                continue
            seen.add(key)
            phrases.append(part)
    text = ", ".join(phrases)
    if behavior == "parameterized_no_flag":
        return f"--no {text}"
    if behavior == "separate_avoid_section":
        return f"avoid: {text}"
    return f"Avoid: {text}."


def compile_prompt(
    structured: StructuredPrompt,
    adapter: Adapter,
    catalog: Catalog,
) -> CompiledPrompt:
    """Compile one :class:`StructuredPrompt` for the chosen adapter."""

    warnings: list[Warning] = []

    if not adapter.supports_mode(structured.mode):
        warnings.append(
            Warning(
                code="mode_not_supported",
                message=f"Adapter {adapter.model_id!r} does not declare support for mode {structured.mode!r}.",
            )
        )

    fragments = _fragments(structured, catalog, adapter)
    params = _allowed_params(structured, adapter)
    text = _join_prompt(fragments, adapter.prompt_style, params)

    timing = _shot_timing(adapter, structured)
    if timing:
        text = f"{timing} {text}".strip()

    neg_behavior = adapter.negative_prompt_behavior or _DEFAULT_NEG_BEHAVIOR
    negative_text = _format_negative(neg_behavior, structured.negative_fragments)

    if neg_behavior == "trailing_avoid_sentence" and negative_text:
        text = f"{text}\n\n{negative_text}"
        negative_text_out = negative_text
    elif neg_behavior == "append_avoid_sentence" and negative_text:
        text = f"{text} {negative_text}".strip()
        negative_text_out = negative_text
    else:
        negative_text_out = negative_text

    dropped = set((structured.visual_parameters or {})) | set((structured.video_parameters or {}))
    dropped -= set(params.keys())
    if dropped:
        warnings.append(
            Warning(
                code="dropped_unsupported_params",
                message=(
                    f"Adapter {adapter.model_id!r} does not support parameters: "
                    f"{sorted(dropped)}. They were dropped."
                ),
            )
        )

    if adapter.adapter_status == "stub_unverified":
        warnings.append(
            Warning(
                code="adapter_stub",
                message=(
                    f"Adapter {adapter.model_id!r} is a stub. Verify against the real "
                    "model before production use."
                ),
            )
        )

    return CompiledPrompt(
        text=text,
        negative_text=negative_text_out,
        parameters=params,
        warnings=warnings,
    )
