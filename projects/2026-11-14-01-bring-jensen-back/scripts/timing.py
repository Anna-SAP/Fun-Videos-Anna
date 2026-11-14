#!/usr/bin/env python3
"""Turn the aligner's medians into the final per-unit timing the film uses.

  timing.py   (reads work/audio/align_raw.json, writes work/audio/lyric_timing.json)

1. Units no estimate reached are interpolated inside their line between the rough window and known units.
2. SEEN overrides a unit's start with a time read off the vocal spectrogram (only where it was clearly off).
3. Order is forced (each unit >= previous + 0.05 s), every end is clipped to the next start, and every unit
   lasts at least 0.08 s.
Only times are written; the words stay in the user's lyric file.
"""
import json
import sys

sys.path.insert(0, 'scripts')
import sung  # noqa: E402

# (entry id, unit index) -> start (s), read off work/qc/voc_*.png where the aligner was visibly off
SEEN = {
    ('i1', 0): 4.15,                       # sung title starts after 4.1 s of piano (aligner said 3.55)
    ('i3', 0): 11.48, ('i3', 8): 13.86,    # the history line starts after a 1.3 s gap; 2nd phrase after the breath
    ('i5', 0): 20.45,                      # news sample starts after the gap at 20.2-20.4
    ('i6', 0): 23.50,
    ('i8', 0): 26.46, ('i8', 1): 26.75, ('i8', 2): 27.00, ('i8', 3): 27.55, ('i8', 4): 28.03, ('i8', 5): 28.57,
    ('h1g', 0): 86.25, ('h1g', 1): 86.50,  # after the (mei guan) ad-lib, not under it
}

raw = json.load(open('work/audio/align_raw.json'))
ents = {e['id']: e for e in sung.entries()}
out = []
for r in raw:
    e = ents[r['id']]
    us = r['units']
    n = len(us)
    s = [u['s'] for u in us]
    en = [u['e'] for u in us]
    known = [i for i in range(n) if s[i] is not None]
    for i in range(n):
        if s[i] is None:
            lo = max([k for k in known if k < i], default=None)
            hi = min([k for k in known if k > i], default=None)
            a_t, a_i = (s[lo], lo) if lo is not None else (e['t0'], -1)
            b_t, b_i = (s[hi], hi) if hi is not None else (e['t1'] - 0.2, n)
            s[i] = a_t + (b_t - a_t) * (i - a_i) / (b_i - a_i)
            en[i] = None
    for (eid, k), v in SEEN.items():
        if eid == r['id']:
            s[k] = v
    for i in range(1, n):
        s[i] = max(s[i], s[i - 1] + 0.05)
    for i in range(n):
        nxt = s[i + 1] if i + 1 < n else None
        if en[i] is None:
            en[i] = nxt if nxt is not None else s[i] + 0.3
        if nxt is not None:
            en[i] = min(en[i], nxt)
        en[i] = max(en[i], s[i] + 0.08)
    out.append({'id': r['id'], 'line': r['line'], 'slice': r['slice'],
                'units': [{'s': round(a, 3), 'e': round(b, 3)} for a, b in zip(s, en)]})
# lines must not overlap their successor's start by more than a hair
for a, b in zip(out, out[1:]):
    if a['units'][-1]['e'] > b['units'][0]['s']:
        a['units'][-1]['e'] = max(a['units'][-1]['s'] + 0.08, b['units'][0]['s'])
json.dump(out, open('work/audio/lyric_timing.json', 'w'), indent=0)
for o in out:
    print(f"{o['id']:5s} L{o['line']:<3} {o['units'][0]['s']:7.2f} -> {o['units'][-1]['e']:7.2f}  ({len(o['units'])} units)")
