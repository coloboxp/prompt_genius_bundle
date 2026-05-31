# Prompt Genius Architecture

## Architecture goal

Keep the first version simple, internal, and file-backed. Do not overbuild a SaaS architecture.

## Recommended folder structure

```text
prompt-genius/
  apps/
    web/
      brief-input/
      prompt-cards/
      fine-tuning-panel/
      json-viewer/
      history/
  backend/
    api/
    catalog-search/
    prompt-assembler/
    model-adapters/
    validators/
    feedback/
  catalog/
    styles/
    camera/
    lighting/
    composition/
    motion/
    shots/
    negative/
    tasks/
    brand/
    examples/
    adapters/
  schemas/
    catalog-item.schema.json
    generated-prompt.schema.json
    storyboard.schema.json
    adapter.schema.json
  agents/
    catalog-auditor/
    prompt-normalizer/
    duplicate-detector/
    prompt-generator/
    prompt-validator/
  evals/
    prompt-quality/
    brand-fit/
    video-stability/
```

## Runtime flow

```text
User brief
  -> brief parser
  -> structured intent
  -> catalog retrieval
  -> reranking
  -> prompt assembler
  -> model adapter
  -> validator
  -> prompt cards
  -> user fine-tuning
  -> export
```

## Main components

### Frontend

Responsibilities:

- Brief input
- Mode selection
- Target model selection
- Prompt card display
- Fine-tuning controls
- JSON preview
- Save and feedback actions

Suggested stack:

- React or Next.js
- Simple component library
- Local-first UX where possible

### Backend API

Responsibilities:

- Parse brief
- Search catalog
- Rerank patterns
- Assemble prompt candidates
- Compile target model output
- Validate generated JSON
- Save history and feedback

Suggested stack:

- FastAPI or Node
- Pydantic or Zod for validation
- JSON Schema for portable rules

### Catalog storage

Start with:

```text
JSON files in Git
```

This is good enough for an internal MVP because it gives:

- Version history
- Code review
- Easy inspection
- Simple backups
- Agent-friendly files

Later options:

- SQLite
- Postgres
- LanceDB
- Chroma
- Qdrant
- Internal knowledge service

### Search and retrieval

MVP search:

- Tags
- Keyword search
- Simple scoring

Phase 3 search:

- Embeddings
- Keyword search
- Tag filters
- Reranking
- Diversity selection
- Quality score boosts
- Brand profile boosts

### Prompt assembler

The assembler should combine selected catalog patterns into a neutral creative object.

It should not directly produce final text first.

Correct flow:

```text
patterns -> structured prompt object -> model-specific compiler -> final prompt text
```

### Model adapters

Adapters are pluggable JSON files. Any number of adapters can coexist: Nano Banana Pro, Adobe Firefly, ChatGPT/GPT Image, Midjourney, Seedance 2.0, Runway, Kling, Sora, Veo, Pika, Figma Make, etc. There is **no default-favored adapter** — the generic adapter is used when the user does not pick one.

Each adapter declares:

- Supported modes (`static_image`, `image_editing`, `text_to_video`, `image_to_video`, `storyboard`, `keyframe`)
- Supported parameters (with per-parameter syntax)
- Unsupported parameters (so the compiler drops them instead of inventing them)
- Prompt style (e.g. detailed natural language, compact descriptive, shot-structured, key-value)
- Negative prompt behavior (append, separate field, `--no` flag, etc.)
- Reference-image grammar
- Export format

Rules:

- The LLM must never invent settings not declared by the chosen adapter.
- The catalog stores model-neutral patterns; per-model phrasing lives in `prompt_fragments.<adapter_id>` and is optional.
- Adding a new model = adding one JSON file. No schema change, no code change.

### Validators

Validators should check:

- Required fields
- Valid mode
- Valid target model
- Valid parameter names
- Valid value ranges
- No unsupported model settings
- JSON schema compliance

### Feedback store

Store:

- User rating
- Prompt card selected
- Exported target model
- Failure reason
- Manual edits
- Pattern IDs used
- Generated output notes, if available

Use this later to improve ranking.

## Suggested tech stack

| Area | Practical choice |
|---|---|
| Frontend | React or Next.js |
| Backend | FastAPI or Node |
| Catalog storage | JSON files in Git |
| Search | SQLite FTS first, vector DB later |
| Embeddings | Internal-approved embedding model |
| Agent | API-based LLM for runtime, Claude CLI for repo work |
| Validation | JSON Schema, Zod, Pydantic |
| Versioning | Git |
| Auth | Simple internal auth first, SSO later |
| Deployment | Internal server, Docker, or local network app |

## Security and privacy

Since this is internal, keep the following rules:

- Do not send sensitive brand data to external tools without approval.
- Keep catalog private.
- Log prompts carefully.
- Avoid storing uploaded images unless needed.
- Make external generation optional.
- Keep model adapters explicit so users know where a prompt is intended to go.

## MVP API endpoints

Possible endpoints:

```text
POST /api/brief/parse
POST /api/prompts/generate
POST /api/prompts/refine
POST /api/prompts/compile
POST /api/prompts/validate
POST /api/feedback
GET  /api/catalog/search
GET  /api/catalog/item/{id}
GET  /api/history
```

## Minimal data stores

For MVP:

```text
/catalog/*.json       source catalog
/data/history.jsonl   generated prompt history
/data/feedback.jsonl  user feedback
/data/index.sqlite    optional keyword index
```

This is enough to prove the concept before adding heavier systems.
