#!/usr/bin/env python3
"""Per-character timing for the lyric layer -> work/audio/lyric_timing.json (times only, no lyric text).

What is sung is not exactly the lyric file: the recording repeats a few things (measured, see storyboard.md).
SUNG lists every sung occurrence as (id, section, line, first unit, end unit, window): a lyric line, or a slice of
one when only part of it is repeated. WIN windows come from reading the transcriptions (seconds only).

Estimates per character start, up to eight:
  - MMS CTC forced alignment of the occurrence inside its window, on the vocal stem and on the mix (ctc.py)
  - whisper-1 word times from six transcriptions: whole song (mix, vocal stem) and per section (vocal stem,
    with and without the lyric prompt), mapped to the lyric characters by aligning toneless pinyin (so a
    homophone the recogniser wrote with another character still counts)
The start is the median of the estimates within 0.25 s of the overall median. HAND overrides the few starts
read off the vocal level / spectrogram where the recognisers do not hear the words (the drop chant, shouted).
Ends: next character's start; the last character of an occurrence ends at the CTC end (at least 0.3 s).
"""
import difflib
import glob
import json
import os
import sys

import numpy as np
from pypinyin import lazy_pinyin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctc  # noqa: E402
import lyrics  # noqa: E402

W = {
    ('Intro', 1): (8.3, 12.6), ('Intro', 2): (12.0, 15.8), ('Intro', 3): (14.6, 18.9), ('Intro', 4): (18.4, 23.1),
    ('Verse 1', 1): (22.6, 26.2), ('Verse 1', 2): (25.7, 29.8), ('Verse 1', 3): (29.2, 33.3), ('Verse 1', 4): (32.7, 36.7),
    ('Verse 1', 5): (36.1, 40.1), ('Verse 1', 6): (39.5, 43.9), ('Verse 1', 7): (43.3, 50.2),
    ('Pre-Chorus 1', 1): (50.2, 55.1), ('Pre-Chorus 1', 2): (54.4, 57.9), ('Pre-Chorus 1', 3): (57.45, 59.12),
    ('Chorus 1', 1): (58.9, 62.3), ('Chorus 1', 2): (61.8, 65.7), ('Chorus 1', 3): (65.1, 69.3), ('Chorus 1', 4): (68.6, 71.9),
    ('Chorus 1', 5): (71.2, 74.1),
    ('Drop 1', 1): (80.6, 85.4),
    ('Verse 2', 1): (86.9, 90.1), ('Verse 2', 2): (89.8, 94.3), ('Verse 2', 3): (93.7, 97.3), ('Verse 2', 4): (96.7, 101.3),
    ('Verse 2', 5): (100.7, 104.5), ('Verse 2', 6): (103.8, 107.9), ('Verse 2', 7): (107.6, 111.9), ('Verse 2', 8): (111.1, 115.5),
    ('Verse 2', 9): (114.8, 118.9), ('Verse 2', 10): (118.3, 122.8),
    ('Pre-Chorus 2', 1): (122.5, 126.3), ('Pre-Chorus 2', 2): (125.9, 129.7), ('Pre-Chorus 2', 3): (129.2, 130.55),
    ('Chorus 2', 1): (130.3, 133.6), ('Chorus 2', 2): (133.0, 137.1), ('Chorus 2', 3): (136.4, 140.6), ('Chorus 2', 4): (139.9, 143.2),
    ('Chorus 2', 5): (142.6, 145.3),
    ('Bridge', 1): (144.7, 148.6), ('Bridge', 2): (148.2, 152.0), ('Bridge', 3): (151.4, 153.9), ('Bridge', 4): (153.2, 156.1),
    ('Bridge', 5): (155.3, 158.2), ('Bridge', 6): (157.6, 162.1),
    ('Verse 3', 1): (161.4, 165.1), ('Verse 3', 2): (164.8, 168.7), ('Verse 3', 3): (168.4, 171.1), ('Verse 3', 4): (170.5, 173.0),
    ('Verse 3', 5): (172.3, 174.6), ('Verse 3', 6): (173.9, 176.0), ('Verse 3', 7): (175.4, 177.1),
    ('Build-Up', 1): (176.3, 180.5), ('Build-Up', 2): (179.9, 183.9),
    ('Final Chorus', 1): (183.3, 186.9), ('Final Chorus', 2): (186.4, 190.4), ('Final Chorus', 3): (189.7, 193.9),
    ('Final Chorus', 4): (193.2, 200.8), ('Final Chorus', 5): (200.1, 202.8),
    ('Outro', 1): (210.5, 215.1), ('Outro', 2): (214.5, 218.8), ('Outro', 3): (218.1, 222.1), ('Outro', 4): (221.5, 226.1),
    ('Outro', 5): (225.7, 230.1),
}
# (id, section, line, unit a, unit b, window); b=None means to the end of the line
SUNG = []
for (s, n), w in W.items():
    SUNG.append((f'{s}|{n}', s, n, 0, None, w))
