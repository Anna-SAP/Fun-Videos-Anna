#!/usr/bin/env python3
"""Drum-machine pattern at 16th-note resolution, folded over bars per section (from the instrumental stem's
kick 30-150 Hz flux and snare flux in feat.npz). Prints, for each section, the mean onset strength on each of the
16 slots of the bar, normalised to the strongest slot, so 'K' rows read like a step sequencer.

  drum_pattern.py "name:bar_a-bar_b,..."   (bar numbers 1-based, inclusive)
"""
import json, sys
import numpy as np
d = np.load('work/audio/feat.npz'); R = float(d['rate'])
bj = json.load(open('work/audio/bars.json')); B = np.array(bj['beats']); bars = bj['bar_idx']
def val(arr, t, w=0.025):
    a = int(max(0, (t - w) * R)); b = int((t + w) * R) + 1
    return float(arr[a:b].max())
for item in sys.argv[1].split(','):
    name, rng = item.split(':'); a, b = map(int, rng.split('-'))
    K = np.zeros(16); S = np.zeros(16); H = np.zeros(16); n = 0
    for k in range(a - 1, b):
        bi = bars[k]
        if k + 1 < len(bars) and bars[k + 1] - bi != 4: continue
        if bi + 4 >= len(B): continue
        for q in range(4):
            t0, t1 = B[bi + q], B[bi + q + 1]
            for s in range(4):
                tt = t0 + (t1 - t0) * s / 4
                K[q * 4 + s] += val(d['kick'], tt); S[q * 4 + s] += val(d['snare'], tt); H[q * 4 + s] += val(d['hat'], tt)
        n += 1
    K /= max(n, 1); S /= max(n, 1); H /= max(n, 1)
    def row(v):
        m = v.max() + 1e-9
        return ' '.join(f'{x / m:4.2f}' for x in v)
    print(f'--- {name} bars {a}-{b} ({n} bars)    1    e    +    a    2    e    +    a    3    e    +    a    4    e    +    a')
    print(f'  kick  {row(K)}'); print(f'  snare {row(S)}'); print(f'  hat   {row(H)}')
