#!/usr/bin/env python3
"""Read the user's lyrics file (work/src/lyrics.txt, not in the repo). Section headers are [Intro], [Verse 1] ...;
bracket lines that are not section names are performance notes and are skipped. The two plain [Chorus] headers
become 'Chorus 1' and 'Chorus 2'. Lines are referred to everywhere else by (section, number from 1).

  LINES  -> list of dict(sec, n, text, chars)   chars: the sung characters only (CJK and digits)
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'work', 'src', 'lyrics.txt')
SECTIONS = ['Intro', 'Verse 1', 'Pre-Chorus', 'Chorus 1', 'Verse 2', 'Chorus 2', 'Verse 3', 'Bridge', 'Verse 4',
            'Final Chorus', 'Outro']
EXPECT = [2, 8, 6, 5, 12, 4, 7, 6, 6, 5, 2]


def load():
    out, sec, nch = [], None, 0
    for raw in open(SHEET, encoding='utf-8'):
        s = raw.strip()
        if not s:
            continue
        m = re.fullmatch(r'\[(.+)\]', s)
        if m:
            name = m.group(1).strip()
            if name == 'Chorus':
                nch += 1
                name = f'Chorus {nch}'
            if name in SECTIONS:
                sec = name
            continue
        n = sum(1 for x in out if x['sec'] == sec) + 1
        chars = [c for c in s if '一' <= c <= '鿿' or c.isdigit()]
        out.append({'sec': sec, 'n': n, 'text': s, 'chars': chars})
    got = [sum(1 for x in out if x['sec'] == s) for s in SECTIONS]
    assert got == EXPECT, f'lyrics file does not parse as expected: {got}'
    return out


LINES = load()


def line(sec, n):
    return next(x for x in LINES if x['sec'] == sec and x['n'] == n)
