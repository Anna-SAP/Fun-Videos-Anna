#!/usr/bin/env python3
"""The record, its rings of lyrics, the line being sung on the arc below it, and the tonearm.

Rule of the film: a sung line appears character by character, in time with the voice, on an arc just outside the
record's lower edge. On the next phrase downbeat it is cut into the record: it shrinks onto its own ring and turns
with the record from then on. The record turns once per line, so every line is one ring. Lines go from the outer
edge inwards, like a record being cut. Spoken lines are never cut.
"""
import math

import skia

import score
from kit import (KAI, PLAY_I, PLUS, SANS_M, SERIF_B, SERIF_K, SERIF_M, TAU, back_out, clamp, col, ease_out, font, glyph, lerp, linear, mix,
                 paint, polar, radial, ramp, smooth, smoother, sweep, text, text_w)

R = 640.0            # record radius, world units
R_IN = 207.0         # radius of ring 1; rings grow outwards like the rings of a tree
PITCH = 21.0         # distance between rings
RL = 176.0           # label radius
N_A = 20
ARC_GAP = 84.0       # px between the record's edge and the centre line of the sung line
SMAX = 86.0          # px, largest character on the arc
ADV = 1.07           # advance per character in em
GAP = 0.5            # extra advance at a phrase break
PIVOT = (608.0, -672.0)
ARM = 772.0


class Cam:
    def __init__(self, z=1.0, cx=540.0, cy=850.0):
        self.z, self.cx, self.cy = z, cx, cy

    def pt(self, x, y):
        return self.cx + self.z * x, self.cy + self.z * y

    def apply(self, cv, rot=0.0):
        cv.translate(self.cx, self.cy)
        cv.scale(self.z, self.z)
        if rot:
            cv.rotate(math.degrees(rot))


def ring_r(slot):
    return R_IN + PITCH * (slot - 1)


def layout(line):
    """em offsets of the characters of a line, centred on 0, and the total width in em"""
    xs, x = [], 0.0
    for c in line['chars']:
        xs.append(x + 0.5)
        x += ADV + (GAP if c['gap'] else 0.0)
    wid = x - (ADV - 1.0) - (GAP if line['chars'][-1]['gap'] else 0.0)
    return [v - wid / 2 for v in xs], wid


def arc_size(line, rho):
    xs, wid = layout(line)
    lmax = rho * min(1.72, 2 * math.asin(min(0.99, 472.0 / rho)))
    return min(SMAX, lmax / wid)


