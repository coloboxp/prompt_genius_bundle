# Brand profile schema

JSON schema for files in
`~/Library/Application Support/PromptGenius/brands/`. Template:
`templates/brand-profile-template.json`.

```json
{
  "id": "acme-default",
  "name": "Acme default",
  "tone": ["trustworthy", "clean", "professional"],
  "visual_style": ["modern", "minimal", "premium"],
  "color_palette": ["deep blue", "white", "soft gray"],
  "prefer": ["clean layouts", "human trust", "calm motion"],
  "avoid": ["cyberpunk", "hacker visuals", "fake UI text"],
  "video_rules": ["prefer slow and stable motion", "avoid flicker"],
  "status": "active",
  "version": "1.0"
}
```

## Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | str | yes | Stable slug. Doesn't change on rename. |
| `name` | str | yes | Display name. |
| `tone` | list[str] | no | Voice descriptors. |
| `visual_style` | list[str] | no | Style cues. |
| `color_palette` | list[str] | no | Brand colors as words or hex. |
| `prefer` | list[str] | no | Phrases to boost in retrieval + prompt. |
| `avoid` | list[str] | no | Phrases to penalise + add to negative prompt. |
| `video_rules` | list[str] | no | Motion guidance. |
| `status` | str | no | `active` / `draft`. |
| `version` | str | no | Free-form; bump it when you change the profile. |

## What the engine does with each field

- `tone + visual_style + prefer` → added to the retrieval intent as boost
  terms. Catalog patterns tagged with matching terms get a relevance bump.
- `avoid` → goes both to retrieval (penalty) **and** to the negative prompt
  fed to the model.
- `video_rules` → joined into the brief for video modes.
- `color_palette` → joined into the brief for image modes.

## What the brand-fit score actually measures

```
boost   = count of tone+visual_style+prefer tokens present in compiled text
penalty = count of avoid tokens present in compiled text
raw     = boost − 2 * penalty
max     = max(len(boost_terms), 1)
score   = clamp01( (raw + max) / (2 * max) )
```

It's a heuristic, not a verdict. Use it as a smoke signal — a 0.2 means
"probably off-brand, eyeball it", a 0.9 doesn't mean "ship it".
