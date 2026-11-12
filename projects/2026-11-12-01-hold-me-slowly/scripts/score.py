#!/usr/bin/env python3
"""The score of the film: every time-dependent decision, read off the measurements of the song.

Measured (see storyboard.md): 59.73 BPM, beat 1.0045 s, first downbeat 2.269 s, bar 4.018 s. A breath at
3.95 s and a wordless hum 4.33-6.30 s in the intro. Verse 12.97-28.6, pre-chorus 29.38-44.85 (the low end
comes in on 29.39, the first word of "you said"), chorus 45.45-64.1 (fullest from the downbeat 46.47),
everything drops on the downbeat 62.54 and fades out to the end of the file, 65.881 s.

Lyrics are read from work/lyrics.json and timed from work/audio/lyric_timing.json; lines and words are
addressed by number here, never by their text.
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from inkwater import H, W, srgb_to_lin

FPS = 30
DUR = 65.881
NFRAMES = int(math.ceil(DUR * FPS))
BEAT = 60 / 59.73
PH = 0.260
BAR0 = 2.269


def B(bar, beat=1):
    """Song time of a bar (1-based, bar 1 = first downbeat 2.269 s) and beat (1-4)."""
    return BAR0 + (bar - 1) * 4 * BEAT + (beat - 1) * BEAT


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LYR = json.load(open(os.path.join(ROOT, 'work/lyrics.json'), encoding='utf-8'))
TIM = json.load(open(os.path.join(ROOT, 'work/audio/lyric_timing.json')))
LINES = TIM['lines']


def ws(li, wi):
    return LINES[li - 1]['words'][wi - 1]['s']


def we(li, wi):
    return LINES[li - 1]['words'][wi - 1]['e']


def ls(li):
    return LINES[li - 1]['start']


def le(li):
    return LINES[li - 1]['end']


# --------------------------------------------------------------------------------------- curves
def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def kf(t, keys):
    """Piecewise smooth interpolation through (time, value) keys; values may be tuples."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            a = ease((t - t0) / max(t1 - t0, 1e-6))
            if isinstance(v0, tuple):
                return tuple(x0 + (x1 - x0) * a for x0, x1 in zip(v0, v1))
            return v0 + (v1 - v0) * a
    return keys[-1][1]


T_PRE = ls(5)          # 29.38: "you said" and the low end
T_CH = ls(9)           # 45.45: first "hold me"
T_DROP = B(16)         # 62.54: everything drops


def fade(t):
    return ease(t / 2.4) * (1 - ease((t - 64.25) / (DUR - 64.25)))


def cool_light(t):
    return kf(t, [(0, 0.0), (2.2, 1.0), (21, 1.0), (T_PRE, 0.75), (44.5, 0.6), (47, 0.32), (T_DROP, 0.3), (DUR, 0.22)])


def warm(t):
    """Warm light 'you': (x, y, radius, intensity) in frame pixels."""
    return kf(t, [(0, (0.80 * W, 0.86 * H, 90.0, 0.0)), (ws(3, 2) - 0.2, (0.80 * W, 0.86 * H, 90.0, 0.0)),
                  (ws(3, 2) + 2.0, (0.80 * W, 0.84 * H, 150.0, 0.55)),
                  (ls(4), (0.79 * W, 0.83 * H, 170.0, 0.6)), (le(4), (0.74 * W, 0.78 * H, 280.0, 0.85)),
                  (T_PRE, (0.72 * W, 0.80 * H, 330.0, 1.15)), (T_PRE + 1.5, (0.72 * W, 0.80 * H, 300.0, 0.78)),
                  (ls(8), (0.66 * W, 0.76 * H, 300.0, 0.78)), (le(8), (0.56 * W, 0.62 * H, 280.0, 0.7)),
                  (B(12) - 0.25, (0.5 * W, 0.5 * H, 250.0, 0.62)), (B(12) + 0.15, (0.5 * W, 0.5 * H, 330.0, 1.0)),
                  (B(12) + 2.5, (0.5 * W, 0.5 * H, 260.0, 0.62)), (ws(11, 4), (0.5 * W, 0.5 * H, 260.0, 0.58)),
                  (we(11, 4), (0.5 * W, 0.5 * H, 300.0, 0.72)), (ws(11, 7), (0.5 * W, 0.5 * H, 290.0, 0.66)),
                  (we(11, 7), (0.5 * W, 0.5 * H, 360.0, 0.85)), (ls(12), (0.5 * W, 0.5 * H, 270.0, 0.62)),
                  (T_DROP, (0.5 * W, 0.5 * H, 270.0, 0.62)), (DUR, (0.5 * W, 0.52 * H, 240.0, 0.3))])


