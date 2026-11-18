"""Lay a lyric line out as flap slots.

A slot is one cell: (dx, row, w, char, unit, kind). dx/row are relative to the line's top-left corner,
w is 1.0 for CJK and full-width punctuation, 0.5 for Latin letters, digits and ASCII punctuation.
unit is the index of the timing unit that makes this slot land (punctuation rides with its neighbour);
kind is 'main' or 'back' (inside parentheses: backing vocal).

Rows follow the sheet's own spaces: each phrase starts a row; very short phrases share a row with the next one
when they fit. Phrases wider than the block are wrapped (WRAP gives the preferred break, by character offset
inside the phrase). Every character of the line except spaces and the phrase-break dash ends up in a slot,
and assert_complete() checks that.
"""
import re

from flap import is_half

OPENERS = '(《“"'


def slots_for(text, a, b, unit_of, kind):
    """slots (dx, char, w, unit, kind) for text[a:b] on one row, dx from 0."""
    out = []
    x = 0.0
    quote_open = False
    k = a
    while k < b:
        ch = text[k]
        if ch == ' ':
            # a space inside a phrase only exists between Latin words
            x += 0.5
            k += 1
            continue
        w = 0.5 if is_half(ch) else 1.0
        u = unit_of[k]
        if u is None:
            # punctuation: openers ride with the next unit, the rest with the previous one
            opener = ch in '(《“' or (ch == '"' and not quote_open)
            if ch == '"':
                quote_open = not quote_open
            j = k
            if opener:
                while j < len(text) and unit_of[j] is None:
                    j += 1
                u = unit_of[j] if j < len(text) else None
            else:
                while j >= 0 and unit_of[j] is None:
                    j -= 1
                u = unit_of[j] if j >= 0 else None
            if u is None:
                j = k
                while j < len(text) and unit_of[j] is None:
                    j += 1
                u = unit_of[j] if j < len(text) else 0
        out.append([x, ch, w, u, kind])
        x += w
        k += 1
    return out, x


def unit_index_map(line):
    unit_of = [None] * len(line['text'])
    for ui, (tok, s, e, bk) in enumerate(line['units']):
        for k in range(s, e):
            unit_of[k] = ui
    return unit_of


def layout_line(line, maxw=10.0, merge_short=2.6, wrap=None, back_align='right', back_newrow=True,
                group=None):
    """rows of slots for one line. Returns (slots, width, nrows); slot = (dx, row, w, char, unit, kind).
    group: optional explicit list of lists of phrase indices that share a row."""
    text = line['text']
    unit_of = unit_index_map(line)
    phr = [slots_for(text, a, b, unit_of, 'main') for a, b in line['phr']]
    spans = list(line['phr'])
    # wrap long phrases
    pieces = []
    for pi, ((sl, wdt), (a, b)) in enumerate(zip(phr, spans)):
        if wdt <= maxw + 1e-6:
            pieces.append((sl, wdt, pi))
            continue
        brk = (wrap or {}).get(pi)
        if brk is None:
            # split into balanced halves, never inside a Latin word
            best = None
            for j in range(1, len(sl)):
                if sl[j][2] == 0.5 and sl[j - 1][2] == 0.5:
                    continue
                left = sl[j][0]
                if left > maxw or wdt - left > maxw:
                    continue
                score = abs(left - (wdt - left))
                if best is None or score < best[0]:
                    best = (score, j)
            brk = best[1]
        L = sl[:brk]
        R = [[s[0] - sl[brk][0]] + s[1:] for s in sl[brk:]]
        pieces.append((L, sl[brk][0], pi))
        pieces.append((R, wdt - sl[brk][0], pi))
    # group into rows
    rows = []
    if group is not None:
        by_pi = {}
        for p in pieces:
            by_pi.setdefault(p[2], []).append(p)
        for g in group:
            row = []
            for pi in g:
                row += by_pi[pi]
            rows.append(row)
    else:
        cur = []
        curw = 0.0
        for p in pieces:
            sl, wdt, pi = p
            gapw = 1.0
            if cur and curw + gapw + wdt <= maxw + 1e-6 and (wdt <= merge_short or curw <= merge_short):
                cur.append(p)
                curw += gapw + wdt
            else:
                if cur:
                    rows.append(cur)
                cur = [p]
                curw = wdt
        if cur:
            rows.append(cur)
    slots = []
    width = 0.0
    for r, row in enumerate(rows):
        x = 0.0
        for j, (sl, wdt, pi) in enumerate(row):
            if j:
                x += 1.0
            for s in sl:
                slots.append((x + s[0], r, s[2], s[1], s[3], 'main'))
            x += wdt
        width = max(width, x)
    nrows = len(rows)
    # backing vocals
    for (a, b) in line['back']:
        sl, wdt = slots_for(text, a, b, unit_of, 'back')
        if wdt > maxw:
            # break at a space
            cut = None
            for j in range(1, len(sl)):
                if sl[j][0] - (sl[j - 1][0] + sl[j - 1][2]) > 0.2 and sl[j][0] <= maxw:
                    cut = j
            parts = [sl[:cut], [[s[0] - sl[cut][0]] + s[1:] for s in sl[cut:]]]
        else:
            parts = [sl]
        for part in parts:
            pw = part[-1][0] + part[-1][2]
            if not back_newrow and nrows and part is parts[0]:
                pass
            x0 = (maxw - pw) if back_align == 'right' else 0.0
            x0 = round(x0 * 2) / 2
            for s in part:
                slots.append((x0 + s[0], nrows, s[2], s[1], s[3], 'back'))
            nrows += 1
            width = max(width, x0 + pw)
    return slots, width, nrows


def assert_complete(line, slots):
    """every non-space character of the line appears exactly once, except the phrase-break dash."""
    want = [c for c in line['text'] if c not in ' —']
    got = sorted(s[3] for s in slots)
    assert sorted(want) == got, (line['i'], ''.join(sorted(want)), ''.join(got))
