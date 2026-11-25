#!/usr/bin/env python3
"""Per-character time estimates for every lyric line, from independent sources:

  A  whisper word timestamps (vocal stem, no prompt)      B  the same on the full mix
  C  CTC forced alignment per line on the vocal stem      D  the same on the mix
  E  CTC forced alignment per section on the vocal stem

  align.py OUT.json
Writes {line index: {"est": [[a, b, c, d, e] per char], "win": [t0, t1]}}; no lyric text in the output.
"""
import difflib, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lyrics, ctc
from pypinyin import lazy_pinyin

L = lyrics.load()
N = len(L)
flat = [(i, k) for i, l in enumerate(L) for k, c in enumerate(l['chars']) if c['py']]
flat_py = [L[i]['chars'][k]['py'] for i, k in flat]
est = {i: [[None] * 5 for _ in l['chars']] for i, l in enumerate(L)}

def asr_chars(path):
    out = []
    for seg in json.load(open(path)):
        for w in seg['words']:
            cs = [c for c in w['w'] if lyrics.is_cjk(c)]
            if not cs:
                continue
            d = (w['e'] - w['s']) / len(cs)
            for j, c in enumerate(cs):
                out.append((lazy_pinyin(c)[0], w['s'] + j * d))
    return out

def same(a, b):
    strip = lambda s: s.replace('ng', 'n').replace('zh', 'z').replace('ch', 'c').replace('sh', 's')
    return a == b or strip(a) == strip(b)

for col, path in ((0, 'work/audio/asr_voc_lv2.json'), (1, 'work/audio/asr_mix_lv2.json')):
    ac = asr_chars(path)
    sm = difflib.SequenceMatcher(None, [p for p, _ in ac], flat_py, autojunk=False)
    n = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                li, ci = flat[j1 + k]
                est[li][ci][col] = round(ac[i1 + k][1], 3)
                n += 1
    print(path, 'matched', n, 'of', len(flat_py))

# rough line windows from A/B
win = {}
for i, l in enumerate(L):
    ts = [v for e in est[i] for v in e[:2] if v is not None]
    win[i] = [min(ts), max(ts)] if ts else None
print({i: w for i, w in win.items()})
HAND = {0: (2.0, 7.9), 23: (115.2, 119.0), 24: (119.2, 122.8), 29: (142.2, 145.4)}   # spoken lines: read off the spectrogram
for i, w in HAND.items():
    win[i] = list(w)
for i in range(N):
    assert win[i], i
for i, l in enumerate(L):
    ids = ctc.romanise([c['c'] if not c['py'] else '啊' for c in l['chars']])
    ids = [ctc.romanise_py(c['py']) if c['py'] else None for c in l['chars']] if hasattr(ctc, 'romanise_py') else ids
    idx = [k for k, c in enumerate(l['chars']) if c['py']]
    lo = max(win[i][0] - 0.7, (win[i - 1][1] - 0.1) if i else 0)
    hi = min(win[i][1] + 1.2, (win[i + 1][0] + 0.3) if i + 1 < N else 167)
    for col, src in ((2, 'voc'), (3, 'mix')):
        r = ctc.align([ids[k] for k in idx], lo, hi, src)
        if r:
            for k, (a, b, s) in zip(idx, r):
                est[i][k][col] = round(a, 3)
# sections
secs = {}
for i, l in enumerate(L):
    secs.setdefault(l['sec'], []).append(i)
for sec, ii in secs.items():
    units = [(i, k) for i in ii for k, c in enumerate(L[i]['chars']) if c['py']]
    ids = [ctc.romanise_py(L[i]['chars'][k]['py']) for i, k in units]
    r = ctc.align(ids, max(0, win[ii[0]][0] - 1.0), min(167, win[ii[-1]][1] + 1.5), 'voc')
    if r:
        for (i, k), (a, b, s) in zip(units, r):
            est[i][k][4] = round(a, 3)
json.dump({str(i): {'est': est[i], 'win': win[i]} for i in range(N)}, open(sys.argv[1], 'w'))
for i, l in enumerate(L):
    print(f"--- L{i} {l['sec']} {'spoken' if l['spoken'] else 'ring %d' % l['ring']}")
    for k, c in enumerate(l['chars']):
        e = est[i][k]
        v = [x for x in e if x is not None]
        sp = (max(v) - min(v)) if v else 0
        print(f"  {k:2d} {c['py'] or '-':6s} " + ' '.join(f'{x:7.2f}' if x is not None else '      .' for x in e) + (f'   spread {sp:.2f}' if sp > 0.2 else ''))
