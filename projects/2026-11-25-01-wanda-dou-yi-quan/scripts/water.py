#!/usr/bin/env python3
"""From the bridge to the end: the drop of water, the twenty rings running out over the city, the round lake by
the sea, the next record, the goodbye, and the map of the five places.

The map is drawn, not traced: a few hand-placed points in kilometres east/south of the city centre, enough to
recognise the coast, the river and where the five places of the song lie relative to each other.
"""
import math

import numpy as np
import skia

import disc as D
import scenes as S
import score
from kit import (KAI, PLAY_I, PLUS, SCREEN, SERIF_B, SERIF_K, SERIF_M, TAU, H, W, back_out, bump, clamp, ease_in, ease_out, glyph, kf, lerp,
                 linear, mix, paint, radial, ramp, rnd, smooth, smoother, text, text_w)

SEC = score.SEC
T_BR = SEC['bridge'][0]                 # 105.44
T_RINGS = score.LINES[21]['t'][6]       # the word on which the rings are let go
T_CH3 = score.grid(0, 'B')              # 123.10
WJC, ZP, SJ, QP, LG = (4.3, -7.8), (9.5, 13.3), (-22.8, 22.2), (-25.6, 8.9), (43.7, 36.6)
PLACE = ((WJC, '五角场'), (ZP, '周浦'), (SJ, '松江'), (QP, '青浦万达茂'), (LG, '临港'))
LAND = [(-90, -70), (-45, -48), (-30, -38), (-16, -30), (-5, -23), (2.9, -17.8), (12, -15), (22, -12.5), (30, -8), (36, 0), (40, 10), (43.5, 20),
        (46, 30), (46.9, 36), (47.0, 40.3), (44.5, 41.2), (38, 42.5), (28, 44), (15, 45.5), (3, 46), (-8, 50), (-16, 56), (-30, 60), (-50, 64), (-90, 68)]
RIVER = [(2.9, -17.8), (4.5, -12), (6.5, -7), (5.5, -3), (2.5, -1), (1.0, 2), (3.5, 5), (2, 9), (0, 13), (-1.5, 19), (-3, 24), (-8, 26), (-16, 25.5),
         (-26, 26), (-40, 24), (-90, 21)]
CREEK = [(2.5, -1.5), (-3, -2.5), (-10, -1), (-20, -3), (-40, -6), (-90, -9)]
LAKE_R = 1.3
ARRIVE = (45.3, 38.2)


def _poly(pts, close=True):
    p = skia.Path()
    p.moveTo(*pts[0])
    for i in range(1, len(pts)):
        p.lineTo(*pts[i])
    if close:
        p.close()
    return p


def _smooth_path(pts, close=False):
    """Catmull-Rom through the points"""
    p = skia.Path()
    n = len(pts)
    p.moveTo(*pts[0])
    for i in range(n - 1 if not close else n):
        p0, p1, p2, p3 = pts[max(0, i - 1) if not close else (i - 1) % n], pts[i % n], pts[(i + 1) % n], pts[min(n - 1, i + 2) if not close else (i + 2) % n]
        p.cubicTo(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6, p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, p2[0], p2[1])
    if close:
        p.close()
    return p


_LAND = _smooth_path(LAND, True)
_RIVER = _smooth_path(RIVER)
_CREEK = _smooth_path(CREEK)
_r = rnd(21)
_LIGHTS = []
while len(_LIGHTS) < 1500:
    if len(_LIGHTS) < 950:
        d = abs(_r.normal(0, 13))
        a = _r.uniform(0, TAU)
        x, y = 1.5 + d * math.cos(a), 0.5 + d * math.sin(a)
    else:
        c = PLACE[int(_r.integers(0, 5))][0] if _r.random() < 0.6 else (_r.uniform(-60, 46), _r.uniform(-40, 50))
        x, y = c[0] + _r.normal(0, 3.5), c[1] + _r.normal(0, 3.5)
    if _LAND.contains(x, y):
        _LIGHTS.append((x, y))
_LIGHTS = [skia.Point(x, y) for x, y in _LIGHTS]
_r2 = rnd(5)
_DUST = [(_r2.uniform(0, W), _r2.uniform(0, H), _r2.uniform(0.6, 2.2), _r2.uniform(0, 1)) for _ in range(90)]

