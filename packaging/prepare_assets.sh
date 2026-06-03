#!/usr/bin/env bash
# Prepare the model + pre-built indexes that ship inside the .app so first
# launch is hot, offline, and doesn't touch HuggingFace.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"

MODEL_NAME="${MODEL_NAME:-all-MiniLM-L6-v2}"
ASSETS_ROOT="packaging/assets"
MODEL_DIR="${ASSETS_ROOT}/models/sentence-transformers/${MODEL_NAME}"
CACHE_DIR="${ASSETS_ROOT}/cache"

if [[ -f "$MODEL_DIR/config.json" && "${REBUILD_ASSETS:-0}" != "1" ]]; then
  echo "[prepare] model already at $MODEL_DIR — skip download. (REBUILD_ASSETS=1 to force.)"
else
  echo "[prepare] downloading sentence-transformers/${MODEL_NAME}"
  mkdir -p "$MODEL_DIR"
  "$PYTHON" - <<PY
import sys
from pathlib import Path
from sentence_transformers import SentenceTransformer
target = Path("$MODEL_DIR")
target.mkdir(parents=True, exist_ok=True)
print(f"  loading SentenceTransformer('$MODEL_NAME')...")
m = SentenceTransformer("$MODEL_NAME")
m.save(str(target))
print(f"  saved to {target} ({sum(f.stat().st_size for f in target.rglob('*') if f.is_file()) / 1e6:.1f} MB)")
PY
fi

echo "[prepare] pre-building catalog dense embeddings + corpus index + vocab"
mkdir -p "$CACHE_DIR/embeddings" "$CACHE_DIR/corpus" "$CACHE_DIR/vocab"
"$PYTHON" - <<PY
from prompt_genius.core.catalog import load_catalog
from prompt_genius.core.corpus import load_or_build_corpus_index
from prompt_genius.core.vocab import load_or_build_vocab
print("  catalog (dense)...")
catalog = load_catalog(
    "catalog",
    backend="dense",
    model_name="$MODEL_NAME",
    cache_dir="$CACHE_DIR/embeddings",
)
print(f"    {len(catalog.items)} items embedded")
print("  corpus BM25 index...")
ci = load_or_build_corpus_index("raw_corpus", cache_dir="$CACHE_DIR/corpus", rebuild=True)
print(f"    {len(ci)} corpus rows")
print("  corpus vocab...")
v = load_or_build_vocab("raw_corpus", cache_dir="$CACHE_DIR/vocab", rebuild=True)
print(f"    {v.sample_size} sampled, {sum(len(p) for p in v.by_category.values())} terms")
PY

echo "[prepare] done."
du -sh "$ASSETS_ROOT"
