#!/usr/bin/env bash
# Convert the approved transparent concept to a bounded embedded RGBA asset.
set -euo pipefail
cd "$(dirname "$0")/.."
magick crates/uefi-app/assets/emblem/regis-steel-gold.png \
    -trim +repage -resize 144x144 -gravity center -background none \
    -extent 144x144 -depth 8 RGBA:crates/uefi-app/assets/emblem/regis-144.rgba
