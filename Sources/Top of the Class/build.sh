#!/bin/sh
# Renders this case's artwork into the case folder.
# Needs rsvg-convert:  brew install librsvg
set -e
src=$(cd "$(dirname "$0")" && pwd)
out=$src/../../"Top of the Class"
mkdir -p "$out"

# Evidence images must be no larger than 1000x1000.
rsvg-convert -w  640 -h  400 "$src/registrar notice.svg"  -o "$out/registrar notice.png"
rsvg-convert -w  900 -h  640 "$src/security camera.svg"   -o "$out/security camera.png"
# The preview is not bound by that limit; this matches the size of the
# preview the Example Case in the submodule ships.
rsvg-convert -w 2188 -h 2188 "$src/police report 1x1.svg" -o "$out/police report 1x1.png"

echo "Rendered into $out"
