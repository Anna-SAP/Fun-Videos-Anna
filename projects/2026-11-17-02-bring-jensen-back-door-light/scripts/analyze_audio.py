#!/usr/bin/env python3
"""Measure the song: loudness curve, spectral balance, onsets, tempo, beat grid, key.

  analyze_audio.py MONO22K.wav OUT.json

numpy/scipy only. Everything here is a measurement to listen with, since the editor cannot hear.
"""
import json
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

src, out = sys.argv[1:3]
sr, x = wavfile.read(src)
x = x.astype(np.float32) / 32768
dur = len(x) / sr
N, HOP = 2048, 512
f, t, Z = signal.stft(x, sr, nperseg=N, noverlap=N - HOP, window='hann', padded=False, boundary=None)
M = np.abs(Z)
fps = sr / HOP
P = M ** 2


def band(lo, hi):
    return 10 * np.log10(P[(f >= lo) & (f < hi)].sum(0) + 1e-10)


rms = 10 * np.log10(P.sum(0) + 1e-10)
bands = {'sub_bass(30-120)': band(30, 120), 'bass(120-300)': band(120, 300), 'mid(300-2k)': band(300, 2000),
         'presence(2k-6k)': band(2000, 6000), 'air(6k-11k)': band(6000, 11000)}
centroid = (M * f[:, None]).sum(0) / (M.sum(0) + 1e-9)

# onset strength: half-wave rectified log-spectral flux
L = np.log1p(40 * M)
flux = np.maximum(L[:, 1:] - L[:, :-1], 0).sum(0)
flux = np.concatenate([[0], flux])
flux_d = flux - signal.medfilt(flux, 31)
flux_d = np.maximum(flux_d, 0)
# low-band flux (kick / bass notes) and high-band flux (hats, plucks)
lo_flux = np.concatenate([[0], np.maximum(L[f < 200][:, 1:] - L[f < 200][:, :-1], 0).sum(0)])
hi_flux = np.concatenate([[0], np.maximum(L[f > 4000][:, 1:] - L[f > 4000][:, :-1], 0).sum(0)])

# tempo from autocorrelation of onset envelope
o = flux_d - flux_d.mean()
ac = signal.correlate(o, o, mode='full')[len(o) - 1:]
ac /= ac[0]
lags = np.arange(len(ac)) / fps
cands = []
for bpm in np.arange(50, 180, .25):
    lag = 60 / bpm * fps
    # score a tempo by its lag and the 2x / 3x / 4x multiples
    s = sum(np.interp(lag * k, np.arange(len(ac)), ac) for k in (1, 2, 3, 4)) / 4
    cands.append((s, bpm))
cands.sort(reverse=True)
top = []
for s, bpm in cands:
    if all(abs(bpm - b) > 3 for _, b in top):
        top.append((round(float(s), 4), float(bpm)))
    if len(top) == 6:
        break

# key: chroma against Krumhansl profiles
A4 = 440
chroma = np.zeros((12, M.shape[1]), np.float32)
for i, fr in enumerate(f):
    if 60 < fr < 4000:
        pc = int(round(12 * np.log2(fr / A4) + 69)) % 12
        chroma[pc] += P[i]
names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
maj = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
mnr = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def key_of(c):
    c = c / (c.sum() + 1e-9)
    best = []
    for k in range(12):
        best.append((float(np.corrcoef(np.roll(maj, k), c)[0, 1]), names[k] + ' major'))
        best.append((float(np.corrcoef(np.roll(mnr, k), c)[0, 1]), names[k] + ' minor'))
    best.sort(reverse=True)
    return [(round(a, 3), b) for a, b in best[:3]]


def per_window(v, win, fn=np.mean):
    n = int(win * fps)
    return [round(float(fn(v[i:i + n])), 2) for i in range(0, len(v) - n + 1, n)]


res = {
    'duration': round(dur, 3), 'frame_rate': fps,
    'tempo_candidates': top,
    'key_overall': key_of(chroma.sum(1)),
    'key_by_30s': [key_of(chroma[:, int(a * fps):int((a + 30) * fps)].sum(1))[0] for a in range(0, int(dur) - 15, 30)],
    'rms_db_per_2s': per_window(rms, 2),
    'centroid_hz_per_2s': per_window(centroid, 2),
    'bands_db_per_4s': {k: per_window(v, 4) for k, v in bands.items()},
    'onset_density_per_4s': None,
}
# onset picking
thr = np.percentile(flux_d, 90) * .6
peaks, _ = signal.find_peaks(flux_d, height=thr, distance=int(.09 * fps))
on_t = peaks / fps
res['onsets'] = [round(float(a), 3) for a in on_t]
res['onset_strength'] = [round(float(flux_d[p]), 2) for p in peaks]
res['onset_density_per_4s'] = [int(((on_t >= a) & (on_t < a + 4)).sum()) for a in range(0, int(dur), 4)]
np.savez_compressed(out.replace('.json', '.npz'), flux=flux_d, lo_flux=lo_flux, hi_flux=hi_flux, rms=rms, centroid=centroid,
                    chroma=chroma, fps=fps, **{'band_' + k.split('(')[0]: v for k, v in bands.items()})
json.dump(res, open(out, 'w'), indent=1)
print('duration', res['duration'])
print('tempo', top)
print('key', res['key_overall'], res['key_by_30s'])
print('rms/2s', res['rms_db_per_2s'])
print('centroid/2s', [int(c) for c in res['centroid_hz_per_2s']])
for k, v in res['bands_db_per_4s'].items():
    print(k, [int(round(a)) for a in v])
print('onsets/4s', res['onset_density_per_4s'])
