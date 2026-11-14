#!/usr/bin/env python3
"""Bring Jensen Back -- lyric MV. Everything on screen is lit bulbs on one LED wall.

  mv.py --preview 12.3,45.6,...      write work/preview/p_<t>.png and a contact sheet
  mv.py --seg K                       render segment K to work/segments/sKK.mkv
  mv.py --all [--jobs N]              render every missing segment in parallel

The rule of this world (see storyboard.md): the lyrics are the green light that 'nobody switched off'. A bulb
lights when its syllable is sung, flashes as it warms up, and glows on after it is switched off. Hook words
that stay up long enough burn into the wall and never fully leave it. Ink by meaning: amber = 1993 / the
past, green = the light that is on, red = headlines / the fall, white = facts.

Lyrics are read from work/audio/lyrics_sung.txt and timed from work/audio/lyric_timing.json; this file
refers to lines by section and position only.
"""
import argparse
import functools
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.chdir(ROOT)

import fx  # noqa: E402
import props  # noqa: E402
from led import (AMBER, FONT_EN, FONT_PIX, FONT_ZH, GH, GREEN, GW, H, RED, W, WHITE, expand, finish,  # noqa: E402
                 glyph_mask, row_mask, stamp)
from lyrics import parse  # noqa: E402
from textwall import Line  # noqa: E402

FPS = 30
DUR = 314.76
NFR = int(math.ceil(DUR * FPS))
BPM = 94.99
BEAT = 60 / BPM
BAR = 4 * BEAT
PH0 = 0.010                    # first downbeat (beat grid fit; kick on 1 and 3)

F = np.load('work/audio/features.npz')
SECS, LINES = parse('work/audio/lyrics_sung.txt')
TIM = {r['i']: r for r in json.load(open(os.environ.get('LYR_TIMING', 'work/audio/lyric_timing.json')))['lines']}
CH = json.load(open('work/audio/chants.json')) if os.path.exists('work/audio/chants.json') else {}

COOL = np.array([0.55, 0.85, 1.0], np.float32)
ROWS = (44, 88, 132)
BIGH = 38
DGREEN = GREEN * 0.55


def feat(name, t):
    a = F[name]
    i = int(np.clip(round(t * FPS), 0, len(a) - 1))
    return float(a[i])


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def sat(x):
    return min(1.0, max(0.0, x))


def beat_of(t):
    return (t - PH0) / BEAT


# ---------------------------------------------------------------- lyric access
def sec_lines(name, occ=0):
    k = 0
    for si, s in enumerate(SECS):
        if s['name'] == name:
            if k == occ:
                return [l['i'] for l in LINES if l['sec'] == si]
            k += 1
    return []


def times(i):
    r = TIM.get(i)
    if not r or not r.get('units'):
        return None
    return [tuple(u) for u in r['units']]


def ts(i):
    tt = times(i)
    return tt[0][0] if tt else 1e9


def te(i):
    tt = times(i)
    return tt[-1][1] if tt else -1e9


@functools.lru_cache(maxsize=512)
def LN(i, x0, y0, w, hmax, hmin=10, align='center', max_rows=3, gap=4, upper=True):
    l = LINES[i]
    return Line(l['text'], l['units'], times(i) or [(1e9, 1e9)] * len(l['units']), x0, y0, w, hmax, hmin, align,
                max_rows, gap, upper=upper)


def off_gain(t, t_off, tau=0.09):
    if t < t_off:
        return 1.0
    return math.exp(-(t - t_off) / tau)


@functools.lru_cache(maxsize=256)
def pix(text, k=1):
    m, _ = glyph_mask(text, FONT_PIX, 16 * k)
    return m


@functools.lru_cache(maxsize=256)
def big(text, h, font=FONT_EN):
    m, _ = row_mask(text, h, en_font=font)
    return m


def center_x(m):
    return (GW - m.shape[1]) / 2


# ---------------------------------------------------------------- the persistent things
@functools.lru_cache(maxsize=256)
def small(text, h=9):
    m, _ = row_mask(text, h, track=0.10)
    return m


@functools.lru_cache(maxsize=512)
def bigfit(text, h, maxw=GW - 8, font=FONT_EN):
    while h > 8:
        m = big(text, h, font)
        if m.shape[1] <= maxw:
            return m
        h -= 1
    return big(text, h, font)


def ticker(field, t, text, y, color, speed=18.0, gain=0.7):
    """bottom crawl, scrolls right-to-left at `speed` bulbs/s."""
    m = small(text, 10)
    w = m.shape[1]
    off = (t * speed) % w
    x = -off
    while x < GW:
        stamp(field, m, x, y, color, gain)
        x += w


def status(field, t, left, right, color, gain=0.8, live=False):
    ml = small(left, 8)
    stamp(field, ml, 4, 8, color, gain)
    if right:
        mr = small(right, 8)
        stamp(field, mr, GW - mr.shape[1] - 4, 8, color, gain)
    if live and (t * 1.6) % 1 < 0.6:
        stamp(field, props.bulb(2), GW - 7, 22, RED, 1.2)


def frame_rule(field, color, gain=0.25):
    field[21, 2:GW - 2] += color * gain
    field[GH - 20, 2:GW - 2] += color * gain


# ---------------------------------------------------------------- lyric layouts
def draw_line(field, t, i, color, x0=6, y0=None, w=None, hmax=20, hmin=11, t_off=None, tau=0.09, yc=None,
              align='center', max_rows=3, gain=1.0, gap=4):
    w = w or GW - 2 * x0
    if y0 is None:
        L0 = LN(i, x0, 0, w, hmax, hmin, align, max_rows, gap)
        y0 = int(round((yc if yc is not None else GH / 2) - L0.height / 2))
    L = LN(i, x0, y0, w, hmax, hmin, align, max_rows, gap)
    g = gain * (off_gain(t, t_off, tau) if t_off is not None else 1.0)
    L.draw(field, t, color, g)
    return L


def stack(field, t, idxs, color, y_bottom=200, x0=6, w=None, hmax=20, hmin=11, keep=2, dimc=None, gap=7,
          max_rows=3, t_end=None, fade=(0.30, 0.10), y_min=0):
    """history stack: the line being sung sits with its bottom at y_bottom, earlier ones ride up and dim."""
    w = w or GW - 2 * x0
    act = [i for i in idxs if ts(i) - 0.22 <= t]
    if not act:
        return
    k = len(act) - 1
    Ls = [LN(i, x0, 0, w, hmax, hmin, 'center', max_rows) for i in idxs[:k + 1]]
    # move when the newest line arrives
    p = ease((t - (ts(idxs[k]) - 0.22)) / 0.16)
    y = y_bottom - Ls[k].height
    tops = {k: y}
    for j in range(k - 1, max(-1, k - keep - 1), -1):
        y = y - gap - Ls[j].height
        tops[j] = y
    shift = (1 - p) * (Ls[k].height + gap)
    g_end = off_gain(t, t_end, 0.12) if t_end is not None else 1.0
    for j, top in tops.items():
        i = idxs[j]
        age = k - j
        if age == 0:
            gg = 1.0
            yy = top
        else:
            gg = (1.0 * (1 - p) + fade[0] * p) if age == 1 else (fade[0] * (1 - p) + fade[1] * p) if age == 2 else fade[1] * (1 - p)
            yy = top + shift
        if age > 0 and yy < y_min:
            # no room above: the older line leaves instead of covering the picture
            gg *= max(0.0, 1 - (y_min - yy) / 12)
            if gg <= 0.01:
                continue
        L = LN(i, x0, int(round(yy)), w, hmax, hmin, 'center', max_rows)
        c = color if (age == 0 or dimc is None) else dimc
        L.draw(field, t, c, gg * g_end, flash=(age == 0))