# ---- the record's body ------------------------------------------------------------------------------------
def body(cv, cam, obj, st, rings_cut, t, disc='A', sheen_rot=0.0):
    """glass of the record. obj 0 = we are inside the memory, the record is only a rim of light;
    obj 1 = the record is an object on the turntable."""
    cx, cy = cam.pt(0, 0)
    r = R * cam.z
    if obj > 0.01:
        # contact shadow
        cv.drawCircle(cx + 10 * cam.z, cy + 22 * cam.z, r * 1.005, paint(st['shadow'], 0.30 * obj, blur=26 * cam.z))
        cv.save()
        ring = skia.Path()
        ring.addCircle(cx, cy, r)
        hole = skia.Path()
        hole.addCircle(cx, cy, RL * cam.z)
        cv.clipPath(ring, True)
        cv.clipPath(hole, skia.ClipOp.kDifference, True)
        g = radial(cx, cy, r, [(0.0, st['glass_in'], 1), (0.27, st['glass_in'], 1), (0.62, st['glass_mid'], 1), (1.0, st['glass_out'], 1)])
        cv.drawCircle(cx, cy, r, paint('#000000', st['glass_a'] * obj, shader=g))
        # fine grooves where the record has been cut
        if rings_cut > 0:
            r_out = ring_r(rings_cut + 0.5) * cam.z
            pg = paint(st['groove'], st.get('groove_a', 0.10) * obj, stroke=max(0.6, 0.9 * cam.z))
            rr = (R_IN - PITCH * 0.5) * cam.z
            step = PITCH / 3 * cam.z
            while rr < r_out:
                cv.drawCircle(cx, cy, rr, pg)
                rr += step
        # the fixed sheen of light on vinyl: two bright and two dark wedges
        hi = st['sheen']
        sw = sweep(cx, cy, [(0.0, hi, 0.0), (0.07, hi, 0.34), (0.14, hi, 0.0), (0.36, '#000000', 0.0), (0.43, '#06102e', 0.16), (0.50, '#000000', 0.0),
                            (0.57, hi, 0.24), (0.64, hi, 0.0), (0.86, '#000000', 0.0), (0.93, '#06102e', 0.14), (1.0, hi, 0.0)], rot=-62 + 2.5 * math.sin(t * 0.7) + sheen_rot)
        cv.drawCircle(cx, cy, r, paint('#ffffff', obj * st.get('sheen_a', 1.0), shader=sw))
        cv.restore()
        # rim
        cv.drawCircle(cx, cy, r - 2.5 * cam.z, paint(st['rim'], 0.85 * obj, stroke=3.0 * cam.z))
        cv.drawCircle(cx, cy, r - 9 * cam.z, paint('#ffffff', 0.20 * obj, stroke=1.2 * cam.z))
        cv.drawCircle(cx, cy, RL * cam.z, paint(st['rim'], 0.9 * obj, stroke=2.4 * cam.z))
        cv.drawCircle(cx, cy, (RL + 9) * cam.z, paint('#ffffff', 0.22 * obj, stroke=1.2 * cam.z))
    if obj < 0.99:
        a = 1 - obj
        cv.drawCircle(cx, cy, r, paint(st['clear_rim'], 0.55 * a, stroke=2.2))
        cv.drawCircle(cx, cy, r - 7, paint(st['clear_rim'], 0.16 * a, stroke=5.0, blur=3))
        # a moving glint on the rim
        sw = sweep(cx, cy, [(0.0, '#ffffff', 0), (0.04, '#ffffff', 0.9), (0.08, '#ffffff', 0), (0.5, '#ffffff', 0), (0.53, '#ffffff', 0.5), (0.56, '#ffffff', 0),
                            (1.0, '#ffffff', 0)], rot=-140 + 6 * t)
        cv.drawCircle(cx, cy, r - 1, paint('#ffffff', 0.9 * a, stroke=3.0, shader=sw))


def spindle(cv, cam, st):
    cx, cy = cam.pt(0, 0)
    cv.drawCircle(cx, cy, 15 * cam.z, paint(st['spindle'], 0.95))
    cv.drawCircle(cx, cy, 15 * cam.z, paint('#8090b0', 0.5, stroke=1.2))
    cv.drawCircle(cx - 4 * cam.z, cy - 4 * cam.z, 4.5 * cam.z, paint('#ffffff', 0.55, blur=1.5))


# ---- one line: on the arc, being cut, or as a ring --------------------------------------------------------
def line_state(line, t):
    """g: 0 on the arc .. 1 cut into its ring; ang: rotation of the line's centre away from straight down"""
    rel = line['rel']
    g = smoother((t - (rel - 0.38)) / 0.68)
    d = line['disc']
    if d == 'A' and score.RIDE[0] <= t < score.RIDE[1]:
        return g, 0.0                       # the camera is riding on the record: nothing on it turns
    if d == 'A' and (abs(rel - score.RIDE[0]) < 0.01 or abs(rel - score.RIDE[1]) < 0.01):
        return g, max(0.0, score.theta(t, d) - score.theta(rel, d))
    if t <= rel - 0.3:
        ang = 0.0
    elif t >= rel + 0.3:
        ang = score.theta(t, d) - score.theta(rel, d)
    else:
        om = (score.theta(rel + 0.3, d) - score.theta(rel - 0.3, d)) / 0.6
        u = (t - rel + 0.3) / 0.6
        ang = om * 0.6 * (u ** 3 - u ** 4 / 2)
    return g, ang


