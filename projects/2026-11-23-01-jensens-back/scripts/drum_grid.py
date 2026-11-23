#!/usr/bin/env python3
"""Where the bar lines are: onset histograms of the separated instrumental, and a per-bar drum table.

  drum_grid.py FEAT.npz [BAR_SECONDS=3.2]

Prints (1) histograms of kick / snare onset times modulo 0.4 s and 0.8 s -- one sharp peak per grid step means a
constant tempo with no drift; (2) for every bar on the grid, the kick / snare / hi-hat strength at each of its 16
steps and the mean level of the low band, the instrumental and the vocal. Section boundaries and the bars without
drums are read off this table.
"""
import sys

import numpy as np

d = np.load(sys.argv[1])
BAR = float(sys.argv[2]) if len(sys.argv) > 2 else 3.2
R = float(d['rate'])
for name in ('kick', 'snare'):
    t = d[name + '_t']
    for mod in (0.4, 0.8):
        h, _ = np.histogram(t % mod, bins=20, range=(0, mod))
        print(f'{name:5s} onsets mod {mod}: {h.tolist()}')


def seg(e, a, b):
    return e[max(0, int(a * R)):int(b * R)]


norm = {k: np.percentile(d[k], 99.5) for k in ('kick', 'snare', 'hat')}
print('bar  t0     low   inst  vox   loud | kick16            snare16           hat16')
n = 0
while n * BAR < len(d['kick']) / R:
    a = n * BAR
    cols = []
    for k in ('kick', 'snare', 'hat'):
        o = ''
        for j in range(16):
            s = seg(d[k], a + j * BAR / 16 - 0.03, a + j * BAR / 16 + 0.04)
            o += '%d' % min(9, int(9.99 * min(1, s.max() / norm[k]))) if len(s) else ' '
        cols.append(o)
    lv = [seg(d[k], a, a + BAR).mean() if len(seg(d[k], a, a + BAR)) else 0 for k in ('low', 'inst', 'vox', 'loud')]
    print('%3d %6.1f %5.0f %5.0f %5.0f %5.0f | %s  %s  %s' % (n, a, *lv, *cols))
    n += 1
