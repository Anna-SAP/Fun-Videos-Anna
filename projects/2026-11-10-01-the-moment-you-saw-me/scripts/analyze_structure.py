#!/usr/bin/env python3
"""Second listening pass: beat grid, bar-by-bar chords and arrangement, self-similarity, lead-melody range.

  analyze_structure.py STEREO44K.wav OUT.json
"""
import json
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

src, out = sys.argv[1:3]
sr, st = wavfile.read(src)
st = st.astype(np.float32) / 32768
mid, side = st.mean(1), (st[:, 0] - st[:, 1]) / 2
dur = len(mid) / sr
N, HOP = 4096, 512
f, t, Z = signal.stft(mid, sr, nperseg=N, noverlap=N - HOP, window='hann', padded=False, boundary=None)
M = np.abs(Z)
fps = sr / HOP
_, _, Zs = signal.stft(side, sr, nperseg=N, noverlap=N - HOP, window='hann', padded=False, boundary=None)
Ms = np.abs(Zs)

L = np.log1p(40 * M)
flux = np.concatenate([[0], np.maximum(L[:, 1:] - L[:, :-1], 0).sum(0)])
flux = np.maximum(flux - signal.medfilt(flux, 41), 0)

# ---- beat grid: search period and phase that best explain the onset envelope
best = (-1, 0, 0)
tt = np.arange(len(flux)) / fps
for bpm in np.arange(70.0, 74.0, .01):
    per = 60 / bpm
    for ph in np.arange(0, per, .01):
        idx = np.round((np.arange(ph, dur - 1, per)) * fps).astype(int)
        s = flux[idx].mean() + .5 * flux[np.minimum(idx + int(per / 2 * fps), len(flux) - 1)].mean()
        if s > best[0]:
            best = (s, bpm, ph)
_, bpm, ph = best
per = 60 / bpm
print(f'beat grid: {bpm:.2f} BPM, period {per:.4f}s, phase {ph:.3f}s')

# ---- downbeat: which of the 4 beat phases carries the most low-end attack
lo = np.log1p(40 * M[f < 150])
lo_flux = np.concatenate([[0], np.maximum(lo[:, 1:] - lo[:, :-1], 0).sum(0)])
beats = np.arange(ph, dur - .5, per)
bi = np.round(beats * fps).astype(int)
scores = [float(np.mean([lo_flux[max(0, i - 2):i + 3].max() for i in bi[k::4]])) for k in range(4)]
print('low-end attack by beat-in-bar phase', [round(s, 2) for s in scores])
k0 = int(np.argmax(scores))
down = beats[k0::4]
if down[0] - 4 * per > -0.05:
    down = np.concatenate([[down[0] - 4 * per], down])
bar = 4 * per
print(f'bar length {bar:.3f}s, first downbeat {down[0]:.3f}s, {len(down)} bars')

# ---- per-bar description
names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
P = M ** 2


def chroma_of(a, b, flo, fhi):
    c = np.zeros(12)
    i0, i1 = int(a * fps), max(int(a * fps) + 1, int(b * fps))
    seg = P[:, i0:i1].sum(1)
    for i, fr in enumerate(f):
        if flo < fr < fhi:
            c[int(round(12 * np.log2(fr / 440) + 69)) % 12] += seg[i]
    return c


def chord(c):
    c = c / (c.sum() + 1e-12)
    best = []
    for r in range(12):
        for nm, iv in (('', (0, 4, 7)), ('m', (0, 3, 7))):
            best.append((c[[(r + i) % 12 for i in iv]].sum() + .15 * c[r], names[r] + nm))
    best.sort(reverse=True)
    return best[0][1], best[1][1]


def db(v):
    return 10 * np.log10(v + 1e-12)


def band(a, b, flo, fhi, mat=P):
    i0, i1 = int(a * fps), max(int(a * fps) + 1, int(b * fps))
    return float(db(mat[(f >= flo) & (f < fhi), i0:i1].mean()))


