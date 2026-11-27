"""Read the user's lyric file (work/src/lyrics.txt). The text lives only there and in memory: scripts refer to
lines as (section, n) and to characters by position, and nothing written to disk by this project contains it.

File format: section headers in square brackets ("[Verse 1 - male rap]"; the part after " - " is a
performance note), then sung lines. Spaces inside a line separate sung phrases. Repeated section names get a
running number: Pre-Chorus 1/2, Chorus 1/2, Drop 1/2.

LINES: list of dicts
  sec    section key, e.g. 'Verse 2'
  n      line number inside the section, from 1
  chars  sung units: one CJK character, one digit, or one Latin word ('GG'); punctuation dropped
  phr    phrase index of every unit (phrases are the space-separated parts of the line)
  text   the line as written (memory only)
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'work', 'src', 'lyrics.txt')
NUMBERED = ('Pre-Chorus', 'Chorus', 'Drop')


def _units(s):
    out, ph = [], []
    for pi, part in enumerate(s.split()):
        for m in re.finditer(r'[A-Za-z]+|[0-9]|[〇㐀-鿿]', part):
            out.append(m.group(0))
            ph.append(pi)
    return out, ph


def _parse():
    lines, counts, sec = [], {}, None
    for raw in open(SHEET, encoding='utf-8').read().splitlines():
        s = raw.strip()
        if not s:
            continue
        m = re.match(r'^\[(.+?)\]$', s)
        if m:
            name = m.group(1).split(' - ')[0].strip()
            if name in NUMBERED:
                counts[name] = counts.get(name, 0) + 1
                name = f'{name} {counts[name]}'
            sec, n = name, 0
            continue
        n += 1
        ch, ph = _units(s)
        lines.append({'sec': sec, 'n': n, 'chars': ch, 'phr': ph, 'text': s})
    return lines


LINES = _parse()
SECTIONS = []
for _x in LINES:
    if _x['sec'] not in SECTIONS:
        SECTIONS.append(_x['sec'])

EXPECT = {'Intro': 4, 'Verse 1': 7, 'Pre-Chorus 1': 3, 'Chorus 1': 5, 'Drop 1': 1, 'Verse 2': 10,
          'Pre-Chorus 2': 3, 'Chorus 2': 5, 'Bridge': 6, 'Verse 3': 7, 'Build-Up': 2, 'Final Chorus': 5,
          'Drop 2': 1, 'Outro': 5}
_got = {s: sum(1 for x in LINES if x['sec'] == s) for s in SECTIONS}
assert _got == EXPECT, _got


def line(sec, n):
    for x in LINES:
        if x['sec'] == sec and x['n'] == n:
            return x
    raise KeyError((sec, n))


def key(x):
    return f"{x['sec']}|{x['n']}"


if __name__ == '__main__':
    for x in LINES:
        print(f"{key(x):16s} units {len(x['chars']):2d} phrases {max(x['phr']) + 1}")
