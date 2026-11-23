#!/usr/bin/env python3
"""Vocal onset peaks in a time range of the separated vocal stem (for hand-timing chants).

  onsets.py T0 T1 [THRESH]

Prints each peak's time, strength and the vocal level just after it. Spectral flux of the log spectrum,
150 Hz - 6 kHz, 10 ms hop.
"""
import sys

import numpy as np
import soundfile as sf
from scipy import signal

t0, t1 = float(sys.argv[1]), float(sys.argv[2])
th = float(sys.argv[3]) if len(sys.argv) > 3 else 0.3
voc, sr = sf.read('work/audio/vocals16k.wav', dtype='float32')
f, tt, Z = signal.stft(voc, sr, nperseg=1024, noverlap=1024 - 160, boundary=None, padded=False)
A = np.abs(Z[(f > 150) & (f < 6000)])
L = np.log1p(50 * A)
flux = np.concatenate([[0], np.maximum(L[:, 1:] - L[:, :-1], 0).sum(0)])
ft = (np.arange(len(flux)) * 160 + 512) / sr
flux = flux / (np.percentile(flux, 98) + 1e-9)
lev = 10 * np.log10((A ** 2).sum(0) + 1e-9)
pk, _ = signal.find_peaks(flux, height=th, distance=6)
for i in pk:
    if t0 <= ft[i] <= t1:
        print(f'{ft[i]:8.2f}  {flux[i]:.2f}  lev {lev[i:i + 8].mean():6.1f}  ' + '#' * int(flux[i] * 20))
