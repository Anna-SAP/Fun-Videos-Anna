#!/usr/bin/env python3
"""Unit starts of a timing file in [T0, T1] as spectrogram marks: [[time, 'line.unit'], ...] (no lyric text).

  marks.py TIMING.json T0 T1 OUT.json
"""
import json
import sys

d = json.load(open(sys.argv[1]))
t0, t1 = float(sys.argv[2]), float(sys.argv[3])
out = []
for r in d['lines']:
    for k, u in enumerate(r['units']):
        if u and t0 <= u[0] <= t1:
            out.append([u[0], f"{r['i']}.{k}"])
json.dump(out, open(sys.argv[4], 'w'))
print(len(out), 'marks')
