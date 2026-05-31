# Add prompts from a CSV

Use this when someone hands you a spreadsheet of model prompts you'd like
the engine to learn from.

## Steps

1. **File → Ingest CSV prompts…** (<kbd>⌘</kbd>+<kbd>I</kbd>).
2. **Pick CSV files…** — you can pick several at once. Each file is
   classified independently, so they can have different schemas.
3. Review the delta table:
   - **Rows in CSV** — total parsed rows.
   - **New** — rows whose dedupe key (model id + normalized prompt text)
     isn't already in `raw_corpus/`.
   - **Duplicates** — silently skipped.
4. If the file is missing required columns, a red warning appears below the
   table and the file is skipped on **Ingest**.
5. Leave **Auto-create a stub adapter…** checked unless you already have a
   verified adapter for every model id in the CSVs.
6. Click **Ingest**.

## What it changes on disk

- New rows are appended to `raw_corpus/<model_id>.csv`.
- Stub adapters are written to `examples/adapters/<model_id>_adapter.json`
  with `adapter_status: stub_unverified`.
- Vocab, corpus BM25, and embeddings caches are invalidated. They rebuild
  lazily on the next Generate (you can force it with
  **Tools → Rebuild indexes…**).

## When ingestion is the wrong tool

If you just want to add a one-off catalog item (a specific lighting recipe,
a style fragment, …), edit a file under `catalog/` directly — the catalog
is the curated layer; the corpus is the raw mined layer.
