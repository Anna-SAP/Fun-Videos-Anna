"""Pre-chorus (drums drop out, riser) and Bridge (half-time, piano only): the two quiet rooms of the film.

Pre-chorus: thin type on black, each phrase closed with a hairline as it is sung ("nailed, signed, nearly over"),
the letters drifting apart with the riser; then red rises from the floor under "Then came Friday".
Bridge: one warm light, serif type that fades in syllable by syllable. The line sung with nothing under it at all
(the instrumental stops for a bar) is set on plain black: solid "welcome back", hollow "earn it back".
"""
import math

import numpy as np

import beat as B
from base import AMBER, GREEN, INK, RED, WHITE, age, draw_tok, solid
from kit import RAD, H, W, clamp, ease_in, ease_io, ease_out, glow, grain, lerp, rect, vignette, xform, _XX, _YY
from typo import row_boxes

CREAM = np.array([0.98, 0.93, 0.82], np.float32)
_LIGHT = None


def _light():
    global _LIGHT
    if _LIGHT is None:
        d = np.hypot((_XX - W * 0.5) / 760.0, (_YY - H * 0.40) / 980.0)
        _LIGHT = np.clip(1 - d, 0, 1)[..., None] ** 1.8
    return _LIGHT


def pre(t, fi, s):
    L = s.line
    a0 = t - s.t0
    img = solid(INK)
    if s.i == 22:
        placed, _ = L.block(s.rows, (150, 520, W - 150, 1400), cjk='heir', lat='play', max_size=150, gap=0.75)
        rb = row_boxes(placed)
        g = clamp(a0 / 4.2)
        for p in placed:
            st = None
            a = age(p, t)
            if a >= 0:
                al = ease_io(a / 0.25)
                st = (1.0, (p.cx - W / 2) * 0.16 * g, lerp(18, 0, ease_out(a / 0.3)), 0, al)
            draw_tok(img, p, t, WHITE, state=st, hot=RED)
        for r, (x0, y0, x1, y1) in rb.items():
            lastp = [p for p in placed if p.row == r][-1]
            a = age(lastp, t) - 0.12
            if a > 0:
                gg = ease_out(a / 0.35, 3)
                cx = W / 2
                hw = (x1 - x0) / 2 * (1 + 0.16 * g) + 30
                rect(img, cx - hw, y1 + 34, cx - hw + 2 * hw * gg, y1 + 38, WHITE, 0.9)
        img = xform(img, 1.0 + 0.06 * g)
    else:
        placed, _ = L.block(s.rows, (90, 430, W - 90, 1500), cjk='song', lat='playb', max_size=400, gap=0.16, align='left')
        g = clamp(a0 / max(0.5, s.t1 - s.t0))
        # red comes up from the floor
        hgt = H * ease_in(g, 2) * 1.02
        rect(img, 0, H - hgt, W, H, RED, 1.0)
        rect(img, 0, H - hgt - 10, W, H - hgt, WHITE, 0.9 if hgt > 4 else 0)
        for p in placed:
            draw_tok(img, p, t, WHITE, kind='rise', dur=0.2, fonts=('song', 'playb'))
        img = xform(img, 1.0 + 0.12 * ease_in(g, 2), 0, (np.sin(t * 70) * 6 * g), 0)
    img = glow(img, 0.5, 0.6, 12)
    img = vignette(img, 0.6)
    return grain(img, fi, 0.04)


RED_TOK = {60: (9, 10), 61: (0, 7), 62: (0,)}


def bridge(t, fi, s):
    L = s.line
    a0 = t - s.t0
    if s.i == 63:
        img = solid(np.array([0.02, 0.02, 0.025], np.float32))
        top, _ = L.block([[0], [1]], (110, 380, W - 110, 900), lat='playb', max_size=330, gap=0.10, align='left')
        bot, _ = L.block([[2, 3], [4, 5]], (110, 1000, W - 110, 1560), lat='playb', max_size=330, gap=0.10, align='left',
                         outline={q: 0.040 for q in (2, 3, 4, 5)})
        for p in top:
            draw_tok(img, p, t, WHITE, kind='fade', dur=0.18, fonts=('song', 'playb'))
        for p in bot:
            draw_tok(img, p, t, WHITE, kind='fade', dur=0.18, fonts=('song', 'playb'))
        img = xform(img, 1.0 + 0.05 * clamp(a0 / 3.4))
        img = glow(img, 0.5, 0.55, 12)
        return grain(img, fi, 0.03)
    lv = B.loud(t, 0.4)
    warm = np.array([0.30, 0.17, 0.07], np.float32) * (0.75 + 0.5 * lv)
    img = solid(np.array([0.035, 0.03, 0.035], np.float32)) + _light() * warm
    placed, _ = L.block(s.rows, (84, 400, W - 84, 1520), cjk='songm', lat='playb', max_size=215, gap=0.42)
    reds = RED_TOK.get(s.i, ())
    rb = row_boxes(placed)
    if s.i in (61, 62):
        # an IOU: every debt gets its line to sign on
        for r, (x0, y0, x1, y1) in rb.items():
            f = [p for p in placed if p.row == r][0]
            a = age(f, t)
            if a > 0:
                gg = ease_out(a / 1.2, 2)
                rect(img, x0, y1 + 30, x0 + (x1 - x0) * gg, y1 + 33, CREAM * 0.7, 0.9)
    for p in placed:
        col = RED if p.i in reds else CREAM
        draw_tok(img, p, t, col, kind='fade', dur=0.38, hot=WHITE if p.i not in reds else None, fonts=('songm', 'playb'))
    img = xform(img, 1.0 + 0.05 * clamp(a0 / 3.4), 0, 0, -10 * clamp(a0 / 3.4))
    img = glow(img, 0.7, 0.5, 14)
    img = vignette(img, 0.7)
    return grain(img, fi, 0.045)
