#!/usr/bin/env python3
"""Draw the vocal band of a stretch of the song, wide enough to read word onsets off it.

  vocal_spectrogram.py MONO.wav OUT.png T0 T1 [PX_PER_SECOND] [MARKS.json]

200 px per second by default, 150 Hz - 6 kHz on a log axis, a tick every 0.1 s and a label every 0.5 s.
MARKS.json is optional: a list of [time, label] pairs drawn as vertical lines (for example the word starts
a recogniser gave), so the picture shows where the recogniser is early or late.

How to read it: a sung vowel is a stack of bright horizontal bands that starts abruptly; s / sh / t are a
bright smear above 3 kHz with nothing below. The start of a phrase is the first of either after a dark gap.
numpy, scipy and Pillow only.
"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import signal
from scipy.io import wavfile

src, out, t0, t1 = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
pps = int(sys.argv[5]) if len(sys.argv) > 5 else 200
marks = json.load(open(sys.argv[6], encoding='utf-8')) if len(sys.argv) > 6 else []

sr, x = wavfile.read(src)
if x.ndim > 1:
    x = x.mean(1)
x = x.astype(np.float32) / 32768
a, b = max(0, int((t0 - .2) * sr)), min(len(x), int((t1 + .2) * sr))
hop = max(1, sr // pps)
N = 1024
f, t, Z = signal.stft(x[a:b], sr, nperseg=N, noverlap=N - hop, window='hann', padded=False, boundary=None)
t = t + a / sr
M = 20 * np.log10(np.abs(Z) + 1e-6)
HGT = 360
fy = np.geomspace(150, min(6000, sr / 2 - 1), HGT)[::-1]
cols = (t >= t0) & (t <= t1)
img = np.stack([np.interp(fy, f, M[:, i]) for i in np.where(cols)[0]], 1)
lo, hi = np.percentile(img, 35), np.percentile(img, 99.7)
img = np.clip((img - lo) / (hi - lo), 0, 1) ** .8
rgb = np.stack([img * 255, img ** 1.6 * 235, img ** 3 * 160 + 18], -1).astype(np.uint8)
W = rgb.shape[1]
canvas = Image.new('RGB', (W, HGT + 46), (10, 10, 14))
canvas.paste(Image.fromarray(rgb), (0, 0))
d = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype('arial.ttf', 14)
except OSError:
    font = ImageFont.load_default()
tt = np.ceil(t0 * 10) / 10
while tt <= t1 + 1e-6:
    px = (tt - t0) / (t1 - t0) * (W - 1)
    major = abs(tt * 2 - round(tt * 2)) < 1e-6
    d.line((px, HGT, px, HGT + (12 if major else 5)), fill=(220, 220, 220))
    if major:
        d.line((px, 0, px, HGT), fill=(70, 70, 80))
        d.text((px + 3, HGT + 14), f'{tt:.1f}', font=font, fill=(230, 230, 230))
    tt = round(tt + .1, 1)
for mt, label in marks:
    if t0 <= mt <= t1:
        px = (mt - t0) / (t1 - t0) * (W - 1)
        d.line((px, 0, px, HGT), fill=(90, 220, 255))
        d.text((px + 3, 4), str(label), font=font, fill=(90, 220, 255))
for hz in (300, 1000, 3000):
    y = int(np.argmin(np.abs(fy - hz)))
    d.text((3, y - 8), f'{hz} Hz', font=font, fill=(150, 150, 160))
canvas.save(out)
print(out, canvas.size, f'{t0}-{t1}s at {pps} px/s')
