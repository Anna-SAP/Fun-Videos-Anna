"""LED wall engine: everything in the film is lit dots on one wall.

The wall is a grid of GW x GH bulbs (pitch P px). A frame is built as a per-bulb RGB intensity field
(GH, GW, 3), then expanded to pixels with a round-dot sprite, unlit bulbs stay faintly visible, and the
light blooms. Text and pixel-art are rasterised straight onto the bulb grid.
"""
import functools
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

cv2.setNumThreads(1)   # one process per core; also keeps fork/spawn workers from deadlocking

W, H = 1080, 1920
P = 8
GW, GH = W // P, H // P          # 135 x 240 bulbs
HERE = os.path.dirname(os.path.abspath(__file__))
FONTDIR = os.path.join(HERE, '..', 'work', 'fonts')
FONT_ZH = os.path.join(FONTDIR, 'NotoSansSC-Black.ttf')
FONT_ZH_B = os.path.join(FONTDIR, 'NotoSansSC-Bold.ttf')
FONT_EN = os.path.join(FONTDIR, 'Anton-Regular.ttf')
FONT_PIX = '/usr/share/fonts/opentype/unifont/unifont.otf'
if not os.path.exists(FONT_PIX):
    import glob
    c = glob.glob('/usr/share/fonts/**/unifont*.[ot]tf', recursive=True)
    FONT_PIX = c[0] if c else FONT_ZH_B

# colours (linear-ish intensities; >1 blooms)
AMBER = np.array([1.00, 0.55, 0.16], np.float32)
GREEN = np.array([0.42, 1.00, 0.22], np.float32)
RED = np.array([1.00, 0.16, 0.10], np.float32)
WHITE = np.array([0.92, 0.95, 1.00], np.float32)
DIM = np.array([0.30, 0.34, 0.32], np.float32)


def _sprite(p=P):
    y, x = np.mgrid[0:p, 0:p].astype(np.float32) + 0.5
    r = np.hypot(x - p / 2, y - p / 2) / (p / 2)
    lit = np.clip((0.92 - r) / 0.22, 0, 1) ** 1.2          # bright core, soft edge
    hot = np.exp(-(r / 0.38) ** 2) * 0.35                    # filament hotspot
    off = np.clip((0.86 - r) / 0.2, 0, 1)                   # unlit lens
    return (lit + hot).astype(np.float32), off.astype(np.float32)


SPR, SPR_OFF = _sprite()
SPR_T = np.tile(SPR, (GH, GW))[..., None]
OFF_T = np.tile(SPR_OFF, (GH, GW))[..., None]
OFF_COL = np.array([0.020, 0.022, 0.024], np.float32)


