#!/usr/bin/env python3
"""One frame per sung line, 0.15 s after its last unit starts, tiled into a sheet labelled with line numbers.

  qc_lines.py TIMING.json OUT.jpg [COLS]

For checking that every line is on screen, readable and not covered, without watching the whole film.
"""
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render  # noqa: E402

timing, out = sys.argv[1:3]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 12
R = render.Renderer(timing)
T = R.film.T
ims = []
for li in sorted(T):
    t = max(u[0] for u in T[li]) + 0.15
    im = cv2.resize(R.frame(int(round(t * render.FPS))), (216, 384), interpolation=cv2.INTER_AREA)
    cv2.putText(im, f'{li}', (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 255, 120), 2, cv2.LINE_AA)
    ims.append(im)
rows = []
for i in range(0, len(ims), cols):
    r = ims[i:i + cols]
    r += [np.zeros_like(ims[0])] * (cols - len(r))
    rows.append(np.concatenate(r, 1))
cv2.imwrite(out, np.concatenate(rows, 0)[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 85])
print(out, len(ims), 'lines')
