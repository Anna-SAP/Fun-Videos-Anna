"""The hook (gang chant, EDM stabs) and the final hook (double drop, full crowd).

Rule of the whole film: what has come back is set SOLID; what has not come back yet is set HOLLOW.
Call = white on black, set to fill the frame. Response (the sheet's parentheses) = the crowd answering back:
a green sticker slammed on top of the call from the other side.
"""
import math

import numpy as np

import beat as B
from base import (GREEN, DGREEN, INK, PAPER, RED, WHITE, YELLOW, MAGENTA, Xf, age, cam, draw_block, draw_tok, entry, heat,
                  rays, solid)
from hand_times import ECHO
from kit import (H, W, back_out, chroma, clamp, draw, ease_io, ease_out, flash, glow, grain, lerp, polyline, quad, rect,
                 rnd, rrect, sprite, vignette, xform)

M = 64   # side margin


def _post(img, t, fi, s, big, shake=10.0):
    k = B.kick(t)
    sn = B.snare(t)
    img = cam(img, t, s.t0, push=0.03, dur=max(1.0, s.t1 - s.t0), k_zoom=0.035 if big else 0.02, k_shake=shake * (1.6 if big else 1.0), seed=s.k)
    img = chroma(img, 5 * sn + (4 * k if big else 0))
    img = glow(img, 0.55 if big else 0.4, 0.6, 10)
    img = vignette(img, 0.55)
    return grain(img, fi, 0.035)


def _bg(t, s, big, c1=None, n=12):
    k = B.kick(t)
    if big:
        c1 = (GREEN * (0.20 + 0.12 * k)) if c1 is None else c1
        return rays(t, INK, c1, n=n, rot=t * 0.11, soft=0.03, cy=H * 0.5)
    c1 = (DGREEN * (0.34 + 0.25 * k)) if c1 is None else c1
    return rays(t, INK, c1, n=n, rot=t * 0.05, soft=0.03, cy=H * 0.5)


def _sticker(img, p, t, big, cx, cy, rot, col=GREEN, tcol=INK, fonts=('hei', 'anton'), pad=(46, 26), crowd=True):
    """the response: a coloured block slammed onto the frame, the crowd behind it as hollow echoes."""
    a = age(p, t)
    if a < 0:
        return 0.0
    sc = lerp(2.6, 1.0, ease_out(a / 0.11, 4))
    w = (p.sp.ink[2] - p.sp.ink[0]) + 2 * pad[0]
    h = (p.sp.ink[3] - p.sp.ink[1]) + 2 * pad[1]
    wob = rot + 1.6 * math.sin(t * 9.0) * math.exp(-a / 0.5)
    if crowd:
        osp = sprite(p.tok['text'], fonts[0], fonts[1], int(round(p.size)), 0.030)
        nn = 5 if big else 2
        for k in range(nn, 0, -1):
            ak = a - 0.05 * k
            if ak < 0:
                continue
            g = ease_out(ak / 0.22)
            off = (62 if big else 54) * k * g
            ox, oy = cx + off * math.sin(math.radians(wob)) * 0 - off * 0.35, cy + off
            draw(img, osp, ox - (p.sp.ink[0] + p.sp.ink[2]) / 2, oy - (p.sp.ink[1] + p.sp.ink[3]) / 2, col,
                 alpha=(0.95 - 0.16 * k) * clamp(ak * 12), rot=wob, cx=ox, cy=oy)
    # shadow, block, text
    rrect(img, cx + 14, cy + 18, w * sc, h * sc, wob, (0, 0, 0), 0.55)
    rrect(img, cx, cy, w * sc, h * sc, wob, col, 1.0)
    px = cx - (p.sp.ink[0] + p.sp.ink[2]) / 2
    py = cy - (p.sp.ink[1] + p.sp.ink[3]) / 2
    draw(img, p.sp, px, py, tcol, 1.0, scale=sc, rot=wob, cx=cx, cy=cy)
    return math.exp(-a / 0.07)


