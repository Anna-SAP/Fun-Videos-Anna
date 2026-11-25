#!/usr/bin/env python3
"""The places of the song, all seen from straight above and all built around one circle at the origin.
Every painter draws in world units (the record's radius is 640) on a canvas that the camera has already
transformed. Nothing here is a photograph or a map tile: every shape is computed.
"""
import math

import numpy as np
import skia

import score
from kit import (PLUS, SCREEN, TAU, back_out, bump, clamp, col, ease_out, kf, lerp, linear, mix, paint, radial, ramp, rgb, rnd, smooth,
                 smoother, sweep)

BIG = 2600.0

# ---- styles: what the record and the lyric look like over each place --------------------------------------
_BASE = dict(sheen_a=1.0, shadow='#1b2a5c', glass_in='#7fb0ff', glass_mid='#3672f4', glass_out='#1f4bcc', glass_a=0.95, groove='#ffffff', groove_a=0.10,
             sheen='#ffffff', rim='#dbe8ff', clear_rim='#ffffff', spindle='#f4f7fc', ink='#14275a', ring_ink='#f2f7ff', ring_a=0.92,
             ring_line_a=0.40, hot='#ee4b6a', spark='#ee4b6a', halo=('#ffffff', 0.9, 7.0), arm='#e9eef7', arm_hi='#ffffff', arm_lo='#b3bfd6',
             arm_dark='#1a2c63', accent='#f4b860', ui='#14275a', bloom=0.05, grain=0.030, vig=0.10)


def _st(**kw):
    d = dict(_BASE)
    d.update(kw)
    return d


STYLES = {
    'obj': _st(),
    'night': _st(ink='#fff3dc', hot='#ffc45e', spark='#ffe2a6', halo=('#070d24', 0.85, 9.0), ring_ink='#eaf1ff', ring_a=0.80, ring_line_a=0.30,
               ui='#dfe8ff', bloom=0.34, grain=0.045, vig=0.30),
    'home': _st(ink='#17306e', hot='#2f6bf2', spark='#2f6bf2', halo=('#fff8ec', 0.95, 8.0), ring_ink='#2a4a96', ring_a=0.72, ring_line_a=0.30,
                clear_rim='#ffffff', bloom=0.04, vig=0.14),
    'dinner': _st(ink='#fff1d8', hot='#ffb14a', spark='#ffd9a0', halo=('#2a140b', 0.85, 9.0), ring_ink='#fff0d6', ring_a=0.78, ring_line_a=0.30,
                  ui='#ffe9c9', bloom=0.12, grain=0.04, vig=0.30),
    'track': _st(ink='#17306e', hot='#ee4b6a', spark='#ee4b6a', halo=('#ffffff', 0.95, 8.0), ring_ink='#213f8a', ring_a=0.70, ring_line_a=0.30,
                 bloom=0.04, vig=0.12),
    'park': _st(ink='#4a2a12', hot='#e2582e', spark='#e2582e', halo=('#fff3da', 0.95, 8.0), ring_ink='#6a3f1c', ring_a=0.70, ring_line_a=0.30,
                ui='#4a2a12', bloom=0.07, vig=0.18),
    'water': _st(shadow='#020818', ink='#eaf6ff', hot='#8fe3ff', spark='#d6f6ff', halo=('#041230', 0.85, 9.0), ring_ink='#eaf6ff', ring_a=0.9,
                 ui='#d5ecff', bloom=0.30, grain=0.04, vig=0.30),
    'objB': _st(sheen_a=0.55, shadow='#7a4a52', glass_in='#fff1e6', glass_mid='#ffc9b4', glass_out='#f08f8f', glass_a=0.92, groove='#ffffff', groove_a=0.16,
                rim='#fff3ea', ink='#3a2148', ring_ink='#7b2a45', ring_a=0.9, ring_line_a=0.38, hot='#f2643d', spark='#f2643d',
                halo=('#fffaf3', 0.9, 7.0), arm_dark='#55294a', accent='#ffd27a', ui='#3a2148', bloom=0.16, vig=0.08),
    'dawn': _st(ink='#17306e', hot='#f2643d', spark='#f2643d', halo=('#ffffff', 0.9, 8.0), ui='#17306e', bloom=0.14, vig=0.10),
}


def blend(a, b, u):
    """mix two styles"""
    if u <= 0:
        return a
    if u >= 1:
        return b
    out = {}
    for k, va in a.items():
        vb = b[k]
        if isinstance(va, (int, float)):
            out[k] = lerp(va, vb, u)
        elif isinstance(va, tuple):
            out[k] = (mix(va[0], vb[0], u), lerp(va[1], vb[1], u), lerp(va[2], vb[2], u))
        elif va is None:
            out[k] = vb
        else:
            out[k] = mix(va, vb, u)
    return out


# ---- people, seen from above ------------------------------------------------------------------------------
WHO = {'he': ('#4f7fe8', '#1c1c28'), 'she': ('#f8ead8', '#3a2418'), 'kid': ('#ffc533', '#2a1c14'), 'ma': ('#b79bc9', '#d0d0d6')}


def person(cv, x, y, kind, head=(0.0, -1.0), s=1.0, sh=None, glow=None, scarf=None, t=0.0):
    if kind == 'she' and scarf is None:
        scarf = True
    """head: unit vector the person faces. sh: (dx, dy, length, alpha) of the cast shadow. scarf: wind phase"""
    coat, hair = WHO[kind]
    hx, hy = head
    ang = math.degrees(math.atan2(hy, hx)) + 90
    if glow:
        cv.drawCircle(x, y, glow[1], paint(glow[0], glow[2], blur=glow[1] * 0.45, blend=PLUS))
    if sh:
        dx, dy, ln, a = sh
        cv.save()
        cv.translate(x + dx * ln * 0.5, y + dy * ln * 0.5)
        cv.rotate(math.degrees(math.atan2(dy, dx)))
        cv.drawOval(skia.Rect.MakeLTRB(-ln * 0.5 - 12 * s, -12 * s, ln * 0.5 + 12 * s, 12 * s), paint('#0a1230', a, blur=5 * s))
        cv.restore()
    cv.save()
    cv.translate(x, y)
    cv.rotate(ang)
    cv.drawOval(skia.Rect.MakeLTRB(-23 * s, -13 * s, 23 * s, 13 * s), paint(coat, 1.0))
    cv.drawOval(skia.Rect.MakeLTRB(-23 * s, -13 * s, 23 * s, 2 * s), paint('#ffffff', 0.16))
    if scarf is not None:
        cv.drawOval(skia.Rect.MakeLTRB(-13 * s, -9 * s, 13 * s, 7 * s), paint('#ea4a5f', 1.0))
    cv.drawCircle(0, -3 * s, 10.5 * s, paint(hair, 1.0))
    cv.drawCircle(-3 * s, -6 * s, 3.2 * s, paint('#ffffff', 0.22, blur=1.2))
    if kind == 'ma':
        cv.drawCircle(0, 6 * s, 4.6 * s, paint(hair, 1.0))
    cv.restore()
    if scarf is not None and scarf is not True:
        # the tail of her scarf blown by the wind (wind blows towards +x, slightly down)
        p = skia.Path()
        p.moveTo(x + 6 * s, y + 2 * s)
        w1 = math.sin(scarf * 9.0) * 7 * s
        w2 = math.sin(scarf * 9.0 + 1.4) * 9 * s
        p.cubicTo(x + 22 * s, y + 4 * s + w1, x + 34 * s, y + 10 * s - w2, x + 50 * s, y + 12 * s + w2)
        cv.drawPath(p, paint('#ea4a5f', 1.0, stroke=6.5 * s))


