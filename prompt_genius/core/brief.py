"""Heuristic brief parser.

Phase 1 deliberately avoids any LLM call. The parser uses keyword and regex
matching against curated vocabularies. The interface is stable: future phases
can swap in an LLM-backed parser behind the same ``parse_brief`` signature.
"""

from __future__ import annotations

import re

from prompt_genius.core.models import Intent

_MOOD_KEYWORDS = {
    "premium", "trustworthy", "trust", "calm", "clean", "minimal", "elegant",
    "playful", "energetic", "bold", "dramatic", "moody", "warm", "cool",
    "human", "humane", "friendly", "professional", "corporate", "luxurious",
    "vibrant", "subtle", "cinematic", "editorial", "documentary", "natural",
    "polished", "refined", "credible", "soft", "hard", "futuristic",
    "nostalgic", "vintage", "modern", "futuristic", "retro",
}

_STYLE_KEYWORDS = {
    "minimal", "editorial", "cinematic", "product render", "photorealistic",
    "isometric", "flat", "3d", "hand-drawn", "illustration", "watercolor",
    "neon", "noir", "cyberpunk", "sci-fi", "surreal", "studio",
    "documentary", "fashion", "lifestyle", "campaign", "hero",
}

_NEGATIVE_PATTERNS = [
    re.compile(r"\bno\s+([a-zA-Z\- ]+?)(?:[.,;]|$)"),
    re.compile(r"\bavoid\s+([a-zA-Z\- ]+?)(?:[.,;]|$)"),
    re.compile(r"\bwithout\s+([a-zA-Z\- ]+?)(?:[.,;]|$)"),
    re.compile(r"\bnot\s+([a-zA-Z\- ]+?)(?:[.,;]|$)"),
]

_FORMAT_PATTERNS = [
    re.compile(r"\b(\d{1,2}:\d{1,2})\b"),
    re.compile(r"\b(square|portrait|landscape|widescreen|vertical|horizontal)\b", re.I),
    re.compile(r"\b(linkedin|instagram|tiktok|youtube|twitter|x|story|reel)\b", re.I),
]

_AUDIENCE_PATTERNS = [
    re.compile(r"for\s+([a-zA-Z\- ]+?(?:buyers?|customers?|users?|teams?|audience|brand))", re.I),
    re.compile(r"\b(enterprise|b2b|b2c|consumer|developer|designer|marketing)\b", re.I),
]

_SUBJECT_HINT_PATTERNS = [
    re.compile(
        r"(?:create|generate|make|design|produce|animate|render|compose)\s+(?:a |an |the )?"
        r"([a-zA-Z0-9\- ]+?)(?:\s+(?:for|with|in|to|that)\b|[.,;]|$)",
        re.I,
    ),
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_matches(patterns: list[re.Pattern[str]], text: str) -> list[str]:
    found: list[str] = []
    for pat in patterns:
        for match in pat.finditer(text):
            candidate = _normalize(match.group(1)).lower()
            if candidate and candidate not in found:
                found.append(candidate)
    return found


def parse_brief(text: str) -> Intent:
    """Parse a free-text brief into a structured :class:`Intent`.

    Heuristic only. No external calls. Safe to call from a GUI thread.
    """

    raw = text or ""
    lowered = raw.lower()

    mood = [kw for kw in _MOOD_KEYWORDS if re.search(rf"\b{re.escape(kw)}\b", lowered)]
    style_hints = [kw for kw in _STYLE_KEYWORDS if re.search(rf"\b{re.escape(kw)}\b", lowered)]

    avoid = _extract_matches(_NEGATIVE_PATTERNS, raw)
    format_hints = _extract_matches(_FORMAT_PATTERNS, raw)
    audience_candidates = _extract_matches(_AUDIENCE_PATTERNS, raw)
    audience = audience_candidates[0] if audience_candidates else None

    subject_candidates = _extract_matches(_SUBJECT_HINT_PATTERNS, raw)
    subject = subject_candidates[0] if subject_candidates else None

    return Intent(
        raw_brief=raw,
        subject=subject,
        audience=audience,
        mood=mood,
        style_hints=style_hints,
        avoid=avoid,
        format_hints=format_hints,
    )
