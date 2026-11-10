"""The lyric sheet, read from the user's own file. No lyric text lives in these scripts.

The file is: credit lines ("role：name"), then pairs of an English line and a Chinese line in full-width
brackets, the whole song written out twice, then a rights notice. The two tellings are identical, so the
film works with the 16 distinct lines (E1..E16 here are index 0..15) and adds REPEAT seconds for the
second telling.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.normpath(os.path.join(HERE, '..', '..', '..', 'TheMomentYouSawMe_lyrics.txt'))
TIMING = os.path.normpath(os.path.join(HERE, '..', 'work', 'audio', 'lyric_timing.json'))
REPEAT = 80.0


def norm(w):
    return re.sub(r"[^a-z']", '', w.lower())


def read_sheet(path=SHEET):
    rows = [r.strip() for r in open(path, encoding='utf-8').read().splitlines() if r.strip()]
    credits, pairs, notice = [], [], ''
    i = 0
    while i < len(rows) and re.match(r'^[^：:（(]{1,12}[：:]', rows[i]):
        k, v = re.split(r'[：:]', rows[i], maxsplit=1)
        credits.append((k.strip(), v.strip()))
        i += 1
    while i < len(rows):
        r = rows[i]
        if re.match(r'^[A-Za-z]', r):
            zh = ''
            if i + 1 < len(rows) and rows[i + 1][0] in '（(':
                zh = rows[i + 1].strip('（()） ')
                i += 1
            pairs.append((r, zh))
        else:
            notice = r
        i += 1
    half = len(pairs) // 2
    assert pairs[:half] == pairs[half:], 'expected the song written out twice'
    return credits, pairs[:half], notice


CREDITS, LINES, NOTICE = read_sheet()
EN = [en.split() for en, _ in LINES]
ZH = [zh for _, zh in LINES]


def timing():
    """Per line: list of (start, end) for each word, first telling."""
    d = json.load(open(TIMING, encoding='utf-8'))
    return [[(w['s'], w['e']) for w in ln['words']] for ln in d['lines']]
