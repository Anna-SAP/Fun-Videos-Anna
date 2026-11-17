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
    ('i1', 0): 4.95,                                        # the news sample: vocal stem silent until 4.58
    ('i2', 0): 8.05, ('i2', 1): 8.70, ('i2', 2): 9.08,      # a scratched 'Week' (8.05-8.45), then 'two'
    ('v1d', 18): 32.25, ('v1e', 0): 32.48,                  # the aligner let 'Elon' start before the last word
    ('b1', 3): 141.45, ('b1', 4): 141.65,                   # build: the speaker labels are not sung (see TAGS)
    ('b2', 4): 143.65, ('b2', 5): 143.90, ('b2', 6): 144.15, ('b2', 7): 144.45,
    ('b3', 3): 146.30, ('b3', 4): 146.48, ('b3', 5): 146.64,
    ('b6', 1): 152.15, ('b6', 2): 152.50, ('b6', 3): 152.92,  # san / er / yi read off the formants
    ('o8', 0): 297.47,                                      # the last line starts after 6 s of piano
}
# leading units that are a printed speaker tag rather than sung syllables: shown with the first sung unit
TAGS = {'b1': 3, 'b2': 4, 'b3': 3}
# the drop chants the same line twice; forced alignment cannot tell the copies apart (IQR > 1 s), so the
# 20 units take the 20 strongest vocal onsets (scripts/vocal_onsets.py 153.4 160.25 0.18) in order
ONSETS = {
    'd1': [153.67, 154.01, 154.35, 154.67, 155.02, 155.21, 155.39, 155.57, 155.85, 156.06],
    'd2': [156.44, 156.78, 157.15, 157.48, 157.87, 158.17, 158.57, 158.85, 159.20, 159.53],
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
    if r['id'] in ONSETS:
        s = list(ONSETS[r['id']])
        en = [None] * n
    nt = TAGS.get(r['id'], 0)
    for i in range(nt):
        s[i] = s[nt]
        en[i] = s[nt] + 0.3
    for i in range(max(1, nt + 1), n):
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
