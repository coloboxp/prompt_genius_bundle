# File locations

Prompt Genius separates **read-only resources** (bundled with the app) from
**writable per-user data** (your history, feedback, brands, config). The
two never overlap.

## Read-only resources

Source mode (running from a git checkout): everything sits at the repo
root.

| What | Path |
|------|------|
| Catalog | `catalog/` |
| Adapters | `examples/adapters/` |
| Schemas | `schemas/` |
| Templates | `templates/` |
| Raw corpus | `raw_corpus/` |
| GUI assets | `prompt_genius/gui/assets/` |

Bundled mode (running `🦊 Prompt Genius.app`): the same trees are unpacked
into `sys._MEIPASS` at launch. They're untouchable from inside the app.

## Writable per-user data

On macOS:

| What | Path |
|------|------|
| Config | `~/Library/Application Support/PromptGenius/config.json` |
| Brand profiles | `~/Library/Application Support/PromptGenius/brands/` |
| Saved cards | `~/Library/Application Support/PromptGenius/history/` |
| Feedback log | `~/Library/Application Support/PromptGenius/feedback.jsonl` |
| Usage log | `~/Library/Application Support/PromptGenius/usage.jsonl` |
| Version log | `~/Library/Application Support/PromptGenius/versions.jsonl` |
| Caches (embeddings, BM25, vocab) | `~/Library/Caches/PromptGenius/` |

Source mode: writables go under `./data/` and `./.cache/` so they stay
git-friendly.

## Why this split

So a fresh install of a new app version doesn't blow away your saved cards
or brand profiles. The `.app` bundle is fully replaceable; the
`~/Library/Application Support/PromptGenius` tree is yours.

## Resetting

To start from scratch:

```
rm -rf ~/Library/Application\ Support/PromptGenius
rm -rf ~/Library/Caches/PromptGenius
```

The app rebuilds defaults on next launch.