def expand(field, off_level=1.0):
    """bulb field (GH,GW,3) -> pixels (H,W,3) float32 with dots and bloom."""
    up = np.repeat(np.repeat(field, P, 0), P, 1)
    img = up * SPR_T + OFF_T * (OFF_COL * off_level)
    # bloom from the bulb field itself (cheap: at grid resolution)
    b1 = cv2.GaussianBlur(field, (0, 0), 1.1)
    b2 = cv2.GaussianBlur(cv2.resize(field, (GW // 3, GH // 3), interpolation=cv2.INTER_AREA), (0, 0), 3.0)
    glow = cv2.resize(b1, (W, H), interpolation=cv2.INTER_LINEAR) * 0.55 + \
        cv2.resize(b2, (W, H), interpolation=cv2.INTER_LINEAR) * 0.45
    return img + glow


@functools.lru_cache(maxsize=64)
def font(path, size):
    return ImageFont.truetype(path, size)


SS = 4  # supersampling for text rasterisation


@functools.lru_cache(maxsize=4096)
def glyph_mask(text, path, h_dots, sharp=0.5, track=0.0):
    """Coverage mask on the bulb grid for one run of text whose cap/ideograph height is h_dots bulbs.
    Returns (mask float32 HxW, list of (x0, x1) bulb columns for each character)."""
    if path == FONT_PIX:
        # bitmap font: render at native 16 px per em then scale by integer factor
        k = max(1, int(round(h_dots / 16)))
        f = font(path, 16)
        boxes = []
        x = 0
        widths = [f.getlength(c) for c in text]
        tw = int(sum(widths) + track * 16 * (len(text) - 1)) + 2
        im = Image.new('L', (max(1, tw), 18), 0)
        d = ImageDraw.Draw(im)
        for c, wdt in zip(text, widths):
            d.text((x, 0), c, font=f, fill=255)
            boxes.append((x * k, (x + wdt) * k))
            x += wdt + track * 16
        a = (np.asarray(im, np.float32) / 255.0 > 0.5).astype(np.float32)
        a = np.kron(a, np.ones((k, k), np.float32))
        return a, boxes
    size = int(h_dots * SS / 0.80)          # em so that ideographs/caps are ~h_dots tall
    f = font(path, size)
    widths = [f.getlength(c) for c in text]
    asc, desc = f.getmetrics()
    pad = 2 * SS
    tw = int(sum(widths) + track * size * max(0, len(text) - 1)) + 2 * pad
    th = asc + desc + 2 * pad
    im = Image.new('L', (tw, th), 0)
    d = ImageDraw.Draw(im)
    x = pad
    boxes = []
    for c, wdt in zip(text, widths):
        d.text((x, pad), c, font=f, fill=255)
        boxes.append(((x) / SS, (x + wdt) / SS))
        x += wdt + track * size
    a = np.asarray(im, np.float32) / 255.0
    # crop vertically to ink
    rows = np.where(a.max(1) > 0.05)[0]
    if len(rows):
        a = a[max(0, rows[0] - SS):rows[-1] + SS + 1]
    gw = max(1, int(round(a.shape[1] / SS)))
    gh = max(1, int(round(a.shape[0] / SS)))
    g = cv2.resize(a, (gw, gh), interpolation=cv2.INTER_AREA)
    # LED quantisation: bulbs are mostly on or off, a little grey keeps curves readable
    g = np.clip((g - (0.5 - sharp * 0.5) * 0.6) / (1 - (0.5 - sharp * 0.5) * 0.6 * 1.6 + 1e-6), 0, 1)
    g = g ** 0.8
    return g.astype(np.float32), [(b0 - pad / SS, b1 - pad / SS) for b0, b1 in boxes]


CJK_RE = __import__('re').compile(r'[\u2e80-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef“”—…·]')
# ink geometry per font (fraction of em): CJK ideograph spans -0.819..+0.093 around the baseline,
# Anton caps -0.860..0
_CJK_TOP, _CJK_BOT = 0.819, 0.093
_LAT_TOP = 0.860
LAT_SCALE = 0.94      # Latin caps a touch shorter than ideographs


@functools.lru_cache(maxsize=4096)
def row_mask(text, h_dots, zh_font=None, en_font=None, track=0.06, upper=True):
    """Mixed CJK/Latin row on the bulb grid. Ideographs and Latin caps are h_dots bulbs tall, centred on
    the same line. Returns (mask float32, per-character [x0, x1) bulb spans)."""
    zh_font = zh_font or FONT_ZH
    en_font = en_font or FONT_EN
    s_cjk = h_dots * SS / (_CJK_TOP + _CJK_BOT)
    s_lat = h_dots * LAT_SCALE * SS / _LAT_TOP
    fz, fe = font(zh_font, int(round(s_cjk))), font(en_font, int(round(s_lat)))
    hpx = h_dots * SS
    pad = 3 * SS
    centre = pad + hpx / 2
    base_z = centre + (_CJK_TOP - _CJK_BOT) / 2 * s_cjk     # baseline so the ideograph box is centred
    base_e = centre + _LAT_TOP / 2 * s_lat
    items = []
    x = pad
    for c in text:
        cjk = bool(CJK_RE.match(c))
        f = fz if cjk else fe
        ch = c if (cjk or not upper) else c.upper()
        if c == ' ':
            w = (0.42 if cjk else 0.30) * (s_cjk if cjk else s_lat)
            w = 0.36 * s_cjk
        else:
            w = f.getlength(ch)
        items.append((x, w, ch, f, base_z if cjk else base_e))
        x += w + (track * s_cjk if c != ' ' else 0)
    tw = int(x + pad)
    th = int(hpx + 2 * pad)
    im = Image.new('L', (max(tw, 1), th), 0)
    d = ImageDraw.Draw(im)
    for x0, w, ch, f, base in items:
        if ch.strip():
            d.text((x0, base), ch, font=f, fill=255, anchor='ls')
    a = np.asarray(im, np.float32) / 255.0
    gh = int(round(th / SS))
    gw = int(round(tw / SS))
    g = cv2.resize(a, (gw, gh), interpolation=cv2.INTER_AREA)
    g = np.clip((g - 0.12) / 0.6, 0, 1) ** 0.85
    spans = [((x0) / SS, (x0 + w) / SS) for x0, w, *_ in items]
    return g.astype(np.float32), spans


def text_width(text, path, h_dots, track=0.0):
    m, _ = glyph_mask(text, path, h_dots, 0.5, track)
    return m.shape[1]


def stamp(field, mask, x, y, color, gain=1.0):
    """add mask*color into field at bulb (x, y) (top-left), clipped."""
    h, w = mask.shape
    x, y = int(round(x)), int(round(y))
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(GW, x + w), min(GH, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    m = mask[y0 - y:y1 - y, x0 - x:x1 - x]
    field[y0:y1, x0:x1] += m[..., None] * (np.asarray(color, np.float32) * gain)


def finish(img, t, grain=0.05, vignette=0.35, rng=None, exposure=1.0):
    """tone-map, vignette, grain -> uint8."""
    x = img * exposure
    x = 1.0 - np.exp(-x * 1.35)
    if vignette:
        x *= VIG[..., None] ** vignette
    if grain:
        g = GRAIN[int(t * 30) % len(GRAIN)]
        x = x + (g[..., None] - 0.5) * grain
    x = np.clip(x, 0, 1) ** (1 / 1.15)
    return (x * 255 + 0.5).astype(np.uint8)


def _vig():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((x - W / 2) / (W * 0.62), (y - H / 2) / (H * 0.62))
    return np.clip(1.15 - r ** 2 * 0.55, 0.25, 1).astype(np.float32)


VIG = _vig()
_r = np.random.default_rng(7)
GRAIN = [cv2.GaussianBlur(_r.random((H, W), np.float32), (0, 0), 0.7) * 1.6 - 0.3 for _ in range(12)]
