"""Shared pieces of every look: palette, the lyric line object, per-token entry animation, backgrounds."""
import functools
import math

import cv2
import numpy as np

import beat as B
from kit import (ANG, RAD, H, W, _XX, _YY, back_out, blit, clamp, draw, ease_io, ease_out, lerp, noise_tex, quad,
                 rect, rgb, rnd, sprite)
from typo import set_block

INK = rgb('#0b0b0d')
WHITE = rgb('#f7f4ea')
PAPER = rgb('#ece5d3')
GREEN = rgb('#7dfa00')
DGREEN = rgb('#1f5c00')
RED = rgb('#ff2a2a')
DRED = rgb('#7a0008')
YELLOW = rgb('#ffe500')
MAGENTA = rgb('#ff2bd6')
CYAN = rgb('#19e3ff')
AMBER = rgb('#ffb000')
GREY = rgb('#8a8a8a')
LEAD = 0.045          # a unit lands this long before its measured onset (eyes need a head start)


class Line:
    """one sung pass of a sheet line: display tokens with their sung times."""

    def __init__(self, i, toks, times, t_end):
        self.i, self.toks = i, toks
        self.times = times            # per token (seconds)
        self.t0 = min(times)
        self.t_end = t_end            # when the last unit stops sounding (approx.)
        self._cache = {}

    def block(self, rows, box, **kw):
        key = (repr(rows), box, tuple(sorted((k, repr(v)) for k, v in kw.items())))
        if key not in self._cache:
            placed, bb = set_block(self.toks, rows, box, **kw)
            for p in placed:
                p.t = self.times[p.i]
            self._cache[key] = (placed, bb)
        return self._cache[key]


def age(p, t):
    return t + LEAD - p.t


def entry(p, t, kind='pop', dur=0.15):
    """-> (scale, dx, dy, rot, alpha) of a token at time t, or None before it is sung."""
    a = age(p, t)
    if a < 0:
        return None
    x = a / dur
    if kind == 'pop':
        return lerp(1.75, 1.0, back_out(x, 2.2)), 0, 0, 0, 1.0
    if kind == 'slam':
        return lerp(3.2, 1.0, ease_out(x, 4)), 0, 0, 0, clamp(x * 3 + 0.4)
    if kind == 'stamp':
        r = (rnd(p.k, p.i, 77) - 0.5) * 16
        return lerp(1.45, 1.0, ease_out(x, 3)), 0, 0, r * (1 - ease_out(x, 2)), 1.0
    if kind == 'rise':
        return 1.0, 0, lerp(0.45 * p.size, 0, ease_out(x, 3)), 0, clamp(x * 1.5)
    if kind == 'drop':
        return 1.0, 0, lerp(-0.6 * p.size, 0, back_out(x, 1.6)), 0, clamp(x * 2)
    if kind == 'fade':
        return lerp(1.04, 1.0, ease_out(x)), 0, lerp(0.10 * p.size, 0, ease_out(x)), 0, ease_io(x)
    if kind == 'left':
        return 1.0, lerp(-0.8 * p.size, 0, ease_out(x, 4)), 0, 0, clamp(x * 2)
    if kind == 'trip':        # triplet stutter: three hits in 0.13 s
        k = min(2, int(a / 0.045))
        return (1.42, 1.18, 1.0)[k], ((rnd(p.k, k) - 0.5) * 0.18 * p.size if k < 2 else 0), 0, 0, 1.0
    return 1.0, 0, 0, 0, 1.0   # 'cut'


def heat(p, t, hold=0.10, fall=0.22):
    """1 while a token is the newest thing sung, falling to 0."""
    a = age(p, t)
    if a < 0:
        return 0.0
    return 1.0 - clamp((a - hold) / fall)


@functools.lru_cache(maxsize=4000)
def _extruded(text, cjk, lat, size, outline, n, dx, dy):
    sp = sprite(text, cjk, lat, size, outline)
    h, w = sp.a.shape
    ex = abs(dx) * n
    ey = abs(dy) * n
    out = np.zeros((h + int(ey) + 2, w + int(ex) + 2), np.uint8)
    for k in range(n, 0, -1):
        ox = int(round(k * dx)) if dx >= 0 else int(round(ex + k * dx))
        oy = int(round(k * dy)) if dy >= 0 else int(round(ey + k * dy))
        roi = out[oy:oy + h, ox:ox + w]
        np.maximum(roi, sp.a, out=roi)
    from kit import Sprite
    return Sprite(out, sp.ox + (0 if dx >= 0 else int(round(ex))), sp.oy + (0 if dy >= 0 else int(round(ey))), sp.adv, sp.ink)


