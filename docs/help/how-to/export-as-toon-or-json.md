# Export a card as JSON or TOON

A card holds the compiled text *and* its structured fields. Pick the
representation that matches the consumer.

## To the clipboard

Right panel, action row (or right-click the card):

| Button | What's copied | When to use |
|--------|---------------|-------------|
| **Copy text** | Just the compiled prompt string. | Pasting into the model directly. |
| **Copy JSON** | Full structured card. | Storing in a tool that wants JSON. |
| **Copy TOON** | Same structure as JSON, ~30–60% fewer tokens. | Feeding the card to *another* LLM as context. |

The TOON button falls back to JSON (with a status-bar notice) if the
`python-toon` package isn't installed in the running environment. In the
bundled `.app` it's always present.

## To a file

**File → Export selected…** (<kbd>⌘</kbd>+<kbd>E</kbd>) writes one of:

- `.md` — human-readable markdown card.
- `.txt` — plain compiled prompt.
- `.json` — structured card.

For TOON-as-file: copy to clipboard, paste into your editor. There's no
file dialog for TOON because TOON is meant for LLM prompts, not for
long-term storage — JSON remains the canonical format on disk.

## What's *not* in the export

- The compiled output never includes the diagnostic `warnings` list
  (adapter-stub notices, dropped-param hints). Those are GUI-only signals.
- The `card_id` is included so a downstream system can join back to your
  history. If you don't want that, edit it out by hand.
