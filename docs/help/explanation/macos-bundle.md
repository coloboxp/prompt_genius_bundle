# macOS bundle architecture

How `🦊 Prompt Genius.app` is put together.

## What's inside

```
🦊 Prompt Genius.app/
├── Contents/
│   ├── Info.plist                       # bundle metadata, Help Book registration
│   ├── MacOS/PromptGenius               # PyInstaller bootloader → frozen Python
│   ├── Resources/
│   │   ├── PromptGenius.icns
│   │   └── PromptGenius.help/           # Apple Help Book bundle
│   └── Frameworks/                      # Qt + Python runtime
└── ...
```

At launch the bootloader unpacks the frozen Python tree (~950 MB) into
`sys._MEIPASS`. That tree contains everything the app needs at runtime:

- The Prompt Genius source.
- PySide6 + Qt frameworks.
- Torch (CPU build), sentence-transformers, transformers, tokenizers.
- The bundled `all-MiniLM-L6-v2` model — no HuggingFace fetch on first run.
- Pre-built catalog dense embeddings, corpus BM25 index, vocab caches.
- `python-toon`, jsonschema, typer, click.

## Pre-import hack for torch

PyInstaller-frozen torch on macOS aborts with `generic_type: cannot
initialize type "GradBucket": an object with that name is already defined`
when its C extension is first imported from a `QThread` instead of the
main thread. Shiboken's lazy-import path triggers a duplicate pybind11
type registration.

The fix lives in `prompt_genius/gui/app.py::_preimport_native_libs`:
torch + sentence-transformers are imported on the main thread before any
QThread is constructed. The worker thread later hits an already-loaded
module and the duplicate registration can't happen.

## Per-user data, never inside the bundle

`Contents/Resources/` is read-only. All writable state lives under
`~/Library/Application Support/PromptGenius/` and `~/Library/Caches/
PromptGenius/`. The bundle is fully replaceable on update — your saved
cards, brand profiles, history, and config survive.

See [file locations](../reference/file-locations.html) for the full layout.

## Ad-hoc signing

`build_mac_app.sh` runs `codesign --force --deep --sign -` after
PyInstaller. That makes Gatekeeper let the bundle run without quarantine
flags on the machine that built it. For distribution to other machines
you need a real Developer ID:

```
codesign --deep --force --options runtime \
  --sign "Developer ID Application: …" \
  dist/PromptGenius.app
```

Then notarize with `notarytool`. Without notarization Gatekeeper still
shows the *"can't open because it's from an unidentified developer"*
warning on first launch even with a Developer ID — notarization is what
removes that warning.

## Help Book

`packaging/PromptGenius.help/` is a separate bundle ID
(`com.innovatrics.promptgenius.help`) registered in the app's Info.plist
as `CFBundleHelpBookFolder` + `CFBundleHelpBookName`. macOS's
`Help Viewer.app` reads `Resources/<lang>.lproj/Help.helpindex` (built by
Apple's `hiutil`) for full-text search across the HTML pages.

Source is Markdown under `docs/help/`. `packaging/build_help_book.py`
converts to HTML and runs `hiutil`. The script is called from
`build_mac_app.sh` before PyInstaller so the freshly-built `.help` bundle
ends up in `Contents/Resources/`.

## Build pipeline

```
build_mac_app.sh
  ├─ make_icon.sh             — splash.png → PromptGenius.icns
  ├─ prepare_assets.sh        — download model + prebuild caches
  ├─ build_help_book.py       — Markdown → Apple Help Book
  └─ pyinstaller PromptGenius.spec
       └─ codesign --force --deep --sign -
```
