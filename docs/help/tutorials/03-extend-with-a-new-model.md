# Add a new target model end-to-end

Goal: ingest a CSV of prompts for a model Prompt Genius doesn't know about
yet, get a working adapter, and generate cards against it. ~15 minutes.

## 1. What you need

- A CSV of representative prompts for the new model. Any schema is fine —
  Prompt Genius detects columns automatically. At minimum it wants something
  that looks like a prompt column; ideally also `target_model`, `mode`,
  `tags`, and `rating`.
- The model's name as you'd like it shown in the **Target** picker, e.g.
  `seedance-2.0` or `firefly-image-3`.

## 2. Ingest the CSV

Open **File → Ingest CSV prompts…** (<kbd>⌘</kbd>+<kbd>I</kbd>).

1. Click **Pick CSV files…** and select your file (or several).
2. The table shows the delta against the current corpus: rows in the CSV,
   how many are *new*, how many are *duplicates*.
3. Leave **Auto-create a stub adapter…** checked. This writes a minimal
   adapter JSON in `examples/adapters/` for any model id that isn't there
   yet — enough to start generating with sensible defaults.
4. Click **Ingest**. Caches are invalidated; vocab and embeddings will
   rebuild on the next generation.

## 3. Pick the new target

Back in the main window, the **Target** dropdown now lists the model. Its
label includes its adapter status — `stub_unverified` is the auto-created
state.

## 4. Generate and review

Generate as usual. The compiled prompt now follows the stub adapter's
defaults. Check the result: do the parameter names match what the model
actually accepts? Is the negative-prompt syntax right?

## 5. Promote the adapter

If the stub works, leave it. If not, open the adapter JSON in
`examples/adapters/<model_id>_adapter.json` and:

- Fix `negative_prompt_behavior` (see [adapter schema](../reference/adapter-schema.html)).
- Adjust `allowed_parameters` and any `prompt_style` overrides.
- Bump `adapter_status` from `stub_unverified` to `verified` once you've run
  a few generations and checked them against the real model.

> Adapter changes don't require a restart. The next Generate picks them up.

## Where to go next

- [Adapter schema](../reference/adapter-schema.html) — the full field list.
- [Retrieval backends](../explanation/retrieval-backends.html) — what the
  new corpus rows now affect.