Ps = Ms ** 2
rows = []
print('\n bar  start   chord(bass)      full  sub   low   mid   pres  air   side  onsets  centroid')
flux_pk, _ = signal.find_peaks(flux, height=np.percentile(flux, 88) * .6, distance=int(.08 * fps))
on_t = flux_pk / fps
feat = []
for n, a in enumerate(down):
    b = a + bar
    if a < 0:
        a = 0
    if b > dur:
        break
    ch = chord(chroma_of(a, b, 180, 2000))
    bass = names[int(np.argmax(chroma_of(a, a + bar / 2, 40, 180)))]
    bass2 = names[int(np.argmax(chroma_of(a + bar / 2, b, 40, 180)))]
    r = dict(bar=n + 1, start=round(float(a), 3), chord=ch[0], alt=ch[1], bass=bass, bass2=bass2,
             full=band(a, b, 30, 16000), sub=band(a, b, 30, 110), low=band(a, b, 110, 300), midb=band(a, b, 300, 2000),
             pres=band(a, b, 2000, 6000), air=band(a, b, 6000, 14000), side=band(a, b, 200, 12000, Ps),
             onsets=int(((on_t >= a) & (on_t < b)).sum()),
             centroid=float((M[:, int(a * fps):int(b * fps)].sum(1) * f).sum() / M[:, int(a * fps):int(b * fps)].sum()))
    rows.append(r)
    feat.append(np.concatenate([chroma_of(a, b, 60, 4000) / (chroma_of(a, b, 60, 4000).sum() + 1e-12) * 3,
                                [r['full'] / 20, r['air'] / 20, r['sub'] / 20]]))
    print(f"{n + 1:4d} {a:7.2f}  {ch[0]:4s}/{ch[1]:4s} {bass:2s}>{bass2:2s}  {r['full']:6.1f}{r['sub']:6.1f}{r['low']:6.1f}{r['midb']:6.1f}{r['pres']:6.1f}"
          f"{r['air']:6.1f}{r['side']:6.1f}  {r['onsets']:4d}   {r['centroid']:6.0f}")

# ---- how exactly does the second half repeat the first?  (24 bars later)
feat = np.array(feat)
for lag in (8, 16, 20, 22, 23, 24, 25, 26):
    if len(feat) > lag + 8:
        d = np.linalg.norm(feat[lag:] - feat[:-lag], axis=1)
        print(f'bar lag {lag}: mean feature distance {d.mean():.3f}')
i24 = int(round(24 * bar * sr))
a, b = int(20 * sr), int(80 * sr)
x1, x2 = mid[a:b], mid[a + i24 - 2000:b + i24 + 2000]
c = signal.correlate(x2, x1, mode='valid')
k = int(np.argmax(np.abs(c)))
nrm = float(c[k] / (np.linalg.norm(x1) * np.linalg.norm(x2[k:k + len(x1)]) + 1e-9))
print(f'waveform correlation, 20-80s vs +24 bars: {nrm:.3f} at offset {(k - 2000) / sr * 1000:+.1f} ms (true lag {(i24 + k - 2000) / sr:.3f}s)')

# ---- lead melody register: harmonic-sum f0 on the centre channel, 300-3400 Hz emphasised
f0s = np.arange(110, 700, 2.0)
sal = np.zeros((len(f0s), M.shape[1]), np.float32)
Mc = np.maximum(M - Ms, 0)          # centre-ish
for h, w in ((1, 1.0), (2, .8), (3, .6), (4, .4), (5, .3)):
    idx = np.clip(np.round(f0s * h / (sr / N)).astype(int), 0, len(f) - 1)
    sal += w * Mc[idx]
f0 = f0s[np.argmax(sal, 0)]
strength = sal.max(0)
sections = {'verse 1 (15-41s)': (15, 41), 'pre-chorus (41-54s)': (41, 54), 'chorus (54-85s)': (54, 85)}
mel = {}
for nm, (a, b) in sections.items():
    i0, i1 = int(a * fps), int(b * fps)
    sel = strength[i0:i1] > np.percentile(strength[i0:i1], 50)
    v = f0[i0:i1][sel]
    q = np.percentile(v, [10, 50, 90])
    midi = lambda hz: names[int(round(12 * np.log2(hz / 440) + 69)) % 12] + str(int(round(12 * np.log2(hz / 440) + 69)) // 12 - 1)
    mel[nm] = [float(x) for x in q]
    print(f'melody salience {nm}: p10 {q[0]:.0f}Hz {midi(q[0])}  median {q[1]:.0f}Hz {midi(q[1])}  p90 {q[2]:.0f}Hz {midi(q[2])}')

json.dump(dict(bpm=float(bpm), beat=float(per), bar=float(bar), phase=float(ph), downbeats=[round(float(d), 3) for d in down],
               bars=rows, melody=mel), open(out, 'w'), indent=1)
