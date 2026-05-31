"""Feedback + usage driven pattern quality scoring.

Inputs:
    - ``catalog/`` : each item carries a curator ``quality_score`` (0..1).
    - ``data/feedback.jsonl`` : append-only feedback events.
    - ``data/history/*.json`` : saved cards (maps card_id → selected_patterns).
    - ``data/usage.jsonl`` : append-only usage events (generated/selected/saved/exported).

Score (each component is a rate in 0..1, time-decayed by ~90 day half-life)::

    new = 0.45 * curator
        + 0.20 * positive_rate
        + 0.10 * save_rate
        + 0.10 * reuse_rate
        + 0.05 * export_rate
        - 0.20 * negative_rate

Clipped to ``[0, 1]``. Patterns with no signal keep their curator score.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prompt_genius.core.config import Config, QualityWeights
from prompt_genius.core.usage import read_usage

_POSITIVE_RATINGS: frozenset[str] = frozenset({"good", "excellent", "perfect"})
_NEGATIVE_RATINGS: frozenset[str] = frozenset(
    {
        "bad",
        "too_generic",
        "off_brand",
        "wrong_style",
        "wrong_model",
        "too_corporate",
        "too_busy",
        "bad_composition",
        "wrong_aspect_ratio",
        "motion_too_fast",
        "motion_too_boring",
        "video_likely_unstable",
        "missing_negative_prompt",
        "unsupported_setting",
    }
)


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
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


def _load_cards(history_dir: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    if not history_dir.exists():
        return cards
    for path in sorted(history_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        card_id = data.get("id")
        if card_id:
            cards[card_id] = data
    return cards


def _decay(weight: float, ts: str | None, now: datetime, half_life_days: float) -> float:
    if not ts:
        return weight
    try:
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return weight
    age_days = max((now - when).total_seconds() / 86400.0, 0.0)
    factor = 0.5 ** (age_days / max(half_life_days, 1.0))
    return weight * factor


def recompute_quality_scores(
    catalog_dir: str | Path,
    feedback_path: str | Path,
    history_dir: str | Path,
    *,
    usage_path: str | Path = "data/usage.jsonl",
    apply: bool = False,
    now: datetime | None = None,
    config: Config | None = None,
) -> dict[str, float]:
    """Recompute quality scores. Returns ``{pattern_id: new_score}``."""

    now = now or datetime.now(timezone.utc)
    weights: QualityWeights = (config or Config.default()).quality
    catalog_root = Path(catalog_dir)
    feedback = _iter_jsonl(Path(feedback_path))
    cards = _load_cards(Path(history_dir))
    usage = read_usage(usage_path)

    positives: dict[str, float] = defaultdict(float)
    negatives: dict[str, float] = defaultdict(float)
    impressions: dict[str, float] = defaultdict(float)

    for entry in feedback:
        rating = (entry.get("rating") or "").lower()
        card_id = entry.get("card_id")
        if not card_id:
            continue
        card = cards.get(card_id) or {}
        patterns = card.get("selected_patterns") or []
        ts = entry.get("recorded_at")
        for pid in patterns:
            impressions[pid] += _decay(1.0, ts, now, weights.half_life_days)
            if rating in _POSITIVE_RATINGS:
                positives[pid] += _decay(1.0, ts, now, weights.half_life_days)
            elif rating in _NEGATIVE_RATINGS:
                negatives[pid] += _decay(1.0, ts, now, weights.half_life_days)


    generations: dict[str, float] = defaultdict(float)
    saves: dict[str, float] = defaultdict(float)
    exports: dict[str, float] = defaultdict(float)
    selections: dict[str, float] = defaultdict(float)
    for entry in usage:
        pid = entry.get("pattern_id")
        ts = entry.get("ts")
        if not pid:
            continue
        event = entry.get("event")
        weight = _decay(1.0, ts, now, weights.half_life_days)
        if event == "generated":
            generations[pid] += weight
        elif event == "selected":
            selections[pid] += weight
        elif event == "saved":
            saves[pid] += weight
        elif event == "exported":
            exports[pid] += weight

    new_scores: dict[str, float] = {}
    for path in sorted(catalog_root.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pid = data.get("id")
        if not pid:
            continue
        curator = float(data.get("quality_score", 0.0))

        denom_feedback = impressions[pid]
        denom_usage = max(generations[pid], 1.0)

        pos_rate = positives[pid] / denom_feedback if denom_feedback else 0.0
        neg_rate = negatives[pid] / denom_feedback if denom_feedback else 0.0
        save_rate = saves[pid] / denom_usage
        export_rate = exports[pid] / denom_usage
        reuse_rate = selections[pid] / denom_usage

        total_signal = denom_feedback + generations[pid] + selections[pid] + saves[pid] + exports[pid]
        # Heavily-decayed signals are not signals — treat near-zero weight as no feedback.
        if total_signal < 0.01:
            new_scores[pid] = curator
            continue

        score = (
            weights.curator_weight * curator
            + weights.positive_rate_weight * _clip01(pos_rate)
            + weights.save_rate_weight * _clip01(save_rate)
            + weights.reuse_rate_weight * _clip01(reuse_rate)
            + weights.export_rate_weight * _clip01(export_rate)
            - weights.negative_rate_penalty * _clip01(neg_rate)
        )
        new_scores[pid] = round(max(0.0, min(1.0, score)), 3)
        if apply and new_scores[pid] != curator:
            data["quality_score"] = new_scores[pid]
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return new_scores


def _clip01(value: float) -> float:
    if math.isnan(value):
        return 0.0
    return max(0.0, min(1.0, value))


def top_and_bottom(scores: dict[str, float], *, k: int = 5) -> dict[str, list[tuple[str, float]]]:
    """Return the ``k`` highest and lowest scored pattern ids."""

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return {"top": ranked[:k], "bottom": ranked[-k:][::-1]}
