#!/usr/bin/env bash
# Wrap dist/PromptGenius.app in a drag-to-install .dmg.
#
# Expects dist/PromptGenius.app to already exist — run build_mac_app.sh
# first. Re-run this without rebuilding the .app when you just want a
# fresh DMG.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP="dist/PromptGenius.app"
OUT="dist/PromptGenius.dmg"

if [ ! -d "$APP" ]; then
  echo "✗  $APP does not exist. Run packaging/build_mac_app.sh first." >&2
  exit 1
fi

echo "[1/4] dependencies"
python3 -m pip install --quiet --user dmgbuild pillow

echo "[2/4] render DMG backdrop"
python3 packaging/make_dmg_background.py

echo "[3/4] build DMG"
# Clean previous so dmgbuild doesn't refuse on an existing target.
rm -f "$OUT"
PG_ROOT="$ROOT" PG_APP="$APP" PG_DMG_OUTPUT="$OUT" \
  python3 -m dmgbuild \
    -s packaging/dmg_settings.py \
    "🦊 Prompt Genius" \
    "$OUT"

echo "[4/4] sign DMG"
# Ad-hoc sign matches the bundled .app signature mode. For distribution,
# sign with a Developer ID and notarize via notarytool.
codesign --force --sign - "$OUT" 2>/dev/null || true

SIZE=$(du -sh "$OUT" | cut -f1)
echo
echo "✅  Built $OUT ($SIZE)"
echo "   open $OUT     # mounts and shows the drag layout"
