"""Poster typesetting for one lyric line: rows of big type that fill the width of the door.

A row is a list of timing units. Every row is scaled so that it is exactly as wide as the box (up to a cap),
so a two-character phrase comes out huge and an eleven-character one small: the size contrast is the design.
Rows break only at the spaces of the lyric sheet unless a phrase is too long.

Each unit is drawn as one mask: opening marks + the character/word + closing marks, CJK in the CJK face,
Latin in the Latin face (marks fall back to the CJK face when the Latin face lacks them). Full-width marks
are set tight instead of on a full em.
"""
import functools

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw

import door as D

TIGHT = set('！？。，：、；“”‘’（）…')


@functools.lru_cache(maxsize=None)
def cmap(path):
    return set(TTFont(path).getBestCmap().keys())


@functools.lru_cache(maxsize=None)
def ink_metrics(path, sample):
    """ink top / bottom relative to the baseline, in em, for a sample string."""
    f = D.font(path, 400)
    x0, y0, x1, y1 = f.getbbox(sample, anchor='ls')
    return y0 / 400.0, y1 / 400.0


class Style:
    def __init__(self, zh=D.F_SANS, en=D.F_ANTON, en_scale=None, cap=300, floor=64, gap=0.11, maxem=9.2,
                 track=0.0, en_drop=0.0, resp_scale=0.46, word_gap=0.26, phrase_gap=0.30, justify=True):
        self.zh, self.en = zh, en
        zt, zb = ink_metrics(zh, '国门灯')
        et, eb = ink_metrics(en, 'HBJ')
        # Latin caps as tall as the CJK ink box (a touch less), sitting on the bottom of the CJK ink
        self.en_scale = en_scale if en_scale else 0.94 * (zb - zt) / (eb - et)
        self.en_shift = zb * 0.80 + en_drop          # move the Latin baseline down to the CJK ink bottom
        self.cap, self.floor, self.gap, self.maxem = cap, floor, gap, maxem
        self.track, self.resp_scale, self.word_gap, self.phrase_gap = track, resp_scale, word_gap, phrase_gap
        self.justify = justify
        self.key = (zh, en, round(self.en_scale, 4), cap, floor, gap, maxem, track, en_drop, resp_scale, word_gap,
                    phrase_gap, justify)


def runs_of(u, st):
    """[(text, font path, size factor, baseline shift em, tight)] for one display unit."""
    out = []
    for part, s in ((u['pre'], u['pre']), ('tok', u['tok']), (u['post'], u['post'])):
        if not s:
            continue
        if part == 'tok':
            if u['cjk']:
                out.append((s, st.zh, 1.0, 0.0, False))
            else:
                out.append((s, st.en, st.en_scale, st.en_shift, False))
            continue
        for ch in s:
            if ch == ' ':
                out.append((' ', None, 0.22, 0.0, False))
            elif (not u['cjk']) and ord(ch) in cmap(st.en) and ch not in '—':
                out.append((ch, st.en, st.en_scale, st.en_shift, False))
            else:
                # a full-width mark right before a closing ASCII bracket is set on its ink, not on its em
                nxt = s[s.index(ch) + 1:s.index(ch) + 2]
                out.append((ch, st.zh, 1.0, 0.0, 'ink' if (ch in '！？。' and nxt == ')') else False))
    return out


@functools.lru_cache(maxsize=8192)
def _unit_metrics(runs, size):
    """advance (px) and ink box (x0,y0,x1,y1 rel. to pen origin on the baseline) of a run list at a size."""
    pen = 0.0
    X0, Y0, X1, Y1 = 1e9, 1e9, -1e9, -1e9
    places = []
    for text, path, k, shift, tight in runs:
        if path is None:
            pen += size * k
            continue
        f = D.font(path, max(6, size * k))
        x0, y0, x1, y1 = f.getbbox(text, anchor='ls')
        dy = shift * size
        if tight:
            # PIL's getbbox is as wide as the advance; measure the ink itself
            m = np.asarray(f.getmask(text, mode='L'))
            m = m.reshape(f.getmask(text, mode='L').size[::-1])
            cols = np.where(m.max(axis=0) > 40)[0]
            i0, i1 = (int(cols[0]), int(cols[-1]) + 1) if len(cols) else (0, x1 - x0)
            pad = 0.07 * size
            ox = pen + pad - (x0 + i0)
            adv = (i1 - i0) + 2 * pad
            x0, x1 = x0 + i0, x0 + i1
        elif text == '—':
            ox = pen
            adv = f.getlength(text) * 0.86
        else:
            ox = pen
            adv = f.getlength(text)
        places.append((text, path, max(6, size * k), ox, dy))
        X0, Y0, X1, Y1 = min(X0, ox + x0), min(Y0, y0 + dy), max(X1, ox + x1), max(Y1, y1 + dy)
        pen += adv
    return pen, (X0, Y0, X1, Y1), tuple(places)


@functools.lru_cache(maxsize=8192)
def unit_mask(runs, size):
    adv, (X0, Y0, X1, Y1), places = _unit_metrics(runs, size)
    pad = 3
    w, h = int(np.ceil(X1 - X0)) + 2 * pad, int(np.ceil(Y1 - Y0)) + 2 * pad
    im = Image.new('L', (max(1, w), max(1, h)), 0)
    d = ImageDraw.Draw(im)
    for text, path, sz, ox, dy in places:
        d.text((ox - X0 + pad, dy - Y0 + pad), text, font=D.font(path, sz), fill=255, anchor='ls')
    return np.asarray(im), X0 - pad, Y0 - pad, adv


