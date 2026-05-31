# Adapter schema

Adapters describe *how* to compile a `StructuredPrompt` for a specific
target model. One JSON file per model, under `examples/adapters/`. The
canonical template is `templates/model-adapter-template.json`.

## Required fields

| Field | Type | Purpose |
|-------|------|---------|
| `model_id` | str | The id surfaced in the **Target** picker. |
| `display_name` | str | Human label. |
| `supported_modes` | list[str] | Which generation modes this model supports. |
| `prompt_style` | object | How to format fragments into the final text (`join`, separators, ordering). |
| `negative_prompt_behavior` | str | One of `inline_no`, `separate_avoid_section`, `trailing_avoid_sentence`, `append_avoid_sentence`. |
| `allowed_parameters` | list[str] | Parameter keys the model accepts (others are dropped with a warning). |
| `adapter_status` | str | `stub_unverified` / `verified`. |

## Optional fields

| Field | Type | Purpose |
|-------|------|---------|
| `parameter_aliases` | object | Map of canonical → model-specific parameter keys. |
| `max_prompt_chars` | int | Hard cap on compiled text length. |
| `video_defaults` | object | Per-adapter overrides of duration / shot count. |
| `notes` | str | Free-form. Surfaces in the Target picker label. |

## `negative_prompt_behavior` values

| Value | Effect |
|-------|--------|
| `inline_no` | Prepends `--no <fragments>` style flags. Common for Midjourney-class models. |
| `separate_avoid_section` | Returns `avoid: <fragments>` as `negative_text`; main text is untouched. |
| `trailing_avoid_sentence` | Appends a blank-line-separated *Avoid: …* paragraph. |
| `append_avoid_sentence` | Joins *Avoid: …* into the main prompt as one sentence. |

## Compile-time warnings

The compiler attaches diagnostic warnings to the in-memory `CompiledPrompt`
when it detects:

- `mode_not_supported` — adapter doesn't declare your `mode` in
  `supported_modes`. The compile still proceeds.
- `dropped_unsupported_params` — you asked for parameters the adapter
  doesn't list in `allowed_parameters`.
- `adapter_stub` — the adapter is marked `stub_unverified`.

These never make it into the serialised JSON (see
[data model](data-model.html)).
