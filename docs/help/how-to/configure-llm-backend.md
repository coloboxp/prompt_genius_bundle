# Configure the LLM backend

Open **Edit → Preferences… → LLM** to switch between proposer backends.

## Backends

| Backend | What it is | When to use |
|---------|-----------|-------------|
| `heuristic` | Deterministic, no LLM. Quick fallback for offline / dev. | UI exploration, automated tests. |
| `claude` | Anthropic's `claude` CLI in `-p` (print) mode. | Default for production use. |
| `codex` | OpenAI's `codex exec`. | When you prefer GPT-class quality. |
| `mlx` | Local model via `mlx-lm`. | Apple Silicon, no network, no API key. |
| `auto` | First of `claude` → `codex` → `heuristic` that's installed. | Convenience. |

## Per-backend knobs

**Effort** (`low` / `medium` / `high` / `xhigh` / `max`) maps to the
backend's reasoning-effort flag. Higher = slower + better.

**Claude:**

- `claude_model` — alias (`sonnet` / `opus` / `haiku`) or full model id.
  Empty = the CLI's default.
- `claude_lean_flags` — skips MCP, tools, slash commands, session
  persistence, and dynamic system prompts. ~40% faster per call. Only turn
  off if your proposer prompt actually needs Claude's tools.

**Codex:**

- `codex_model` — empty = CLI default, or e.g. `gpt-5`, `gpt-4o`.
- `codex_lean_flags` — adds `--ephemeral --ignore-user-config --ignore-rules
  --skip-git-repo-check` and pins `model_reasoning_effort`. ~10% faster.

**MLX:**

- `mlx_model` — HuggingFace id, e.g.
  `mlx-community/Llama-3.2-3B-Instruct-4bit`.
- `mlx_max_tokens`, `mlx_temperature`, `hf_token`, `hf_cache_dir`.

## Timeout

`timeout_seconds` caps each subprocess call. Default 180s — already padded
for tail latency. Raise it if you're using `xhigh`/`max` effort on a large
model.

## If the chosen backend isn't installed

Generate refuses to fall back silently. Prompt Genius asks if you want to
visit the install page for `claude` / `codex`. Until the binary is on
`PATH`, switch to `heuristic` or `mlx` to keep working.
