"""Mode conversion: static prompt → video prompt.

Reuses the existing assembler so the conversion stays catalog-driven. The
static card's selected_patterns become the visual seed; video-side patterns
(motion, shot, transition) are layered on by re-searching the catalog.
"""

from __future__ import annotations

from typing import Any

from prompt_genius.core.adapters import Adapter
from prompt_genius.core.assembler import assemble
from prompt_genius.core.brief import parse_brief
from prompt_genius.core.catalog import Catalog, search
from prompt_genius.core.compiler import compile_prompt
from prompt_genius.core.models import CompiledPrompt, StructuredPrompt


def static_to_video(
    static_card: dict[str, Any],
    *,
    target_mode: str,
    adapter: Adapter,
    catalog: Catalog,
    allow_drafts: bool = True,
) -> tuple[StructuredPrompt | list[StructuredPrompt], CompiledPrompt | list[CompiledPrompt]]:
    """Convert a static card dict into a video card for ``target_mode``.

    ``target_mode`` must be one the chosen adapter supports
    (``text_to_video``, ``image_to_video``, ``storyboard``, ``keyframe``).
    """

    if not adapter.supports_mode(target_mode):
        raise ValueError(
            f"Adapter {adapter.model_id!r} does not support {target_mode!r}"
        )

    brief = static_card.get("title") or ""
    creative = (static_card.get("structured") or {}).get("creative_intent") or {}
    seed_text = " ".join(
        filter(
            None,
            [
                brief,
                creative.get("subject") or "",
                " ".join(creative.get("mood") or []),
                " ".join(creative.get("style") or []),
            ],
        )
    )
    intent = parse_brief(seed_text)

    # Preserve original avoid list explicitly.
    if creative.get("avoid"):
        intent.avoid = list({*intent.avoid, *creative["avoid"]})

    matches = search(catalog, intent, target_mode, allow_drafts=allow_drafts)
    structured = assemble(intent, matches, adapter, target_mode)
    if isinstance(structured, list):
        compiled = [compile_prompt(s, adapter, catalog) for s in structured]
    else:
        compiled = compile_prompt(structured, adapter, catalog)
    return structured, compiled
