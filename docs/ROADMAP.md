# Prompt Genius Roadmap

## Build strategy

Build the smallest useful loop first:

```text
Brief -> 5 prompt cards -> pick one -> fine-tune -> export -> rate
```

Everything else should support this loop.

## Phase 0: Catalog discovery and normalization

### Goal

Understand the existing prompt corpus and convert it into a useful structure.

### Inputs

- Existing JSON prompt files
- Plain-text prompts
- Notes
- Model-specific prompts
- Prompt fragments
- Old experiments
- Video prompt examples
- Image prompt examples

### Claude CLI tasks

1. Inventory all prompt-related files.
2. Identify file formats and schemas currently used.
3. Detect repeated structures.
4. Detect prompt categories.
5. Find duplicates and near-duplicates.
6. Find invalid or inconsistent JSON.
7. Identify model-specific syntax and parameters.
8. Propose a normalized taxonomy.
9. Propose JSON schemas for catalog items.
10. Produce a migration plan.

### Outputs

- `catalog_audit_report.md`
- `proposed_taxonomy.md`
- `proposed_schemas/`
- `migration_plan.md`
- `list_of_risks.md`
- `scripts/catalog_inventory.py`
- `scripts/validate_catalog.py`
- `scripts/find_duplicates.py`

### Acceptance criteria

- Existing prompts are inventoried.
- At least 80 percent can be classified into useful types.
- JSON schema exists.
- Validator catches invalid catalog items.
- Duplicate detection produces a report.
- First normalized catalog has at least 100 high-quality usable patterns.

## Phase 1: Static image prompt MVP

### Goal

Let a designer enter a brief and get 5 strong static image prompt cards.

### Features

- Brief input
- Mode selector: Static Image
- Target model selector
- Prompt card generation
- JSON preview
- Copy prompt
- Fine-tuning controls:
  - style
  - aspect ratio
  - lens
  - lighting
  - composition
  - mood
  - negative prompt
- Save/favorite prompt
- Basic feedback:
  - good
  - bad
  - too generic
  - wrong style
  - off-brand

### Not included yet

- Full video storyboard system
- Full embeddings
- External model API execution
- Figma plugin
- Full team analytics

### Acceptance criteria

- User can go from brief to 5 prompt options.
- User can adjust prompt through controls.
- Prompt JSON validates.
- User can copy text prompt.
- Generated prompts reference which catalog patterns were used.
- No unsupported model settings are invented.

## Phase 2: Video prompt MVP

### Goal

Add video prompt generation for text-to-video and image-to-video.

### Features

- Mode selector:
  - Text-to-video
  - Image-to-video
- Video prompt cards
- Video-specific controls:
  - duration
  - aspect ratio
  - shot count
  - camera movement
  - subject motion
  - pacing
  - continuity
  - end frame
  - negative motion prompt
- Generate 3 to 5 video directions
- Export video prompt JSON
- Export model-specific prompt

### Acceptance criteria

- User can create a video prompt from a text brief.
- User can convert a static image prompt into a video prompt.
- User can adjust motion parameters without rewriting the whole prompt.
- Video JSON validates.
- Prompt includes motion, pacing, continuity, and artifact-avoidance instructions.

## Phase 3: Retrieval and reranking

### Goal

Make the catalog truly intelligent.

### Features

- Embeddings for catalog items
- Keyword search
- Tag search
- Reranking
- Diversity control
- Brand profile ranking
- Quality score
- Why this pattern was selected
- Similar prompt suggestions
- Pattern usage tracking

### Acceptance criteria

- Same brief produces better targeted results than simple keyword search.
- Output options are meaningfully different.
- System avoids incompatible patterns.
- User feedback affects future ranking.
- Patterns with poor feedback decay in ranking.

## Phase 4: Storyboard and campaign mode

### Goal

Support longer creative thinking, especially for video and campaigns.

### Features

- Storyboard mode
- Shot list generation
- Prompt per shot
- Campaign visual set generation
- Static plus video pairing:
  - key visual prompt
  - animated version prompt
  - social crop prompt
  - thumbnail prompt
- Export complete campaign prompt pack

### Acceptance criteria

- User can generate a 4-shot storyboard from a brief.
- Each shot has its own prompt and settings.
- User can reorder or edit shots.
- System can generate static key visual plus video prompt from the same creative direction.

## Phase 5: Evaluation and prompt quality loop

### Goal

Make the tool improve over time.

### Features

- Prompt rating
- Result rating
- Why did this fail feedback
- Prompt version history
- Pattern quality score
- Brand fit score
- Output checklist
- Prompt comparison

### Evaluation dimensions

| Dimension | Question |
|---|---|
| Brand fit | Does this match our visual identity? |
| Prompt clarity | Is the prompt specific enough? |
| Model fit | Is it written correctly for the target model? |
| Output usefulness | Could a designer use the result? |
| Originality | Is it too generic? |
| Stability | For video, does it avoid warping and flicker? |
| Reusability | Can this become a template? |

### Acceptance criteria

- Users can rate prompts.
- Ratings are saved.
- Prompt versions are tracked.
- Low-performing patterns can be found.
- Curator can see top and worst catalog items.

## Phase 6: Internal integrations

### Goal

Bring Prompt Genius closer to real designer workflows.

### Possible integrations

| Integration | Purpose |
|---|---|
| Figma plugin | Send selected prompt to design workflow |
| Browser extension | Use Prompt Genius while working in AI tools |
| Image model exports | Copy-ready prompts via pluggable adapters: Nano Banana Pro, Adobe Firefly, ChatGPT/GPT Image, Midjourney, and any other adapter added later |
| Video model exports | Copy-ready prompts via pluggable adapters: Seedance 2.0, Runway, Kling, Sora, Veo, Pika, and any other adapter added later |
| Internal asset library | Use brand-approved references |
| Git integration | Version catalog changes |
| Slack share | Share prompt card internally |

### Acceptance criteria

- User can export to at least 2 target tools.
- Internal prompt links can be shared.
- Saved prompts are searchable.
- Brand profiles can be reused.

## Practical priority order

1. Catalog audit
2. Schema design
3. Normalize first 100 to 300 active patterns
4. Static image prompt workbench
5. Video prompt workbench
6. Fine-tuning controls
7. Embeddings and reranking
8. Feedback loop
9. Integrations
