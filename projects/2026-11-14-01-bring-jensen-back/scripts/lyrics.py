"""Read the user's lyric sheet (never copied into the repo) and turn each sheet line into display units.

  SHEET = work/audio/lyrics_sheet.txt   (a copy of the user's file; work/ is not committed)

A sheet line is addressed by its 1-based line number in that file (L13 = line 13). Stage directions in
full-width parentheses （…） are dropped. Half-width parentheses hold call-and-response ad-libs, e.g. (Back!):
they are kept as units with adlib=True.

A unit is one sung syllable-ish item: one CJK character, or one Latin word (Thirty-three, he's, CUDA, 1600).
Punctuation never becomes a unit; it is attached to the unit before it for display. Each unit records
whether a space came before it and which phrase (space/dash separated chunk) it belongs to, so the type
layer can lay a line out in rows.
"""
import json
import re

SHEET = 'work/audio/lyrics_sheet.txt'
TIMING = 'work/audio/lyric_timing.json'

_CJK = r'[㐀-鿿豈-﫿]'
_WORD = r"[A-Za-z0-9][A-Za-z0-9'’\-]*"
_TOK = re.compile(rf'({_CJK})|({_WORD})|(\s+)|(.)')


def raw_lines():
    with open(SHEET, encoding='utf-8') as f:
        return [l.rstrip('\n').rstrip('\r') for l in f]


def units(n, keep_adlib=True):
    """Units of sheet line n (1-based). Each unit: dict(t=text, cjk, adlib, space, phrase, punct)."""
    s = raw_lines()[n - 1]
    s = re.sub(r'（[^）]*）', ' ', s)          # stage directions
    s = s.replace('《', '').replace('》', '')
    out = []
    adlib = False
    phrase = 0
    pending_space = False
    for m in _TOK.finditer(s):
        cjk, word, sp, other = m.groups()
        if sp:
            pending_space = True
            continue
        if other:
            if other == '(':
                adlib = True
                phrase += 1
            elif other == ')':
                adlib = False
                phrase += 1
            elif other in '—':
                phrase += 1
            elif out:
                out[-1]['punct'] += other
                if other in ',，。?？!！':
                    pending_space = True
            continue
        if pending_space and out and not out[-1]['adlib'] == adlib:
            pass
        if pending_space and out:
            phrase += 1 if (cjk or out[-1]['cjk'] or out[-1]['punct']) else 0
        u = {'t': cjk or word, 'cjk': bool(cjk), 'adlib': adlib, 'space': pending_space and bool(out),
             'phrase': phrase, 'punct': ''}
        if not keep_adlib and adlib:
            pending_space = False
            continue
        out.append(u)
        pending_space = False
    # renumber phrases 0..k
    ids = {p: i for i, p in enumerate(sorted({u['phrase'] for u in out}))}
    for u in out:
        u['phrase'] = ids[u['phrase']]
    return out


def text(n):
    """Display text of a line (for on-screen use only)."""
    out = ''
    for u in units(n):
        if u['space']:
            out += ' '
        out += u['t'] + u['punct']
    return out


def align_text(n, keep_adlib=True):
    """Text handed to the aligner: CJK characters run together, Latin words separated by spaces."""
    out = ''
    prev_cjk = True
    for u in units(n, keep_adlib):
        if out and not (u['cjk'] and prev_cjk):
            out += ' '
        out += u['t']
        prev_cjk = u['cjk']
    return out


def load_timing():
    with open(TIMING, encoding='utf-8') as f:
        return json.load(f)


if __name__ == '__main__':
    import sys
    for n in (map(int, sys.argv[1:]) if len(sys.argv) > 1 else range(1, len(raw_lines()) + 1)):
        us = units(n)
        if us:
            print(f'L{n:<3} {len(us):2d}u  ' + ' | '.join(
                ''.join(('[' if u['adlib'] else '') + u['t'] + (']' if u['adlib'] else '') for u in us if u['phrase'] == p)
                for p in range(max(u['phrase'] for u in us) + 1)))