# ---------------------------------------------------------------- chants (Bring him / Bring Jensen / Back!)
def chant_events(kind=None):
    ev = CH.get('events', [])
    return [e for e in ev if kind is None or e['kind'] == kind]


def slam(field, t, t0, text, y, h, color, hold=0.45, decay=0.25, font=FONT_EN, x=None, punch=0.18):
    """a word hits the wall: over-bright flash, a short scale punch from bigger, holds, then fades."""
    if t < t0 - 0.02:
        return 0.0
    a = t - t0
    if a > hold + 4 * decay:
        return 0.0
    hh = int(round(h * (1 + punch * math.exp(-a / 0.06))))
    m = big(text, hh, font)
    if m.shape[1] > GW - 2:
        m = cv2.resize(m, (GW - 2, int(m.shape[0] * (GW - 2) / m.shape[1])), interpolation=cv2.INTER_AREA)
    g = (1 + 1.2 * math.exp(-a / 0.07)) * (1.0 if a < hold else math.exp(-(a - hold) / decay))
    xx = center_x(m) if x is None else x
    stamp(field, m, xx, y - m.shape[0] / 2, color, g)
    return g


# ---------------------------------------------------------------- burn-in
BURN_TXT = ['BRING', 'JENSEN', 'BACK']


@functools.lru_cache(maxsize=1)
def burn_mask():
    f = np.zeros((GH, GW), np.float32)
    for txt, y in zip(BURN_TXT, ROWS):
        m = big(txt if txt != 'BACK' else 'BACK!', BIGH)
        if m.shape[1] > GW - 4:
            m = cv2.resize(m, (GW - 4, m.shape[0]), interpolation=cv2.INTER_AREA)
        x = int(center_x(m))
        f[int(y - m.shape[0] / 2):int(y - m.shape[0] / 2) + m.shape[0], x:x + m.shape[1]] += m
    return np.clip(f, 0, 1)


def burn_level(t):
    """how deep the hook has burned into the wall by time t (sum of hook exposure, saturating)."""
    lv = 0.0
    for a, b in HOOKS:
        lv += max(0.0, min(t, b) - a)
    return 0.034 * (1 - math.exp(-lv / 30.0))


# ---------------------------------------------------------------- sections
def section_bounds():
    """start/end of every section from the timed lines."""
    out = []
    for si, s in enumerate(SECS):
        idx = [l['i'] for l in LINES if l['sec'] == si and times(l['i'])]
        if not idx:
            continue
        out.append((s['name'], si, min(ts(i) for i in idx), max(te(i) for i in idx)))
    return out


SB = section_bounds()


def occ_bounds(name, occ=0):
    k = 0
    for nm, si, a, b in SB:
        if nm == name:
            if k == occ:
                return a, b
            k += 1
    return None


HOOK_SECS = [b for b in (occ_bounds('Hook', 0), occ_bounds('Hook 2', 0), occ_bounds('Hook', 1)) if b]
HOOKS = [(a - 1.0, b + 0.5) for a, b in HOOK_SECS]


class FrameState:
    def __init__(self):
        self.field = np.zeros((GH, GW, 3), np.float32)
        self.zoom, self.cx, self.cy, self.rot = 1.0, 0.5, 0.5, 0.0
        self.crowd = None              # (bounce, raise, rim colour)
        self.glitch = 0.0
        self.power = 1.0
        self.white = 0.0               # whole-wall flash
        self.burn_color = GREEN
        self.burn_gain = 1.0
        self.burn_scale = 1.0
        self.chroma = 0.0
        self.exposure = 1.0


# ================================================================ motifs (the upper half of the verses)
def wave_rows(field, t, y0, rows, color, gain=0.5):
    for r in range(rows):
        xs = np.arange(GW)
        ys = y0 + r * 5 + 2 * np.sin(xs * 0.18 + t * 3.0 + r * 1.3)
        for x, y in zip(xs, ys.astype(int)):
            if 0 <= y < GH:
                field[y, x] += color * gain * (0.6 + 0.4 * math.sin(x * 0.4 + t * 5))


def plates(field, t, x, y, n, color):
    for k in range(n):
        m = np.zeros((7, 40), np.float32)
        cv2.ellipse(m, (20, 3), (19, 3), 0, 0, 360, 1.0, 1)
        stamp(field, m, x + math.sin(k * 1.7) * 2, y - k * 4, color, 0.9)


def chip(field, x, y, s, color, t):
    m = np.zeros((s, s), np.float32)
    cv2.rectangle(m, (4, 4), (s - 5, s - 5), 1.0, 1)
    cv2.rectangle(m, (9, 9), (s - 10, s - 10), 0.6, -1)
    for k in range(6, s - 6, 4):
        m[0:4, k] = 1
        m[s - 4:s, k] = 1
        m[k, 0:4] = 1
        m[k, s - 4:s] = 1
    stamp(field, m, x, y, color, 0.95)


def cores(field, t, t0, x, y, cols, rows, color):
    """CUDA: a grid of cores lighting up in parallel waves."""
    for r in range(rows):
        for c in range(cols):
            ph = (t - t0) * 4 - (r + c) * 0.25
            v = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(ph * 2.2)) if ph > 0 else 0.1
            field[y + r * 4:y + r * 4 + 3, x + c * 4:x + c * 4 + 3] += color * v


def racks(field, t, x, y, n, color):
    for k in range(n):
        xx = x + k * 13
        field[y:y + 50, xx] += color * 0.6
        field[y:y + 50, xx + 10] += color * 0.6
        field[y, xx:xx + 11] += color * 0.6
        field[y + 49, xx:xx + 11] += color * 0.6
        for j in range(3, 48, 4):
            on = (math.sin(t * 7 + k * 3.1 + j * 1.7) > 0.2)
            field[y + j, xx + 2:xx + 9] += color * (0.25 + (0.8 if on else 0))


def drops(field, t, t0, color, n=18, seed=1):
    rng = np.random.default_rng(seed)
    xs = rng.integers(4, GW - 4, n)
    st = rng.uniform(0, 1.2, n)
    sp = rng.uniform(40, 80, n)
    for x, s0, v in zip(xs, st, sp):
        a = t - t0 - s0
        if a < 0:
            continue
        y = int(24 + v * a * a * 1.2)
        for k in range(7):
            yy = y - k
            if 24 <= yy < 118:
                field[yy, x:x + 2] += color * 1.4 * (1.0 - k * 0.13)


def candles(field, t, x, y, n, color):
    for k in range(n):
        xx = x + k * 9
        field[y:y + 12, xx:xx + 4] += color * 0.55
        fl = 0.8 + 0.4 * math.sin(t * 13 + k * 2.3)
        field[y - 4:y - 1, xx + 1:xx + 3] += AMBER * fl * 1.3
        field[y - 5, xx + 1 + (int(t * 9 + k) % 2)] += AMBER * fl


def candle_chart(field, t, t0, t1, x, y, w, h, color, cliff=True):
    """red candlesticks walking down, the last ones fall off a cliff."""
    n = 12
    p = sat((t - t0) / max(0.3, (t1 - t0) * 0.8))
    vals = np.linspace(0.85, 0.55, n)
    if cliff:
        vals[-3:] = [0.30, 0.12, 0.03]
    show = int(np.ceil(p * n))
    for k in range(show):
        cx = x + int(k * w / n)
        top = y + int((1 - vals[k]) * h)
        body = max(3, int(h * 0.12))
        field[top:top + body, cx:cx + 4] += color * 1.0
        field[max(y, top - 3):top + body + 3, cx + 1:cx + 3] += color * 0.6


def counter(field, t, t0, t1, v0, v1, y, color, h=40, fmt='{:,}'):
    p = ease((t - t0) / max(0.05, t1 - t0))
    v = int(round(v0 + (v1 - v0) * p))
    m = bigfit(fmt.format(v), h)
    stamp(field, m, center_x(m), y, color, 1.0)