def draw_line(cv, cam, line, t, st, fade=1.0, show_arc=True):
    """draw a sung line in whatever state it is in at time t"""
    if t < line['t0'] - 0.5:
        return
    g, ang = line_state(line, t)
    if g <= 0 and not show_arc:
        return
    cx, cy = cam.pt(0, 0)
    rho_arc = R * cam.z + ARC_GAP
    rho_ring = ring_r(line['slot']) * cam.z
    xs, wid = layout(line)
    s_arc = arc_size(line, rho_arc)
    s_ring = PITCH * 0.80 * cam.z
    rho = lerp(rho_arc, rho_ring, g)
    size = lerp(s_arc, s_ring, g ** 0.8)
    ink = mix(st['ink'], st['ring_ink'], g)
    a_txt = lerp(1.0, st['ring_a'], g) * fade
    name = SERIF_K if g < 0.5 else SERIF_B
    n = len(xs)
    # the groove that the line sits on once it is cut
    if g > 0.02:
        half = wid * size / rho / 2 + 0.6 * size / rho
        span = TAU - 2 * half
        ext = span * smooth(g * 1.15)
        if ext > 0.01:
            p = skia.Path()
            a0 = math.degrees(ang + half) + 90          # skia: 0 deg = +x, clockwise; our angle is from +y towards -x
            p.addArc(skia.Rect.MakeLTRB(cx - rho, cy - rho, cx + rho, cy + rho), a0, math.degrees(ext))
            cv.drawPath(p, paint(st['ring_ink'], st['ring_line_a'] * g * fade, stroke=max(0.9, 1.3 * cam.z)))
    # underline that grows with the singing, and the spark at its head (arc state only)
    if g < 0.98 and show_arc:
        tt = line['t']
        halo = st.get('halo')
        if halo and t >= tt[0] - 0.1:       # a soft bed under the words so they read over any floor
            vis = ramp(t, tt[0] - 0.1, tt[0] + 0.5) * (1 - g)
            a1 = ang - (xs[0] - 0.9) * size / rho
            a2 = ang - (lerp(xs[0], xs[-1], ramp(t, tt[0], tt[-1])) + 0.9) * size / rho
            p = skia.Path()
            p.addArc(skia.Rect.MakeLTRB(cx - rho, cy - rho, cx + rho, cy + rho), math.degrees(a2) + 90, math.degrees(a1 - a2))
            cv.drawPath(p, paint(halo[0], 0.36 * halo[1] * vis * fade, stroke=size * 1.5, blur=26, cap=skia.Paint.kButt_Cap))
        if t >= tt[0] - 0.25:
            if t >= tt[-1]:
                e = xs[-1] + 0.55 + 0.25 * ease_out((t - tt[-1]) / 0.5)
            elif t < tt[0]:
                e = xs[0] - 0.6
            else:
                k = max(i for i in range(n) if tt[i] <= t)
                nxt = tt[k + 1] if k + 1 < n else tt[k] + 0.4
                nx = xs[k + 1] if k + 1 < n else xs[k] + 0.6
                e = lerp(xs[k], nx, smooth((t - tt[k]) / max(0.05, nxt - tt[k])))
            a_left = ang - (xs[0] - 0.62) * size / rho
            a_now = ang - e * size / rho
            ru = rho + 0.68 * size * (1 - g)
            if a_left > a_now:
                p = skia.Path()
                p.addArc(skia.Rect.MakeLTRB(cx - ru, cy - ru, cx + ru, cy + ru), math.degrees(a_now) + 90, math.degrees(a_left - a_now))
                cv.drawPath(p, paint(st['ink'], 0.55 * (1 - g) * fade, stroke=2.2))
            sing = ramp(t, tt[0] - 0.25, tt[0]) * (1 - ramp(t, tt[-1] + 0.25, tt[-1] + 0.7))
            if sing > 0.01:
                sx, sy = polar(ru, a_now)
                cv.drawCircle(cx + sx, cy + sy, 16, paint(st['hot'], 0.55 * sing * fade, blur=9, blend=st.get('spark_blend')))
                cv.drawCircle(cx + sx, cy + sy, 4.6, paint(st['spark'], sing * fade))
    # characters
    halo = st.get('halo')
    for k, c in enumerate(line['chars']):
        tk = line['t'][k]
        p = clamp((t - tk + 0.07) / 0.17)
        if p <= 0:
            continue
        a = ang - xs[k] * size / rho
        pop = (1 - g) * (1 - ease_out(p))
        x, y = polar(rho + 16 * pop, a)
        hot = math.exp(-max(0.0, t - tk) / 0.42) * (1 - g)
        rot = math.degrees(a)
        sc = 1 + 0.32 * pop
        if halo and g < 0.9:
            glyph(cv, c['c'], cx + x, cy + y, name, size, paint(halo[0], halo[1] * p * (1 - g) * fade, blur=halo[2]), rot, sc)
        glyph(cv, c['c'], cx + x, cy + y, name, size, paint(mix(ink, st['hot'], hot), a_txt * p), rot, sc)


