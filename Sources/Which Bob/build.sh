#!/bin/sh
# Renders this case's artwork into the case folder.
# Needs rsvg-convert:  brew install librsvg
set -e
src=$(cd "$(dirname "$0")" && pwd)
out=$src/../../"Which Bob"
mkdir -p "$out"

# Evidence images must be no larger than 1000x1000.
rsvg-convert -w  700 -h  620 "$src/threat letter.svg" -o "$out/threat letter.png"
rsvg-convert -w  760 -h  480 "$src/station memo.svg"  -o "$out/station memo.png"
rsvg-convert -w  640 -h  340 "$src/scanner card.svg"  -o "$out/scanner card.png"
# The preview is not bound by that limit; this matches the size of the
# preview the Example Case in the submodule ships.
rsvg-convert -w 2188 -h 2188 "$src/police report 1x1.svg" -o "$out/police report 1x1.png"

echo "Rendered into $out"