def bulb_on(field, x, y, r, t_on, t, color=GREEN):
    if t < t_on:
        stamp(field, props.bulb(r), x, y, color, 0.10)
        return
    a = t - t_on
    g = 1.0 + 1.5 * math.exp(-a / 0.12)
    stamp(field, props.bulb(r), x, y, color, 1.3 * g)


def verse1_motif(field, t, k, i):
    """k = position in verse 1 (0-based), i = line index; drawn in the band y 26..112."""
    t0, t1 = ts(i), te(i)
    a = t - t0
    G, A = GREEN, AMBER
    if k == 0:                                   # nine years old, across the sea
        m = big('9', 74)
        stamp(field, m, center_x(m) - 20, 28, A, 1.0)
        mm = big('岁', 26)
        stamp(field, mm, center_x(m) + m.shape[1] / 2 - 10, 70, A, 0.9)
        wave_rows(field, t, 96, 3, G, 0.45)
    elif k == 1:                                 # dishes
        plates(field, t, 47, 98, min(8, 1 + int(max(0, a) * 4)), A)
    elif k == 2:                                 # $40,000 and a bet nobody understood
        m = bigfit('$40,000', 38)
        stamp(field, m, center_x(m), 34, G, 1.0)
        card = np.zeros((34, 24), np.float32)
        cv2.rectangle(card, (0, 0), (23, 33), 1.0, 1)
        q = big('?', 18)
        card[8:8 + q.shape[0], (24 - q.shape[1]) // 2:(24 - q.shape[1]) // 2 + q.shape[1]] += q[:26, :24]
        stamp(field, card, 56, 76, WHITE, 0.8 * ease(a / 0.3))
    elif k == 3:                                 # thirty days from dead: a countdown
        d = max(0, 30 - int(max(0, a) / max(0.1, (t1 - t0)) * 30))
        m = big(f'{d:02d}', 64)
        stamp(field, m, center_x(m), 28, RED, 1.0)
        mm = small('DAYS LEFT', 10)
        stamp(field, mm, center_x(mm), 96, RED, 0.8)
    elif k == 4:
        m = big('1999', 40)
        stamp(field, m, 8, 34, A, 1.0)
        chip(field, 82, 30, 44, G, t)
    elif k == 5:
        m = big('2006', 40)
        stamp(field, m, 8, 34, A, 1.0)
        cores(field, t, t0, 80, 32, 11, 10, G)
    elif k == 6:                                 # the AI wind; the world queues
        for r in range(7):
            xx = int((t * (60 + r * 9) + r * 37) % (GW + 40)) - 40
            field[34 + r * 8, max(0, xx):max(0, min(GW, xx + 30))] += G * 0.7
        for q in range(16):
            x = 6 + q * 8 - int((t - t0) * 6) % 8
            if 0 <= x < GW - 3:
                stamp(field, props.bulb(2), x, 98, WHITE, 0.55)
    elif k == 7:                                 # AI factory, compute is the new oil
        racks(field, t, 8, 44, 5, G)
        drop = np.zeros((34, 22), np.float32)
        pts = np.array([[11, 0], [21, 22], [17, 30], [5, 30], [1, 22]], np.int32)
        cv2.fillPoly(drop, [pts], 1.0)
        stamp(field, drop, 100, 56, A, 0.9 * ease(a / 0.4))
    elif k == 8:                                 # the leather jacket is armour
        stamp(field, props.jacket(1.0), 33, 28, G, 0.85)
    elif k == 9:                                 # the more you buy: take-off
        v = np.linspace(0, 1, 30) ** 3
        stamp(field, props.chart(110, 70, v, ease(a / max(0.3, t1 - t0))), 12, 36, G, 1.0)
    elif k == 10:                                # night market: lanterns, phone flashes
        for q in range(7):
            x = 10 + q * 17
            y = 40 + int(6 * math.sin(q * 0.9))
            stamp(field, props.bulb(5), x, y, RED if q % 2 else A, 0.8)
        fl = feat('snare', t)
        if fl > 0.45:
            rng = np.random.default_rng(int(t * 30))
            stamp(field, props.bulb(4), rng.integers(10, 120), rng.integers(60, 100), WHITE, 2.0 * fl)
    elif k == 11:                                # sixty direct reports, one seat
        p = ease(a / max(0.3, (t1 - t0) * 0.7))
        for r in range(6):
            for c in range(10):
                x0, y0 = 10 + c * 6, 34 + r * 12
                x1, y1 = 104, 70
                x = int(x0 + (x1 - x0) * p * 0.0)
                field[y0:y0 + 3, x:x + 3] += WHITE * 0.7
        stamp(field, props.chair(0.8), 90, 36, G, 0.9)
    elif k == 12:                                # 33 years, same man, same seat
        m = big('33', 70)
        stamp(field, m, 10, 30, A, 1.0)
        stamp(field, props.chair(0.8), 86, 34, G, 0.9)
    elif k == 13:                                # from a diner booth to the top of the Street
        stamp(field, props.booth(0.8), 5, 40, A, 0.7)
        stamp(field, props.chart(40, 60, np.linspace(0.05, 0.95, 12) ** 1.5, ease(a / 1.5)), 92, 32, G, 1.0)


def verse2_motif(field, t, k, i):
    t0, t1 = ts(i), te(i)
    a = t - t0
    R, Wt = RED, WHITE
    date = {0: '4.29', 4: '11.8', 12: '11.12'}
    if k in date:
        m = big(date[k], 56)
        stamp(field, m, center_x(m), 32, R, 1.0)
        if k == 4:
            env = np.zeros((20, 30), np.float32)
            cv2.rectangle(env, (0, 0), (29, 19), 1.0, 1)
            cv2.line(env, (0, 0), (15, 10), 1.0, 1)
            cv2.line(env, (29, 0), (15, 10), 1.0, 1)
            stamp(field, env, 52, 92, Wt, 0.8)
    elif k == 1:                                 # two figures
        for q, c in enumerate((Wt, R)):
            x = 30 + int(a * 10) + q * (14 - int(min(8, a * 4)))
            stamp(field, props.bulb(5), x, 60, c, 0.9)
            field[72:88, x + 4:x + 7] += c * 0.6
    elif k == 2:                                 # the wind grows louder
        for r in range(9):
            sp = 50 + 30 * ease(a / 2)
            xx = int((t * sp + r * 41) % (GW + 40)) - 40
            ln = int(10 + 30 * ease(a / 2))
            field[34 + r * 8, max(0, xx):max(0, min(GW, xx + ln))] += Wt * 0.6
    elif k == 3:                                 # three chairs of Capitol Hill
        for q in range(3):
            env = np.zeros((20, 30), np.float32)
            cv2.rectangle(env, (0, 0), (29, 19), 1.0, 1)
            cv2.line(env, (0, 0), (15, 10), 1.0, 1)
            cv2.line(env, (29, 0), (15, 10), 1.0, 1)
            stamp(field, env, 10 + q * 40, 54, Wt, 0.9 * ease((a - q * 0.35) / 0.15))
    elif k == 6:                                 # the board walks in
        m = np.zeros((40, 40), np.float32)
        cv2.circle(m, (16, 16), 13, 1.0, 2)
        cv2.line(m, (26, 26), (38, 38), 1.0, 3)
        stamp(field, m, 47 + int(6 * math.sin(t * 2)), 40, Wt, 0.9)
    elif k == 7:
        candle_chart(field, t, t0, t1, 10, 32, 115, 74, R)
    elif k == 8:
        drops(field, t, t0, R)
    elif k == 9:
        m = big('?', 70)
        stamp(field, m, center_x(m), 30, Wt, 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 6)))
    elif k == 10:
        for q in range(3):
            x = 24 + q * 30
            pg = np.zeros((40, 26), np.float32)
            cv2.rectangle(pg, (0, 0), (25, 39), 1.0, 1)
            for yy in range(6, 36, 5):
                cv2.line(pg, (4, yy), (21, yy), 0.7, 1)
            stamp(field, pg, x, 44 - q * 4, Wt if q == 0 else R, 0.85 * ease((a - q * 0.5) / 0.15))
    elif k == 11:
        m = bigfit('-11%', 58)
        stamp(field, m, center_x(m), 32, R, 1.0)
        for q in range(22):
            x = 8 + q * 5
            hh = int(6 + 8 * (0.5 + 0.5 * math.sin(t * 11 + q * 1.9)))
            field[106 - hh:106, x:x + 3] += AMBER * 0.6
    elif k == 13:
        m = big('33', 56)
        stamp(field, m, 14, 30, AMBER, 0.9)
        if a > 0.6:
            cv2.line(field, (8, 88), (64, 30), tuple(float(c) for c in R * 1.4), 2)
        tk = small('EFFECTIVE IMMEDIATELY', 10)
        stamp(field, tk, GW - ((t - t0) * 30 % (tk.shape[1] + GW)), 96, R, 1.0)
    elif k == 14:                                # interim hand-off
        x = int(10 + 100 * ease(a / 1.6))
        field[60:64, 10:x] += Wt * 0.6
        stamp(field, props.bulb(4), x - 4, 58, AMBER, 1.0)
    elif k == 15:                                # the jacket walks off the stage
        y = 26 + int(110 * ease((a - 0.3) / 1.8))
        stamp(field, props.jacket(0.95), 34, y, Wt, 0.8, )
        field[110:113, 4:GW - 4] += Wt * 0.3
    elif k == 16:
        counter(field, t, t0, t0 + 1.9, 0, 1600, 40, Wt, 46)
    elif k == 17:
        counter(field, t, t0, t0 + 1.9, 0, 30000, 40, Wt, 40, '{:,}+')
    elif k == 18:
        stamp(field, props.flowers(1.0), 12, 50, Wt, 0.7)
        stamp(field, props.flowers(1.0), 78, 52, Wt, 0.6)
        candles(field, t, 46, 92, 5, AMBER * 0.6)


