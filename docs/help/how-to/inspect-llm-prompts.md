# See exactly what was sent to the LLM

Use this when a generation produced something surprising and you want to
know whether the LLM was given misleading context.

## Steps

1. Run a Generate with the `claude` or `codex` backend. (Heuristic + MLX
   don't fan out subprocess calls; nothing is recorded.)
2. **Tools → Show last LLM prompts…** (<kbd>⌘</kbd>+<kbd>L</kbd>).
3. The dialog opens with one tab per parallel proposer call. Each tab is
   labelled with its creative-direction tilt (`editorial`, `playful`, …).

## What you see per tab

- **Header** — backend, binary path, extra CLI args, direction, latency,
  return code, prompt/output character counts.
- **Prompt (input)** — the exact string fed to `claude -p` via stdin or
  passed positionally to `codex exec`. Monospaced; preserves newlines.
- **Raw output** — the model's raw stdout, pre-JSON-parsing. Useful when
  the parser silently dropped a malformed proposal.

## Copy a prompt

Click **Copy prompt** to put the current tab's prompt on the clipboard.
Drop it into a chat session with `claude` / `codex` directly to A/B
reproduce the call by hand.

## Lifecycle

The trace is in-process and per-generation. Starting a new Generate clears
the previous batch. It's never written to disk — close the app and the
trace is gone. (This is intentional: prompts can contain sensitive brief
content, and the disk trail belongs in your version-controlled corpus, not
in a debug log.)
