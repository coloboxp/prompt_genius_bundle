"""Pattern → StructuredPrompt assembly.

Combines retrieved catalog matches into one (or many, for storyboard/keyframe)
model-neutral :class:`StructuredPrompt` instances. No model-specific behavior
lives here; that is the compiler's job.
"""

from __future__ import annotations

from typing import Any

from prompt_genius.core.adapters import Adapter
from prompt_genius.core.config import Config, VideoDefaults
from prompt_genius.core.models import (
    CatalogItem,
    Intent,
    Match,
    StructuredPrompt,
)

_IMAGE_MODES: frozenset[str] = frozenset({"static_image", "image_editing"})
_VIDEO_SINGLE_MODES: frozenset[str] = frozenset({"text_to_video", "image_to_video"})
_STORYBOARD_MODE = "storyboard"
_KEYFRAME_MODE = "keyframe"

_IMAGE_TYPES_ORDER: tuple[str, ...] = (
    "style_pattern",          # style first — biggest impact
    "composition_pattern",
    "camera_pattern",
    "lighting_pattern",
    "task_template",          # task last — only used when it scored well
    "negative_pattern",
)

_VIDEO_TYPES_ORDER: tuple[str, ...] = (
    "style_pattern",
    "shot_pattern",
    "motion_pattern",
    "camera_pattern",
    "lighting_pattern",
    "transition_pattern",
    "task_template",
    "negative_pattern",
)

_MIN_TASK_SCORE: float = 2.5  # below this, task templates are skipped


def _first(matches: dict[str, list[Match]], type_name: str) -> tuple[CatalogItem, float] | None:
    bucket = matches.get(type_name)
    if not bucket:
        return None
    head = bucket[0]
    return head.item, head.score


def _picked_items(matches: dict[str, list[Match]], order: tuple[str, ...]) -> list[CatalogItem]:
    seen: set[str] = set()
    picked: list[CatalogItem] = []
    for type_name in order:
        head = _first(matches, type_name)
        if not head:
            continue
        item, score = head
        # task_template is opt-in: only include it if it's clearly relevant.
        if type_name == "task_template" and score < _MIN_TASK_SCORE:
            continue
        if item.id in seen:
            continue
        picked.append(item)
        seen.add(item.id)
    return picked


def _collect_negative_fragments(
    intent: Intent, matches: dict[str, list[Match]]
) -> list[str]:
    fragments = [m.item.prompt_fragments.get("generic", "")
                 for m in matches.get("negative_pattern", [])
                 if m.item.prompt_fragments.get("generic")]
    if intent.avoid:
        fragments.append("avoid: " + ", ".join(intent.avoid))
    return fragments


def _creative_intent(intent: Intent) -> dict[str, Any]:
    return {
        "subject": intent.subject,
        "audience": intent.audience,
        "mood": list(intent.mood),
        "style": list(intent.style_hints),
        "format": list(intent.format_hints),
        "avoid": list(intent.avoid),
    }


def _why(items: list[CatalogItem], extra: str | None = None) -> str:
    parts = [
        f"{item.name} ({item.id}) — {item.description.split('.')[0]}"
        for item in items
        if item
    ]
    if extra:
        parts.append(extra)
    return " | ".join(parts) if parts else "model-neutral defaults applied"


_INFO_ONLY_PARAM_KEYS: frozenset[str] = frozenset(
    {"shot_role", "duration_hint_seconds", "transition"}
)


def _visual_parameters(items: list[CatalogItem], intent: Intent) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for item in items:
        if item.type in {"camera_pattern", "lighting_pattern", "composition_pattern", "style_pattern"}:
            for key, value in item.parameters.items():
                if key in _INFO_ONLY_PARAM_KEYS:
                    continue
                params.setdefault(key, value)
    if intent.format_hints:
        params.setdefault("aspect_ratio_hint", intent.format_hints[0])
    return params


