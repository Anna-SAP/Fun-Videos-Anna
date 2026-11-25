#!/usr/bin/env python3
"""Audio features for the picture, from the separated instrumental (drums) and vocal stems.

  feat.py INST22K.wav VOCALS22K.wav MIX22K.wav OUT.npz

Writes 200 Hz envelopes: kick (30-150 Hz flux), snare (150-2500 Hz flux weighted with 2.5-8 kHz), hat (7-11 kHz
flux), loud (mix RMS dB), low (instrumental 30-150 Hz energy dB), vox (vocal RMS dB), and peak lists
(kick_t, snare_t) picked from the flux curves. Everything in the film that moves on the beat reads these, so
the picture follows the drums that were actually played, not an assumed grid.
"""
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft, find_peaks

def load(p):
    sr, x = wavfile.read(p)
    x = x.astype(np.float32) / 32768
    return sr, (x.mean(1) if x.ndim > 1 else x)

sr, inst = load(sys.argv[1])
_, vox = load(sys.argv[2])
_, mix = load(sys.argv[3])
HOP = 110            # 4.99 ms -> ~200.45 Hz
RATE = sr / HOP
def spec(x):
    f, t, Z = stft(x, sr, nperseg=1024, noverlap=1024 - HOP, boundary='zeros', padded=True)
    return f, np.abs(Z)
f, A = spec(inst)
M = np.log1p(40 * A)
def flux(lo, hi):
    b = (f >= lo) & (f < hi)
    return np.concatenate([[0], np.maximum(np.diff(M[b], axis=1), 0).sum(0)]).astype(np.float32)
def edb(A, lo, hi):
    b = (f >= lo) & (f < hi)
    return (10 * np.log10((A[b] ** 2).sum(0) + 1e-9)).astype(np.float32)
kick = flux(30, 150)
snare = flux(150, 2500) * 0.5 + flux(2500, 8000)
hat = flux(7000, 11000)
_, Am = spec(mix)
_, Av = spec(vox)
out = dict(rate=RATE, kick=kick, snare=snare, hat=hat, low=edb(A, 30, 150), loud=edb(Am, 30, 11000),
           vox=edb(Av, 100, 8000), inst=edb(A, 30, 11000))
def peaks(e, rel, dist):
    thr = np.percentile(e, 99) * rel
    p, _ = find_peaks(e, height=thr, distance=int(dist * RATE))
    return (p / RATE).astype(np.float32), e[p]
out['kick_t'], out['kick_v'] = peaks(kick, 0.35, 0.12)
out['snare_t'], out['snare_v'] = peaks(snare, 0.40, 0.12)
np.savez(sys.argv[4], **out)
print('rate', RATE, 'kicks', len(out['kick_t']), 'snares', len(out['snare_t']))
