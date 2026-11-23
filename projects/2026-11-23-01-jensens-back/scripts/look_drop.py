"""Build (snare roll, call and response) and Drop (EDM, supersaw lead).

Build: call = white on black; response = the frame answering in negative. "Ready?" is re-struck on every stutter
of the vocal (times measured from the vocal stem) while the tunnel behind it speeds up; the count-down numerals
each take the whole frame.
Drop: the hook's colours turned inside out -- black type on full-bleed colour, one colour per bar; the recording
repeats one bar of chant, so every bar is the same two shots in a new colour.
"""
import math

import numpy as np

import beat as B
from base import (GREEN, DGREEN, INK, MAGENTA, RED, DRED, WHITE, YELLOW, CYAN, Xf, age, draw_block, draw_tok, rays, rings,
                  solid)
from hand_times import ECHO
from kit import (H, W, chroma, clamp, draw, ease_out, flash, glow, grain, lerp, quad, rect, rnd, rrect, sprite, vignette,
                 xform)

M = 60
BARS = [(GREEN, INK, WHITE), (YELLOW, INK, WHITE), (MAGENTA, WHITE, INK), (WHITE, INK, GREEN)]


def _ticker(img, t, toks, y, size, col, band, speed):
    txt = ''.join(tk['text'] + ('—' if tk['dash'] else '') for tk in toks) + '  ◆  '
    txt = txt.replace('◆', '/')
    sp = sprite(txt, 'hei', 'anton', size)
    rect(img, 0, y - size * 0.98, W, y + size * 0.30, band, 1.0)
    w = max(40.0, sp.adv)
    x = -((t * speed) % w) if speed > 0 else ((-t * speed) % w) - w
    while x < W:
        draw(img, sp, x, y, col)
        x += w


def build(t, fi, s):
    if s.i == 39:
        return ready(t, fi, s)
    L = s.line
    a0 = t - s.t0
    img = rings(t, INK, np.array([0.10, 0.10, 0.11], np.float32), period=150, speed=0.9 + 0.25 * s.n, soft=0.05)
    placed, bb = L.block(s.rows, (M, 300, W - M, 1640), cjk='hei', lat='anton', max_size=470, gap=0.20, align='left')
    inv = 0.0
    rowsn = len(s.rows)
    for r in range(rowsn):
        ps = [p for p in placed if p.row == r]
        if ps[0].tok['back']:
            a = age(ps[0], t)
            if a < 0:
                continue
            g = ease_out(a / 0.09, 3)
            y0 = min(p.y - 0.90 * p.size for p in ps) - 16
            y1 = max(p.y + 0.14 * p.size for p in ps) + 16
            rect(img, W * (1 - g), y0, W, y1, WHITE, 1.0)
            inv = max(inv, math.exp(-a / 0.06))
            for p in ps:
                draw_tok(img, p, t, INK, kind='left', dur=0.10, hot=RED, fonts=('hei', 'anton'))
        else:
            for p in ps:
                draw_tok(img, p, t, WHITE, kind='pop', hot=GREEN)
    img = xform(img, 1.0 + 0.05 * clamp(a0 / 3.2) + 0.02 * B.kick(t))
    if inv > 0.5:
        img = 1.0 - img
    img = chroma(img, 4 * B.snare(t))
    img = glow(img, 0.45, 0.6, 10)
    img = vignette(img, 0.5)
    return grain(img, fi, 0.04)


