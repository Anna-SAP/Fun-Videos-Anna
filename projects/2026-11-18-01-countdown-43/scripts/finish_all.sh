#!/usr/bin/env bash
# After render.py --segments: master + share copy (original MP3 stream copied), audio QC, preview sheets.
set -euo pipefail
cd "$(dirname "$0")/.."
SONG=work/song.mp3
TOTAL=330.0
python3 scripts/finish.py "$SONG" media/countdown-43.mp4 work/segments --fps 30 --kbps 5200 --total $TOTAL --threads 4 --preset medium --title "Countdown 43"
python3 scripts/finish.py "$SONG" variants/share/countdown-43_share.mp4 work/segments --fps 30 --kbps 2000 --share --total $TOTAL --threads 4 --preset medium --title "Countdown 43"
python3 scripts/qc_audio.py "$SONG" media/countdown-43.mp4
python3 scripts/qc_audio.py "$SONG" variants/share/countdown-43_share.mp4
mkdir -p work/qc/frames && rm -f work/qc/frames/*.jpg
ffmpeg -v error -y -i media/countdown-43.mp4 -vf "fps=1/4,scale=216:384" work/qc/frames/f_%03d.jpg
python3 scripts/sheet.py thumbs/countdown-43_sheet.jpg 12 216 work/qc/frames/f_*.jpg