# ================================================================ section helpers
I_INTRO, I_V1, I_PRE, I_HK1, I_V2, I_V3, I_BR, I_HK3, I_OUT1, I_OUT2 = range(10)


def SL(si):
    return [l['i'] for l in LINES if l['sec'] == si]


def first(si):
    return ts(SL(si)[0])


def last(si):
    return te(SL(si)[-1])


T_DROP = PH0 + 8 * BAR                 # the beat comes in (bar 9)
T_V1 = first(I_V1) - 0.35
T_PRE = first(I_PRE) - 0.15
T_HK1 = first(I_HK1) - 0.30
T_V2 = first(I_V2) - 0.25
T_HK2 = 141.30
T_V3 = first(I_V3) - 0.60
T_BR = first(I_BR) - 0.25
T_BUILD = last(I_BR) + 0.05
T_HK3 = first(I_HK3) - 0.30
T_OUT1 = first(I_OUT1) - 0.40
T_BREAK = PH0 + 112 * BAR              # bar 113: everything drops
T_OUT2 = first(I_OUT2) - 0.40
T_FINAL = PH0 + 119 * BAR              # bar 120: the beat comes back for the last chant
T_LASTLINE_END = None
T_END = DUR


@functools.lru_cache(maxsize=256)
def subline(i, u0, u1, x0, y0, w, hmax, hmin=10, max_rows=2):
    """part of line i made of units [u0, u1) -- e.g. the Chinese tail after 'Bring Jensen Back! (Back!)'."""
    l = LINES[i]
    un = l['units']
    a = un[u0][1]
    b = len(l['text']) if u1 >= len(un) else un[u1][1]
    txt = l['text'][a:b].strip()
    a2 = l['text'].index(txt, a)
    units = [[u, s - a2, e - a2] for u, s, e in un[u0:u1]]
    tt = (times(i) or [])[u0:u1]
    return Line(txt, units, tt, x0, y0, w, hmax, hmin, 'center', max_rows)


def utime(i, u):
    tt = times(i)
    return tt[u][0] if tt and u < len(tt) else 1e9


def fall(f, t, t0, seed=0):
    """bulbs fall off the wall after t0: every column lets go at its own moment and accelerates down."""
    if t <= t0:
        return f
    rng = np.random.default_rng(seed)
    delay = rng.uniform(0, 0.55, GW)
    a = np.maximum(0, t - t0 - delay)
    d = (260 * a * a).astype(int)
    out = np.zeros_like(f)
    ys = np.arange(GH)
    for x in np.where(d > 0)[0]:
        src = ys - d[x]
        ok = src >= 0
        col = np.zeros((GH, 3), np.float32)
        col[ok] = f[src[ok], x]
        out[:, x] = col
    keep = d == 0
    out[:, keep] = f[:, keep]
    # what reached the floor piles up dimly
    return out


def hook_block(st, t, idxs, big_rows=True, extra=1.0):
    """the hook: BRING / JENSEN / BACK! slams up top, the Chinese tail lights below, crowd answers."""
    f = st.field
    raise_amt = 0.0
    for i in idxs:
        l = LINES[i]
        un = l['units']
        t_on, t_end = ts(i) - 0.25, te(i) + 0.15
        nxt = idxs[idxs.index(i) + 1] if idxs.index(i) + 1 < len(idxs) else None
        t_off = (ts(nxt) - 0.30) if nxt is not None else t_end + 0.8
        if not (t_on <= t <= t_off + 0.6):
            continue
        g_off = off_gain(t, t_off, 0.10)
        words = [u[0].lower() for u in un]
        if words[:3] == ['bring', 'jensen', 'back']:
            for k, (wd, y) in enumerate(zip(['BRING', 'JENSEN', 'BACK!'], ROWS)):
                tw = utime(i, k)
                if t >= tw - 0.03:
                    a = t - tw
                    hh = int(round(BIGH * (1 + 0.22 * math.exp(-a / 0.06))))
                    m = big(wd, hh)
                    if m.shape[1] > GW - 4:
                        m = cv2.resize(m, (GW - 4, m.shape[0]), interpolation=cv2.INTER_AREA)
                    col = WHITE if k < 2 else GREEN
                    stamp(f, m, center_x(m), y - m.shape[0] / 2, col, g_off * (1 + 1.3 * math.exp(-a / 0.08)) * extra)
            # the answer (Back!)
            if len(un) > 3 and words[3] == 'back':
                tb = utime(i, 3)
                if t >= tb - 0.03:
                    a = t - tb
                    raise_amt = max(raise_amt, math.exp(-max(0, a - 0.25) / 0.35))
                    st.white = max(st.white, 0.35 * math.exp(-a / 0.09) * extra)
            if len(un) > 4:
                L = subline(i, 4, len(un), 6, 156, GW - 12, 21, 12, 2)
                L.draw(f, t, GREEN, g_off)
        elif words[:2] == ['facts', 'first']:
            tf = utime(i, 0)
            if t >= tf - 0.03:
                a = t - tf
                g = g_off * (1 + 1.3 * math.exp(-a / 0.08))
                m1, m2 = big('FACTS', 42), big('FIRST', 42)
                stamp(f, m1, center_x(m1), 26, WHITE, g)
                if t >= utime(i, 1) - 0.03:
                    stamp(f, m2, center_x(m2), 72, WHITE, g)
            tr = utime(i, 2)
            if tr - 0.03 <= t < utime(i, 6) - 0.05:
                Lr = subline(i, 2, 6, 6, 118, GW - 12, 20, 12, 1)
                Lr.draw(f, t, AMBER, g_off)
            tb = utime(i, 6)
            if t >= tb - 0.03:
                for k, (wd, y) in enumerate(zip(['BRING', 'JENSEN', 'BACK!'], [140, 164, 188])):
                    tw = utime(i, 6 + k)
                    if t >= tw - 0.03:
                        a = t - tw
                        m = big(wd, int(22 * (1 + 0.2 * math.exp(-a / 0.06))))
                        stamp(f, m, center_x(m), y - m.shape[0] / 2, GREEN if k == 2 else WHITE,
                              g_off * (1 + 1.2 * math.exp(-a / 0.08)))
        else:
            # Chinese hook lines; the bracketed answer raises the crowd
            resp = [k for k, u in enumerate(un) if l['text'].find('(', 0) >= 0 and u[1] > l['text'].find('(')]
            col = WHITE if ('证据' in l['text']) else GREEN
            nmain = resp[0] if resp else len(un)
            L = subline(i, 0, nmain, 6, 0, GW - 12, 30, 14, 2)
            L2 = subline(i, 0, nmain, 6, int(100 - L.height / 2), GW - 12, 30, 14, 2)
            L2.draw(f, t, col, g_off)
            if resp:
                tr = utime(i, resp[0])
                Lr = subline(i, resp[0], len(un), 6, 150, GW - 12, 24, 14, 1)
                Lr.draw(f, t, WHITE, g_off)
                if t >= tr - 0.03:
                    raise_amt = max(raise_amt, math.exp(-max(0, t - tr - 0.3) / 0.35))
                    st.white = max(st.white, 0.25 * math.exp(-(t - tr) / 0.09))
            if '绿灯' in l['text']:
                bulb_on(f, GW / 2 - 9, 36, 9, utime(i, 0), t)
            if '股价' in l['text']:
                v = np.concatenate([np.linspace(0.9, 0.82, 10), np.linspace(0.8, 0.35, 8)])
                stamp(f, props.chart(110, 40, v, ease((t - ts(i)) / 1.2)), 12, 40, RED, 0.9 * g_off)
            if '证据' in l['text']:
                pass
    return raise_amt


