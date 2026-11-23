"""Drawing kit for the film: glyph sprites, poster-block layout, alpha blits, and full-frame post effects.

Frames are float32 H x W x 3 in 0..1 (display-referred). Text is rasterised once per (string, fonts, size, style)
with Pillow into an alpha sprite; animation is an affine warp of that sprite into the frame.
"""
import functools
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(ROOT, 'work', 'fonts')
FONTS = {
    'hei': 'NotoSansSC-Black.ttf', 'heib': 'NotoSansSC-Bold.ttf', 'heir': 'NotoSansSC-Regular.ttf',
    'song': 'NotoSerifSC-Black.ttf', 'songm': 'NotoSerifSC-SemiBold.ttf', 'songr': 'NotoSerifSC-Regular.ttf',
    'zcool': 'ZCOOLQingKeHuangYou.ttf', 'anton': 'Anton.ttf', 'barlow': 'BarlowCondensed-BlackItalic.ttf',
    'barlowb': 'BarlowCondensed-Bold.ttf', 'mono': 'JetBrainsMono-Bold.ttf', 'courier': 'CourierPrime-Bold.ttf',
    'playb': 'PlayfairDisplay-BlackItalic.ttf', 'play': 'PlayfairDisplay-Italic.ttf', 'archivo': 'ArchivoBlack.ttf',
}
# how tall a Latin font must be set, relative to the CJK size next to it, for the caps to match the CJK body
LAT_SCALE = {'anton': 0.98, 'barlow': 1.12, 'barlowb': 1.12, 'mono': 0.95, 'courier': 1.05, 'playb': 1.02,
             'play': 1.02, 'archivo': 0.98, 'hei': 1.0, 'heib': 1.0, 'heir': 1.0, 'song': 1.0, 'songm': 1.0,
             'songr': 1.0, 'zcool': 1.0}


def rgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


@functools.lru_cache(maxsize=None)
def font(key, size):
    return ImageFont.truetype(os.path.join(FD, FONTS[key]), int(round(size)))


def is_cjk(c):
    return ord(c) >= 0x2E80


def runs(text):
    out = []
    for c in text:
        k = is_cjk(c)
        if out and out[-1][0] == k:
            out[-1][1] += c
        else:
            out.append([k, c])
    return out


class Sprite:
    """alpha mask (uint8) of a string; (ox, oy) is where the pen origin (left, baseline) sits inside the mask."""
    __slots__ = ('a', 'ox', 'oy', 'adv', 'ink')

    def __init__(self, a, ox, oy, adv, ink):
        self.a, self.ox, self.oy, self.adv, self.ink = a, ox, oy, adv, ink


@functools.lru_cache(maxsize=20000)
def sprite(text, cjk, lat, size, outline=0.0, track=0.0):
    """outline > 0 -> hollow letters with a stroke of outline*size px. track = extra advance per glyph (em)."""
    size = max(6, int(round(size)))
    ls = size * LAT_SCALE.get(lat, 1.0)
    pad = int(size * 0.35) + 8
    segs, x = [], 0.0
    for k, s in runs(text):
        f = font(cjk if k else lat, size if k else ls)
        if track:
            for ch in s:
                segs.append((x, ch, f))
                x += f.getlength(ch) + track * size
        else:
            segs.append((x, s, f))
            x += f.getlength(s)
    adv = x
    w = int(math.ceil(adv)) + 2 * pad
    h = int(size * 1.6) + 2 * pad
    im = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(im)
    base = pad + int(size * 1.15)
    for x, s, f in segs:
        d.text((pad + x, base), s, font=f, fill=255, anchor='ls')
    a = np.asarray(im)
    if outline > 0:
        r = max(1, int(round(outline * size)))
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        inner = cv2.erode(a, k)
        a = cv2.subtract(a, inner)
        a = cv2.GaussianBlur(a, (0, 0), 0.6)
    ys, xs = np.nonzero(a > 8)
    if len(xs) == 0:
        return Sprite(np.zeros((2, 2), np.uint8), 0, 0, adv, (0, 0, 0, 0))
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    m = 3
    x0, y0 = max(0, x0 - m), max(0, y0 - m)
    x1, y1 = min(w, x1 + m), min(h, y1 + m)
    a = np.ascontiguousarray(a[y0:y1, x0:x1])
    # ink box relative to the pen origin: left, top (negative = above baseline), right, bottom
    ink = (x0 + m - pad, y0 + m - base, x1 - m - pad, y1 - m - base)
    return Sprite(a, pad - x0, base - y0, adv, ink)


def blit(img, a, x, y, color, alpha=1.0):
    """alpha-blend mask a (uint8 or float 0..1) at integer top-left (x, y)."""
    h, w = a.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, img.shape[1]), min(y + h, img.shape[0])
    if x1 <= x0 or y1 <= y0 or alpha <= 0:
        return
    m = a[y0 - y:y1 - y, x0 - x:x1 - x]
    m = m.astype(np.float32) * (alpha / 255.0 if a.dtype == np.uint8 else alpha)
    roi = img[y0:y1, x0:x1]
    roi += (np.asarray(color, np.float32) - roi) * m[..., None]


