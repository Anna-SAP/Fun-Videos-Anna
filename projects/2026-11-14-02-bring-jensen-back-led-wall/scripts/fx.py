"""Frame-level effects: camera, crowd silhouettes in front of the wall, glitch, chromatic split."""
import functools

import cv2
import numpy as np

from led import H, W


def camera(img, zoom=1.0, cx=0.5, cy=0.5, dx=0.0, dy=0.0, rot=0.0):
    """zoom >= 1 into the wall around (cx, cy) (fractions), then shift by (dx, dy) px and rotate (deg)."""
    if abs(zoom - 1) < 1e-4 and abs(dx) < 0.05 and abs(dy) < 0.05 and abs(rot) < 1e-3:
        return img
    px, py = cx * W, cy * H
    M = cv2.getRotationMatrix2D((px, py), rot, zoom)
    M[0, 2] += (W / 2 - px) + dx
    M[1, 2] += (H / 2 - py) + dy
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))


def chroma(img, px):
    """lateral colour split by px pixels (red right, blue left)."""
    k = int(round(px))
    if k < 1:
        return img
    out = img.copy()
    out[:, k:, 0] = img[:, :-k, 0]
    out[:, :-k, 2] = img[:, k:, 2]
    return out


def glitch(img, amount, seed):
    """horizontal tearing bands + dropouts; amount 0..1."""
    if amount <= 0.01:
        return img
    rng = np.random.default_rng(seed)
    out = img.copy()
    n = int(3 + 14 * amount)
    for _ in range(n):
        y0 = int(rng.integers(0, H - 8))
        hh = int(rng.integers(6, int(20 + 160 * amount)))
        sh = int(rng.normal(0, 90 * amount))
        band = out[y0:y0 + hh]
        out[y0:y0 + hh] = np.roll(band, sh, axis=1)
        if rng.random() < 0.25 * amount:
            out[y0:y0 + hh] *= rng.uniform(0.0, 0.4)
        if rng.random() < 0.3 * amount:
            c = int(rng.integers(0, 3))
            out[y0:y0 + hh, :, c] = np.roll(out[y0:y0 + hh, :, c], int(rng.normal(0, 30)), axis=1)
    return chroma(out, 6 * amount)


@functools.lru_cache(maxsize=1)
def _crowd_layout(n=11, seed=3):
    rng = np.random.default_rng(seed)
    xs = np.linspace(-0.04, 1.04, n) + rng.normal(0, 0.018, n)
    return [dict(x=float(x), s=float(rng.uniform(0.86, 1.18)), ph=float(rng.uniform(0, 6.28)),
                 arm=int(rng.integers(0, 3)), lag=float(rng.uniform(0, 0.12)), side=int(rng.integers(0, 2)))
            for x in xs]


def crowd_mask(t, bounce, raise_amt, rows=1, height=0.17, seed=3):
    """silhouettes of heads and shoulders along the bottom edge (float mask at half resolution).
    bounce: 0..1 head bob (kick); raise_amt: 0..1 fists up (the crowd answering "Back!")."""
    from PIL import Image, ImageDraw
    w2, h2 = W // 2, H // 2
    im = Image.new('L', (w2, h2), 0)
    d = ImageDraw.Draw(im)
    base = h2
    for p in _crowd_layout(seed=seed):
        s = p['s'] * height * h2 / 3.3
        x = p['x'] * w2
        by = base - 0.2 * s + 6 * bounce * np.sin(p['ph'] + t * 0.0) * 0 - 10 * bounce * p['s']
        # shoulders
        d.rounded_rectangle([x - 1.25 * s, by - 1.55 * s, x + 1.25 * s, base + 40], radius=int(0.6 * s), fill=255)
        # neck + head
        d.rectangle([x - 0.28 * s, by - 2.0 * s, x + 0.28 * s, by - 1.4 * s], fill=255)
        hy = by - 2.55 * s
        d.ellipse([x - 0.62 * s, hy - 0.78 * s, x + 0.62 * s, hy + 0.72 * s], fill=255)
        # cap brim on some heads (hip-hop crowd)
        if p['arm'] == 2:
            d.rounded_rectangle([x - 0.66 * s, hy - 0.8 * s, x + 0.66 * s, hy - 0.2 * s], radius=int(0.3 * s), fill=255)
            d.rectangle([x - 0.1 * s, hy - 0.45 * s, x + 1.0 * s, hy - 0.28 * s], fill=255)
        # raised fist
        r = float(np.clip(raise_amt - p['lag'], 0, 1)) / max(1e-3, 1 - p['lag'])
        if r > 0.02 and p['arm'] != 1:
            sx = x + (0.9 if p['side'] else -0.9) * s
            sy = by - 1.3 * s
            ex = sx + (0.35 if p['side'] else -0.35) * s
            ey = sy - (0.6 + 2.6 * r) * s
            d.line([(sx, sy), (ex, ey)], fill=255, width=int(0.42 * s))
            d.rounded_rectangle([ex - 0.32 * s, ey - 0.5 * s, ex + 0.32 * s, ey + 0.15 * s], radius=int(0.12 * s), fill=255)
    m = np.asarray(im, np.float32) / 255.0
    m = cv2.GaussianBlur(m, (0, 0), 1.6)
    return m


def apply_crowd(img, m, rim_color, rim=0.9):
    """darken the wall behind silhouettes, add a thin rim of wall light on their edges."""
    M = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
    edge = np.clip(M - cv2.GaussianBlur(M, (0, 0), 3.0), 0, 1) * 2.2
    halo = cv2.GaussianBlur(M, (0, 0), 14) - M
    out = img * (1 - M[..., None] * 0.97)
    out += (edge[..., None] * rim + np.clip(halo, 0, 1)[..., None] * 0.15) * np.asarray(rim_color, np.float32)
    return out
