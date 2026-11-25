#!/usr/bin/env python3
"""Drawing helpers on top of Skia: colours, fonts, paints, single glyphs with rotation, easing, keyframes."""
import functools
import math
import os

import numpy as np
import skia

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 30
TAU = 2 * math.pi

SERIF_B = 'NotoSerifSC-Bold.ttf'
SERIF_K = 'NotoSerifSC-Black.ttf'
SERIF_M = 'NotoSerifSC-Medium.ttf'
SERIF_R = 'NotoSerifSC-Regular.ttf'
SANS_M = 'NotoSansSC-Medium.ttf'
SANS_R = 'NotoSansSC-Regular.ttf'
KAI = 'LXGWWenKai-Medium.ttf'
KAI_R = 'LXGWWenKai-Regular.ttf'
PLAY_I = 'PlayfairDisplay-Italic.ttf'
PLAY = 'PlayfairDisplay-Regular.ttf'


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def col(c, a=1.0):
    """'#rrggbb' or (r,g,b) floats -> skia.Color4f"""
    if isinstance(c, str):
        c = rgb(c)
    return skia.Color4f(c[0], c[1], c[2], max(0.0, min(1.0, a)))


def mix(c1, c2, u):
    if isinstance(c1, str):
        c1 = rgb(c1)
    if isinstance(c2, str):
        c2 = rgb(c2)
    u = max(0.0, min(1.0, u))
    return tuple(a + (b - a) * u for a, b in zip(c1, c2))


@functools.lru_cache(None)
def face(name):
    tf = skia.Typeface.MakeFromFile(os.path.join(ROOT, 'work', 'fonts', name))
    assert tf is not None, name
    return tf


@functools.lru_cache(None)
def _font(name, size):
    f = skia.Font(face(name), size)
    f.setSubpixel(True)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setLinearMetrics(True)
    f.setHinting(skia.FontHinting.kNone)
    return f


def font(name, size):
    return _font(name, round(size * 4) / 4)


def paint(c, a=1.0, stroke=None, blur=0.0, blend=None, shader=None, cap=None):
    p = skia.Paint(AntiAlias=True)
    p.setColor4f(col(c, a))
    if stroke is not None:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        p.setStrokeCap(cap or skia.Paint.kRound_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur > 0:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    if blend is not None:
        p.setBlendMode(blend)
    if shader is not None:
        p.setShader(shader)
    return p


PLUS = skia.BlendMode.kPlus
SCREEN = skia.BlendMode.kScreen
MULT = skia.BlendMode.kMultiply
SOFT = skia.BlendMode.kSoftLight
OVERLAY = skia.BlendMode.kOverlay


def radial(cx, cy, r, stops):
    """stops: [(pos, colour, alpha)]"""
    return skia.GradientShader.MakeRadial((cx, cy), r, [col(c, a) for _, c, a in stops], [p for p, _, _ in stops])


def linear(p0, p1, stops):
    return skia.GradientShader.MakeLinear([p0, p1], [col(c, a) for _, c, a in stops], [p for p, _, _ in stops])


def sweep(cx, cy, stops, rot=0.0):
    m = skia.Matrix()
    m.setRotate(rot, cx, cy)
    return skia.GradientShader.MakeSweep(cx, cy, [col(c, a) for _, c, a in stops], [p for p, _, _ in stops], localMatrix=m)


@functools.lru_cache(4096)
def _gm(name, size, ch):
    f = font(name, size)
    m = f.getMetrics()
    return f.measureText(ch), -(m.fAscent + m.fDescent) / 2 - size * 0.02


def glyph(cv, ch, x, y, name, size, pnt, rot=0.0, sc=1.0):
    """draw one character centred on (x, y), rotated by rot degrees (clockwise on screen)"""
    q = round(size * 4) / 4
    w, dy = _gm(name, q, ch)
    cv.save()
    cv.translate(x, y)
    if rot:
        cv.rotate(rot)
    if sc != 1.0:
        cv.scale(sc, sc)
    cv.drawString(ch, -w / 2, dy, font(name, q), pnt)
    cv.restore()


def text(cv, s, x, y, name, size, pnt, align='c', track=0.0):
    """a straight run of text; y is the visual centre line. track = extra advance in em. returns width"""
    f = font(name, size)
    _, dy = _gm(name, round(size * 4) / 4, '国')
    if track == 0.0:
        w = f.measureText(s)
        x0 = x - w / 2 if align == 'c' else (x - w if align == 'r' else x)
        cv.drawString(s, x0, y + dy, f, pnt)
        return w
    ws = [f.measureText(c) + track * size for c in s]
    w = sum(ws) - track * size
    x0 = x - w / 2 if align == 'c' else (x - w if align == 'r' else x)
    for c, cw in zip(s, ws):
        cv.drawString(c, x0, y + dy, f, pnt)
        x0 += cw
    return w


def text_w(s, name, size, track=0.0):
    f = font(name, size)
    return sum(f.measureText(c) + track * size for c in s) - track * size if track else f.measureText(s)


# ---- easing / keyframes ---------------------------------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


def smooth(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def smoother(u):
    u = clamp(u)
    return u * u * u * (u * (6 * u - 15) + 10)


def ease_out(u, p=3):
    u = clamp(u)
    return 1 - (1 - u) ** p


def ease_in(u, p=3):
    return clamp(u) ** p


def back_out(u, s=1.6):
    u = clamp(u) - 1
    return u * u * ((s + 1) * u + s) + 1


def ramp(t, a, b):
    """0 before a, 1 after b, smooth in between"""
    return smooth((t - a) / (b - a)) if b > a else float(t >= b)


def bump(t, a, b, c, d):
    """0 -> 1 between a..b, 1 -> 0 between c..d"""
    return ramp(t, a, b) * (1 - ramp(t, c, d))


def kf(t, keys, ease=smooth):
    """piecewise interpolation through [(time, value), ...]"""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * ease((t - t0) / (t1 - t0))
    return keys[-1][1]


def lerp(a, b, u):
    return a + (b - a) * u


def rnd(seed):
    return np.random.default_rng(seed)


def polar(r, a):
    """world/screen point at radius r, angle a measured from straight down, positive = towards the left
    (the direction a clockwise-turning disc carries its lower edge)"""
    return -r * math.sin(a), r * math.cos(a)