def blit_add(img, a, x, y, color, alpha=1.0):
    h, w = a.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, img.shape[1]), min(y + h, img.shape[0])
    if x1 <= x0 or y1 <= y0 or alpha <= 0:
        return
    m = a[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32) * (alpha / 255.0 if a.dtype == np.uint8 else alpha)
    img[y0:y1, x0:x1] += np.asarray(color, np.float32) * m[..., None]


def draw(img, sp, px, py, color, alpha=1.0, scale=1.0, rot=0.0, sx=None, sy=None, shear=0.0, add=False, cx=None, cy=None):
    """draw sprite with its pen origin at (px, py). scale / rot (degrees) / shear act about (cx, cy) in frame
    coordinates (default: the centre of the sprite's ink box)."""
    if alpha <= 0.003:
        return
    fn = blit_add if add else blit
    sx = scale if sx is None else sx
    sy = scale if sy is None else sy
    if abs(sx - 1) < 1e-3 and abs(sy - 1) < 1e-3 and abs(rot) < 1e-3 and abs(shear) < 1e-4:
        fn(img, sp.a, px - sp.ox, py - sp.oy, color, alpha)
        return
    h, w = sp.a.shape
    if cx is None:
        cx = px + (sp.ink[0] + sp.ink[2]) / 2
    if cy is None:
        cy = py + (sp.ink[1] + sp.ink[3]) / 2
    th = math.radians(rot)
    c, s = math.cos(th), math.sin(th)
    A = np.array([[c * sx, (-s + shear * c) * sy], [s * sx, (c + shear * s) * sy]], np.float64)
    # sprite pixel (u, v) sits at frame (px - ox + u, py - oy + v) before the transform
    o = np.array([px - sp.ox - cx, py - sp.oy - cy])
    corners = np.array([[0, 0], [w, 0], [0, h], [w, h]], np.float64) + o
    tc = corners @ A.T + np.array([cx, cy])
    x0, y0 = np.floor(tc.min(0)).astype(int) - 1
    x1, y1 = np.ceil(tc.max(0)).astype(int) + 1
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, img.shape[1]), min(y1, img.shape[0])
    if x1c <= x0c or y1c <= y0c:
        return
    t = A @ o + np.array([cx, cy]) - np.array([x0c, y0c])
    M = np.hstack([A, t[:, None]])
    interp = cv2.INTER_AREA if max(sx, sy) < 0.6 else cv2.INTER_LINEAR
    m = cv2.warpAffine(sp.a, M, (int(x1c - x0c), int(y1c - y0c)), flags=interp)
    fn(img, m, x0c, y0c, color, alpha)


def rect(img, x0, y0, x1, y1, color, alpha=1.0):
    x0, y0, x1, y1 = [int(round(v)) for v in (x0, y0, x1, y1)]
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, img.shape[1]), min(y1, img.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    if alpha >= 0.999:
        img[y0:y1, x0:x1] = color
    else:
        roi = img[y0:y1, x0:x1]
        roi += (np.asarray(color, np.float32) - roi) * alpha


def quad(img, pts, color, alpha=1.0):
    """filled convex polygon (antialiased)."""
    pts = np.asarray(pts, np.float32)
    x0, y0 = np.floor(pts.min(0)).astype(int) - 2
    x1, y1 = np.ceil(pts.max(0)).astype(int) + 2
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, img.shape[1]), min(y1, img.shape[0])
    if x1c <= x0c or y1c <= y0c:
        return
    m = np.zeros((y1c - y0c, x1c - x0c), np.uint8)
    cv2.fillConvexPoly(m, np.round((pts - [x0c, y0c]) * 16).astype(np.int32), 255, cv2.LINE_AA, 4)
    blit(img, m, x0c, y0c, color, alpha)


def rrect(img, cx, cy, w, h, rot, color, alpha=1.0):
    th = math.radians(rot)
    c, s = math.cos(th), math.sin(th)
    hw, hh = w / 2, h / 2
    pts = [(cx + c * a - s * b, cy + s * a + c * b) for a, b in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
    quad(img, pts, color, alpha)


def polyline(img, pts, color, width, alpha=1.0):
    pts = np.asarray(pts, np.float32)
    if len(pts) < 2:
        return
    pad = int(width) + 3
    x0, y0 = np.floor(pts.min(0)).astype(int) - pad
    x1, y1 = np.ceil(pts.max(0)).astype(int) + pad
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, img.shape[1]), min(y1, img.shape[0])
    if x1c <= x0c or y1c <= y0c:
        return
    m = np.zeros((y1c - y0c, x1c - x0c), np.uint8)
    cv2.polylines(m, [np.round((pts - [x0c, y0c]) * 16).astype(np.int32)], False, 255, max(1, int(round(width))), cv2.LINE_AA, 4)
    blit(img, m, x0c, y0c, color, alpha)


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease_out(x, p=3):
    x = clamp(x)
    return 1 - (1 - x) ** p


