#!/usr/bin/env python3
"""Per-frame drum and vocal envelopes for the renderer, measured from the separated stems.

  drums.py   ->  work/audio/env.npz  (+ prints a per-bar summary)

kick  : onset strength 35-140 Hz of the accompaniment stem
snare : onset strength 180-400 Hz + 1.5-5 kHz (broadband crack) of the accompaniment stem
hat   : onset strength 7-14 kHz of the accompaniment stem
voc   : RMS of the vocal stem
All are sampled at 24 fps (one value per output frame), normalised to their 99th percentile.
Onset lists (frame indices of local peaks above a threshold) are stored too, so effects can fire exactly on
measured hits instead of an assumed pattern.
"""
import sys

import numpy as np
import soundfile as sf
from scipy import signal

sys.path.insert(0, 'scripts')
from common import FPS, NFRAMES, T0, BEAT  # noqa: E402

acc, sr = sf.read('work/sep/htdemucs/stereo/no_vocals.wav', dtype='float32')
voc, _ = sf.read('work/sep/htdemucs/stereo/vocals.wav', dtype='float32')
acc = acc.mean(1)
voc = voc.mean(1)
N, HOP = 2048, 256
f, t, Z = signal.stft(acc, sr, nperseg=N, noverlap=N - HOP, window='hann', padded=False, boundary=None)
M = np.log1p(30 * np.abs(Z))
fr = sr / HOP


def flux(lo, hi):
    b = M[(f >= lo) & (f < hi)]
    d = np.maximum(b[:, 1:] - b[:, :-1], 0).sum(0)
    return np.concatenate([[0], d])


def per_frame(x):
    # max over each output frame's window
    out = np.zeros(NFRAMES, np.float32)
    for i in range(NFRAMES):
        a = int(i / FPS * fr)
        b = int((i + 1) / FPS * fr) + 1
        seg = x[a:b]
        out[i] = seg.max() if len(seg) else 0
    p = np.percentile(out, 99)
    return np.clip(out / (p + 1e-9), 0, 1.5)


kick = per_frame(flux(35, 140))
snare = per_frame(flux(180, 400) * 0.5 + flux(1500, 5000))
hat = per_frame(flux(7000, 14000))
hop = int(sr / FPS)
vr = np.array([np.sqrt(np.mean(voc[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(NFRAMES)], np.float32)
vdb = 20 * np.log10(vr + 1e-9)
vocal = np.clip((vdb + 45) / 30, 0, 1)


def peaks(x, thr, mind=4):
    p, _ = signal.find_peaks(x, height=thr, distance=mind)
    return p.astype(np.int32)


kp, sp, hp = peaks(kick, 0.45), peaks(snare, 0.45), peaks(hat, 0.5, 2)
np.savez('work/audio/env.npz', kick=kick, snare=snare, hat=hat, vocal=vocal, kick_on=kp, snare_on=sp, hat_on=hp)
print('kicks', len(kp), 'snares', len(sp), 'hats', len(hp))
# per bar summary: 16 cells (sixteenths): K for kick, S snare, x both, . none
bar_frames = int(round(4 * BEAT * FPS))
f0 = int(round(T0 * FPS))
ks, ss = set(kp.tolist()), set(sp.tolist())
for b in range(110):
    cells = ''
    for c in range(16):
        a = f0 + b * bar_frames + int(c * bar_frames / 16)
        rng = range(a - 1, a + 3)
        k = any(i in ks for i in rng)
        s = any(i in ss for i in rng)
        cells += 'x' if k and s else 'K' if k else 'S' if s else '.'
    print(f'{b + 1:3d} {cells}')
