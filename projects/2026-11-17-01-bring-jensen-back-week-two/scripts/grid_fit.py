#!/usr/bin/env python3
"""Fit a beat grid (BPM + phase) to one stretch of the accompaniment stem.

  grid_fit.py T_START T_END [BPM_LO BPM_HI]

Onset strength = spectral flux of the instrumental stem in the kick band (35-140 Hz) and the snare crack
(1.5-5 kHz). For every candidate tempo and phase, score = mean onset strength on the beats, with beats 2 and 4
weighted by snare and 1 and 3 by kick, so the fit also says where bar lines fall.
"""
import sys

import numpy as np
import soundfile as sf
from scipy import signal

t0, t1 = float(sys.argv[1]), float(sys.argv[2])
lo, hi = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else (80.0, 92.0)
x, sr = sf.read('work/sep/inst.wav', dtype='float32')
x = x.mean(1)
N, HOP = 2048, 256
f, t, Z = signal.stft(x, sr, nperseg=N, noverlap=N - HOP, padded=False, boundary=None)
M = np.log1p(30 * np.abs(Z))
fr = sr / HOP


def flux(a, b):
    m = M[(f >= a) & (f < b)]
    return np.concatenate([[0], np.maximum(m[:, 1:] - m[:, :-1], 0).sum(0)])


K = flux(35, 140)
S = flux(1500, 5000)
K /= np.percentile(K, 99)
S /= np.percentile(S, 99)
times = np.arange(len(K)) / fr + (N / 2) / sr


def val(arr, ts):
    i = np.clip(np.round((ts - (N / 2) / sr) * fr).astype(int), 0, len(arr) - 1)
    # max within +-1 frame
    return np.maximum(np.maximum(arr[i], arr[np.clip(i - 1, 0, None)]), arr[np.clip(i + 1, None, len(arr) - 1)])


best = None
for bpm in np.arange(lo, hi, 0.01):
    p = 60 / bpm
    for ph in np.arange(0, 4 * p, 0.005):
        beats = np.arange(t0 + ph, t1, p)
        if len(beats) < 8:
            continue
        idx = np.arange(len(beats)) % 4
        sc = np.where(idx % 2 == 1, val(S, beats), val(K, beats)).mean()
        if best is None or sc > best[0]:
            best = (sc, bpm, ph)
sc, bpm, ph = best
p = 60 / bpm
first = t0 + ph
# express the downbeat as the earliest bar line >= 0 on this grid
d0 = first - np.floor(first / (4 * p)) * 4 * p
print(f'{t0:.1f}-{t1:.1f}: {bpm:.2f} BPM, beat {p:.4f}s, first downbeat in range {first:.3f}s, '
      f'grid origin {d0:.3f}s, score {sc:.3f}')