def _chant(t, fi, s, big, var):
    L = s.line
    k = B.kick(t)
    img = _bg(t, s, big)
    nt = len(L.toks)
    call, _ = L.block([[0], [1]], (M, 230, W - M, 900), lat='anton', max_size=520, gap=0.07, align='left')
    resp, _ = L.block([[2]], (M, 0, W - M, 400), lat='anton', max_size=190)
    half = 3 + (nt - 3 + 1) // 2 if var != 0 else 6
    if var == 2:
        half = 8
    if var == 1:
        half = 7
    zh, zbb = L.block([list(range(3, half)), list(range(half, nt))], (M, 1150, W - M, 1720), max_size=300, gap=0.12, align='left')
    fl = 0.0
    # ---- line-specific graphics behind the lower rows
    if var == 2:
        # "one line, straight up": the chart line is drawn as the phrase is sung, then leaves through the top
        p0, p1 = zh[0], zh[-1]
        a0 = age(p0, t)
        if a0 > 0:
            g = clamp(a0 / max(0.3, (zh[5].t - p0.t)))          # walk during the first row
            up = clamp(age(zh[5], t) / 0.45)
            pts = []
            n = 26
            for q in range(n + 1):
                x = lerp(-20, W * 0.80, q / n)
                y = 1720 - 190 * (q / n) + 46 * math.sin(q * 2.1 + s.k) * (0.4 + 0.6 * rnd(q, 5))
                pts.append((x, y))
            m = max(2, int(g * n) + 1)
            pts = pts[:m]
            if up > 0:
                x_end, y_end = pts[-1]
                pts.append((x_end + 70, lerp(y_end, -80, ease_out(up, 3))))
            polyline(img, pts, GREEN * 0.35, 46)
            polyline(img, pts, GREEN, 18)
    xf = Xf()
    draw_block(img, call, t, WHITE, kind='pop', dur=0.16, ex=(10, 2.0, 2.4, GREEN * 0.55) if big else (7, 2.0, 2.4, DGREEN))
    # ---- lower rows
    for p in zh:
        a = age(p, t)
        if a < 0:
            continue
        col, hot, st, kind = WHITE, GREEN, None, 'pop'
        if var == 0 and p.row == 1:
            # "there and back": the row goes out to the right and returns
            al = age(zh[-1], t)
            if al > 0.05:
                d = math.sin(min(al - 0.05, 0.56) / 0.56 * math.pi) * 110
                st = (1.0, d, 0, 0, 1.0)
        if var == 1 and p.row == 0:
            # "unanimous": every character is a ballot, all of them the same colour
            g = ease_out(a / 0.10, 3)
            sz = p.size * 0.98
            cxm, cym = p.x + p.w / 2, p.y - 0.39 * p.size
            rrect(img, cxm, cym, sz * lerp(1.5, 1.0, g), sz * lerp(1.5, 1.0, g), 0, GREEN, 1.0)
            col, hot = INK, WHITE
        if var == 1 and p.row == 1:
            # "back in place at once": characters fly home from wherever they were
            g = ease_out(a / 0.17, 4)
            ox = (rnd(p.k, 3) - 0.5) * 900 * (1 - g)
            oy = (rnd(p.k, 4) - 0.2) * 700 * (1 - g)
            st = (lerp(2.2, 1.0, g), ox, oy, (rnd(p.k, 5) - 0.5) * 120 * (1 - g), 1.0)
        if var == 2 and p.row == 1:
            al = age(zh[-1], t)
            kind = 'rise'
            if al > 0.25:
                st = (1.0, 0, -ease_io(clamp((al - 0.25) / 0.9)) * 70, 0, 1.0)
        draw_tok(img, p, t, col, kind=kind, hot=hot, state=st)
    # ---- the response on top
    rp = resp[0]
    fl = _sticker(img, rp, t, big, W * 0.63, 985, -7.0)
    img = flash(img, 0.75 * fl, GREEN)
    return _post(img, t, fi, s, big)


