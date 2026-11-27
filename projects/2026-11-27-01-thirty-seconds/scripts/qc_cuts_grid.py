#!/usr/bin/env python3
"""Hard cuts of the film against the tracked beat grid (the tempo drifts, so no constant BPM) and the shot list.

  qc_cuts_grid.py FILM [SCENE_THRESHOLD=0.30]

Finds hard cuts with ffmpeg's scene detector; for each prints the nearest planned cut (timeline.SHOTS), the
nearest tracked beat or eighth (bar.beat) and the offsets in frames. Detections that are not planned cuts are
listed separately (white hits on the downbeats, the explosion and stamps can trigger the detector).
"""
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, 'scripts')
import timeline as T  # noqa: E402

film = sys.argv[1]
thr = sys.argv[2] if len(sys.argv) > 2 else '0.30'
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', film, '-vf', f"select='gt(scene,{thr})',showinfo", '-an', '-f', 'null', '-'],
                   capture_output=True, text=True, errors='replace')
det = [float(m) for m in re.findall(r'pts_time:([0-9.]+)', r.stderr)]
plan = np.array([s.t0 for s in T.SHOTS[1:]])
grid = np.sort(np.concatenate([T.BEATS, (T.BEATS[:-1] + T.BEATS[1:]) / 2]))
matched, other = [], []
for t in det:
    j = int(np.argmin(abs(plan - t)))
    if abs(plan[j] - t) * T.FPS <= 1.01:
        matched.append((t, j))
    else:
        other.append(t)
print(f'detected {len(det)}; matching a planned cut (within 1 frame): {len(matched)} of {len(plan)} planned')
worst = 0.0
stops = [a for a, b in T.STOPS]
for t, j in matched:
    g = float(grid[int(np.argmin(abs(grid - plan[j])))])
    off = (plan[j] - g) * T.FPS
    on_stop = any(abs(plan[j] - s) < 0.05 for s in stops)
    if not on_stop:
        worst = max(worst, abs(off))
    i = int(np.argmin(abs(T.BEATS - g)))
    print(f'  {t:8.3f}  shot {T.SHOTS[j + 1].id}  grid {i // 4 + 1}.{i % 4 + 1}  plan-grid {off:+.2f} f' + ('  (cut on a measured stop)' if on_stop else ''))
missed = [T.SHOTS[j + 1].id for j in range(len(plan)) if j not in {m[1] for m in matched}]
print(f'max |planned cut - beat/eighth grid| = {worst:.2f} frames (excluding the two cuts placed on measured stops)')
print('planned cuts not detected (dissolve-like or same-looking plates):', missed)
print('other detections (hits, flashes):', [round(x, 2) for x in other])
