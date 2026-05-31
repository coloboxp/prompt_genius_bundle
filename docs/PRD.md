# Prompt Genius PRD

Version: 0.1  
Date: 2026-05-30  
Status: Draft  
Audience: Internal design, motion, marketing, and AI tooling teams

## 1. Product summary

Prompt Genius is an internal tool that helps designers and creative teams create better prompts for static image generation and video generation.

The user writes a short or detailed brief. The system uses an internal JSON catalog of prompt patterns, styles, examples, settings, negative prompts, motion patterns, and model adapter rules to generate several strong prompt options. The user picks one, fine-tunes it through simple controls, and exports the result as text, JSON, or model-specific prompt format.

The tool supports:

| Mode | Purpose |
|---|---|
| Static image prompt | Generate visuals, hero images, campaign images, icons, moodboards, product renders |
| Image editing prompt | Modify an existing image or visual concept |
| Image-to-video prompt | Animate a still image or design concept |
| Text-to-video prompt | Generate short video clips from description |
| Storyboard / scene-by-scene video prompt | Break an idea into shots or scenes and generate one prompt per shot, with continuity between them |
| Frame-by-frame / keyframe video prompt | Generate explicit start-frame, mid-keyframe, and end-frame prompts for fine control |
| Prompt fine-tuning | Adjust lens, lighting, camera movement, motion, style, mood, pacing, aspect ratio, and negative prompts |

## 2. Product thesis

Designers do not need a giant prompt library.

They need a tool that understands rough creative intent and converts it into strong, practical prompt options for the tools they use.

Prompt Genius should behave like a creative prompt compiler:

```text
messy user brief
  -> structured creative intent
  -> retrieved catalog patterns
  -> ranked prompt candidates
  -> editable prompt cards
  -> model-specific export
```

The catalog is hidden intelligence. The designer sees a guided creative workflow.

## 3. Core problem

Designers and motion creators face several problems with AI image and video tools.

| Problem | Impact |
|---|---|
| Prompts are hard to write well | Designers waste time with trial and error |
| Different AI tools need different prompt styles | A prompt that works in one tool may fail in another |
| Video prompts are harder than image prompts | They need motion, timing, camera movement, continuity, and transitions |
| Good prompts get lost | There is no shared memory of what worked |
| Prompt quality is inconsistent | Outputs look generic, AI-ish, or off-brand |
| Parameters are scattered | Lens, lighting, aspect ratio, motion, seed, duration, and style settings differ per tool |
| Existing prompt catalogs are too passive | Browsing prompts is slow and boring |
| Designers do not want to edit JSON | JSON is useful internally, but the UI must be simple |

## 4. Target users

### 4.1 Visual designer

Needs to generate static visuals, moodboards, hero images, campaign concepts, UI illustrations, icons, or presentation graphics.

Typical request:

> Create a clean enterprise SaaS hero visual for biometric onboarding.

Needs:

- Strong visual prompt variants
- Style controls
- Brand-safe negative prompts
- Aspect ratio presets
- Model-specific output
- Fast iteration

### 4.2 Motion designer or video editor

Needs to turn an idea, image, or campaign concept into short video prompts.

Typical request:

> Animate this product visual into a 6-second video with a slow camera push, subtle light movement, and premium enterprise mood.

Needs:

- Duration controls
- Shot structure
- Camera movement
- Subject motion
- Start and end frame logic
- Keyframe logic
- Pacing
- Continuity
- Negative motion instructions

### 4.3 Brand or marketing designer

Needs repeatable campaign visuals and video variants that stay on-brand.

Typical request:

> Make 5 visual directions for a product launch campaign, but keep them premium, trustworthy, and non-sci-fi.

Needs:

- Brand profile
- Approved styles
- Forbidden styles
- Prompt history
- Saved prompt packs
- Reusable campaign templates

### 4.4 Prompt curator

Maintains the internal prompt catalog.

Needs:

- Deduplication
- Tagging
- Schema validation
- Quality scoring
- Deprecated prompt handling
- Prompt pattern extraction

### 4.5 Developer or AI tooling maintainer

Builds and maintains schemas, adapters, retrieval, validation, and agent workflows.

Needs:

- JSON schemas
- Tests
- Prompt validation
- Model adapter configs
- Git-based catalog versioning
- CLI-based catalog maintenance

## 5. Goals