def _facts(t, fi, s, big):
    """'the facts ain't back': the frame flips to paper; the unfinished report is a mostly empty page."""
    L = s.line
    img = solid(PAPER)
    k = B.kick(t)
    top, _ = L.block([[0, 1, 2], [3, 4]], (M, 250, W - M, 800), lat='anton', max_size=420, gap=0.09, align='left',
                     outline={3: 0.042, 4: 0.042})
    draw_block(img, top, t, INK, kind='pop', sel=lambda p: p.row == 0, ex=(8, 2, 2.4, RED) if big else None)
    draw_block(img, top, t, INK, kind='pop', sel=lambda p: p.row == 1, dash_col=INK)
    # the page
    page = (110, 930, W - 70, 1740)
    a0 = t - s.t0
    g = ease_out(clamp(a0 / 0.18), 3)
    xf = Xf(W / 2, 1300, 1.0, lerp(7, 1.6, g), 0, lerp(900, 0, g))
    pts = [xf.pt(page[0] + 16, page[1] + 22), xf.pt(page[2] + 16, page[1] + 22), xf.pt(page[2] + 16, page[3] + 22), xf.pt(page[0] + 16, page[3] + 22)]
    quad(img, pts, (0, 0, 0), 0.22)
    pts = [xf.pt(page[0], page[1]), xf.pt(page[2], page[1]), xf.pt(page[2], page[3]), xf.pt(page[0], page[3])]
    quad(img, pts, (1, 1, 1), 1.0)
    zh, bb = L.block([[5, 6, 7, 8], [9, 10, 11, 12]], (page[0] + 60, page[1] + 60, page[2] - 80, page[1] + 470), cjk='song', max_size=190, gap=0.22, align='left', valign='top')
    draw_block(img, zh, t, INK, kind='cut', xf=xf, fonts=('song', 'anton'))
    # cursor after the last typed character
    typed = [p for p in zh if age(p, t) >= 0]
    cx = (typed[-1].x + typed[-1].w + 10) if typed else zh[0].x
    base = typed[-1].y if typed else zh[0].y
    sz = zh[0].size
    if int(t * 3.75) % 2 == 0 or (typed and age(typed[-1], t) < 0.25):
        pts = [xf.pt(cx, base - 0.86 * sz), xf.pt(cx + 0.14 * sz, base - 0.86 * sz), xf.pt(cx + 0.14 * sz, base + 0.10 * sz), xf.pt(cx, base + 0.10 * sz)]
        quad(img, pts, RED, 1.0)
    # the lines nobody has written yet
    y = zh[-1].y + 0.62 * sz
    for q in range(7):
        yy = y + q * 0.86 * sz
        if yy > page[3] - 40:
            break
        pts = [xf.pt(page[0] + 60, yy), xf.pt(page[2] - 60, yy), xf.pt(page[2] - 60, yy + 4), xf.pt(page[0] + 60, yy + 4)]
        quad(img, pts, (0.80, 0.79, 0.76), 1.0)
    img = cam(img, t, s.t0, push=0.03, dur=s.t1 - s.t0, k_zoom=0.016, k_shake=6.0, seed=s.k)
    img = flash(img, 0.9 * math.exp(-(t - s.t0) / 0.06), (1, 1, 1))
    img = vignette(img, 0.35)
    return grain(img, fi, 0.045)


