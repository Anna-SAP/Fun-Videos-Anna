#!/usr/bin/env python3
"""Second opinion for the rap verses: force a whole section (all its lines in one pass) through the CTC aligner,
on the vocal stem and on the mix, and compare with the per-line medians (align2.py) and the transcripts' word
times (map.json).  -> work/audio/align_sec.json ; prints the units where the estimates disagree."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctc  # noqa: E402
from lyrics import parse  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
secs, lines = parse(os.path.join(ROOT, 'work', 'src', 'lyrics.txt'))
C = {}
for p in json.load(open(os.path.join(ROOT, 'work', 'audio', 'align_ctc.json')))['perfs']:
    C.setdefault(p['line'], p)
MAPU = json.load(open(os.path.join(ROOT, 'work', 'audio', 'map.json')))['units']
SECTIONS = [(range(10, 22), 40.4, 80.0), (range(22, 24), 79.4, 85.6), (range(24, 36), 85.2, 124.2), (range(36, 40), 123.6, 137.7),
            (range(44, 58), 149.2, 195.1), (range(58, 64), 194.6, 214.0), (range(70, 72), 239.3, 245.2)]
ROM = {l['i']: ctc.romanise([u[0] for u in l['units']]) for l in lines}
out = {}
for rng, t0, t1 in SECTIONS:
    ids, own = [], []
    for i in rng:
        ids += ROM[i]
        own += [(i, u) for u in range(len(ROM[i]))]
    res = {}
    for src in ('voc', 'mix'):
        r = ctc.align(ids, t0, t1, src)
        if r is None:
            print('fail', list(rng)[0], src)
            continue
        for (i, u), x in zip(own, r):
            res.setdefault((i, u), {})[src] = x[0]
    for i in rng:
        row = []
        bad = 0
        for u in range(len(ROM[i])):
            a = C[i]['units'][u][0] if i in C else None
            v, m = res.get((i, u), {}).get('voc'), res.get((i, u), {}).get('mix')
            w = MAPU.get(f'{i}.{u}')
            out[f'{i}.{u}'] = {'line': a, 'voc': v, 'mix': m, 'asr': w}
            xs = [x for x in (a, v, m, w) if x is not None]
            sp = max(xs) - min(xs) if len(xs) > 1 else 0
            if sp > 0.20:
                bad += 1
                row.append(f"{u}:" + '/'.join('--' if x is None else f'{x:.2f}' for x in (a, v, m, w)))
        print(f'{i:3d} n{len(ROM[i])} disagree {bad}  ' + '  '.join(row))
json.dump(out, open(os.path.join(ROOT, 'work', 'audio', 'align_sec.json'), 'w'))
