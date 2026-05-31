# Prompt Workflows

## Workflow A: Static image prompt

### User input

```text
Create a premium hero image for a biometric onboarding platform. It should feel trustworthy, enterprise, human, and clean. Avoid hacker or surveillance vibes.
```

### System steps

1. Detect mode: static image.
2. Extract task: landing page hero image.
3. Extract audience: enterprise buyers.
4. Extract desired mood: premium, trustworthy, human, clean.
5. Extract avoid list: hacker, surveillance, cyberpunk, dystopian.
6. Retrieve matching style, composition, lighting, camera, negative prompt, and task templates.
7. Generate 5 prompt cards.
8. Validate each generated prompt JSON.
9. Display cards.

### Prompt card examples

| Card | Direction |
|---|---|
| 1 | Premium enterprise hero |
| 2 | Human trust and identity |
| 3 | Abstract secure onboarding |
| 4 | Product UI floating composition |
| 5 | Editorial campaign visual |

### Fine-tuning controls

- Style
- Realism
- Aspect ratio
- Lens
- Camera angle
- Lighting
- Composition
- Color palette
- Subject type
- Negative prompt
- Brand safety

## Workflow B: Image-to-video prompt

### User input

```text
Animate this product hero image. Make it feel premium, with a slow camera push, soft lighting movement, and subtle UI glow. No dramatic sci-fi effects.
```

### System steps

1. Detect mode: image-to-video.
2. Identify source image role: start frame.
3. Extract desired motion: slow camera push, soft lighting movement, subtle UI glow.
4. Extract avoid list: dramatic sci-fi effects, fast motion, unstable geometry.
5. Retrieve matching motion, camera, pacing, continuity, and negative motion patterns.
6. Generate 3 to 5 video prompt cards.
7. Validate video prompt JSON.
8. Display cards.

### Video controls

| Control | Example values |
|---|---|
| Duration | 4s, 6s, 8s, 10s |
| Camera motion | slow push-in, dolly left, orbit, handheld, static |
| Subject motion | subtle, medium, dynamic |
| Lighting motion | gentle shimmer, soft gradient shift, no movement |
| Start frame | match uploaded image |
| End frame | slightly closer product focus |
| Pacing | calm, energetic, cinematic |
| Continuity | preserve layout, preserve face, preserve product shape |
| Text behavior | no text, preserve existing text, avoid fake text |
| Motion risk | safe, creative, experimental |

## Workflow C: Text-to-video prompt

### User input

```text
Create a 6-second launch video for a secure digital onboarding product. Premium, clean, not futuristic, suitable for LinkedIn.
```

### System steps

1. Detect mode: text-to-video.
2. Extract task: product launch video.
3. Extract duration: 6 seconds.
4. Extract channel: LinkedIn.
5. Extract style: premium, clean, not futuristic.
6. Retrieve video task templates, motion patterns, pacing patterns, negative motion patterns, and campaign patterns.
7. Generate prompt options.
8. Validate JSON.

### Output options

- Single-shot calm product reveal
- Multi-shot campaign teaser
- LinkedIn product hero animation
- Abstract secure identity animation
- Human-centered onboarding moment

## Workflow D: Storyboard-to-video prompt

### User input

```text
Create a 15-second product concept video for identity verification.
```

### System output

| Shot | Duration | Description |
|---|---:|---|
| 1 | 3s | Calm opening with person using phone |
| 2 | 4s | Smooth identity scan visualization |
| 3 | 4s | Secure approval moment |
| 4 | 4s | Product UI and brand message |

### Why storyboard matters

Video prompts often work better when the idea is split into shots. A single large prompt can become unstable or unclear.

Storyboard mode should create:

- One prompt per shot
- Duration per shot
- Camera movement per shot
- Subject movement per shot
- Transition logic
- Continuity rules
- Negative prompt per shot

## Workflow E: Prompt refinement

### User examples

- Make it more premium.
- Change the lens to macro.
- Make the camera movement slower.
- Make it less AI-looking.
- Add more negative space.
- Make it suitable for a slide.
- Make it safer for brand.
- Turn this static prompt into a video prompt.

### Correct behavior

The system should update structured fields.

Bad:

```text
original prompt + macro lens
```

Good:

```json
{
  "camera": {
    "lens": "macro",
    "framing": "close-up product detail",
    "depth_of_field": "shallow",
    "focus": "surface texture and product details"
  }
}
```

Then it should recompile the final target prompt.

## Workflow F: Static plus video pair

This is useful for campaign work.

### User input

```text
Create a key visual and a matching 6-second animation for a product launch.
```

### Output

- Static image prompt
- Matching image-to-video prompt
- Thumbnail prompt
- Social crop prompt
- Negative prompt shared across assets
- Brand consistency notes

## Workflow G: Existing prompt improvement

### User input

The user pastes an existing prompt.

### System output

- Diagnosis
- Weak points
- Improved version
- Structured JSON
- Suggested negative prompt
- Optional model-specific export

### Example diagnosis criteria

- Too vague
- Missing subject
- Missing composition
- Missing output format
- Missing negative prompt
- Missing camera or lens
- Missing motion details for video
- Contains unsupported parameters