def _video_parameters(
    items: list[CatalogItem],
    intent: Intent,
    *,
    duration_seconds: float,
    shot_count: int | None = None,
    video_defaults: VideoDefaults | None = None,
) -> dict[str, Any]:
    defaults = video_defaults or VideoDefaults()
    params: dict[str, Any] = {
        "duration_seconds": duration_seconds,
        "aspect_ratio": intent.format_hints[0] if intent.format_hints else defaults.default_aspect_ratio,
    }
    for item in items:
        if item.type in {"motion_pattern", "shot_pattern", "transition_pattern"}:
            for key, value in item.parameters.items():
                if key in _INFO_ONLY_PARAM_KEYS:
                    continue
                params.setdefault(key, value)
    params.setdefault("camera_motion", defaults.default_camera_motion)
    params.setdefault("subject_motion", defaults.default_subject_motion)
    params.setdefault("pacing", defaults.default_pacing)
    params.setdefault("continuity", list(defaults.default_continuity))
    params["artifact_avoidance"] = list(defaults.artifact_avoidance)
    if shot_count is not None:
        params["shot_count"] = shot_count
    return params


def _default_duration(intent: Intent, defaults: VideoDefaults) -> float:
    for hint in intent.format_hints + intent.mood + intent.style_hints:
        if hint.endswith("s") and hint[:-1].isdigit():
            return float(hint[:-1])
    return defaults.single_shot_duration_seconds


def _make_single(
    intent: Intent,
    matches: dict[str, list[Match]],
    adapter: Adapter,
    mode: str,
    *,
    video_defaults: VideoDefaults,
) -> StructuredPrompt:
    if mode in _IMAGE_MODES:
        order = _IMAGE_TYPES_ORDER
    else:
        order = _VIDEO_TYPES_ORDER
    picked = _picked_items(matches, order)
    return StructuredPrompt(
        mode=mode,
        target_model=adapter.model_id,
        creative_intent=_creative_intent(intent),
        selected_patterns=[item.id for item in picked],
        why_this_works=_why(picked),
        negative_fragments=_collect_negative_fragments(intent, matches),
        visual_parameters=_visual_parameters(picked, intent) if mode in _IMAGE_MODES else None,
        video_parameters=(
            _video_parameters(
                picked,
                intent,
                duration_seconds=_default_duration(intent, video_defaults),
                video_defaults=video_defaults,
            )
            if mode in _VIDEO_SINGLE_MODES
            else None
        ),
    )


_SHOT_ROLE_HINTS: tuple[tuple[str, str], ...] = (
    ("opening", "calm opening, slow establishing pace, sets tone and subject"),
    ("detail", "tight close-up detail, stable framing"),
    ("reveal", "pull-back reveal, expose subject in context"),
    ("closing", "closing brand frame, stable composition for copy and logo"),
)


def _make_storyboard(
    intent: Intent,
    matches: dict[str, list[Match]],
    adapter: Adapter,
    *,
    shot_count: int = 4,
    total_duration: float = 15.0,
    per_shot_matches: list[dict[str, list[Match]]] | None = None,
    video_defaults: VideoDefaults | None = None,
) -> list[StructuredPrompt]:
    """Build a storyboard with per-shot distinct retrieval.

    ``per_shot_matches`` is optional and supplied by the caller (e.g.
    :func:`prompt_genius.core.generate.generate_cards`) when it has re-run
    :func:`search` for each shot's role-tinted intent. When absent, falls back
    to the round-robin behaviour from the global ``matches`` argument.
    """

    defaults = video_defaults or VideoDefaults()
    common_picks = _picked_items(matches, _VIDEO_TYPES_ORDER)
    per_shot_duration = round(total_duration / shot_count, 2)

    shot_items_default = [m.item for m in matches.get("shot_pattern", [])][:shot_count]
    while len(shot_items_default) < shot_count:
        shot_items_default.append(None)  # type: ignore[arg-type]

    out: list[StructuredPrompt] = []
    for index in range(shot_count):
        shot_index = index + 1
        if per_shot_matches and index < len(per_shot_matches):
            shot_matches = per_shot_matches[index]
            picks = _picked_items(shot_matches, _VIDEO_TYPES_ORDER)
        else:
            shot_default = shot_items_default[index]
            picks = ([shot_default] if shot_default else []) + [
                i for i in common_picks if i.type != "shot_pattern"
            ]
        negatives = _collect_negative_fragments(intent, per_shot_matches[index] if per_shot_matches and index < len(per_shot_matches) else matches)
        out.append(
            StructuredPrompt(
                mode=_STORYBOARD_MODE,
                target_model=adapter.model_id,
                creative_intent=_creative_intent(intent),
                selected_patterns=[item.id for item in picks if item],
                why_this_works=_why(picks, f"shot {shot_index} of {shot_count}"),
                negative_fragments=negatives,
                visual_parameters=None,
                video_parameters=_video_parameters(
                    picks, intent,
                    duration_seconds=per_shot_duration,
                    shot_count=1,
                    video_defaults=defaults,
                ),
                shot_number=shot_index,
                duration_seconds=per_shot_duration,
            )
        )
    return out


