#!/usr/bin/env python3
"""Per-video-frame audio envelopes that drive the wall's power.

  features.py STEREO44K.wav INST44K.wav OUT.npz FPS

kick : low-band (35-150 Hz) onset strength of the instrumental, peak-normalised, with a fast attack
snare: 1.5-6 kHz onset strength of the instrumental (snares, claps, hats)
sub  : 30-120 Hz energy of the instrumental in dB (tells where the drums/808 drop out)
rms  : full-mix level in dB
voc  : vocal-stem level in dB (vocals = mix - inst)
"""
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

mix_p, inst_p, out, fps = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
sr, mix = wavfile.read(mix_p)
_, inst = wavfile.read(inst_p)
mix = mix.astype(np.float32).mean(1) / 32768
inst = inst.astype(np.float32).mean(1) / 32768
voc = mix - inst
n = len(mix)
nf = int(np.ceil(n / sr * fps))
HOP = 256
N = 2048
f, t, Z = signal.stft(inst, sr, nperseg=N, noverlap=N - HOP, boundary=None, padded=False)
M = np.abs(Z)
L = np.log1p(30 * M)


def band_flux(lo, hi):
    b = L[(f >= lo) & (f < hi)]
    fl = np.concatenate([[0], np.maximum(b[:, 1:] - b[:, :-1], 0).sum(0)])
    return fl


def to_frames(x, tt, how='max'):
    out = np.zeros(nf, np.float32)
    idx = np.clip((tt * fps).astype(int), 0, nf - 1)
    if how == 'max':
        np.maximum.at(out, idx, x)
    else:
        s = np.zeros(nf)
        c = np.zeros(nf)
        np.add.at(s, idx, x)
        np.add.at(c, idx, 1)
        out = (s / np.maximum(c, 1)).astype(np.float32)
        # fill gaps
        for i in range(1, nf):
            if c[i] == 0:
                out[i] = out[i - 1]
    return out


tt = (np.arange(M.shape[1]) * HOP + N / 2) / sr
k = band_flux(35, 150)
s = band_flux(1500, 6000)
k = to_frames(k, tt)
s = to_frames(s, tt)


def norm_env(x, decay):
    x = x / (np.percentile(x[x > 0], 99) + 1e-9)
    x = np.clip(x, 0, 1.5)
    y = np.zeros_like(x)
    a = np.exp(-1 / (decay * fps))
    for i in range(len(x)):
        y[i] = max(x[i], (y[i - 1] if i else 0) * a)
    return y


kick = norm_env(k, 0.12)
snare = norm_env(s, 0.08)
sub_e = (M[(f >= 30) & (f < 120)] ** 2).sum(0)
sub = 10 * np.log10(to_frames(sub_e, tt, 'mean') + 1e-10)


def level(x):
    w = int(sr / fps)
    m = np.zeros(nf, np.float32)
    for i in range(nf):
        seg = x[i * w:(i + 1) * w]
        m[i] = 10 * np.log10((seg ** 2).mean() + 1e-10) if len(seg) else -100
    return m


rms = level(mix)
vl = level(voc)
np.savez(out, kick=kick, snare=snare, sub=sub.astype(np.float32), rms=rms, voc=vl, fps=fps)
print('frames', nf, 'kick>0.5', int((kick > 0.5).sum()), 'snare>0.5', int((snare > 0.5).sum()))
