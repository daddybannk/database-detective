#!/bin/sh
# Renders this case's artwork into the case folder.
#
# This is the one case here not rendered with rsvg-convert. Its cards carry
# 👉👈, and Apple Color Emoji is an `sbix` font -- colour stored as bitmaps in
# a table cairo does not read. rsvg draws text through cairo, so it finds no
# colour layer, falls back to the font's monochrome outline and renders the
# pair as a single black blob. Chrome draws it in colour.
#
# Needs Google Chrome. Set CHROME to point somewhere else, or to Chromium.
set -e
src=$(cd "$(dirname "$0")" && pwd)
out=$src/../../"Vibe Code"
mkdir -p "$out"

chrome=${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}
if [ ! -x "$chrome" ]; then
	echo "build.sh: no Chrome at '$chrome'." >&2
	echo "Install Google Chrome, or set CHROME=/path/to/chrome." >&2
	exit 1
fi

# Chrome will not be handed the user's own profile: a throwaway one keeps the
# render from touching their browser state, and goes when the script does.
profile=$(mktemp -d)
trap 'rm -rf "$profile"' EXIT

# render <svg> <png> <css width> <css height> <scale>
# Chrome shoots the page at its CSS size times the device scale factor, so the
# PNG lands at width*scale by height*scale. Spaces in the path have to be
# percent encoded before they go into a file:// URL.
render() {
	url=$(printf '%s' "file://$src/$1" | sed 's/ /%20/g')
	"$chrome" --headless=new --disable-gpu --hide-scrollbars --no-first-run \
		--user-data-dir="$profile" \
		--window-size="$3,$4" --force-device-scale-factor="$5" \
		--screenshot="$out/$2" "$url" >/dev/null 2>&1
	test -f "$out/$2" || { echo "build.sh: Chrome wrote no $2" >&2; exit 1; }
}

# Evidence images must be no larger than 1000x1000.
render "incident report.svg"   "incident report.png"   700 600 1
render "chat log.svg"          "chat log.png"          540 480 1
# The preview is not bound by that limit; this matches the size of the
# preview the Example Case in the submodule ships.
render "police report 1x1.svg" "police report 1x1.png" 1000 1000 2.188

echo "Rendered into $out"
