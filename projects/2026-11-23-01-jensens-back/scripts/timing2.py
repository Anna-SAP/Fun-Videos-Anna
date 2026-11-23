#!/usr/bin/env python3
"""Final per-unit sung times -> work/audio/lyric_timing.json (times only, no lyric text).

  timing2.py [--marks]     --marks also writes work/qc/marks.json ([time, "line.unit"]) for the spectrogram check

Rap verses: CTC forced alignment (align2.py), each start pulled to the nearest vocal onset within 50 ms.
Chants (intro, hooks, build, drop, outro), where a crowd doubles the lead and the aligner's posteriors collapse:
HAND times, set from the transcripts' word times, the vocal onset list and the spectrogram, on the 0.2 s grid
where the delivery is on it. A sheet line sung twice has two entries.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lyrics import parse  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
secs, lines = parse(os.path.join(ROOT, 'work', 'src', 'lyrics.txt'))
NU = {l['i']: len(l['units']) for l in lines}
C = json.load(open(os.path.join(ROOT, 'work', 'audio', 'align_ctc.json')))['perfs']
on = np.load(os.path.join(ROOT, 'work', 'audio', 'vox_onsets.npz'))
flux, ft, lev = on['flux'], on['ft'], on['lev']

HAND = __import__('hand_times').HAND     # [(line, [t per unit], snap?)]
FIX = __import__('hand_times').FIX       # {(line, perf#, unit): t}  single-unit corrections on top of CTC


def snap(t, back=0.05, fwd=0.05, th=0.30):
    m = (ft >= t - back) & (ft <= t + fwd)
    if m.any():
        j = int(np.argmax(flux[m]))
        if flux[m][j] > th:
            return float(ft[m][j])
    return t


S = json.load(open(os.path.join(ROOT, 'work', 'audio', 'align_sec.json')))
hand_lines = {h[0] for h in HAND}
perfs = []
seen = {}
for p in C:
    i = p['line']
    k = seen.get(i, 0)
    seen[i] = k + 1
    if i in hand_lines:
        continue
    ts = []
    for u, (a0, _b0) in enumerate(p['units']):
        e = S.get(f'{i}.{u}', {})
        xs = [x for x in (a0, e.get('voc'), e.get('mix'), e.get('asr')) if x is not None]
        ts.append(snap(float(np.median(xs))))
    for (li, pk, u), t in FIX.items():
        if li == i and pk == k:
            ts[u] = t
    perfs.append({'line': i, 't': ts, 'end': max(p['units'][-1][1], ts[-1] + 0.2), 'src': 'ctc'})
for i, ts, sn in HAND:
    assert len(ts) == NU[i], (i, len(ts), NU[i])
    ts = [snap(t, 0.04, 0.04) if sn else t for t in ts]
    perfs.append({'line': i, 't': ts, 'end': ts[-1] + 0.45, 'src': 'hand'})
perfs.sort(key=lambda p: p['t'][0])
# order inside a performance, and a floor on the spacing
for p in perfs:
    ts = p['t']
    for k in range(1, len(ts)):
        if ts[k] < ts[k - 1] + 0.05:
            ts[k] = ts[k - 1] + 0.05
    p['t'] = [round(float(t), 3) for t in ts]
    p['end'] = round(float(max(p['end'], ts[-1] + 0.15)), 3)
for a, b in zip(perfs, perfs[1:]):
    if b['t'][0] < a['t'][-1] + 0.04:
        print('overlap', a['line'], a['t'][-1], b['line'], b['t'][0])
    a['end'] = min(a['end'], b['t'][0])
json.dump({'perfs': perfs}, open(os.path.join(ROOT, 'work', 'audio', 'lyric_timing.json'), 'w'), indent=0)
print(len(perfs), 'performances', sum(len(p['t']) for p in perfs), 'units')
if '--marks' in sys.argv:
    marks = [[t, f"{p['line']}.{u}"] for p in perfs for u, t in enumerate(p['t'])]
    json.dump(marks, open(os.path.join(ROOT, 'work', 'qc', 'marks.json'), 'w'))
if '--bars' in sys.argv:
    for p in perfs:
        b = p['t'][0] / 3.2
        print(f"{p['line']:3d} {p['src']:4s} first {p['t'][0]:7.2f} (bar {int(b)} +{(b - int(b)) * 3.2:4.2f}s) last {p['t'][-1]:7.2f} n{len(p['t'])}")