class Xf:
    """block transform about a pivot."""

    def __init__(self, cx=W / 2, cy=H / 2, scale=1.0, rot=0.0, dx=0.0, dy=0.0):
        self.cx, self.cy, self.s, self.rot, self.dx, self.dy = cx, cy, scale, rot, dx, dy
        th = math.radians(rot)
        self.c, self.sn = math.cos(th), math.sin(th)

    def pt(self, x, y):
        u, v = (x - self.cx) * self.s, (y - self.cy) * self.s
        return self.cx + self.c * u - self.sn * v + self.dx, self.cy + self.sn * u + self.c * v + self.dy


ID = Xf()


def draw_tok(img, p, t, col, kind='pop', dur=0.15, xf=ID, hot=None, alpha=1.0, fonts=('hei', 'anton'), outline=0.0,
             ex=None, add=False, state=None, track=0.0, dash_col=None):
    """draw one placed token with its entry animation. ex = (n, dx, dy, colour) for a 3-D extrusion.
    state overrides the entry animation: (scale, dx, dy, rot, alpha)."""
    st = entry(p, t, kind, dur) if state is None else state
    if st is None:
        return False
    s, dx, dy, r, al = st
    al *= alpha
    c = np.asarray(col, np.float32)
    if hot is not None:
        hh = heat(p, t)
        if hh > 0:
            c = c + (np.asarray(hot, np.float32) - c) * hh
    # token centre under the block transform
    cx0, cy0 = (p.x0 + p.x1) / 2, (p.y0 + p.y1) / 2
    cx, cy = xf.pt(cx0 + dx, cy0 + dy)
    px, py = p.x + (cx - cx0), p.y + (cy - cy0)
    sc, rot = s * xf.s, r + xf.rot
    if ex is not None:
        n, ex_dx, ex_dy, ex_col = ex
        spx = _extruded(p.tok['text'], fonts[0], fonts[1], int(round(p.size)), outline, n, ex_dx, ex_dy)
        draw(img, spx, px, py, ex_col, al, scale=sc, rot=rot, cx=cx, cy=cy)
    draw(img, p.sp, px, py, c, al, scale=sc, rot=rot, cx=cx, cy=cy, add=add)
    if p.dash:
        # the sheet's em dash, drawn as a rule after the token
        x0 = p.x + p.w + 0.16 * p.size
        x1 = x0 + 0.78 * p.size
        yb = p.y - 0.36 * p.size
        th = max(3.0, 0.085 * p.size)
        g = ease_out(clamp(age(p, t) / 0.25))
        pts = [xf.pt(x0, yb - th / 2), xf.pt(x0 + (x1 - x0) * g, yb - th / 2), xf.pt(x0 + (x1 - x0) * g, yb + th / 2),
               xf.pt(x0, yb + th / 2)]
        quad(img, pts, c if dash_col is None else dash_col, al)
    return True


def draw_block(img, placed, t, col, sel=None, **kw):
    n = 0
    for p in placed:
        if sel is not None and not sel(p):
            continue
        c = col(p) if callable(col) else col
        n += bool(draw_tok(img, p, t, c, **kw))
    return n


def last_onset(placed, t):
    """age of the newest sung token (seconds), or None."""
    best = None
    for p in placed:
        a = age(p, t)
        if a >= 0 and (best is None or a < best):
            best = a
    return best


# ---------------------------------------------------------------- backgrounds
def solid(col):
    img = np.empty((H, W, 3), np.float32)
    img[:] = col
    return img