def chants_in(t, a, b, kinds=None):
    return [e for e in chant_events() if a <= e['t'] <= b and (kinds is None or e['kind'] in kinds)]


def chant_slams(st, t, a, b, rows=ROWS, size=BIGH, colors=None, crowd=True):
    """title chant: BRING / JENSEN / BACK land on their own rows at the sung hits; groups replace each other."""
    f = st.field
    ev = chants_in(t - 3.0, a, b)
    ev = [e for e in ev if e['t'] <= t + 0.03 and e['t'] >= a]
    if not ev:
        return 0.0
    gl = ev[-1]['grp']
    grp = [e for e in ev if e['grp'] == gl]
    nxt = [e for e in chant_events() if e['t'] > t + 0.03 and a <= e['t'] <= b]
    raise_amt = 0.0
    row_of = {'BRING': 0, 'JENSEN': 1, 'BACK': 2, 'BACK!': 2}
    for e in grp:
        k = row_of.get(e['text'], 1)
        aa = t - e['t']
        g = (1 + 1.3 * math.exp(-aa / 0.08)) * (1.0 if aa < 1.6 else math.exp(-(aa - 1.6) / 0.3))
        m = big(e['text'], int(size * (1 + 0.22 * math.exp(-aa / 0.06))))
        if m.shape[1] > GW - 4:
            m = cv2.resize(m, (GW - 4, m.shape[0]), interpolation=cv2.INTER_AREA)
        col = (colors or {}).get(k, GREEN if k == 2 else WHITE)
        stamp(f, m, center_x(m), rows[k] - m.shape[0] / 2, col, g)
        if k == 2:
            raise_amt = max(raise_amt, math.exp(-max(0, aa - 0.2) / 0.35))
            st.white = max(st.white, 0.3 * math.exp(-aa / 0.08))
    return raise_amt


# ================================================================ the score
def intro(st, t):
    """0 .. drop: 1993 diner in amber -> 33 years roll -> green light on -> the news -> run it back -> chant."""
    f = st.field
    L0, L1, L2, L3, L4 = SL(I_INTRO)
    tg = utime(L1, len(LINES[L1]['units']) - 3)            # "green light on": the light switches on at 'green'
    t_news = ts(L2) - 0.12
    # run it back: 'run' of line 3 starts a 1 s rewind of the wall's own content
    t_rw = utime(L3, 2)
    teff = t
    if t_rw <= t < t_rw + 0.9:
        teff = t_rw - (t - t_rw) * 7.5
        st.glitch = max(st.glitch, 0.35)
        st.chroma = 3
    if teff < t_news:
        # diner (fades as the counter rolls)
        dine = 1 - 0.75 * ease((teff - ts(L1)) / 3.0)
        stamp(f, props.booth(1.0), 8, 30, AMBER, 0.75 * dine)
        for q, x in enumerate((44, 60, 76)):
            stamp(f, props.cup_body(0.42), x, 66, AMBER, 0.95 * dine)
            stamp(f, props.steam(teff + q, 0.42, heat=1.0, seed=q), x, 52, WHITE, 0.5 * dine)
        status(f, teff, 'SANTA CLARA', '1993', AMBER, 0.7)
        if teff < ts(L1) - 0.2:
            draw_line(f, teff, L0, AMBER, yc=150, hmax=20, t_off=ts(L1) - 0.25)
        else:
            # thirty-three years roll by
            p = ease((teff - ts(L1)) / max(0.5, utime(L1, 3) - ts(L1)))
            yr = int(round(1993 + 33 * p))
            m = big(str(yr), 52)
            stamp(f, m, center_x(m), 100, GREEN if teff >= tg else AMBER, 1.0)
            if teff >= utime(L1, 4) - 0.05:
                # four trillion
                v = ease((teff - utime(L1, 4)) / 0.9)
                cap = '$' + format(int(4e12 * v), ',')
                mm = bigfit(cap, 14)
                stamp(f, mm, center_x(mm), 160, GREEN if teff >= tg else AMBER, 0.95)
                stamp(f, props.chart(110, 30, np.linspace(0.02, 1, 24) ** 2.2, v), 12, 175, GREEN, 0.8)
            draw_line(f, teff, L1, WHITE, yc=212, hmax=12, hmin=9, max_rows=2, gain=0.85)
            bulb_on(f, GW - 26, 36, 9, tg, teff)
            if teff >= tg:
                a = teff - tg
                st.white = max(st.white, 0.25 * math.exp(-a / 0.12))
        ticker(f, teff, 'SANTA CLARA · 1993 · THREE ENGINEERS · ONE BOOTH · ', GH - 16, AMBER, 14, 0.45)
    else:
        a = teff - t_news
        # the cut: electrical glitch, the news in red
        st.glitch = max(st.glitch, 0.9 * math.exp(-a / 0.35) if a >= 0 else 0)
        if teff < ts(L3) - 0.1 or t >= t_rw + 0.9 or teff < t_rw:
            fl = 1.0 if (int(teff * 30) % 7) else 0.35
            m = small('BREAKING', 10)
            stamp(f, m, 6, 30, RED, fl)
            draw_line(f, teff, L2, RED, yc=110, hmax=22, gain=fl)
            ticker(f, teff, 'EFFECTIVE IMMEDIATELY · ', GH - 16, RED, 40, 0.6)
        if teff >= ts(L4) - 0.2:
            st.field[:] *= 0.0
            draw_line(f, teff, L4, WHITE, yc=110, hmax=22, t_off=chants_in(0, 0, 30)[0]['t'] - 0.1)
    if ts(L3) - 0.1 <= t < ts(L4) - 0.2:
        draw_line(f, t, L3, WHITE, yc=170, hmax=20, t_off=ts(L4) - 0.25)
    # call and response, stutter, title build
    ev = [e for e in chants_in(t, 0, T_DROP + 0.01) if e['t'] <= t + 0.03]
    if ev and t > ts(L4) + 0.5:
        f[:] *= 0.0
        e = ev[-1]
        grp = [x for x in ev if x['grp'] == e['grp']]
        for x in grp:
            aa = t - x['t']
            if x['kind'] in ('call', 'stutter'):
                m = bigfit('BRING HIM', 30 if x['kind'] == 'call' else 24)
                g = (1 + 1.2 * math.exp(-aa / 0.06)) * math.exp(-aa / (0.5 if x['kind'] == 'call' else 0.2))
                y = 70 if x['kind'] == 'call' else 70 + (hash(x['t']) % 5 - 2) * 18
                stamp(f, m, center_x(m), y - m.shape[0] / 2, WHITE, g)
            elif x['kind'] == 'resp':
                m = big('BACK!', int(64 * (1 + 0.25 * math.exp(-aa / 0.06))))
                g = (1 + 1.5 * math.exp(-aa / 0.08)) * math.exp(-aa / 0.6)
                stamp(f, m, center_x(m), 150 - m.shape[0] / 2, GREEN, g)
                st.white = max(st.white, 0.3 * math.exp(-aa / 0.08))
                st.crowd = (0.0, math.exp(-max(0, aa - 0.15) / 0.3), GREEN)
            elif x['kind'] == 'title':
                k = {'BRING': 0, 'JENSEN': 1}.get(x['text'], 2)
                m = big(x['text'], 40)
                stamp(f, m, center_x(m), ROWS[k] - m.shape[0] / 2, WHITE if k < 2 else GREEN,
                      1 + 1.2 * math.exp(-aa / 0.07))
        # power climbs into the drop
        st.power = 0.7 + 0.5 * ease((t - 17.7) / 2.5)
        st.zoom = 1.0 + 0.03 * ease((t - 17.7) / 2.5)


