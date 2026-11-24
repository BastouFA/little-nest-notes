#!/usr/bin/env bash
# Re-generate the social preview image and favicon set from the HTML templates
# in this folder. Needs Google Chrome (or Chromium) and ImageMagick (`magick`).
# Only run this when you change the logo or the OG image text; the outputs are
# committed in site/ so hosts never need to run it.
#
#   bash scripts/brand/make_brand_assets.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="$ROOT/site/assets"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

shot() { # url width height out
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --default-background-color=00000000 --window-size="$2,$3" --screenshot="$4" "$1" >/dev/null 2>&1
}

# 1200 x 630 Open Graph / Twitter card image
shot "file://$HERE/og-image.html" 1200 630 "$TMP/og.png"
magick "$TMP/og.png" -strip -colors 128 -define png:compression-level=9 "$OUT/og-image.png"

# Square icons (full bleed) for apple-touch-icon and the web manifest
shot "file://$HERE/icon.html" 512 512 "$TMP/square.png"
magick "$TMP/square.png" -strip -resize 512x512 "$OUT/icon-512.png"
magick "$TMP/square.png" -strip -resize 192x192 "$OUT/icon-192.png"
magick "$TMP/square.png" -strip -resize 180x180 "$OUT/apple-touch-icon.png"

# Rounded mark for favicon.ico (16, 32, 48 px)
shot "file://$HERE/icon.html?round=1" 512 512 "$TMP/round.png"
magick "$TMP/round.png" -strip -define icon:auto-resize=48,32,16 "$ROOT/site/favicon.ico"

ls -l "$OUT/og-image.png" "$OUT/icon-512.png" "$OUT/icon-192.png" "$OUT/apple-touch-icon.png" "$ROOT/site/favicon.ico"
