#!/usr/bin/env python3
"""Spectrogram strip for reading by eye: strip.py WAV22K T0 T1 OUT.png [PX_PER_S=100] [MARKS_JSON]
Linear 0-11 kHz, 360 px tall; yellow ticks every second (labels every 1 s), cyan ticks at tracked beats
(long tick = bar line from work/audio/bars.json if present)."""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy.io import wavfile
from scipy.signal import stft
wav, t0, t1, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
pps = float(sys.argv[5]) if len(sys.argv) > 5 else 100
sr, x = wavfile.read(wav)
x = x.astype(np.float32) / 32768
if x.ndim > 1: x = x.mean(1)
seg = x[int(t0 * sr):int(t1 * sr)]
hop = int(sr / pps)
f, t, Z = stft(seg, sr, nperseg=1024, noverlap=1024 - hop, boundary=None, padded=False)
S = 20 * np.log10(np.abs(Z[f < 11000]) + 1e-9)
S = np.clip((S - (np.percentile(S, 99.5) - 70)) / 70, 0, 1)[::-1]
H = 360
im = Image.fromarray((255 * S).astype(np.uint8)).resize((int((t1 - t0) * pps), H)).convert('RGB')
W = im.width
im2 = Image.new('RGB', (W, H + 30), (0, 0, 0)); im2.paste(im, (0, 30)); dr = ImageDraw.Draw(im2)
for s in np.arange(np.ceil(t0), t1):
    xx = (s - t0) * pps; dr.line([xx, 0, xx, 12], fill=(255, 255, 0)); dr.text((xx + 2, 0), f'{s:.0f}', fill=(255, 255, 0))
if os.path.exists('work/audio/bars.json'):
    bj = json.load(open('work/audio/bars.json'))
    for b in bj['beats']:
        if t0 <= b <= t1:
            xx = (b - t0) * pps; dr.line([xx, 18, xx, 26], fill=(0, 200, 255))
    for k, b in enumerate(bj['bars']):
        if t0 <= b <= t1:
            xx = (b - t0) * pps; dr.line([xx, 14, xx, 30], fill=(255, 80, 80)); dr.text((xx + 2, 14), f'b{k+1}', fill=(255, 120, 120))
if len(sys.argv) > 6:
    for tt, lab in json.load(open(sys.argv[6])):
        if t0 <= tt <= t1:
            xx = (tt - t0) * pps; dr.line([xx, 30, xx, H + 30], fill=(0, 255, 0)); dr.text((xx + 2, 32), lab, fill=(0, 255, 0))
im2.save(out)
