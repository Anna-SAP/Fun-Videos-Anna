"""Shared constants and small image helpers for the Bring Jensen Back MV.

Canvas 1080x1920, 24 fps. The song is 96.00 BPM with the first downbeat at 0.090 s, so one beat is exactly
15 frames and one bar 60 frames; every cut in timeline.py is written as B(bar, beat).

Images are float32 RGB in 0..1, shape (H, W, 3). Layers are (rgb_premultiplied, alpha) pairs.
"""
import functools
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 24
BPM = 96.0
BEAT = 60.0 / BPM          # 0.625 s = 15 frames
BAR = 4 * BEAT             # 2.5 s = 60 frames
T0 = 0.090                 # first downbeat (measured)
DUR = 275.232              # song length (s), from ffmpeg
NFRAMES = int(math.ceil(DUR * FPS))

FONTS = 'work/fonts'

# palette: newsprint, ink, signal green ("the green light"), alarm red, diner amber
PAPER = np.array([0.929, 0.902, 0.839], np.float32)
INK = np.array([0.043, 0.043, 0.047], np.float32)
GREEN = np.array([0.55, 1.00, 0.18], np.float32)
GREEN_D = np.array([0.20, 0.55, 0.05], np.float32)
RED = np.array([1.00, 0.17, 0.15], np.float32)
AMBER = np.array([1.00, 0.66, 0.23], np.float32)
WHITE = np.array([1, 1, 1], np.float32)
CREAM = np.array([0.93, 0.89, 0.80], np.float32)


def B(bar, beat=1, frac=0.0):
    """Seconds of (1-based bar, 1-based beat), snapped to the frame grid."""
    t = T0 + (bar - 1) * BAR + (beat - 1 + frac) * BEAT
    return round(t * FPS) / FPS


def bar_of(t):
    return (t - T0) / BAR + 1


def beat_phase(t):
    """(beat index from first downbeat, fraction 0..1 within the beat)."""
    x = (t - T0) / BEAT
    i = math.floor(x)
    return i, x - i


def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def sstep(a, b, x):
    if a == b:
        return np.where(x >= b, 1.0, 0.0) if isinstance(x, np.ndarray) else float(x >= b)
    u = np.clip((x - a) / (b - a), 0.0, 1.0)
    return u * u * (3 - 2 * u)


def ease_out(u, p=3):
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** p


def ease_in_out(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def kick(t, decay=6.0, beats=(0, 2)):
    """Pulse 1 -> 0 after each kick (beats 1 and 3 of the bar by default)."""
    i, f = beat_phase(t)
    if (i % 4) in beats:
        return math.exp(-decay * f)
    return 0.0


def pulse(t, decay=6.0, every=1.0, offset=0.0):
    x = (t - T0) / BEAT / every - offset
    f = x - math.floor(x)
    return math.exp(-decay * f)


def over(dst, rgb, a):
    """Composite premultiplied rgb with alpha a (H,W) or (H,W,1) over dst, in place."""
    if a.ndim == 2:
        a = a[..., None]
    dst *= (1 - a)
    dst += rgb
    return dst


def over_color(dst, a, color, opacity=1.0):
    if a.ndim == 2:
        a = a[..., None]
    a = a * opacity
    dst *= (1 - a)
    dst += a * np.asarray(color, np.float32)
    return dst


def screen(dst, rgb):
    dst[:] = 1 - (1 - dst) * (1 - rgb)
    return dst


def lum(img):
    return img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114


def blank(color=INK):
    return np.full((H, W, 3), np.asarray(color, np.float32), np.float32)


@functools.lru_cache(maxsize=64)
def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name + '.ttf'), int(size))


def is_cjk(ch):
    o = ord(ch)
    return 0x2E80 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFFEF or 0x3000 <= o <= 0x303F


