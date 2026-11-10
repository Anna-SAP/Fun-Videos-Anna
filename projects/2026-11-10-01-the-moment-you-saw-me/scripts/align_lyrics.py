#!/usr/bin/env python3
"""Put a time on every word of the lyric sheet.

  align_lyrics.py            (run from the project folder; needs work/audio/{v1,v2,pre1,pre2,ch1,ch2}.m4a)

whisper-1 is asked for word timestamps on each vocal-focused excerpt, with that section's lines from the
sheet as its prompt so it hears the right words. Both tellings are transcribed; the recording repeats
exactly after 80.000 s, so every word gets several independent estimates (prompted and unprompted, first
and second telling, plus the whole-song pass) and the median is kept. Words no run matched are placed by
interpolation inside their line.
"""
import difflib
import json
import os
import statistics
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lyrics import EN, REPEAT, TIMING, norm  # noqa: E402

A = 'work/audio'
# excerpt, start in the song, which lines it holds, telling
SECTIONS = [('v1', 13, range(0, 6), 0), ('pre1', 40, range(6, 8), 0), ('ch1', 53, range(8, 16), 0),
            ('v2', 93, range(0, 6), 1), ('pre2', 120, range(6, 8), 1), ('ch2', 133, range(8, 16), 1)]

ref = [(li, wi, norm(w)) for li, ws in enumerate(EN) for wi, w in enumerate(ws)]
est = {(li, wi): [] for li, wi, _ in ref}


def take(words, offset, lines, shift):
    toks = [(li, wi, w) for li, wi, w in ref if li in lines]
    a = [w for _, _, w in toks]
    b = [norm(w['word']) for w in words]
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                w = words[j1 + k]
                li, wi, _ = toks[i1 + k]
                est[(li, wi)].append((w['start'] + offset - shift, w['end'] + offset - shift))


for name, off, lines, tell in SECTIONS:
    prompted = f'{A}/a_{name}.json'
    if not os.path.exists(prompted):
        prompt = ', '.join(' '.join(EN[i]) for i in lines)
        subprocess.run([sys.executable, 'scripts/transcribe.py', f'{A}/{name}.m4a', prompted, 'whisper-1', prompt], check=True,
                       stdout=subprocess.DEVNULL)
    for path in (prompted, f'{A}/t_{name}_whisper-1.json'):
        if os.path.exists(path):
            take(json.load(open(path, encoding='utf-8')).get('words', []), off, set(lines), REPEAT * tell)
full = json.load(open(f'{A}/whisper.json', encoding='utf-8'))['words']
take([w for w in full if w['start'] < 90], 0, set(range(16)), 0)
take([w for w in full if w['start'] >= 90], 0, set(range(16)), REPEAT)

out = []
for li, ws in enumerate(EN):
    row = []
    for wi in range(len(ws)):
        e = est[(li, wi)]
        row.append([statistics.median(x[0] for x in e), statistics.median(x[1] for x in e), len(e)] if e else [None, None, 0])
    out.append(row)
# fill the gaps, keep order, give every word a sensible length
flat = [(li, wi) for li, ws in enumerate(EN) for wi in range(len(ws))]
for k, (li, wi) in enumerate(flat):
    if out[li][wi][0] is None:
        prev = next((out[a][b] for a, b in reversed(flat[:k]) if out[a][b][0] is not None), None)
        nxt = next(((out[a][b], j) for j, (a, b) in enumerate(flat[k + 1:], 1) if out[a][b][0] is not None), None)
        s = prev[1] if prev else nxt[0][0] - .4
        e = s + (nxt[0][0] - s) / (nxt[1]) if nxt else s + .4
        out[li][wi] = [s, e, 0]
# whisper hands the silence before a phrase to its first word, so phrase-initial words come out early.
# These starts were read off vocal-band spectrograms (work/qc/vocal_a.png, vocal_b.png; 200 px per second):
# the first formant energy of the phrase, or the sibilant for words that begin with one.
SEEN = {(0, 0): 15.5, (1, 0): 18.7, (2, 0): 22.0, (5, 0): 35.3, (6, 0): 42.3, (6, 1): 43.0, (7, 0): 49.1, (8, 0): 54.45,
        (9, 0): 58.95, (11, 0): 65.75, (12, 1): 68.98, (12, 2): 69.42, (13, 0): 71.75, (15, 0): 78.55, (15, 3): 82.55}
HELD = {(6, 1): 46.4, (7, 1): 53.6, (15, 2): 82.5, (13, 4): 75.2, (5, 3): 40.9}      # long notes: where the word really ends
for (li, wi), s in SEEN.items():
    out[li][wi][0] = s
for li, row in enumerate(out):
    for wi, w in enumerate(row):
        if wi + 1 < len(row):
            w[1] = row[wi + 1][0]
for (li, wi), e in HELD.items():
    out[li][wi][1] = e
last = 0.0
for li, wi in flat:
    s, e, n = out[li][wi]
    s = max(s, last + .04)
    e = max(e, s + .12)
    out[li][wi] = [round(s, 3), round(e, 3), n]
    last = s
json.dump({'lines': [{'words': [{'s': s, 'e': e, 'n': n} for s, e, n in row]} for row in out]}, open(TIMING, 'w'), indent=1)
for li, row in enumerate(out):
    print(f'E{li + 1:<2d} {row[0][0]:6.2f}-{row[-1][1]:6.2f}  ' + ' '.join(f'{s:.2f}({n})' for s, e, n in row))
