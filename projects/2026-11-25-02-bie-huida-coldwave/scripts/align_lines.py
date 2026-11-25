#!/usr/bin/env python3
"""Line-level timing: force each lyric line (toneless pinyin) through the MMS CTC emissions of the vocal stem
and of the mix inside a rough window read off the two whole-song transcriptions (WIN, seconds only).
Prints per line the first/last character times from both sources and their mean posterior.
Writes work/audio/line_times.json: {"Sec|n": {"t0", "t1", "voc": [...], "mix": [...]}}. No lyric text is written.

Also runs two tests whose answers decide what the recording actually contains:
  ticks: chorus-1 line 5 forced with its two tick words versus four, over the same window
  adlib: the 15.3-17.3 s intro vocal forced as the title phrase versus the transcriber's syllables
"""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctc
import lyrics
from pypinyin import lazy_pinyin

WIN = {
    'Intro': [(2.3, 7.9), (10.4, 15.5)],
    'Verse 1': [(25.6, 29.5), (29.1, 32.9), (33.1, 38.1), (37.5, 41.5), (41.7, 46.3), (45.7, 48.6), (48.0, 50.3), (49.7, 56.0)],
    'Pre-Chorus': [(55.3, 60.8), (60.3, 65.1), (64.5, 69.0), (67.9, 72.8), (72.2, 77.9), (77.3, 81.5)],
    'Chorus 1': [(81.4, 86.1), (85.5, 89.8), (89.2, 94.2), (93.6, 98.4), (97.7, 102.7)],
    'Verse 2': [(102.0, 105.8), (105.9, 110.0), (110.1, 114.3), (114.5, 119.3), (118.6, 122.1), (121.5, 124.2),
                (123.6, 126.4), (125.7, 128.2), (127.5, 130.9), (130.3, 133.6), (132.9, 135.9), (135.2, 138.6)],
    'Chorus 2': [(137.9, 142.0), (141.3, 146.2), (145.5, 150.6), (149.9, 154.5)],
    'Verse 3': [(153.8, 157.1), (156.5, 159.3), (158.6, 161.3), (160.6, 163.5), (162.8, 167.3), (166.6, 171.2), (170.5, 172.9)],
    'Bridge': [(173.9, 178.4), (177.7, 181.6), (181.9, 186.5), (185.8, 191.0), (190.3, 196.4), (195.9, 199.6)],
    'Verse 4': [(198.9, 203.9), (203.2, 208.1), (207.4, 212.6), (211.9, 216.6), (215.9, 220.0), (219.2, 223.6)],
    'Final Chorus': [(224.2, 228.4), (227.7, 232.6), (231.9, 236.9), (236.1, 241.1), (240.3, 246.1)],
    'Outro': [(248.0, 254.3), (255.6, 258.6)],
}


def ids_of(chars):
    py = lazy_pinyin(''.join(chars))
    assert len(py) == len(chars)
    return [ctc.romanise_py(p) for p in py]


def run(chars, t0, t1, src):
    r = ctc.align(ids_of(chars), t0, t1, src)
    return r


out = {}
print('line            voc first..last (score)        mix first..last (score)')
for x in lyrics.LINES:
    t0, t1 = WIN[x['sec']][x['n'] - 1]
    rv = run(x['chars'], t0, t1, 'voc')
    rm = run(x['chars'], t0, t1, 'mix')
    key = f"{x['sec']}|{x['n']}"
    out[key] = {'win': [t0, t1], 'voc': [[round(a, 3), round(b, 3), round(s, 3)] for a, b, s in rv] if rv else None,
                'mix': [[round(a, 3), round(b, 3), round(s, 3)] for a, b, s in rm] if rm else None}
    def fmt(r):
        return f'{r[0][0]:7.2f}..{r[-1][1]:7.2f} ({np.mean([s for _, _, s in r]):.2f})' if r else '   --   '
    print(f'{key:16s} {fmt(rv):28s} {fmt(rm)}')
json.dump(out, open('work/audio/line_times.json', 'w'), indent=0)

print('\n--- ticks test (chorus 1 line 5)')
c = lyrics.line('Chorus 1', 5)['chars']
base, tick = c[:-4], c[-4:-2]
for k in (1, 2, 3, 4):
    ch = base + tick * k
    for src in ('voc', 'mix'):
        r = run(ch, 97.7, 103.0, src)
        if r:
            sc = [s for _, _, s in r]
            print(f'  {k} ticks {src}: mean {np.mean(sc):.3f}  tick scores ' + ' '.join(f'{s:.2f}' for _, _, s in r[len(base):]) +
                  '  tick starts ' + ' '.join(f'{a:.2f}' for a, _, _ in r[len(base):]))
print('\n--- adlib test (intro 15.0-17.6)')
title = lyrics.line('Chorus 1', 1)['chars'][:3]
for name, ch in (('title x1', title), ('title x2', title * 2), ('asr-syll x3', list('变瘦') * 3)):
    for src in ('voc', 'mix'):
        r = run(ch, 15.0, 17.6, src)
        if r:
            print(f'  {name:12s} {src}: mean {np.mean([s for _, _, s in r]):.3f}  starts ' + ' '.join(f'{a:.2f}' for a, _, _ in r))
