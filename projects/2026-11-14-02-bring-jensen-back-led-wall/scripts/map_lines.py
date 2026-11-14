#!/usr/bin/env python3
"""Find where each lyric line is sung, from free transcriptions.

  map_lines.py LYRICS.txt OUT.json ASR1.json [ASR2.json ...]

Each transcript's characters (CJK + latin letters/digits, normalised) are aligned to the lyric sheet's
characters with difflib; every matched character carries the time of the transcript word it came from.
A line's rough span is the median over transcripts of its first/last matched character times, and its
coverage says how much of it any transcript actually heard. Lines no transcript heard are reported, not
guessed.
"""
import difflib
import json
import sys

import numpy as np

sys.path.insert(0, __import__('os').path.dirname(__file__))
from lyrics import norm, parse  # noqa: E402

lyr, out = sys.argv[1:3]
asrs = sys.argv[3:]
secs, lines = parse(lyr)
# lyric character stream with (line, unit) owner
L, owner = [], []
for l in lines:
    for ui, (u, a, b) in enumerate(l['units']):
        for ch in norm(u):
            L.append(ch)
            owner.append((l['i'], ui))
Ls = ''.join(L)

per_line = {l['i']: {'s': [], 'e': [], 'cov': []} for l in lines}
unit_hits = {}
for path in asrs:
    d = json.load(open(path))
    T, tt = [], []
    for s in d['segments']:
        ws = s.get('words') or []
        for w in ws:
            nw = norm(w['w'])
            if not nw:
                continue
            n = len(nw)
            for k, ch in enumerate(nw):
                T.append(ch)
                tt.append(w['s'] + (w['e'] - w['s']) * k / n)
    Ts = ''.join(T)
    sm = difflib.SequenceMatcher(None, Ls, Ts, autojunk=False)
    hit = {}
    for a, b, size in sm.get_matching_blocks():
        if size < 2:
            continue
        for k in range(size):
            hit[a + k] = tt[b + k]
    for l in lines:
        idx = [i for i, o in enumerate(owner) if o[0] == l['i']]
        h = [hit[i] for i in idx if i in hit]
        cov = len(h) / max(1, len(idx))
        per_line[l['i']]['cov'].append(cov)
        if cov >= 0.3 and h:
            per_line[l['i']]['s'].append(min(h))
            per_line[l['i']]['e'].append(max(h))
        for i in idx:
            if i in hit:
                unit_hits.setdefault(owner[i], []).append(hit[i])

res = []
for l in lines:
    p = per_line[l['i']]
    r = {'i': l['i'], 'sec': l['sec'], 'cov': round(float(max(p['cov'])), 2), 'n': len(p['s'])}
    if p['s']:
        r['s'] = round(float(np.median(p['s'])), 2)
        r['e'] = round(float(np.median(p['e'])), 2)
    res.append(r)
json.dump({'lines': res, 'units': {f'{k[0]}.{k[1]}': round(float(np.median(v)), 3) for k, v in unit_hits.items()}},
          open(out, 'w'), indent=0)
for r, l in zip(res, lines):
    print(f"{r['i']:3d} {l['sec_name'][:8]:8s} cov {r['cov']:.2f} n{r['n']} "
          f"{r.get('s', -1):7.2f}-{r.get('e', -1):7.2f}  {l['text'][:30]}")
