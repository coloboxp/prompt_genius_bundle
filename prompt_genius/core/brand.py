"""Brand profile loading + intent enrichment.

A brand profile contributes ``prefer`` tokens (boost) and ``avoid`` tokens
(negative) to an :class:`Intent`. Pure functions; no I/O outside the loader.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from prompt_genius.core.models import Intent


@dataclass(slots=True)
class BrandProfile:
    """Minimal brand profile contract used by search + assembler."""

    id: str
    name: str
    tone: list[str] = field(default_factory=list)
    visual_style: list[str] = field(default_factory=list)
    color_palette: list[str] = field(default_factory=list)
    prefer: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    video_rules: list[str] = field(default_factory=list)
    status: str = "draft"
    version: str = "0.1"

    @classmethod
    def from_dict(cls, data: dict) -> "BrandProfile":
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            tone=list(data.get("tone") or []),
            visual_style=list(data.get("visual_style") or []),
            color_palette=list(data.get("color_palette") or []),
            prefer=list(data.get("prefer") or []),
            avoid=list(data.get("avoid") or []),
            video_rules=list(data.get("video_rules") or []),
            status=data.get("status", "draft"),
            version=str(data.get("version", "0.1")),
        )

    def boost_terms(self) -> list[str]:
        return [*self.tone, *self.visual_style, *self.prefer]


def load_brand_profile(path: str | Path) -> BrandProfile:
    with Path(path).open(encoding="utf-8") as handle:
        return BrandProfile.from_dict(json.load(handle))


def brand_fit_score(card_dict: dict, brand: BrandProfile | None) -> float:
    """Heuristic 0..1 score of how well a generated card matches a brand profile.

    Token-overlap based: count brand prefer/tone/style tokens that appear in
    the compiled prompt text, minus brand avoid tokens that appear.
    """

    if brand is None:
        return 0.5

    compiled = card_dict.get("compiled")
    if isinstance(compiled, list):
        text = " ".join((c or {}).get("text", "") for c in compiled).lower()
    else:
        text = ((compiled or {}).get("text") or "").lower()
    if not text:
        return 0.0

    boost = sum(1 for term in brand.boost_terms() if term.lower() in text)
    penalty = sum(1 for term in brand.avoid if term.lower() in text)
    raw = boost - 2 * penalty
    max_possible = max(len(brand.boost_terms()), 1)
    return max(0.0, min(1.0, round((raw + max_possible) / (2 * max_possible), 3)))


def apply_brand(intent: Intent, brand: BrandProfile | None) -> Intent:
    """Return a new :class:`Intent` augmented with brand prefers and avoids."""

    if brand is None:
        return intent
    extra_mood = [m for m in brand.tone if m not in intent.mood]
    extra_style = [s for s in brand.visual_style if s not in intent.style_hints]
    extra_avoid = [a for a in brand.avoid if a not in intent.avoid]
    return Intent(
        raw_brief=intent.raw_brief,
        subject=intent.subject,
        audience=intent.audience,
        mood=[*intent.mood, *extra_mood],
        style_hints=[*intent.style_hints, *extra_style],
        avoid=[*intent.avoid, *extra_avoid],
        format_hints=list(intent.format_hints),
    )