# repeats the recording adds (measured): the last phrase of chorus 1 line 5 echoed, then the whole line again;
# drop 2's line is sung as two separate shouts; the outro's last line comes twice
SUNG += [('Chorus 1|5#echo', 'Chorus 1', 5, 4, None, (75.3, 77.7)),
         ('Chorus 1|5#again', 'Chorus 1', 5, 0, None, (78.0, 80.9)),
         ('Drop 2|1#a', 'Drop 2', 1, 0, 4, (202.6, 206.0)),
         ('Drop 2|1#b', 'Drop 2', 1, 4, None, (206.2, 210.4)),
         ('Outro|5#again', 'Outro', 5, 0, None, (232.8, 237.4))]
SUNG.sort(key=lambda e: e[5][0])
# shouted chant: one shout every two beats on beats 2 and 4 of bars 46-48 (vocal-stem level onsets); each shout
# is two characters, the second about a third of a beat later
HAND = {}
for k, t in enumerate((81.01, 81.90, 82.79, 83.68, 84.58)):
    HAND[('Drop 1|1', 2 * k)] = t
    HAND[('Drop 1|1', 2 * k + 1)] = t + 0.17
# the name in the pre-chorus 1 stop: CTC on stem and mix agree on the first and last syllable
HAND[('Pre-Chorus 1|3', 0)] = 57.70
HAND[('Pre-Chorus 1|3', 2)] = 58.58


def py(chars):
    out = []
    for c in chars:
        p = lazy_pinyin(c)
        out.append(p[0].lower() if p and p[0] else c.lower())
    return out


def asr_sources():
    srcs = []
    for p in ['work/audio/whisper_full.json', 'work/audio/whisper_voc.json'] + sorted(glob.glob('work/audio/asr/*_*.json')):
        d = json.load(open(p))
        off = d.get('offset', 0.0)
        seq = []
        for w in d.get('words', []):
            txt = [c for c in w['word'] if '〇' <= c <= '鿿' or c.isdigit()]
            if not txt:
                continue
            dd = (w['end'] - w['start']) / len(txt)
            for i, c in enumerate(txt):
                seq.append((py([c])[0], off + w['start'] + i * dd))
        srcs.append((os.path.basename(p), seq))
    return srcs


DIGIT = {'0': 'ling', '1': 'yi', '2': 'er', '3': 'san', '4': 'si', '5': 'wu', '6': 'liu', '7': 'qi', '8': 'ba', '9': 'jiu'}


def asr_est(units_py, t0, t1, seq):
    sub = [(p, t) for p, t in seq if t0 - 0.3 <= t <= t1 + 0.3]
    sub = [(DIGIT.get(p, p), t) for p, t in sub]
    sm = difflib.SequenceMatcher(a=units_py, b=[p for p, _ in sub], autojunk=False)
    est = [None] * len(units_py)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            est[a + k] = sub[b + k][1]
    return est