1. Turn vague creative briefs into high-quality static image and video prompt options.
2. Use the internal prompt catalog as hidden intelligence, not as the main UI.
3. Let designers fine-tune prompts through simple controls.
4. Support both general prompt generation and model-specific prompt exports.
5. Store all generated prompts in JSON.
6. Build reusable internal knowledge over time.
7. Support brand consistency.
8. Make prompt iteration faster and less random.
9. Allow Claude CLI or similar coding agents to inspect, normalize, and maintain the prompt catalog.
10. Keep the tool internal, free, and lightweight.

## 6. Non-goals

For the first versions, do not build:

| Non-goal | Reason |
|---|---|
| Public SaaS | Not needed |
| Marketplace | Adds moderation and noise |
| Billing | Irrelevant for internal use |
| Social prompt sharing | Not needed |
| Huge user management | Internal only |
| Complex multi-tenant architecture | Overkill |
| Automatic publishing to every AI platform | Too much early complexity |
| Training custom models | Not needed for MVP |
| Full media generation pipeline | Prompt creation is enough at first |

## 7. Product principles

### 7.1 The catalog is hidden intelligence

The designer should not browse thousands of prompts.

The designer should write a brief. The system should retrieve, combine, and adapt catalog patterns behind the scenes.

### 7.2 Prompts are structured objects, not plain text

Every prompt should have structured parts:

```json
{
  "subject": "...",
  "style": "...",
  "composition": "...",
  "lighting": "...",
  "camera": "...",
  "motion": "...",
  "negative_prompt": "...",
  "settings": {},
  "target_model": "..."
}
```

This makes prompts easier to search, combine, evaluate, and convert.

### 7.3 Separate creative intent from model syntax

The system should first create a neutral creative object. Then it compiles that object into the target format.

Adapters are pluggable. The starter set below is a non-exhaustive sample — any of these can be the active target, and new adapters can be added by dropping a JSON file into `examples/adapters/`.

| Target | Mode | Output style |
|---|---|---|
| Generic | static image, image editing, text-to-video, image-to-video, storyboard | Model-neutral natural-language compile. Default when no target is selected. |
| Nano Banana Pro | static image, image editing | Detailed natural-language image prompt with trailing "Avoid:" sentence |
| ChatGPT / GPT Image | static image, image editing | Conversational natural-language prompt; reference images by description |
| Adobe Firefly | static image | Concise descriptive prompt; supports content credentials and style references |
| Midjourney | static image | Compact descriptive prompt plus `--ar`, `--no`, `--style`, `--v` parameters |
| Seedance 2.0 | text-to-video, image-to-video, storyboard | Shot-structured prompt with `（0-Xs）` timing markers, explicit camera + subject motion, pacing, continuity, artifact avoidance |
| Runway | text-to-video, image-to-video | Natural-language motion description with start/end frame fields |
| Other (Kling, Sora, Veo, Pika, Figma Make, …) | varies | Add an adapter JSON; no schema change required |

The system **must never bias generation toward a default model**. The neutral creative object is built first; the user (or the adapter chosen for export) drives any model-specific phrasing.

### 7.4 Designers edit with controls, not raw JSON

Designers should see controls like:

- Style
- Lens
- Lighting
- Camera angle
- Camera motion
- Duration
- Aspect ratio
- Shot count
- Mood
- Realism
- Pacing
- Negative prompt
- Brand safety level

The JSON updates in the background.

### 7.5 Human stays in control

The tool proposes. The designer chooses.

The system should explain why it suggested a prompt, but it should not pretend there is only one correct answer.

## 8. Primary workflows

### 8.1 Static image prompt

1. User selects Static Image.
2. User writes a brief.
3. User selects optional target model.
4. System extracts intent.
5. System retrieves relevant prompt patterns.
6. System generates 5 to 10 prompt cards.
7. User picks one.
8. User fine-tunes style, lens, lighting, composition, mood, and aspect ratio.
9. System rebuilds prompt.
10. User exports text or JSON.

### 8.2 Image-to-video prompt

1. User selects Image-to-Video.
2. User uploads or references an image.
3. User writes desired animation.
4. System creates 3 to 5 motion directions.
5. User picks one.
6. User fine-tunes motion, duration, camera, pacing, and start/end frame.
7. System exports model-specific video prompt.

### 8.3 Text-to-video prompt

1. User selects Text-to-Video.
2. User describes the clip.
3. System extracts duration, aspect ratio, style, shot count, camera movement, and motion intensity.
4. System creates multiple prompt options.
5. User picks and fine-tunes.
6. System exports final prompt and JSON.

