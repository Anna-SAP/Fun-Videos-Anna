"""Procedural doors. Each door lives in a 'world' image larger than the frame: the door itself, its frame,
the wall around it and the floor in front, so the camera can sit against the door (lyrics fill the frame)
or pull back until the whole closed door and the line of light under it are in view.

world(style) -> dict(base=uint8 HxWx3, gap=uint8 HxW, spill=uint8 HxW, door=(x0, y0, x1, y1))
  base   the front of everything, lit only by a weak fill from our side
  gap    where light from behind gets through by itself: the slit under the door and around its frame
  spill  how much of that light lands on the floor and the frame in front of the door (0..255)
Worlds are cached as PNGs under work/tex/ so every render process loads them instead of rebuilding.

Styles
  wood    the front door (正门): six recessed panels, dark stained wood, brass handle
  steel   the war-room door: brushed steel, rivets, a wired-glass slot
  white   Washington: tall painted double door with mouldings, in shadow
  board   the board room: walnut double door, vertical grain, a blank brass plate
  vault   the closed room in Congress: heavy padded double door with studs
"""
import os

import cv2
import numpy as np

from common import noise2

WW, WH = 2300, 3500           # world size
DW, DH = 1080, 2520           # door leaf size (one leaf, or both leaves of a double door together)
DX0 = (WW - DW) // 2
DY0 = 260
FLOOR = DY0 + DH + 14         # floor line (bottom of the door gap)
TEX = 'work/tex'