NIGHT = dict(sea0='#06142f', sea1='#0b2a5c', land='#15346c', land_e='#2f62b8', river='#0a2552', ring='#6f9fea', light='#ffd79a', label='#dcebff')
DAY = dict(echo=1.0, sea0='#b9d6f6', sea1='#d3e7fb', land='#fbfaf5', land_e='#8fb3e0', river='#9cc4f2', ring='#c3d2ea', light='#a9c0e2', label='#17306e')


class MapCam:
    def __init__(self, s, kx, ky, sx=540.0, sy=850.0):
        self.s, self.kx, self.ky, self.sx, self.sy = s, kx, ky, sx, sy

    def pt(self, x, y):
        return self.sx + (x - self.kx) * self.s, self.sy + (y - self.ky) * self.s


def draw_map(cv, mc, pal, t, alpha=1.0, lights=1.0, rings_glow=0.0):
    cv.saveLayer(None, paint('#ffffff', alpha))
    cv.drawPaint(paint('#ffffff', 1, shader=linear((0, 0), (W, H), [(0, pal['sea0'], 1), (1, pal['sea1'], 1)])))
    cv.save()
    cv.translate(mc.sx, mc.sy)
    cv.scale(mc.s, mc.s)
    cv.translate(-mc.kx, -mc.ky)
    px = 1.0 / mc.s
    # islands in the river mouth
    for (cx, cy, rx, ry, rot) in ((25, -38, 42, 8.5, -17), (26, -21.5, 11, 3.0, -20), (41, -15, 4.5, 2.6, -20)):
        cv.save()
        cv.translate(cx, cy)
        cv.rotate(rot)
        cv.drawOval(skia.Rect.MakeLTRB(-rx, -ry, rx, ry), paint(pal['land'], 1))
        cv.drawOval(skia.Rect.MakeLTRB(-rx, -ry, rx, ry), paint(pal['land_e'], 0.55, stroke=1.6 * px))
        cv.restore()
    for wdt, al in ((34, 0.16), (18, 0.26)):
        cv.drawPath(_LAND, paint('#ffffff', al * pal.get('echo', 0.0), stroke=wdt * px))
    cv.drawPath(_LAND, paint(pal['land_e'], 0.35, stroke=10 * px, blur=6 * px))
    cv.drawPath(_LAND, paint(pal['land'], 1))
    cv.drawPath(_LAND, paint(pal['land_e'], 0.7, stroke=1.8 * px))
    cv.save()
    cv.clipPath(_LAND, True)
    # ring roads: the city itself is drawn in circles
    for (rx, ry, a) in ((6, 6.5, 0.55), (9.5, 10, 0.45), (14.5, 14, 0.38), (27, 25, 0.22)):
        cv.drawOval(skia.Rect.MakeLTRB(1.5 - rx, 0.5 - ry, 1.5 + rx, 0.5 + ry), paint(pal['ring'], a, stroke=max(1.4 * px, 0.14)))
    cv.drawPath(_CREEK, paint(pal['river'], 1, stroke=max(0.22, 1.5 * px)))
    cv.drawPath(_RIVER, paint(pal['river'], 1, stroke=max(0.62, 3 * px)))
    if lights > 0:
        pp = paint(pal['light'], 0.85 * lights, stroke=max(0.16, 1.9 * px))
        cv.drawPoints(skia.Canvas.kPoints_PointMode, _LIGHTS, pp)
        cv.drawCircle(1.5, 0.5, 15, paint(pal['light'], 0.14 * lights, blur=6, blend=PLUS))
    # the new town by the sea: a round lake and the ring roads around it
    lx, ly = LG
    for k, rr in enumerate((2.05, 2.85, 3.7, 4.7)):
        g = 0.0
        if rings_glow > 0:
            g = math.exp(-((rings_glow * 6 - k - 1) ** 2) * 1.2)
        cv.drawCircle(lx, ly, rr, paint(mix(pal['ring'], '#ffffff', g), 0.50 + 0.5 * g, stroke=max(0.10 + 0.1 * g, 1.6 * px)))
    for k in range(8):
        a = TAU * k / 8 + 0.2
        cv.drawLine(lx + 1.5 * math.cos(a), ly + 1.5 * math.sin(a), lx + 4.7 * math.cos(a), ly + 4.7 * math.sin(a), paint(pal['ring'], 0.30, stroke=max(0.07, 1.2 * px)))
    cv.restore()
    cv.drawCircle(lx, ly, LAKE_R, paint('#ffffff', 1, shader=radial(lx - 0.4, ly - 0.5, 2.0, [(0, mix(pal['sea1'], '#ffffff', 0.25), 1), (1, pal['sea1'], 1)])))
    cv.drawCircle(lx, ly, LAKE_R, paint(pal['land_e'], 0.9, stroke=max(0.05, 1.8 * px)))
    cv.restore()
    cv.restore()


