# Claude CLI task: prompt assembler prototype

Build a small prototype that assembles prompt cards from normalized catalog items in `catalog/`.

## Goal

Given a user brief and a mode, return N prompt cards compiled for whichever target adapter the user picks. Default to the `generic` adapter if no target is specified — never default to a specific commercial model.

## Inputs

- User brief (free text)
- Mode: `static_image`, `image_editing`, `text_to_video`, `image_to_video`, `storyboard`, or `keyframe`
- Target model: any `model_id` present in `examples/adapters/*.json` (e.g. `generic`, `nano_banana_pro`, `firefly`, `chatgpt_image`, `midjourney`, `seedance_2_0`, `runway`). Default `generic`.
- Optional brand profile (`templates/brand-profile-template.json`)
- Number of options (default 5)
- Risk level: `safe`, `creative`, `experimental`

## Steps

1. Parse the user brief into structured intent (subject, mood, audience, avoid list, format).
2. Load the chosen adapter from `examples/adapters/<model_id>_adapter.json`. Reject mode/target combinations the adapter does not support (e.g. `text_to_video` on an image-only adapter).
3. Search catalog items by tags, keywords, and `applies_to`.
4. Select a diverse set of patterns (no two cards built from identical style+camera+lighting triple).
5. Combine patterns into a structured prompt object validated against `schemas/generated-prompt.schema.json` (or `schemas/video-prompt.schema.json` / `schemas/storyboard.schema.json` for video / storyboard modes).
6. Compile prompt text using **only** the chosen adapter:
   - Take the `prompt_fragments.<model_id>` value if the catalog item defines one.
   - Otherwise fall back to `prompt_fragments.generic` and reshape it according to the adapter's `prompt_style` and `negative_prompt_behavior`.
   - Drop any parameter the adapter marks `supported: false` (do not silently keep it).
7. Validate output JSON.
8. Return prompt cards.

## Rules

- Never default to a specific commercial model. The default target is `generic`.
- Do not invent unsupported settings — only emit fields whitelisted in the chosen adapter.
- Do not use `deprecated` or `archived` catalog items unless explicitly allowed.
- Do not use adapters marked `adapter_status: stub_unverified` in production output without a clear UI warning.
- Include selected pattern IDs (`selected_patterns`) in each output.
- Include a short `why_this_works` explanation referencing each pattern.
- Include a negative prompt when available.
- For video modes, always include `duration`, `camera_motion`, `subject_motion`, `pacing`, `continuity`, and `artifact_avoidance` — but format them per the adapter (e.g. Seedance uses `（0-Xs）`, Runway uses start/end frame fields, generic uses plain `duration: Xs` syntax).
- For storyboard or keyframe modes, emit one prompt object per shot/frame with its own continuity rules to the previous shot/frame.
