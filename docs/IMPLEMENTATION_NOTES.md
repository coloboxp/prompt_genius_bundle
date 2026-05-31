# Implementation Notes

## Start simple

The first version does not need a complex database or fully automated prompt generation pipeline.

Start with:

- JSON catalog in Git
- Simple backend
- Simple React UI
- Prompt cards
- Fine-tuning controls
- Copy/export
- Feedback

## Suggested MVP stack

| Layer | Choice |
|---|---|
| Frontend | React or Next.js |
| Backend | FastAPI or Node |
| Validation | JSON Schema plus Pydantic or Zod |
| Catalog | JSON files in Git |
| Search | Keyword and tags first |
| Embeddings | Add later |
| Agent | Use LLM for generation and Claude CLI for catalog work |
| Storage | JSONL for feedback/history first |

## First internal demo

The first demo should show:

1. User writes a brief.
2. App returns 5 prompt cards.
3. User selects one.
4. User changes lens, lighting, aspect ratio, or motion.
5. Prompt updates correctly.
6. User copies final prompt.
7. User opens JSON preview.
8. User rates the prompt.

## Do not build these first

- Public login
- Payments
- Marketplace
- Social sharing
- Full plugin system
- Complex analytics
- Training custom models
- Automatic generation through every external tool

## What the app should never do

- Invent unsupported model parameters.
- Show thousands of raw prompts as the main UI.
- Force designers to edit JSON.
- Modify the catalog without validation.
- Let an agent overwrite the source corpus.
- Hide which patterns were used.

## Useful first UI sections

### Left panel

- Mode selector
- Brief input
- Target model
- Brand profile
- Number of options
- Risk level

### Main panel

- Prompt cards
- Why this works
- Settings summary
- Copy button
- Select button

### Right panel

- Fine-tuning controls
- Prompt preview
- Negative prompt
- JSON preview
- Export options

## First internal test brief set

Use a small test set to compare output quality:

1. Premium enterprise hero image for biometric onboarding.
2. Human-centered trust campaign image for identity verification.
3. Product launch video for secure digital onboarding.
4. Animate a static product visual with calm premium motion.
5. Create a 4-shot storyboard for identity verification.
6. Create a LinkedIn social video for a B2B security product.
7. Create a clean icon set for identity verification features.
8. Improve this existing prompt and make it less AI-looking.
9. Convert this static image prompt into a video prompt.
10. Make this concept more brand-safe and less futuristic.
