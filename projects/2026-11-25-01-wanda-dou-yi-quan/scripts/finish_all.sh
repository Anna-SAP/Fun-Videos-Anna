#!/usr/bin/env bash
# After render.py --all: master + share copy (the original MP3 stream is copied, not re-encoded), audio QC, sheets.
set -euo pipefail
cd "$(dirname "$0")/.."
SONG=work/src/song.mp3
TOTAL=167.233
NAME=dou-yi-quan
mkdir -p media variants/share thumbs work/qc/frames
python3 scripts/finish.py "$SONG" media/$NAME.mp4 work/segments --fps 30 --kbps 6000 --total $TOTAL --threads 4 --preset medium --title "兜一圈"
python3 scripts/finish.py "$SONG" variants/share/${NAME}_share.mp4 work/segments --fps 30 --kbps 2200 --share --total $TOTAL --threads 4 --preset medium --title "兜一圈"
python3 scripts/qc_audio.py "$SONG" media/$NAME.mp4
python3 scripts/qc_audio.py "$SONG" variants/share/${NAME}_share.mp4
rm -f work/qc/frames/*.jpg
ffmpeg -v error -y -i media/$NAME.mp4 -vf "fps=1/4,scale=216:384" work/qc/frames/f_%03d.jpg
python3 scripts/sheet.py thumbs/${NAME}_sheet.jpg 11 216 work/qc/frames/f_*.jpg
