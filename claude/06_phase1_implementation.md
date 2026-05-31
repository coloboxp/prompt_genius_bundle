# Claude CLI task: Phase 1 implementation — Python core + CLI (Qt GUI later)

Build the Phase 1 MVP of Prompt Genius as a **Python package with a CLI** today, with the core structured so a Qt (PySide6) GUI can be added later without rewriting any logic.

## Non-negotiable architectural rules

1. **Pure-function core.** Every operation a UI will eventually call must live in `prompt_genius/core/` as a pure function or method returning a dataclass / typed dict. **No `print()`, no `input()`, no `argparse` inside `core/`.** The CLI and the future Qt GUI are both thin shells over the same core.
2. **Model-agnostic by default.** Default `target_model` is `generic`. Never hardcode a commercial model as the default anywhere — not in defaults, not in tests, not in fixtures.
3. **Adapter-driven compilation.** All model-specific behavior comes from `examples/adapters/*.json`. Adding a new model = adding one JSON. Do not branch on `model_id == "..."` anywhere in `core/`.
4. **Catalog-driven generation.** All prompt content comes from catalog items + adapter rules + user brief. Do not bake style/lighting/camera defaults into Python code — those live in `catalog/`.
5. **Strict adapter whitelisting.** When compiling, drop any field the adapter marks `supported: false`. Never invent a setting that isn't in the adapter.
6. **Stub adapters carry a warning.** Any prompt compiled with an `adapter_status: stub_unverified` adapter must include a clear warning in the returned card object.

## Repository layout to create

```
prompt_genius/
  __init__.py
  core/
    __init__.py
    brief.py            # parse_brief(text) -> Intent
    catalog.py          # load_catalog(path) -> Catalog; search(catalog, intent, mode, n) -> [Match]
    adapters.py         # load_adapters(path) -> dict[str, Adapter]; resolve(adapter_id) -> Adapter
    assembler.py        # assemble(intent, matches, adapter, mode) -> StructuredPrompt
    compiler.py         # compile(structured_prompt, adapter) -> CompiledPrompt
    validator.py        # validate_card(card) -> list[ValidationError]
    models.py           # @dataclass: Intent, Match, StructuredPrompt, CompiledPrompt, PromptCard, ValidationError, Warning
    storage.py          # save_card(card, dir), save_feedback(feedback, path) — JSONL append
  cli/
    __init__.py
    main.py             # typer app; only place that touches stdin/stdout
    formatters.py       # render a PromptCard as plain text / JSON for the terminal
  tests/
    test_brief.py
    test_catalog.py
    test_adapters.py
    test_assembler.py
    test_compiler.py
    test_end_to_end.py
pyproject.toml          # package metadata; entry point: prompt-genius = prompt_genius.cli.main:app
README_DEV.md           # how to install, run, test
```

Use `typer` for the CLI and `pydantic` v2 (or stdlib dataclasses + `jsonschema`) for validation. No web framework. No async.

## CLI surface (Phase 1)

All commands read/write JSON on stdin/stdout where appropriate so the future GUI can call the same Python functions directly, and a power user can pipe.

```
prompt-genius generate --brief "..." --mode static_image --target generic --n 5 [--brand-profile FILE] [--risk safe]
prompt-genius compile --card-file card.json --target nano_banana_pro
prompt-genius refine --card-file card.json --change "lens=85mm" --change "lighting=dramatic"
prompt-genius list-adapters
prompt-genius list-modes
prompt-genius validate --card-file card.json
prompt-genius save --card-file card.json --to history/
prompt-genius feedback --card-id <id> --rating good|bad|too_generic|off_brand --note "..."
```

`generate` is the headline command. It must return N prompt cards as a JSON array on stdout (one card per object) plus a human-readable summary on stderr when run interactively (detect via `sys.stdout.isatty()`).

## Mode coverage for Phase 1

Implement these modes end-to-end:

- `static_image`
- `image_editing`
- `text_to_video`
- `image_to_video`
- `storyboard` (returns one structured prompt per shot)
- `keyframe` (returns one structured prompt per frame: start, mid-keyframes, end)

For Phase 1 it's acceptable for `storyboard` and `keyframe` to produce simple multi-shot output without retrieval-driven shot variation — the data structures and adapter compilation must already be correct, even if the variety comes in Phase 3.

## Catalog seed

Before the assembler is usable, the catalog needs real items. Seed `catalog/` with at least:

