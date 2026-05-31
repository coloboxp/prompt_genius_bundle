# Your first prompt card

A ten-minute walk-through. By the end you'll have generated, inspected, and
exported a prompt card for a still image.

## Before you start

You need:

- A running Prompt Genius — either the bundled `🦊 Prompt Genius.app`, or
  `prompt-genius-gui` from a source checkout.
- One installed LLM backend. The recommended default is `claude` (Anthropic's
  CLI). `codex` (OpenAI's CLI) also works. If neither is installed the engine
  falls back to a deterministic heuristic — useful for trying the UI, not for
  real output.

Confirm the backend in **Edit → Preferences… → LLM**. The chosen backend is
shown in the status bar after each generation.

## 1. Type a brief

In the **Brief** field, describe what you want. The engine reads the words
you use to pull matching catalog patterns, so be specific. Example:

> Editorial portrait of a 60-year-old jazz pianist mid-performance — backlit,
> deep blue stage haze, warm bokeh, Leica grain, hands in focus.

There's a **Try an example** button if you want to start from a known-good brief.

## 2. Pick mode + target

- **Mode** decides the kind of asset (`static_image`, `text_to_video`,
  `storyboard`, etc.). The hints panel below switches Image ↔ Video
  automatically.
- **Target** is the model that will eventually consume the prompt. `generic`
  is model-agnostic. Other targets compile through an *adapter* — they know
  the model's parameter syntax and negative-prompt convention.

## 3. (Optional) Add hints

The **Hints** tabs append guidance to your brief (lens, lighting, aspect
ratio, camera motion, …). Anything left blank is ignored. Hints are
suggestions, not hard constraints — the LLM is free to bend them when it
makes sense.

## 4. Generate

Click **Generate** or press <kbd>⌘</kbd>+<kbd>↩</kbd>. Cards stream into the
middle panel as the LLM finishes each one. The status bar shows progress and
elapsed time.

## 5. Inspect a card

Click any card. The right panel shows:

- The compiled prompt text (read-only).
- A *why this works* rationale.
- A **brand-fit** score (only meaningful if a brand profile is active).
- The structured fields the engine used — edit any field and the prompt text
  re-compiles live.

## 6. Copy or export

In the right-panel action row:

- **Copy text** — the prompt string, ready to paste into the model.
- **Copy JSON** — the full structured card.
- **Copy TOON** — same structure, 30–60% fewer tokens. Useful when you're
  feeding the card to *another* LLM as context.

For a file, use **File → Export selected…** (<kbd>⌘</kbd>+<kbd>E</kbd>).

## Where to go next

- [Create a brand profile](../how-to/manage-brand-profiles.html) so future
  cards score themselves against your style rules.
- [Inspect the LLM prompts](../how-to/inspect-llm-prompts.html) when you want
  to know exactly what was sent to `claude` / `codex`.
- [Adapter schema](../reference/adapter-schema.html) when you want to add a
  new target model.
