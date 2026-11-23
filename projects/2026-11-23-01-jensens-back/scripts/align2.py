#!/usr/bin/env python3
"""Per-unit sung times for every performance of every sheet line.

  align2.py [--probe]       -> work/audio/align_ctc.json  (times only, no lyric text)

A 'performance' is one sung pass of a sheet line (some lines are sung more than once: the last line of each
hook, the drop chant, one line of the outro). Rough spans come from the transcripts mapped onto the sheet
(map_lines.py) and, where the transcripts heard nothing usable, from HAND (read off the transcripts' word times
and the vocal onset list). Each performance is forced through the MMS CTC aligner in several windows (alone with
three paddings, and together with its neighbours; on the vocal stem and on the mix); the median is kept.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctc  # noqa: E402
from lyrics import parse  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
secs, lines = parse(os.path.join(ROOT, 'work', 'src', 'lyrics.txt'))
MAP = {r['i']: r for r in json.load(open(os.path.join(ROOT, 'work', 'audio', 'map.json')))['lines']}
# (line, start, end) rough spans set by hand; a line listed more than once is sung more than once
HAND = [
    (0, 1.5, 2.9), (1, 7.3, 8.1), (2, 8.1, 12.3), (3, 12.7, 15.5),
    (9, 32.0, 35.1), (9, 35.2, 38.3),
    (28, 98.3, 101.5),
    (40, 137.6, 139.1), (41, 139.1, 140.9), (40, 140.9, 142.3), (41, 142.3, 144.1),
    (40, 144.1, 145.5), (41, 145.5, 147.2), (40, 147.2, 148.4),
    (44, 149.5, 152.6), (45, 152.7, 155.8),
    (69, 230.4, 233.6), (69, 233.6, 236.8),
    (72, 245.1, 246.3), (72, 248.0, 249.5),
]
SKIP = {42, 43}        # not found in the recording (see storyboard)
hand_lines = {h[0] for h in HAND}
perfs = [(i, s, e) for (i, s, e) in HAND]
for l in lines:
    i = l['i']
    if i in hand_lines or i in SKIP:
        continue
    r = MAP[i]
    assert 's' in r, i
    perfs.append((i, r['s'], r['e']))
perfs.sort(key=lambda p: p[1])
ROM = {l['i']: ctc.romanise([u[0] for u in l['units']]) for l in lines}

out = []
for k, (i, s, e) in enumerate(perfs):
    est = [[] for _ in ROM[i]]
    for src in ('voc', 'mix'):
        for p0, p1 in ((0.5, 0.6), (0.9, 0.9), (0.3, 0.4)):
            r = ctc.align(ROM[i], s - p0, e + p1, src)
            if r:
                for u, x in enumerate(r):
                    est[u].append(x)
        # with the previous / next performance
        for d in (-1, 1):
            j = k + d
            if not (0 <= j < len(perfs)):
                continue
            a, b = (j, k) if d < 0 else (k, j)
            if perfs[b][1] - perfs[a][2] > 1.5:
                continue
            ids = ROM[perfs[a][0]] + ROM[perfs[b][0]]
            r = ctc.align(ids, perfs[a][1] - 0.6, perfs[b][2] + 0.7, src)
            if r:
                off = 0 if d > 0 else len(ROM[perfs[a][0]])
                for u in range(len(ROM[i])):
                    est[u].append(r[off + u])
    U, SC, IQ = [], [], []
    for u, xs in enumerate(est):
        a = np.array(xs, np.float64)
        U.append([round(float(np.median(a[:, 0])), 3), round(float(np.median(a[:, 1])), 3)])
        SC.append(round(float(np.median(a[:, 2])), 3))
        IQ.append(round(float(np.percentile(a[:, 0], 75) - np.percentile(a[:, 0], 25)), 3))
    out.append({'line': i, 'rough': [s, e], 'units': U, 'score': SC, 'iqr': IQ})
    print(f"{i:3d} rough {s:7.2f}-{e:7.2f}  ctc {U[0][0]:7.2f}-{U[-1][1]:7.2f}  score~{np.median(SC):.2f} min {min(SC):.2f}  iqr~{np.median(IQ):.2f} max {max(IQ):.2f}")
json.dump({'perfs': out}, open(os.path.join(ROOT, 'work', 'audio', 'align_ctc.json'), 'w'), indent=0)
