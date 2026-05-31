# Risks and Metrics

## Main risks

| Risk | What happens | Mitigation |
|---|---|---|
| Catalog becomes noisy | Bad prompts hurt output quality | Curate, score, dedupe |
| LLM invents settings | Designer loses trust | Use adapter whitelists |
| Video prompts are unstable | Outputs flicker, warp, or drift | Add motion constraints and negative motion prompts |
| Tool becomes too technical | Designers avoid it | Hide JSON by default |
| Too many prompt cards | Choice overload | Default to 5 options |
| Outputs feel generic | Low value | Use brand profiles and strong patterns |
| Model APIs change | Exports break | Use model adapters |
| Internal brand data leaks | Security issue | Keep catalog internal and control external generation |
| Agent edits catalog badly | Catalog corruption | Git review and validation |
| Prompt success is subjective | Hard to improve | Collect ratings and failure reasons |

## Specific video risks

| Risk | Impact | Mitigation |
|---|---|---|
| Motion too fast | Output looks cheap or chaotic | Default to calm motion for brand-safe work |
| Geometry drift | Product or UI changes shape | Add continuity constraints |
| Fake text | Video creates broken text | Use no text or preserve text instruction |
| Flicker | Output looks unstable | Add stable lighting and no flicker instructions |
| Overly cinematic output | Not suitable for B2B | Use channel and brand profile constraints |
| Start frame mismatch | Image-to-video does not preserve input | Add preserve layout, preserve subject, preserve color rules |

## Success metrics

Since this is internal and free, measure usefulness, not SaaS growth.

| Metric | Target |
|---|---|
| Time from brief to usable prompt | Under 2 minutes |
| Prompt card usefulness | 60 percent or more rated useful |
| Average prompt refinements before use | 3 or fewer |
| Prompt reuse rate | Increasing over time |
| Saved prompt rate | Increasing over time |
| Catalog duplicate rate | Decreasing over time |
| Invalid JSON rate | Near zero |
| Unsupported setting errors | Near zero |
| Designer satisfaction | Track with simple internal survey |
| Video prompt stability rating | Track manually first |

## Feedback tags

Users should be able to mark why a prompt failed:

- Too generic
- Wrong style
- Off-brand
- Too much sci-fi
- Too corporate
- Too busy
- Bad composition
- Wrong aspect ratio
- Motion too fast
- Motion too boring
- Video likely unstable
- Missing negative prompt
- Wrong target model
- Unsupported setting

## Quality scoring

Pattern quality score should be based on:

- Manual curator score
- User ratings
- Save rate
- Reuse rate
- Export rate
- Failure rate
- Deprecated status

Simple formula for later:

```text
quality_score =
  0.40 * curator_score +
  0.20 * save_rate +
  0.20 * positive_feedback_rate +
  0.10 * reuse_rate -
  0.10 * failure_rate
```

Keep it simple at first. Manual ratings are enough for MVP.

## Acceptance checklist for generated prompts

### Static image prompt

- Has clear subject
- Has desired style
- Has composition
- Has lighting
- Has format or aspect ratio
- Has negative prompt
- Has target model
- Does not include unsupported settings
- Matches brand profile if selected

### Video prompt

- Has duration
- Has shot count or single-shot declaration
- Has camera motion
- Has subject motion
- Has pacing
- Has continuity rules
- Has negative motion prompt
- Has target model
- Does not include unsupported settings