def whale(cv, x, y, L, heading, t, alpha=1.0, night=True):
    """a whale from above; L = length in px, heading in radians (0 = swimming to the right)"""
    f = score.flow(t)
    sw = math.sin(f * 1.5)
    cv.saveLayer(None, paint('#ffffff', alpha))
    cv.save()
    cv.translate(x, y)
    cv.rotate(math.degrees(heading))
    s = L / 200.0
    cv.scale(s, s)
    body = skia.Path()
    body.moveTo(100, 0)
    body.cubicTo(96, -30, 40, -36, -10, -26)
    body.cubicTo(-50, -18, -78, -9 + sw * 3, -92, -4 + sw * 7)
    body.cubicTo(-108, -30 + sw * 10, -128, -34 + sw * 12, -138, -26 + sw * 12)
    body.cubicTo(-126, -10 + sw * 10, -118, 0 + sw * 9, -116, 0 + sw * 9)
    body.cubicTo(-118, 2 + sw * 9, -126, 12 + sw * 10, -138, 28 + sw * 12)
    body.cubicTo(-128, 36 + sw * 12, -108, 30 + sw * 10, -92, 6 + sw * 7)
    body.cubicTo(-78, 10 + sw * 3, -50, 18, -10, 26)
    body.cubicTo(40, 36, 96, 30, 100, 0)
    body.close()
    fin = skia.Path()
    for sgn in (-1, 1):
        fin.moveTo(36, sgn * 28)
        fin.cubicTo(20, sgn * (56 + 4 * sw), -8, sgn * (64 + 6 * sw), -20, sgn * (60 + 6 * sw))
        fin.cubicTo(-6, sgn * 44, 4, sgn * 34, 12, sgn * 28)
        fin.close()
    c0, c1 = ('#2c5aa8', '#6fa0ea') if night else ('#3b6fc4', '#8db5f0')
    cv.drawPath(body, paint('#bfe0ff', 0.35, stroke=26, blur=16, blend=PLUS if night else None))
    cv.drawPath(fin, paint(c0, 1))
    cv.drawPath(body, paint('#ffffff', 1, shader=linear((0, -36), (0, 36), [(0, c1, 1), (0.5, c0, 1), (1, c1, 1)])))
    cv.drawLine(-70, 0, 78, 0, paint('#ffffff', 0.18, stroke=3))
    cv.drawCircle(62, 0, 5, paint('#0a1a3a', 0.8))
    cv.restore()
    cv.restore()


def mini_disc(cv, x, y, r, t, st, rot=0.0, a=1.0):
    cv.drawCircle(x + r * 0.06, y + r * 0.12, r, paint('#1b2a5c', 0.28 * a, blur=r * 0.12))
    cv.drawCircle(x, y, r, paint('#ffffff', a, shader=radial(x, y, r, [(0, '#7fb0ff', 1), (0.55, '#3672f4', 1), (1, '#1f4bcc', 1)])))
    for k in range(4):
        cv.drawCircle(x, y, r * (0.42 + 0.14 * k), paint('#ffffff', 0.28 * a, stroke=max(0.8, r * 0.012)))
    sw = skia.GradientShader.MakeSweep(x, y, [skia.Color4f(1, 1, 1, 0), skia.Color4f(1, 1, 1, 0.4), skia.Color4f(1, 1, 1, 0), skia.Color4f(1, 1, 1, 0),
                                              skia.Color4f(1, 1, 1, 0.3), skia.Color4f(1, 1, 1, 0), skia.Color4f(1, 1, 1, 0)], [0, 0.07, 0.14, 0.5, 0.57, 0.64, 1.0])
    cv.drawCircle(x, y, r, paint('#ffffff', a, shader=sw))
    cv.drawCircle(x, y, r * 0.30, paint('#fff8ea', a))
    cv.drawCircle(x + r * 0.13 * math.cos(rot), y + r * 0.13 * math.sin(rot), r * 0.055, paint('#4f7fe8', a))
    cv.drawCircle(x - r * 0.13 * math.cos(rot), y - r * 0.13 * math.sin(rot), r * 0.055, paint('#ea4a5f', a))
    cv.drawCircle(x, y, r * 0.035, paint('#ffffff', a))
    cv.drawCircle(x, y, r, paint('#dbe8ff', 0.9 * a, stroke=max(1.0, r * 0.02)))


