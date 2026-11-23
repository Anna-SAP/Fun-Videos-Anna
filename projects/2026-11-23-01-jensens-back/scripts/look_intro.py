"""Intro and Outro (vinyl crackle, news sample, DJ scratch / vinyl crackle, piano, DJ scratch).

A record turns in the dark; its speed jumps with the scratches (read from the hi-hat / snare band of the
instrumental). The news sample is typed like a wire; the chant that follows sets up the film's two voices:
the call in white on black, the answer in black on green.
The outro returns to the record, shows the one lit window the lyric talks about, renames the song in solid type and
leaves the next song's title hollow -- it stays hollow through the instrumental tail.
"""
import math

import numpy as np

import beat as B
from base import (GREEN, DGREEN, INK, RED, WHITE, YELLOW, Xf, age, draw_block, draw_tok, rays, solid)
from kit import (ANG, RAD, H, W, chroma, clamp, draw, ease_io, ease_out, flash, glow, grain, lerp, rect, rnd, rrect,
                 scanlines, sprite, vignette, xform, _XX, _YY)

CREAM = np.array([0.98, 0.93, 0.82], np.float32)
_ACC = {}


def _spin(t):
    """record angle (turns): 33 rpm plus what the scratches add, integrated once at 60 Hz."""
    if 'a' not in _ACC:
        n = int(270 * 60)
        a = np.zeros(n, np.float32)
        acc = 0.0
        for k in range(n):
            tt = k / 60.0
            sc = B.snare(tt) + 0.6 * B.hat(tt)
            scratch = 0.0
            if tt < 16.0 or tt > 239.0:
                scratch = 2.4 * sc * math.sin(tt * 37.0)
            acc += (0.55 + scratch) / 60.0
            a[k] = acc
        _ACC['a'] = a
    return float(_ACC['a'][min(len(_ACC['a']) - 1, int(t * 60))])


def vinyl(t, level=1.0, cy=H * 0.5, r_out=700.0):
    rad = RAD if cy == H * 0.5 else np.hypot(_XX - W / 2, _YY - cy)
    ang = ANG if cy == H * 0.5 else np.arctan2(_YY - cy, _XX - W / 2)
    turns = _spin(t)
    groove = 0.5 + 0.5 * np.sin(rad * 0.85)
    # two soft highlights opposite each other, fixed in space; the label and a smudge turn with the record
    hl = np.cos(ang - 0.9) ** 2
    hl = hl ** 6
    wob = 0.5 + 0.5 * np.cos((ang - turns * 2 * math.pi) * 1.0)
    v = 0.035 + 0.045 * groove + 0.30 * hl * (0.6 + 0.4 * groove) + 0.02 * wob
    disc = np.clip((r_out - rad) / 3.0, 0, 1)
    v = v * disc + 0.02 * (1 - disc)
    img = np.repeat(v[..., None], 3, axis=2).astype(np.float32) * level
    lab = np.clip((165.0 - rad) / 2.0, 0, 1)[..., None]
    labcol = GREEN * (0.75 + 0.25 * wob[..., None]) * level
    img = img + (labcol - img) * lab
    hole = np.clip((16.0 - rad) / 2.0, 0, 1)[..., None]
    img = img * (1 - hole)
    # a mark on the label so the turning reads
    a2 = turns * 2 * math.pi
    for rr in (60, 95, 130):
        x, y = W / 2 + math.cos(a2) * rr, cy + math.sin(a2) * rr
        rect(img, x - 7, y - 7, x + 7, y + 7, INK, 0.9 * level)
    return img


def _crackle(img, fi, n=10):
    for k in range(n):
        if rnd(fi, k, 1) < 0.5:
            x, y = int(rnd(fi, k, 2) * W), int(rnd(fi, k, 3) * H)
            s = 1 + int(rnd(fi, k, 4) * 3)
            img[y:y + s, x:x + s] += 0.6
    return img


def _post(img, t, fi, k_zoom=0.02):
    img = xform(img, 1.0 + k_zoom * B.kick(t))
    img = chroma(img, 2 + 6 * B.snare(t))
    img = scanlines(img, 0.6)
    img = glow(img, 0.5, 0.55, 10)
    img = vignette(img, 0.7)
    return _crackle(grain(img, fi, 0.05), fi)


def cold_open(t, fi, s0):
    img = vinyl(t, ease_io(clamp(t / 1.3)))
    return _post(img, t, fi)


