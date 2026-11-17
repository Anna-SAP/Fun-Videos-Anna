"""The two places that are not a door.

tower      the Taipei interlude: night over the water, a stepped tower whose whole facade is a wall of light
           (the lyric that names the wall is lit on it as LED dots)
broadcast  the intro's TV: scanlines, a lower-third bar for the news sample, static
"""
import math
import os

import cv2
import numpy as np

from common import H, W, hash01, noise2

TEX = 'work/tex'
TW, TH = 2300, 3500
TCX = TW // 2


def tower_segments():
    """(y_top, y_bottom, half_width_top, half_width_bottom) of the stacked, flared segments."""
    segs = []
    y = 640
    for i in range(8):
        h = 250
        segs.append((y, y + h, 205, 150))
        y += h
    # podium
    segs.append((y, y + 380, 260, 330))
    return segs, y + 380


def build_tower():
    yy = np.linspace(0, 1, TH, dtype=np.float32)[:, None]
    sky = np.zeros((TH, TW, 3), np.float32)
    top = np.array([0.006, 0.01, 0.03], np.float32)
    hor = np.array([0.05, 0.035, 0.07], np.float32)
    sky[:] = (top * (1 - yy[..., None]) + hor * yy[..., None])
    rng = np.random.default_rng(101)
    for _ in range(900):
        x, y = rng.integers(0, TW), rng.integers(0, int(TH * 0.6))
        b = rng.random() ** 3 * 0.5
        sky[y, x] += b
    sky = cv2.GaussianBlur(sky, (0, 0), 0.7)
    mask = np.zeros((TH, TW), np.float32)
    segs, ground = tower_segments()
    for (a, b, wt, wb) in segs:
        pts = np.array([[TCX - wb, b], [TCX - wt, a], [TCX + wt, a], [TCX + wb, b]], np.int32)
        cv2.fillPoly(mask, [pts], 1.0, cv2.LINE_AA)
    # crown and spire
    cv2.rectangle(mask, (TCX - 120, 470), (TCX + 120, 640), 1.0, -1)
    cv2.rectangle(mask, (TCX - 60, 300), (TCX + 60, 470), 1.0, -1)
    cv2.rectangle(mask, (TCX - 12, 40), (TCX + 12, 300), 1.0, -1)
    # city skyline at the bottom
    x = 0
    while x < TW:
        w = int(rng.integers(60, 180))
        h = int(rng.integers(120, 520))
        if abs(x + w / 2 - TCX) > 380:
            cv2.rectangle(mask, (x, ground - h), (x + w, TH), 0.85, -1)
        x += w + int(rng.integers(0, 30))
    cv2.rectangle(mask, (0, ground), (TW, TH), 1.0, -1)
    body = np.array([0.012, 0.016, 0.028], np.float32)
    img = sky * (1 - mask[..., None]) + body * mask[..., None]
    # window dots on the skyline and the tower, dim
    win = (rng.random((TH // 14, TW // 10)) < 0.18).astype(np.float32) * rng.random((TH // 14, TW // 10)).astype(np.float32)
    win = cv2.resize(win, (TW, TH), interpolation=cv2.INTER_NEAREST)
    grid = ((np.arange(TH)[:, None] % 14 < 6) & (np.arange(TW)[None, :] % 10 < 5)).astype(np.float32)
    img += (win * grid * (mask > 0.5))[..., None] * np.array([0.10, 0.08, 0.04], np.float32)
    # edge highlights of the tower segments (city glow from below)
    edge = cv2.Canny((mask * 255).astype(np.uint8), 50, 150).astype(np.float32) / 255.0
    img += cv2.GaussianBlur(edge, (0, 0), 1.0)[..., None] * np.array([0.05, 0.06, 0.09], np.float32)
    # the facade area that can light up (the shaft), as a mask
    facade = np.zeros((TH, TW), np.float32)
    for (a, b, wt, wb) in segs[:8]:
        pts = np.array([[TCX - wb + 14, b - 12], [TCX - wt + 14, a + 12], [TCX + wt - 14, a + 12], [TCX + wb - 14, b - 12]], np.int32)
        cv2.fillPoly(facade, [pts], 1.0)
    # reflections of the city on the water (bottom strip)
    return img, facade


_tw = None


def tower_world():
    global _tw
    if _tw is not None:
        return _tw
    os.makedirs(TEX, exist_ok=True)
    p = f'{TEX}/tower'
    if not os.path.exists(p + '_base.png'):
        img, fac = build_tower()
        cv2.imwrite(p + '_base.png', (np.clip(img, 0, 1) * 255)[..., ::-1].astype(np.uint8))
        cv2.imwrite(p + '_facade.png', (fac * 255).astype(np.uint8))
    _tw = {'base': cv2.imread(p + '_base.png')[..., ::-1].copy(), 'facade': cv2.imread(p + '_facade.png', 0)}
    return _tw


def tower_view(cam, fill=1.0):
    from typo import cam_xform
    w = tower_world()
    M = cam_xform(cam)
    base = cv2.warpAffine(w['base'], M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    fac = cv2.warpAffine(w['facade'], M, (W, H), flags=cv2.INTER_LINEAR).astype(np.float32) / 255.0
    return base.astype(np.float32) * (fill / 255.0), fac


_dots = {}


def dotgrid(pitch=12, r=0.42):
    """Screen-space LED dot pattern (1 inside round dots, soft edges)."""
    key = (pitch, r)
    if key not in _dots:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        u = (xx % pitch) / pitch - 0.5
        v = (yy % pitch) / pitch - 0.5
        d = np.sqrt(u * u + v * v)
        _dots[key] = np.clip((r - d) / 0.08, 0, 1).astype(np.float32)
    return _dots[key]


def static(t, amt):
    """TV static (screen space, 0..1)."""
    rng = np.random.default_rng(int(t * 30) + 7)
    s = rng.random((H // 3, W // 3)).astype(np.float32)
    s = cv2.resize(s, (W, H), interpolation=cv2.INTER_NEAREST)
    return s * amt


def ripple(t, cx, cy, t0, speed=900.0, width=60.0):
    """A ring of light expanding from (cx, cy) since t0 (screen space): the knock's shock wave."""
    a = t - t0
    if a < 0 or a > 1.2:
        return None
    yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32) * 4
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    r = a * speed
    ring = np.exp(-((d - r) / width) ** 2) * (1 - a / 1.2) ** 2
    return cv2.resize(ring.astype(np.float32), (W, H))


_ = (math, hash01, noise2)
