"""Canvas, clock and small helpers shared by every module.

The film is 1080x1920 at 30 fps. The song is 86.78 BPM with the first downbeat at 0.030 s (measured by
analyze_structure.py), so one beat is 0.6914 s = 20.74 frames: every cut is rounded from seconds to the
nearest frame on its own, never accumulated as "N frames per beat".
"""
import functools
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 30
DUR = 303.24
NFRAMES = int(round(DUR * FPS))
BPM = 86.78
BEAT = 60.0 / BPM
BAR = 4 * BEAT
T0 = 0.030

FONTS = {
    'sans': 'work/fonts/NotoSansSC-Black.ttf',
    'sansb': 'work/fonts/NotoSansSC-Bold.ttf',
    'serif': 'work/fonts/NotoSerifSC-Black.ttf',
    'anton': 'work/fonts/Anton.ttf',
    'archivo': 'work/fonts/ArchivoBlack.ttf',
    'bebas': 'work/fonts/BebasNeue.ttf',
    'mono': 'work/fonts/SpaceMono.ttf',
    'monor': 'work/fonts/SpaceMonoR.ttf',
    'qingke': 'work/fonts/ZCOOLQingKe.ttf',
    'marker': 'work/fonts/PermanentMarker.ttf',
}


def bar_t(n, beat=0):
    """Time of bar n (1-based, as printed by analyze_structure.py) plus `beat` beats."""
    return T0 + (n - 1) * BAR + beat * BEAT


def beat_phase(t):
    """Position inside the current beat, 0..1."""
    return ((t - T0) / BEAT) % 1.0


def frame_of(t):
    return int(round(t * FPS))


def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def smooth(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def ease_out(x, p=3):
    x = clamp01(x)
    return 1 - (1 - x) ** p


def ease_in(x, p=3):
    return clamp01(x) ** p


def back_out(x, s=2.2):
    """Overshoot ease: goes past 1 and settles (for knocks)."""
    x = clamp01(x)
    x = x - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, x):
    return a + (b - a) * x


def window(t, a, b, fin=0.2, fout=0.2):
    """1 inside [a, b], ramps of length fin/fout outside."""
    if t < a - fin or t > b + fout:
        return 0.0
    v = 1.0
    if t < a:
        v = smooth((t - (a - fin)) / max(fin, 1e-6))
    elif t > b:
        v = 1 - smooth((t - b) / max(fout, 1e-6))
    return float(v)


@functools.lru_cache(maxsize=64)
def font(name, size):
    return ImageFont.truetype(FONTS.get(name, name), int(size))


def hash01(*k):
    """Deterministic pseudo-random number in [0, 1) from integers/strings."""
    h = 2166136261
    for v in k:
        for ch in str(v):
            h = ((h ^ ord(ch)) * 16777619) & 0xffffffff
        h = ((h ^ 0x9e) * 16777619) & 0xffffffff
    return (h % 100000) / 100000.0


@functools.lru_cache(maxsize=4096)
def glyph(text, fname, size, stroke=0):
    """Tight grayscale mask (float32 0..1) of `text` in font `fname` at `size` px, plus its ink offset.
    Returns (mask, ox, oy, adv) where (ox, oy) is the ink box's top-left relative to the pen origin
    (baseline at y = ascent) and adv is the advance width."""
    f = font(fname, size)
    asc, desc = f.getmetrics()
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    w, h = max(1, r - l + 4), max(1, b - t + 4)
    im = Image.new('L', (w, h), 0)
    ImageDraw.Draw(im).text((-l + 2, -t + 2), text, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
    adv = f.getlength(text)
    return np.asarray(im, np.float32) / 255.0, l - 2, t - 2, adv


def ink_box(text, fname, size):
    f = font(fname, size)
    return f.getbbox(text)


def paste_add(dst, src, x, y, k=1.0):
    """dst[y:y+h, x:x+w] = max(dst, src*k) with clipping; dst/src are 2-D float arrays."""
    h, w = src.shape[:2]
    x0, y0 = int(round(x)), int(round(y))
    x1, y1 = x0 + w, y0 + h
    cx0, cy0 = max(0, x0), max(0, y0)
    cx1, cy1 = min(dst.shape[1], x1), min(dst.shape[0], y1)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    sub = src[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    np.maximum(dst[cy0:cy1, cx0:cx1], sub * k, out=dst[cy0:cy1, cx0:cx1])


def paste_scaled(dst, src, cx, cy, scale, k=1.0, rot=0.0):
    """Paste src scaled about its centre to (cx, cy) with max-blend."""
    if scale <= 0.01 or k <= 0.002:
        return
    h, w = src.shape[:2]
    if abs(scale - 1) < 1e-3 and abs(rot) < 1e-3:
        paste_add(dst, src, cx - w / 2, cy - h / 2, k)
        return
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rot, scale)
    nw, nh = int(w * scale * 1.2 + 8), int(h * scale * 1.2 + 8)
    M[0, 2] += nw / 2 - w / 2
    M[1, 2] += nh / 2 - h / 2
    out = cv2.warpAffine(src, M, (nw, nh), flags=cv2.INTER_LINEAR)
    paste_add(dst, out, cx - nw / 2, cy - nh / 2, k)


def noise2(h, w, scale, seed, octaves=3):
    """Smooth value noise in [0, 1] (float32), built from upscaled random grids."""
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    s = scale
    for _ in range(octaves):
        gh, gw = max(2, int(h / s) + 2), max(2, int(w / s) + 2)
        g = rng.random((gh, gw)).astype(np.float32)
        acc += amp * cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)
        tot += amp
        amp *= 0.5
        s /= 2.0
    acc /= tot
    return np.clip(acc, 0, 1)


def to8(img):
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def hexc(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


os.makedirs('work/preview', exist_ok=True)
