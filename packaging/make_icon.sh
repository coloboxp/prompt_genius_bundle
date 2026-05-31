#!/usr/bin/env bash
# Generate PromptGenius.icns from the splash artwork using mac-native iconutil.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SRC="prompt_genius/gui/assets/splash.png"
ICONSET="packaging/PromptGenius.iconset"
OUT="packaging/PromptGenius.icns"

if [[ ! -f "$SRC" ]]; then
    echo "Missing $SRC"; exit 1
fi

rm -rf "$ICONSET"
mkdir -p "$ICONSET"

for SIZE in 16 32 64 128 256 512 1024; do
  sips -z "$SIZE" "$SIZE" "$SRC" --out "$ICONSET/icon_${SIZE}x${SIZE}.png" >/dev/null
done
# @2x retina variants for the sizes Apple expects
cp "$ICONSET/icon_32x32.png"    "$ICONSET/icon_16x16@2x.png"
cp "$ICONSET/icon_64x64.png"    "$ICONSET/icon_32x32@2x.png"
cp "$ICONSET/icon_256x256.png"  "$ICONSET/icon_128x128@2x.png"
cp "$ICONSET/icon_512x512.png"  "$ICONSET/icon_256x256@2x.png"
cp "$ICONSET/icon_1024x1024.png" "$ICONSET/icon_512x512@2x.png"
rm -f "$ICONSET/icon_64x64.png" "$ICONSET/icon_1024x1024.png"

iconutil -c icns "$ICONSET" -o "$OUT"
rm -rf "$ICONSET"
echo "Built $OUT ($(ls -lh "$OUT" | awk '{print $5}'))"