# ---- 1. Wujiaochang, 23 December 2006, evening ------------------------------------------------------------
ROADS = (-90.0, 0.0, 90.0, 135.0, 180.0)        # five roads: N, E, S, SW, W (degrees, y down)
RING_IN, RING_OUT, WALK = 178.0, 300.0, 326.0
_r = rnd(7)
_BLD = []
_sect = sorted(a % 360 for a in ROADS)
for _i in range(len(_sect)):
    a0, a1 = _sect[_i], _sect[(_i + 1) % len(_sect)] + (360 if _i == len(_sect) - 1 else 0)
    n = int((a1 - a0) / 9)
    for _ in range(n * 3):
        a = math.radians(_r.uniform(a0 + 13, a1 - 13) if a1 - a0 > 40 else (a0 + a1) / 2)
        rr = _r.uniform(430, 1500)
        w, h = _r.uniform(90, 230), _r.uniform(80, 200)
        if abs(rr * math.sin(math.radians((a1 - a0) / 2 - 8))) < 80:
            continue
        _BLD.append((rr * math.cos(a), rr * math.sin(a), w, h, math.degrees(a) + _r.choice([0, 90]), _r.integers(1 << 30), _r.uniform(0.3, 1.0)))
_WIND = [(_r.uniform(-1, 1), _r.uniform(-1, 1), _r.uniform(0.6, 1.4), _r.uniform(0, 1)) for _ in range(46)]
_CARS_RING = [(_r.uniform(0, TAU), _r.uniform(0.36, 0.5), _r.choice([212.0, 262.0]), _r.choice(['#e9eefb', '#f3c94f', '#d9534f', '#9fb5e8', '#f5f5f5'])) for _ in range(8)]
_CARS_ROAD = [(i, lane, _r.uniform(0, 1), _r.uniform(130, 190), _r.choice(['#e9eefb', '#f3c94f', '#d9534f', '#9fb5e8'])) for i in range(5) for lane in (-1, 1)
              for _ in range(2)]


def _car(cv, x, y, ang, body, lights=1.0, s=1.0):
    cv.save()
    cv.translate(x, y)
    cv.rotate(math.degrees(ang))
    cv.drawRoundRect(skia.Rect.MakeLTRB(26 * s, -34 * s, 150 * s, 34 * s), 30, 30, paint('#ffe7b0', 0.20 * lights, blur=16, blend=PLUS))
    cv.drawRoundRect(skia.Rect.MakeLTRB(-21 * s, -11 * s, 21 * s, 11 * s), 6 * s, 6 * s, paint(body, 1.0))
    cv.drawRoundRect(skia.Rect.MakeLTRB(-9 * s, -8.5 * s, 9 * s, 8.5 * s), 4 * s, 4 * s, paint('#0b1330', 0.55))
    cv.drawCircle(-21 * s, -6 * s, 3.2 * s, paint('#ff3b3b', 0.9 * lights))
    cv.drawCircle(-21 * s, 6 * s, 3.2 * s, paint('#ff3b3b', 0.9 * lights))
    cv.drawCircle(-26 * s, 0, 12 * s, paint('#ff2a2a', 0.22 * lights, blur=7, blend=PLUS))
    cv.restore()


def couple_pos(t):
    """the two of them walk once around the ring during the first verse and pre-chorus; returns (angle, gap)"""
    a0 = math.radians(128)
    l5 = score.LINES[5]
    u = clamp((score.flow(t) - score.flow(score.SEC['v1'][0] - 1.5)) / (score.flow(l5['t'][-1] + 0.25) - score.flow(score.SEC['v1'][0] - 1.5)))
    return a0 + TAU * u, u


