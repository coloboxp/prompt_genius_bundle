# Data model

The three dataclasses every part of Prompt Genius passes around. Defined in
`prompt_genius/core/models.py`.

## `Intent`

What the brief was *about*, after parsing.

| Field | Type | Notes |
|-------|------|-------|
| `raw_brief` | str | Verbatim brief text. |
| `subject` | str \| None | Detected primary subject. |
| `audience` | str \| None | Detected audience cue. |
| `mood` | list[str] | Mood / tone words. |
| `style_hints` | list[str] | Style descriptors. |
| `avoid` | list[str] | Phrases to keep out — go to negative prompt. |
| `format_hints` | list[str] | Layout / aspect / framing cues. |

`Intent` is built by the brief parser (heuristic or LLM-based) and consumed
by retrieval to score catalog patterns.

## `StructuredPrompt`

The model-neutral creative object produced by the assembler. One per card,
or one *per shot* in storyboard / keyframe modes.

| Field | Type | Notes |
|-------|------|-------|
| `mode` | str | `static_image` / `text_to_video` / `storyboard` / … |
| `target_model` | str | Adapter id this prompt will compile for. |
| `creative_intent` | dict | The full Intent payload as JSON. |
| `selected_patterns` | list[str] | Catalog item ids that fed this card. |
| `why_this_works` | str | One-paragraph rationale from the proposer. |
| `negative_fragments` | list[str] | Things to exclude — fed to negative prompt. |
| `visual_parameters` | dict \| None | Image-side knobs (lens, aspect, …). |
| `video_parameters` | dict \| None | Video-side knobs (camera/subject motion, …). |
| `shot_number` | int \| None | 1-indexed shot in storyboard. |
| `duration_seconds` | float \| None | Per-shot duration if applicable. |
| `frame_role` | str \| None | `start` / `mid` / `end` for keyframe mode. |

## `CompiledPrompt`

The end-of-line result for a single target model. **No `warnings` field is
ever serialised** — they're diagnostic only and live as a programmatic
attribute.

| Field | Type | Notes |
|-------|------|-------|
| `text` | str | The string to feed the model. |
| `negative_text` | str | The negative prompt, formatted per adapter convention. |
| `parameters` | dict | Adapter-filtered parameters. |

## `PromptCard`

The top-level object exposed by `generate_cards`. The GUI's middle panel
lists one of these per row.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | Stable card id (used by feedback / history join). |
| `title` | str | Short label. |
| `mode` | str | See `StructuredPrompt`. |
| `target_model` | str | Adapter id. |
| `structured` | `StructuredPrompt` or list | Per-shot list in storyboard / keyframe. |
| `compiled` | `CompiledPrompt` or list | Mirrors `structured`. |
| `why_this_works` | str | Top-level rationale (mirrors structured's). |
| `selected_patterns` | list[str] | Catalog ids used across the card. |
| `risk_level` | str | `safe` / `creative` / `experimental`. |
| `created_at` | str | ISO 8601 timestamp. |

## Why warnings are dropped from JSON

Warnings (adapter-stub notices, dropped parameters, unsupported modes) are
useful when you're holding the dataclass in code — they tell you something
broken without raising. They're noise once the JSON is fed to a model. The
GUI surfaces relevant warnings in the status bar; programmatic callers can
read `card.warnings` directly.