def _split(t, fi, s, big):
    """top half: the man is back (solid, on green). bottom half: the answer is not (hollow, on black)."""
    L = s.line
    k = B.kick(t)
    img = _bg(t, s, big, c1=(DGREEN * 0.30))
    a0 = t - s.t0
    yb = 960 * ease_out(clamp(a0 / 0.12), 3)
    if big:
        img[:int(yb)] = rays(t, GREEN, GREEN * 0.80, n=12, rot=-t * 0.11, soft=0.03, cy=480)[:int(yb)]
    else:
        rect(img, 0, 0, W, yb, GREEN * (0.92 + 0.08 * k))
    top, _ = L.block([[0, 1, 2, 3]], (M, 250, W - M, 560), max_size=300)
    r1, _ = L.block([[4, 5, 6]], (M, 610, W - M, 860), max_size=200, align='right')
    bot, _ = L.block([[7, 8, 9, 10, 11]], (M, 1090, W - M, 1400), max_size=300, outline={q: 0.040 for q in range(7, 12)})
    r2, _ = L.block([[12, 13, 14]], (M, 1450, W - M, 1700), max_size=200, align='right', outline={q: 0.044 for q in range(12, 15)})
    draw_block(img, top, t, INK, kind='pop', hot=WHITE)
    # the answer back, with its echo: solid
    for p in r1:
        a = age(p, t)
        if a < 0:
            continue
        for q in (3, 2, 1):
            if a > 0.05 * q:
                draw(img, p.sp, p.x - 16 * q, p.y + 16 * q, INK, alpha=0.30 - 0.07 * q)
        draw_tok(img, p, t, INK, kind='slam')
    draw_block(img, bot, t, WHITE, kind='pop', hot=GREEN)
    for p in r2:
        a = age(p, t)
        if a < 0:
            continue
        for q in (3, 2, 1):
            if a > 0.05 * q:
                draw(img, p.sp, p.x - 16 * q, p.y + 16 * q, GREEN, alpha=0.5 - 0.12 * q)
        draw_tok(img, p, t, GREEN, kind='slam')
    return _post(img, t, fi, s, big, shake=8.0)


def _truth(t, fi, s, big):
    """'we brought him back' solid; 'now bring the truth back' hollow, still waiting to be filled.
    The track sings the line twice; the second time the frame is turned inside out, and the last hollow word is
    struck again on every stutter of 'back' that follows (times measured from the vocal stem)."""
    L = s.line
    k = B.kick(t)
    second = s.prev is not None and s.prev.i == s.i
    if second:
        img = rays(t, GREEN, GREEN * 0.80, n=12, rot=-t * 0.08, soft=0.03)
        solid_c, hollow_c, exc, hot = INK, INK, WHITE, WHITE
    else:
        img = _bg(t, s, big)
        solid_c, hollow_c, exc, hot = WHITE, GREEN, (GREEN * 0.55 if big else DGREEN), WHITE
    top, _ = L.block([[0, 1], [2, 3]], (M, 240, W - M, 880), lat='anton', max_size=430, gap=0.08, align='left')
    out = {q: 0.040 for q in range(4, 9)}
    bot, _ = L.block([[4, 5, 6], [7, 8]], (M, 1010, W - M, 1700), lat='anton', max_size=430, gap=0.08, align='left', outline=out)
    draw_block(img, top, t, solid_c, kind='pop', ex=(10 if big else 7, 2.0, 2.4, exc), dash_col=hollow_c)
    last = bot[-1]
    al = age(last, t)
    hits = [e for e in ECHO['back2' if big else 'back1'] if t + 0.045 >= e] if second else []
    ah = (t + 0.045 - hits[-1]) if hits else None
    for p in bot:
        st = None
        if p is last and ah is not None:
            st = (lerp(1.30, 1.0, ease_out(ah / 0.12, 3)), 0, 0, 0, 1.0)
        elif al > 0.3:
            st = (1.0 + 0.04 * k, 0, 0, 0, 1.0)
        draw_tok(img, p, t, hollow_c, kind='pop', state=st, hot=hot)
    for e in hits[-4:]:
        ae = t + 0.045 - e
        if ae < 0.6:
            g = ae / 0.6
            draw(img, last.sp, last.x, last.y, hollow_c, alpha=0.7 * (1 - g) ** 1.4, scale=1.0 + 1.3 * g)
    img = _post(img, t, fi, s, big)
    if ah is not None:
        img = flash(img, 0.35 * math.exp(-ah / 0.05), (1, 1, 1))
    return img


def hook(t, fi, s):
    big = s.sec == 'hook2'
    i = s.i if s.i < 10 else s.i - 60
    if i in (4, 5, 6):
        return _chant(t, fi, s, big, i - 4)
    if i == 7:
        return _facts(t, fi, s, big)
    if i == 8:
        return _split(t, fi, s, big)
    return _truth(t, fi, s, big)