def wujiaochang(cv, t, p):
    f = score.flow(t)
    quiet = ramp(t, 36.3, 37.4) * (1 - ramp(t, 41.5, 42.2))      # the band thins out in the pre-chorus
    lit = 1 - 0.55 * quiet
    cv.drawRect(skia.Rect.MakeLTRB(-BIG, -BIG, BIG, BIG), paint('#0d1433', 1, shader=radial(0, 0, 1500, [(0, '#1b2658', 1), (1, '#0a0f2a', 1)])))
    # city blocks
    for (x, y, w, h, rot, seed, lum) in _BLD:
        cv.save()
        cv.translate(x, y)
        cv.rotate(rot)
        cv.drawRoundRect(skia.Rect.MakeLTRB(-w / 2 + 14, -h / 2 + 18, w / 2 + 14, h / 2 + 18), 10, 10, paint('#04081c', 0.5, blur=8))
        cv.drawRoundRect(skia.Rect.MakeLTRB(-w / 2, -h / 2, w / 2, h / 2), 10, 10, paint(mix('#18224f', '#27356f', lum), 1))
        cv.drawRoundRect(skia.Rect.MakeLTRB(-w / 2 + 9, -h / 2 + 9, w / 2 - 9, h / 2 - 9), 6, 6, paint('#ffffff', 0.035))
        rr = rnd(int(seed))
        nx, ny = int(w / 26), int(h / 26)
        pw = paint('#ffd68a', 0.75 * lit)
        pc = paint('#a9c8ff', 0.6 * lit)
        for ix in range(nx):
            for iy in range(ny):
                v = rr.random()
                if v < 0.30:
                    cv.drawRect(skia.Rect.MakeXYWH(-w / 2 + 12 + ix * 26, -h / 2 + 12 + iy * 26, 9, 9), pw if v < 0.22 else pc)
        cv.restore()
    # roads
    asph = '#222c5e'
    for a in ROADS:
        cv.save()
        cv.rotate(a)
        cv.drawRect(skia.Rect.MakeLTRB(RING_IN + 60, -78, BIG, 78), paint('#313c75', 1))            # sidewalk
        cv.drawRect(skia.Rect.MakeLTRB(RING_IN + 60, -58, BIG, 58), paint(asph, 1))
        dash = paint('#c9d3ff', 0.34, stroke=3.2, cap=skia.Paint.kButt_Cap)
        dash.setPathEffect(skia.DashPathEffect.Make([26, 30], 0))
        cv.drawLine(RING_OUT + 60, 0, BIG, 0, dash)
        cv.restore()
    cv.drawCircle(0, 0, WALK + 22, paint('#313c75', 1))
    cv.drawCircle(0, 0, RING_OUT, paint(asph, 1))
    cv.drawCircle(0, 0, (RING_IN + RING_OUT) / 2, paint('#c9d3ff', 0.22, stroke=2.4))
    # island: the sunken plaza
    cv.drawCircle(0, 0, RING_IN, paint('#ffffff', 1, shader=radial(0, 0, RING_IN, [(0, '#3b4a94', 1), (0.7, '#2a3777', 1), (1, '#222d63', 1)])))
    for k in range(5):
        cv.drawCircle(0, 0, 34 + k * 30, paint('#b8c6ff', 0.10, stroke=2))
    for k in range(10):
        a = TAU * k / 10
        cv.drawLine(40 * math.cos(a), 40 * math.sin(a), 170 * math.cos(a), 170 * math.sin(a), paint('#b8c6ff', 0.07, stroke=2))
    # lamps
    for a in ROADS:
        for k in range(8):
            for side in (-1, 1):
                d = RING_OUT + 150 + k * 170
                ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
                x, y = d * ca - side * 68 * sa, d * sa + side * 68 * ca
                cv.drawCircle(x, y, 60, paint('#ffb65c', 0.20 * lit, blur=26, blend=PLUS))
                cv.drawCircle(x, y, 4.5, paint('#ffe1ad', 0.95 * lit))
    for k in range(12):
        a = TAU * (k + 0.5) / 12
        x, y = (WALK + 14) * math.cos(a), (WALK + 14) * math.sin(a)
        cv.drawCircle(x, y, 64, paint('#ffb65c', 0.22 * lit, blur=26, blend=PLUS))
        cv.drawCircle(x, y, 4.5, paint('#ffe1ad', 0.95 * lit))
    # traffic: around the ring (clockwise) and along the five roads
    ca = 1 - 0.75 * quiet
    for (a0, w, rr, body) in _CARS_RING:
        a = a0 + w * f
        cv.saveLayer(None, paint('#ffffff', ca)) if ca < 0.99 else cv.save()
        _car(cv, rr * math.cos(a), rr * math.sin(a), a + math.pi / 2, body, lit)
        cv.restore()
    for (i, lane, off, sp, body) in _CARS_ROAD:
        a = math.radians(ROADS[i])
        L = 1700.0
        d = RING_OUT + 80 + ((off * L + lane * sp * f) % L)
        x, y = d * math.cos(a) - lane * 30 * math.sin(a), d * math.sin(a) + lane * 30 * math.cos(a)
        cv.saveLayer(None, paint('#ffffff', ca)) if ca < 0.99 else cv.save()
        _car(cv, x, y, a if lane > 0 else a + math.pi, body, lit)
        cv.restore()
    # the egg: a lattice shell of coloured light over the ring, with the elevated road running under it
    cv.drawRect(skia.Rect.MakeLTRB(-BIG, -40, BIG, 40), paint('#0a1030', 0.38, blur=14))
    cv.drawRect(skia.Rect.MakeLTRB(-BIG, -30, BIG, 30), paint('#3a4686', 0.92))
    cv.drawLine(-BIG, 0, BIG, 0, paint('#d5dcff', 0.25, stroke=2))
    egg = skia.Path()
    egg.addOval(skia.Rect.MakeLTRB(-410, -236, 410, 236))
    cv.save()
    cv.clipPath(egg, True)
    hue = 0.5 + 0.5 * math.sin(f * 0.5)
    g = linear((-410, -236), (410, 236), [(0, mix('#39e0d0', '#7a7cff', hue), 1), (0.5, mix('#7a7cff', '#ff6fb1', hue), 1), (1, mix('#ff6fb1', '#ffc45e', hue), 1)])
    pl = paint('#ffffff', 0.50 * (0.6 + 0.4 * lit), stroke=3.0, shader=g)
    for k in range(-16, 17):
        cv.drawLine(k * 58 - 300, -260, k * 58 + 300, 260, pl)
        cv.drawLine(k * 58 + 300, -260, k * 58 - 300, 260, pl)
    cv.drawOval(skia.Rect.MakeLTRB(-410, -236, 410, 236), paint('#ffffff', 0.10, shader=g))
    cv.restore()
    cv.drawOval(skia.Rect.MakeLTRB(-410, -236, 410, 236), paint('#ffffff', 0.9, stroke=5, shader=g))
    cv.drawOval(skia.Rect.MakeLTRB(-410, -236, 410, 236), paint('#ffffff', 0.5, stroke=16, blur=14, shader=g, blend=PLUS))
    # the two of them, and the circle their walk draws
    a, u = couple_pos(t)
    a0 = math.radians(128)
    closed = ramp(t, score.LINES[5]['t'][-1], score.LINES[5]['t'][-1] + 0.5)
    if u > 0.002:
        path = skia.Path()
        path.addArc(skia.Rect.MakeLTRB(-WALK, -WALK, WALK, WALK), math.degrees(a0), math.degrees(a - a0) - 3)
        dot = paint('#ffe6b8', 0.55 * (1 - closed), stroke=5, cap=skia.Paint.kRound_Cap)
        dot.setPathEffect(skia.DashPathEffect.Make([1, 17], 0))
        cv.drawPath(path, dot)
        if closed > 0:
            cv.drawCircle(0, 0, WALK, paint('#ffd88f', 0.55 * closed, stroke=14, blur=10, blend=PLUS))
            cv.drawCircle(0, 0, WALK, paint('#fff1d1', 0.95 * closed, stroke=3.2))
    # "twenty years": twenty rings run outwards from that circle when the band comes back
    t20 = score.LINES[6]['t'][4]
    if t > t20:
        for k in range(20):
            tk = t20 + k * 0.085
            if t > tk:
                age = t - tk
                rr = WALK + 14 * k + 470 * (1 - math.exp(-age * 1.5))
                cv.drawCircle(0, 0, rr, paint('#ffe2a8', 0.75 * math.exp(-age * 1.3), stroke=2.6))
    gap = lerp(52, 30, smooth(u * 1.15))
    blush = bump(t, 23.8, 24.3, 26.6, 28.5)
    sweat = bump(t, 30.9, 31.4, 34.9, 35.6)
    for kind, da, rr in (('she', 0.0, WALK), ('he', -gap / WALK, WALK - 4)):
        aa = a + da
        x, y = rr * math.cos(aa), rr * math.sin(aa)
        hd = (-math.sin(aa), math.cos(aa))
        if kind == 'she':
            person(cv, x, y, kind, hd, 1.05, glow=('#ff5d7a', 46 + 30 * blush, 0.18 + 0.5 * blush), scarf=f)
        else:
            if sweat > 0:       # his heartbeat, on the beat
                pu = score.pulse(t, 1, 3.0)
                cv.drawCircle(x, y, 30 + 46 * (1 - pu), paint('#8fb4ff', 0.7 * sweat * pu, stroke=2.4))
            person(cv, x, y, kind, hd, 1.05, glow=('#6f9bff', 44, 0.20))
    # wind
    for (wx, wy, sp, ph) in _WIND:
        u2 = (ph + f * 0.55 * sp) % 1.0
        x = -900 + 1800 * u2 + wx * 120
        y = wy * 1100 + 260 * u2
        al = math.sin(math.pi * u2) * 0.20 * (1 - 0.6 * quiet)
        cv.drawLine(x, y, x + 110 * sp, y + 16 * sp, paint('#dfe8ff', al, stroke=2.0))


