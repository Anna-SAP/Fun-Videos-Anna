"""One split-flap cell: glyph tiles, flap faces and the fold animation.

A cell is two halves around a hinge. Changing from A to B: the top flap (A's top half) falls toward the
viewer and flattens onto the hinge, uncovering B's top half; past 90 degrees its back (B's bottom half)
keeps falling and lands over A's bottom half. A character that lands at time T has spun through a few other
characters first, one fold per step, the last fold ending exactly at T.

Tiles are cached per (char, style, w, h): w, h is the cell pitch in pixels; the flap face is inset inside it
and the rest is the dark housing. Everything is float32 RGB in 0..1.
"""
import functools
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = os.environ.get('FONT_DIR', 'work/fonts')
CJK_FONT = os.path.join(FONT_DIR, 'NotoSansSC-Bold.ttf')
CJK_BLACK = os.path.join(FONT_DIR, 'NotoSansSC-Black.ttf')
LAT_FONT = os.path.join(FONT_DIR, 'BarlowCondensed-Bold.ttf')

HOUSING = np.array((0.018, 0.018, 0.021), np.float32)

STYLES = {
    #        flap colour                 ink
    'w': ((0.100, 0.100, 0.106), (0.93, 0.91, 0.86)),    # white on black: the board's default
    'a': ((0.100, 0.100, 0.106), (1.00, 0.68, 0.14)),    # amber ink: backing vocals, the counter
    'r': ((0.60, 0.065, 0.055), (0.98, 0.95, 0.92)),     # red flap: AI
    'g': ((0.045, 0.40, 0.21), (0.95, 0.99, 0.94)),      # green flap: 重启 / Reset / Respawn
    'd': ((0.100, 0.100, 0.106), (0.50, 0.50, 0.48)),    # dim grey ink: labels
    'k': ((0.100, 0.100, 0.106), (0.100, 0.100, 0.106)), # blank
}


def is_half(ch):
    return ord(ch) < 0x2E80 and ch not in '—…'


@functools.lru_cache(maxsize=None)
def _font(path, size):
    return ImageFont.truetype(path, size)


@functools.lru_cache(maxsize=2500)
def glyph(ch, w, h, half, heavy=False):
    """alpha mask (h, w) of the character centred on the cell's hinge."""
    S = 3 if w < 200 else 2
    W, H = w * S, h * S
    im = Image.new('L', (W, H), 0)
    if ch.strip():
        d = ImageDraw.Draw(im)
        if half:
            f = _font(LAT_FONT, int(H * 0.60))
            cap = f.getbbox('H', anchor='ls')
            base = H / 2 + (cap[3] - cap[1]) / 2
        else:
            f = _font(CJK_BLACK if heavy else CJK_FONT, int(W * 0.78))
            em = f.getbbox('国', anchor='ls')
            base = H / 2 + (em[3] - em[1]) / 2 - em[3]
        bb = d.textbbox((0, 0), ch, font=f, anchor='ls')
        x = (W - (bb[2] - bb[0])) / 2 - bb[0]
        d.text((x, base), ch, font=f, fill=255, anchor='ls')
    return np.asarray(im.resize((w, h), Image.LANCZOS), np.float32) / 255.0


@functools.lru_cache(maxsize=None)
def face(w, h):
    """shading multiplier and coverage mask for a cell of pitch (w, h)."""
    mx, my = max(1.0, 0.045 * w), max(1.0, 0.035 * h)
    py = np.arange(h, dtype=np.float32) + 0.5
    px = np.arange(w, dtype=np.float32) + 0.5
    yy, xx = np.meshgrid(py, px, indexing='ij')
    hinge = h / 2
    top = yy < hinge
    t_rel = np.clip((yy - my) / (hinge - my), 0, 1)
    b_rel = np.clip((yy - hinge) / (h - my - hinge), 0, 1)
    sh = np.where(top, 1.20 - 0.45 * t_rel ** 1.5, 0.88 + 0.34 * np.exp(-b_rel / 0.05) - 0.22 * b_rel)
    xr = (xx - mx) / (w - 2 * mx) * 2 - 1
    sh *= 1.0 - 0.10 * xr ** 2
    # rounded rectangle per half
    r = 0.075 * min(w, h)
    def rrect(x0, y0, x1, y1):
        qx = np.maximum(np.maximum(x0 + r - xx, xx - (x1 - r)), 0)
        qy = np.maximum(np.maximum(y0 + r - yy, yy - (y1 - r)), 0)
        d = np.sqrt(qx ** 2 + qy ** 2) - r
        inside = (xx > x0) & (xx < x1) & (yy > y0) & (yy < y1)
        m = np.clip(0.5 - d, 0, 1) * inside
        edge_x = np.clip(np.minimum(xx - x0, x1 - xx), 0, 1)
        edge_y = np.clip(np.minimum(yy - y0, y1 - yy), 0, 1)
        return np.minimum(m, np.minimum(edge_x, edge_y))
    gap = max(0.8, 0.012 * h)
    m = np.where(top, rrect(mx, my, w - mx, hinge - gap / 2), rrect(mx, hinge + gap / 2, w - mx, h - my))
    return sh.astype(np.float32), m.astype(np.float32)