def main():
    srcs = asr_sources()
    res, report = [], []
    for sid, s, n, a, b, (t0, t1) in SUNG:
        x = lyrics.line(s, n)
        units = x['chars'][a:b]
        upy = py(units)
        ids = [ctc.romanise_py(p) if p.isalpha() else ctc.romanise_py('gg') for p in upy]
        rv = ctc.align(ids, t0, t1, 'voc')
        rm = ctc.align(ids, t0, t1, 'mix')
        ests = []
        if rv:
            ests.append([r[0] for r in rv])
        if rm:
            ests.append([r[0] for r in rm])
        ests += [asr_est(upy, t0, t1, seq) for _, seq in srcs]
        starts, nest = [], []
        for i in range(len(units)):
            if (sid, i) in HAND:
                starts.append(HAND[(sid, i)])
                nest.append(-1)
                continue
            e = np.array([es[i] for es in ests if es[i] is not None and t0 - 0.3 <= es[i] <= t1 + 0.3])
            if len(e) == 0:
                starts.append(None)
                nest.append(0)
                continue
            med = np.median(e)
            keep = e[np.abs(e - med) <= 0.25]
            starts.append(float(np.median(keep if len(keep) else e)))
            nest.append(len(e))
        # fill gaps by interpolation inside the occurrence
        idx = [i for i, v in enumerate(starts) if v is not None]
        for i in range(len(starts)):
            if starts[i] is None:
                starts[i] = float(np.interp(i, idx, [starts[j] for j in idx]))
        st = np.array(starts)
        for i in range(1, len(st)):
            st[i] = max(st[i], st[i - 1] + 0.06)
        ctc_end = max([r[1] for r in (rv or [])[-1:]] + [r[1] for r in (rm or [])[-1:]] + [st[-1] + 0.3])
        en = list(st[1:]) + [max(ctc_end, st[-1] + 0.3)]
        cv = float(np.mean([r[2] for r in rv])) if rv else 0.0
        res.append({'id': sid, 'sec': s, 'n': n, 'a': a, 'b': b if b is not None else len(x['chars']),
                    'start': [round(float(v), 3) for v in st], 'end': [round(float(v), 3) for v in en],
                    'nest': nest, 'ctc': round(cv, 3)})
        report.append((sid, st[0], en[-1], np.mean([q for q in nest if q >= 0] or [0]), cv))
    # one voice cannot sing two lines at once: where the merged estimates of a line's last characters run past
    # the next line's first character, squeeze those characters evenly in before it (min 0.06 s apart)
    for p, q in zip(res, res[1:]):
        lim = q['start'][0] - 0.06
        st = p['start']
        if st[-1] <= lim:
            continue
        i = len(st) - 1
        while i > 0 and st[i] > lim - 0.06 * (len(st) - 1 - i):
            i -= 1
        lo = st[i]
        k = len(st) - 1 - i
        step = max(0.04, (lim - lo) / max(k, 1))
        for j in range(1, k + 1):
            st[i + j] = round(min(lo + step * j, lim), 3)
        p['end'] = [round(x, 3) for x in st[1:]] + [p['end'][-1]]
        report.append((p['id'] + ' squeezed', st[i], st[-1], k, 0.0))
    # no overlap between occurrences
    for p, q in zip(res, res[1:]):
        if p['end'][-1] > q['start'][0] - 0.02:
            p['end'][-1] = round(max(p['start'][-1] + 0.12, q['start'][0] - 0.02), 3)
    json.dump(res, open('work/audio/lyric_timing.json', 'w'), indent=0)
    for sid, a, b, ne, cv in report:
        print(f'{sid:22s} {a:7.2f} - {b:7.2f}  est/char {ne:4.1f}  ctc {cv:.2f}')


if __name__ == '__main__':
    main()
