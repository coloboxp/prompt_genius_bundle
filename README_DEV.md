# Prompt Genius — Developer Guide

Phase 1 ships as a Python package with a Typer CLI. The core is GUI-agnostic so a Qt (PySide6) layer can be added later without touching `prompt_genius/core/`.

## Install

```bash
pip install -e ".[dev]"               # core + tests
pip install -e ".[dev,gui]"           # + PySide6 Qt GUI
pip install -e ".[dev,gui,embeddings]" # + dense embeddings (sentence-transformers)
pip install -e ".[dev,gui,mlx]"       # + MLX on-device LLM brief parser (Apple Silicon)
pip install -e ".[all]"               # everything above
```

Or with `uv` in a project venv:

```bash
uv venv && uv pip install -e ".[all]"
```

Requires Python 3.11+. The LLM-backed brief parser uses the `claude -p` or `codex exec` CLIs via subprocess — install those separately if you want them on PATH.

## Run the CLI

```bash
prompt-genius list-adapters
prompt-genius list-modes
prompt-genius generate \
  --brief "Premium enterprise hero image for biometric onboarding" \
  --mode static_image \
  --target generic \
  --n 5
```

Pipe-friendly. Use `--json` to force JSON output even on a TTY.

### Other commands

```bash
# Phase 1 — core loop
prompt-genius generate --brief "..." --mode text_to_video --target generic --n 3
prompt-genius generate --brief "..." --mode storyboard --target seedance_2_0 --n 1
prompt-genius generate --brief "..." --mode keyframe --target generic --n 1
prompt-genius compile --card-file card.json --target seedance_2_0
prompt-genius refine --card-file card.json --change lens=85mm --change lighting=dramatic
prompt-genius validate --card-file card.json
prompt-genius save --card-file card.json --to data/history/
prompt-genius feedback --card-id <uuid> --rating good --note "perfect for the launch"

# Phase 2 — video MVP + brand profile + adapter-specific export
prompt-genius generate --brief "..." --brand-profile templates/brand-profile-template.json
prompt-genius convert --card-file card.json --target-mode image_to_video --target seedance_2_0
prompt-genius export --card-file card.json --format markdown --out card.md
prompt-genius list-exports

# Phase 4 — coordinated campaign pack
prompt-genius campaign --brief "Product launch" \
    --image-target nano_banana_pro --video-target seedance_2_0 \
    --brand-profile templates/brand-profile-template.json

# Phase 5 — versioning + diffing + brand fit + quality recompute
prompt-genius version --card-file card.json --note "tightened mood"
prompt-genius diff --a v1.json --b v2.json --field prompt
prompt-genius brand-fit --card-file card.json --brand-profile templates/brand-profile-template.json
prompt-genius quality                           # dry run
prompt-genius quality --apply                   # writes new scores back into catalog/

# GUI (requires .[gui] extra)
prompt-genius-gui
```

## Run the tests

```bash
pytest -q
QT_QPA_PLATFORM=offscreen pytest -q   # also exercises the GUI smoke test
```

40 tests across all phases:

- Phase 1: adapters, catalog (bias guard), brief, assembler, compiler (whitelisting, stub warnings, Seedance timing), end-to-end, Qt-readiness AST scan.
- Phase 2: static→video convert, brand-profile bias, exporters.
- Phase 3: TF-IDF reranking, brand-boost scoring.
- Phase 4: campaign multi-role pack, independent image/video targets.
- Phase 5: version JSONL, card diff, brand fit score, quality recompute.
- GUI: offscreen QApplication launch + worker round-trip.

## Project layout

```
prompt_genius/
  core/                # GUI-agnostic. Pure functions returning dataclasses.
    adapters.py        # JSON adapter loading / resolution
    brief.py           # Heuristic Intent extraction (no LLM in Phase 1)
    catalog.py         # JSON catalog loading + tag/keyword search
    assembler.py       # Patterns → model-neutral StructuredPrompt
    compiler.py        # StructuredPrompt → adapter-whitelisted CompiledPrompt
    generate.py        # Top-level facade: brief → list[PromptCard]
    models.py          # All dataclasses
    storage.py         # JSON / JSONL persistence (cards, feedback)
    validator.py       # JSON-schema validation
  cli/                 # Only place that touches stdin/stdout
    main.py            # Typer app
    formatters.py      # Terminal-friendly renderers
catalog/               # Normalized catalog items (status: draft until reviewed)
examples/adapters/     # Model adapters (generic, NBP, Seedance, Firefly, ChatGPT image, Midjourney, Runway)
raw_corpus/            # Source CSVs (read-only)
schemas/               # JSON schemas
scripts/               # CSV inventory / dedupe / seeding utilities
tests/                 # pytest suite
```

## Adding a new target model

No code change required.

1. Drop a JSON file into `examples/adapters/<model_id>_adapter.json` following the existing pattern.
2. Validate it: `python scripts/validate_catalog.py examples/adapters schemas/model-adapter.schema.json` — wait, that's the catalog validator; instead just run `pytest tests/test_adapters.py`.
3. Confirm by running `prompt-genius list-adapters`.

