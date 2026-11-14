"""Backgrounds. Each scene is a function scene(t, p, fi) -> float32 RGB (H, W, 3); p is the shot's param dict.

  diner   the 1993 booth: warm amber, three mugs, a window with the street outside (and later the green light)
  stage   keynote stage: black, an LED dot wall showing one giant word/number, sweeping spot beams
  rally   flat colour, rotating sunburst, a crowd of silhouettes with fists and signs bouncing on the kicks
  paper   newsprint: greeked columns, rules, halftone, red accents
  void    flat colour + grain (for counters and chants)
  board   the case file: dark graph paper, pinned cards, red string
  letter  warm ruled paper for the bridge
"""
import functools
import math

import cv2
import numpy as np

import girl as G
from common import (AMBER, CREAM, GREEN, GREEN_D, H, INK, PAPER, RED, W, clamp01, glyph, halftone_fast, load_rgba,
                    over, over_color, sstep)

PROPS = 'work/assets/props/'


@functools.lru_cache(maxsize=64)
def prop(name, width):
    """Premultiplied RGB + alpha of a prop scaled to `width` px."""
    rgb, a = load_rgba(PROPS + name + '.png')
    h = int(round(a.shape[0] * width / a.shape[1]))
    rgb = cv2.resize(rgb, (int(width), h), interpolation=cv2.INTER_AREA)
    a = cv2.resize(a, (int(width), h), interpolation=cv2.INTER_AREA)
    return rgb, a


def put(img, name, width, cx, cy, rot=0.0, alpha=1.0, tint=None):
    """Composite a prop centred at (cx, cy)."""
    rgb, a = prop(name, int(width))
    if rot:
        h, w = a.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), rot, 1.0)
        ext = int(math.hypot(w, h)) + 2
        M[0, 2] += (ext - w) / 2
        M[1, 2] += (ext - h) / 2
        rgb = cv2.warpAffine(rgb, M, (ext, ext))
        a = cv2.warpAffine(a, M, (ext, ext))
    if tint is not None:
        rgb = a[..., None] * np.asarray(tint, np.float32)
    h, w = a.shape
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb <= xa or yb <= ya:
        return img
    sa = a[ya - y0:yb - y0, xa - x0:xb - x0][..., None] * alpha
    img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - sa) + rgb[ya - y0:yb - y0, xa - x0:xb - x0] * alpha
    return img


def solid(color):
    return np.full((H, W, 3), np.asarray(color, np.float32), np.float32)


@functools.lru_cache(maxsize=4)
def _yy_xx():
    return np.mgrid[0:H, 0:W].astype(np.float32)


def glow(img, cx, cy, r, color, strength=1.0):
    """Additive radial glow."""
    x0, y0, x1, y1 = int(max(0, cx - 3 * r)), int(max(0, cy - 3 * r)), int(min(W, cx + 3 * r)), int(min(H, cy + 3 * r))
    if x1 <= x0 or y1 <= y0:
        return img
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    d2 = ((xx - cx) ** 2 + (yy - cy) ** 2) / (r * r)
    g = (np.exp(-d2 * 1.6) * 0.9 + np.exp(-d2 * 0.25) * 0.25) * strength
    img[y0:y1, x0:x1] += g[..., None] * np.asarray(color, np.float32)
    return img


