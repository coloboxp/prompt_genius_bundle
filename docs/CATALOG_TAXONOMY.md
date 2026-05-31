# Catalog Taxonomy

## Purpose

The catalog is the hidden intelligence behind Prompt Genius. It should contain reusable prompt patterns, not only full prompts.

A full prompt can be stored, but the most valuable assets are smaller building blocks that can be assembled, adapted, and fine-tuned.

## Catalog item types

| Type | Purpose |
|---|---|
| `style_pattern` | Visual style, mood, art direction |
| `camera_pattern` | Lens, angle, framing, depth of field |
| `lighting_pattern` | Studio light, natural light, dramatic light |
| `composition_pattern` | Centered, rule of thirds, hero layout, close-up |
| `motion_pattern` | Push-in, orbit, pan, tilt, handheld, static |
| `shot_pattern` | Opening shot, detail shot, reveal shot, closing shot |
| `transition_pattern` | Cut, fade, match cut, morph, camera move |
| `negative_pattern` | What to avoid |
| `brand_pattern` | Internal brand rules |
| `model_setting` | Model-specific flags and parameters |
| `task_template` | Hero image, campaign video, social ad, UI mockup |
| `prompt_example` | Full working prompt example |
| `evaluation_rubric` | Scoring rules |
| `adapter_rule` | How to convert neutral prompt to target model |

## Required fields for every catalog item

| Field | Purpose |
|---|---|
| `id` | Stable unique identifier |
| `type` | Pattern type |
| `category` | More specific grouping |
| `name` | Human-readable name |
| `description` | When and why to use it |
| `applies_to` | Modes or tasks where it fits |
| `not_recommended_for` | Modes or tasks where it should be avoided |
| `prompt_fragments` | Model-specific fragments |
| `parameters` | Structured parameter values |
| `compatible_with` | Styles or concepts that pair well |
| `avoid_with` | Styles or concepts that conflict |
| `tags` | Search and retrieval tags |
| `quality_score` | Curated or feedback-based score |
| `status` | active, draft, deprecated, archived |
| `version` | Item version |

## Example categories

### Static image categories

- Style
- Camera
- Lens
- Lighting
- Composition
- Color
- Material
- Subject
- Environment
- Realism
- Negative prompt
- Aspect ratio
- Brand safety

### Video categories

- Duration
- Shot count
- Camera motion
- Subject motion
- Lighting motion
- Transition
- Pacing
- Continuity
- Start frame
- End frame
- Artifact avoidance
- Motion intensity

## Good catalog item rules

A good catalog item should:

- Be specific enough to be useful.
- Say when to use it.
- Say when not to use it.
- Include tags.
- Include model-specific prompt fragments where useful.
- Include structured parameters.
- Avoid vague labels like nice, cool, modern without context.
- Avoid duplicate meaning under different names.
- Have a quality score.
- Have a status.

## Bad catalog item examples

Bad:

```json
{
  "prompt": "Make it beautiful and modern"
}
```

Better:

```json
{
  "id": "style_premium_enterprise_clean_001",
  "type": "style_pattern",
  "category": "enterprise_brand_style",
  "name": "Premium clean enterprise style",
  "description": "Useful for B2B SaaS, product launches, enterprise trust, security, and identity products.",
  "applies_to": ["static_image", "text_to_video", "image_to_video", "campaign_visual"],
  "not_recommended_for": ["playful_children_brand", "gaming_campaign", "experimental_art"],
  "prompt_fragments": {
    "generic": "premium enterprise visual style, clean layout, calm trust-focused mood, refined details, modern B2B aesthetic"
  },
  "tags": ["premium", "enterprise", "b2b", "trust", "clean"],
  "quality_score": 0.86,
  "status": "active",
  "version": "1.0"
}
```

## Active catalog versus raw corpus

Keep two layers:

```text
raw_corpus/
  all old prompts, notes, experiments, messy data

catalog/
  curated, normalized, validated, active patterns
```

The raw corpus can contain thousands of prompts. The active catalog should start smaller and cleaner.

Recommended MVP active catalog size:

```text
100 to 300 high-quality items
```

## Quality score guidance

| Score | Meaning |
|---|---|
| 0.90 to 1.00 | Excellent, proven, reusable |
| 0.75 to 0.89 | Good, active |
| 0.50 to 0.74 | Usable but needs review |
| 0.25 to 0.49 | Weak, avoid unless needed |
| 0.00 to 0.24 | Deprecated or bad |

## Status values

| Status | Meaning |
|---|---|
| `draft` | New or unreviewed |
| `active` | Approved for retrieval |
| `deprecated` | Keep for history, do not use by default |
| `archived` | Old, hidden from normal search |

## Model-specific fragments

**`generic` is always required and is the default.** It must read as a clean, model-neutral instruction that any major image or video model can consume. The system uses `generic` unless the user explicitly picks a specific adapter.

Model-specific fragments under `prompt_fragments.<adapter_id>` are **optional refinements**, not defaults. Only add a per-model fragment when the corpus or adapter docs show the model needs different phrasing or grammar — for example, Seedance shot-timing markers `（0-Xs）`, Midjourney `--ar`/`--no` flags, Firefly style-reference grammar.

Never include a per-model fragment that just paraphrases the generic one. That bakes in unverified bias.

Example (only Seedance differs from generic; everything else relies on `generic`):

```json
{
  "prompt_fragments": {
    "generic": "slow camera push-in, calm premium motion, stable subject",
    "seedance_2_0": "slow push-in camera movement, preserve layout, subtle light motion, no warping, （0-6秒）"
  }
}
```

If no per-model fragment exists for the user's chosen adapter, the compiler falls back to `generic` + the adapter's prompt-style rules.

## Compatibility and conflict logic

Use `compatible_with` and `avoid_with` to prevent bad combinations.

Example:

- Macro lens is compatible with product detail.
- Macro lens is not recommended for wide environment scene.
- Cyberpunk negative prompt is compatible with enterprise trust.
- Dramatic neon lighting may conflict with brand-safe enterprise visuals.