# ---- 2. the new flat in Zhoupu: the curtains she chose ----------------------------------------------------
def home(cv, t, p):
    f = score.flow(t)
    l = score.LINES[11]
    pull = ramp(t, l['t'][5] - 0.3, l['t'][11] + 0.2)           # she draws the curtain across during the second half-line
    cv.drawRect(skia.Rect.MakeLTRB(-BIG, -BIG, BIG, BIG), paint('#e6cfa9', 1))
    rr = rnd(3)
    for k in range(-24, 25):                                    # floorboards
        x = k * 64
        cv.drawRect(skia.Rect.MakeLTRB(x, -BIG, x + 64, BIG), paint(mix('#e9d3ae', '#dabd92', rr.random()), 1))
        cv.drawLine(x, -BIG, x, BIG, paint('#b89a6c', 0.30, stroke=1.6))
        for j in range(8):
            y = -1500 + j * 420 + rr.uniform(0, 400)
            cv.drawLine(x, y, x + 64, y, paint('#b89a6c', 0.28, stroke=1.6))
    # rug and round table
    cv.drawCircle(10, 16, 384, paint('#7a5a2c', 0.25, blur=16))
    cv.drawCircle(0, 0, 376, paint('#efe5d3', 1))
    for rr2, wdt, c in ((352, 10, '#3b7bf2'), (326, 3, '#3b7bf2'), (250, 2.5, '#9db9ee')):
        cv.drawCircle(0, 0, rr2, paint(c, 0.9, stroke=wdt))
    cv.drawCircle(10, 16, 150, paint('#5a3d1a', 0.30, blur=12))
    cv.drawCircle(0, 0, 146, paint('#ffffff', 1, shader=radial(-30, -40, 220, [(0, '#f8f2e6', 1), (1, '#e6d9c3', 1)])))
    cv.drawCircle(0, 0, 146, paint('#c9b89b', 0.8, stroke=2))
    for k in range(7):                                          # flowers in a glass vase
        a = TAU * k / 7 + 0.3
        cv.drawCircle(46 * math.cos(a), 46 * math.sin(a), 21, paint(['#ffffff', '#cfe1ff', '#ffd9e2'][k % 3], 0.95))
        cv.drawCircle(46 * math.cos(a), 46 * math.sin(a), 6, paint('#f4b860', 1))
    cv.drawCircle(0, 0, 26, paint('#bfe0ff', 0.9))
    cv.drawCircle(0, 0, 26, paint('#ffffff', 0.9, stroke=2))
    # boxes not yet unpacked, a plant, a sofa still in its wrapping
    for (bx, by, bw, rot) in ((-455, 470, 150, 8), (-360, 585, 110, -14), (465, -330, 120, 20)):
        cv.save()
        cv.translate(bx, by)
        cv.rotate(rot)
        cv.drawRect(skia.Rect.MakeLTRB(-bw / 2 + 8, -bw / 2 + 12, bw / 2 + 8, bw / 2 + 12), paint('#5a3d1a', 0.25, blur=10))
        cv.drawRect(skia.Rect.MakeLTRB(-bw / 2, -bw / 2, bw / 2, bw / 2), paint('#cfa66e', 1))
        cv.drawRect(skia.Rect.MakeLTRB(-bw / 2, -9, bw / 2, 9), paint('#e9d4a8', 1))
        cv.drawLine(0, -bw / 2, 0, bw / 2, paint('#a67f48', 0.6, stroke=2))
        cv.restore()
    cv.drawRoundRect(skia.Rect.MakeLTRB(300, 430, 570, 610), 36, 36, paint('#5a3d1a', 0.25, blur=14))
    cv.drawRoundRect(skia.Rect.MakeLTRB(290, 416, 560, 596), 36, 36, paint('#9fb3d1', 1))
    cv.drawRoundRect(skia.Rect.MakeLTRB(310, 432, 540, 536), 24, 24, paint('#b7c8e2', 1))
    cv.drawRoundRect(skia.Rect.MakeLTRB(330, 446, 410, 520), 18, 18, paint('#3b7bf2', 0.95))
    for k in range(9):
        a = TAU * k / 9 + 0.2 * math.sin(f * 0.8 + k)
        cv.save()
        cv.translate(-470, -400)
        cv.rotate(math.degrees(a))
        cv.drawOval(skia.Rect.MakeLTRB(10, -22, 104, 22), paint(mix('#3f9a6a', '#2f7d57', k / 9), 1))
        cv.restore()
    cv.drawCircle(-470, -400, 32, paint('#c98b5b', 1))
    # light through the window: warm where the window is bare, blue and pleated where it comes through the curtain
    wy = -600.0
    sway = math.sin(f * 1.3) * 8
    gap0, gap1 = lerp(-520, -520, pull), lerp(330, -300, pull)       # the bare part of the window: from gap0 to gap1
    sk = -0.42                                                       # the light leans to the left as it crosses the floor
    L = 1750.0

    def beam(x0, x1, c, a, blur=10):
        q = skia.Path()
        q.moveTo(x0, wy)
        q.lineTo(x1, wy)
        q.lineTo(x1 + sk * L, wy + L)
        q.lineTo(x0 + sk * L, wy + L)
        q.close()
        cv.drawPath(q, paint(c, a, blur=blur))
    beam(gap0, gap1, '#fff3cf', 0.50, 12)
    beam(gap1, 520, '#3f7dff', 0.36, 14)
    n = int((520 - gap1) / 84)
    for k in range(n):                                               # the pleats
        x = gap1 + (k + 0.5) * (520 - gap1) / max(1, n) + sway * 0.6 * math.sin(k * 0.9 + f * 2)
        beam(x - 15, x + 15, '#2456c8', 0.10, 12)
    # wall, window, the curtain she chose
    cv.drawRect(skia.Rect.MakeLTRB(-BIG, -BIG, BIG, wy), paint('#f6f2ea', 1))
    cv.drawRect(skia.Rect.MakeLTRB(-BIG, wy - 6, BIG, wy + 16), paint('#6b4c22', 0.22, blur=12))
    cv.drawRect(skia.Rect.MakeLTRB(-540, wy - 40, 540, wy - 8), paint('#cfe6ff', 1))
    cv.drawRect(skia.Rect.MakeLTRB(-540, wy - 40, 540, wy - 8), paint('#8fb2dd', 1, stroke=3))
    for xm in (-270, 0, 270):
        cv.drawLine(xm, wy - 40, xm, wy - 8, paint('#8fb2dd', 1, stroke=3))
    cv.drawLine(-560, wy + 6, 560, wy + 6, paint('#a58a5c', 1, stroke=5))      # the rail
    pth = skia.Path()
    n = 30
    pleat = []
    for k in range(n + 1):
        x = lerp(gap1, 540, k / n)
        y = wy + 40 + 15 * math.sin(k * 1.35 + f * 2.2 * (0.3 + pull)) + sway * 0.5 * (1 - k / n)
        pth.moveTo(x, y) if k == 0 else pth.lineTo(x, y)
        pleat.append((x, y))
    cv.drawPath(pth, paint('#1d3f9a', 0.35, stroke=70, blur=12))
    cv.drawPath(pth, paint('#3b7bf2', 1, stroke=58))
    for k, (x, y) in enumerate(pleat):
        cv.drawLine(x, y - 24, x, y + 24, paint('#2456c8' if k % 2 else '#8fb6ff', 0.55, stroke=3.5))
    # she is drawing it across; he has just put a box down and is looking at her
    person(cv, gap1 - 30, wy + 92, 'she', (1.0, -0.25), 1.5, sh=(-0.3, 1.0, 80, 0.22))
    cv.drawLine(gap1 - 10, wy + 76, gap1 + 14, wy + 52, paint('#f8ead8', 1, stroke=10))
    u = smooth(clamp((t - score.SEC['home'][0] + 0.4) / 3.2))
    hx, hy = lerp(430, 150, u), lerp(120, -300, u)
    person(cv, hx, hy, 'he', (lerp(-0.7, -0.95, u), lerp(-0.7, -0.3, u)), 1.5, sh=(-0.3, 1.0, 90, 0.22))


