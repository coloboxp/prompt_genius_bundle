# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone macOS PromptGenius.app.

Run via packaging/build_mac_app.sh which first calls prepare_assets.sh to
materialize the sentence-transformers model and pre-built indexes under
packaging/assets/.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
ASSETS = ROOT / "packaging" / "assets"

# -------- read-only resources bundled into the .app -------------------------

datas = [
    (str(ROOT / "catalog"), "catalog"),
    (str(ROOT / "schemas"), "schemas"),
    (str(ROOT / "examples"), "examples"),
    (str(ROOT / "raw_corpus"), "raw_corpus"),
    (str(ROOT / "templates"), "templates"),
    (str(ROOT / "prompt_genius" / "gui" / "assets"),
     "prompt_genius/gui/assets"),
]

# Apple Help Book — built by packaging/build_help_book.py before PyInstaller.
# PyInstaller's BUNDLE step relocates everything under Contents/Frameworks/
# by default. The osascript open-help call references the help book by its
# CFBundleHelpBookFolder name, but Help Viewer expects to find the .help
# bundle inside Contents/Resources/. To make that work we ship a copy
# both alongside the rest of the resources and into the Resources/ root via
# a runtime hook (see hooks/hook-runtime-help-book.py).
_HELP_BOOK = ROOT / "packaging" / "build" / "PromptGenius.help"
if _HELP_BOOK.exists():
    datas.append((str(_HELP_BOOK), "PromptGenius.help"))

# Pre-downloaded sentence-transformers model + pre-built indexes.
if (ASSETS / "models").exists():
    datas.append((str(ASSETS / "models"), "models"))
if (ASSETS / "cache").exists():
    datas.append((str(ASSETS / "cache"), ".cache"))

# sentence-transformers + transformers ship .json/.txt config files we need.
datas += collect_data_files("sentence_transformers")
datas += collect_data_files("transformers", include_py_files=False)
datas += collect_data_files("jsonschema")
datas += collect_data_files("jsonschema_specifications")

# -------- hidden imports the static analyzer can't infer --------------------

hidden = []
hidden += collect_submodules("prompt_genius")
hidden += [
    # sentence-transformers core
    "sentence_transformers",
    "sentence_transformers.SentenceTransformer",
    "sentence_transformers.models",
    "sentence_transformers.models.Transformer",
    "sentence_transformers.models.Pooling",
    "sentence_transformers.models.Normalize",
    "sentence_transformers.util",
    # transformers — only the bert flavor all-MiniLM-L6-v2 needs
    "transformers",
    "transformers.models.bert",
    "transformers.models.bert.modeling_bert",
    "transformers.models.bert.tokenization_bert",
    "transformers.models.bert.tokenization_bert_fast",
    "transformers.models.bert.configuration_bert",
    # tokenizers backend
    "tokenizers",
    # utility deps PyInstaller often misses
    "jsonschema", "jsonschema_specifications",
    "typer", "rich", "click", "shellingham",
    "anthropic",        # harmlessly missing if SDK not installed
    # Compact JSON alternative for LLM prompts (pkg: python-toon, module: toon)
    "toon", "toon.encoder", "toon.types",
]

# -------- analysis ----------------------------------------------------------

a = Analysis(
    [str(ROOT / "prompt_genius" / "gui" / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[str(ROOT / "packaging" / "hooks")],   # overrides hook-torch.py
    runtime_hooks=[],
    excludes=[
        # Cuts hundreds of MB; we use CPU torch only.
        "tkinter", "tcl", "tk", "Tkinter",
        "tensorflow", "flax", "jax", "jaxlib",
        "IPython", "jupyter", "notebook", "ipykernel",
        "pytest", "_pytest",
        "PyQt5", "PyQt6", "PySide2",
        "matplotlib", "pandas", "scipy.signal",
        "sklearn", "skimage",
        # We only run model.encode() — pure inference. Excluding torch's
        # training-only / multi-GPU subpackages avoids the duplicate
        # pybind11 type-registration crash that fires when the bundled
        # PyInstaller hooks pull these in twice.
        "torch.distributed", "torch.distributed.c10d",
        "torch.distributed.rpc", "torch.distributed.fsdp",
        "torch.distributed.elastic", "torch.distributed.checkpoint",
        "torch.distributed.optim", "torch.distributed.tensor",
        "torch.distributed.algorithms", "torch.distributed.nn",
        "torch.testing", "torch.utils.tensorboard",
        "torch.onnx", "torch.fx.experimental",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="PromptGenius",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                # macOS .app — no terminal window
    target_arch=None,             # build for the current arch (arm64 on Apple Silicon)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PromptGenius",
)

app = BUNDLE(
    coll,
    name="PromptGenius.app",
    icon=str(ROOT / "packaging" / "PromptGenius.icns")
        if (ROOT / "packaging" / "PromptGenius.icns").exists() else None,
    bundle_identifier="com.innovatrics.promptgenius",
    info_plist={
        "CFBundleName": "Prompt Genius",
        "CFBundleDisplayName": "🦊 Prompt Genius",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        "LSApplicationCategoryType": "public.app-category.developer-tools",
        # Lets the app keep running when the window is closed if useful later.
        "LSUIElement": False,
        # Register the bundled Apple Help Book so Help → 🦊 Prompt Genius Help
        # opens it in macOS Help Viewer.
        "CFBundleHelpBookFolder": "PromptGenius.help",
        "CFBundleHelpBookName": "com.innovatrics.promptgenius.help",
    },
)
