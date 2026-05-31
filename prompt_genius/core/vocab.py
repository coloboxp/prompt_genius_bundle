"""Per-category vocabulary mined from the raw corpus.

Designers want the GUI's combo boxes (lens, lighting, camera motion, pacing,
etc) to show real options taken from prompts that worked — not a hand-rolled
list of 6 fallbacks. This module scans every ``content`` string in the corpus
once, extracts category-tagged phrases by regex, counts their occurrences, and
returns the top-N per category.

The result is cached to ``.cache/vocab/<hash>.json`` so the scan only runs when
the corpus changes.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from prompt_genius.core.corpus import CorpusRow, iter_rows


# ----------------------------------------------------------- category patterns
#
# Each entry: (compiled_regex, post_processor)
# - regex captures the candidate phrase in group 1 OR uses the full match
# - post_processor lowercases / normalizes whitespace; returning "" drops it
#
# Patterns are intentionally tolerant. We're optimizing for recall;
# duplicates and near-misses are deduped by case-folded text after extraction.


def _norm(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip().lower()
    if len(text) > 60 or len(text) < 2:
        return ""
    return text


_LENS_TERMS = (
    r"(?:14mm|16mm|18mm|20mm|24mm|28mm|35mm|40mm|50mm|55mm|70mm|85mm|"
    r"100mm|105mm|135mm|180mm|200mm|300mm|400mm|600mm|800mm|"
    r"macro|tilt[- ]shift|anamorphic|fish[- ]?eye|telephoto|wide[- ]angle|"
    r"portrait lens|prime lens|zoom lens|cinema lens|panavision|leica [a-z0-9]+|"
    r"canon eos [a-z0-9]+(?: ii| iii)?|nikon z[0-9]+|sony [aαa][0-9]+)"
)
_LENS_RE = re.compile(rf"\b({_LENS_TERMS})\b", re.IGNORECASE)


_LIGHTING_TERMS = (
    r"(?:soft studio lighting|hard studio lighting|softbox|beauty dish|"
    r"key light|rim light|kicker|fill light|backlight|backlit|side light|"
    r"top light|natural (?:window )?light|window light|"
    r"golden hour|blue hour|magic hour|sunset light|sunrise light|midday sun|"
    r"overcast|cloudy|hazy|foggy|misty|"
    r"dramatic (?:low[- ]key |chiaroscuro )?lighting|low[- ]key lighting|"
    r"high[- ]key lighting|chiaroscuro|noir lighting|"
    r"neon (?:lighting|glow|signs?)|candle ?light|fluorescent|tungsten|"
    r"practical lights?|street lights?|moonlight|firelight|stage lights?|"
    r"volumetric (?:light|fog)|god rays|lens flare|bloom|haze|"
    r"hard shadows?|soft shadows?|long shadows?|harsh light|diffused light)"
)
_LIGHTING_RE = re.compile(rf"\b({_LIGHTING_TERMS})\b", re.IGNORECASE)


_CAMERA_MOTION_TERMS = (
    r"(?:push[- ]in|pull[- ]back|pull[- ]out|dolly (?:in|out|left|right|forward|back)|"
    r"track(?:ing)? (?:left|right|forward|in|out)?|crane (?:up|down|shot)?|"
    r"orbit(?:ing)?|whip[- ]pan|pan (?:left|right)?|tilt (?:up|down)?|"
    r"handheld|shoulder mounted|gimbal|steadicam|locked[- ]off|static (?:camera|shot)?|"
    r"slow zoom|fast zoom|smooth zoom|rack focus|focus pull|"
    r"hyperlapse|timelapse|aerial|drone (?:shot|footage)?|fly[- ]?through|"
    r"first[- ]person|pov)"
)
_CAMERA_MOTION_RE = re.compile(rf"\b({_CAMERA_MOTION_TERMS})\b", re.IGNORECASE)


_PACING_TERMS = (
    r"(?:calm pacing|slow pacing|medium pacing|fast pacing|frenetic pacing|"
    r"dramatic pacing|energetic pacing|brisk pacing|languid pacing|"
    r"snappy cuts|long takes?|cinematic pacing)"
)
_PACING_RE = re.compile(rf"\b({_PACING_TERMS})\b", re.IGNORECASE)


_FRAMING_TERMS = (
    r"(?:extreme close[- ]up|close[- ]up|medium close[- ]up|medium shot|"
    r"medium wide|wide shot|extreme wide|full shot|cowboy shot|"
    r"over[- ]the[- ]shoulder|two[- ]shot|three[- ]shot|profile shot|"
    r"birds?[- ]eye view|worms?[- ]eye view|low angle|high angle|"
    r"dutch angle|eye level|top[- ]down|aerial view)"
)
_FRAMING_RE = re.compile(rf"\b({_FRAMING_TERMS})\b", re.IGNORECASE)


_STYLE_TERMS = (
    r"(?:cinematic|editorial|documentary|fashion|lifestyle|hyper[- ]realistic|"
    r"photorealistic|surreal|impressionist|expressionist|cubist|art deco|"
    r"minimal(?:ist)?|maximal(?:ist)?|baroque|vintage film|noir|cyberpunk|"
    r"steampunk|solarpunk|biopunk|art nouveau|bauhaus|brutalist|cottagecore|"
    r"y2k|vaporwave|synthwave|retrofuturist|anime|manga|studio ghibli|"
    r"makoto shinkai|wes anderson|david fincher|wong kar[- ]wai|"
    r"renaissance painting|oil painting|watercolor|ink wash|woodblock|"
    r"isometric|pixel art|low[- ]poly|claymation|stop[- ]motion)"
)
_STYLE_RE = re.compile(rf"\b({_STYLE_TERMS})\b", re.IGNORECASE)


_COLOR_TERMS = (
    r"(?:teal and orange|monochrome|sepia|black and white|grayscale|"
    r"warm tones?|cool tones?|pastel palette|muted palette|vivid palette|"
    r"high saturation|desaturated|complementary colors?|analogous colors?|"
    r"gold(?:en)? tones?|silver tones?|copper tones?|bronze tones?|"
    r"earth tones?|jewel tones?|neon palette|cinematic color grade)"
)
_COLOR_RE = re.compile(rf"\b({_COLOR_TERMS})\b", re.IGNORECASE)


_MOOD_TERMS = (
    r"(?:trustworthy|premium|luxurious|elegant|sophisticated|edgy|gritty|"
    r"dreamy|ethereal|moody|atmospheric|nostalgic|melancholic|hopeful|"
    r"playful|whimsical|serious|contemplative|intimate|grand|epic|"
    r"calm|serene|peaceful|tense|chaotic|energetic|vibrant|sleek|"
    r"raw|polished|refined|gritty|cinematic|cozy|stark|brutal)"
)
_MOOD_RE = re.compile(rf"\b({_MOOD_TERMS})\b", re.IGNORECASE)


_PATTERNS: dict[str, re.Pattern[str]] = {
    "lens": _LENS_RE,
    "lighting": _LIGHTING_RE,
    "camera_motion": _CAMERA_MOTION_RE,
    "pacing": _PACING_RE,
    "framing": _FRAMING_RE,
    "style": _STYLE_RE,
    "color_palette": _COLOR_RE,
    "mood": _MOOD_RE,
}


# ----------------------------------------------------------- result type


@dataclass(slots=True)
class CorpusVocab:
    """{category: [(value, count), ...]} sorted by descending count."""

    by_category: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    sample_size: int = 0

    def top(self, category: str, n: int = 30) -> list[str]:
        return [value for value, _ in self.by_category.get(category, [])[:n]]

    def to_dict(self) -> dict:
        return {
            "sample_size": self.sample_size,
            "by_category": {
                cat: [list(pair) for pair in pairs]
                for cat, pairs in self.by_category.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CorpusVocab":
        return cls(
            by_category={
                cat: [tuple(pair) for pair in pairs]
                for cat, pairs in data.get("by_category", {}).items()
            },
            sample_size=int(data.get("sample_size", 0)),
        )


# ----------------------------------------------------------- extractor


def extract_vocab(
    rows: Iterable[CorpusRow],
    *,
    patterns: dict[str, re.Pattern[str]] | None = None,
) -> CorpusVocab:
    """Sweep every row's content with each category regex; tally counts."""

    patterns = patterns or _PATTERNS
    counters: dict[str, Counter[str]] = {cat: Counter() for cat in patterns}
    count = 0
    for row in rows:
        text = row.content or ""
        if not text:
            continue
        count += 1
        for category, regex in patterns.items():
            for match in regex.finditer(text):
                phrase = _norm(match.group(1) if match.groups() else match.group(0))
                if phrase:
                    counters[category][phrase] += 1
    by_category = {
        cat: counter.most_common() for cat, counter in counters.items() if counter
    }
    return CorpusVocab(by_category=by_category, sample_size=count)


