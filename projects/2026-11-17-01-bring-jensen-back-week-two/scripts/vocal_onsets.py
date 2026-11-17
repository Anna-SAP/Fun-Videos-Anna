#!/usr/bin/env python3
"""Syllable onsets of the vocal stem in [T0, T1]: spectral flux 150 Hz-6 kHz, peaks >= MIN_GAP apart.

  vocal_onsets.py T0 T1 [MIN_GAP=0.12] [N]

Used where forced alignment cannot tell repeated chants apart (the drop): the N strongest onsets, in time
order, are printed so they can be assigned to the sung units one by one.
"""
import sys

import numpy as np
import soundfile as sf
from scipy import signal

t0, t1 = float(sys.argv[1]), float(sys.argv[2])
gap = float(sys.argv[3]) if len(sys.argv) > 3 else 0.12
n = int(sys.argv[4]) if len(sys.argv) > 4 else None
x, sr = sf.read('work/audio/vocals22k.wav', dtype='float32')
seg = x[int((t0 - 0.2) * sr):int((t1 + 0.2) * sr)]
f, t, Z = signal.stft(seg, sr, nperseg=1024, noverlap=1024 - 128, padded=False, boundary=None)
M = np.log1p(40 * np.abs(Z[(f > 150) & (f < 6000)]))
fl = np.concatenate([[0], np.maximum(M[:, 1:] - M[:, :-1], 0).sum(0)])
fl = signal.savgol_filter(fl, 5, 2)
tt = t + t0 - 0.2 + 512 / sr
pk, pr = signal.find_peaks(fl, distance=max(1, int(gap * sr / 128)), prominence=np.percentile(fl, 60) * 0.3)
cand = [(tt[i], fl[i]) for i in pk if t0 <= tt[i] <= t1]
if n:
    cand = sorted(sorted(cand, key=lambda c: -c[1])[:n])
print(len(cand), 'onsets')
print(' '.join(f'{c[0]:.2f}' for c in cand))
