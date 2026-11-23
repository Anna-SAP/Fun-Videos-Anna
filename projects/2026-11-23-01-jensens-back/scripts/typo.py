"""Display tokens and poster-block layout.

A display token is one timing unit of the sheet (a CJK character or a Latin word / number) together with the
punctuation that hangs on it, so what is on screen is the sheet's own text, character for character. A block is a
set of rows; every row is set as large as the box allows, so a line of lyrics fills the frame like a poster.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import LAT_SCALE, is_cjk, sprite  # noqa: E402

OPEN = '(（“‘「『《['


def tokens(line):
    """-> list of dicts: text, u (unit index), back, sp (space before), dash (em dash after), br (phrase break before)"""
    text, us = line['text'], line['units']
    toks = []
    pend_open, pend_sp = '', False
    pos = 0
    nq = 0
    for ui, (u, a, b, back) in enumerate(us):
        gap = text[pos:a]
        for k, ch in enumerate(gap):
            if ch.isspace():
                pend_sp = True
                continue
            if ch == '—':
                if toks:
                    toks[-1]['dash'] = True
                else:
                    pend_open += ch
                continue
            if ch == '"':
                # ASCII quotes pair up within a line: 1st opens, 2nd closes, ...
                opening = nq % 2 == 0
                nq += 1
            else:
                opening = ch in OPEN or (ch == '…' and all(c in OPEN + '"…' for c in gap[k:]))
            if opening or not toks:
                pend_open += ch
            else:
                toks[-1]['text'] += ch
        toks.append({'text': pend_open + text[a:b], 'u': ui, 'back': bool(back), 'sp': pend_sp, 'dash': False,
                     'cjk': is_cjk(u[0])})
        pend_open, pend_sp = '', False
        pos = b
    for ch in text[pos:]:
        if ch.isspace():
            continue
        if ch == '—':
            toks[-1]['dash'] = True
        else:
            toks[-1]['text'] += ch
    for t in toks:
        t['q0'] = t['text'].count('"')
    got = ''.join(t['text'] + ('—' if t['dash'] else '') for t in toks)
    want = ''.join(text.split())
    assert got == want, (got, want)
    return toks


def tok_w(t):
    """rough width of a token in CJK ems (for automatic row breaking)."""
    return sum(1.0 if is_cjk(c) else 0.5 for c in t['text'])


def auto_rows(toks, target=5.0, maxrows=6):
    """group tokens into rows at the sheet's own breaks (spaces between CJK phrases, dashes, parentheses)."""
    groups, cur = [], []
    for i, t in enumerate(toks):
        prev = toks[i - 1] if i else None
        brk = False
        if prev is not None:
            if prev['dash'] or prev['back'] != t['back']:
                brk = True
            elif t['sp'] and (t['cjk'] or prev['cjk']):
                brk = True
        if brk and cur:
            groups.append(cur)
            cur = []
        cur.append(i)
    if cur:
        groups.append(cur)
    # split groups that are much too wide, merge neighbours that are small
    rows = []
    for g in groups:
        wsum = sum(tok_w(toks[i]) for i in g)
        if wsum > target * 1.7 and len(g) > 3:
            n = int(round(wsum / target))
            n = max(2, n)
            per = wsum / n
            acc, row = 0.0, []
            for i in g:
                row.append(i)
                acc += tok_w(toks[i])
                if acc >= per - 0.26 and len(rows) + 1 < 99 and i != g[-1]:
                    rows.append(row)
                    row, acc = [], 0.0
            if row:
                rows.append(row)
        else:
            rows.append(g)
    merged = [rows[0]]
    for r in rows[1:]:
        a = merged[-1]
        wa = sum(tok_w(toks[i]) for i in a)
        wr = sum(tok_w(toks[i]) for i in r)
        same_voice = toks[a[-1]]['back'] == toks[r[0]]['back'] and not toks[a[-1]]['dash']
        if same_voice and wa + wr <= target * 1.15 and (len(merged) + (len(rows) - rows.index(r)) > maxrows or wa + wr <= target * 0.9):
            merged[-1] = a + r
        else:
            merged.append(r)
    return merged


class Placed:
    __slots__ = ('tok', 'i', 'row', 'x', 'y', 'size', 'sp', 'w', 'dash', 'cx', 'cy', 'x0', 'y0', 'x1', 'y1', 't', 'te', 'k')