def free_line(cv, line, t, st, cx, cy, rho, fade=1.0):
    """a sung line that is not cut into a record: it rides a ripple outwards and fades"""
    tmp = dict(line)
    tmp.update(disc='A', slot=1, rel=1e9)
    cam = D.Cam((rho - D.ARC_GAP) / D.R, cx, cy)
    D.draw_line(cv, cam, tmp, t, st, fade)


# ---- bridge and the spoken exchange -------------------------------------------------------------------------
def map_cam(t):
    u = smoother((t - 110.25) / 3.5)
    v = smoother((t - (T_CH3 - 1.75)) / 1.75)
    s = 10.0 * (10.0 ** u) * lerp(1.0, 1.06, clamp((t - 113.75) / 8)) * (3.85 / 1.06) ** v
    kx = lerp(lerp(WJC[0], ARRIVE[0], u), LG[0], v)
    ky = lerp(lerp(WJC[1], ARRIVE[1], u), LG[1], v)
    return MapCam(s, kx, ky, 540.0, lerp(lerp(850.0, 960.0, u), 850.0, v))


def bridge(cv, t):
    st_w = S.STYLES['water']
    w = ramp(t, T_BR - 0.5, score.DROP_T + 0.2)
    st = S.blend(S.STYLES['obj'], st_w, w)
    cam = D.Cam(0.78 * (1 + 0.010 * score.pulse(t, 4, 3.0) * (1 - ramp(t, T_BR - 1.2, T_BR))), 540, 850)
    cx, cy = 540, 850
    phase_b = t >= 109.6
    mc = map_cam(t)
    if not phase_b:
        S.deck(cv, t, {'cam': cam}, 'A')
        if w > 0:
            cv.drawPaint(paint('#ffffff', w, shader=radial(cx, cy, 1300, [(0, '#0e2f66', 1), (0.6, '#0a2150', 1), (1, '#05112b', 1)])))
        ma = ramp(t, T_RINGS + 0.1, T_RINGS + 1.6)
        if ma > 0:
            draw_map(cv, mc, NIGHT, t, alpha=ma)
    else:
        arrive = ramp(t, 113.3, 114.4)
        draw_map(cv, mc, NIGHT, t, rings_glow=bump(t, 113.2, 114.6, 114.6, 114.61) if t < 114.6 else 0.0)
    # ripples that leave the first circle and cross the city
    wx, wy = mc.pt(*WJC)
    if t > T_RINGS:
        hb = (score.rec(t) - score.bp(T_RINGS)) / 2.0
        for k in range(int(hb) + 1):
            age = (hb - k) * 2 * 0.535
            if age < 0 or age > 7.5 or k > 9:
                continue
            rr = (4 + 15.0 * age) * mc.s
            if rr > 4000:
                continue
            al = 0.55 * math.exp(-age * 0.20) * (1 - ramp(t, 114.2, 115.8))
            cv.drawCircle(wx, wy, rr, paint('#bfe6ff', al, stroke=2.4))
            cv.drawCircle(wx, wy, rr, paint('#7fc4ff', al * 0.35, stroke=14, blur=9, blend=PLUS))
        cv.drawCircle(wx, wy, max(3.0, 0.9 * mc.s), paint('#ffe1ad', 0.9 * ramp(t, T_RINGS + 0.6, T_RINGS + 1.4), stroke=2.0))
    if not phase_b:
        # the record: its glass thins away once the rings are let go
        ga = 1 - ramp(t, T_RINGS, T_RINGS + 1.2)
        if ga > 0:
            cv.saveLayer(None, paint('#ffffff', ga))
            D.body(cv, cam, 1.0, st, 20, t)
            la = 1 - ramp(t, score.DROP_T, score.DROP_T + 0.9)
            if la > 0:
                S.label(cv, cam, t, 'A', kid=1.0, alpha=la)
            D.spindle(cv, cam, st)
            cv.restore()
        # the twenty rings: outermost first, each one runs outwards with its line of words
        for l in score.SUNG:
            if l['disc'] != 'A':
                continue
            tk = T_RINGS + (20 - l['slot']) * 0.085
            e = 1.0 if t < tk else math.exp(1.15 * (t - tk))
            if e > 4.0:
                continue
            wob = 1 + 0.012 * math.sin((t - score.DROP_T) * 14 - l['slot'] * 0.7) * math.exp(-max(0, t - score.DROP_T) * 1.6) * (t > score.DROP_T)
            D.draw_line(cv, D.Cam(0.78 * e * wob, cx, cy), l, t, st, fade=1 - ramp(e, 1.5, 3.6), show_arc=False)
        # tonearm leaves
        ta = 1 - ramp(t, T_BR - 0.9, T_BR - 0.1)
        if ta > 0:
            D.tonearm(cv, cam, lerp(D.ring_r(21), D.R + 60, ramp(t, T_BR - 1.0, T_BR - 0.2)), ramp(t, T_BR - 1.2, T_BR - 0.8), st, ta)
        # the drop
        u = (t - (T_BR - 0.1)) / (score.DROP_T - (T_BR - 0.1))
        if 0 < u < 1:
            r = lerp(70, 13, ease_in(u, 2))
            cv.drawCircle(cx + 6, cy + 10, r * 1.15, paint('#020a20', 0.35 * u, blur=lerp(26, 4, u)))
            cv.drawCircle(cx, cy, r, paint('#ffffff', 1, shader=radial(cx - r * 0.3, cy - r * 0.35, r * 1.3, [(0, '#ffffff', 0.95), (0.5, '#bfe6ff', 0.85 * u + 0.1), (1, '#5fa8ff', 0.6 * u)]),
                                           blur=lerp(14, 0.5, u)))
        for k in range(4):
            age = t - score.DROP_T - k * 0.16
            if 0 < age < 2.2:
                cv.drawCircle(cx, cy, 14 + 380 * (1 - math.exp(-age * 1.6)), paint('#eaf6ff', 0.9 * math.exp(-age * 1.7), stroke=3.2 - k * 0.5))
        if 0 < t - score.DROP_T < 0.5:
            cv.drawCircle(cx, cy, 60 * (t - score.DROP_T) / 0.5 + 12, paint('#ffffff', 0.8 * (1 - (t - score.DROP_T) / 0.5), blur=8, blend=PLUS))
    # the sea by the lake: the whale, and the two of them on the sea wall
    if t > 111.5:
        wa = ramp(t, 112.6, 113.6) * (1 - ramp(t, T_CH3 - 1.4, T_CH3 - 0.7))
        f = score.flow(t)
        hx, hy = 49.25 + 0.25 * math.sin(f * 0.21), 39.9 - 0.36 * (f - score.flow(113.0)) * 0.55
        X, Y = mc.pt(hx, hy)
        if wa > 0:
            sp = (score.rec(t) / 4.0) % 1.0                    # it breathes once a bar: one more ring on the water
            cv.drawCircle(X, Y - 0.72 * mc.s, (0.25 + 1.3 * sp) * mc.s, paint('#eaf6ff', 0.6 * (1 - sp) * wa, stroke=2.2))
            whale(cv, X, Y, 2.15 * mc.s, -math.pi / 2 + 0.10 * math.sin(f * 0.5), t, wa)
        pa = ramp(t, 114.0, 115.0) * (1 - ramp(t, T_CH3 - 1.6, T_CH3 - 1.0))
        if pa > 0:
            px, py = mc.pt(46.55, 38.25)
            cv.saveLayer(None, paint('#ffffff', pa))
            S.person(cv, px, py - 26, 'she', (1, 0.1), 1.25, glow=('#ff8da3', 46, 0.30))
            S.person(cv, px - 4, py + 26, 'he', (1, 0.1), 1.25, glow=('#7faaff', 46, 0.30))
            cv.restore()
    # what is sung over the water is not cut: it rides out on a ripple
    for i, hold, end in ((21, 109.15, 110.0), (22, 114.0, 114.9)):
        l = score.LINES[i]
        if l['t0'] - 0.5 < t < end:
            d = ease_in(clamp((t - hold) / (end - hold)), 2)
            free_line(cv, l, t, st_w, cx, cy, 584 + 150 * d, fade=1 - d)
    # what is said is written small beside them
    for i, y, c in ((23, 1420, '#ffd9e0'), (24, 1535, '#cfe2ff')):
        l = score.LINES[i]
        fade = 1 - ramp(t, T_CH3 - 0.85, T_CH3 - 0.35)
        D.said(cv, l, t, 540, y, st_w, size=72, hold=20.0, fade=fade, c=c)
    # "no hurry --": the dash of the last spoken line is the first stroke of the next record's rim
    l = score.LINES[24]
    td = l['t'][-1] + 0.3
    if t > td:
        u = smooth((t - td) / (T_CH3 - 0.35 - td))
        lx, ly = mc.pt(*LG)
        rr = LAKE_R * mc.s
        p = skia.Path()
        p.addArc(skia.Rect.MakeLTRB(lx - rr, ly - rr, lx + rr, ly + rr), -90, 360 * u)
        cv.drawPath(p, paint('#ffffff', 0.95, stroke=3.2))
        cv.drawPath(p, paint('#bfe6ff', 0.5, stroke=16, blur=10, blend=PLUS))
    return st if not phase_b else st_w