# ----------------------------------------------------------- disk cache


def _corpus_signature(corpus_dir: Path) -> str:
    parts: list[str] = []
    if not corpus_dir.exists():
        return "missing"
    for path in sorted(corpus_dir.glob("*.csv")):
        stat = path.stat()
        parts.append(f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}")
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:16]


def load_or_build_vocab(
    corpus_dir: str | Path,
    cache_dir: str | Path = ".cache/vocab",
    *,
    rebuild: bool = False,
) -> CorpusVocab:
    """Return a :class:`CorpusVocab`, building and caching on first call."""

    corpus_root = Path(corpus_dir)
    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    signature = _corpus_signature(corpus_root)
    cache_path = cache_root / f"corpus_vocab-{signature}.json"
    if cache_path.exists() and not rebuild:
        try:
            return CorpusVocab.from_dict(json.loads(cache_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError, KeyError):
            pass
    vocab = extract_vocab(iter_rows(corpus_root))
    try:
        cache_path.write_text(
            json.dumps(vocab.to_dict(), ensure_ascii=False), encoding="utf-8",
        )
    except OSError:
        pass
    return vocab


def merge_vocab_lists(
    catalog_vocab: dict[str, list[str]],
    corpus_vocab: CorpusVocab,
    *,
    per_category_cap: int = 40,
) -> dict[str, list[str]]:
    """Merge catalog + corpus vocabularies, capping length per category."""

    out: dict[str, list[str]] = {}
    keys = set(catalog_vocab) | set(corpus_vocab.by_category)
    for key in keys:
        seen: dict[str, None] = {}
        for value in (catalog_vocab.get(key) or []):
            if value and value.lower() not in seen:
                seen[value.lower()] = None
                seen[value] = None  # preserve original casing dedupe
        for value in corpus_vocab.top(key, per_category_cap * 2):
            lower = value.lower()
            if lower in seen:
                continue
            seen[lower] = None
        # Reconstruct preserving insertion order, drop the lower-case helper keys
        merged: list[str] = []
        for value in catalog_vocab.get(key, []):
            if value not in merged:
                merged.append(value)
        for value in corpus_vocab.top(key, per_category_cap * 2):
            if value not in merged and value.lower() not in {m.lower() for m in merged}:
                merged.append(value)
        out[key] = merged[:per_category_cap]
    return out