def shot_role_hints() -> tuple[tuple[str, str], ...]:
    """Return the ordered (role, retrieval hint) pairs used to vary shots."""

    return _SHOT_ROLE_HINTS


_FRAME_ROLE_HINT: dict[str, str] = {
    "start": "establishing frame: subject just entering, calm, full-context view",
    "keyframe": "midpoint frame: motion at its peak, subject foregrounded",
    "end": "resolution frame: subject settled, brand-safe negative space",
}


def _make_keyframes(
    intent: Intent,
    matches: dict[str, list[Match]],
    adapter: Adapter,
    *,
    keyframe_count: int = 3,
    total_duration: float = 6.0,
    video_defaults: VideoDefaults | None = None,
) -> list[StructuredPrompt]:
    defaults = video_defaults or VideoDefaults()
    roles = ["start", "keyframe", "end"]
    if keyframe_count > 3:
        roles = ["start"] + ["keyframe"] * (keyframe_count - 2) + ["end"]
    elif keyframe_count == 2:
        roles = ["start", "end"]

    picks = _picked_items(matches, _VIDEO_TYPES_ORDER)
    per_frame_duration = round(total_duration / keyframe_count, 2)

    out: list[StructuredPrompt] = []
    for index, role in enumerate(roles, start=1):
        patterns = [item.id for item in picks]
        # Inject the role hint as an inline LLM-style fragment so each frame reads differently.
        patterns.append(f"llm:{_FRAME_ROLE_HINT.get(role, role)}")
        out.append(
            StructuredPrompt(
                mode=_KEYFRAME_MODE,
                target_model=adapter.model_id,
                creative_intent=_creative_intent(intent),
                selected_patterns=patterns,
                why_this_works=_why(picks, f"frame {index}/{keyframe_count} ({role})"),
                negative_fragments=_collect_negative_fragments(intent, matches),
                visual_parameters=None,
                video_parameters=_video_parameters(
                    picks, intent,
                    duration_seconds=per_frame_duration,
                    shot_count=1,
                    video_defaults=defaults,
                ),
                frame_role=role,
                duration_seconds=per_frame_duration,
            )
        )
    return out


def assemble(
    intent: Intent,
    matches: dict[str, list[Match]],
    adapter: Adapter,
    mode: str,
    *,
    shot_count: int | None = None,
    keyframe_count: int | None = None,
    total_duration: float | None = None,
    per_shot_matches: list[dict[str, list[Match]]] | None = None,
    config: Config | None = None,
) -> StructuredPrompt | list[StructuredPrompt]:
    """Assemble matches into a StructuredPrompt for the given mode."""

    cfg = config or Config.default()
    defaults = cfg.video
    resolved_shot_count = shot_count or defaults.default_shot_count
    resolved_keyframe_count = keyframe_count or defaults.default_keyframe_count

    if mode == _STORYBOARD_MODE:
        return _make_storyboard(
            intent, matches, adapter,
            shot_count=resolved_shot_count,
            total_duration=total_duration or defaults.storyboard_total_duration_seconds,
            per_shot_matches=per_shot_matches,
            video_defaults=defaults,
        )
    if mode == _KEYFRAME_MODE:
        return _make_keyframes(
            intent, matches, adapter,
            keyframe_count=resolved_keyframe_count,
            total_duration=total_duration or defaults.keyframe_total_duration_seconds,
            video_defaults=defaults,
        )
    return _make_single(intent, matches, adapter, mode, video_defaults=defaults)