def _sticker(img, p, t, cx, cy, rot, col=GREEN, tcol=INK):
    a = age(p, t)
    if a < 0:
        return 0.0
    sc = lerp(2.6, 1.0, ease_out(a / 0.11, 4))
    w = (p.sp.ink[2] - p.sp.ink[0]) + 90
    h = (p.sp.ink[3] - p.sp.ink[1]) + 56
    rrect(img, cx + 14, cy + 18, w * sc, h * sc, rot, (0, 0, 0), 0.55)
    rrect(img, cx, cy, w * sc, h * sc, rot, col, 1.0)
    draw(img, p.sp, cx - (p.sp.ink[0] + p.sp.ink[2]) / 2, cy - (p.sp.ink[1] + p.sp.ink[3]) / 2, tcol, 1.0, scale=sc, rot=rot, cx=cx, cy=cy)
    return math.exp(-a / 0.07)


def intro(t, fi, s):
    L = s.line
    a0 = t - s.t0
    if s.i == 0:
        # the news sample, typed on a wire band over the turning record
        img = vinyl(t)
        placed, bb = L.block(s.rows, (96, 1130, W - 96, 1560), lat='courier', max_size=118, gap=0.30, align='left', valign='top')
        g = ease_out(clamp(a0 / 0.15), 3)
        rect(img, 0, 1080, W * g, 1600, WHITE, 0.96)
        rect(img, 0, 1080, 26 * g, 1600, RED, 1.0)
        typed = None
        for p in placed:
            if draw_tok(img, p, t, INK, kind='cut', fonts=('hei', 'courier')):
                typed = p
        if typed is not None and (int(t * 4) % 2 == 0 or age(typed, t) < 0.3):
            rect(img, typed.x + typed.w + 10, typed.y - 0.72 * typed.size, typed.x + typed.w + 10 + 0.5 * typed.size, typed.y + 0.06 * typed.size, RED, 1.0)
        # level meter of the voice
        v = B.vox(t)
        for q in range(14):
            hh = 20 + 150 * v * (0.4 + 0.6 * rnd(fi // 2, q))
            rect(img, 96 + q * 30, 1040 - hh, 96 + q * 30 + 18, 1040, RED if q < 10 else WHITE, 0.9)
        return _post(img, t, fi)
    if s.i == 1:
        img = vinyl(t, 0.55)
        placed, _ = L.block(s.rows, (60, 260, W - 60, 1680), cjk='hei', max_size=470, gap=0.10)
        sl = 0.0
        for p in placed:
            a = age(p, t)
            if a >= 0:
                sl = max(sl, math.exp(-a / 0.07))
            draw_tok(img, p, t, WHITE, kind='slam', dur=0.10, fonts=('hei', 'anton'), ex=(12, 2.2, 2.6, RED))
        img = xform(img, 1 + 0.06 * sl, 0, (rnd(fi, 1) - 0.5) * 30 * sl, (rnd(fi, 2) - 0.5) * 30 * sl)
        img = flash(img, 0.6 * sl, (1, 1, 1))
        return _post(img, t, fi)
    if s.i == 2:
        second = s.prev is not None and s.prev.i == 2
        img = vinyl(t, 0.45)
        top, _ = L.block([[0, 1], [2]], (60, 250, W - 60, 900), lat='anton', max_size=430, gap=0.08, align='left')
        bot, _ = L.block([[3, 4], [5]], (60, 1060, W - 60, 1710), lat='anton', max_size=430, gap=0.08, align='left')
        ab = age(bot[0], t)
        if second:
            rect(img, 0, 0, W, 960, GREEN, 1.0)
        if ab >= 0:
            g = ease_out(ab / 0.10, 3)
            rect(img, W * (1 - g), 960, W, H, INK if second else GREEN, 1.0)
        draw_block(img, top, t, INK if second else WHITE, kind='pop', hot=WHITE if second else GREEN)
        draw_block(img, bot, t, WHITE if second else INK, kind='pop', hot=GREEN if second else WHITE)
        return _post(img, t, fi)
    # line 3: call, answer, call, answer
    img = vinyl(t, 0.45)
    c1, _ = L.block([[0]], (60, 270, W - 60, 640), lat='anton', max_size=420, align='left')
    c2, _ = L.block([[2]], (60, 1010, W - 60, 1380), lat='anton', max_size=420, align='left')
    r1, _ = L.block([[1]], (60, 0, W - 60, 400), lat='anton', max_size=250)
    r2, _ = L.block([[3]], (60, 0, W - 60, 400), lat='anton', max_size=250)
    draw_block(img, c1, t, WHITE, kind='pop', ex=(8, 2, 2.4, DGREEN))
    draw_block(img, c2, t, WHITE, kind='pop', ex=(8, 2, 2.4, DGREEN))
    fl = _sticker(img, r1[0], t, W * 0.60, 800, -7)
    fl = max(fl, _sticker(img, r2[0], t, W * 0.42, 1545, 6))
    img = flash(img, 0.7 * fl, GREEN)
    return _post(img, t, fi, 0.03)


def _window(img, t, cx, cy, level):
    """one lit window in a dark wall."""
    fl = 0.92 + 0.08 * math.sin(t * 7.3) * math.sin(t * 2.1)
    warm = np.array([1.0, 0.78, 0.40], np.float32) * fl * level
    d = np.hypot((_XX - cx) / 520.0, (_YY - cy) / 620.0)
    img += (np.clip(1 - d, 0, 1) ** 2.2)[..., None] * warm * 0.42
    w, h = 190, 270
    rect(img, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, warm, 1.0)
    rect(img, cx - 5, cy - h / 2, cx + 5, cy + h / 2, INK, 0.9)
    rect(img, cx - w / 2, cy - 5, cx + w / 2, cy + 5, INK, 0.9)


def outro(t, fi, s):
    L = s.line
    a0 = t - s.t0
    if s.i in (70, 71):
        img = solid(np.array([0.03, 0.03, 0.04], np.float32))
        _window(img, t, W / 2, 500, 1.0 if s.i == 70 else 0.8)
        placed, _ = L.block(s.rows, (96, 860, W - 96, 1600), cjk='songm', lat='playb', max_size=225, gap=0.36)
        for p in placed:
            draw_tok(img, p, t, CREAM, kind='fade', dur=0.3, hot=WHITE, fonts=('songm', 'playb'))
        img = xform(img, 1.0 + 0.04 * clamp(a0 / 3.2))
        img = glow(img, 0.7, 0.5, 14)
        img = vignette(img, 0.7)
        return _crackle(grain(img, fi, 0.05), fi)
    if s.i == 72:
        second = s.prev is not None and s.prev.i == 72
        img = solid(GREEN) if second else vinyl(t, 0.5)
        placed, _ = L.block(s.rows, (60, 300, W - 60, 1640), lat='anton', max_size=520, gap=0.07, align='left')
        sl = 0.0
        for p in placed:
            a = age(p, t)
            if a >= 0:
                sl = max(sl, math.exp(-a / 0.07))
            draw_tok(img, p, t, INK if second else WHITE, kind='slam', dur=0.10, fonts=('hei', 'anton'),
                     ex=(10, 2.2, 2.6, WHITE if second else GREEN * 0.7))
        img = xform(img, 1 + 0.05 * sl, 0, (rnd(fi, 1) - 0.5) * 24 * sl, (rnd(fi, 2) - 0.5) * 24 * sl)
        img = flash(img, 0.5 * sl, (1, 1, 1))
        return _post(img, t, fi)
    # 73: the next song's title stays hollow, through the instrumental tail to the end
    k = B.kick(t)
    tb = L.times[-1]
    tail = t - tb
    lvl = 1.0
    if t > 264.2:
        lvl = 1 - ease_io(clamp((t - 264.2) / 1.7))
    if tail > 0:
        img = rays(t, INK, DGREEN * (0.45 + 0.5 * k), n=12, rot=t * 0.10, soft=0.03)
    else:
        img = vinyl(t, 0.45)
    top, _ = L.block([[0, 1, 2, 3]], (64, 330, W - 64, 600), max_size=190, align='left')
    out = {q: 0.028 for q in (4, 5, 6, 7)}
    big, _ = L.block([[4, 5], [6], [7]], (64, 680, W - 64, 1680), lat='anton', max_size=470, gap=0.07, align='left', outline=out)
    draw_block(img, top, t, WHITE, kind='pop', hot=GREEN)
    last = big[-1]
    for p in big:
        st = None
        if tail > 0.25:
            st = (1.0 + 0.045 * k, 0, 0, 0, 1.0)
        draw_tok(img, p, t, GREEN, kind='pop', state=st, hot=WHITE, fonts=('hei', 'anton'))
    if tail > 0:
        # the last hollow word keeps sending its outline out on every beat of the tail
        for q in range(4):
            ph = ((tail / B.BEAT) + q / 4.0) % 1.0
            sc = 1.0 + 0.9 * ph
            draw(img, last.sp, last.x, last.y, GREEN, alpha=0.5 * (1 - ph) ** 1.5, scale=sc)
        # a cursor after it: still to be written
        if int(t * 3.75) % 2 == 0:
            rect(img, last.x + last.w + 18, last.y - 0.74 * last.size, last.x + last.w + 18 + 0.10 * last.size, last.y + 0.02 * last.size, WHITE, 1.0)
    img = xform(img, 1.0 + 0.03 * k, 0, (rnd(fi, 1) - 0.5) * 12 * k * (tail > 0), (rnd(fi, 2) - 0.5) * 12 * k * (tail > 0))
    img = chroma(img, 2 + 5 * B.snare(t))
    img = glow(img, 0.5, 0.55, 10)
    img = vignette(img, 0.6)
    img = grain(img, fi, 0.04)
    return img * lvl
