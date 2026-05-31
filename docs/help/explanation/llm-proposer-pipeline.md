# LLM proposer pipeline

How "Generate" turns one brief into N distinct prompt cards.

## Fan-out, not a single call

Asking one LLM call for "give me 5 prompt cards" produces five
near-identical cards — the model self-reinforces. The proposer instead
fans out **N parallel single-card** calls, each tilted by a different
creative direction:

```
direction tilts (cycled):
  editorial       — clean, restrained, magazine-y
  playful         — quirky, unexpected, humorous
  cinematic       — wide lensing, dramatic light, mood
  documentary     — naturalistic, observational
  textural        — material-first, surface detail
```

Each call gets the same brief, the same retrieval results, the same
adapter context — only the direction prompt differs. The output is more
varied than asking one call for N cards, and latency is bounded by the
slowest single call instead of summed across N.

## How parallelism is bounded

`ThreadPoolExecutor(max_workers=min(max_parallel, n))`. Default
`max_parallel=5`. Each worker spawns a fresh `claude -p` or `codex exec`
subprocess. Output streams back via `as_completed()`.

## Streaming to the GUI

The pool dispatches a callback for each completed proposal. The GUI's
`GenerateWorker.card_ready` signal lights each card on screen as soon as
its assembly + compile finish — you don't wait for all five.

## When the LLM is silent

If a subprocess returns no output (timeout, non-zero rc), the proposer
drops that card. No retry — the parallel batch already has N candidates;
losing one or two is usually fine and avoids hammering the backend.

For zero results (every call failed), the proposer falls back to the
heuristic backend rather than returning nothing. The status bar shows a
warning when this happens.

## Lean flags

Both `claude_lean_flags` and `codex_lean_flags` strip features that aren't
useful for one-shot prompt generation:

- **Claude**: skips MCP servers, tool use, slash commands, session
  persistence, and dynamic system-prompt sections. ~40% faster per call.
- **Codex**: adds `--ephemeral --ignore-user-config --ignore-rules
  --skip-git-repo-check` and pins reasoning effort. ~10% faster.

If your proposer prompt needs those features (rare), turn the lean flag
off in Preferences.

## Capturing the prompts

Every subprocess call is recorded in an in-process trace
(`prompt_genius/core/llm_trace.py`). The GUI's
**Tools → Show last LLM prompts** dialog reads it. The trace is per-process
and reset on each Generate — it's never written to disk.