def title_drop(st, t):
    f = st.field
    a = t - T_DROP
    st.white = max(st.white, 0.9 * math.exp(-a / 0.12))
    r = chant_slams(st, t, T_DROP - 1.0, T_V1)
    st.crowd = (feat('kick', t), r, GREEN)
    status(f, t, '33 YEARS', 'SAME SEAT', GREEN, 0.6)
    ticker(f, t, 'THIRTY-THREE YEARS · SAME MAN · SAME SEAT · ', GH - 16, GREEN, 22, 0.55)
    st.burn_gain = 1.0


def verse1(st, t):
    f = st.field
    st.burn_scale = 0.6
    idx = SL(I_V1)
    act = [i for i in idx if ts(i) - 0.25 <= t] or [idx[0]]
    i = act[-1]
    k = idx.index(i)
    # motif fades in with its line, out with the next
    nxt = idx[k + 1] if k + 1 < len(idx) else None
    g_in = ease((t - (ts(i) - 0.25)) / 0.2)
    sub = np.zeros_like(f)
    verse1_motif(sub, t, k, i)
    if k > 0 and t < ts(i) - 0.25 + 0.2:
        sub2 = np.zeros_like(f)
        verse1_motif(sub2, t, k - 1, idx[k - 1])
        f += sub2 * (1 - g_in)
    f += sub * g_in
    stack(f, t, idx, GREEN, y_bottom=210, hmax=19, hmin=11, keep=1, dimc=DGREEN, max_rows=2,
          t_end=T_PRE, y_min=112)
    status(f, t, '33 YEARS', 'SAME SEAT', GREEN, 0.5)
    frame_rule(f, GREEN, 0.18)
    ticker(f, t, 'THIRTY-THREE YEARS · SAME MAN · SAME SEAT · ', GH - 16, GREEN, 22, 0.45)


def prechorus(st, t, si=I_PRE):
    """the drums drop out: power follows the 808 heartbeat, the words fall off the pedestal."""
    f = st.field
    L0, L1, L2 = SL(si)
    sub_db = feat('sub', t)
    hb = sat((sub_db + 60) / 30)
    st.power = 0.45 + 0.85 * hb
    st.zoom = 1.0 + 0.04 * ease((t - first(si)) / 7)
    tmp = np.zeros_like(f)
    t_fall = te(L0) + 0.12
    draw_line(tmp, t, L0, RED, yc=80, hmax=24, max_rows=2)
    tmp = fall(tmp, t, t_fall + 0.05, seed=3)
    f += tmp * off_gain(t, ts(L1) - 0.2, 0.3)
    if t >= ts(L1) - 0.2:
        draw_line(f, t, L1, WHITE, yc=150, hmax=20, max_rows=2, t_off=ts(L2) - 0.15)
    if t >= ts(L2) - 0.15:
        un = LINES[L2]['units']
        a = t - ts(L2)
        m1 = bigfit('33 YEARS', 40)
        stamp(f, m1, center_x(m1), 60, AMBER, 1.0 + 0.8 * math.exp(-a / 0.1))
        tw = utime(L2, len(un) - 2)
        if t >= tw - 0.03:
            m2 = bigfit('1 WEEK?', 48)
            stamp(f, m2, center_x(m2), 130, RED, 1.0 + 1.2 * math.exp(-(t - tw) / 0.08))
            st.glitch = max(st.glitch, 0.4 * math.exp(-(t - tw) / 0.2))


def hook(st, t, si, extra=1.0):
    f = st.field
    r = hook_block(st, t, SL(si), extra=extra)
    st.crowd = (feat('kick', t), r, GREEN)
    status(f, t, 'BRING HIM BACK', 'LIVE', GREEN, 0.55, live=True)
    ticker(f, t, 'BRING JENSEN BACK · FACTS FIRST · ', GH - 16, GREEN, 26, 0.5)


def verse2(st, t):
    f = st.field
    st.burn_scale = 0.6
    idx = SL(I_V2)
    act = [i for i in idx if ts(i) - 0.25 <= t] or [idx[0]]
    i = act[-1]
    k = idx.index(i)
    g_in = ease((t - (ts(i) - 0.25)) / 0.18)
    sub = np.zeros_like(f)
    verse2_motif(sub, t, k, i)
    if k > 0 and g_in < 1:
        sub2 = np.zeros_like(f)
        verse2_motif(sub2, t, k - 1, idx[k - 1])
        f += sub2 * (1 - g_in)
    f += sub * g_in
    stack(f, t, idx, WHITE, y_bottom=210, hmax=19, hmin=11, keep=1, dimc=np.array([0.45, 0.30, 0.30], np.float32),
          max_rows=2, t_end=T_HK2 + 0.3, y_min=112)
    dates = [(0, '4.29'), (4, '11.8'), (12, '11.12')]
    d = '4.29'
    for kk, s in dates:
        if k >= kk:
            d = s
    status(f, t, 'NEWS ' + d, 'LIVE', RED, 0.6, live=True)
    # bar 51 (measured): the low end vanishes under 'effective immediately' -- the wall loses power with it
    b51 = PH0 + 50 * BAR
    if b51 <= t < b51 + BAR:
        hb = sat((feat('sub', t) + 60) / 30)
        st.power = 0.40 + 0.75 * hb
    frame_rule(f, RED, 0.2)
    ticker(f, t, 'EFFECTIVE IMMEDIATELY · ', GH - 16, RED, 30, 0.45)
    # ad-libs: counting up
    for e in chants_in(t, t - 1.2, t + 0.02, ('adlib',)):
        if e['t'] <= t:
            aa = t - e['t']
            m, _ = row_mask('（' + e['text'] + '）', 12)
            stamp(f, m, GW - m.shape[1] - 6, 100, AMBER, (1 + math.exp(-aa / 0.08)) * math.exp(-aa / 0.6))


