# Refine a card from a generated image

Once you've rendered a card with the real model and the result isn't quite
right, the Refine dialog turns your critique into a revised prompt.

## Steps

1. Select the card you want to refine in the middle panel.
2. **Tools → Refine from feedback…** (<kbd>⌘</kbd>+<kbd>R</kbd>).
3. The dialog pre-fills with the card's compiled prompt.
4. Describe what was wrong with the rendered image — be concrete. Examples:
   - *"Hands look melted, also the depth of field is too shallow."*
   - *"Wrong era — wardrobe reads 2010s, should be late 70s."*
   - *"Lost the brand teal in the wide shots."*
5. Pick a backend (`claude` / `codex`) and effort.
6. Click **Generate refined prompt**. The dialog calls the backend and
   returns a revised prompt.
7. Choose:
   - **Apply as new card** — replaces the brief and queues a fresh generate
     so the structured pipeline runs from scratch on the new wording.
   - **Replace current card** — overwrites the compiled text of the
     selected card in place. Use this for quick iteration when you don't
     need a new variant.

## What's actually happening

The refine call is a single LLM round-trip — it doesn't go through the
proposer pipeline, doesn't fan out direction tilts, doesn't touch the
catalog. It's purely *text → critique → text*. That makes it fast (one
call) but it means the result isn't structurally aware of your adapter.
That's why "Apply as new card" is the right choice for serious revisions —
it sends the refined text back through the full pipeline.
