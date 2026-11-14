"""Pixel-art props drawn straight onto the bulb grid (1 pixel = 1 bulb).

Each prop returns a float32 mask (h, w) in 0..1 for a given time, so steam can rise, a flag can be lowered,
a line chart can draw itself. They are the film's recurring objects:
  cup      -- the diner coffee (hot in 1993, cold at the end)
  booth    -- the diner booth (卡座)
  chair    -- the CEO's seat (same man, same seat / 一张空椅子)
  jacket   -- the leather jacket on a hanger (皮衣还挂在后台), can be lowered on a pole (降半杆)
  bulb     -- the green light (绿灯亮着 没人关)
  chart    -- a price line (four trillion / 股价跌了)
  flowers  -- flowers left at the door (花还摆着)
  fist     -- a raised fist (crowd response)
"""
import functools

import numpy as np
from PIL import Image, ImageDraw


def _im(w, h):
    im = Image.new('L', (w, h), 0)
    return im, ImageDraw.Draw(im)


def _arr(im):
    return np.asarray(im, np.float32) / 255.0


@functools.lru_cache(maxsize=8)
def cup_body(s=1.0):
    w, h = int(46 * s), int(34 * s)
    im, d = _im(w, h)
    # cup: slightly tapered body, rim highlight, handle ring, saucer
    bw = int(28 * s)
    x0 = int(6 * s)
    top, bot = int(4 * s), int(26 * s)
    d.polygon([(x0, top), (x0 + bw, top), (x0 + bw - 3 * s, bot), (x0 + 3 * s, bot)], fill=150)
    d.line([(x0, top), (x0 + bw, top)], fill=255, width=max(1, int(2 * s)))
    d.ellipse([x0 + bw - 4 * s, top + 5 * s, x0 + bw + 9 * s, top + 17 * s], outline=200, width=max(1, int(3 * s)))
    # stripe on the cup (diner mug band)
    d.line([(x0 + 1.5 * s, top + 7 * s), (x0 + bw - 1.5 * s, top + 7 * s)], fill=255, width=max(1, int(2 * s)))
    d.rounded_rectangle([0, bot, w - 1, bot + 4 * s], radius=int(2 * s), fill=210)
    return _arr(im)


def steam(t, s=1.0, heat=1.0, seed=0):
    """three wisps rising above the cup; heat 0 = cold (none)."""
    w, h = int(46 * s), int(30 * s)
    out = np.zeros((h, w), np.float32)
    if heat <= 0.01:
        return out
    yy = np.arange(h, dtype=np.float32)
    for k in range(3):
        x_base = (12 + 8 * k) * s
        ph = t * 1.3 + k * 2.1 + seed
        # wisp = sequence of points drifting upward, swaying
        for i in range(0, int(h), 1):
            y = h - 1 - i
            amp = (2.0 + 2.2 * i / h) * s
            x = x_base + amp * np.sin(ph * 2.2 - i * 0.28 * (1 / s) + k)
            life = (i / h)
            a = heat * (1 - life) ** 0.8 * (0.55 + 0.45 * np.sin(ph * 3 - i * 0.35)) ** 2
            xi = int(round(x))
            if 0 <= xi < w:
                out[y, xi] = max(out[y, xi], a)
    return out