def _grain(h, w, seed, stretch=60, tone=(0.32, 0.18, 0.10)):
    """Vertical wood grain: long streaks (anisotropic noise) plus a few gently wandering growth lines."""
    rng = np.random.default_rng(seed)

    def aniso(sy, sx, sd):
        g = np.random.default_rng(sd).random((max(2, h // sy), max(2, w // sx))).astype(np.float32)
        return cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)

    streak = 0.5 * aniso(220, 6, seed) + 0.3 * aniso(500, 14, seed + 1) + 0.2 * aniso(60, 3, seed + 2)
    wander = (aniso(700, 300, seed + 3) - 0.5) * 40
    xs = np.arange(w, dtype=np.float32)[None, :] + wander
    lines = 0.5 + 0.5 * np.sin(xs * 0.075 + aniso(900, 200, seed + 4) * 4)
    g = 0.62 + 0.22 * streak + 0.16 * lines ** 4
    g *= 0.88 + 0.24 * noise2(h, w, 400, seed + 5, 2)
    col = np.stack([g * tone[0], g * tone[1], g * tone[2]], -1)
    _ = (rng, stretch)
    return col.astype(np.float32)


def _bevel_rect(img, x0, y0, x1, y1, depth, k=0.55, inset=True):
    """Shade a rectangle's border as a 45-degree bevel lit from the upper left."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dl, dr, dt, db = xx - x0, x1 - 1 - xx, yy - y0, y1 - 1 - yy
    d = np.minimum(np.minimum(dl, dr), np.minimum(dt, db))
    band = (d < depth).astype(np.float32)
    # which side is closest -> facing direction
    side = np.argmin(np.stack([dl, dr, dt, db]), 0)
    light = np.choose(side, [1.0, -1.0, 1.0, -1.0]).astype(np.float32)
    if inset:
        light = -light
    shade = 1.0 + band * light * k
    img[y0:y1, x0:x1] *= shade[..., None]
    # a thin dark line at the outer and inner edges of the bevel
    edge = ((d < 2) | ((d > depth - 2) & (d < depth))).astype(np.float32)
    img[y0:y1, x0:x1] *= (1 - 0.35 * edge)[..., None]


def _panel_grid(img, x0, y0, x1, y1, rows, cols, margin, gap, depth, k=0.5):
    pw = (x1 - x0 - 2 * margin - (cols - 1) * gap) / cols
    heights = rows
    tot = sum(heights)
    avail = y1 - y0 - 2 * margin - (len(heights) - 1) * gap
    y = y0 + margin
    for hfrac in heights:
        ph = avail * hfrac / tot
        for c in range(cols):
            px = x0 + margin + c * (pw + gap)
            _bevel_rect(img, int(px), int(y), int(px + pw), int(y + ph), depth, k)
        y += ph + gap


def _wall(seed, tone=(0.075, 0.072, 0.07)):
    n = noise2(WH, WW, 90, seed, 4)
    n2 = noise2(WH, WW, 6, seed + 9, 1)
    v = 0.75 + 0.35 * n + 0.08 * n2
    return np.stack([v * tone[0], v * tone[1], v * tone[2]], -1).astype(np.float32)


def _floor(img, seed, tone=(0.05, 0.045, 0.04)):
    h = WH - FLOOR
    n = noise2(h, WW, 40, seed, 3)
    planks = (0.85 + 0.15 * np.sin(np.arange(WW)[None, :] * 0.018 + n * 3)).astype(np.float32)
    v = (0.7 + 0.4 * n) * planks
    img[FLOOR:] = np.stack([v * tone[0], v * tone[1], v * tone[2]], -1)


def _frame(img, x0, y0, x1, y1, w=70, tone=(0.09, 0.08, 0.075)):
    """Door casing around the opening."""
    t = np.array(tone, np.float32)
    img[y0 - w:y0, x0 - w:x1 + w] = t * 1.15
    img[y0 - w:FLOOR, x0 - w:x0] = t
    img[y0 - w:FLOOR, x1:x1 + w] = t * 0.8
    _bevel_rect(img, x0 - w, y0 - w, x1 + w, FLOOR, 18, 0.35, inset=False)


def _handle(img, cx, cy, s=1.0, col=(0.42, 0.32, 0.14)):
    c = np.array(col, np.float32)
    r = int(36 * s)
    yy, xx = np.mgrid[-r * 3:r * 3, -r * 3:r * 3].astype(np.float32)
    plate = (np.abs(xx) < r * 0.75) & (np.abs(yy) < r * 2.6)
    knob = (xx ** 2 + (yy + r * 0.2) ** 2) < (r * 1.05) ** 2
    sh = np.clip(1.0 - (xx + yy) / (r * 4), 0.35, 1.3)
    sub = img[cy - r * 3:cy + r * 3, cx - r * 3:cx + r * 3]
    m = (plate | knob)[..., None]
    spec = np.exp(-((xx + r * 0.35) ** 2 + (yy + r * 0.55) ** 2) / (r * 0.25) ** 2)[..., None]
    sub[:] = np.where(m, c * sh[..., None] * 0.5 + spec * 0.35, sub)
    # keyhole
    kh = ((xx ** 2 + (yy - r * 1.4) ** 2) < (r * 0.22) ** 2) | ((np.abs(xx) < r * 0.09) & (yy > r * 1.4) & (yy < r * 1.95))
    sub[kh] = 0.0


def _gap_masks(x0, y0, x1, y1, double=False):
    gap = np.zeros((WH, WW), np.float32)
    gap[y1:FLOOR, x0 + 6:x1 - 6] = 1.0          # under the door: the bright slit
    gap[y0 - 3:y1, x0 - 3:x0] = 0.35             # hinge side, thin
    gap[y0 - 3:y1, x1:x1 + 3] = 0.45             # latch side
    gap[y0 - 3:y0, x0:x1] = 0.3
    if double:
        cx = (x0 + x1) // 2
        gap[y0:y1, cx - 2:cx + 2] = 0.55
    # spill on the floor: a soft fan from the slit
    spill = np.zeros((WH, WW), np.float32)
    yy, xx = np.mgrid[FLOOR:WH, 0:WW].astype(np.float32)
    dy = yy - FLOOR
    cx = (x0 + x1) / 2
    half = (x1 - x0) / 2 + dy * 0.9
    fan = np.clip(1 - np.abs(xx - cx) / np.maximum(half, 1), 0, 1) ** 1.5
    spill[FLOOR:] = fan * np.exp(-dy / 420.0)
    # spill grazing the lower door/frame edge
    spill[y1 - 60:y1, x0 - 70:x1 + 70] = np.linspace(0, 0.35, 60)[:, None]
    return gap, spill


def build(style):
    seed = {'wood': 11, 'steel': 23, 'white': 37, 'board': 41, 'vault': 53}[style]
    x0, y0, x1, y1 = DX0, DY0, DX0 + DW, DY0 + DH
    img = _wall(seed)
    _floor(img, seed)
    double = style in ('white', 'board', 'vault')
    if style == 'wood':
        leaf = _grain(DH, DW, seed, tone=(0.20, 0.115, 0.07))
        _panel_grid(leaf, 0, 0, DW, DH, [1.0, 1.35, 1.0], 2, 90, 70, 34, 0.55)
        _frame(img, x0, y0, x1, y1, tone=(0.085, 0.06, 0.045))
        img[y0:y1, x0:x1] = leaf
        _handle(img, x1 - 120, y0 + int(DH * 0.53), 1.0)
    elif style == 'steel':
        n = noise2(DH, DW, 3, seed, 1)
        streak = cv2.resize(np.random.default_rng(seed).random((DH, 40)).astype(np.float32), (DW, DH))
        v = 0.5 + 0.12 * streak + 0.1 * n + 0.15 * noise2(DH, DW, 300, seed + 1, 2)
        leaf = np.stack([v * 0.13, v * 0.145, v * 0.16], -1).astype(np.float32)
        _bevel_rect(leaf, 0, 0, DW, DH, 26, 0.6, inset=False)
        _bevel_rect(leaf, 330, 330, DW - 330, 560, 16, 0.6)      # wired-glass slot (dark)
        leaf[346:544, 346:DW - 346] = 0.02
        for yy in list(range(60, DH, 160)):
            for xx in (40, DW - 40):
                cv2.circle(leaf, (xx, yy), 9, (0.3, 0.32, 0.35), -1)
                cv2.circle(leaf, (xx - 2, yy - 2), 4, (0.45, 0.47, 0.5), -1)
        cv2.rectangle(leaf, (0, DH - 300), (DW, DH - 292), (0.06, 0.06, 0.07), -1)
        _frame(img, x0, y0, x1, y1, tone=(0.06, 0.065, 0.07))
        img[y0:y1, x0:x1] = leaf
        _handle(img, x1 - 120, y0 + int(DH * 0.5), 1.0, col=(0.35, 0.36, 0.38))
    elif style == 'white':
        n = noise2(DH, DW, 200, seed, 3)
        v = 0.8 + 0.2 * n
        leaf = np.stack([v * 0.30, v * 0.31, v * 0.33], -1).astype(np.float32)
        half = DW // 2
        for lx in (0, half):
            _panel_grid(leaf, lx, 0, lx + half, DH, [0.55, 1.6, 1.0], 1, 70, 60, 28, 0.45)
        _frame(img, x0, y0, x1, y1, w=95, tone=(0.2, 0.2, 0.21))
        img[y0:y1, x0:x1] = leaf
        _handle(img, x0 + half - 70, y0 + int(DH * 0.52), 0.8)
        _handle(img, x0 + half + 70, y0 + int(DH * 0.52), 0.8)
    elif style == 'board':
        leaf = _grain(DH, DW, seed, tone=(0.16, 0.085, 0.05))
        half = DW // 2
        _bevel_rect(leaf, 0, 0, half, DH, 22, 0.5, inset=False)
        _bevel_rect(leaf, half, 0, DW, DH, 22, 0.5, inset=False)
        _frame(img, x0, y0, x1, y1, tone=(0.07, 0.05, 0.035))
        img[y0:y1, x0:x1] = leaf
        # blank brass plate
        px0, py0 = x0 + half - 210, y0 + 360
        plate = img[py0:py0 + 120, px0:px0 + 420]
        plate[:] = np.array([0.32, 0.24, 0.11], np.float32) * (0.8 + 0.4 * np.linspace(1, 0, 420)[None, :, None])
        _bevel_rect(img, px0, py0, px0 + 420, py0 + 120, 8, 0.6, inset=False)
        for cx in (x0 + half - 50, x0 + half + 50):
            img[y0 + int(DH * 0.45):y0 + int(DH * 0.6), cx - 12:cx + 12] = (0.36, 0.27, 0.12)
    elif style == 'vault':
        n = noise2(DH, DW, 120, seed, 3)
        v = 0.75 + 0.25 * n
        leaf = np.stack([v * 0.17, v * 0.06, v * 0.055], -1).astype(np.float32)   # oxblood padding
        half = DW // 2
        for lx in (0, half):
            _bevel_rect(leaf, lx, 0, lx + half, DH, 30, 0.5, inset=False)
            for yy in range(90, DH - 60, 120):
                for xx in range(lx + 70, lx + half - 40, 120):
                    o = 60 if (yy // 120) % 2 else 0
                    cv2.circle(leaf, (xx + o if xx + o < lx + half - 40 else xx, yy), 8, (0.33, 0.25, 0.12), -1)
        _frame(img, x0, y0, x1, y1, w=110, tone=(0.06, 0.045, 0.04))
        img[y0:y1, x0:x1] = leaf
    gap, spill = _gap_masks(x0, y0, x1, y1, double)
    return {'base': img, 'gap': gap, 'spill': spill, 'door': (x0, y0, x1, y1)}


_cache = {}


def world(style):
    if style in _cache:
        return _cache[style]
    os.makedirs(TEX, exist_ok=True)
    p = f'{TEX}/{style}'
    if not os.path.exists(p + '_base.png'):
        w = build(style)
        cv2.imwrite(p + '_base.png', (np.clip(w['base'], 0, 1) * 255)[..., ::-1].astype(np.uint8))
        cv2.imwrite(p + '_gap.png', (np.clip(w['gap'], 0, 1) * 255).astype(np.uint8))
        cv2.imwrite(p + '_spill.png', (np.clip(w['spill'], 0, 1) * 255).astype(np.uint8))
    base = cv2.imread(p + '_base.png')[..., ::-1].copy()
    gap = cv2.imread(p + '_gap.png', 0)
    spill = cv2.imread(p + '_spill.png', 0)
    _cache[style] = {'base': base, 'gap': gap, 'spill': spill, 'door': (DX0, DY0, DX0 + DW, DY0 + DH)}
    return _cache[style]


if __name__ == '__main__':
    import sys
    for s in sys.argv[1:] or ['wood', 'steel', 'white', 'board', 'vault']:
        if os.path.exists(f'{TEX}/{s}_base.png'):
            os.remove(f'{TEX}/{s}_base.png')
        w = world(s)
        small = cv2.resize(w['base'], (WW // 4, WH // 4))
        g = cv2.resize(w['gap'], (WW // 4, WH // 4))
        out = np.clip(small.astype(np.float32) * 2.2 + g[..., None] * np.array([0.6, 1.0, 0.7]), 0, 255).astype(np.uint8)
        cv2.imwrite(f'work/preview/door_{s}.jpg', out[..., ::-1])
        print(s)