@functools.lru_cache(maxsize=2500)
def tile(ch, style, w, h, heavy=False):
    """the resting cell (h, w, 3) and its flap coverage mask."""
    half = is_half(ch)
    fcol, ink = STYLES[style]
    sh, m = face(w, h)
    a = glyph(ch, w, h, half, heavy) if style != 'k' else np.zeros((h, w), np.float32)
    fcol = np.array(fcol, np.float32)
    ink = np.array(ink, np.float32)
    col = fcol[None, None] * (1 - a[..., None]) + ink[None, None] * a[..., None]
    col = col * sh[..., None]
    if w >= 40:
        rng = np.random.default_rng((ord(ch[0]) * 131 + ord(style)) % (2 ** 32))
        n = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), max(0.6, w / 80))
        col *= (0.95 + 0.10 * n)[..., None]
    out = HOUSING[None, None] * (1 - m[..., None]) + col * m[..., None]
    return np.ascontiguousarray(out, np.float32), m


def fold(a, sa, b, sb, w, h, p, heavy=False):
    """cell image mid-fold from (a, style sa) to (b, style sb), p in [0, 1]."""
    if p <= 0:
        return tile(a, sa, w, h, heavy)[0]
    if p >= 1:
        return tile(b, sb, w, h, heavy)[0]
    ta, ma = tile(a, sa, w, h, heavy)
    tb, mb = tile(b, sb, w, h, heavy)
    hh = h // 2
    out = np.empty_like(ta)
    out[:hh] = tb[:hh]
    out[hh:] = ta[hh:]
    ang = np.pi * p
    c = float(np.cos(ang))
    s = float(np.sin(ang))
    dx = 0.09 * s * w / 2
    if p < 0.5:
        out[:hh] = HOUSING + (out[:hh] - HOUSING) * (0.50 + 0.50 * (1 - c))
        src = ta[:hh] * (1.0 - 0.6 * s)
        hgt = max(1.0, hh * c)
        pts0 = np.float32([[0, 0], [w, 0], [w, hh], [0, hh]])
        pts1 = np.float32([[-dx, hh - hgt], [w + dx, hh - hgt], [w, hh], [0, hh]])
        M = cv2.getPerspectiveTransform(pts0, pts1)
        warped = cv2.warpPerspective(src, M, (w, hh), flags=cv2.INTER_LINEAR)
        mk = cv2.warpPerspective(ma[:hh], M, (w, hh), flags=cv2.INTER_LINEAR)
        out[:hh] = out[:hh] * (1 - mk[..., None]) + warped * mk[..., None]
    else:
        src = tb[hh:] * (0.40 + 0.60 * (-c))
        hb = h - hh
        hgt = max(1.0, hb * (-c))
        pts0 = np.float32([[0, 0], [w, 0], [w, hb], [0, hb]])
        pts1 = np.float32([[0, 0], [w, 0], [w + dx, hgt], [-dx, hgt]])
        M = cv2.getPerspectiveTransform(pts0, pts1)
        warped = cv2.warpPerspective(src, M, (w, hb), flags=cv2.INTER_LINEAR)
        mk = cv2.warpPerspective(mb[hh:], M, (w, hb), flags=cv2.INTER_LINEAR)
        # the landing flap throws a little shadow on the half it is about to cover
        out[hh:] = HOUSING + (out[hh:] - HOUSING) * (0.6 + 0.4 * (-c))
        out[hh:] = out[hh:] * (1 - mk[..., None]) + warped * mk[..., None]
    return out
