"""Verse 1 (old school boom bap) and verse 3 (boom bap drums with trap hi-hats): a cut-and-paste news collage.

Every phrase of the sheet is a strip of paper slapped onto the page when its first syllable is sung; the characters
are inked in one by one as they are sung. Verse 1 is daylight newsprint; verse 3 is the same collage on black paper
with the trap section's glitch laid over it, because the beat itself is that mix.
"""
import math

import numpy as np

import beat as B
from base import (GREEN, INK, PAPER, RED, WHITE, YELLOW, Xf, age, draw_tok, paper, solid)
from kit import (H, W, chroma, clamp, ease_out, flash, glow, grain, halftone, lerp, quad, rnd, scanlines, slices, vignette,
                 xform)
from typo import row_boxes

BOX = (74, 250, W - 74, 1690)
# what a row is (by sheet line, row): a weekday tab, or a quotation
TAB = {(10, 0), (18, 0), (19, 3), (24, 0), (30, 0), (44, 0)}
QUOTE = {(11, 0), (11, 1), (14, 0), (16, 1), (16, 2), (21, 0), (45, 1), (47, 1)}
LIGHT = [(INK, PAPER, YELLOW), (None, INK, RED), (RED, WHITE, YELLOW), ((1, 1, 1), INK, RED), (None, INK, RED), (INK, PAPER, YELLOW)]
DARK = [(PAPER, INK, RED), (None, WHITE, GREEN), (GREEN, INK, WHITE), (None, WHITE, GREEN), (RED, WHITE, YELLOW), (PAPER, INK, RED)]


def _decor(s, dark):
    """the page under the strips: paper, one big halftone disc, tape, registration marks. Built once per shot."""
    if getattr(s, '_bg', None) is not None:
        return s._bg
    img = paper(s.k, dark)
    k = s.k
    cx = lerp(120, W - 120, rnd(k, 11))
    cy = lerp(350, H - 350, rnd(k, 12))
    r = lerp(380, 620, rnd(k, 13))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.hypot(xx - cx, yy - cy)
    tone = np.clip(1.15 - d / r, 0, 1) * 0.85
    dots = (halftone(18 if not dark else 22, 30.0 + 15 * (k % 3)) < tone).astype(np.float32)
    col = (RED if (k % 2 == 0) else INK) if not dark else (GREEN * 0.55 if k % 2 == 0 else np.array([0.32, 0.32, 0.34], np.float32))
    a = dots[..., None] * (0.55 if not dark else 0.5)
    img = img + (col - img) * a
    # tape / bars
    for q in range(2):
        ang = math.radians(lerp(-38, 38, rnd(k, 20 + q)))
        px, py = lerp(0, W, rnd(k, 30 + q)), (120 if q == 0 else H - 150) + lerp(-40, 40, rnd(k, 40 + q))
        ln, th = 900, lerp(34, 70, rnd(k, 50 + q))
        c, sn = math.cos(ang), math.sin(ang)
        pts = [(px - c * ln - sn * th, py - sn * ln + c * th), (px + c * ln - sn * th, py + sn * ln + c * th),
               (px + c * ln + sn * th, py + sn * ln - c * th), (px - c * ln + sn * th, py - sn * ln - c * th)]
        quad(img, pts, (YELLOW if q == 0 else INK) if not dark else (np.array([0.2, 0.2, 0.22], np.float32) if q else GREEN * 0.8), 0.9 if q == 0 else 0.85)
    s._bg = img
    return img


