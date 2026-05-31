# Claude CLI task: catalog audit

You are helping build an internal tool called Prompt Genius.

The raw prompt corpus lives in `raw_corpus/` as two CSV files exported from a public prompt-catalog site:

| File | Target model | Mode | Rows |
|---|---|---|---|
| `raw_corpus/nano-banana-pro-prompts-20260324.csv` | Nano Banana Pro (Gemini image model) | static image / image editing | 11,766 |
| `raw_corpus/seedance-2-0-prompts-20260324.csv` | Seedance 2.0 | text-to-video / image-to-video | 1,078 |

Confirmed via `scripts/csv_inventory.py`. About 12% of NBP rows and 38% of Seedance rows are CJK-dominant (mostly Chinese); plan translation work accordingly.

Both CSVs share these columns:

```text
id, title, description, content, sourceLink, sourcePublishedAt, author, sourceMedia
```

The seedance CSV adds two extra columns:

```text
sourceReferenceImages, sourceVideos
```

`content` holds the actual prompt text. `sourceMedia` is a JSON array of preview URLs. `author` is a JSON object `{"name":..., "link":...}`. Some `content` values are in Chinese (Seedance) or contain mixed languages.

Your task is to inspect this corpus and produce a catalog audit. Do not rewrite anything yet.

## First tasks

1. Inventory both CSVs: row counts, unique authors, language distribution in `content`, length distribution, null/empty fields.
2. For each CSV, sample 50 rows and detect the recurring structural patterns inside `content` (e.g. `subject — style — lighting — camera — negative` vs free-form prose vs structured key-value).
3. Detect prompt categories per row:
   - style
   - lighting
   - camera / lens
   - composition
   - motion (Seedance only)
   - shot / scene structure (Seedance only)
   - negative prompts
   - model-specific syntax (Nano Banana Pro phrasing, Seedance shot timing markers, etc.)
   - full prompt examples
4. Find duplicates and near-duplicates by hash of `content` and by similar `title`.
5. Find rows with malformed JSON in `sourceMedia` / `author` / `sourceReferenceImages` / `sourceVideos`.
6. Identify model-specific syntax and parameters (Nano Banana Pro keywords, Seedance shot markers like `（0-4秒）`, camera grammar, etc.).
7. Propose a normalized taxonomy that maps raw CSV rows → catalog item types defined in `docs/CATALOG_TAXONOMY.md`.
8. Propose JSON schemas for catalog items (reuse `schemas/catalog-item.schema.json` where possible).
9. Produce a migration plan from CSV rows → normalized catalog JSON files.

## Output files

Create:

- `audit/catalog_audit_report.md`
- `audit/proposed_taxonomy.md`
- `audit/proposed_schemas/`
- `audit/migration_plan.md`
- `audit/list_of_risks.md`

## Rules

- Do not modify or delete the source CSVs.
- Do not change the existing catalog yet.
- Mark uncertain classifications clearly.
- Prefer small, reviewable changes.
- Do not invent model settings for Nano Banana Pro or Seedance — confirm against the actual `content` examples in the corpus.
- Keep `raw_corpus/` separate from the normalized active catalog.
- Sample first. Do not try to load all rows into a single LLM context — use `scripts/csv_inventory.py` and `scripts/csv_dedupe.py` for aggregation.