def ease_in(x, p=3):
    return clamp(x) ** p


def ease_io(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def back_out(x, s=1.9):
    x = clamp(x) - 1
    return x * x * ((s + 1) * x + s) + 1


def lerp(a, b, x):
    return a + (b - a) * x


def rnd(*key):
    """deterministic 0..1 from integers."""
    h = 2166136261
    for k in key:
        h = ((h ^ (int(k) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
        h ^= h >> 13
        h = (h * 0x5bd1e995) & 0xFFFFFFFF
        h ^= h >> 15
    return h / 4294967296.0


# ---------------------------------------------------------------- full-frame post
_YY, _XX = np.mgrid[0:H, 0:W].astype(np.float32)
RAD = np.hypot(_XX - W / 2, _YY - H / 2)
ANG = np.arctan2(_YY - H / 2, _XX - W / 2)
VIG = np.clip(1.0 - (RAD / (0.62 * math.hypot(W, H))) ** 2.4, 0, 1)[..., None].astype(np.float32)
_rs = np.random.RandomState(7)
GRAIN = [(_rs.randn(H // 2, W // 2).astype(np.float32)) for _ in range(6)]


def xform(img, scale=1.0, rot=0.0, dx=0.0, dy=0.0, border=cv2.BORDER_REFLECT, cx=W / 2, cy=H / 2):
    if abs(scale - 1) < 1e-4 and abs(rot) < 1e-3 and abs(dx) < 0.3 and abs(dy) < 0.3:
        return img
    M = cv2.getRotationMatrix2D((cx, cy), -rot, scale)
    M[0, 2] += dx
    M[1, 2] += dy
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR, borderMode=border)


def chroma(img, px, radial=0.0):
    """split red / blue sideways by px pixels (+ optional radial scale split)."""
    if abs(px) < 0.4 and radial <= 0:
        return img
    out = img.copy()
    if radial > 0:
        for ch, s in ((0, 1 + radial), (2, 1 - radial)):
            M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, s)
            M[0, 2] += px if ch == 0 else -px
            out[..., ch] = cv2.warpAffine(img[..., ch], M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    else:
        p = int(round(px))
        out[..., 0] = np.roll(img[..., 0], p, axis=1)
        out[..., 2] = np.roll(img[..., 2], -p, axis=1)
    return out


def glow(img, amount=0.6, thresh=0.55, sigma=9, tint=None):
    if amount <= 0:
        return img
    small = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    b = np.maximum(small - thresh, 0)
    b = cv2.GaussianBlur(b, (0, 0), sigma)
    if tint is not None:
        b = b * tint
    up = cv2.resize(b, (W, H), interpolation=cv2.INTER_LINEAR)
    return img + up * (amount / max(1e-3, 1 - thresh))


def grain(img, fi, amount=0.04):
    g = GRAIN[fi % len(GRAIN)]
    if (fi // len(GRAIN)) % 2:
        g = g[::-1, ::-1]
    g = cv2.resize(g, (W, H), interpolation=cv2.INTER_NEAREST)
    return img + g[..., None] * amount


def vignette(img, amount=1.0):
    if amount <= 0:
        return img
    return img * (1 - amount + amount * VIG)


_SCAN = (0.82 + 0.18 * (np.arange(H) % 4 < 2)).astype(np.float32)[:, None, None]


def scanlines(img, amount=1.0):
    return img * (1 - amount + amount * _SCAN)


def slices(img, seed, n=6, maxdx=80, hmin=10, hmax=120):
    """horizontal band displacement glitch."""
    out = img.copy()
    for k in range(n):
        y = int(rnd(seed, k, 1) * H)
        h = int(lerp(hmin, hmax, rnd(seed, k, 2)))
        dx = int((rnd(seed, k, 3) * 2 - 1) * maxdx)
        out[y:y + h] = np.roll(img[y:y + h], dx, axis=1)
    return out


def flash(img, a, color=(1, 1, 1)):
    if a <= 0:
        return img
    return img + (np.asarray(color, np.float32) - img) * min(a, 1.0)


def to8(img):
    return (np.clip(img, 0, 1) * 255.0 + 0.5).astype(np.uint8)


@functools.lru_cache(maxsize=8)
def noise_tex(seed, w, h, scale):
    """smooth value noise 0..1."""
    rs = np.random.RandomState(seed)
    small = rs.rand(max(2, h // scale), max(2, w // scale)).astype(np.float32)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)


@functools.lru_cache(maxsize=4)
def halftone(period=14, angle=30.0):
    """dot screen threshold map 0..1 over the frame (compare a tone against it to get dots)."""
    th = math.radians(angle)
    u = (_XX * math.cos(th) + _YY * math.sin(th)) / period
    v = (-_XX * math.sin(th) + _YY * math.cos(th)) / period
    d = np.hypot(u - np.round(u), v - np.round(v)) / 0.7071
    return d.astype(np.float32)
