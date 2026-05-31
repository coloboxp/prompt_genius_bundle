# Rebuild the retrieval indexes

Prompt Genius keeps three lazy caches:

- **Catalog embeddings** — dense vectors per catalog item.
- **Corpus BM25 index** — sparse term-frequency index over `raw_corpus/`.
- **Vocab** — per-category term lists mined from the corpus, used to fill
  the editable combo boxes in the hints panel.

All three rebuild automatically the first time you Generate after they
change. Most of the time you don't need to think about them.

## When to force a rebuild

- After a big CSV ingest — to warm the new corpus rows before the next
  Generate so latency stays predictable.
- After editing a lot of `catalog/*.json` files by hand.
- If the hints combo boxes look stale (missing terms you know are in the
  corpus).

## Steps

1. **Tools → Rebuild indexes…**
2. A modal shows progress. You can click **Hide** — the rebuild keeps
   running in the background.
3. When it finishes you get a summary: catalog items, corpus rows, vocab
   categories, and how long each phase took.

## Hot reload

You don't have to wait for the rebuild to finish before generating. The
GUI prewarms the retrieval index on launch (see
**embeddings.prewarm_on_launch** in [Settings](../reference/settings.html)),
and Generate uses whatever cache is current when it fires.
