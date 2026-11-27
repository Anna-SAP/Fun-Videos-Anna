#!/usr/bin/env python3
"""A picture of the whole song on the beat grid, one bar per row, so sections, gaps and stops can be read by eye.

  barmap.py BEATS.json FEAT.npz OUT.png [PHASE=0]

Each row is one bar (4 tracked beats, starting at beat PHASE + 4k), split into 64 columns (16th-note x4).
Three stacked strips per row: instrumental level (grey), vocal level (cyan), kick flux (red) + snare/hat flux (yellow).
Left margin: bar number and start time.
"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

B = np.array(json.load(open(sys.argv[1]))['beats'])
d = np.load(sys.argv[2])
out = sys.argv[3]
ph = int(sys.argv[4]) if len(sys.argv) > 4 else 0
R = float(d['rate'])
COLS, RH, LM = 64, 21, 120


def norm(a, lo, hi):
    return np.clip((a - lo) / (hi - lo), 0, 1)


inst = norm(d['inst'], np.percentile(d['inst'], 5), np.percentile(d['inst'], 99.5))
vox = norm(d['vox'], np.percentile(d['vox'], 30), np.percentile(d['vox'], 99.5))
kick = norm(d['kick'], 0, np.percentile(d['kick'], 99.7))
sn = norm(d['snare'] + d['hat'], 0, np.percentile(d['snare'] + d['hat'], 99.7))
bars = []
k = ph
while k + 4 < len(B):
    bars.append(k)
    k += 4
W = LM + COLS * 12
H = len(bars) * RH + 10
im = Image.new('RGB', (W, H), (10, 10, 14))
dr = ImageDraw.Draw(im)
font = ImageFont.load_default()
for r, k in enumerate(bars):
    y = r * RH + 4
    t0, t1 = B[k], B[k + 4]
    dr.text((4, y + 4), f'{r + 1:3d} {t0:6.2f}', fill=(220, 220, 220), font=font)
    for c in range(COLS):
        beat = c // 16
        a = B[k + beat] + (B[k + beat + 1] - B[k + beat]) * (c % 16) / 16
        b = B[k + beat] + (B[k + beat + 1] - B[k + beat]) * (c % 16 + 1) / 16
        i0, i1 = int(a * R), max(int(b * R), int(a * R) + 1)
        x = LM + c * 12
        g = int(255 * inst[i0:i1].mean())
        dr.rectangle([x, y, x + 11, y + 5], fill=(g, g, g))
        v = int(255 * vox[i0:i1].mean())
        dr.rectangle([x, y + 6, x + 11, y + 11], fill=(0, v, v))
        kk = int(255 * kick[i0:i1].max())
        ss = int(255 * sn[i0:i1].max())
        dr.rectangle([x, y + 12, x + 11, y + 17], fill=(kk, ss, 0))
    for beat in range(5):
        x = LM + beat * 16 * 12
        dr.line([x - 1, y, x - 1, y + 17], fill=(90, 90, 255) if beat % 4 == 0 else (60, 60, 90))
im.save(out)
print(out, len(bars), 'bars')