@functools.lru_cache(maxsize=6000)
def glyph(fontname, size, text):
    """Alpha mask (float32) of a text run, tightly cropped to the font's line box. Returns (mask, advance, ascent)."""
    f = font(fontname, size)
    asc, desc = f.getmetrics()
    w = max(1, int(math.ceil(f.getlength(text))))
    pad = int(size * 0.25)
    im = Image.new('L', (w + 2 * pad, asc + desc + 2 * pad), 0)
    ImageDraw.Draw(im).text((pad, pad), text, font=f, fill=255)
    m = np.asarray(im, np.float32) / 255.0
    return m, pad, asc, w


def paste_mask(canvas_a, m, x, y, scale=1.0, angle=0.0, alpha=1.0):
    """Max-composite a mask into a full-canvas alpha plane at top-left (x, y) with optional scale/rotation
    about the mask centre. Returns bbox."""
    if scale != 1.0 or angle != 0.0:
        h, w = m.shape
        Mx = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
        # enlarge output to fit
        nw, nh = int(w * scale * 1.5 + 4), int(h * scale * 1.5 + 4)
        Mx[0, 2] += nw / 2 - w / 2
        Mx[1, 2] += nh / 2 - h / 2
        m = cv2.warpAffine(m, Mx, (nw, nh), flags=cv2.INTER_LINEAR)
        x = x + w / 2 - nw / 2
        y = y + h / 2 - nh / 2
    x, y = int(round(x)), int(round(y))
    h, w = m.shape
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    sub = m[y0 - y:y1 - y, x0 - x:x1 - x] * alpha
    np.maximum(canvas_a[y0:y1, x0:x1], sub, out=canvas_a[y0:y1, x0:x1])
    return (x0, y0, x1, y1)


_GRAIN = None


def grain(frame_idx, amount=0.05):
    """Per-frame film/paper grain from a fixed bank of noise tiles."""
    global _GRAIN
    if _GRAIN is None:
        rng = np.random.default_rng(7)
        _GRAIN = [cv2.GaussianBlur(rng.standard_normal((H // 2, W // 2)).astype(np.float32), (0, 0), 0.7)
                  for _ in range(12)]
    g = _GRAIN[frame_idx % 12]
    g = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)
    return g * amount


def halftone(L, cell=10.0, angle=45.0, gain=1.0):
    """Ink coverage (0..1) of an AM halftone screen for luminance L (H,W): dark -> big dots."""
    h, w = L.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angle)
    u = (xx * math.cos(a) + yy * math.sin(a)) / cell
    v = (-xx * math.sin(a) + yy * math.cos(a)) / cell
    du = u - np.floor(u) - 0.5
    dv = v - np.floor(v) - 0.5
    d = np.sqrt(du * du + dv * dv)
    Lb = cv2.blur(L, (int(cell), int(cell)))
    r = np.sqrt(clamp01((1 - Lb) * gain)) * 0.62
    return clamp01((r - d) * cell * 0.9 + 0.5)


@functools.lru_cache(maxsize=8)
def _ht_grid(h, w, cell, angle):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angle)
    u = (xx * math.cos(a) + yy * math.sin(a)) / cell
    v = (-xx * math.sin(a) + yy * math.cos(a)) / cell
    du = u - np.floor(u) - 0.5
    dv = v - np.floor(v) - 0.5
    return np.sqrt(du * du + dv * dv).astype(np.float32)


def halftone_fast(L, cell=10, angle=45.0, gain=1.0):
    d = _ht_grid(L.shape[0], L.shape[1], float(cell), float(angle))
    Lb = cv2.blur(L, (int(cell), int(cell)))
    r = np.sqrt(clamp01((1 - Lb) * gain)) * 0.62
    return clamp01((r - d) * cell * 0.9 + 0.5)


def vignette(strength=0.35):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
    return (1 - strength * clamp01(d - 0.35) ** 1.5)[..., None].astype(np.float32)


def to_u8(img):
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def load_rgba(path):
    im = np.asarray(Image.open(path).convert('RGBA'), np.float32) / 255.0
    a = im[..., 3:4]
    return im[..., :3] * a, im[..., 3]