# ---------------------------------------------------------------------------------------------------- diner
@functools.lru_cache(maxsize=4)
def _diner_base(variant):
    img = np.zeros((H, W, 3), np.float32)
    yy, xx = _yy_xx()
    wall = np.array([0.20, 0.10, 0.05], np.float32)
    img[:] = wall * (0.75 + 0.35 * (1 - yy / H))[..., None]
    for x in range(0, W, 54):   # wood panel lines
        img[:, x:x + 3] *= 0.82
    # window
    wx0, wy0, wx1, wy1 = 110, 170, 970, 930
    sky = np.array([0.03, 0.05, 0.10], np.float32)
    img[wy0:wy1, wx0:wx1] = sky * (1.2 - 0.6 * (yy[wy0:wy1, wx0:wx1] - wy0) / (wy1 - wy0))[..., None]
    rng = np.random.default_rng(3)
    for _ in range(26):   # far street bokeh
        cx, cy = rng.uniform(wx0, wx1), rng.uniform(wy0 + 380, wy1 - 40)
        col = [np.array([1.0, 0.75, 0.35]), np.array([0.9, 0.3, 0.25]), np.array([0.6, 0.7, 1.0])][rng.integers(3)]
        glow(img, cx, cy, rng.uniform(8, 22), col * 0.5, 0.55)
    img[wy0:wy1, wx0:wx1] = np.minimum(img[wy0:wy1, wx0:wx1], 1)
    # window frame + mullion
    fr = np.array([0.55, 0.55, 0.58], np.float32)
    img[wy0 - 16:wy0, wx0 - 16:wx1 + 16] = fr
    img[wy1:wy1 + 16, wx0 - 16:wx1 + 16] = fr
    img[wy0 - 16:wy1 + 16, wx0 - 16:wx0] = fr
    img[wy0 - 16:wy1 + 16, wx1:wx1 + 16] = fr
    img[wy0:wy1, 532:548] = fr
    # booth backs (red vinyl) left and right, table in the middle
    red = np.array([0.62, 0.08, 0.07], np.float32)
    for side in (-1, 1):
        cx = 540 + side * 470
        m = (((xx - cx) / 260) ** 2 + ((yy - 1130) / 330) ** 2 < 1) | ((np.abs(xx - cx) < 260) & (yy > 1130) & (yy < 1640))
        img[m] = red * (0.85 + 0.25 * np.cos((xx[m] - cx) / 40))[..., None]
        for k in range(-3, 4):   # tufting lines
            lx = int(cx + k * 64)
            if 0 <= lx < W:
                col = (m[:, lx:lx + 4])
                img[:, lx:lx + 4][col] *= 0.7
    # table top (formica + chrome edge)
    top = np.array([0.86, 0.80, 0.70], np.float32)
    img[1240:1330, 120:960] = top
    img[1330:1352, 120:960] = np.array([0.80, 0.80, 0.84], np.float32)
    img[1352:1700, 500:580] = np.array([0.45, 0.45, 0.48], np.float32)
    # checker floor
    fy = 1700
    sq = 90
    for j, y in enumerate(range(fy, H, sq)):
        for i, x in enumerate(range(-sq, W + sq, sq)):
            c = np.array([0.08, 0.07, 0.07]) if (i + j) % 2 else np.array([0.85, 0.80, 0.70])
            img[y:y + sq, max(0, x):max(0, x + sq)] = c
    return np.clip(img, 0, 1)


def _steam(img, t, cx, cy, strength, seed, phi):
    """Rising wisps from a mug: three sine-displaced bright ribbons, blurred."""
    if strength <= 0.01:
        return img
    h, w = 420, 220
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = (h - yy) / h
    acc = np.zeros((h, w), np.float32)
    for k in range(3):
        off = (k - 1) * 34
        x = w / 2 + off + 26 * np.sin(v * 5.0 + phi * 1.6 + seed * 3 + k * 2.1) * v + 10 * np.sin(v * 13 - phi * 3 + k)
        acc += np.exp(-((xx - x) / (7 + 16 * v)) ** 2) * np.maximum(np.sin(np.clip(v * math.pi, 0, math.pi)), 0) ** 1.5 * (0.6 + 0.4 * np.sin(phi * 2 + k * 1.7 + v * 4))
    acc = cv2.GaussianBlur(acc, (0, 0), 6) * 0.22 * strength
    x0, y0 = int(cx - w / 2), int(cy - h)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    img[ya:yb, xa:xb] += acc[ya - y0:yb - y0, xa - x0:xb - x0, None] * np.array([1.0, 0.95, 0.9], np.float32)
    return img


def diner(t, p, fi):
    img = _diner_base(0).copy()
    green = p.get('green', 0.0)
    if callable(green):
        green = green(t)
    if green > 0:
        flick = 1.0 + 0.05 * math.sin(t * 31) * math.sin(t * 7.3)
        glow(img, 800, 420, 70, GREEN, 1.4 * green * flick)
        glow(img, 800, 420, 260, GREEN * 0.5, 0.5 * green)
        img[170:930, 110:970] += GREEN * 0.06 * green
    # neon title sign inside the window
    neon = p.get('neon')
    if neon is not None:
        lit = neon(t) if callable(neon) else neon
        _neon_sign(img, lit, t)
    mugs = p.get('mugs', 3)
    steam = p.get('steam', 1.0)
    xs = {3: (300, 540, 780), 1: (540,), 2: (420, 660)}[mugs] if mugs else ()
    for i, x in enumerate(xs):
        put(img, 'mug', 190, x, 1190)
        _steam(img, t, x, 1110, steam, i, t)
    for name, w, cx, cy in p.get('table', ()):   # outro: flowers, candle
        put(img, name, w, cx, cy)
    if p.get('candle'):
        glow(img, p['candle'][0], p['candle'][1], 40, AMBER, 0.9 + 0.15 * math.sin(t * 17) * math.sin(t * 5.1))
    # warm grade + flicker of an old print
    flick = 1 + 0.035 * math.sin(fi * 2.7) * math.sin(fi * 0.9)
    img = img * np.array([1.06, 0.97, 0.84], np.float32) * flick
    return img


