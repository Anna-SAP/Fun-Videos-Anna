#!/usr/bin/env bash
# Cut video A's hair shots into the clips that went to Kling 4.0 Video Edit (via Figma Weave).
#
#   prepare_uploads.sh VIDEO_A OUT_DIR
#
# Frame-exact cuts (video A is 30 fps), scaled 1276x718 -> 1280x720 (Kling wants >= 700 px each way),
# no audio, last frame held up to a whole second: Kling bills and returns whole seconds, and an
# input whose length matches the requested duration keeps the edit on video A's timing.
#
#   shot1  frames   0-81   solo doll, push-in to the two-doll close-up  82 -> 90 frames (3 s)
#   clip1  frames   0-137  shot1 + pale-bg two shot + face/hand close   138 -> 150 (5 s)
#   clip2  frames 219-474  3-frame flash + the two-doll dance           256 -> 270 (9 s)
#   clip3  frames 527-690  close dance -> group formation               164 -> 180 (6 s)
#
# Frames 138-218 (hands) and 475-526 (A2O / "Stage 1" graphics) have no hair and are never sent.
set -euo pipefail
a=$1; out=$2
mkdir -p "$out"

cut() {   # first_frame end_frame(exclusive) held_frames name
  ffmpeg -v error -y -i "$a" \
    -vf "trim=start_frame=$1:end_frame=$2,setpts=PTS-STARTPTS,scale=1280:720:flags=lanczos,setsar=1,tpad=stop=$3:stop_mode=clone,format=yuv420p" \
    -an -c:v libx264 -preset slow -crf 12 -r 30 "$out/$4.mp4"
}

cut   0  82  8 shot1_3s_f000-081
cut   0 138 12 clip1_intro_5s_f000-137
cut 219 475 14 clip2_dance_9s_f219-474
cut 527 691 16 clip3_finale_6s_f527-690
echo "written to $out"
