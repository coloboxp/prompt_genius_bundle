# Scripts

These are starter scripts. They are intentionally simple.

## inventory_catalog.py

Scans a catalog directory and reports basic counts.

Usage:

```bash
python scripts/inventory_catalog.py examples/catalog-items
```

## validate_catalog.py

Validates catalog items against the starter schema.

Usage:

```bash
python scripts/validate_catalog.py examples/catalog-items schemas/catalog-item.schema.json
```

This script uses `jsonschema` if installed. If not installed, it falls back to basic required-field checks.

## csv_inventory.py

Scans `raw_corpus/` CSV files. Reports per file: row count, column null counts, content length distribution, language ratio (latin vs CJK), unique authors, malformed JSON counts, date range.

Usage:

```bash
python scripts/csv_inventory.py raw_corpus/
```

## csv_dedupe.py

Detects exact duplicates (sha256 of `content`) and near-duplicate titles (Levenshtein ≤3, bucketed by first 4 chars). Writes one report per CSV to the audit output dir: `<basename>_duplicates.csv` with columns `id_a,id_b,reason`.

Usage:

```bash
python scripts/csv_dedupe.py raw_corpus/ audit/
```
