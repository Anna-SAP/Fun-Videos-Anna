"""Verse 2 (trap, triplet flow): the week the stock fell. A trading screen at night.

Candles scroll behind the words and fall with the lines that count the losses; when the lyric turns to the push
for a second chance the screen warms from red to amber, and the last line's dawn floods it from below.
Characters land with a three-hit stutter (the triplet flow), and the snare tears the picture sideways.
"""
import math

import numpy as np

import beat as B
from base import AMBER, GREEN, INK, RED, WHITE, YELLOW, age, draw_tok, solid
from kit import (H, W, chroma, clamp, ease_io, ease_out, flash, glow, grain, lerp, polyline, rect, rnd, scanlines, slices,
                 vignette, xform)

BOX = (70, 250, W - 70, 1090)
QUOTE = {(28, 0), (28, 1), (35, 1)}


def _walk(n, seed, drift):
    v, out = 0.0, []
    for k in range(n):
        d = (rnd(seed, k, 1) - 0.5 + drift) * 2
        o = v
        v += d
        out.append((o, v, max(o, v) + rnd(seed, k, 2) * 0.8, min(o, v) - rnd(seed, k, 3) * 0.8))
    return out


_SER = {}


def _candles(img, t, mood, acc, k):
    """mood 0 = falling (red), 1 = turning (amber), 2 = rising (green). Candles scroll right to left; the newest
    candle is at the right edge and the whole chart jumps a little on every kick."""
    drift = (-0.30, 0.03, 0.34)[mood]
    if mood not in _SER:
        _SER[mood] = _walk(600, 17 + mood, drift)
    ser = _SER[mood]
    cw = 72.0
    x_scroll = t * 58.0
    k0 = int(x_scroll // cw)
    n = int(W // cw) + 3
    lo_v = min(ser[(k0 + q) % 600][3] for q in range(n))
    hi_v = max(ser[(k0 + q) % 600][2] for q in range(n))
    y_top, y_bot = 1130.0, 1800.0
    sc = (y_bot - y_top) / max(hi_v - lo_v, 1e-3)
    gcol = acc * 0.20
    for gy in range(0, H, 120):
        rect(img, 0, gy, W, gy + 2, gcol, 1.0)
    off = x_scroll % 120
    for gx in range(0, W + 120, 120):
        rect(img, gx - off, 0, gx - off + 2, H, gcol, 1.0)
    down = RED * 0.95
    up = GREEN * 0.9 if mood == 2 else (AMBER if mood == 1 else GREEN * 0.45)
    pts = []
    for q in range(n):
        kk = (k0 + q) % 600
        o, c, hi, lo = ser[kk]
        x = q * cw - (x_scroll % cw)
        yo, yc = y_bot - (o - lo_v) * sc, y_bot - (c - lo_v) * sc
        yh, yl = y_bot - (hi - lo_v) * sc, y_bot - (lo - lo_v) * sc
        col = up if c >= o else down
        rect(img, x + cw * 0.45, yh, x + cw * 0.55, yl, col, 0.9)
        rect(img, x + cw * 0.14, min(yo, yc), x + cw * 0.86, max(yo, yc) + 4, col, 1.0)
        pts.append((x + cw * 0.5, yc - 6 * k))
    polyline(img, pts, acc * 0.35, 30)
    polyline(img, pts, WHITE, 6)


def crash(t, fi, s):
    L = s.line
    n = s.n                       # 0..11 inside the verse
    mood = 0 if n < 4 else (1 if n < 10 else 2)
    acc = (RED, AMBER, GREEN)[mood]
    img = solid(INK)
    _candles(img, t, mood, acc, B.kick(t))
    img *= 0.8
    last = s.i == 35
    if last:
        # "Monday morning, daybreak": light comes up from the bottom during the last phrase
        placed0, _ = L.block(s.rows, BOX, cjk='hei', lat='barlow', max_size=300, gap=0.14, align='left', valign='top')
        td = placed0[-2].t
        g = ease_io(clamp((t - td + 0.3) / 1.6))
        if g > 0:
            yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
            dawn = np.clip((yy - (1.0 - 1.25 * g)) / 0.55, 0, 1)
            col = np.array([1.0, 0.72, 0.30], np.float32) * (1 - dawn * 0.4) + np.array([1, 1, 1], np.float32) * dawn * 0.4
            img = img + (col - img) * dawn * (0.9 * g)
    placed, bb = L.block(s.rows, BOX, cjk='hei', lat='barlow', max_size=300, gap=0.14, align='left', valign='top')
    nrows = len(s.rows)
    for p in placed:
        col, hot = WHITE, acc
        if (s.i, p.row) in QUOTE:
            col, hot = YELLOW, WHITE
        a = age(p, t)
        if a >= 0:
            # a tick mark to the left of every row, the way a tape prints
            if p is next(q for q in placed if q.row == p.row):
                g = ease_out(clamp(a / 0.12))
                rect(img, 0, p.y - 0.80 * p.size, 44 * g, p.y + 0.04 * p.size, acc, 1.0)
        draw_tok(img, p, t, col, kind='trip', hot=hot, fonts=('hei', 'barlow'), ex=(6, 2, 2, acc * 0.45))
    k, sn, ht = B.kick(t), B.snare(t), B.hat(t)
    a0 = t - s.t0
    rot = 0.0
    if s.i == 34:
        # "the nail on the door starts to wobble"
        tw = placed[-3].t
        if t > tw:
            rot = 2.2 * math.sin((t - tw) * 13.0) * min(1.0, (t - tw) / 0.4)
    img = xform(img, 1.0 + 0.03 * k + 0.025 * clamp(a0 / 3.2), rot, (rnd(fi, 1) - 0.5) * 14 * k, (rnd(fi, 2) - 0.5) * 14 * k)
    img = chroma(img, 3 + 9 * sn + 4 * ht)
    if sn > 0.6:
        img = slices(img, fi // 2 + s.k * 7, n=4, maxdx=44, hmax=70)
    img = scanlines(img, 0.7)
    img = glow(img, 0.6, 0.55, 10)
    img = flash(img, 0.5 * math.exp(-a0 / 0.05), acc)
    img = vignette(img, 0.75)
    return grain(img, fi, 0.045)
