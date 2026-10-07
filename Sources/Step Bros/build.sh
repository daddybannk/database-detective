#!/bin/sh
# Renders this case's artwork into the case folder.
# Needs rsvg-convert:  brew install librsvg
set -e
src=$(cd "$(dirname "$0")" && pwd)
out=$src/../../"Step Bros"
mkdir -p "$out"

# Evidence images must be no larger than 1000x1000.
rsvg-convert -w  700 -h  334 "$src/race rules.svg"  -o "$out/race rules.png"
rsvg-convert -w  560 -h  680 "$src/course card.svg" -o "$out/course card.png"
rsvg-convert -w 1000 -h  660 "$src/witness photo.svg" -o "$out/witness photo.png"
# The preview is not bound by that limit; this matches the size of the
# preview the Example Case in the submodule ships.
rsvg-convert -w 2188 -h 2188 "$src/police report 1x1.svg" -o "$out/police report 1x1.png"

echo "Rendered into $out"