# ---- 3. supper in Songjiang: "one more dish" --------------------------------------------------------------
def _dish(cv, kind, s=1.0):
    cv.drawCircle(5, 8, 62 * s, paint('#2a1206', 0.35, blur=8))
    if kind == 6:                                   # bamboo steamer of soup dumplings
        cv.drawCircle(0, 0, 62 * s, paint('#c99a5a', 1))
        cv.drawCircle(0, 0, 62 * s, paint('#8a6230', 1, stroke=6 * s))
        cv.drawCircle(0, 0, 50 * s, paint('#efe2c4', 1))
        for k in range(6):
            a = TAU * k / 6
            x, y = (0, 0) if k == 5 else (30 * s * math.cos(a), 30 * s * math.sin(a))
            cv.drawCircle(x, y, 15 * s, paint('#fffaf0', 1))
            cv.drawCircle(x, y, 15 * s, paint('#d9c9a8', 0.8, stroke=1.4))
            cv.drawCircle(x, y, 3 * s, paint('#d9c9a8', 0.9))
        return
    cv.drawCircle(0, 0, 60 * s, paint('#fffdf8', 1))
    cv.drawCircle(0, 0, 60 * s, paint('#d9cfc0', 0.9, stroke=2))
    cv.drawCircle(0, 0, 44 * s, paint('#efe9dd', 0.8, stroke=1.5))
    rr = rnd(100 + kind)
    if kind == 0:                                   # red-braised pork
        cv.drawCircle(0, 0, 40 * s, paint('#6a2a12', 0.55))
        for _ in range(9):
            x, y = rr.uniform(-24, 24) * s, rr.uniform(-24, 24) * s
            cv.drawRoundRect(skia.Rect.MakeXYWH(x - 10 * s, y - 9 * s, 20 * s, 18 * s), 5, 5, paint(mix('#8a3518', '#b4512a', rr.random()), 1))
            cv.drawRoundRect(skia.Rect.MakeXYWH(x - 8 * s, y - 8 * s, 9 * s, 5 * s), 2, 2, paint('#ffd9a8', 0.5))
    elif kind == 1:                                 # greens
        for _ in range(12):
            a = rr.uniform(0, 360)
            cv.save()
            cv.rotate(a)
            cv.drawOval(skia.Rect.MakeLTRB(2 * s, -9 * s, 40 * s, 9 * s), paint(mix('#3f9a52', '#7cc36a', rr.random()), 1))
            cv.restore()
    elif kind == 2:                                 # steamed fish on an oval of soy
        cv.drawOval(skia.Rect.MakeLTRB(-46 * s, -24 * s, 46 * s, 24 * s), paint('#7a4a22', 0.45))
        pth = skia.Path()
        pth.moveTo(-40 * s, 0)
        pth.cubicTo(-20 * s, -22 * s, 16 * s, -18 * s, 28 * s, 0)
        pth.lineTo(44 * s, -14 * s)
        pth.lineTo(44 * s, 14 * s)
        pth.lineTo(28 * s, 0)
        pth.cubicTo(16 * s, 18 * s, -20 * s, 22 * s, -40 * s, 0)
        cv.drawPath(pth, paint('#e7e3da', 1))
        for k in range(5):
            cv.drawLine((-20 + k * 9) * s, -8 * s, (-12 + k * 9) * s, 8 * s, paint('#4f9a4a', 1, stroke=2.4 * s))
        cv.drawCircle(-30 * s, -2 * s, 2.2 * s, paint('#222222', 1))
    elif kind == 3:                                 # soup
        cv.drawCircle(0, 0, 46 * s, paint('#ffffff', 1, shader=radial(-10, -12, 60 * s, [(0, '#ffe7a3', 1), (1, '#f1b955', 1)])))
        for _ in range(7):
            cv.drawCircle(rr.uniform(-28, 28) * s, rr.uniform(-28, 28) * s, rr.uniform(4, 8) * s, paint(rr.choice(['#fff5cf', '#7cc36a', '#ff9a5a']), 0.95))
    elif kind == 4:                                 # shrimp
        for _ in range(8):
            cv.save()
            cv.translate(rr.uniform(-24, 24) * s, rr.uniform(-24, 24) * s)
            cv.rotate(rr.uniform(0, 360))
            pth = skia.Path()
            pth.addArc(skia.Rect.MakeLTRB(-12 * s, -12 * s, 12 * s, 12 * s), 0, 230)
            cv.drawPath(pth, paint(mix('#ff7b4a', '#ffa25f', rr.random()), 1, stroke=7.5 * s))
            cv.restore()
    elif kind == 5:                                 # sliced chicken
        for k in range(6):
            cv.save()
            cv.rotate(-30 + k * 12)
            cv.drawRoundRect(skia.Rect.MakeLTRB(-34 * s, (-26 + k * 8) * s, 34 * s, (-17 + k * 8) * s), 4, 4, paint(mix('#fff0c4', '#f4d68a', k / 6), 1))
            cv.restore()
    else:                                           # sweet rice
        cv.drawCircle(0, 0, 38 * s, paint('#f7e4c0', 1))
        for k in range(8):
            a = TAU * k / 8
            cv.drawCircle(24 * s * math.cos(a), 24 * s * math.sin(a), 6 * s, paint(['#c0392b', '#f4b860', '#3f9a52'][k % 3], 1))
        cv.drawCircle(0, 0, 8 * s, paint('#c0392b', 1))


