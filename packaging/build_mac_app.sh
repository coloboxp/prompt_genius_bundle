#!/usr/bin/env bash
# One-shot macOS build:
#   icon → deps → assets → help book → PyInstaller → install help → sign.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BUILD_VENV="${BUILD_VENV:-$ROOT/.venv-build}"

if [[ "${REUSE_BUILD_VENV:-0}" != "1" ]]; then
  rm -rf "$BUILD_VENV"
fi

python3 -m venv "$BUILD_VENV"
PYTHON="$BUILD_VENV/bin/python"
export PYTHON

echo "[1/7] icon"
bash packaging/make_icon.sh

echo "[2/7] clean build venv + dependencies"
"$PYTHON" -m pip install --quiet --upgrade pip "setuptools<82" wheel
"$PYTHON" -m pip install --quiet -e ".[all]" pyinstaller markdown

echo "[3/7] prepare bundled assets (model + caches)"
bash packaging/prepare_assets.sh

echo "[4/7] build Apple Help Book"
"$PYTHON" packaging/build_help_book.py

echo "[5/7] clean previous build"
rm -rf build/PromptGenius dist/PromptGenius dist/PromptGenius.app

echo "[6/7] PyInstaller"
"$PYTHON" -m PyInstaller packaging/PromptGenius.spec --noconfirm --clean

echo "[7/7] install Help Book under Contents/Resources/"
# PyInstaller's macOS BUNDLE step cross-links Contents/Resources/ ↔
# Contents/Frameworks/ via relative symlinks. Moving a symlink to itself
# creates a self-loop, so always install the help bundle from the
# canonical packaging/build/ source. Strip the symlink first, then copy.
APP="dist/PromptGenius.app"
HELP_DST="$APP/Contents/Resources/PromptGenius.help"
HELP_FRMW="$APP/Contents/Frameworks/PromptGenius.help"
HELP_SRC="packaging/build/PromptGenius.help"
if [ -e "$HELP_DST" ] || [ -L "$HELP_DST" ]; then
  rm -rf -- "$HELP_DST"
fi
if [ -e "$HELP_FRMW" ] || [ -L "$HELP_FRMW" ]; then
  rm -rf -- "$HELP_FRMW"
fi
if [ -d "$HELP_SRC" ]; then
  cp -R "$HELP_SRC" "$HELP_DST"
  echo "   installed $HELP_SRC → $HELP_DST"
else
  echo "   WARN: $HELP_SRC missing — Help menu will fall back to in-app browser."
fi

# Ad-hoc sign so Gatekeeper lets it run without "damaged" warnings.
# For distribution outside your machine you need a real Developer ID:
#   codesign --deep --force --options runtime --sign "Developer ID Application: …" PromptGenius.app
codesign --force --deep --sign - "$APP" 2>/dev/null || true

SIZE=$(du -sh "$APP" | cut -f1)
echo
echo "✅  Built $APP ($SIZE)"
echo "   open $APP"
echo "   (first launch may need: right-click → Open, since the bundle is ad-hoc signed)"