Set `adapter_status: stub_unverified` until you have confirmed the model's real grammar from working examples; compiled prompts will then carry a warning.

## Adding catalog items

1. Hand-write a JSON file under the matching `catalog/<category>/` folder.
2. Use `prompt_fragments.generic` as the primary text. **Do not add per-model fragments that just paraphrase generic** — the bias guard test will fail.
3. Keep `status: draft` until reviewed. The CLI accepts drafts by default (`--allow-drafts`) for Phase 1 because the seed ships as draft.

To re-seed the synthesized starter set:

```bash
python scripts/seed_catalog.py catalog/
```

This is idempotent: it overwrites only the seed file paths.

## Qt GUI contract (for later)

A future Qt layer must depend only on `prompt_genius.core`. The entry point you'll call from `QPushButton.clicked` is:

```python
from prompt_genius.core import generate_cards

cards = generate_cards(
    brief_text=text_edit.toPlainText(),
    mode=mode_combo.currentText(),
    target_model=target_combo.currentText() or None,
    n=spin_box.value(),
    catalog_dir="catalog",
    adapters_dir="examples/adapters",
    should_cancel=lambda: cancel_flag.is_set(),
)
```

Every returned object is a stdlib dataclass — wire it directly to Qt models. See `prompt_genius/core/README.md` for the full public API contract.

## Phase status

| Phase | Status | Where |
|---|---|---|
| 0 — Catalog discovery + normalization | done | `claude/01..04`, `scripts/csv_*.py`, `scripts/seed_catalog.py`, `catalog/` |
| 1 — Static image MVP | done | `prompt_genius/core/`, `prompt_genius/cli/`, 6 modes wired |
| 2 — Video MVP | done | `core/convert.py`, `core/brand.py`, `core/export.py` |
| 3 — Retrieval + reranking | done | `core/embeddings.py` TF-IDF + `core/retrieval.py` pluggable backend (sentence-transformers when `[embeddings]` installed) + MMR diversity reranker + brand boost |
| 4 — Storyboard + campaign | done | `generate_campaign`; storyboard mode runs **distinct per-shot retrieval** with role-tinted intents |
| 5 — Evaluation + quality loop | done | `core/versioning.py`, `core/usage.py` ledger, `core/quality.py` with all rating types + 90-day half-life decay + usage-driven save/reuse/export rates, `brand_fit_score`, CLI `version` / `diff` / `brand-fit` / `quality` |
| 6 — Internal integrations | exports + GUI shipped; HTTP server / Figma / browser / Slack / asset library / git snapshot deferred to v2 |
| 7 — Settings + config + MLX | done | `core/config.py` single source of truth for every magic number, GUI Settings dialog (General / LLM / Embeddings / Paths / Advanced tabs), MLX on-device brief parser, `claude -p` and `codex exec` subprocess brief parsers, HF model download |

## What's in the GUI

Launch with `prompt-genius-gui`. Three panels:

- **Left**: brief input, mode picker, target adapter, # cards, risk, brand profile picker, draft toggle, fine-tune tabs (image: aspect / lens / lighting / realism; video: duration / shot count / camera motion / subject motion / pacing), Generate / Cancel.
- **Middle**: tabbed Cards / History list.
- **Right**: compiled prompt, why-this-works, brand-fit score, editable JSON, Copy / Snapshot / Export, feedback widget with rating + note.
- **Settings dialog** (Cmd+,): every Config field is bindable. Advanced tab exposes retrieval weights, quality weights, video defaults — every magic number.
- **Theme**: system / light / dark.
- **Shortcuts**: ⌘N new brief, ⌘↩ generate, ⌘S save card, ⌘E export, Esc cancel, ⌘, settings.

## Magic numbers — all configurable

Every weight that used to live inline is now in `prompt_genius/core/config.py` and bound to a control in the Settings → Advanced tab:

- `RetrievalWeights`: tag_weight, text_weight, compatible_with_weight, avoid_with_penalty, intent_avoid_penalty, cosine_weight, brand_boost_weight.
- `QualityWeights`: curator/positive/save/reuse/export weights, negative_rate_penalty, half_life_days.
- `VideoDefaults`: single-shot duration, storyboard total, keyframe total, default shot count, default keyframe count, default aspect ratio / camera motion / subject motion / pacing / continuity, artifact_avoidance list.
- `EmbeddingsConfig`: prefer_dense, model_name, cache_dir, mmr_diversity, per_type_limit.
- `LlmConfig`: backend (heuristic / claude / codex / mlx / auto), effort, CLI binary + args + timeout, MLX model + max_tokens + temperature, HF token + cache dir.
- `PathsConfig`: every directory and JSONL path the engine writes.
- `GuiConfig`: theme, default mode, default target, default n, default risk, brand profile path, allow_drafts default.

Config persists to `~/.prompt-genius/config.json`. The Settings dialog reads/writes that file. The first launch creates a default config.