def set_block(toks, rows, box, cjk='hei', lat='anton', max_size=420, gap=0.10, align='center', valign='center',
              fill=True, outline=None, sizes=None, track=0.0, row_align=None, dash_w=0.9, space=0.30, pgap=0.42):
    """place tokens. box = (x0, y0, x1, y1). outline: {token index: stroke fraction} for hollow tokens.
    sizes: optional {row index: size multiplier cap}. Returns (placed list, (bx0, by0, bx1, by1))."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    outline = outline or {}

    def row_width(r, size):
        wsum, parts = 0.0, []
        for n, i in enumerate(r):
            t = toks[i]
            if n and t['sp']:
                wsum += size * (pgap if (t['cjk'] or toks[r[n - 1]]['cjk']) else space)
            sp = sprite(t['text'], cjk, lat, size, outline.get(i, 0.0), track)
            parts.append((i, wsum, sp))
            wsum += sp.adv
            if t['dash'] and n < len(r) - 1:
                wsum += size * (dash_w + 0.3)
            elif t['dash']:
                wsum += size * (dash_w + 0.15)
        return wsum, parts

    rs = []
    for ri, r in enumerate(rows):
        w100, _ = row_width(r, 100)
        size = min(max_size * ((sizes or {}).get(ri, 1.0)), bw / max(w100, 1e-3) * 100) if fill else max_size * ((sizes or {}).get(ri, 1.0))
        size = min(size, bw / max(w100, 1e-3) * 100)
        rs.append(size)
    for _ in range(3):
        metrics = []
        for ri, r in enumerate(rows):
            wsum, parts = row_width(r, rs[ri])
            if wsum > bw + 1:
                rs[ri] *= bw / wsum
                wsum, parts = row_width(r, rs[ri])
            top = min(p[2].ink[1] for p in parts)
            bot = max(p[2].ink[3] for p in parts)
            # keep CJK rows on a common body so rows of the same size line up whatever glyphs they hold
            if any(toks[i]['cjk'] for i in r):
                top, bot = min(top, -0.86 * rs[ri]), max(bot, 0.06 * rs[ri])
            metrics.append((wsum, parts, top, bot))
        gaps = [gap * (rs[i] + rs[i + 1]) / 2 for i in range(len(rows) - 1)]
        total = sum(m[3] - m[2] for m in metrics) + sum(gaps)
        if total <= bh + 1:
            break
        k = bh / total
        rs = [s * k for s in rs]
    if valign == 'center':
        y = y0 + (bh - total) / 2
    elif valign == 'top':
        y = y0
    else:
        y = y1 - total
    placed = []
    bx0, bx1 = 1e9, -1e9
    by0 = y
    for ri, (wsum, parts, top, bot) in enumerate(metrics):
        al = (row_align or {}).get(ri, align)
        xs = x0 if al == 'left' else x1 - wsum if al == 'right' else x0 + (bw - wsum) / 2
        base = y - top
        for n, (i, off, sp) in enumerate(parts):
            p = Placed()
            p.tok, p.i, p.row, p.size, p.sp = toks[i], i, ri, rs[ri], sp
            p.x, p.y, p.w = xs + off, base, sp.adv
            p.dash = toks[i]['dash']
            p.x0, p.y0, p.x1, p.y1 = p.x + sp.ink[0], base + sp.ink[1], p.x + sp.ink[2], base + sp.ink[3]
            p.cx, p.cy = (p.x0 + p.x1) / 2, base + (top + bot) / 2
            p.t = p.te = None
            p.k = len(placed)
            placed.append(p)
        bx0, bx1 = min(bx0, xs), max(bx1, xs + wsum)
        y += (bot - top) + (gaps[ri] if ri < len(gaps) else 0)
    return placed, (bx0, by0, bx1, y)


def row_boxes(placed):
    """ink box of every row: {row: (x0, y0, x1, y1)} (dash included)."""
    out = {}
    for p in placed:
        x1 = p.x + p.w + (p.size * 1.05 if p.dash else 0)
        b = out.get(p.row)
        top, bot = p.y - 0.88 * p.size, p.y + 0.10 * p.size
        out[p.row] = (min(b[0], p.x), min(b[1], top), max(b[2], x1), max(b[3], bot)) if b else (p.x, top, x1, bot)
    return out


if __name__ == '__main__':
    from lyrics import parse
    secs, lines = parse(sys.argv[1])
    for l in lines:
        tk = tokens(l)
        rows = auto_rows(tk, float(sys.argv[2]) if len(sys.argv) > 2 else 5.0)
        print(l['i'], ' / '.join(' '.join(f"{i}:{tk[i]['text']}" + ('—' if tk[i]['dash'] else '') for i in r) for r in rows))
