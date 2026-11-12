#!/usr/bin/env python3
"""Final word timing: forced alignment (median of 16-24 estimates) corrected by reading the separated vocal.

  word_timing.py ALIGN_RAW.json LYRICS.json OUT.json

Whisper's alignment is reliable inside a phrase but puts a line's first word at the end of the preceding
silence (up to 2 s early) and drifts 0.1-0.4 s early elsewhere. SEEN holds starts read off the vocal-only
spectrograms (work/qc/spec/w*.png): the first sung energy of the word (breath / fricative for h-, s-, f-
words, otherwise the vowel). HELD marks the real end of long notes. Words are addressed as (line, word),
1-based, so no lyric text lives in this file.
"""
import json
import sys

raw = json.load(open(sys.argv[1]))
lyr = json.load(open(sys.argv[2], encoding='utf-8'))
out = sys.argv[3]

SEEN = {
    (1, 1): 12.97, (1, 2): 13.42, (1, 3): 13.95, (1, 4): 14.38, (1, 5): 15.58, (1, 6): 16.02,
    (2, 1): 17.62, (2, 2): 18.20, (2, 3): 18.80, (2, 4): 19.22, (2, 5): 19.68,
    (3, 1): 20.90, (3, 2): 21.75, (3, 3): 22.05, (3, 4): 22.64, (3, 5): 23.30, (3, 6): 24.00,
    (4, 1): 25.55, (4, 2): 25.88, (4, 3): 26.20, (4, 4): 26.45, (4, 5): 27.40, (4, 6): 28.12,
    (5, 1): 29.38, (5, 2): 29.78, (5, 3): 30.48, (5, 4): 31.45, (5, 5): 31.72, (5, 6): 32.12,
    (6, 1): 33.78, (6, 2): 34.18, (6, 3): 34.92, (6, 4): 35.42, (6, 5): 35.82,
    (7, 1): 37.82, (7, 2): 38.20, (7, 3): 38.42, (7, 4): 38.98, (7, 5): 39.65, (7, 6): 39.98, (7, 7): 40.28,
    (8, 1): 41.95, (8, 2): 42.20, (8, 3): 42.45, (8, 4): 43.50, (8, 5): 43.88, (8, 6): 44.12,
    (9, 1): 45.45, (9, 2): 45.98, (9, 3): 46.38,
    (10, 1): 49.45, (10, 2): 49.85, (10, 3): 50.45,
    (11, 1): 53.45, (11, 2): 53.75, (11, 3): 54.35, (11, 4): 55.82, (11, 5): 57.42, (11, 6): 57.95, (11, 7): 58.32,
    (12, 1): 61.42, (12, 2): 61.95, (12, 3): 62.38,
}
# real end of long notes / last word of a line
HELD = {(1, 6): 17.15, (2, 5): 20.75, (3, 6): 24.80, (4, 6): 28.60, (5, 6): 32.80, (6, 5): 36.60,
        (7, 7): 41.35, (8, 3): 43.48, (8, 6): 44.85, (9, 3): 47.85, (10, 3): 51.75, (11, 4): 56.80,
        (11, 7): 59.05, (12, 3): 64.10}
# words placed by counting syllables rather than by a clear onset (less sure)
UNSURE = {(2, 2), (2, 3), (5, 4), (5, 5), (7, 6), (8, 2), (8, 5), (9, 2)}

lines = [l['en'].split() for l in lyr['lines']]
al = {(r['line'] + 1, r['word'] + 1): r for r in raw}
res = []
for li, ws in enumerate(lines, 1):
    row = []
    for wi in range(1, len(ws) + 1):
        s = SEEN.get((li, wi), al[(li, wi)]['s'] + 0.15)
        row.append({'s': round(s, 3), 'src': 'seen' if (li, wi) in SEEN else 'align+0.15',
                    'unsure': (li, wi) in UNSURE})
    for wi, w in enumerate(row, 1):
        if (li, wi) in HELD:
            w['e'] = HELD[(li, wi)]
        elif wi < len(row):
            w['e'] = row[wi]['s']
        else:
            w['e'] = w['s'] + 0.6
        assert w['e'] - w['s'] >= 0.12, (li, wi)
    for a, b in zip(row, row[1:]):
        assert b['s'] > a['s'] + 0.04, (li, row)
    res.append({'line': li, 'start': row[0]['s'], 'end': row[-1]['e'], 'words': row})
for a, b in zip(res, res[1:]):
    assert b['start'] > a['end'] - 0.05, (a['line'], b['line'])
json.dump({'hum': [3.95, 4.33, 6.30], 'lines': res}, open(out, 'w'), indent=1)
for r in res:
    print(f"L{r['line']:<2} {r['start']:6.2f}-{r['end']:6.2f}  " + ' '.join(f"{w['s']:.2f}" for w in r['words']))
