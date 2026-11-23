#!/usr/bin/env bash
# After render.py --all: master + share copy (the original MP3 stream is copied, not re-encoded), audio QC, sheets.
set -euo pipefail
cd "$(dirname "$0")/.."
SONG=work/src/song.mp3
TOTAL=266.448
mkdir -p media variants/share thumbs work/qc/frames
python3 scripts/finish.py "$SONG" media/jensens-back.mp4 work/segments --fps 30 --kbps 5200 --total $TOTAL --threads 4 --preset medium --title "Jensen's Back"
python3 scripts/finish.py "$SONG" variants/share/jensens-back_share.mp4 work/segments --fps 30 --kbps 2000 --share --total $TOTAL --threads 4 --preset medium --title "Jensen's Back"
python3 scripts/qc_audio.py "$SONG" media/jensens-back.mp4
python3 scripts/qc_audio.py "$SONG" variants/share/jensens-back_share.mp4
rm -f work/qc/frames/*.jpg
ffmpeg -v error -y -i media/jensens-back.mp4 -vf "fps=1/4,scale=216:384" work/qc/frames/f_%03d.jpg
python3 scripts/sheet.py thumbs/jensens-back_sheet.jpg 12 216 work/qc/frames/f_*.jpg