# ---- final chorus: the next record --------------------------------------------------------------------------
T_NEEDLE = score.LINES[28]['t'][4] + 0.06       # "the needle comes down": it lands on the last syllable of that phrase


def final(cv, t):
    st = S.STYLES['objB']
    cam = D.Cam(0.78 * (1 + 0.010 * score.pulse(t, 4, 3.0) * (t < score.SIL2[0])), 540, 850)
    cx, cy = cam.pt(0, 0)
    S.deck(cv, t, {'cam': cam}, 'B')
    # the first record, full, put aside
    mini_disc(cv, 1010, 1845, 255, t, st, rot=0.6)
    for k in range(20):
        cv.drawCircle(1010, 1845, 255 * (D.ring_r(k + 1) / D.R), paint('#ffffff', 0.22, stroke=1.0))
    cut = score.rings_done(t, 'B')
    D.body(cv, cam, 1.0, st, cut, t, 'B')
    # twenty rings still to come
    l27 = score.LINES[27]
    t20 = l27['t'][8]
    if t > t20:
        for k in range(20):
            tk = t20 + k * 0.045
            if t > tk:
                a = 0.42 * math.exp(-(t - tk) * 0.9) + 0.07
                cv.drawCircle(cx, cy, D.ring_r(k + 1) * cam.z, paint('#ffffff', a * (1 - ramp(t, 141.0, 141.6) * 0), stroke=1.6))
    S.label(cv, cam, t, 'B')
    D.spindle(cv, cam, st)
    D.quan_rings(cv, cam, t, st, 'B')
    D.draw_lines(cv, cam, t, st, 'B')
    # the needle
    down = ramp(t, T_NEEDLE - 0.45, T_NEEDLE)
    swing = ramp(t, T_NEEDLE - 1.5, T_NEEDLE - 0.35)
    up = ramp(t, score.SIL2[0], score.SIL2[0] + 0.5)
    away = ramp(t, score.SIL2[0] + 0.35, score.SIL2[1])
    rs = lerp(D.R + 62, D.ring_r(min(4.6, cut + 1)), swing)
    rs = lerp(rs, D.R + 62, away)
    D.tonearm(cv, cam, rs, max(1 - down, up), st)
    age = t - T_NEEDLE
    if 0 < age < 1.6:
        sx, sy = D.stylus_at(rs)
        X, Y = cam.pt(sx, sy)
        for k in range(3):
            a2 = age - k * 0.13
            if a2 > 0:
                cv.drawCircle(X, Y, 8 + 200 * (1 - math.exp(-a2 * 2.2)), paint('#ffffff', 0.9 * math.exp(-a2 * 2.4), stroke=3.0))
        cv.drawCircle(X, Y, 30, paint('#fff0c8', 0.8 * math.exp(-age * 4), blur=12, blend=PLUS))
    D.counter(cv, t, st)
    # the goodbye is spoken, so it is written, not cut
    l = score.LINES[29]
    if t > l['t0'] - 0.2:
        again = math.exp(-max(0.0, t - score.EXTRA_SAY[0]) * 5.0) * (t >= score.EXTRA_SAY[0])
        cv.save()
        cv.translate(540, 1560)
        cv.scale(1 + 0.05 * again, 1 + 0.05 * again)
        D.said(cv, l, t, 0, 0, st, size=96, hold=20.0)
        cv.restore()
    return st


