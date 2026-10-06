#!/bin/sh
# Renders this case's artwork into the case folder.
# Needs rsvg-convert:  brew install librsvg
set -e
src=$(cd "$(dirname "$0")" && pwd)
out=$src/../../"Spy Everywhere"
mkdir -p "$out"

# Evidence images must be no larger than 1000x1000.
rsvg-convert -w  700 -h  360 "$src/hall notice.svg"    -o "$out/hall notice.png"
rsvg-convert -w  560 -h  760 "$src/activity board.svg" -o "$out/activity board.png"
# The preview is not bound by that limit; this matches the size of the
# preview the Example Case in the submodule ships.
rsvg-convert -w 2188 -h 2188 "$src/police report 1x1.svg" -o "$out/police report 1x1.png"

echo "Rendered into $out"