def dinner(cv, t, p):
    f = score.flow(t)
    t0 = score.SEC['dinner'][0]
    l = score.LINES[12]
    cv.drawRect(skia.Rect.MakeLTRB(-BIG, -BIG, BIG, BIG), paint('#3a2216', 1, shader=radial(0, 0, 1500, [(0, '#5d3a22', 1), (1, '#24130b', 1)])))
    rr = rnd(5)
    for k in range(-14, 15):                         # floor tiles
        for j in range(-18, 19):
            if (k + j) % 2 == 0:
                cv.drawRect(skia.Rect.MakeXYWH(k * 120, j * 120, 120, 120), paint('#ffffff', 0.022))
    # the table
    cv.drawCircle(14, 26, 560, paint('#0d0603', 0.55, blur=30))
    cv.drawCircle(0, 0, 548, paint('#ffffff', 1, shader=radial(-120, -160, 900, [(0, '#d99a62', 1), (1, '#a8683a', 1)])))
    for k in range(9):
        cv.drawCircle(0, 0, 80 + k * 54, paint('#7a4520', 0.10, stroke=2))
    cv.drawCircle(0, 0, 548, paint('#7a4520', 0.8, stroke=5))
    # places: bowls, chopsticks. three of them and one place that is always being filled
    seats = ((-90, 'ma'), (150, 'he'), (30, 'she'))
    for k, (ang, who) in enumerate(seats):
        a = math.radians(ang)
        cv.save()
        cv.rotate(ang + 90)
        cv.translate(0, -445)
        cv.drawCircle(4, 6, 40, paint('#2a1206', 0.35, blur=6))
        cv.drawCircle(0, 0, 38, paint('#fffdf8', 1))
        cv.drawCircle(0, 0, 38, paint('#3b7bf2', 0.85, stroke=3))
        cv.drawCircle(0, 0, 27, paint('#fbf7ee', 1))
        cv.drawLine(58, -38, 64, 44, paint('#5a2d16', 1, stroke=4))
        cv.drawLine(70, -38, 74, 44, paint('#5a2d16', 1, stroke=4))
        cv.drawCircle(-66, 6, 20, paint('#fffdf8', 1))
        cv.drawCircle(-66, 6, 13, paint('#7a4a22', 0.8))
        cv.restore()
    # the turntable in the middle of the table turns with the record
    th = score.theta(t)
    cv.drawCircle(8, 14, 322, paint('#2a1206', 0.35, blur=14))
    cv.save()
    cv.rotate(math.degrees(th))
    cv.drawCircle(0, 0, 316, paint('#ffffff', 1, shader=radial(-80, -90, 520, [(0, '#e9d2ad', 0.97), (1, '#d2b185', 0.97)])))
    cv.drawCircle(0, 0, 316, paint('#ffffff', 0.7, stroke=3))
    cv.drawCircle(0, 0, 300, paint('#a8683a', 0.35, stroke=1.5))
    # dishes arrive one by one; the last one lands on the last word of the line
    times = [t0 - 9, t0 - 9, t0 - 9, t0 - 9, t0 + 0.9, t0 + 2.0, l['t'][9] - 0.1, l['t'][12] - 0.05]
    n = len(times)
    for k in range(n):
        if t < times[k]:
            continue
        a = TAU * k / n + 0.4
        u = clamp((t - times[k]) / 0.45)
        cv.save()
        cv.translate(212 * math.cos(a), 212 * math.sin(a))
        cv.rotate(math.degrees(-th) + k * 40)
        sc = 0.3 + 0.7 * back_out(u)
        cv.scale(sc * (1 + 0.5 * (1 - u)), sc * (1 + 0.5 * (1 - u)))
        _dish(cv, k % 8)
        cv.restore()
        if 0 < t - times[k] < 0.8 and k >= 4:
            cv.drawCircle(212 * math.cos(a), 212 * math.sin(a), 70 + 90 * u, paint('#fff1d0', 0.7 * (1 - clamp((t - times[k]) / 0.8)), stroke=3))
    cv.drawCircle(0, 0, 56, paint('#fffdf8', 1))
    cv.drawCircle(0, 0, 56, paint('#3b7bf2', 0.8, stroke=3))
    cv.drawCircle(0, 0, 40, paint('#f1b955', 1))
    cv.restore()
    # steam
    for k in range(7):
        u = (f * 0.22 + k / 7) % 1.0
        cv.drawCircle(40 * math.sin(k * 2.1 + f) + 30 * u, -60 * u + 20 * math.cos(k * 1.7), 40 + 120 * u, paint('#ffffff', 0.10 * math.sin(math.pi * u), blur=30))
    # the three of them; mother gets up to put the last dish down
    up = bump(t, l['t'][9] - 0.5, l['t'][9], l['t'][12] + 0.3, l['t'][12] + 0.9)
    for ang, who in seats:
        a = math.radians(ang)
        d = 628 - (70 * up if who == 'ma' else 0)
        x, y = d * math.cos(a), d * math.sin(a)
        person(cv, x, y, who, (-math.cos(a), -math.sin(a)), 1.9, sh=(0.3, 0.95, 70, 0.30))
    # the lamp over the table
    cv.drawCircle(0, 0, 820, paint('#ffffff', 1, shader=radial(0, 0, 820, [(0, '#ffd59a', 0.10), (0.6, '#ffb65c', 0.07), (1, '#ffb65c', 0.0)]), blend=PLUS))


# ---- 4. the kart track at the mall in Qingpu, and the same circle years later -----------------------------
TRK = 372.0
_r4 = rnd(11)
_TREES = [(TAU * (k + 0.5) / 14, 720 + 60 * (k % 2), 96 + 26 * _r4.random(), _r4.random()) for k in range(14)]
_TREES += [(TAU * k / 9 + 0.3, 1120 + 70 * (k % 2), 120 + 30 * _r4.random(), _r4.random()) for k in range(9)]
_TREES = [q for q in _TREES if not (520 < q[1] * math.sin(q[0]) < 1000 and abs(q[1] * math.cos(q[0])) < 640)]      # keep the lyric's arc clear
_FLAGS = ['#ee4b6a', '#f4b860', '#3b7bf2', '#3fb37a', '#ffffff']
SEASON = ('#f7b8cf', '#58b56b', '#f0a13a', '#dfe9f2')           # spring, summer, autumn, winter canopies