# ---- after the goodbye: the five places, each a record still turning ---------------------------------------
def outro(cv, t):
    t0 = score.SIL2[1]
    st = S.STYLES['dawn']
    mc = MapCam(lerp(10.2, 10.9, smooth(clamp((t - t0) / 16))), 8.0, 6.0, 540, 1085)
    draw_map(cv, mc, DAY, t, lights=0.5)
    f = score.flow(t)
    b = score.rec(t) - score.bp(t0)
    # the road between them, in the order the song visits them
    pts = [mc.pt(*c) for c, _ in PLACE]
    prog = clamp((t - t0 - 0.3) / 7.2) * 4
    for k in range(4):
        u = clamp(prog - k)
        if u <= 0:
            continue
        (x0, y0), (x1, y1) = pts[k], pts[k + 1]
        mx, my = (x0 + x1) / 2 - (y1 - y0) * 0.18, (y0 + y1) / 2 + (x1 - x0) * 0.18
        p = skia.Path()
        p.moveTo(x0, y0)
        p.quadTo(mx, my, x1, y1)
        pm = skia.PathMeasure(p, False)
        seg = skia.Path()
        pm.getSegment(0, pm.getLength() * smooth(u), seg, True)
        pp = paint('#f2643d', 0.9, stroke=4.0)
        pp.setPathEffect(skia.DashPathEffect.Make([2, 13], 0))
        cv.drawPath(seg, pp)
    wh = mc.pt(53.5, 30.0 - 0.8 * (t - t0) * 0.5)
    whale(cv, wh[0], wh[1], 70, -math.pi / 2 + 0.1 * math.sin(f), t, 0.9, night=False)
    for k, ((c, name), (x, y)) in enumerate(zip(PLACE, pts)):
        ta = t0 + 0.15 + k * 1.8 if k else t0
        a = ease_out(clamp((t - ta) / 0.5))
        if a <= 0:
            continue
        pu = score.pulse(t, 2, 4.0)
        for j in range(2):
            u = ((b / 4.0) - j / 2.0 - k * 0.13) % 1.0
            cv.drawCircle(x, y, 48 + 110 * u, paint('#3b7bf2', 0.42 * (1 - u) * a, stroke=2.0))
        r = 46 * back_out(a) * (1 + 0.05 * pu)
        mini_disc(cv, x, y, r, t, st, rot=TAU * b / 8.0 + k, a=a)
        right = k in (1, 4)
        below = k in (0,)
        lx2, ly2, al = x, y - 76, 'c'
        if k == 4:
            lx2, ly2, al = x - 4, y + 80, 'c'
        if k == 3:
            lx2, ly2, al = x + 40, y - 74, 'c'
        text(cv, name, lx2, ly2, SERIF_B, 36, paint('#ffffff', 0.95 * a, blur=6), align=al, track=0.10)
        text(cv, name, lx2, ly2, SERIF_B, 36, paint('#ffffff', 0.95 * a, blur=6), align=al, track=0.10)
        text(cv, name, lx2, ly2, SERIF_B, 36, paint('#17306e', a), align=al, track=0.10)
    for (kx, ky, nm, rot) in ((51.0, 10.0, '东海', 0), (-22.0, -40.5, '长江口', -32), (-13.0, 58.5, '杭州湾', 14), (-33.0, 28.6, '黄浦江', 0)):
        X, Y = mc.pt(kx, ky)
        cv.save()
        cv.translate(X, Y)
        cv.rotate(rot)
        text(cv, nm, 0, 0, KAI, 30 if nm != '黄浦江' else 24, paint('#5f8fd0', 0.85 * ramp(t, t0 + 1.0, t0 + 2.0)), track=0.4)
        cv.restore()
    # title
    a = ramp(t, t0 + 0.4, t0 + 1.4)
    for k, ch in enumerate('兜一圈'):
        u = ease_out(clamp((t - (t0 + 0.4 + k * 0.27)) / 0.7))
        glyph(cv, ch, 540 + (k - 1) * 200, 300 + 26 * (1 - u), SERIF_K, 168, paint('#ffffff', 0.9 * u, blur=12))
        glyph(cv, ch, 540 + (k - 1) * 200, 300 + 26 * (1 - u), SERIF_K, 168, paint('#17306e', u))
    a2 = ramp(t, t0 + 1.6, t0 + 2.4)
    text(cv, '万达入沪二十载', 540, 444, SERIF_M, 44, paint('#17306e', a2), track=0.42)
    # one year on every beat, from 2006 up to 2026
    n = int(clamp(math.floor(b - 2.0), 0, 20))
    frac = (b - 2.0) - math.floor(b - 2.0) if 0 < b - 2.0 < 20.0 else 1.0
    pop = math.exp(-frac * 5.0) if 0 < n <= 20 and b - 2.0 < 21 else 0.0
    done = math.exp(-max(0.0, b - 22.0) * 0.5) if b >= 22.0 else 0.0
    text(cv, '2006', 540 - 52, 512, PLAY_I, 44, paint('#3b7bf2', a2), align='r', track=0.06)
    text(cv, '—', 540, 510, PLAY_I, 40, paint('#3b7bf2', a2 * 0.8))
    cv.save()
    cv.translate(540 + 52, 512)
    cv.scale(1 + 0.16 * pop, 1 + 0.16 * pop)
    text(cv, str(2006 + n), 0, -10 * pop, PLAY_I, 44, paint(mix('#3b7bf2', '#f2643d', max(pop, done)), a2), align='l', track=0.06)
    cv.restore()
    if b >= 22.0:
        for (x, y) in pts:
            u = clamp((b - 22.0) / 4.0)
            cv.drawCircle(x, y, 50 + 420 * ease_out(u), paint('#f2643d', 0.6 * (1 - u), stroke=3.0))
    return st