def hook2(st, t):
    f = st.field
    raise_amt = 0.0
    ev = [e for e in chants_in(t, T_HK2 - 0.5, T_V3) if e['t'] <= t + 0.03]
    if not ev:
        return
    cur = ev[-1]
    if cur['kind'] == 'count':
        aa = t - cur['t']
        m = bigfit(cur['text'], 110 if cur['text'] != 'READY?' else 44)
        stamp(f, m, center_x(m), 120 - m.shape[0] / 2, WHITE if cur['text'] == 'READY?' else GREEN,
              1 + 1.5 * math.exp(-aa / 0.07))
        st.white = max(st.white, 0.2 * math.exp(-aa / 0.08))
        st.zoom = 1.0 + 0.06 * math.exp(-aa / 0.15)
    elif cur['kind'] in ('facts', 'run', 'adlib') and cur['text'] not in ('HEY YEAH',):
        grp = [e for e in ev if e['grp'] == cur['grp']]
        if cur['kind'] == 'facts':
            for e in grp:
                aa = t - e['t']
                m = big(e['text'], 52)
                stamp(f, m, center_x(m), (60 if e['text'] == 'FACTS' else 118) - m.shape[0] / 2, WHITE,
                      1 + 1.3 * math.exp(-aa / 0.08))
        elif cur['kind'] == 'run':
            words = [e['text'] for e in grp]
            m = bigfit(' '.join(words), 34)
            stamp(f, m, center_x(m), 112 - m.shape[0] / 2, AMBER, 1.2)
            st.glitch = max(st.glitch, 0.25)
            st.chroma = 3
        else:
            aa = t - cur['t']
            m = bigfit(cur['text'], 60)
            stamp(f, m, center_x(m), 112 - m.shape[0] / 2, RED, (1 + math.exp(-aa / 0.06)) * math.exp(-aa / 0.4))
    else:
        raise_amt = chant_slams(st, t, T_HK2 - 0.5, T_V3)
        hy = [e for e in ev if e['text'] == 'HEY YEAH' and t - e['t'] < 0.9]
        for e in hy:
            aa = t - e['t']
            m = big('HEY YEAH', 20)
            stamp(f, m, center_x(m), 205, AMBER, (1 + math.exp(-aa / 0.06)) * math.exp(-aa / 0.5))
    st.crowd = (feat('kick', t), raise_amt, GREEN)
    status(f, t, 'BRING HIM BACK', 'LIVE', GREEN, 0.55, live=True)
    ticker(f, t, 'BRING JENSEN BACK · ', GH - 16, GREEN, 30, 0.5)


def verse3(st, t):
    """the trending list: every new line enters at #1 and pushes the rest down."""
    f = st.field
    st.burn_scale = 0.5
    idx = SL(I_V3)
    act = [i for i in idx if ts(i) - 0.25 <= t]
    status(f, t, '热搜 TRENDING', '', AMBER, 0.6)
    frame_rule(f, AMBER, 0.2)
    if not act:
        return
    k = len(act) - 1
    p = ease((t - (ts(idx[k]) - 0.25)) / 0.18)
    y = 28.0
    hat = feat('snare', t)
    cols = [WHITE, GREEN, AMBER, RED]
    end_clear = idx[-1]
    for age in range(0, 4):
        j = k - age
        if j < 0:
            break
        i = idx[j]
        L = LN(i, 22, 0, GW - 28, 15, 10, 'center', 2)
        hgt = L.height + 10
        yy = y if age == 0 else y + (0 if p >= 1 else 0)
        # the item slides from where it was (one slot higher) to its new slot
        prev_y = yy - (LN(idx[k], 22, 0, GW - 28, 15, 10, 'center', 2).height + 10) * (1 - p) if age > 0 else yy
        y_draw = prev_y if age > 0 else yy
        gain = [1.0, 0.55, 0.32, 0.16][age] * (1 if age < 3 else (1 - p))
        rank = small(f'#{age + 1}', 12)
        stamp(f, rank, 3, y_draw + 2, cols[age % 4], gain * (0.8 + 0.4 * hat))
        Ld = LN(i, 22, int(round(y_draw)), GW - 28, 15, 10, 'center', 2)
        Ld.draw(f, t, WHITE if age == 0 else np.array([0.7, 0.75, 0.7], np.float32), gain, flash=(age == 0))
        y += hgt
    # specials
    i = idx[k]
    txt = LINES[i]['text']
    if '半杆' in txt:
        # the jacket on a flagpole, lowered to half-mast
        pole_x = 112
        f[120:205, pole_x] += WHITE * 0.5
        yj = 120 + int(36 * ease((t - ts(i) - 0.6) / 1.4))
        stamp(f, props.jacket(0.42), pole_x - 32, yj, GREEN, 0.8)
    if '个位数' in txt:
        m = big('<10%', 36)
        stamp(f, m, GW - m.shape[1] - 8, 160, RED, 0.9 * ease((t - ts(i)) / 0.3))
    if i == end_clear:
        # nobody gets to write the ending yet: the list empties, a cursor blinks
        tc = te(i) + 0.15
        if t >= tc:
            f[:] *= math.exp(-(t - tc) / 0.08)
    if t >= te(end_clear) + 0.15:
        if (t * 2.2) % 1 < 0.55:
            f[112:132, 64:70] += WHITE * 1.0


def bridge(st, t):
    """half-time, piano and pad: one line at a time, white, quiet; the empty chair waits."""
    f = st.field
    idx = SL(I_BR)
    act = [i for i in idx if ts(i) - 0.3 <= t] or [idx[0]]
    i = act[-1]
    k = idx.index(i)
    nxt = idx[k + 1] if k + 1 < len(idx) else None
    t_off = (ts(nxt) - 0.35) if nxt is not None else T_BUILD
    st.zoom = 1.04 + 0.03 * math.sin((t - T_BR) * 0.25)
    st.power = 0.8
    chair_g = 0.22 + (0.55 if '椅子' in LINES[i]['text'] else 0)
    stamp(f, props.chair(1.1), (GW - props.chair(1.1).shape[1]) / 2, 22, GREEN, chair_g)
    txt = LINES[i]['text']
    if '超频' in txt:
        for q in range(8):
            hh = int(min(8, (t - ts(i)) * 5) - q)
            if hh > 0:
                f[200 - q * 6:204 - q * 6, 10:30] += AMBER * 0.5
        lv = 0.86 + 0.06 * math.sin(t * 17)
        f[150:204, 120:124] += GREEN * 0.25
        f[int(204 - 54 * lv):204, 120:124] += GREEN * 0.8
    draw_line(f, t, i, WHITE, yc=150, hmax=19, hmin=11, max_rows=3, t_off=t_off, tau=0.18)
    if k > 0 and t < ts(i):
        draw_line(f, t, idx[k - 1], WHITE, yc=150, hmax=19, hmin=11, max_rows=3, t_off=ts(i) - 0.35, tau=0.18)


def build(st, t):
    f = st.field
    a = (t - T_BUILD) / max(1, T_HK3 - T_BUILD)
    st.power = 0.6 + 0.6 * ease(a)
    st.zoom = 1.0 + 0.05 * ease(a)
    st.burn_gain = 1.0 + 6.0 * ease(a)
    r = chant_slams(st, t, T_BUILD, T_HK3)
    st.crowd = (feat('kick', t), r, GREEN)
    ticker(f, t, 'BRING JENSEN BACK · ', GH - 16, GREEN, 20 + 30 * a, 0.5)


def diner(st, t, si, cold=1.0, dim=1.0):
    f = st.field
    stamp(f, props.booth(0.86), 4, 34, AMBER, 0.55 * dim)
    stamp(f, props.cup_body(0.55), 39, 75, AMBER, 0.85 * dim)
    stamp(f, props.steam(t, 0.55, heat=1 - cold), 39, 57, WHITE, 0.4 * dim)
    stamp(f, props.flowers(0.6), 66, 69, WHITE, 0.5 * dim)
    bulb_on(f, GW - 26, 34, 9, -1, t)


