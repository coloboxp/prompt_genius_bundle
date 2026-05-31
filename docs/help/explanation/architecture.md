# Architecture

High-level layout, top-down. Helpful before diving into the code.

## Three layers

```
┌───────────────────────────────────────────────┐
│  GUI (PySide6)        prompt_genius/gui/      │
│  CLI (Typer)          prompt_genius/cli/      │
├───────────────────────────────────────────────┤
│  Pipeline / orchestration                     │
│  prompt_genius/core/generate.py               │
├───────────────────────────────────────────────┤
│  Pure-function core   prompt_genius/core/     │
│  (catalog, retrieval, proposer, compiler,     │
│   adapters, brand, config, models)            │
└───────────────────────────────────────────────┘
```

The pure-function core has no I/O beyond loaders. It can run in tests
without a display, without network, without subprocesses.

## What happens on Generate

1. **Brief parse**. The brief becomes an `Intent` — either via the
   heuristic parser or by calling `claude` / `codex`.
2. **Retrieval**. The intent is scored against the catalog and the corpus.
   The active backend (`tfidf` / `bm25` / `dense` / `hybrid`) returns
   ranked `Match` objects, deduped by type with MMR diversity.
3. **Proposal**. The proposer fans out N parallel LLM subprocess calls,
   each with a different *creative direction* tilt. Each returns a
   `StructuredPrompt`. The heuristic proposer is the offline fallback.
4. **Assembly**. Selected catalog patterns + brand intent + structured
   prompt become a complete card.
5. **Compile**. The adapter for the chosen target model turns the
   structured prompt into a `CompiledPrompt` — final text, negative
   text, parameters.
6. **Stream**. Each card is emitted to the GUI as it lands. The status
   bar shows progress; the middle panel grows.

## GUI threading model

- The main thread owns Qt, the splash, the menubar, and all widgets.
- An `IndexPrewarmWorker` (`QThread`) warms the retrieval index on launch
  so the first Generate doesn't pay the cold-start cost.
- Each Generate fans out a `GenerateWorker` (`QThread`). It signals
  individual cards back (`card_ready`) and a final batch
  (`cards_ready`). Cancellation is cooperative.
- LLM subprocesses fan out from the proposer via a
  `ThreadPoolExecutor` *inside* `GenerateWorker`. The pool size matches
  `max_parallel` from config.

## Why pure-function core

Tests stay fast and deterministic. Swapping the GUI for a CLI (or for an
in-process API) only needs to swap the orchestration layer, not the core.
The same `generate_cards()` call powers the GUI's middle panel and the
`prompt-genius generate` command.