def draw_lines(cv, cam, t, st, disc='A', fade=1.0, show_arc=True):
    for l in score.SUNG:
        if l['disc'] == disc:
            draw_line(cv, cam, l, t, st, fade, show_arc)


def quan_rings(cv, cam, t, st, disc='A', fade=1.0):
    """every time the word for 'a round' is sung, one ring leaves the rim of the record"""
    cx, cy = cam.pt(0, 0)
    for l in score.SUNG:
        if l['disc'] != disc or t < l['t0'] or t > l['t1'] + 2.0:
            continue
        for k, c in enumerate(l['chars']):
            age = t - l['t'][k]
            if c['c'] == '圈' and 0 < age < 1.8:
                rr = R * cam.z + 8 + 250 * (1 - math.exp(-age * 2.4))
                cv.drawCircle(cx, cy, rr, paint(st['hot'], 0.85 * math.exp(-age * 2.6) * fade, stroke=3.2))
                cv.drawCircle(cx, cy, R * cam.z, paint(st['hot'], 0.5 * math.exp(-age * 5.0) * fade, stroke=10, blur=8))


# ---- tonearm ----------------------------------------------------------------------------------------------
def stylus_at(r):
    """point at radius r from the spindle that the arm can reach (lower right of the record)"""
    px, py = PIVOT
    d = math.hypot(px, py)
    a = (d * d + r * r - ARM * ARM) / (2 * d)
    h = math.sqrt(max(0.0, r * r - a * a))
    ux, uy = px / d, py / d
    c1 = (a * ux - h * uy, a * uy + h * ux)
    c2 = (a * ux + h * uy, a * uy - h * ux)
    return c1 if c1[1] > c2[1] else c2


def tonearm(cv, cam, r_stylus, lift, st, alpha=1.0):
    """lift 0 = needle in the groove, 1 = raised. r_stylus: radius the needle sits at (world)."""
    if alpha <= 0.01:
        return
    sx, sy = stylus_at(r_stylus)
    px, py = PIVOT
    z = cam.z
    cv.saveLayer(None, paint('#ffffff', alpha))
    ang = math.atan2(sy - py, sx - px)
    for shadow in (True, False):
        cv.save()
        if shadow:
            off = 12 + 34 * lift
            cv.translate(off * 0.5 * z, off * z)
        X, Y = cam.pt(px, py)
        cv.translate(X, Y)
        cv.scale(z * (1 + 0.025 * lift * (0 if shadow else 1)), z * (1 + 0.025 * lift * (0 if shadow else 1)))
        cv.rotate(math.degrees(ang))
        if shadow:
            ps = paint(st['shadow'], 0.26, blur=(9 + 10 * lift) * z)
            cv.drawRoundRect(skia.Rect.MakeLTRB(-150, -11, ARM - 40, 11), 11, 11, ps)
            cv.drawRoundRect(skia.Rect.MakeLTRB(ARM - 78, -30, ARM + 34, 30), 12, 12, ps)
            cv.drawCircle(0, 0, 64, ps)
        else:
            # counterweight
            cv.drawRoundRect(skia.Rect.MakeLTRB(-176, -34, -78, 34), 14, 14, paint(st['arm_dark'], 1.0))
            cv.drawRoundRect(skia.Rect.MakeLTRB(-176, -34, -78, -6), 14, 14, paint('#ffffff', 0.12))
            # tube
            tube = linear((0, -10), (0, 10), [(0, st['arm_hi'], 1), (0.45, st['arm'], 1), (1, st['arm_lo'], 1)])
            cv.drawRoundRect(skia.Rect.MakeLTRB(-90, -9.5, ARM - 60, 9.5), 9.5, 9.5, paint('#ffffff', 1, shader=tube))
            # headshell
            cv.save()
            cv.translate(ARM - 22, 0)
            cv.rotate(-21)
            cv.drawRoundRect(skia.Rect.MakeLTRB(-62, -27, 40, 27), 9, 9, paint(st['arm_dark'], 1.0))
            cv.drawRoundRect(skia.Rect.MakeLTRB(-62, -27, 40, -3), 9, 9, paint('#ffffff', 0.13))
            cv.drawRoundRect(skia.Rect.MakeLTRB(-20, -27, -8, 27), 2, 2, paint(st['accent'], 1.0))
            cv.drawRoundRect(skia.Rect.MakeLTRB(34, -5, 78, 5), 5, 5, paint(st['arm'], 1.0))
            cv.restore()
            # pivot
            cv.drawCircle(0, 0, 62, paint(st['arm_lo'], 1.0))
            cv.drawCircle(0, 0, 56, paint('#ffffff', 1, shader=radial(-14, -18, 90, [(0, st['arm_hi'], 1), (1, st['arm'], 1)])))
            cv.drawCircle(0, 0, 26, paint(st['arm_dark'], 1.0))
            cv.drawCircle(-6, -7, 7, paint('#ffffff', 0.35, blur=2))
        cv.restore()
    cv.restore()
    return sx, sy


