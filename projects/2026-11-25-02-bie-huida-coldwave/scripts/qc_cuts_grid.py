#!/usr/bin/env python3
"""Hard cuts of the film against the tracked beat grid (the tempo drifts, so no constant BPM).

  qc_cuts_grid.py FILM [SCENE_THRESHOLD]
Finds hard cuts with ffmpeg's scene detector and prints each with the nearest tracked beat (bar.beat) and the
offset in frames. Fades and white flashes can also trigger; they are labelled when they match a STATIC point.
"""
import json
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, 'scripts')
import timeline as T

film = sys.argv[1]
thr = sys.argv[2] if len(sys.argv) > 2 else '0.30'
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', film, '-vf', f"select='gt(scene,{thr})',showinfo", '-an', '-f', 'null', '-'],
                   capture_output=True, text=True, errors='replace')
cuts = [float(m) for m in re.findall(r'pts_time:([0-9.]+)', r.stderr)]
flashes = list(T.STATIC_BURST) + list(T.STATIC_BED) + [50.30]
plan = sorted(s.t0 for s in __import__('shots').SHOTS)
bad = 0
for t in cuts:
    i = int(np.argmin(abs(T.BEATS - t)))
    k = max(j for j, bi in enumerate(T.BAR_IDX) if bi <= i)
    off = (t - T.BEATS[i]) * T.FPS
    tag = ''
    if min(abs(np.array(flashes) - t)) < 0.09 or min(abs(np.array(flashes) + 1 / 24 - t)) < 0.05:
        tag = '  (static flash / frame slip)'
    elif min(abs(np.array(plan) - t)) < 0.05:
        tag = '  shot cut'
    flag = '' if abs(off) <= 1.01 or tag.startswith('  (') else '   <-- off the grid'
    bad += bool(flag)
    print(f'{t:8.3f}s  bar {k + 1}.{i - T.BAR_IDX[k] + 1}  {off:+5.2f} frames{tag}{flag}')
print(len(cuts), 'detections,', bad, 'off the grid')