def lap(t):
    """the kart's angle: one lap per bar, clockwise, starting at the bottom of the track"""
    return math.pi / 2 + TAU * (score.rec(t) - 129) / 4.0


def track(cv, t, p):
    f = score.flow(t)
    t_p = score.SEC['pre2'][0]
    grow = ramp(t, t_p - 0.3, t_p + 1.5)                    # the track turns into a path in a park
    warm = ramp(t, t_p - 0.3, t_p + 2.5)
    ground = mix('#e9eef3', '#f3dfb8', warm)
    cv.drawRect(skia.Rect.MakeLTRB(-BIG, -BIG, BIG, BIG), paint(ground, 1))
    for k in range(-14, 15):
        cv.drawLine(k * 170, -BIG, k * 170, BIG, paint('#9fb0c4', 0.22 * (1 - grow), stroke=2))
        cv.drawLine(-BIG, k * 170, BIG, k * 170, paint('#9fb0c4', 0.22 * (1 - grow), stroke=2))
    sun = (0.62, 0.78)                                       # shadows fall down-right
    slen = lerp(0.55, 1.5, warm)
    # trees: their canopies go round the seasons once a bar in the pre-chorus ("time likes to go round too")
    phase = (score.rec(t) - 145) / 4.0
    for (a, d, r0, v) in _TREES:
        x, y = d * math.cos(a), d * math.sin(a)
        cv.drawCircle(x + sun[0] * r0 * slen, y + sun[1] * r0 * slen, r0, paint('#3a2a10', 0.20, blur=14))
    for (a, d, r0, v) in _TREES:
        x, y = d * math.cos(a), d * math.sin(a)
        if grow > 0:
            ph = (phase + v * 0.12) % 1.0 * 4
            c = mix(SEASON[int(ph) % 4], SEASON[(int(ph) + 1) % 4], smooth(ph - int(ph)))
            c = mix('#58b56b', c, grow)
        else:
            c = mix('#58b56b', '#3f9a5a', v)
        cv.drawCircle(x, y, r0, paint(c, 1))
        cv.drawCircle(x - r0 * 0.25, y - r0 * 0.28, r0 * 0.62, paint('#ffffff', 0.16, blur=10))
        cv.drawCircle(x + r0 * 0.2, y + r0 * 0.2, r0 * 0.5, paint('#000000', 0.07, blur=10))
    # the track
    cv.drawCircle(0, 0, TRK + 96, paint('#3a2a10', 0.18, blur=20))
    cv.drawCircle(0, 0, TRK, paint(mix('#3c4458', '#e7cf9d', grow), 1, stroke=150))
    curb = paint('#ee4b6a', 1 - grow, stroke=16, cap=skia.Paint.kButt_Cap)
    curb.setPathEffect(skia.DashPathEffect.Make([34, 34], 0))
    for rr in (TRK - 75, TRK + 75):
        cv.drawCircle(0, 0, rr, paint('#ffffff', 1 - 0.4 * grow, stroke=16 - 8 * grow))
        cv.drawCircle(0, 0, rr, curb)
    dash = paint('#ffffff', 0.6 * (1 - grow), stroke=4, cap=skia.Paint.kButt_Cap)
    dash.setPathEffect(skia.DashPathEffect.Make([30, 40], 0))
    cv.drawCircle(0, 0, TRK, dash)
    for k in range(6):                                       # start line
        for j in range(2):
            if (k + j) % 2 == 0:
                cv.drawRect(skia.Rect.MakeXYWH(-20 + j * 20, TRK - 60 + k * 20, 20, 20), paint('#ffffff', 0.95 * (1 - grow)))
    # the infield: turf, then a round fountain in the park
    cv.drawCircle(0, 0, TRK - 84, paint(mix('#62bf78', '#8fca84', warm), 1))
    cv.drawCircle(0, 0, TRK - 84, paint('#ffffff', 0.10, shader=radial(-80, -100, 400, [(0, '#ffffff', 0.5), (1, '#ffffff', 0)])))
    cv.drawCircle(0, 0, 150, paint('#e9eef3', 1))
    cv.drawCircle(0, 0, 150, paint('#b9c7d6', 1, stroke=6))
    cv.drawCircle(0, 0, 122, paint('#ffffff', 1, shader=radial(0, 0, 122, [(0, '#bfe6ff', 1), (1, '#6fb4ee', 1)])))
    for k in range(3):
        u = (f * 0.5 + k / 3) % 1.0
        cv.drawCircle(0, 0, 14 + 100 * u, paint('#ffffff', 0.8 * (1 - u), stroke=3))
    cv.drawCircle(0, 0, 12, paint('#ffffff', 1))
    # bunting round the track
    for k in range(40):
        a = TAU * k / 40
        cv.save()
        cv.rotate(math.degrees(a))
        cv.translate(TRK + 122, 0)
        pth = skia.Path()
        pth.moveTo(0, -11)
        pth.lineTo(24 + 3 * math.sin(f * 4 + k), 0)
        pth.lineTo(0, 11)
        pth.close()
        cv.drawPath(pth, paint(_FLAGS[k % 5], 0.95 * (1 - grow)))
        cv.restore()
    cv.drawCircle(0, 0, TRK + 122, paint('#8794a8', 0.7 * (1 - grow), stroke=2.5))
    # the kart and its laps
    a = lap(t)
    if grow < 1:
        for k in range(1, 30):
            aa = a - k * 0.055
            al = 0.30 * (1 - k / 30) * (1 - grow)
            cv.drawCircle(TRK * math.cos(aa), TRK * math.sin(aa), 15 - k * 0.3, paint('#ffd23f', al))
        x, y = TRK * math.cos(a), TRK * math.sin(a)
        cv.save()
        cv.translate(x, y)
        cv.rotate(math.degrees(a) + 90)
        cv.saveLayer(None, paint('#ffffff', 1 - grow))
        cv.drawRoundRect(skia.Rect.MakeLTRB(-44 + 8, -28 + 12, 44 + 8, 28 + 12), 12, 12, paint('#1a2233', 0.35, blur=8))
        for wx in (-30, 30):
            for wy in (-30, 30):
                cv.drawRoundRect(skia.Rect.MakeXYWH(wx - 11, wy - 7, 22, 14), 4, 4, paint('#1a2233', 1))
        cv.drawRoundRect(skia.Rect.MakeLTRB(-44, -24, 44, 24), 12, 12, paint('#ffd23f', 1))
        cv.drawRoundRect(skia.Rect.MakeLTRB(26, -24, 44, 24), 8, 8, paint('#ee4b6a', 1))
        cv.drawRect(skia.Rect.MakeLTRB(-44, -4, 30, 4), paint('#ffffff', 0.9))
        cv.drawCircle(-6, 0, 16, paint('#ee4b6a', 1))                      # a red helmet
        cv.drawCircle(-10, -4, 5, paint('#ffffff', 0.5, blur=1.5))
        cv.restore()
        cv.restore()
        # the two of them at the fence, turning their heads after the kart
        for who, px, py in (('she', -400, -405), ('he', -340, -448)):
            dx, dy = x - px, y - py
            d = math.hypot(dx, dy) + 1e-6
            near = math.exp(-((d - 160) / 220) ** 2) if d < 700 else 0
            cv.saveLayer(None, paint('#ffffff', 1 - grow))
            person(cv, px, py, who, (dx / d, dy / d), 1.6, sh=(sun[0], sun[1], 70, 0.25), glow=('#ffffff', 70, 0.10 + 0.25 * near))
            cv.restore()
    # years later: three walk the same circle; the child's shadow grows up to his shoulder
    if grow > 0:
        l15, l16 = score.LINES[15], score.LINES[16]
        aw = math.pi * 0.62 + 0.9 * (score.flow(t) - score.flow(t_p)) / 8.6 * math.pi
        g = smooth(clamp((t - l15['t'][0]) / (l16['t'][-1] - l15['t'][0])))
        hd = (-math.sin(aw), math.cos(aw))
        for who, off, s, shl in (('she', TRK + 62, 1.7, 190), ('kid', TRK, lerp(0.75, 1.5, g), lerp(50, 166, g)), ('he', TRK - 62, 1.7, 196)):
            x, y = off * math.cos(aw), off * math.sin(aw)
            cv.saveLayer(None, paint('#ffffff', grow))
            person(cv, x, y, who, hd, s, sh=(sun[0], sun[1], shl * slen / 1.5 * 1.25, 0.40))
            cv.restore()
        # low sun
        cv.drawRect(skia.Rect.MakeLTRB(-BIG, -BIG, BIG, BIG), paint('#ffffff', warm, shader=linear((-800, -900), (700, 900), [(0, '#ffcf7a', 0.34), (1, '#ff9a5a', 0.04)]), blend=skia.BlendMode.kSoftLight))