@functools.lru_cache(maxsize=4)
def booth(s=1.0):
    """two high-backed booth benches facing each other across a table (side view)."""
    w, h = int(118 * s), int(64 * s)
    im, d = _im(w, h)
    # left bench back + seat
    d.rounded_rectangle([0, 0, 16 * s, h - 1], radius=int(6 * s), outline=255, width=max(1, int(2 * s)))
    d.rectangle([3 * s, 6 * s, 13 * s, h - 22 * s], fill=70)          # tufted cushion
    for yy in range(int(10 * s), int(h - 24 * s), int(7 * s)):
        d.point([(8 * s, yy)], fill=200)
    d.rounded_rectangle([0, h - 24 * s, 34 * s, h - 16 * s], radius=int(3 * s), fill=200)
    # right bench (mirror)
    d.rounded_rectangle([w - 1 - 16 * s, 0, w - 1, h - 1], radius=int(6 * s), outline=255, width=max(1, int(2 * s)))
    d.rectangle([w - 1 - 13 * s, 6 * s, w - 1 - 3 * s, h - 22 * s], fill=70)
    for yy in range(int(10 * s), int(h - 24 * s), int(7 * s)):
        d.point([(w - 1 - 8 * s, yy)], fill=200)
    d.rounded_rectangle([w - 1 - 34 * s, h - 24 * s, w - 1, h - 16 * s], radius=int(3 * s), fill=200)
    # table: top + pedestal
    d.rectangle([38 * s, h - 34 * s, w - 1 - 38 * s, h - 31 * s], fill=255)
    d.rectangle([w / 2 - 2 * s, h - 31 * s, w / 2 + 2 * s, h - 4 * s], fill=170)
    d.rectangle([w / 2 - 12 * s, h - 4 * s, w / 2 + 12 * s, h - 2 * s], fill=170)
    # lamp over the table
    d.line([(w / 2, 0), (w / 2, 8 * s)], fill=120)
    d.polygon([(w / 2 - 9 * s, 14 * s), (w / 2 + 9 * s, 14 * s), (w / 2 + 4 * s, 8 * s), (w / 2 - 4 * s, 8 * s)], fill=255)
    return _arr(im)


@functools.lru_cache(maxsize=4)
def chair(s=1.0):
    """high-back office chair, front three-quarter view."""
    w, h = int(56 * s), int(90 * s)
    im, d = _im(w, h)
    cx = w / 2
    # backrest
    d.rounded_rectangle([cx - 20 * s, 0, cx + 20 * s, 44 * s], radius=int(12 * s), fill=120, outline=255, width=max(1, int(2 * s)))
    d.rounded_rectangle([cx - 13 * s, 6 * s, cx + 13 * s, 36 * s], radius=int(8 * s), outline=190, width=1)
    # armrests
    d.rounded_rectangle([cx - 27 * s, 46 * s, cx - 19 * s, 50 * s], radius=int(2 * s), fill=220)
    d.rounded_rectangle([cx + 19 * s, 46 * s, cx + 27 * s, 50 * s], radius=int(2 * s), fill=220)
    d.line([(cx - 22 * s, 50 * s), (cx - 18 * s, 56 * s)], fill=180, width=max(1, int(2 * s)))
    d.line([(cx + 22 * s, 50 * s), (cx + 18 * s, 56 * s)], fill=180, width=max(1, int(2 * s)))
    # seat
    d.rounded_rectangle([cx - 22 * s, 52 * s, cx + 22 * s, 60 * s], radius=int(4 * s), fill=255)
    # gas lift
    d.rectangle([cx - 2 * s, 60 * s, cx + 2 * s, 74 * s], fill=200)
    # star base + casters
    for dx, dy in [(-22, 82), (22, 82), (-11, 86), (11, 86), (0, 80)]:
        d.line([(cx, 75 * s), (cx + dx * s, dy * s)], fill=220, width=max(1, int(2 * s)))
        d.ellipse([cx + dx * s - 2 * s, dy * s - 1 * s, cx + dx * s + 2 * s, dy * s + 3 * s], fill=255)
    return _arr(im)