def rays_gain(t):
    return kf(t, [(0, 0.0), (le(4) - 1.0, 0.0), (T_PRE, 0.9), (44, 0.7), (B(12), 1.1), (T_DROP, 1.0), (DUR, 0.5)])


def water_tint(t):
    """(top, bottom) background colours, linear."""
    a = kf(t, [(0, (6, 14, 34, 3, 5, 12)), (21, (6, 14, 34, 3, 5, 12)), (T_PRE + 2, (10, 12, 34, 7, 5, 14)),
               (44, (14, 10, 30, 9, 5, 12)), (B(12) + 2, (22, 10, 26, 10, 4, 9)), (DUR, (16, 8, 20, 6, 3, 7))])
    return srgb_to_lin(a[:3]), srgb_to_lin(a[3:])


def ambient(t):
    """Strength of the slow current (cells/frame)."""
    return kf(t, [(0, 0.10), (12, 0.14), (ws(6, 1) - 0.6, 0.15), (ws(6, 1) + 0.6, 0.035), (le(6) - 0.2, 0.035),
                  (le(6) + 1.2, 0.15), (44.5, 0.13), (47, 0.05), (DUR, 0.04)])


def vortex(t):
    return kf(t, [(0, 0.0), (T_CH - 0.4, 0.0), (B(12) + 1.2, 0.62), (ws(11, 4), 0.6), (we(11, 4), 0.3),
                  (ls(12) - 0.5, 0.3), (ls(12) + 1.0, 0.5), (DUR, 0.42)])


def half_life(t):
    """Seconds for released ink to fade to half."""
    return kf(t, [(0, 2.2), (T_CH - 1, 2.2), (B(12), 1.0), (DUR, 1.0)])


def zoom(t):
    z = kf(t, [(0, 1.10), (12, 1.07), (T_PRE, 1.045), (T_CH - 0.3, 1.04), (B(12) + 1.5, 1.0), (ls(12), 1.0),
               (DUR, 1.035)])
    # the frame breathes on the long note of "breathe"
    a, b = ws(11, 7), we(11, 7) + 1.2
    if a < t < b:
        z += 0.045 * math.sin(math.pi * (t - a) / (b - a)) ** 2
    return z


def cam_center(t):
    return kf(t, [(0, (0.5 * W, 0.47 * H)), (12, (0.5 * W, 0.5 * H)), (T_CH, (0.5 * W, 0.52 * H)),
                  (B(12) + 1.5, (0.5 * W, 0.5 * H))])


# --------------------------------------------------------------------------------------- rain
def drops():
    """Raindrops on the surface: on beats in the intro, scattered in the verse, thinning in the
    pre-chorus, a last one on 'eyes'; none after. (t0, x, y, amplitude) in frame pixels."""
    rng = np.random.default_rng(21)
    d = []
    for k, t0 in enumerate([B(1), B(1, 3), B(2), B(2, 3), B(3), B(3, 3)]):
        d.append((t0, [540, 330, 760, 420, 700, 260][k], [880, 1300, 560, 640, 1340, 980][k], 1.0))
    t = 12.6
    while t < 41.6:
        quiet = ws(3, 6) - 0.3 < t < ls(4) + 0.2           # nothing falls on "silence"
        rate = 0.75 if t < T_PRE else 0.75 - 0.5 * (t - T_PRE) / (41.6 - T_PRE)
        if not quiet:
            d.append((t, float(rng.uniform(60, W - 60)), float(rng.uniform(140, H - 140)), float(rng.uniform(.45, .9))))
        t += float(rng.exponential(1 / rate))
    for bar in (4, 5, 6, 7, 8, 9, 10):
        d.append((B(bar), float(rng.uniform(120, W - 120)), float(rng.uniform(300, H - 300)), 0.9))
    return d


def last_drop(eyes_xy):
    return (ws(8, 6) + 0.25, eyes_xy[0], eyes_xy[1], 1.25)


# --------------------------------------------------------------------------------------- type
FONT = os.path.join(ROOT, 'work/fonts')
F_SERIF = {300: 'cormorant-garamond-latin-300-italic.ttf', 400: 'cormorant-garamond-latin-400-italic.ttf',
           500: 'cormorant-garamond-latin-500-italic.ttf'}