def ready(t, fi, s):
    L = s.line
    rd, _ = L.block([[0]], (M, 600, W - M, 1300), lat='anton', max_size=600)
    p = rd[0]
    nums = [1, 2, 3]
    tn = [L.times[q] for q in nums]
    if t + 0.045 >= tn[0]:
        # count-down: each numeral takes the whole frame
        q = max(k for k in range(3) if t + 0.045 >= tn[k])
        bg, fg = [(RED, WHITE), (YELLOW, INK), (WHITE, INK)][q]
        a = t + 0.045 - tn[q]
        img = rays(t, bg, bg * 0.82, n=10, rot=t * 0.9, soft=0.02)
        sp = sprite(L.toks[nums[q]]['text'], 'hei', 'anton', 1040)
        fit = min(1.0, (W - 120) / max(1, sp.ink[2] - sp.ink[0]))
        sc = fit * lerp(2.4, 1.0, ease_out(a / 0.10, 4)) * (1.0 + 0.06 * clamp(a / 0.4))
        cx, cy = W / 2, H / 2 - 20
        px = cx - (sp.ink[0] + sp.ink[2]) / 2
        py = cy - (sp.ink[1] + sp.ink[3]) / 2
        draw(img, sp, px + 22, py + 26, INK if q == 0 else GREEN * 0.0 + (0.55, 0.5, 0.0) if q == 1 else (0.6, 0.6, 0.6), 1.0, scale=sc, cx=cx, cy=cy)
        draw(img, sp, px, py, fg, 1.0, scale=sc, cx=cx, cy=cy)
        img = xform(img, 1.0, 0, (rnd(fi, 3) - 0.5) * 30 * math.exp(-a / 0.1), (rnd(fi, 4) - 0.5) * 30 * math.exp(-a / 0.1))
        img = flash(img, math.exp(-a / 0.04), (1, 1, 1))
        img = chroma(img, 6)
        return grain(vignette(img, 0.3), fi, 0.04)
    hits = [p.t] + ECHO['ready']
    n = sum(1 for h in hits if t + 0.045 >= h)
    last = max(h for h in hits if t + 0.045 >= h)
    a = t + 0.045 - last
    prog = clamp((t - p.t) / (tn[0] - p.t))
    neg = n % 2 == 0
    bgc, fgc = (WHITE, INK) if neg else (INK, WHITE)
    img = rings(t * (1 + 3 * prog) , bgc, bgc * 0.86 + (GREEN * 0.20 if not neg else 0), period=170, speed=1.2, soft=0.04)
    sc = lerp(1.35 + 0.3 * prog, 1.0, ease_out(a / 0.12, 3)) * (0.86 + 0.16 * prog)
    draw_tok(img, p, t, fgc, state=(sc, 0, 0, (rnd(n, 9) - 0.5) * 10 * prog, 1.0), fonts=('hei', 'anton'),
             ex=(10, 2.2, 2.6, GREEN if not neg else RED))
    sn = B.snare(t)
    img = xform(img, 1.0 + 0.03 * sn, 0, (rnd(fi, 1) - 0.5) * 22 * prog, (rnd(fi, 2) - 0.5) * 22 * prog)
    img = chroma(img, 3 + 8 * prog)
    img = flash(img, 0.6 * math.exp(-a / 0.05), GREEN if not neg else (1, 1, 1))
    img = glow(img, 0.4, 0.6, 10)
    return grain(vignette(img, 0.5), fi, 0.04)


def _hey(img, L, idx, t, col, tcol, y0=1300):
    """the two-syllable answer: two blocks thrown in from the left and the right."""
    for q, i in enumerate(idx):
        sp = sprite(L.toks[i]['text'], 'hei', 'anton', 210)
        a = t + 0.045 - L.times[i]
        if a < 0:
            continue
        g = ease_out(a / 0.10, 4)
        cx = lerp(-300, 300, g) if q == 0 else lerp(W + 300, W - 310, g)
        cy = y0 + (0 if q == 0 else 190)
        rot = (-9 if q == 0 else 7) + 2 * math.sin(t * 11 + q)
        w = sp.ink[2] - sp.ink[0] + 90
        h = sp.ink[3] - sp.ink[1] + 56
        rrect(img, cx + 14, cy + 16, w, h, rot, (0, 0, 0), 0.5)
        rrect(img, cx, cy, w, h, rot, col, 1.0)
        draw(img, sp, cx - (sp.ink[0] + sp.ink[2]) / 2, cy - (sp.ink[1] + sp.ink[3]) / 2, tcol, 1.0, rot=rot, cx=cx, cy=cy)


