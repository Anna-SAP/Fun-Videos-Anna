#!/usr/bin/env python3
"""Fine tempo measurement per stretch: onset envelopes (low band = kick, full band) at 5 ms hop, autocorrelation
and comb-fit of beat period + phase.   tempo.py WAV22K [t0-t1,...]"""
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft

sr, x = wavfile.read(sys.argv[1])
x = x.astype(np.float32) / 32768
if x.ndim > 1:
    x = x.mean(1)
HOP = 110  # 5 ms @22050
f, t, Z = stft(x, sr, nperseg=1024, noverlap=1024 - HOP, boundary=None, padded=False)
M = np.log1p(40 * np.abs(Z))
def flux(lo, hi):
    b = (f >= lo) & (f < hi)
    d = np.diff(M[b], axis=1)
    return np.concatenate([[0], np.maximum(d, 0).sum(0)])
env = {'low': flux(30, 150), 'snare': flux(150, 2500), 'hi': flux(6000, 11000), 'full': flux(30, 11000)}
dt = HOP / sr
rng = [(0, len(x) / sr)] if len(sys.argv) < 3 else [tuple(map(float, r.split('-'))) for r in sys.argv[2].split(',')]
for t0, t1 in rng:
    print(f'--- {t0:.1f}-{t1:.1f}')
    for name, e in env.items():
        s = e[int(t0 / dt):int(t1 / dt)].copy()
        s -= s.mean()
        ac = np.correlate(s, s, 'full')[len(s) - 1:]
        ac /= ac[0] + 1e-9
        lags = np.arange(len(ac)) * dt
        m = (lags > 0.25) & (lags < 4.0)
        idx = np.where(m)[0]
        pk = [i for i in idx[1:-1] if ac[i] > ac[i - 1] and ac[i] >= ac[i + 1]]
        pk = sorted(pk, key=lambda i: -ac[i])[:8]
        print(f' {name:5s}', ' '.join(f'{lags[i]:.3f}s({ac[i]:.2f})' for i in sorted(pk)))
