#!/usr/bin/env python3
"""Second cut plan, from the final per-character timing (lyric_timing.json) instead of the first line alignment.

For a shot that opens on lyric line N: candidate cut points are the tracked beats. Take the latest beat at or
before line N's first character (+0.05 s) that still leaves line N-1's last character on screen for 0.25 s; if
there is none, the first beat after that limit. Bar lines win when they qualify. The three choruses stay on
their downbeats; s06 (bar 27) and s15 (beat 60.3) are then kept by hand, see storyboard.md. Writes work/audio/cuts.json in the same format as plan_cuts.py.
"""
import json
import numpy as np
bj = json.load(open('work/audio/bars.json')); B = np.array(bj['beats']); bars = bj['bar_idx']
LT = json.load(open('work/audio/lyric_timing.json'))
keys = list(LT.keys())
old = json.load(open('work/audio/cuts.json'))
FIXED = {'s09': B[bars[38]], 's17': B[bars[65]], 's27': B[bars[106]]}


def barbeat(t):
    i = int(np.argmin(abs(B - t)))
    k = max(j for j, bi in enumerate(bars) if bi <= i)
    return f'b{k + 1}.{i - bars[k] + 1}'


out = {}
for sid, v in old.items():
    key = v['line']
    if sid in FIXED:
        t, why = FIXED[sid], 'chorus downbeat'
    else:
        first = LT[key]['start'][0]
        i = keys.index(key)
        lo = LT[keys[i - 1]]['start'][-1] + 0.25 if i > 0 else 0
        cand = B[(B <= first + 0.05) & (B >= lo)]
        barset = set(B[bars])
        if len(cand):
            onbar = [c for c in cand if c in barset and first - c <= 0.6]
            t = onbar[-1] if onbar else cand[-1]
            why = 'bar' if onbar else 'head'
        else:
            t = B[B >= lo][0]
            why = 'after previous line'
    out[sid] = dict(v, cut=round(float(t), 3), first_char=LT[key]['start'][0], rule=why, at=barbeat(t), frame=int(round(t * 24)))
    flag = '' if abs(out[sid]['cut'] - v['cut']) < 0.01 else f"   (was {v['cut']:.3f} {v['at']})"
    print(f"{sid} {v['kf']} {key:16s} first {LT[key]['start'][0]:7.2f}  cut {t:7.3f} {barbeat(t):8s} {why}{flag}")
json.dump(out, open('work/audio/cuts.json', 'w'), indent=1)
