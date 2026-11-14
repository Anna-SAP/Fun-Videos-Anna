#!/usr/bin/env python3
"""Check that every hard cut in the film sits on the beat grid.

  qc_cuts.py FILM BPM FIRST_BEAT_SECONDS [FPS] [SCENE_THRESHOLD]

Finds hard cuts with ffmpeg's scene detector, then prints each cut with the nearest beat and how many frames
off it is. Dissolves and fades are not hard cuts and will not show up, which is intended.
Defaults: FPS 24, threshold 0.30. If cuts are missing lower the threshold, if moving shots show up raise it.
"""
import re
import subprocess
import sys

film, bpm, first = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
fps = float(sys.argv[4]) if len(sys.argv) > 4 else 24.0
thr = sys.argv[5] if len(sys.argv) > 5 else '0.30'
beat = 60 / bpm

r = subprocess.run(['ffmpeg', '-hide_banner', '-i', film, '-vf', f"select='gt(scene,{thr})',showinfo", '-an', '-f', 'null', '-'],
                   capture_output=True, text=True, errors='replace')
cuts = [float(m) for m in re.findall(r'pts_time:([0-9.]+)', r.stderr)]
bad = 0
for t in cuts:
    n = round((t - first) / beat)
    off = (t - (first + n * beat)) * fps
    bar, b = n // 4 + 1, n % 4 + 1
    flag = '' if abs(off) <= 1.01 else '   <-- off the grid'
    bad += bool(flag)
    print(f'{t:8.3f}s  beat {n:4d} (bar {bar}, beat {b}, assuming 4/4)  {off:+5.2f} frames{flag}')
print(len(cuts), 'hard cuts,', bad, 'off the grid')