def _neon_sign(img, lit, t):
    """'BRING JENSEN BACK' as a red neon tube sign in the window; `lit` = number of words switched on (0..3)."""
    words = ['BRING', 'JENSEN', 'BACK']
    m_all = _neon_masks()
    for i, (m, x, y) in enumerate(m_all):
        on = clamp01(lit - i)
        if on <= 0:
            tube = 0.18
        else:
            tube = 0.18 + 0.82 * on * (1 - 0.08 * (math.sin(t * 40 + i) > 0.95))
        col = np.array([1.0, 0.25, 0.35], np.float32)
        h, w = m.shape
        sub = img[y:y + h, x:x + w]
        g = cv2.GaussianBlur(m, (0, 0), 14) * 1.6 + cv2.GaussianBlur(m, (0, 0), 4) * 0.8
        sub += (g * tube)[..., None] * col * 0.9
        core = m * tube
        sub[:] = sub * (1 - core[..., None]) + core[..., None] * (col * 0.4 + 0.6)
    return img


@functools.lru_cache(maxsize=1)
def _neon_masks():
    out = []
    y = 300
    for word, size in (('BRING', 150), ('JENSEN', 170), ('BACK', 190)):
        m, pad, asc, w = glyph('PermanentMarker', size, word)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        tube = np.clip(cv2.dilate(m, k) - cv2.erode(m, k), 0, 1)   # hollow tube look
        x = int(540 - m.shape[1] / 2)
        out.append((tube, x, y))
        y += int(size * 1.02)
    return out


# ---------------------------------------------------------------------------------------------------- stage
DOT = 16


@functools.lru_cache(maxsize=2)
def _dot_tile():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = (xx % DOT) - DOT / 2 + 0.5
    dy = (yy % DOT) - DOT / 2 + 0.5
    d = np.sqrt(dx * dx + dy * dy)
    return clamp01((DOT * 0.36 - d) * 0.9 + 0.5).astype(np.float32)


