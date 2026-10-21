#!/usr/bin/env bash
# Make the two preview images every project page uses:
#   OUT_poster.jpg — one frame at POSTER_TIME, 360 px wide
#   OUT_sheet.jpg  — 12 evenly spaced frames tiled 6x2, 360 px tall each
#
#   contact_sheet.sh VIDEO OUT_PREFIX [POSTER_TIME=10]
set -euo pipefail
f=$1; o=$2; t=${3:-10}
d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
ffmpeg -v error -y -ss "$t" -i "$f" -frames:v 1 -vf "scale=360:-2" -q:v 4 "${o}_poster.jpg"
tmp=$(mktemp -d)
for i in $(seq 1 12); do
  tt=$(python3 -c "print($d/13*$i)")
  ffmpeg -v error -y -ss "$tt" -i "$f" -frames:v 1 -vf "scale=-2:360" "$tmp/$(printf %02d "$i").jpg"
done
ffmpeg -v error -y -i "$tmp/%02d.jpg" -vf "tile=6x2:padding=4:color=white" -q:v 5 -frames:v 1 "${o}_sheet.jpg"
rm -rf "$tmp"
echo "written ${o}_poster.jpg ${o}_sheet.jpg"
