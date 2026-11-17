"""Read the user's lyric sheet (kept in work/, never committed) and expose each line as display text + units.

  SHEET = work/audio/lyrics_sheet.txt   (a verbatim copy of the lyrics the user pasted)

A sheet line is addressed by its 1-based line number (L13 = line 13). Stage directions in full-width
parentheses （…） are not lyrics and are removed; everything else stays exactly as written, including
quotes, dashes, question marks and half-width call-backs such as (Back!).

display(n)  -> the exact on-screen text of line n
units(n)    -> sung units of line n: one CJK character or one Latin word each, with the character span
               [a, b) it owns in display(n). Punctuation is owned by the unit it touches (leading quotes and
               ellipses by the next unit, everything else by the previous one), so a character is revealed
               exactly when the syllable it belongs to is sung.
phrases(n)  -> display(n) cut at spaces into chunks (Latin runs stay together) for row layout.
"""
import json
import re

SHEET = 'work/audio/lyrics_sheet.txt'
TIMING = 'work/audio/lyric_timing.json'

_CJK = r'[㐀-鿿豈-﫿]'
_WORD = r"[A-Za-z0-9][A-Za-z0-9'’\-]*"
_TOK = re.compile(rf'({_CJK})|({_WORD})')
_OPENERS = '“‘(（《…'


def _opens(s, k):
    c = s[k]
    if c == '"':
        return s[:k].count('"') % 2 == 0
    return c in _OPENERS


def raw_lines():
    with open(SHEET, encoding='utf-8') as f:
        return [l.rstrip('\n').rstrip('\r') for l in f]


def display(n):
    s = raw_lines()[n - 1]
    if s.startswith('['):
        return ''
    s = re.sub(r'（[^）]*）', '', s)
    return s.strip()


def units(n):
    s = display(n)
    out = []
    depth = 0
    toks = list(_TOK.finditer(s))
    for m in toks:
        a, b = m.span()
        depth = s[:a].count('(') - s[:a].count(')')
        out.append({'t': m.group(0), 'cjk': bool(m.group(1)), 'adlib': depth > 0, 'a': a, 'b': b})
    # give every non-space, non-unit character to a unit
    owner = [-1] * len(s)
    for i, u in enumerate(out):
        for k in range(u['a'], u['b']):
            owner[k] = i
    for k, c in enumerate(s):
        if owner[k] >= 0 or c.isspace():
            continue
        nxt = next((i for i, u in enumerate(out) if u['a'] > k), None)
        prv = max((i for i, u in enumerate(out) if u['b'] <= k), default=None)
        if _opens(s, k) and nxt is not None:
            owner[k] = nxt
        elif prv is not None:
            owner[k] = prv
        else:
            owner[k] = nxt if nxt is not None else 0
    for i, u in enumerate(out):
        ks = [k for k in range(len(s)) if owner[k] == i]
        u['span'] = (min(ks), max(ks) + 1)
    return out


def owner_map(n):
    """For each display character of line n: the index of the unit that reveals it (spaces: -1)."""
    s = display(n)
    us = units(n)
    own = [-1] * len(s)
    for i, u in enumerate(us):
        for k in range(len(s)):
            pass
    # recompute with the same rule as units() (kept explicit for clarity)
    for i, u in enumerate(us):
        a, b = u['a'], u['b']
        for k in range(a, b):
            own[k] = i
    for k, c in enumerate(s):
        if own[k] >= 0 or c.isspace():
            continue
        nxt = next((i for i, u in enumerate(us) if u['a'] > k), None)
        prv = max((i for i, u in enumerate(us) if u['b'] <= k), default=None)
        if _opens(s, k) and nxt is not None:
            own[k] = nxt
        elif prv is not None:
            own[k] = prv
        else:
            own[k] = nxt if nxt is not None else 0
    return own


def phrases(n):
    """Chunks of display(n) for row layout, as (a, b) character spans. Cut at spaces and in front of an
    opening parenthesis or quote; a parenthesised call-back or a quotation stays in one chunk, consecutive
    Latin words stay together, and a lone dash joins the chunk before it."""
    s = display(n)
    cuts = []
    a = None
    depth = 0
    for k, c in enumerate(s):
        opening = c == '(' or c in '“' or (c == '"' and _opens(s, k))
        closing = c == ')' or c in '”' or (c == '"' and not _opens(s, k))
        if a is not None and depth == 0 and (c.isspace() or (opening and k > a)):
            cuts.append((a, k))
            a = None
        if not c.isspace() and a is None:
            a = k
        if opening:
            depth += 1
        elif closing:
            depth = max(0, depth - 1)
    if a is not None:
        cuts.append((a, len(s)))
    out = []
    for a, b in cuts:
        w = s[a:b]
        latin = not re.search(_CJK, w) and bool(re.search(r'[A-Za-z]', w)) and w[0] not in '(“"'
        if out and w.strip('—') == '':
            out[-1] = (out[-1][0], b, out[-1][2])
        elif out and latin and out[-1][2] and not s[out[-1][0]:out[-1][1]].endswith('—'):
            out[-1] = (out[-1][0], b, True)
        else:
            out.append((a, b, latin))
    return [(a, b) for a, b, _ in out]


def align_text(us):
    """Text handed to the aligner: CJK characters run together, Latin words separated by spaces."""
    out, spans, prev_cjk = '', [], True
    for u in us:
        if out and not (u['cjk'] and prev_cjk):
            out += ' '
        a = len(out)
        out += u['t']
        spans.append((a, len(out)))
        prev_cjk = u['cjk']
    return out, spans


def load_timing():
    with open(TIMING, encoding='utf-8') as f:
        return json.load(f)


if __name__ == '__main__':
    import sys
    rng = map(int, sys.argv[1:]) if len(sys.argv) > 1 else range(1, len(raw_lines()) + 1)
    for n in rng:
        d = display(n)
        if not d:
            continue
        us = units(n)
        print(f'L{n:<3} {len(us):2d}u  ' + ' | '.join(d[a:b] for a, b in phrases(n)) + '   ::  ' +
              ' '.join(('[' if u['adlib'] else '') + d[u['span'][0]:u['span'][1]] + (']' if u['adlib'] else '')
                       for u in us))
