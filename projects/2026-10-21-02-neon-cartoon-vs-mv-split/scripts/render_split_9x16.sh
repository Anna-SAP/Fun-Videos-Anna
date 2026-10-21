#!/usr/bin/env bash
# Render a 9:16 top/bottom comparison video (1080x1920, 30 fps) from two clips.
#
#   render_split_9x16.sh TOP.mp4 BOTTOM.mkv OFFSET_SECONDS OUT_PREFIX
#
#   TOP       the reference clip (project 02: AI cartoon version) — defines duration
#   BOTTOM    the clip to sync to it (project 02: official MV)
#   OFFSET    how many seconds BOTTOM must be delayed so it lines up with TOP
#             (project 02: 0.0407 — measured with tools/av/find_offset.py)
#   output    OUT_PREFIX_fit.mp4  — full 16:9 frame in each half, blurred fill
#             OUT_PREFIX_crop.mp4 — each half centre-cropped to fill 1080x960
#
# Audio comes from BOTTOM (the official MV has the clean track), delayed by OFFSET
# and faded out over the last 0.4 s. Parameters are those used for the delivered
# NEON videos; this file packages the two ffmpeg commands from that session.
set -euo pipefail
TOP=$1; BOT=$2; OFF=$3; OUT=$4
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$TOP")
FADE_ST=$(python3 -c "print(round($DUR-0.4,3))")
DELAY_SAMPLES=$(python3 -c "print(round($OFF*48000))")
LEN=$(python3 -c "print($DUR+0.2)")
ENC=(-c:v libx264 -preset slow -crf 18 -profile:v high -r 30 -c:a aac -b:a 192k -ar 48000 -movflags +faststart)
AUDIO="[1:a]aresample=48000,adelay=${DELAY_SAMPLES}S:all=1,atrim=0:${DUR},afade=t=out:st=${FADE_ST}:d=0.4[a]"

# 1) fit: whole frame visible, empty space filled with a blurred, darkened copy
ffmpeg -v error -y -i "$TOP" -t "$LEN" -i "$BOT" -filter_complex "
[0:v]fps=30,setsar=1,split[c1][c2];
[c2]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,gblur=sigma=28,eq=brightness=-0.06[cbg];
[c1]scale=1080:-2:flags=lanczos[cfg];
[cbg][cfg]overlay=(W-w)/2:(H-h)/2[top];
[1:v]tpad=start_duration=${OFF}:start_mode=clone,fps=30,setsar=1,split[m1][m2];
[m2]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960,gblur=sigma=28,eq=brightness=-0.06[mbg];
[m1]scale=1080:-2:flags=lanczos[mfg];
[mbg][mfg]overlay=(W-w)/2:(H-h)/2[bot];
[top][bot]vstack,format=yuv420p[v];
${AUDIO}" -map "[v]" -map "[a]" -t "$DUR" "${ENC[@]}" "${OUT}_fit.mp4"

# 2) crop: each half fills 1080x960 (sides of a 16:9 frame are lost)
ffmpeg -v error -y -i "$TOP" -t "$LEN" -i "$BOT" -filter_complex "
[0:v]fps=30,setsar=1,scale=1080:960:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:960[top];
[1:v]tpad=start_duration=${OFF}:start_mode=clone,fps=30,setsar=1,scale=1080:960:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:960[bot];
[top][bot]vstack,format=yuv420p[v];
${AUDIO}" -map "[v]" -map "[a]" -t "$DUR" "${ENC[@]}" "${OUT}_crop.mp4"

echo "written ${OUT}_fit.mp4 and ${OUT}_crop.mp4"
