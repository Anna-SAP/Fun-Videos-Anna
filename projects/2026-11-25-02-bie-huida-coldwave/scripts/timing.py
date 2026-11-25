#!/usr/bin/env python3
"""Per-character timing for the lyric layer: work/audio/lyric_timing.json.

Up to four independent estimates of each character's start: MMS CTC alignment on the vocal stem and on the mix
(align_lines.py), and the word times of the two whole-song faster-whisper transcriptions (vocal stem, mix), mapped
onto the lyric characters with difflib (a transcribed word's span is shared evenly by its characters). The start
is the median of the estimates that agree with it within 0.25 s (outliers dropped), ends are the next character's
start (last character: the CTC end, at least 0.25 s). Lines are kept from overlapping. HAND holds the few starts
read off the spectrogram where the estimates disagree. Output has times only, no lyric text.
"""
import difflib
import json
import os
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lyrics
from opencc_lite import t2s

L = json.load(open('work/audio/line_times.json'))
HAND = {('Chorus 2', 1, 0): 138.32}


def asr_chars(path):
    out = []
    for s in json.load(open(path)):
        for w in s['words']:
            txt = [c for c in t2s(w['w']) if '一' <= c <= '鿿' or c.isdigit()]
            if not txt:
                continue
            d = (w['e'] - w['s']) / len(txt)
            for i, c in enumerate(txt):
                out.append((c, w['s'] + i * d))
    return out


ASR = [asr_chars('work/audio/asr_vocals.json'), asr_chars('work/audio/asr_mix.json')]


def asr_estimates(chars, t0, t1, seq):
    sub = [(c, t) for c, t in seq if t0 - 0.5 <= t <= t1 + 0.5]
    sm = difflib.SequenceMatcher(a=chars, b=[c for c, _ in sub], autojunk=False)
    est = [None] * len(chars)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            est[a + k] = sub[b + k][1]
    return est


res = {}
prev_end = 0.0
report = []
for x in lyrics.LINES:
    key = f"{x['sec']}|{x['n']}"
    v, m = L[key]['voc'], L[key]['mix']
    ch = x['chars']
    t0, t1 = L[key]['win']
    ests = [[a for a, _, _ in v], [a for a, _, _ in m]] + [asr_estimates(ch, t0, t1, s) for s in ASR]
    starts = []
    for i in range(len(ch)):
        if (x['sec'], x['n'], i) in HAND:
            starts.append(HAND[(x['sec'], x['n'], i)]); continue
        e = np.array([es[i] for es in ests if es[i] is not None])
        med = np.median(e)
        keep = e[np.abs(e - med) <= 0.25]
        starts.append(float(np.median(keep if len(keep) else e)))
        report.append(len(e))
    starts = np.array(starts)
    # monotonic, at least 0.06 s apart
    for i in range(1, len(starts)):
        starts[i] = max(starts[i], starts[i - 1] + 0.06)
    if starts[0] < prev_end + 0.02:
        shift = prev_end + 0.02 - starts[0]
        starts[0] += shift
        for i in range(1, len(starts)):
            starts[i] = max(starts[i], starts[i - 1] + 0.06)
    last_end = max(v[-1][1], m[-1][1], starts[-1] + 0.25)
    ends = list(starts[1:]) + [last_end]
    res[key] = {'start': [round(float(s), 3) for s in starts], 'end': [round(float(e), 3) for e in ends]}
    prev_end = min(last_end, starts[-1] + 1.2)
# keep lines from overlapping: a line's last char ends before the next line starts
keys = list(res.keys())
for a, b in zip(keys, keys[1:]):
    nb = res[b]['start'][0]
    if res[a]['end'][-1] > nb - 0.02:
        res[a]['end'][-1] = round(max(res[a]['start'][-1] + 0.12, nb - 0.02), 3)
json.dump(res, open('work/audio/lyric_timing.json', 'w'), indent=0)
print('estimates per char: mean', round(float(np.mean(report)), 2), ' chars with 4:', sum(1 for r in report if r == 4), '/', len(report))
for k in keys:
    print(f"{k:16s} {res[k]['start'][0]:7.2f} - {res[k]['end'][-1]:7.2f}")