@functools.lru_cache(maxsize=256)
def led_mask(key, fontname='Anton', box=(40, 120, 1040, 1180), kind='text'):
    """Low-res (H/DOT x W/DOT) lit mask for a key word or prop on the LED wall."""
    gw, gh = W // DOT, H // DOT
    m = np.zeros((gh, gw), np.float32)
    x0, y0, x1, y1 = [v // DOT for v in box]
    bw, bh = x1 - x0, y1 - y0
    if kind == 'text':
        lines = key.split('\n')
        size = 200
        masks = [glyph(fontname, size, ln)[0] for ln in lines]
        tw = max(mm.shape[1] for mm in masks)
        th = sum(mm.shape[0] * 0.78 for mm in masks)
        k = min(bw / (tw / 1.0), bh / th)
        y = y0 + (bh - th * k) / 2
        for mm in masks:
            small = cv2.resize(mm, (max(1, int(mm.shape[1] * k)), max(1, int(mm.shape[0] * k))), interpolation=cv2.INTER_AREA)
            xx0 = int(x0 + (bw - small.shape[1]) / 2)
            yy0 = int(y - small.shape[0] * 0.11)
            hh, ww = small.shape
            ya, yb = max(0, yy0), min(gh, yy0 + hh)
            xa, xb = max(0, xx0), min(gw, xx0 + ww)
            m[ya:yb, xa:xb] = np.maximum(m[ya:yb, xa:xb], small[ya - yy0:yb - yy0, xa - xx0:xb - xx0])
            y += mm.shape[0] * 0.78 * k
    else:   # prop silhouette
        rgb, a = load_rgba(PROPS + key + '.png')
        k = min(bw / a.shape[1], bh / a.shape[0])
        small = cv2.resize(a, (max(1, int(a.shape[1] * k)), max(1, int(a.shape[0] * k))), interpolation=cv2.INTER_AREA)
        L = cv2.resize((rgb.mean(2) / np.maximum(a, 1e-3)), small.shape[::-1], interpolation=cv2.INTER_AREA)
        small = small * (0.45 + 0.55 * clamp01(L * 1.5 + 0.2))
        xx0 = int(x0 + (bw - small.shape[1]) / 2)
        yy0 = int(y0 + (bh - small.shape[0]) / 2)
        hh, ww = small.shape
        m[yy0:yy0 + hh, xx0:xx0 + ww] = np.maximum(m[yy0:yy0 + hh, xx0:xx0 + ww], small[:gh - yy0, :gw - xx0])
    return clamp01(m * 1.3)


def stage(t, p, fi):
    img = solid(p.get('bg', (0.015, 0.02, 0.015)))
    col = np.asarray(p.get('led', GREEN), np.float32)
    keys = p.get('keys', [])   # list of (t0, key, kind)
    cur = None
    for k in keys:
        if t >= k[0]:
            cur = k
    tile = _dot_tile()
    base = 0.07
    lit = np.zeros((H // DOT, W // DOT), np.float32)
    if cur is not None:
        lm = led_mask(cur[1], kind=cur[2] if len(cur) > 2 else 'text')
        age = t - cur[0]
        # wipe the new key on, column by column (an LED wall refreshing)
        cols = int(clamp01(age / 0.18) * lm.shape[1])
        lit[:, :cols] = lm[:, :cols]
    flick = 0.9 + 0.1 * math.sin(fi * 1.9)
    big = cv2.resize(lit, (W - W % DOT, H - H % DOT), interpolation=cv2.INTER_NEAREST)
    L = np.zeros((H, W), np.float32)
    L[:big.shape[0], :big.shape[1]] = big
    dots = tile * (base + (1 - base) * L * flick)
    img += dots[..., None] * col
    bloom = cv2.GaussianBlur(cv2.resize(L * tile, (W // 4, H // 4), interpolation=cv2.INTER_AREA), (0, 0), 6)
    img += cv2.resize(bloom, (W, H))[..., None] * col * 0.55
    # spot beams
    yy, xx = _yy_xx()
    for k in range(p.get('beams', 2)):
        ang = math.sin(t * 0.6 + k * 2.4) * 0.35 + (k - 0.5) * 0.5
        sx = 540 + (k - 0.5) * 700
        dxl = (xx - sx) * math.cos(ang) - (yy + 100) * math.sin(ang)
        width = 60 + (yy + 100) * 0.22
        beam = np.exp(-(dxl / width) ** 2) * clamp01((yy + 100) / 900) * 0.10
        img += beam[..., None] * np.array([0.9, 1.0, 0.85], np.float32)
    # floor sheen
    img[1500:] += (np.linspace(0, 0.06, H - 1500, dtype=np.float32)[:, None, None] * col)
    return img


# ---------------------------------------------------------------------------------------------------- rally
def _sunburst(img, t, color, n=16, alpha=0.25, cx=540, cy=900, spin=0.08):
    yy, xx = _yy_xx()
    ang = np.arctan2(yy - cy, xx - cx) + t * spin
    s = (np.sin(ang * n) > 0).astype(np.float32)
    s = cv2.GaussianBlur(s, (0, 0), 1.0)
    img[:] = img * (1 - alpha * s[..., None]) + np.asarray(color, np.float32) * alpha * s[..., None]
    return img


@functools.lru_cache(maxsize=4)
def _crowd_layout(seed, rows):
    rng = np.random.default_rng(seed)
    people = []
    for r in range(rows):
        y = 1660 + r * 110
        n = 9 + r * 2
        for i in range(n):
            x = (i + rng.uniform(-0.3, 0.3) + (0.5 if r % 2 else 0)) * W / n
            people.append((x, y, rng.uniform(0.85, 1.2) * (1 + r * 0.18), rng.uniform(0, 1), rng.random() < 0.35,
                           rng.random() < (0.12 if r == 0 else 0.0), r))
    return people


SIGN_WORDS = ['BACK!', '33', 'FACTS!', '给个说法', 'BACK!', '要个答案', 'TRUTH', 'BACK!']


def crowd(img, t, kick, color=INK, seed=1, rows=3, signs=True, sign_color=PAPER, sign_ink=INK, density=1.0):
    """Silhouette crowd along the bottom; each person bobs on the kicks with their own phase."""
    people = _crowd_layout(seed, rows)
    A = np.zeros((H, W), np.float32)
    sign_layer = []
    for (x, y, s, ph, fist, sign, r) in people:
        if (ph * 10) % 1 > density:
            continue
        bob = kick * 22 * s * (0.6 + 0.4 * math.sin(ph * 6.28))
        yy = y - bob
        hr = 46 * s
        cv2.ellipse(A, (int(x), int(yy - 150 * s)), (int(hr * 0.85), int(hr)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
        cv2.ellipse(A, (int(x), int(yy + 40 * s)), (int(120 * s), int(150 * s)), 0, 180, 360, 1.0, -1, cv2.LINE_AA)
        cv2.rectangle(A, (int(x - 120 * s), int(yy + 40 * s)), (int(x + 120 * s), H), 1.0, -1)
        if fist:
            up = 40 * s * kick
            ax = x + (60 if ph > 0.5 else -60) * s
            cv2.line(A, (int(ax), int(yy - 40 * s)), (int(ax + 10 * s), int(yy - 260 * s - up)), 1.0, int(34 * s), cv2.LINE_AA)
            cv2.circle(A, (int(ax + 10 * s), int(yy - 280 * s - up)), int(30 * s), 1.0, -1, cv2.LINE_AA)
        if sign and signs:
            sx = x + (-70 if ph > 0.5 else 70) * s
            top = yy - 470 * s - 30 * s * kick
            cv2.line(A, (int(sx), int(yy - 40 * s)), (int(sx), int(top + 120 * s)), 1.0, int(14 * s), cv2.LINE_AA)
            sign_layer.append((sx, top, s, (ph + seed) % 1))
    img = over_color(img, A, color)
    for (sx, top, s, ph) in sign_layer:
        w, h = int(250 * s), int(150 * s)
        x0, y0 = int(sx - w / 2), int(top)
        rot = (ph - 0.5) * 16
        _sign(img, x0, y0, w, h, SIGN_WORDS[int(ph * len(SIGN_WORDS)) % len(SIGN_WORDS)], rot, sign_color, sign_ink)
    return img


@functools.lru_cache(maxsize=64)
def _sign_sprite(w, h, word, rot):
    pad = 20
    a = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
    a[pad:pad + h, pad:pad + w] = 1
    cjk = any(ord(c) > 0x2E80 for c in word)
    m, gp, asc, gw = glyph('NotoSansSC-Black' if cjk else 'Anton', 100, word)
    k = min((w * 0.86) / max(1, gw), (h * 0.8) / (m.shape[0] * 0.75))
    sm = cv2.resize(m, (max(1, int(m.shape[1] * k)), max(1, int(m.shape[0] * k))), interpolation=cv2.INTER_AREA)
    ink = np.zeros_like(a)
    y0 = pad + (h - sm.shape[0]) // 2 + int(sm.shape[0] * 0.06)
    x0 = pad + (w - sm.shape[1]) // 2
    hh, ww = min(sm.shape[0], ink.shape[0] - y0), min(sm.shape[1], ink.shape[1] - x0)
    ink[y0:y0 + hh, x0:x0 + ww] = sm[:hh, :ww]
    M = cv2.getRotationMatrix2D((a.shape[1] / 2, a.shape[0] / 2), rot, 1)
    return cv2.warpAffine(a, M, a.shape[::-1]), cv2.warpAffine(ink, M, a.shape[::-1])


def _sign(img, x0, y0, w, h, word, rot, col, ink):
    a, m = _sign_sprite(int(w), int(h), word, round(rot))
    pad = 20
    x0 -= pad
    y0 -= pad
    hh, ww = a.shape
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + ww), min(H, y0 + hh)
    if xb <= xa or yb <= ya:
        return
    sa = a[ya - y0:yb - y0, xa - x0:xb - x0][..., None]
    sm = m[ya - y0:yb - y0, xa - x0:xb - x0][..., None]
    sub = img[ya:yb, xa:xb]
    sub[:] = sub * (1 - sa) + np.asarray(col, np.float32) * sa
    sub[:] = sub * (1 - sm) + np.asarray(ink, np.float32) * sm


def rally(t, p, fi):
    img = solid(p.get('bg', GREEN))
    if p.get('burst', True):
        _sunburst(img, t, p.get('burst_color', GREEN_D), alpha=p.get('burst_alpha', 0.22), cy=p.get('burst_y', 900))
    return img


# ---------------------------------------------------------------------------------------------------- paper
@functools.lru_cache(maxsize=4)
def _paper_base(tone):
    rng = np.random.default_rng(11)
    base = np.asarray(PAPER if tone == 0 else CREAM, np.float32)
    n = cv2.GaussianBlur(rng.standard_normal((H // 2, W // 2)).astype(np.float32), (0, 0), 1.2)
    n = cv2.resize(n, (W, H))
    fib = cv2.GaussianBlur(rng.standard_normal((H, W)).astype(np.float32), (0, 0), 0.6)
    img = base[None, None] * (1 + 0.035 * n[..., None] + 0.02 * fib[..., None])
    return np.clip(img, 0, 1).astype(np.float32)


@functools.lru_cache(maxsize=8)
def _greek(seed, cols=4, top=380, alpha=0.20):
    """Greeked newspaper columns: grey 'text lines' with ragged ends, column rules, a few boxes."""
    rng = np.random.default_rng(seed)
    A = np.zeros((H, W), np.float32)
    margin, gut = 50, 30
    cw = (W - 2 * margin - (cols - 1) * gut) / cols
    for c in range(cols):
        x0 = margin + c * (cw + gut)
        y = top
        while y < H - 40:
            if rng.random() < 0.06:
                bh = int(rng.uniform(140, 300))
                A[y:y + bh, int(x0):int(x0 + cw)] = 0.55
                y += bh + 26
                continue
            if rng.random() < 0.08:
                y += 22
                continue
            ln = cw * (rng.uniform(0.55, 1.0) if rng.random() < 0.18 else 1.0)
            A[y:y + 9, int(x0):int(x0 + ln)] = 1
            y += 19
        if c < cols - 1:
            xr = int(x0 + cw + gut / 2)
            A[top:H - 40, xr:xr + 2] = 1.2
    A[top - 30:top - 22, margin:W - margin] = 1.6
    return A * alpha


def paper(t, p, fi):
    img = _paper_base(p.get('tone', 0)).copy()
    if p.get('greek', True):
        A = _greek(p.get('seed', 1), p.get('cols', 4), p.get('top', 380), p.get('greek_alpha', 0.2))
        img *= (1 - A[..., None] * 0.9)
    if p.get('rule_red'):
        img[p.get('rule_y', 330):p.get('rule_y', 330) + 14, 50:W - 50] = RED
    return img


# ---------------------------------------------------------------------------------------------------- void / board / letter
def void(t, p, fi):
    img = solid(p.get('bg', INK))
    if p.get('burst'):
        _sunburst(img, t, p.get('burst_color', (0.1, 0.1, 0.1)), alpha=p.get('burst_alpha', 0.5), cy=p.get('burst_y', 900),
                  n=p.get('rays', 16))
    return img


@functools.lru_cache(maxsize=2)
def _board_base():
    img = solid((0.07, 0.085, 0.11))
    yy, xx = _yy_xx()
    g = (((xx % 60) < 2) | ((yy % 60) < 2)).astype(np.float32) * 0.05
    img += g[..., None] * np.array([0.5, 0.7, 1.0], np.float32)
    rng = np.random.default_rng(5)
    n = cv2.GaussianBlur(rng.standard_normal((H // 4, W // 4)).astype(np.float32), (0, 0), 3)
    img *= (1 + 0.12 * cv2.resize(n, (W, H))[..., None])
    return np.clip(img, 0, 1)


def board(t, p, fi):
    img = _board_base().copy()
    for (x0, y0, x1, y1) in p.get('strings', []):
        cv2.line(img, (int(x0), int(y0)), (int(x1), int(y1)), (0.85, 0.12, 0.1), 5, cv2.LINE_AA)
        for (x, y) in ((x0, y0), (x1, y1)):
            cv2.circle(img, (int(x), int(y)), 11, (0.9, 0.9, 0.85), -1, cv2.LINE_AA)
    return img


@functools.lru_cache(maxsize=2)
def _letter_base():
    img = _paper_base(1).copy()
    for y in range(260, H - 120, 92):
        img[y:y + 3, 60:W - 60] *= np.array([0.80, 0.86, 0.95], np.float32)
    img[:, 130:133] *= np.array([1.0, 0.75, 0.75], np.float32)
    return img


def letter(t, p, fi):
    return _letter_base().copy()


SCENES = {'diner': diner, 'stage': stage, 'rally': rally, 'paper': paper, 'void': void, 'board': board,
          'letter': letter}