- 30 items derived from `raw_corpus/nano-banana-pro-prompts-20260324.csv` (style, camera, lighting, composition, negative patterns)
- 15 items derived from `raw_corpus/seedance-2-0-prompts-20260324.csv` (motion, shot, transition, pacing, continuity patterns)
- All seven of the existing `examples/catalog-items/*.json` copied/promoted into `catalog/` if not already represented

Selection rules:

- Highest-confidence rows only (clear structure, no malformed JSON in side columns, deduped via `scripts/csv_dedupe.py`).
- Every catalog item must have `prompt_fragments.generic`. Per-model fragments only when the corpus shows the model truly needs different phrasing.
- Preserve provenance: `source.csv_id`, `source.url`, `source.author`, `source.file` on every item.
- Translate CJK content to English for `generic`; keep original under the model-specific fragment only if the language genuinely matters.
- All seed items start as `status: draft` unless a human has reviewed them. The CLI will refuse drafts by default unless `--allow-drafts` is passed.

## Brief parser (`core/brief.py`)

`parse_brief(text: str) -> Intent` extracts a structured intent. For Phase 1 the parser can be heuristic (keywords + regex) — do **not** call an LLM. Future phases can swap in an LLM-backed parser behind the same interface.

`Intent` fields (minimum):

```python
@dataclass
class Intent:
    subject: str | None
    audience: str | None
    mood: list[str]
    style_hints: list[str]
    avoid: list[str]
    format_hints: list[str]   # e.g. "16:9", "linkedin", "square"
    raw_brief: str
```

## Catalog search (`core/catalog.py`)

For Phase 1, simple scoring is fine:

- +3 per tag match against intent
- +2 per keyword match against `name` or `description`
- +1 per `compatible_with` match
- −5 if the item's `avoid_with` matches the intent
- Filter by `applies_to` includes the requested mode
- Filter out `status` in {`deprecated`, `archived`} (and `draft` unless `--allow-drafts`)
- Diversity guard: when selecting N matches, deduplicate by `(type, category)` first

Return the top N matches per pattern type needed for the mode.

## Assembler (`core/assembler.py`)

`assemble(intent, matches, adapter, mode) -> StructuredPrompt`

Combines patterns into a model-neutral `StructuredPrompt` dataclass:

```python
@dataclass
class StructuredPrompt:
    mode: str
    target_model: str
    creative_intent: dict
    visual_parameters: dict | None    # static / editing modes
    video_parameters: dict | None     # video / storyboard / keyframe modes
    selected_patterns: list[str]      # catalog item IDs
    why_this_works: str               # ≤ 3 sentences citing patterns by id
    negative_fragments: list[str]     # collected from negative_pattern items + intent.avoid
```

For storyboard mode, return a list of `StructuredPrompt` objects, one per shot, with `shot_number` and `duration_seconds`.

For keyframe mode, return a list with explicit `frame_role` ∈ {`start`, `keyframe`, `end`}.

## Compiler (`core/compiler.py`)

`compile(structured: StructuredPrompt, adapter: Adapter) -> CompiledPrompt`

Rules:

1. For each catalog item id in `selected_patterns`, use `prompt_fragments[adapter.model_id]` if present, else `prompt_fragments.generic`.
2. Concatenate fragments using the adapter's `prompt_style`:
   - `detailed_natural_language` → single paragraph, English sentences.
   - `compact_descriptive` → comma-separated phrase list.
   - `shot_structured_natural_language` → one block per shot, prefixed with the adapter's `shot_timing_syntax` if present.
   - `conversational_natural_language` → first-person request style.
   - `concise_descriptive` → short single sentence + key parameters.
   - `natural_language_motion` → motion-focused paragraph with explicit camera/subject motion fields.
   - `structured_natural_language` (generic) → `key: value` lines.
3. Append negative prompt according to `adapter.negative_prompt_behavior`:
   - `append_avoid_sentence` → `Avoid: …`
   - `trailing_avoid_sentence` → same, separate paragraph
   - `separate_avoid_section` → `avoid: …` on its own line/section
   - `parameterized_no_flag` → `--no x, y, z`
4. Drop every field the adapter marks `supported: false`. Do not silently keep them.
5. If `adapter.adapter_status == "stub_unverified"`, attach a `Warning("Adapter is a stub. Verify against the real model before production use.")` to the output.
6. Return:

```python
@dataclass
class CompiledPrompt:
    text: str
    negative_text: str
    parameters: dict        # only adapter-supported params
    warnings: list[Warning]
```

## Prompt card (returned by `generate`)

```python
@dataclass
class PromptCard:
    id: str                       # uuid4
    title: str
    mode: str
    target_model: str
    structured: StructuredPrompt | list[StructuredPrompt]  # list for storyboard/keyframe
    compiled: CompiledPrompt | list[CompiledPrompt]
    why_this_works: str
    selected_patterns: list[str]
    risk_level: str
    warnings: list[Warning]
    created_at: str               # ISO 8601 UTC
```

Cards must validate against `schemas/generated-prompt.schema.json` (or `video-prompt.schema.json` / `storyboard.schema.json`) before being returned.

## Tests (must pass)

- `test_adapters.py`: every JSON in `examples/adapters/` loads and validates against `schemas/model-adapter.schema.json`. Generic adapter is loadable as the default.
- `test_catalog.py`: every JSON in `catalog/` loads and validates. No item has `prompt_fragments` missing `generic`. No per-model fragment is identical to `generic` (bias guard).
- `test_brief.py`: parses 5 sample briefs into expected Intent shapes.
- `test_assembler.py`: assembles a `StructuredPrompt` for each mode with deterministic seeds.
- `test_compiler.py`:
  - For each adapter, compiling the same `StructuredPrompt` produces output that contains no field the adapter doesn't whitelist.
  - Stub adapters emit a warning.
  - Negative prompt formatting matches `negative_prompt_behavior`.
- `test_end_to_end.py`: `generate --brief "Premium enterprise hero" --mode static_image --target generic --n 5` returns 5 valid cards, each schema-valid, no two with identical `selected_patterns`.

Run tests with `pytest -q`. Build must pass before this task is considered done.

## Qt-readiness checklist (must be true at the end)

A future contributor adding a PySide6 GUI must be able to write `from prompt_genius.core import generate_cards` and wire it to a `QPushButton` without changing any core code. Verify by:

- No `core/*.py` imports `typer`, `argparse`, `click`, `sys.stdin`, `sys.stdout`, or `print`.
- Every core function returns dataclasses or plain dicts — never raw strings meant for display.
- All paths/config come in as arguments, never read from `os.environ` inside `core/` (env reads belong in `cli/main.py`).
- All long-running operations (e.g. catalog load) are idempotent and cancellable (accept a `should_cancel: Callable[[], bool] | None = None` parameter where it makes sense).
- Add a `prompt_genius/core/README.md` documenting the public API surface that a GUI will call.

## What NOT to build in Phase 1

- No web frontend, no FastAPI, no Next.js.
- No Qt GUI yet. Just keep the door open for it.
- No embeddings / vector search — keyword + tag scoring only.
- No LLM-backed brief parser — heuristic only.
- No external model API calls — Prompt Genius produces prompts; it does not call Nano Banana Pro / Seedance / etc.
- No auth, no multi-user, no remote storage.
- No automatic CSV → catalog conversion of all rows. Hand-pick the seed batch.

## Acceptance criteria

- `pip install -e .` succeeds.
- `prompt-genius list-adapters` lists all 7 adapters with status.
- `prompt-genius generate --brief "Premium enterprise hero image for biometric onboarding" --mode static_image --target generic --n 5` prints 5 schema-valid cards in under 2 seconds on a laptop.
- `prompt-genius generate --brief "6-second product launch teaser" --mode text_to_video --target generic --n 3` returns 3 video cards with `duration_seconds`, `camera_motion`, `pacing`, `continuity`.
- `prompt-genius generate --brief "..." --mode storyboard --target generic` returns a card whose `structured` is a list of 3–5 shot prompts with timing.
- `prompt-genius compile --card-file card.json --target seedance_2_0` recompiles the same structured prompt for Seedance, with `（0-Xs）` timing markers in the output text.
- `prompt-genius compile --card-file card.json --target firefly` emits a warning that Firefly adapter is a stub.
- All tests pass.
- `core/` contains zero references to `typer`, `argparse`, `sys.stdin`, `sys.stdout`, or `print`.

## Rules

- Do not modify `raw_corpus/`.
- Do not invent model settings — only emit what the chosen adapter whitelists.
- Do not default to a commercial model anywhere.
- If you must skip something, leave a `TODO(phase2): …` comment and explain why in the PR / summary, not in a doc file.
- Keep commits small and reviewable.
