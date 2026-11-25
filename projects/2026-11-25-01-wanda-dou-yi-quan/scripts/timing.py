#!/usr/bin/env python3
"""Merge the per-character estimates into one start time per character.

  timing.py ALIGN_RAW.json OUT.json [--report]

Candidates per character: the three CTC estimates, the two whisper estimates (+0.07 s, not for the first
character of a line: whisper gives the silence before a phrase to its first word), and the same character of
the repeats of a chorus line shifted by the median offset between the two lines. The answer is the median of
the largest cluster of candidates (0.12 s wide), snapped to the nearest onset of the vocal stem within 0.06 s.
HAND overrides come from reading the spectrogram. Output has times only, no lyric text.
"""
import json, os, sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft, find_peaks
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lyrics
L = lyrics.load()
raw = json.load(open(sys.argv[1]))
REPORT = '--report' in sys.argv
SIB = [(7, 17, 25), (8, 18), (9, 19, 27), (10, 20, 28)]
HAND = {}
if os.path.exists(os.path.join(os.path.dirname(__file__), 'hand_times.json')):
    HAND = {tuple(map(int, k.split('.'))): v for k, v in json.load(open(os.path.join(os.path.dirname(__file__), 'hand_times.json'))).items()}

def cluster(c, w=0.12):
    c = sorted(c)
    best = []
    for a in c:
        g = [x for x in c if a <= x <= a + w]
        if len(g) > len(best):
            best = g
    return float(np.median(best)), len(best)

def cands(i, k):
    e = raw[str(i)]['est'][k]
    c = [x for x in e[2:] if x is not None]
    if k > 0:
        c += [x + 0.07 for x in e[:2] if x is not None]
    return c

base = {}
for i, l in enumerate(L):
    for k in range(len(l['chars'])):
        c = cands(i, k)
        base[(i, k)] = cluster(c) if c else (None, 0)
# sibling transfer
final = {}
for i, l in enumerate(L):
    sib = [s for g in SIB if i in g for s in g if s != i]
    for k in range(len(l['chars'])):
        c = cands(i, k)
        for s in sib:
            if len(L[s]['chars']) != len(l['chars']):
                continue
            offs = [base[(i, j)][0] - base[(s, j)][0] for j in range(len(l['chars'])) if base[(i, j)][1] >= 3 and base[(s, j)][1] >= 3]
            if len(offs) >= 4 and base[(s, k)][0] is not None:
                c += [base[(s, k)][0] + float(np.median(offs))] * 2
        final[(i, k)] = cluster(c) if c else (None, 0)

# vocal onsets
sr, v = wavfile.read('work/audio/voc22k.wav'); v = v.astype(np.float32) / 32768
HOP = 110
f, t, Z = stft(v, sr, nperseg=1024, noverlap=1024 - HOP, boundary=None, padded=False)
M = np.log1p(60 * np.abs(Z[(f > 150) & (f < 6000)]))
flux = np.concatenate([[0], np.maximum(np.diff(M, axis=1), 0).sum(0)])
flux = flux / np.percentile(flux, 99)
pk, _ = find_peaks(flux, height=0.25, distance=8)
pk_t = t[pk] - 0.012
def snap(x, w=0.06):
    j = np.argmin(np.abs(pk_t - x))
    return (float(pk_t[j]), True) if abs(pk_t[j] - x) <= w else (x, False)

out = {}
for i, l in enumerate(L):
    ts, prev = [], None
    for k, c in enumerate(l['chars']):
        x, n = final[(i, k)]
        how = f'n{n}'
        if (i, k) in HAND:
            x, how = HAND[(i, k)], 'hand'
        elif x is None:
            x, how = None, 'none'
        else:
            x2, ok = snap(x)
            if ok:
                x, how = x2, how + '+snap'
        ts.append([x, how])
    # fill missing: after previous char by 0.22 s
    for k in range(len(ts)):
        if ts[k][0] is None:
            ts[k][0] = ts[k - 1][0] + 0.24
    for k in range(1, len(ts)):
        if ts[k][0] < ts[k - 1][0] + 0.07:
            ts[k][0] = ts[k - 1][0] + 0.07
    out[str(i)] = {'t': [round(x, 3) for x, _ in ts], 'how': [h for _, h in ts]}
    if REPORT:
        flags = [f"{k}:{c['py']}@{ts[k][0]:.2f}({ts[k][1]})" for k, c in enumerate(l['chars']) if ts[k][1].startswith(('n1', 'n2', 'none')) ]
        print(f"L{i:2d} {l['sec'][:10]:10s} start {ts[0][0]:7.2f} end {ts[-1][0]:7.2f}  weak: {' '.join(flags)}")
json.dump(out, open(sys.argv[2], 'w'))
