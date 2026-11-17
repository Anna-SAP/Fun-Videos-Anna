#!/usr/bin/env python3
"""The whole song's vocal spectrogram in stacked rows with every on-screen unit's start marked, so the timing
can be checked by eye. Labels are entry ids only (no lyric text).

  timing_sheet.py OUT.jpg [SECONDS_PER_ROW=20] [PX_PER_SECOND=75]
"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import signal
from scipy.io import wavfile

out = sys.argv[1]
spr = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
pps = int(sys.argv[3]) if len(sys.argv) > 3 else 75
sr, x = wavfile.read('work/audio/vocals22k.wav')
x = x.astype(np.float32) / 32768.0
hop = sr // pps
f, t, Z = signal.stft(x, sr, nperseg=1024, noverlap=1024 - hop, padded=False, boundary=None)
band = (f > 150) & (f < 5000)
S = 20 * np.log10(np.abs(Z[band]) + 1e-6)
fb = f[band]
# log-frequency rows
rows_px = 110
lf = np.geomspace(150, 5000, rows_px)
idx = np.searchsorted(fb, lf).clip(0, len(fb) - 1)
S = S[idx][::-1]
lo, hi = np.percentile(S, 40), np.percentile(S, 99.7)
S = np.clip((S - lo) / (hi - lo), 0, 1)
tim = json.load(open('work/audio/lyric_timing.json'))
dur = len(x) / sr
nrows = int(np.ceil(dur / spr))
W = int(spr * pps) + 60
H = nrows * (rows_px + 34)
img = Image.new('RGB', (W, H), (8, 8, 10))
d = ImageDraw.Draw(img)
try:
    fnt = ImageFont.truetype('work/fonts/SpaceMonoR.ttf', 11)
except OSError:
    fnt = ImageFont.load_default()
for r in range(nrows):
    t0 = r * spr
    a, b = int(t0 * pps), int(min(dur, t0 + spr) * pps)
    seg = S[:, a:b]
    rgb = np.stack([seg ** 0.8 * 255, seg ** 1.1 * 200, seg ** 2 * 120], -1).astype(np.uint8)
    y0 = r * (rows_px + 34) + 16
    img.paste(Image.fromarray(rgb), (50, y0))
    d.text((4, y0 + 40), f'{t0:5.0f}s', fill=(150, 150, 150), font=fnt)
    for s in range(int(t0), int(t0 + spr) + 1):
        xx = 50 + (s - t0) * pps
        d.line([(xx, y0 + rows_px), (xx, y0 + rows_px + 4)], fill=(90, 90, 90))
    for e in tim:
        for k, u in enumerate(e['units']):
            if t0 <= u['s'] < t0 + spr:
                xx = 50 + (u['s'] - t0) * pps
                d.line([(xx, y0), (xx, y0 + rows_px)], fill=(80, 220, 255) if k else (255, 90, 90), width=1)
                if k == 0:
                    d.text((xx + 2, y0 - 14), e['id'], fill=(255, 140, 140), font=fnt)
img.save(out, quality=88)
print(out, img.size)