def outro(st, t, si):
    f = st.field
    idx = SL(si)
    dim = 1.0 if si == I_OUT1 else 0.6
    diner(st, t, si, cold=1.0, dim=dim)
    act = [i for i in idx if ts(i) - 0.25 <= t] or [idx[0]]
    i = act[-1]
    stack(f, t, idx[:-1], AMBER if si == I_OUT1 else GREEN, y_bottom=200, hmax=18, hmin=11, keep=1,
          dimc=AMBER * 0.5, max_rows=2, t_end=ts(idx[-1]) - 0.1)
    last_i = idx[-1]
    if t >= ts(last_i) - 0.2:
        # 'Then bring Jensen... back.' -- the last word waits for its beat
        un = LINES[last_i]['units']
        nxt_ch = [e['t'] for e in chant_events() if e['t'] > te(last_i)]
        t_out = min(te(last_i) + 1.2, (nxt_ch[0] - 0.12) if nxt_ch else 1e9)
        for k, (wd, y) in enumerate(zip(['THEN BRING', 'JENSEN…', 'BACK.'], [104, 138, 174])):
            uu = [0, 2, 3][k]
            tw = utime(last_i, min(uu, len(un) - 1))
            if t >= tw - 0.03:
                aa = t - tw
                m = bigfit(wd, 30 if k < 2 else 40)
                stamp(f, m, center_x(m), y - m.shape[0] / 2, GREEN if k == 2 else WHITE,
                      (1 + 1.2 * math.exp(-aa / 0.08)) * off_gain(t, t_out, 0.10))
    if si == I_OUT1:
        ticker(f, t, 'SANTA CLARA · 绿灯还亮着 · ', GH - 16, AMBER, 14, 0.4)
    # run it back on the scratch before the last line
    t_s = ts(idx[-2]) - 0.25
    if t_s <= t < t_s + 0.5:
        st.glitch = max(st.glitch, 0.4 * (1 - (t - t_s) / 0.5))
        st.chroma = 2


def end_chants(st, t, a, b):
    f = st.field
    r = chant_slams(st, t, a, b)
    st.crowd = (feat('kick', t), r, GREEN)


def finale(st, t):
    """the last chant, then everything switches off except one green bulb and what burned in."""
    f = st.field
    end_chants(st, t, T_FINAL - 1.0, T_END)
    t_off = 312.6
    if t >= t_off:
        f[:] *= math.exp(-(t - t_off) / 0.15)
        st.crowd = None
    if t >= T_FINAL + 0.5:
        g = 1.0
        bulb_on(f, GW / 2 - 7, 200, 7, -1, t)
    if t >= 313.2:
        m = small('BRING JENSEN BACK', 9)
        stamp(f, m, center_x(m), 222, WHITE, 0.45 * ease((t - 313.2) / 0.4))


def scene(t):
    st = FrameState()
    f = st.field
    if t < T_DROP:
        intro(st, t)
    elif t < T_V1:
        title_drop(st, t)
    elif t < T_PRE:
        verse1(st, t)
    elif t < T_HK1:
        prechorus(st, t, I_PRE)
    elif t < T_V2:
        hook(st, t, I_HK1)
    elif t < T_HK2:
        verse2(st, t)
    elif t < T_V3:
        hook2(st, t)
    elif t < T_BR:
        verse3(st, t)
    elif t < T_BUILD:
        bridge(st, t)
    elif t < T_HK3:
        build(st, t)
    elif t < T_OUT1:
        hook(st, t, I_HK3, extra=1.15)
    elif t < T_BREAK:
        outro(st, t, I_OUT1)
        if t >= 276.0:
            end_chants(st, t, 276.0, T_BREAK)
    elif t < T_OUT2:
        # bar 113: the floor drops out -- only the cold cup and the green light
        diner(st, t, I_OUT2, cold=1.0, dim=0.45 * (1 - 0.5 * ease((t - T_BREAK) / 1.5)))
        st.power = 0.7
    elif t < max(T_FINAL, te(SL(I_OUT2)[-1]) + 1.0):
        outro(st, t, I_OUT2)
        st.power = 0.75 if t < T_FINAL else 1.0
        if t >= T_FINAL:
            end_chants(st, t, T_FINAL + 2.0, T_END)
    else:
        finale(st, t)
    return st


def beat_drive(st, t):
    """the wall's power supply breathes with the kick; snares shake the camera a hair."""
    k = feat('kick', t)
    s = feat('snare', t)
    in_beat = T_DROP <= t < T_BREAK or t >= T_FINAL
    if in_beat and not (T_PRE <= t < T_HK1):
        st.power *= 0.86 + 0.24 * k
        st.zoom *= 1.0 + 0.012 * k
    return k, s


def render(t):
    st = scene(t)
    k, s = beat_drive(st, t)
    f = st.field
    # burn-in: the hook has left its ghost on the wall
    bl = burn_level(t) * st.burn_gain * st.burn_scale
    if bl > 0.0005:
        f += burn_mask()[..., None] * (GREEN * bl * (1.0 if t < 312.6 else 0.6))
    f *= st.power if t < 312.6 else 1.0
    if st.white > 0:
        f += st.white * 0.35 * np.array([0.8, 1.0, 0.8], np.float32)
    img = expand(np.clip(f, 0, 4))
    if st.crowd is not None:
        bounce, raise_amt, rim = st.crowd
        m = fx.crowd_mask(t, bounce, raise_amt)
        img = fx.apply_crowd(img, m, rim * 0.9)
    sx = (math.sin(t * 91.0) * 2.5 * s) if (T_DROP <= t < T_BREAK) else 0
    img = fx.camera(img, st.zoom, 0.5, 0.5, sx, 0, 0)
    if st.glitch > 0.02:
        img = fx.glitch(img, min(1.0, st.glitch), int(t * FPS))
    if st.chroma:
        img = fx.chroma(img, st.chroma)
    return finish(img, t, grain=0.045, vignette=0.4)


# ================================================================ CLI
SEG = 10.0


def segments():
    n = int(math.ceil(DUR / SEG))
    return [(k, int(round(k * SEG * FPS)), min(NFR, int(round((k + 1) * SEG * FPS)))) for k in range(n)]


def render_seg(k):
    _, f0, f1 = segments()[k]
    out = f'work/segments/s{k:03d}.mkv'
    tmp = out + '.part.mkv'
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        p.stdin.write(render(fi / FPS).tobytes())
    p.stdin.close()
    p.wait()
    os.replace(tmp, out)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    ap.add_argument('--seg', type=int)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--sheet', default='work/preview/sheet.jpg')
    a = ap.parse_args()
    if a.preview:
        os.makedirs('work/preview', exist_ok=True)
        paths = []
        for s in a.preview.split(','):
            t = float(s)
            img = render(t)
            p = f'work/preview/p_{t:07.2f}.png'
            cv2.imwrite(p, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            paths.append(p)
        ims = [cv2.resize(cv2.imread(p), (270, 480), interpolation=cv2.INTER_AREA) for p in paths]
        for im, p in zip(ims, paths):
            cv2.putText(im, os.path.basename(p)[2:-4], (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cols = min(6, len(ims))
        rows = int(math.ceil(len(ims) / cols))
        sheet = np.zeros((rows * 480, cols * 270, 3), np.uint8)
        for n, im in enumerate(ims):
            sheet[(n // cols) * 480:(n // cols + 1) * 480, (n % cols) * 270:(n % cols + 1) * 270] = im
        cv2.imwrite(a.sheet, sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
        print(a.sheet)
    elif a.seg is not None:
        print(render_seg(a.seg))
    elif a.all:
        import multiprocessing as mp
        os.makedirs('work/segments', exist_ok=True)
        todo = [k for k, _, _ in segments() if not os.path.exists(f'work/segments/s{k:03d}.mkv')]
        print(len(todo), 'segments to render', flush=True)
        with mp.get_context('spawn').Pool(a.jobs) as pool:
            for out in pool.imap_unordered(render_seg, todo):
                print(out, flush=True)
