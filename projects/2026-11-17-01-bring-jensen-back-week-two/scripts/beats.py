#!/usr/bin/env python3
"""Beat times for the whole song with a dynamic-programming beat tracker (Ellis 2007) on the
accompaniment stem, because the tempo is not constant: 86.78 BPM up to the Taipei interlude, then it
drifts between ~85.4 and ~84.5 BPM.

  beats.py  ->  work/audio/beats.json  {beats: [...], downbeats: [...]}

Onset strength: kick-band flux + snare-crack flux. Downbeats: of the 4 possible bar phases, the one whose
beats 2 and 4 carry the most snare, chosen per 8-bar block so a phase slip in a break cannot propagate.
"""
import json

import numpy as np
import soundfile as sf
from scipy import signal

x, sr = sf.read('work/sep/inst.wav', dtype='float32')
x = x.mean(1)
N, HOP = 2048, 256
f, t, Z = signal.stft(x, sr, nperseg=N, noverlap=N - HOP, padded=False, boundary=None)
M = np.log1p(30 * np.abs(Z))
fr = sr / HOP
off = (N / 2) / sr


def flux(a, b):
    m = M[(f >= a) & (f < b)]
    v = np.concatenate([[0], np.maximum(m[:, 1:] - m[:, :-1], 0).sum(0)])
    return v / (np.percentile(v, 99) + 1e-9)


K, S, B = flux(35, 140), flux(1500, 5000), flux(140, 1500)
O = K + S + 0.3 * B
O = O - signal.medfilt(O, 31)
O = np.clip(O, 0, None)
n = len(O)
p0 = 0.705 * fr  # prior period in frames
alpha = 120.0
score = O.copy()
back = np.full(n, -1)
lo, hi = int(0.80 * p0), int(1.22 * p0)
for i in range(n):
    a, b = i - hi, i - lo
    if b <= 0:
        continue
    a = max(a, 0)
    prev = np.arange(a, b)
    tau = i - prev
    cand = score[prev] - alpha * np.log(tau / p0) ** 2 * 0.01
    j = int(np.argmax(cand))
    if cand[j] > 0:
        score[i] = O[i] + cand[j]
        back[i] = prev[j]
# backtrack from the best frame in the last two periods
i = int(np.argmax(score[n - int(2 * p0):])) + n - int(2 * p0)
bt = []
while i >= 0:
    bt.append(i)
    i = back[i]
bt = np.array(bt[::-1])
beats = bt / fr + off
# keep beats only where there is rhythm (drop the ones in the drumless intro tail/outro if they are spurious)
beats = beats[(beats > 0.0) & (beats < 303.3)]
# downbeats per 8-bar block
Sv = lambda ts: S[np.clip(np.round((ts - off) * fr).astype(int), 0, n - 1)]
Kv = lambda ts: K[np.clip(np.round((ts - off) * fr).astype(int), 0, n - 1)]
down = []
blk = 32
for s0 in range(0, len(beats), blk):
    seg = beats[s0:s0 + blk]
    best = max(range(4), key=lambda ph: sum(Sv(seg[(np.arange(len(seg)) - ph) % 4 % 2 == 1])) +
               0.5 * sum(Kv(seg[(np.arange(len(seg)) - ph) % 4 == 0])))
    down += [float(b) for k, b in enumerate(seg) if (k - best) % 4 == 0]
json.dump({'beats': [round(float(b), 3) for b in beats], 'downbeats': [round(b, 3) for b in down]},
          open('work/audio/beats.json', 'w'))
d = np.diff(beats)
print(len(beats), 'beats', len(down), 'downbeats')
for s in range(0, 303, 15):
    m = (beats[:-1] >= s) & (beats[:-1] < s + 15)
    if m.any():
        print(f'{s:3d}-{s + 15:3d}s  period {np.median(d[m]):.4f}  ({60 / np.median(d[m]):.2f} BPM)  n={m.sum()}')
print('downbeats', [round(b, 2) for b in down[:12]], '...')