# ---- the turntable under the record -----------------------------------------------------------------------
def deck(cv, t, p, pal='A'):
    """screen-space background of the object shots; p: dict(cam=Cam). Rings of light leave the record on the beat."""
    cam = p['cam']
    if pal == 'A':
        g = linear((0, 0), (0, 1920), [(0, '#eef5fd', 1), (0.55, '#dfeaf8', 1), (1, '#cfe0f5', 1)])
        ringc, plat, plat_e = '#ffffff', '#f6f9fe', '#b4c6e2'
    else:
        g = linear((0, 0), (0, 1920), [(0, '#ffe3cf', 1), (0.45, '#fdeee6', 1), (1, '#d8e8fb', 1)])
        ringc, plat, plat_e = '#ffffff', '#fffaf5', '#e3bfae'
    cv.drawPaint(paint('#ffffff', 1, shader=g))
    cx, cy = cam.pt(0, 0)
    R = 640 * cam.z
    cv.drawCircle(cx - 260, cy - 420, 900, paint('#ffffff', 0.55, blur=220))
    b = score.rec(t)
    for k in range(5):
        u = ((b / 4.0) - k / 5.0) % 1.0
        cv.drawCircle(cx, cy, R + 40 + 760 * u, paint(ringc, 0.75 * (1 - u) ** 1.5, stroke=3.0))
        cv.drawCircle(cx, cy, R + 40 + 760 * u, paint('#7fa4dd' if pal == 'A' else '#f0a68e', 0.10 * (1 - u), stroke=10, blur=8))
    cv.drawCircle(cx + 8 * cam.z, cy + 16 * cam.z, R + 34 * cam.z, paint('#3b5a94' if pal == 'A' else '#9a5a52', 0.22, blur=22))
    cv.drawCircle(cx, cy, R + 34 * cam.z, paint(plat, 1))
    cv.drawCircle(cx, cy, R + 34 * cam.z, paint(plat_e, 0.9, stroke=2))
    n = 72
    th = score.theta(t, 'A' if pal == 'A' else 'B')
    for k in range(n):                                       # strobe dots on the platter's edge
        a = TAU * k / n + th
        cv.drawCircle(cx + (R + 19 * cam.z) * math.cos(a), cy + (R + 19 * cam.z) * math.sin(a), 2.6 * cam.z, paint(plat_e, 0.9))


def label(cv, cam, t, disc='A', kid=0.0, alpha=1.0, rot=0.0):
    """the paper label in the middle of the record: the two of them, side by side, going round"""
    import disc as D
    from kit import SERIF_B, PLAY_I, glyph
    cx, cy = cam.pt(0, 0)
    z = cam.z
    r = D.RL * z
    th = score.theta(t, disc) + rot
    cv.saveLayer(None, paint('#ffffff', alpha))
    if disc == 'A':
        cv.drawCircle(cx, cy, r, paint('#ffffff', 1, shader=radial(cx - 40 * z, cy - 50 * z, r * 1.5, [(0, '#fffdf7', 1), (1, '#f3ead8', 1)])))
        c1, c2 = '#1f4bcc', '#8a97b8'
    else:
        cv.drawCircle(cx, cy, r, paint('#ffffff', 1, shader=radial(cx - 40 * z, cy - 50 * z, r * 1.5, [(0, '#fffaf2', 1), (1, '#ffe4cf', 1)])))
        c1, c2 = '#b03a56', '#c79a8a'
    cv.drawCircle(cx, cy, r - 10 * z, paint(c1, 0.9, stroke=2.2 * z))
    cv.drawCircle(cx, cy, r - 17 * z, paint(c1, 0.5, stroke=1.0 * z))
    cv.save()
    cv.translate(cx, cy)
    cv.rotate(math.degrees(th))
    # title on the upper arc, years on the lower one
    for k, ch in enumerate('兜一圈'):
        a = math.radians(-90 + (k - 1) * 30)
        glyph(cv, ch, 116 * z * math.cos(a), 116 * z * math.sin(a), SERIF_B, 46 * z, paint(c1, 1), rot=math.degrees(a) + 90)
    yrs = '2006 — 2026' if disc == 'A' else '2026 —'
    n = len(yrs)
    for k, ch in enumerate(yrs):
        a = math.radians(90 - (k - (n - 1) / 2) * 9.5)
        glyph(cv, ch, 126 * z * math.cos(a), 126 * z * math.sin(a), PLAY_I, 25 * z, paint(c2, 1), rot=math.degrees(a) - 90)
    # the two of them
    cv.scale(z, z)
    person(cv, -58, 4, 'he', (0, -1), 1.15)
    person(cv, 58, 4, 'she', (0, -1), 1.15, scarf=None)
    if kid > 0:
        cv.saveLayer(None, paint('#ffffff', kid))
        person(cv, 0, 58, 'kid', (0, -1), 0.95)
        cv.restore()
    cv.restore()
    cv.restore()