def paper_line(t, fi, s):
    dark = s.sec == 'v3'
    if s.i in (56, 57):
        return swap(t, fi, s)
    L = s.line
    img = _decor(s, dark).copy()
    nrows = len(s.rows)
    al = {r: ('left' if (r + s.k) % 2 == 0 else 'right') for r in range(nrows)}
    placed, bb = L.block(s.rows, BOX, cjk='hei', lat='anton', max_size=285, gap=0.30, align='left', row_align=al)
    rb = row_boxes(placed)
    pal = DARK if dark else LIGHT
    first = {}
    for p in placed:
        first.setdefault(p.row, p)
    boil = int(t * 10)
    for r in range(nrows):
        f = first[r]
        a = age(f, t) + 0.02
        if a < 0:
            continue
        x0, y0, x1, y1 = rb[r]
        strip, tcol, hot = pal[(r + s.k * 2) % len(pal)]
        if (s.i, r) in TAB:
            strip, tcol, hot = RED, WHITE, YELLOW
        elif (s.i, r) in QUOTE:
            strip, tcol, hot = (YELLOW, INK, RED) if not dark else (GREEN, INK, WHITE)
        rot = (rnd(s.k, r, 1) - 0.5) * 6.0 + (rnd(s.k, r, boil) - 0.5) * 0.5
        g = ease_out(a / 0.10, 3)
        sc = lerp(1.35, 1.0, g)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        xf = Xf(cx, cy, sc, rot, lerp((rnd(s.k, r, 2) - 0.5) * 240, 0, g), lerp(-60, 0, g))
        if strip is not None:
            px, py = 30, 20
            # the strip is unrolled as far as the newest sung character
            xe = x0
            for p in placed:
                if p.row == r:
                    ap = age(p, t)
                    if ap >= 0:
                        pe = p.x + p.w + (p.size * 1.0 if p.dash else 0)
                        xe = max(xe, lerp(p.x, pe, ease_out(ap / 0.08)))
            x1 = min(x1, xe)
            c4 = [(x0 - px, y0 - py), (x1 + px, y0 - py), (x1 + px, y1 + py), (x0 - px, y1 + py)]
            quad(img, [xf.pt(x + 12, y + 16) for x, y in c4], (0, 0, 0), 0.35 * clamp(a * 20))
            quad(img, [xf.pt(x, y) for x, y in c4], strip, 1.0)
        for p in placed:
            if p.row != r:
                continue
            draw_tok(img, p, t, tcol, kind='stamp', dur=0.12, xf=xf, hot=hot, dash_col=tcol)
    k, sn = B.kick(t), B.snare(t)
    jx = (rnd(boil, 1) - 0.5) * 5
    jy = (rnd(boil, 2) - 0.5) * 5
    a0 = t - s.t0
    slide = (1 - ease_out(clamp(a0 / 0.12), 3)) * 70
    img = xform(img, 1.0 + 0.022 * k + 0.02 * clamp(a0 / 3.2), (rnd(boil, 3) - 0.5) * 0.5, jx, jy + slide)
    if dark:
        img = chroma(img, 6 * B.hat(t) + 5 * sn)
        if sn > 0.75:
            img = slices(img, fi // 2, n=4, maxdx=46)
        img = scanlines(img, 0.5)
        img = glow(img, 0.45, 0.6, 9)
        img = vignette(img, 0.6)
        return grain(img, fi, 0.045)
    img = flash(img, 0.10 * sn, (1, 1, 1))
    img = vignette(img, 0.38)
    return grain(img, fi, 0.06)


def swap(t, fi, s):
    """v3's last two lines, drums out: 'truth first, then back' -- and reality turns the order around."""
    L = s.line
    img = solid(INK)
    sh = s if s.i == 56 else s.prev
    L56 = sh.line
    top, _ = L56.block([[0, 1, 2, 3, 4]], (74, 300, W - 74, 520), max_size=150, align='left')
    a_, _ = L56.block([[5, 6, 7]], (74, 600, W - 74, 950), max_size=330, align='left', outline={5: 0.03, 6: 0.03, 7: 0.03})
    b_, _ = L56.block([[8, 9, 10]], (74, 1000, W - 74, 1350), max_size=330, align='left')
    g = 0.0
    if s.i == 57:
        l57, _ = L.block([[0, 1, 2, 3, 4], [5, 6, 7, 8]], (74, 1420, W - 74, 1740), max_size=150, align='left', gap=0.2)
        # the two big rows trade places while the second half of the line is sung
        t_sw = l57[5].t
        g = ease_out(clamp((t + 0.045 - t_sw) / 0.5), 3)
    for p in top:
        draw_tok(img, p, t, WHITE * 0.75, kind='rise')
    dy = 400 * g
    for p in a_:   # truth: hollow
        st = None if s.i == 56 else (1.0, 70 * math.sin(g * math.pi), dy, 0, 1.0)
        draw_tok(img, p, t, WHITE, kind='pop', state=st)
    for p in b_:   # back: solid green
        st = None if s.i == 56 else (1.0, -70 * math.sin(g * math.pi), -dy, 0, 1.0)
        draw_tok(img, p, t, GREEN, kind='pop', state=st)
    if s.i == 57:
        for p in l57:
            draw_tok(img, p, t, WHITE, kind='rise', hot=RED)
    img = xform(img, 1.0 + 0.03 * clamp((t - sh.t0) / 6.4))
    img = glow(img, 0.5, 0.6, 10)
    img = vignette(img, 0.6)
    return grain(img, fi, 0.035)