# ---- small furniture --------------------------------------------------------------------------------------
def counter(cv, t, st, alpha=1.0):
    """which ring is being cut, top left"""
    l = score.line_at(t, pre=0.2)
    n = None
    if l is not None and l['disc'] and t >= l['t0'] - 0.1:
        n = l['slot'], l['disc']
    if n is None:
        return
    a = alpha * ramp(t, l['t0'] - 0.1, l['t0'] + 0.2) * (1 - ramp(t, l['rel'], l['rel'] + 0.3))
    if a <= 0.01:
        return
    x, y = 70, 150
    pre = '下一张 · ' if n[1] == 'B' else ''
    w = text(cv, pre + '第', x, y, SERIF_M, 30, paint(st['ui'], 0.8 * a), align='l', track=0.08)
    w2 = text(cv, f'{n[0]}', x + w + 12, y - 2, PLAY_I, 52, paint(st['ui'], a), align='l')
    text(cv, '圈', x + w + w2 + 24, y, SERIF_M, 30, paint(st['ui'], 0.8 * a), align='l')
    if n[1] == 'A':
        text(cv, '/ 20', x + w + w2 + 70, y + 2, PLAY_I, 30, paint(st['ui'], 0.5 * a), align='l')


def said(cv, line, t, x, y, st, size=58, align='c', hold=1.6, fade=1.0, c=None, halo=None):
    """a spoken line: straight, in a handwriting face, each character on its syllable; never cut into the record"""
    tt = line['t']
    if t < tt[0] - 0.1:
        return
    out = 1 - ramp(t, tt[-1] + hold, tt[-1] + hold + 0.6)
    if out <= 0:
        return
    s = ''.join(ch['c'] + ch['tail'] for ch in line['chars'])
    w = text_w(s, KAI, size, 0.04)
    x0 = x - w / 2 if align == 'c' else (x if align == 'l' else x - w)
    f = font(KAI, size)
    c = c or st['ink']
    halo = halo or st.get('halo')
    for k, ch in enumerate(line['chars']):
        p = clamp((t - tt[k] + 0.05) / 0.22)
        seg = ch['c'] + ch['tail']
        segw = text_w(seg, KAI, size, 0.04) + 0.04 * size
        if p > 0:
            dy = 10 * (1 - ease_out(p))
            if halo:
                text(cv, seg, x0, y + dy, KAI, size, paint(halo[0], halo[1] * p * out * fade, blur=halo[2]), align='l', track=0.04)
            text(cv, seg, x0, y + dy, KAI, size, paint(c, p * out * fade), align='l', track=0.04)
        x0 += segw
