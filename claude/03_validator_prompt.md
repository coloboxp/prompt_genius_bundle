# Claude CLI task: create catalog validation scripts

Create or extend validation scripts for the Prompt Genius catalog and the raw CSV corpus.

## Scripts to create or extend

Normalized catalog (already stubbed):

- `scripts/validate_catalog.py`
- `scripts/inventory_catalog.py`
- `scripts/find_duplicates.py`

Raw CSV corpus:

- `scripts/csv_inventory.py`
- `scripts/csv_dedupe.py`

## Validator requirements (catalog JSON)

1. Load all JSON files from the catalog directory.
2. Validate each item against `schemas/catalog-item.schema.json`.
3. Report missing required fields.
4. Report invalid `status` values.
5. Report invalid `quality_score` values.
6. Report duplicate IDs.
7. Report empty tags.
8. Report `prompt_fragments` missing the `generic` key.
9. Report items where any `prompt_fragments.<adapter_id>` is a near-duplicate of `prompt_fragments.generic` (warning) — that fragment is adding bias without adding value and should be removed unless the model truly needs different phrasing.
10. Exit with non-zero status if validation fails.

## Inventory requirements (catalog JSON)

Report:

- Number of JSON files
- Number of valid files
- Number of invalid files
- Counts by `type`
- Counts by `status`
- Top tags
- Missing fields
- Coverage of per-adapter fragments (count of items with at least one fragment per known adapter)

## Duplicate detection (catalog JSON)

Start simple:

- Duplicate IDs
- Exact duplicate `prompt_fragments.generic`
- Very similar `name`s

Later: near-duplicate embedding detection.

## CSV inventory requirements (`scripts/csv_inventory.py`)

For each CSV in `raw_corpus/`:

- Row count
- Unique authors (parsed from JSON in `author`)
- Empty / null counts per column
- Length distribution of `content` (min, p50, p95, max)
- Language guess for `content` (latin vs CJK ratio)
- Date range from `sourcePublishedAt`

## CSV dedupe requirements (`scripts/csv_dedupe.py`)

For each CSV:

- Exact duplicates by `sha256(content)`
- Near-duplicates by case-folded `title` Levenshtein ≤ 3 (sampled, not full O(n²) on 301k rows — bucket by first 4 chars first)
- Write a CSV report `audit/<source>_duplicates.csv` with columns `id_a,id_b,reason`

Do not modify the source CSVs.
