#!/usr/bin/env python3
"""Whole-song chart for reading by eye: sustained wideband noise floor of the instrumental stem
(1-10.5 kHz energy under a 0.5 s minimum filter: a noise snare decays inside 0.4 s and vanishes, held static stays),
its flatness, instrumental low-band (kick/bass) level and vocal level. work/qc/noise_floor.png"""
import json
import numpy as np
from PIL import Image, ImageDraw
from scipy.io import wavfile
from scipy.signal import stft
from scipy.ndimage import minimum_filter1d, uniform_filter1d
def load(p):
    sr, x = wavfile.read(p); x = x.astype(np.float32) / 32768
    return sr, (x.mean(1) if x.ndim > 1 else x)
sr, x = load('work/audio/inst22k.wav')
HOP = 220; fps = sr / HOP
f, t, Z = stft(x, sr, nperseg=1024, noverlap=1024 - HOP, boundary=None, padded=False)
P = np.abs(Z) ** 2 + 1e-12
b = (f >= 1000) & (f < 10500)
wide = 10 * np.log10(P[b].sum(0))
flat = np.exp(np.log(P[b]).mean(0)) / P[b].mean(0)
floor = minimum_filter1d(wide, int(0.5 * fps))
flatfl = minimum_filter1d(uniform_filter1d(flat, 10), int(0.5 * fps))
lowb = (f >= 30) & (f < 150)
low = uniform_filter1d(10 * np.log10(P[lowb].sum(0)), 20)
_, v = load('work/audio/vocals22k.wav')
_, _, Zv = stft(v, sr, nperseg=1024, noverlap=1024 - HOP, boundary=None, padded=False)
vox = uniform_filter1d(10 * np.log10((np.abs(Zv) ** 2).sum(0) + 1e-12), 20)
np.savez('work/audio/noise_floor.npz', fps=fps, floor=floor, flatfl=flatfl, low=low, vox=vox, wide=wide)
PX = 8  # px per second
W = int(t[-1] * PX) + 60
H = 520
im = Image.new('RGB', (W, H), (12, 12, 12)); dr = ImageDraw.Draw(im)
def plot(y, lo, hi, y0, h, col):
    yy = np.clip((y - lo) / (hi - lo), 0, 1)
    step = max(1, int(fps / PX))
    pts = [(30 + i / fps * PX, y0 + h - yy[i] * h) for i in range(0, len(y), step)]
    dr.line(pts, fill=col)
    dr.text((2, y0), f'{hi}', fill=col); dr.text((2, y0 + h - 10), f'{lo}', fill=col)
plot(floor, -70, -20, 20, 120, (255, 255, 255))
plot(flatfl, 0, 0.6, 150, 100, (255, 90, 90))
plot(low, -50, 0, 260, 110, (90, 200, 255))
plot(vox, -60, 0, 380, 110, (120, 255, 120))
for s in range(0, int(t[-1]) + 1, 5):
    xx = 30 + s * PX
    dr.line([xx, 0, xx, 12 if s % 10 else 18], fill=(255, 255, 0))
    if s % 10 == 0: dr.text((xx + 2, 0), str(s), fill=(255, 255, 0))
im.save('work/qc/noise_floor.png')
print(W)