def tail(cv, t):
    """the band's last hit, then two soft thumps: one for each of them"""
    st = dict(S.STYLES['dawn'])
    t0 = score.BAND_OUT
    wash = ramp(t, t0 - 0.05, t0 + 1.2)
    outro(cv, t)
    cv.drawPaint(paint('#ffffff', wash, shader=linear((0, 0), (0, H), [(0, '#f6f9fd', 1), (1, '#e3eefa', 1)])))
    cx, cy = 540, 900
    th1, th2 = score.THUMPS
    for k, (tk, who, dx) in enumerate(((th1, 'he', -36), (th2, 'she', 36))):
        age = t - tk
        if age <= 0:
            continue
        a = back_out(clamp(age / 0.35))
        cv.drawCircle(cx + dx, cy, 30 + 520 * (1 - math.exp(-age * 1.3)), paint('#4f7fe8' if who == 'he' else '#ea4a5f', 0.55 * math.exp(-age * 1.5), stroke=2.6))
        cv.save()
        cv.translate(cx + dx, cy)
        cv.scale(2.3 * a, 2.3 * a)
        S.person(cv, 0, 0, who, (0, -1), 1.0, sh=(0.3, 0.95, 26, 0.16))
        cv.restore()
    u = smooth((t - (th2 + 0.25)) / 1.5)
    if u > 0:
        p = skia.Path()
        p.addArc(skia.Rect.MakeLTRB(cx - 150, cy - 150, cx + 150, cy + 150), -90, 360 * u)
        cv.drawPath(p, paint('#17306e', 0.9, stroke=3.0))
    a3 = ramp(t, th2 + 1.2, th2 + 2.0)
    text(cv, '明朝会', 540, cy + 250, KAI, 60, paint('#17306e', 0.9 * a3), track=0.3)
    # the crackle of the run-out groove
    dust = 1 - ramp(t, 165.2, 166.4)
    for (x, y, r, ph) in _DUST:
        if (math.sin(t * 23.0 + ph * 80) > 0.93):
            cv.drawCircle(x, y, r, paint('#17306e', 0.35 * dust))
    cv.drawPaint(paint('#f3f7fc', ramp(t, 166.2, score.DUR - 0.05)))
    st['grain'] = 0.05
    return st


def late_part(cv, t, main_part):
    if t < T_CH3 - 0.9:
        return bridge(cv, t)
    if t < T_CH3:
        u = smooth((t - (T_CH3 - 0.9)) / 0.9)
        bridge(cv, t)
        cv.saveLayer(None, paint('#ffffff', u))
        st = final(cv, t)
        cv.restore()
        return S.blend(S.STYLES['water'], st, u)
    if t < score.SIL2[1]:
        return final(cv, t)
    if t < score.BAND_OUT:
        st = outro(cv, t)
        fl = 1 - ramp(t, score.SIL2[1], score.SIL2[1] + 0.5)
        if fl > 0:
            cv.drawPaint(paint('#ffffff', 0.85 * fl))
        return st
    return tail(cv, t)