@functools.lru_cache(maxsize=4)
def jacket(s=1.0):
    """a leather jacket on a hanger: hook, shoulders, lapels, zip, cuffs."""
    w, h = int(70 * s), int(84 * s)
    im, d = _im(w, h)
    cx = w / 2
    # hanger hook + bar
    d.arc([cx - 4 * s, 0, cx + 4 * s, 8 * s], 180, 360 + 90, fill=255, width=1)
    d.line([(cx, 6 * s), (cx, 10 * s)], fill=255)
    d.line([(cx, 10 * s), (cx - 24 * s, 18 * s)], fill=255, width=max(1, int(2 * s)))
    d.line([(cx, 10 * s), (cx + 24 * s, 18 * s)], fill=255, width=max(1, int(2 * s)))
    # body
    body = [(cx - 24 * s, 16 * s), (cx - 6 * s, 12 * s), (cx + 6 * s, 12 * s), (cx + 24 * s, 16 * s),
            (cx + 32 * s, 24 * s), (cx + 34 * s, 70 * s), (cx + 26 * s, 72 * s), (cx + 22 * s, 36 * s),
            (cx + 22 * s, 78 * s), (cx - 22 * s, 78 * s), (cx - 22 * s, 36 * s), (cx - 26 * s, 72 * s),
            (cx - 34 * s, 70 * s), (cx - 32 * s, 24 * s)]
    d.polygon(body, fill=95, outline=255)
    # collar / lapels
    d.polygon([(cx - 6 * s, 12 * s), (cx - 14 * s, 14 * s), (cx - 8 * s, 34 * s), (cx - 1 * s, 22 * s)], fill=200)
    d.polygon([(cx + 6 * s, 12 * s), (cx + 14 * s, 14 * s), (cx + 8 * s, 34 * s), (cx + 1 * s, 22 * s)], fill=200)
    # zip (asymmetric moto zip)
    d.line([(cx + 2 * s, 24 * s), (cx + 6 * s, 76 * s)], fill=255, width=1)
    # pockets, belt, cuffs
    d.line([(cx - 16 * s, 46 * s), (cx - 9 * s, 52 * s)], fill=230, width=1)
    d.line([(cx + 12 * s, 46 * s), (cx + 18 * s, 52 * s)], fill=230, width=1)
    d.rectangle([cx - 22 * s, 72 * s, cx + 22 * s, 75 * s], fill=170)
    d.line([(cx - 34 * s, 66 * s), (cx - 26 * s, 68 * s)], fill=230)
    d.line([(cx + 34 * s, 66 * s), (cx + 26 * s, 68 * s)], fill=230)
    return _arr(im)


@functools.lru_cache(maxsize=8)
def bulb(r=10):
    """one big round signal light with a hot core."""
    n = 2 * r + 1
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    d = np.hypot(x - r, y - r) / r
    disc = np.clip((1.02 - d) * 6, 0, 1)
    core = np.exp(-(d / 0.55) ** 2)
    return (disc * (0.55 + 0.75 * core)).astype(np.float32)


def chart(w, h, values, progress=1.0, fill=0.18):
    """price line through `values` (0..1), drawn up to `progress` (0..1) of its length, with faint fill."""
    im, d = _im(w, h)
    n = len(values)
    pts = [(i / (n - 1) * (w - 1), (1 - v) * (h - 3) + 1) for i, v in enumerate(values)]
    k = progress * (n - 1)
    kk = int(np.floor(k))
    show = pts[:kk + 1]
    if kk + 1 < n:
        f = k - kk
        x0, y0 = pts[kk]
        x1, y1 = pts[kk + 1]
        show = show + [(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)]
    if len(show) >= 2:
        d.polygon(show + [(show[-1][0], h - 1), (0, h - 1)], fill=int(255 * fill))
        d.line(show, fill=255, width=1, joint='curve')
        hx, hy = show[-1]
        d.ellipse([hx - 1.5, hy - 1.5, hx + 1.5, hy + 1.5], fill=255)
    return _arr(im)


@functools.lru_cache(maxsize=4)
def flowers(s=1.0):
    w, h = int(44 * s), int(46 * s)
    im, d = _im(w, h)
    heads = [(10, 10), (22, 5), (33, 11), (16, 17), (28, 18)]
    for hx, hy in heads:
        d.line([(hx * s, (hy + 4) * s), (w / 2, h - 12 * s)], fill=150, width=1)
    for hx, hy in heads:
        for a in range(5):
            ang = a / 5 * 2 * np.pi
            px, py = hx * s + 3 * s * np.cos(ang), hy * s + 3 * s * np.sin(ang)
            d.ellipse([px - 2 * s, py - 2 * s, px + 2 * s, py + 2 * s], fill=230)
        d.ellipse([hx * s - 1.2 * s, hy * s - 1.2 * s, hx * s + 1.2 * s, hy * s + 1.2 * s], fill=120)
    # paper wrap
    d.polygon([(w / 2 - 12 * s, h - 22 * s), (w / 2 + 12 * s, h - 22 * s), (w / 2 + 4 * s, h - 1), (w / 2 - 4 * s, h - 1)],
              fill=110, outline=255)
    return _arr(im)


def stamp_prop(field, mask, x, y, color, gain=1.0):
    from led import stamp
    stamp(field, mask, x, y, color, gain)