class Placed:
    __slots__ = ('mask', 'x', 'y', 'ui', 'row', 'size', 'resp', 'cx', 'cy')

    def __init__(self, mask, x, y, ui, row, size, resp):
        self.mask, self.x, self.y, self.ui, self.row, self.size, self.resp = mask, x, y, ui, row, size, resp
        self.cx, self.cy = x + mask.shape[1] / 2, y + mask.shape[0] / 2


def _gap_before(du, k, st, first):
    if first:
        return 0.0
    u, p = du[k], du[k - 1]
    if u['brk']:
        if (not u['cjk']) and (not p['cjk']):
            return st.word_gap
        return st.phrase_gap if (u['cjk'] and p['cjk']) else st.word_gap
    if u['cjk'] != p['cjk']:
        return 0.10
    return st.track


def row_em(du, idxs, st):
    """width of a row in em (at size 1.0 == 100px reference)."""
    w = 0.0
    for n, k in enumerate(idxs):
        w += _gap_before(du, k, st, n == 0) * 100
        w += _unit_metrics(tuple(runs_of(du[k], st)), 100)[0] * (st.resp_scale if du[k]['resp'] and not all(
            du[j]['resp'] for j in idxs) else 1.0)
    return w / 100.0


def auto_rows(du, st, box_w, box_h, max_rows=5):
    """break the line into rows at phrase boundaries; merge the narrowest neighbours until it fits the box."""
    phrases = {}
    for k, u in enumerate(du):
        phrases.setdefault(u['phrase'], []).append(k)
    rows = []
    for ph in phrases.values():
        # a phrase wider than maxem is cut at word/character boundaries into near-equal pieces
        em = row_em(du, ph, st)
        if em > st.maxem and len(ph) > 3:
            n = int(np.ceil(em / st.maxem))
            cuts = [0]
            target = em / n
            acc = 0.0
            for j, k in enumerate(ph):
                acc += row_em(du, [k], st) + (st.word_gap if not du[k]['cjk'] else 0)
                if acc >= target * len(cuts) and len(cuts) < n and j + 1 < len(ph):
                    cuts.append(j + 1)
            cuts.append(len(ph))
            rows += [ph[a:b] for a, b in zip(cuts[:-1], cuts[1:])]
        else:
            rows.append(ph)

    def height(rs):
        return sum(min(st.cap, box_w / max(row_em(du, r, st), 0.1)) * (1.0 + st.gap) for r in rs)

    while len(rows) > 1 and (height(rows) > box_h or len(rows) > max_rows):
        best = None
        for j in range(len(rows) - 1):
            if du[rows[j][-1]]['resp'] != du[rows[j + 1][0]]['resp'] and len(rows) <= max_rows:
                continue
            em = row_em(du, rows[j] + rows[j + 1], st)
            if em <= st.maxem * 1.25 and (best is None or em < best[0]):
                best = (em, j)
        if best is None:
            break
        j = best[1]
        rows[j:j + 2] = [rows[j] + rows[j + 1]]
    return rows


def layout(du, box, st, rows=None, align='left', valign='center', row_opts=None, max_rows=5):
    """-> [Placed], (x0,y0,x1,y1) ink box.  row_opts: {row index: {'cap':px, 'align':..., 'scale':k, 'dx':px}}"""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    rows = rows if rows is not None else auto_rows(du, st, bw, bh, max_rows)
    row_opts = row_opts or {}
    zt, zb = ink_metrics(st.zh, '国门灯')
    sizes = []
    for r, idxs in enumerate(rows):
        o = row_opts.get(r, {})
        allresp = all(du[k]['resp'] for k in idxs)
        cap = o.get('cap', st.cap * (st.resp_scale * 1.25 if allresp else 1.0))
        s = min(cap, bw / max(row_em(du, idxs, st), 0.1)) * o.get('scale', 1.0)
        sizes.append(max(st.floor * (0.6 if allresp else 1.0), s))
    tot = sum(s * (zb - zt) for s in sizes) + sum(st.gap * max(sizes[i], sizes[i + 1]) * 0.5 + 10
                                                  for i in range(len(sizes) - 1))
    if tot > bh:
        k = bh / tot
        sizes = [s * k for s in sizes]
        tot = bh
    y = y0 + {'top': 0, 'center': (bh - tot) / 2, 'bottom': bh - tot}[valign]
    out = []
    for r, idxs in enumerate(rows):
        o = row_opts.get(r, {})
        size = int(round(sizes[r]))
        base = y - zt * size
        allresp = all(du[k]['resp'] for k in idxs)
        # measure the row at this size
        items = []
        pen = 0.0
        for n, k in enumerate(idxs):
            sz = size * (st.resp_scale if du[k]['resp'] and not allresp else 1.0)
            pen += _gap_before(du, k, st, n == 0) * size
            m, ox, oy, adv = unit_mask(tuple(runs_of(du[k], st)), int(round(sz)))
            lift = -(size - sz) * 0.42 if sz != size else 0.0          # small responses ride high
            items.append((k, m, pen + ox, oy + lift, sz))
            pen += adv
        left = min(i[2] for i in items)
        right = max(i[2] + i[1].shape[1] for i in items)
        w = right - left
        a = o.get('align', align)
        xs = x0 + {'left': 0, 'center': (bw - w) / 2, 'right': bw - w}[a] - left + o.get('dx', 0)
        for k, m, px, oy, sz in items:
            out.append(Placed(m, int(round(xs + px)), int(round(base + oy)), k, r, sz, du[k]['resp']))
        y += size * (zb - zt)
        if r + 1 < len(rows):
            y += st.gap * max(sizes[r], sizes[r + 1]) * 0.5 + 10
    bx0 = min(p.x for p in out)
    by0 = min(p.y for p in out)
    bx1 = max(p.x + p.mask.shape[1] for p in out)
    by1 = max(p.y + p.mask.shape[0] for p in out)
    return out, (bx0, by0, bx1, by1)