### 8.4 Storyboard-to-video prompt

1. User selects Storyboard.
2. User describes campaign or video idea.
3. System proposes a shot list.
4. User edits shots.
5. System creates one prompt per shot.
6. User exports storyboard JSON, shot prompts, and model-specific prompts.

### 8.5 Prompt refinement

After choosing a prompt, user can say:

- Make it more premium.
- Change the lens to 85mm.
- Make it less AI-looking.
- Make the motion slower.
- Make it suitable for LinkedIn.
- Make it safer for our brand.
- Turn this static prompt into a video prompt.

The system should update the structured prompt, not just append words.

## 9. Main product modules

### 9.1 Brief intake

Accepts:

- One sentence
- Long creative brief
- Existing prompt
- Static image prompt to convert into video prompt
- Video idea to convert into storyboard
- Uploaded image description later

Extracts:

```json
{
  "mode": "static_image",
  "task": "hero_image",
  "audience": "enterprise buyers",
  "style": ["premium", "trustworthy", "clean"],
  "avoid": ["cyberpunk", "hacker", "surveillance"],
  "format": "16:9",
  "target_model": "generic"
}
```

### 9.2 Retrieval and ranking

The backend should:

1. Parse user brief.
2. Search catalog using keywords, tags, embeddings, task type, model target, and brand profile.
3. Rerank results.
4. Pick useful pattern combinations.
5. Generate prompt cards.
6. Validate final JSON.

Ranking signals:

| Signal | Example |
|---|---|
| Task match | Hero image, product video, social ad |
| Mode match | Static image, image-to-video, text-to-video |
| Style match | Premium, editorial, minimal |
| Model match | Whichever adapter the user selected (Nano Banana Pro, Firefly, ChatGPT image, Seedance 2.0, Runway, etc.) — no default bias |
| Brand match | Approved internal style |
| Quality score | Patterns that worked before |
| Negative match | Avoid wrong style |
| Diversity | Avoid 5 similar options |

### 9.3 Prompt card generator

Each prompt option should appear as a card with:

- Title
- Best use case
- Mode
- Target model
- Prompt
- Negative prompt
- Settings
- Why this works
- Risk level
- Edit controls
- JSON preview

### 9.4 Fine-tuning panel

Static image controls:

| Group | Controls |
|---|---|
| Format | Aspect ratio, output size, transparent background |
| Style | Minimal, editorial, cinematic, product render, photorealistic |
| Camera | Lens, angle, framing, depth of field |
| Lighting | Natural, studio, softbox, dramatic, daylight, low-key |
| Composition | Centered, spacious, close-up, wide, hero layout |
| Color | Brand palette, muted, vibrant, monochrome |
| Subject | Human, product, abstract, environment |
| Text | No text, placeholder text, readable text |
| Brand safety | Safe, balanced, experimental |
| Negative prompt | Avoid list |

Video controls:

| Group | Controls |
|---|---|
| Format | Duration, aspect ratio, resolution target |
| Video mode | Text-to-video, image-to-video, storyboard |
| Shot design | Shot count, scene order, transitions |
| Camera motion | Push-in, pull-out, pan, tilt, orbit, static |
| Subject motion | None, subtle, medium, dynamic |
| Lighting motion | Static, shimmer, gradient shift, reveal |
| Pacing | Calm, medium, fast, dramatic |
| Continuity | Preserve character, product, logo, layout |
| End frame | Same as start, close-up, reveal, brand frame |
| Text behavior | Avoid fake text, preserve existing text |
| Artifact control | Avoid warping, flicker, morphing, unstable hands |
| Motion risk | Safe, creative, experimental |

### 9.5 Model adapters

Each model adapter should define what the target model supports and how to format output.

The app should never let the LLM invent settings. Each adapter should have a whitelist of supported fields.

## 10. MVP scope

The first useful product is a Prompt Workbench.

MVP features:

1. Brief input
2. Static image mode
3. Video mode
4. Generate 5 prompt cards
5. Pick one
6. Fine-tune through controls
7. Copy final prompt
8. View/export JSON
9. Save prompt
10. Basic rating

Catalog size for MVP:

```text
100 to 300 high-quality normalized patterns
```

The full thousands of prompts can remain in the repo, but they should not all become active immediately.

## 11. Success definition

The MVP is successful when an internal designer can go from a vague brief to a usable static image or video prompt in under 2 minutes, with fewer manual rewrites than before.
