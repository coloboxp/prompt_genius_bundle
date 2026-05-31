# Packaging Prompt Genius for macOS

One-shot build:

```bash
bash packaging/build_mac_app.sh
```

Produces `dist/PromptGenius.app`. Drag it to `/Applications` and launch.
First launch needs **Right-click → Open** because the bundle is ad-hoc signed.

## What's bundled

| What | Where in .app | Why |
|---|---|---|
| Python 3.12 + PySide6 + all deps | `Contents/MacOS/` + frameworks | runs without a Python install |
| `catalog/`, `schemas/`, `examples/`, `raw_corpus/`, `templates/` | `Contents/Resources/` | read-only reference data |
| Splash artwork | `Contents/Resources/prompt_genius/gui/assets/splash.png` | window splash + icon source |
| sentence-transformers model (all-MiniLM-L6-v2, ~80MB) | `Contents/Resources/models/sentence-transformers/all-MiniLM-L6-v2/` | offline dense embeddings |
| Pre-built catalog dense vectors | `Contents/Resources/.cache/embeddings/` | hot first launch |
| Pre-built corpus BM25 index + vocab | `Contents/Resources/.cache/corpus/` + `.../vocab/` | hot first launch |

## What's NOT bundled

| What | Why | What happens if missing |
|---|---|---|
| `claude` CLI | Node-based, separate install | GUI offers "Open install page" when picked |
| `codex` CLI | Node-based, separate install | same |
| `mlx-lm` model files | optional, large, Apple Silicon only | MLX backend not selectable until installed |
| Anthropic API key | user secret | claude path uses OAuth instead |

## Per-user data location

Writable data + caches don't live inside the .app (which would be read-only on Gatekeeper-quarantined installs). The bundled app writes to:

- `~/Library/Application Support/PromptGenius/` — config, history, feedback, versions
- `~/Library/Caches/PromptGenius/` — embeddings cache, corpus index cache, vocab cache

Source-tree runs (`prompt-genius-gui` from a `pip install -e .`) keep the existing relative `./data/` and `./.cache/` layout so they don't pollute your home.

## Steps (if running anything manually)

```bash
# Just the icon (PromptGenius.icns from splash.png)
bash packaging/make_icon.sh

# Just the bundled assets (model + caches)
bash packaging/prepare_assets.sh

# Just PyInstaller (assumes assets are prepared)
python3 -m PyInstaller packaging/PromptGenius.spec --noconfirm --clean
```

## Code signing for distribution

Ad-hoc `codesign -s -` is fine for your own machine. To share without the Gatekeeper warning you need a Developer ID:

```bash
codesign --deep --force --options runtime \
    --sign "Developer ID Application: Your Name (TEAMID)" \
    dist/PromptGenius.app
xcrun notarytool submit dist/PromptGenius.app \
    --apple-id you@example.com --team-id TEAMID --wait
xcrun stapler staple dist/PromptGenius.app
```

## Expected bundle size

| Layer | Size |
|---|---|
| Python + PySide6 | ~150 MB |
| torch (CPU) + sentence-transformers code | ~250 MB |
| all-MiniLM-L6-v2 model files | ~85 MB |
| catalog + schemas + adapters + templates | <1 MB |
| raw_corpus CSVs (4 files) | ~40 MB |
| pre-built caches | ~5 MB |
| **Total** | **~530 MB** |

To shrink: install CPU-only torch in the build env (`pip install torch --index-url https://download.pytorch.org/whl/cpu`) before running `build_mac_app.sh`.
