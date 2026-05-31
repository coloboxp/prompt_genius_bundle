# Retrieval backends

Catalog items are scored against the brief's intent. Four backends, picked
in **Preferences → Embeddings → backend**.

## tfidf

Classical TF-IDF over catalog item text + tags. Zero dependencies, very
fast, hides under the floor on long-tail vocabulary because rare terms
dominate IDF. Good for tiny / heterogeneous catalogs.

## bm25

Okapi BM25 (`bm25_k1=1.5`, `bm25_b=0.75` by default). Better than TF-IDF
on terms that repeat — handles "deep blue, deep navy, deep ocean" more
gracefully. Still zero ML dependency.

## dense

Sentence-transformers `all-MiniLM-L6-v2` embeddings, cosine similarity.
Catches semantic similarity TF-IDF / BM25 miss ("moody" ≈ "low-key
dramatic" ≈ "noir lighting"). The cost is model load time on first use —
the bundled `.app` ships the model on disk so there's no network.

## hybrid

Runs both `bm25` and `dense`, fuses with Reciprocal Rank Fusion
(`hybrid_rrf_k=60`), then reranks with MMR for diversity
(`mmr_diversity=0.4`). Best quality, ~2x latency of either alone. Default
in fresh installs.

## How fusion works

For each candidate item *c*, the BM25 rank and the dense-cosine rank are
both turned into reciprocal-rank scores:

```
RRF(c) = sum(1 / (k + rank_in_list(c))) over all source lists
```

This weights an item that's in the top of *both* lists more than one
that's near the top of just one. The `hybrid_rrf_k` knob controls how
much top-ranked items dominate (lower = more dominance).

## MMR rerank

After fusion, Maximum Marginal Relevance trims duplicates: picks the
highest-relevance item, then iteratively picks items that maximize

```
score = λ * relevance − (1 − λ) * max_similarity_to_already_picked
```

`mmr_diversity` is `(1 − λ)`. Set to 0 for pure relevance, to 0.6+ for
maximum diversity (often too aggressive — 0.3–0.4 is the sweet spot).

## When each backend wins

| Catalog size | Recommended |
|--------------|-------------|
| < 200 items | `bm25` — dense models over-fit on tiny sets. |
| 200 – 2000 items | `hybrid` — best of both. |
| > 2000 items | `hybrid` or `dense` — keep MMR diversity high. |

## Latency

Dense + hybrid prewarm on GUI launch (`prewarm_on_launch=true`). Cold
first-call is ~3–4s; warmed calls are 100–200ms for catalogs in the low
thousands.
