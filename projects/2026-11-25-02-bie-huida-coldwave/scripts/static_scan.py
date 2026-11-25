#!/usr/bin/env python3
"""Find shortwave-radio static: broadband noise bursts (high spectral flatness across 1-11 kHz together with a
jump in wideband energy that lasts longer than a hi-hat). Writes work/audio/static_curve.npz and strip images
work/qc/static_NN.png (spectrogram 0-11 kHz, flatness curve in red, wideband energy in green).

  static_scan.py [MIX22K]
"""
import sys
import numpy as np
from PIL import Image, ImageDraw
from scipy.io import wavfile
from scipy.signal import stft
from scipy.ndimage import uniform_filter1d, median_filter

src = sys.argv[1] if len(sys.argv) > 1 else 'work/audio/mono22k.wav'
sr, x = wavfile.read(src)
x = x.astype(np.float32) / 32768
if x.ndim > 1:
    x = x.mean(1)
HOP = 220   # 10 ms
f, t, Z = stft(x, sr, nperseg=1024, noverlap=1024 - HOP, boundary=None, padded=False)
P = np.abs(Z) ** 2 + 1e-12
fps = sr / HOP
b = (f >= 1000) & (f < 10500)
flat = np.exp(np.log(P[b]).mean(0)) / P[b].mean(0)
wide = 10 * np.log10(P[b].sum(0))
flat_s = uniform_filter1d(flat, 15)            # 150 ms
wide_s = uniform_filter1d(wide, 15)
base = median_filter(wide_s, size=int(6 * fps))   # local 6 s median
np.savez('work/audio/static_curve.npz', fps=fps, flat=flat_s, wide=wide_s, base=base)
# strips
S = 10 * np.log10(P[f < 11000])
S = np.clip((S - (S.max() - 80)) / 80, 0, 1)
W = 30
for k in range(int(np.ceil(t[-1] / W))):
    a, e = int(k * W * fps), min(int((k + 1) * W * fps), len(flat_s) - 1)
    img = (255 * S[::-1, a:e]).astype(np.uint8)
    im = Image.fromarray(img).resize(((e - a) * 2, 300)).convert('RGB')
    dr = ImageDraw.Draw(im)
    for i in range(a, e - 1):
        xx = (i - a) * 2
        dr.line([xx, 300 - flat_s[i] * 600, xx + 2, 300 - flat_s[i + 1] * 600], fill=(255, 60, 60))
        dr.line([xx, 150 - (wide_s[i] - base[i]) * 8, xx + 2, 150 - (wide_s[i + 1] - base[i + 1]) * 8], fill=(60, 255, 60))
    for s in range(k * W, (k + 1) * W + 1):
        xx = int((s - k * W) * fps * 2)
        dr.line([xx, 0, xx, 8 if s % 5 else 20], fill=(255, 255, 0))
        if s % 5 == 0:
            dr.text((xx + 2, 10), str(s), fill=(255, 255, 0))
    im.save(f'work/qc/static_{k:02d}.png')
print('flatness percentiles', np.percentile(flat_s, [50, 90, 99, 99.9]).round(3))
