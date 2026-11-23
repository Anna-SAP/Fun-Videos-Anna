#!/usr/bin/env python3
"""One frame per sung performance, 0.15 s after its last unit lands -> contact sheet (checks layout of every line).

  qc_lines.py OUT.jpg [COLS]
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score  # noqa: E402
from kit import FPS, to8  # noqa: E402

out = sys.argv[1]
cols = int(sys.argv[2]) if len(sys.argv) > 2 else 12
tw, th = 216, 384
ss = score.shots()
rows = -(-len(ss) // cols)
sheet = np.zeros((rows * (th + 22), cols * tw, 3), np.uint8)
for k, s in enumerate(ss):
    t = min(max(s.line.times) + 0.15, s.t1 - 0.04)
    fi = int(round(t * FPS))
    im = to8(score.frame(fi / FPS, fi))
    r, c = divmod(k, cols)
    sheet[r * (th + 22) + 22:(r + 1) * (th + 22), c * tw:(c + 1) * tw] = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
    cv2.putText(sheet, f'{s.i} @{t:.1f}', (c * tw + 4, r * (th + 22) + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
cv2.imwrite(out, sheet[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 86])
print(out, len(ss))