F_SCRIPT = 'great-vibes-latin-400-normal.ttf'
F_ZH = 'wenkai-light.ttf'
_fonts = {}


def font(name, size):
    k = (name, int(size))
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(os.path.join(FONT, name), int(size))
    return _fonts[k]


def glyphs(text, fnt, tracking=0.0, bow=0.0, spread=None):
    """Render a word to a float mask. tracking in em; bow: baseline sag in em (letters follow an arc and
    turn with it); spread: per-letter extra x offset in em (the unclench animation).
    Returns (mask, baseline_y_in_mask, left_x_in_mask, advance)."""
    size = fnt.size
    asc, desc = fnt.getmetrics()
    pad = int(size * 0.6)
    if not (tracking or bow or spread is not None):
        adv = fnt.getlength(text)
        img = Image.new('L', (int(adv + 2 * pad), asc + desc + 2 * pad), 0)
        ImageDraw.Draw(img).text((pad, pad + asc), text, font=fnt, fill=255, anchor='ls')
        return np.asarray(img, np.float32) / 255.0, pad + asc, pad, adv
    adv_l = [fnt.getlength(c) for c in text]
    xs, x = [], 0.0
    for i, a in enumerate(adv_l):
        xs.append(x + (spread[i] * size if spread is not None else 0.0))
        x += a + tracking * size
    adv = x - tracking * size
    sag = bow * size
    off = pad + (int(max(abs(v) for v in spread) * size) if spread is not None else 0)
    cw = int(adv + 2 * off + size)
    ch = int(asc + desc + 2 * pad + abs(sag))
    canvas = np.zeros((ch, cw), np.float32)
    for c, x0, a in zip(text, xs, adv_l):
        u = (x0 + a / 2) / max(adv, 1)
        dy = sag * (1 - (2 * u - 1) ** 2)
        li = Image.new('L', (int(a + size), asc + desc + size), 0)
        ImageDraw.Draw(li).text((size // 2, size // 2 + asc), c, font=fnt, fill=255, anchor='ls')
        if bow:
            slope = sag * -4 * (2 * u - 1) / max(adv, 1)
            li = li.rotate(math.degrees(math.atan(slope)), resample=Image.BICUBIC, center=(size // 2 + a / 2, size // 2 + asc))
        la = np.asarray(li, np.float32) / 255.0
        X0 = int(round(off + x0 - size // 2))
        Y0 = int(round(pad + dy - size // 2))
        y0, x0c = max(Y0, 0), max(X0, 0)
        y1, x1 = min(Y0 + la.shape[0], ch), min(X0 + la.shape[1], cw)
        canvas[y0:y1, x0c:x1] = np.maximum(canvas[y0:y1, x0c:x1], la[y0 - Y0:y1 - Y0, x0c - X0:x1 - X0])
    return canvas, pad + asc, off, adv


# colours (linear emission)
SILVER = np.float32([0.50, 0.66, 1.00]) * 1.05
MOON = np.float32([0.62, 0.70, 0.86])
AMBER = np.float32([1.00, 0.58, 0.26]) * 1.05
HONEY = np.float32([1.00, 0.74, 0.42])
ROSE = np.float32([1.00, 0.50, 0.58])
PEACH = np.float32([1.00, 0.70, 0.58])
WINE = np.float32([0.78, 0.16, 0.26])


class Word:
    """One word of ink: where it is, how it is written, how long it is held, how it is let go."""

    def __init__(self, text, fnt, x, base, color, t0, t1, hold, line, idx, **kw):
        self.text, self.fnt, self.color = text, fnt, color
        self.t0, self.t1 = t0, t1                      # sung start / end
        self.hold = hold                               # time the line starts being let go
        self.line, self.idx = line, idx
        self.release = kw.get('release', 1.4)          # seconds from held to fully free
        self.emis = kw.get('emis', 1.0)
        self.scat = kw.get('scat', 0.6)
        self.lift = kw.get('lift', 0.7)               # >0 rises, <0 sinks once let go
        self.burst = kw.get('burst', 0.35)             # swirl when let go
        self.erase = kw.get('erase', 0.8)              # half-life (s) of the ink left in place after letting go
        self.wdur = kw.get('wdur', None)               # writing time; default from the sung length
        self.tracking = kw.get('tracking', 0.0)
        self.bow = kw.get('bow', 0.0)
        self.streaks = kw.get('streaks', False)
        self.unclench = kw.get('unclench', False)
        self.x, self.base = x, base
        m, by, lx, adv = glyphs(text, fnt, self.tracking, self.bow)
        self.adv = adv
        self.set_mask(m, by, lx)

    def set_mask(self, m, by, lx):
        self.m = m
        self.px = int(round(self.x - lx))
        self.py = int(round(self.base - by))
        cols = np.where(m.max(0) > 0.05)[0]
        rows = np.where(m.max(1) > 0.05)[0]
        self.ix0, self.ix1 = cols[0], cols[-1] + 1
        self.iy0, self.iy1 = rows[0], rows[-1] + 1
        hh, ww = m.shape
        xx = (np.arange(ww, dtype=np.float32) - self.ix0) / max(self.ix1 - self.ix0, 1)
        yy = (np.arange(hh, dtype=np.float32) - (self.iy0 + self.iy1) / 2) / max(self.ix1 - self.ix0, 1)
        self.xr = xx[None, :] - 0.18 * yy[:, None]      # italic-slanted wipe

    def write_span(self):
        if self.wdur is not None:
            d = self.wdur
        else:
            d = min(max(0.85 * (self.t1 - self.t0), 0.26), 0.75)
        return self.t0 - 0.07, d

    def reveal(self, t):
        a, d = self.write_span()
        return min(max((t - a) / d, 0.0), 1.0)

    def wipe(self, p):
        soft = 0.22
        return np.clip((p * (1 + soft) - self.xr) / soft, 0, 1)

    def still(self, t):
        """1 while held, easing to 0 over the release."""
        a, _ = self.write_span()
        if t < a - 0.3:
            return 0.0
        if t < self.hold:
            return 1.0
        return 1.0 - ease((t - self.hold) / self.release)

    def bbox(self):
        return (self.px + self.ix0, self.py + self.iy0, self.px + self.ix1, self.py + self.iy1)


class Row:
    def __init__(self, words, font_name, size, cx, base, tracking=None, align='center'):
        self.words, self.font_name, self.size, self.cx, self.base = words, font_name, size, cx, base
        self.tracking = tracking or {}
        self.align = align


def layout_line(li, rows, color, hold, zh=None, zh_y=None, **common):
    """Place one lyric line. rows: list of Row; per-word overrides go in common['per'][word_index]."""
    words_txt = LYR['lines'][li - 1]['en'].split()
    per = common.pop('per', {})
    out = []
    for row in rows:
        fnt = font(row.font_name, row.size) if not isinstance(row.font_name, dict) else None
        items = []
        for wi in row.words:
            fn = row.font_name.get(wi, row.font_name['*']) if isinstance(row.font_name, dict) else row.font_name
            sz = per.get(wi, {}).get('size', row.size)
            f = font(fn, sz)
            tr = per.get(wi, {}).get('tracking', 0.0)
            bw = per.get(wi, {}).get('bow', 0.0)
            txt = words_txt[wi - 1]
            if tr or bw:
                adv = glyphs(txt, f, tr, bw)[3]
            else:
                adv = f.getlength(txt)
            items.append((wi, txt, f, adv))
        space = font(row.font_name if not isinstance(row.font_name, dict) else row.font_name['*'], row.size).getlength(' ') * 1.05
        total = sum(a for *_, a in items) + space * (len(items) - 1)
        x = row.cx - total / 2 if row.align == 'center' else (row.cx if row.align == 'left' else row.cx - total)
        for wi, txt, f, adv in items:
            o = dict(common)
            o.update({k: v for k, v in per.get(wi, {}).items() if k != 'size'})
            col = o.pop('color', color)
            wd = Word(txt, f, x, row.base, col, ws(li, wi), we(li, wi), o.pop('hold', hold), li, wi, **o)
            out.append(wd)
            x += adv + space
    if zh is not None and zh_y is not None:
        out_zh = Caption(LYR['lines'][li - 1]['zh'], zh, zh_y, ls(li) + 0.25, hold - 0.1)
        return out, out_zh
    return out, None


class Caption:
    """Quiet Chinese translation: printed, not ink; fades in and out."""

    def __init__(self, text, cx, y, t0, t1, size=46):
        f = font(F_ZH, size)
        tr = 0.14 * size
        adv = [f.getlength(c) for c in text]
        wtot = sum(adv) + tr * (len(text) - 1)
        asc, desc = f.getmetrics()
        img = Image.new('L', (int(wtot + 40), asc + desc + 40), 0)
        d = ImageDraw.Draw(img)
        x = 20
        for c, a in zip(text, adv):
            d.text((x, 20 + asc), c, font=f, fill=255, anchor='ls')
            x += a + tr
        self.m = np.asarray(img, np.float32) / 255.0
        self.px = int(cx - wtot / 2 - 20)
        self.py = int(y - asc - 20)
        self.t0, self.t1 = t0, t1

    def alpha(self, t):
        return ease((t - self.t0) / 0.6) * (1 - ease((t - self.t1) / 0.55))


# --------------------------------------------------------------------------------------- the lyric score
def score():
    words, caps = [], []

    def add(res):
        w, c = res
        words.extend(w)
        if c is not None:
            caps.append(c)

    S300, S400, S500 = F_SERIF[300], F_SERIF[400], F_SERIF[500]
    cx = W / 2

    # title, written into the water after the hum
    tt = Word('Hold Me Slowly', font(F_SCRIPT, 118), 0, 0, PEACH * 0.85, 6.55, 8.6, 9.7, 0, 0,
              wdur=1.9, lift=0.45, burst=0.4, release=1.8, emis=0.9)
    tt.x = cx - tt.adv / 2
    tt.base = 905
    m, by, lx, adv = glyphs(tt.text, tt.fnt)
    tt.set_mask(m, by, lx)
    words.append(tt)
    caps.append(Caption('慢慢抱紧我', cx, 1040, 7.4, 9.9, size=42))

    nxt = lambda li: ls(li + 1) - 0.15

    # L1: the word "bent" sags on a bowed baseline; the rest is upright
    add(layout_line(1, [Row([1, 2, 3], S400, 112, cx, 520), Row([4], S500, 210, cx, 745), Row([5, 6], S500, 150, cx, 925)],
                    SILVER, nxt(1), zh=cx, zh_y=1030, per={4: {'bow': 0.16, 'tracking': 0.04}}))
    # L2: words 4-5 ("old goodbyes") are grey and heavy and sink
    add(layout_line(2, [Row([1, 2, 3], S400, 120, cx, 1250), Row([4, 5], S500, 150, cx, 1425)],
                    SILVER, nxt(2), zh=cx, zh_y=1530,
                    per={4: {'lift': -0.9, 'color': MOON, 'release': 2.2, 'burst': 0.15},
                         5: {'lift': -0.9, 'color': MOON, 'release': 2.2, 'burst': 0.15}}))
    # L3: 'you' is the first warm ink; the last word ('silence') is spaced and faint
    add(layout_line(3, [Row([1, 2, 3], S400, 128, cx, 480), Row([4], S400, 128, cx, 645), Row([5, 6], S300, 138, cx, 830)],
                    SILVER, nxt(3), zh=cx, zh_y=935,
                    per={2: {'color': AMBER, 'emis': 1.1},
                         6: {'tracking': 0.22, 'emis': 0.55, 'wdur': 0.75, 'color': MOON}}))
    # L4: words 5-6 ("hidden kind") carry almost no light of their own; the warm light finds them
    add(layout_line(4, [Row([1, 2, 3], S400, 118, cx, 1190), Row([4, 5, 6], S500, 140, cx + 30, 1365)],
                    SILVER, nxt(4), zh=cx, zh_y=1470,
                    per={2: {'color': AMBER},
                         5: {'emis': 0.06, 'scat': 2.6, 'color': HONEY},
                         6: {'emis': 0.06, 'scat': 2.6, 'color': HONEY}}))
    # L5: what 'you' said, in warm ink; the last word ('time') is written slowly and spaced
    add(layout_line(5, [Row([1, 2], S400, 96, cx, 520), Row([3], S500, 190, cx, 710), Row([4, 5, 6], S500, 138, cx, 890)],
                    AMBER, nxt(5), zh=cx, zh_y=995,
                    per={6: {'tracking': 0.12, 'wdur': 0.68}}))
    # L6: the current stops while it is sung (score.ambient)
    add(layout_line(6, [Row([1, 2, 3, 4], S500, 130, cx, 1190), Row([5], S500, 165, cx, 1370)],
                    HONEY, nxt(6), zh=cx, zh_y=1478, per={5: {'wdur': 0.7}}))
    # L7: word 3 ("hurt") is wine-dark and drains out of the bottom
    add(layout_line(7, [Row([1, 2, 3], S500, 140, cx, 560), Row([4, 5], S400, 128, cx, 725), Row([6, 7], S500, 138, cx, 895)],
                    AMBER, nxt(7), zh=cx, zh_y=1005,
                    per={3: {'color': WINE * 1.25, 'lift': -1.8, 'burst': 0.1, 'release': 1.0, 'scat': 0.9}}))
    # L8: word 3 ('rain') is a long note, written slowly, then falls in streaks;
    # the last raindrop lands on 'eyes'
    add(layout_line(8, [Row([1, 2, 3], S500, 140, cx, 1190), Row([4, 5, 6], S500, 140, cx, 1365)],
                    PEACH, le(8) - 0.05, zh=cx, zh_y=1475, erase=0.3, release=0.5,
                    per={3: {'wdur': we(8, 3) - ws(8, 3), 'lift': -1.3, 'streaks': True, 'burst': 0.05,
                             'release': 0.9, 'color': MOON * 1.1, 'hold': we(8, 3) + 0.15}}))

    # chorus: the rule turns -- words are held, and what is let go joins the ring around them
    hold_910 = we(10, 3) + 0.15
    add(layout_line(9, [Row([1, 2], S500, 132, cx - 70, 790), Row([3], F_SCRIPT, 200, cx + 40, 955)],
                    AMBER, hold_910, zh=cx, zh_y=None, per={3: {'wdur': 0.95}}, lift=0.0, burst=0.25, release=0.6, erase=0.35))
    add(layout_line(10, [Row([1, 2], S500, 132, cx + 70, 1120), Row([3], F_SCRIPT, 200, cx - 40, 1285)],
                    ROSE, hold_910, zh=cx, zh_y=None, per={3: {'wdur': 0.95}}, lift=0.0, burst=0.25, release=0.6, erase=0.35))
    # L11: word 2 ('my') is the turn from 'your' to 'my';
    # 'unclench' is written tight and opens; the frame breathes on 'breathe' (score.zoom)
    add(layout_line(11, [Row([1, 2, 3], S500, 138, cx, 735), Row([4], S500, 176, cx, 935), Row([5, 6, 7], {'*': S500, 7: F_SCRIPT}, 132, cx, 1150)],
                    PEACH, ls(12) - 1.5, zh=cx, zh_y=1295,
                    per={2: {'color': AMBER * 1.15}, 4: {'unclench': True, 'wdur': 0.55},
                         7: {'size': 190, 'wdur': 0.7}}, lift=0.0, burst=0.25, release=0.7, erase=0.35))
    # L12 the last "Hold me slowly." stays to the end
    add(layout_line(12, [Row([1, 2], S500, 150, cx, 880), Row([3], F_SCRIPT, 240, cx, 1080)],
                    ROSE * 0.6 + AMBER * 0.4, DUR + 5, zh=cx, zh_y=1215, per={3: {'wdur': 1.1}}, lift=0.0))
    # one caption for both "hold me slowly" lines of the first chorus
    caps.append(Caption(LYR['lines'][8]['zh'], cx, 1400, ls(9) + 0.3, hold_910 + 0.3))
    return words, caps


def ring_sources(t):
    """Ink fed into the ring through the whole chorus: (x, y, colour, strength). Two arms, cool and warm,
    each fed at two points; it swells when a 'hold me' is sung."""
    if t < B(12) - 0.9:
        return []
    k = 0.35 * ease((t - (B(12) - 0.9)) / 1.2)
    for a in (B(12) - 0.9, ls(10), we(10, 3) + 0.15, ls(12) - 1.5, ls(12)):
        if a < t < a + 2.6:
            k += 0.75 * math.sin(math.pi * (t - a) / 2.6)
    k *= 1 - ease((t - T_DROP) / 2.5)
    r = 395
    out = []
    for ang, col in ((math.pi + 0.1, MOON * 1.15), (0.1, AMBER), (math.pi / 2 + 0.35, ROSE), (-math.pi / 2 + 0.35, HONEY)):
        out.append((0.5 * W + r * math.cos(ang), 0.5 * H + r * math.sin(ang), col, k * (1.0 if col is not ROSE and col is not HONEY else 0.6)))
    return out


def plume(t):
    """Warm plume that wipes the frame into the pre-chorus: (x, y, strength)."""
    a, b = le(4) - 0.35, T_PRE + 1.4
    if a < t < b:
        return (0.74 * W, H + 40, math.sin(math.pi * (t - a) / (b - a)))
    return None


def exhale(t):
    """The hum in the intro: a faint breath of cool ink rising from below."""
    a, b0, b = TIM['hum']
    if a < t < b + 0.4:
        return (0.5 * W, 0.76 * H, math.sin(math.pi * min((t - a) / (b + 0.4 - a), 1.0)))
    return None