def _drop_post(img, t, fi, slam):
    k = B.kick(t)
    img = xform(img, 1.0 + 0.05 * k + 0.10 * slam, 0, (rnd(fi, 1) - 0.5) * 34 * max(k, slam), (rnd(fi, 2) - 0.5) * 34 * max(k, slam))
    img = chroma(img, 4 + 8 * k, radial=0.006 + 0.012 * max(k, slam))
    img = glow(img, 0.35, 0.7, 9)
    img = vignette(img, 0.4)
    return grain(img, fi, 0.04)


def drop(t, fi, s):
    import score
    L = s.line
    kbar = int(round((L.times[0] - 137.6) // 3.2)) % 4
    col, tcol, ecol = BARS[kbar]
    if s.i == 40:
        img = rays(t, col, col * 0.72, n=12, rot=t * 0.45, soft=0.02)
        call, _ = L.block([[0], [1]], (M - 10, 290, W - M + 10, 1180), lat='anton', max_size=640, gap=0.06)
        slam = 0.0
        for p in call:
            a = age(p, t)
            if a >= 0:
                slam = max(slam, math.exp(-a / 0.07))
            draw_tok(img, p, t, tcol, kind='slam', dur=0.10, fonts=('hei', 'anton'), ex=(14, 2.2, 2.6, ecol))
        _hey(img, L, (2, 3), t, tcol, col, y0=1330)
    else:
        col, tcol, ecol = RED, WHITE, INK
        img = rays(t, RED, DRED * 1.5, n=12, rot=-t * 0.45, soft=0.02)
        # limit-up arrows climbing
        for q in range(9):
            x = 80 + q * 118 + 30 * math.sin(q * 1.7)
            y = H - ((t * (700 + 90 * (q % 3)) + q * 211) % (H + 300)) + 150
            quad(img, [(x, y - 70), (x + 52, y + 30), (x - 52, y + 30)], WHITE, 0.22)
            rect(img, x - 18, y + 30, x + 18, y + 120, WHITE, 0.22)
        cur = [q for q in (0, 1, 2) if t + 0.045 >= L.times[q]]
        slam = 0.0
        if cur:
            q = cur[-1]
            a = t + 0.045 - L.times[q]
            slam = math.exp(-a / 0.07)
            sp = sprite(L.toks[q]['text'], 'hei', 'anton', 820)
            fit = min(1.0, (W - 110) / max(1, sp.ink[2] - sp.ink[0]))
            sc = fit * lerp(2.6, 1.0, ease_out(a / 0.10, 4)) * (1 + 0.05 * clamp(a / 0.4))
            cx, cy = W / 2, 780
            px = cx - (sp.ink[0] + sp.ink[2]) / 2
            py = cy - (sp.ink[1] + sp.ink[3]) / 2
            draw(img, sp, px + 24, py + 28, INK, 1.0, scale=sc, cx=cx, cy=cy)
            draw(img, sp, px, py, WHITE, 1.0, scale=sc, cx=cx, cy=cy)
        _hey(img, L, (3, 4), t, YELLOW, INK, y0=1330)
    if kbar >= 1:
        # the two sheet lines the recording does not sing run as tape above and below
        _ticker(img, t, score.TOK[42], 236, 60, YELLOW if s.i == 41 else col, INK, 420)
        _ticker(img, t, score.TOK[43], 1740, 60, YELLOW if s.i == 41 else col, INK, -420)
    img = flash(img, 0.8 * slam * (1 if (t - s.t0) < 0.5 or slam > 0.6 else 0.6), (1, 1, 1))
    return _drop_post(img, t, fi, slam)