def rays(t, c0, c1, n=14, rot=0.0, soft=0.06, cx=W / 2, cy=H / 2, twist=0.0):
    """sunburst of n pairs of rays about (cx, cy)."""
    if cx == W / 2 and cy == H / 2:
        ang, rad = ANG, RAD
    else:
        ang = np.arctan2(_YY - cy, _XX - cx)
        rad = np.hypot(_XX - cx, _YY - cy)
    ph = ang * (n / (2 * math.pi)) + rot
    if twist:
        ph = ph + rad * (twist / 1000.0)
    tri = np.abs((ph % 1.0) - 0.5) * 2          # 0..1 triangle
    m = np.clip((tri - 0.5) / soft + 0.5, 0, 1)[..., None]
    return np.asarray(c0, np.float32) + (np.asarray(c1, np.float32) - np.asarray(c0, np.float32)) * m


def rings(t, c0, c1, period=160.0, speed=1.0, soft=0.08, cx=W / 2, cy=H / 2, power=0.75):
    """concentric rings flying outwards (tunnel)."""
    rad = RAD if (cx == W / 2 and cy == H / 2) else np.hypot(_XX - cx, _YY - cy)
    ph = (rad ** power) / (period ** power) - t * speed
    tri = np.abs((ph % 1.0) - 0.5) * 2
    m = np.clip((tri - 0.5) / soft + 0.5, 0, 1)[..., None]
    return np.asarray(c0, np.float32) + (np.asarray(c1, np.float32) - np.asarray(c0, np.float32)) * m


def stripes(c0, c1, period=120.0, angle=45.0, shift=0.0, soft=0.04, duty=0.5):
    th = math.radians(angle)
    u = (_XX * math.cos(th) + _YY * math.sin(th)) / period + shift
    tri = np.abs((u % 1.0) - 0.5) * 2
    m = np.clip((tri - (1 - duty)) / soft + 0.5, 0, 1)[..., None]
    return np.asarray(c0, np.float32) + (np.asarray(c1, np.float32) - np.asarray(c0, np.float32)) * m


@functools.lru_cache(maxsize=4)
def paper_tex(seed=3, dark=False):
    """static sheet of paper, a little larger than the frame so it can be offset per line."""
    w, h = W + 160, H + 160
    n1 = noise_tex(seed, w, h, 220)
    n2 = noise_tex(seed + 1, w, h, 24)
    rs = np.random.RandomState(seed + 2)
    fine = rs.randn(h, w).astype(np.float32)
    fine = cv2.GaussianBlur(fine, (0, 0), 0.8)
    v = 0.5 + (n1 - 0.5) * 0.10 + (n2 - 0.5) * 0.05 + fine * 0.035
    # fibres
    fib = np.zeros((h, w), np.float32)
    for k in range(260):
        x, y = rs.randint(0, w), rs.randint(0, h)
        a = rs.rand() * math.pi
        ln = rs.randint(12, 46)
        cv2.line(fib, (x, y), (int(x + math.cos(a) * ln), int(y + math.sin(a) * ln)), float(rs.rand() * 0.5 + 0.3), 1, cv2.LINE_AA)
    v = v - fib * 0.05
    if dark:
        base = np.array([0.105, 0.105, 0.115], np.float32)
        img = base + (v[..., None] - 0.5) * 0.11
    else:
        base = PAPER
        img = base + (v[..., None] - 0.5) * 0.36
    return np.clip(img, 0, 1).astype(np.float32)


def paper(seed_off=0, dark=False):
    tex = paper_tex(3, dark)
    ox = int(rnd(seed_off, 1) * 150)
    oy = int(rnd(seed_off, 2) * 150)
    return tex[oy:oy + H, ox:ox + W].copy()


def cam(img, t, t0, push=0.035, dur=3.2, k_zoom=0.02, k_shake=0.0, seed=0, rot=0.0, snare_shake=0.0):
    """slow push-in over a line + kick zoom + shake."""
    from kit import xform
    g = clamp((t - t0) / dur)
    k = B.kick(t)
    s = 1.0 + push * g + k_zoom * k
    dx = dy = 0.0
    amp = k_shake * k + snare_shake * B.snare(t)
    if amp > 0.2:
        fi = int(t * 30)
        dx = (rnd(fi, seed, 1) - 0.5) * 2 * amp
        dy = (rnd(fi, seed, 2) - 0.5) * 2 * amp
    return xform(img, s, rot, dx, dy)
