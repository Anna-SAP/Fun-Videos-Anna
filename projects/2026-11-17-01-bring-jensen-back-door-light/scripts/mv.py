#!/usr/bin/env python3
"""Bring Jensen Back 2.0 (the door is shut, the light is on) -- lyric MV, 1080x1920, 30 fps.

  mv.py --preview 12.3,45.6,...      write work/preview/p_<t>.png and a contact sheet
  mv.py --seg K                       render segment K to work/segments/sKKK.mkv
  mv.py --all [--jobs N]              render every missing segment in parallel

The rule of this world (storyboard.md): one closed door, light still on behind it. In the close shot a sung
character is a cut through the door -- the only way to see the light is through the words; when the line is
over its light goes out and the cut stays as a scar. In the far shot the words are the light the door spills
on the floor, and each new line pushes the older ones back toward the door. At the drop the rule flips: the
whole leaf glows and the words are the only dark thing left.

Lyrics come from work/lyrics.txt (the user's sheet, not committed) and work/audio/lyric_timing.json; this
file refers to lines by index and to units by position only.
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

cv2.setNumThreads(int(os.environ.get('CV_THREADS', '2')))
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.chdir(ROOT)

import door as D  # noqa: E402
import lyr  # noqa: E402
import typo as T  # noqa: E402
from door import AMBER, COLD, GOLD, H, RED, TEAL, W, WHITE, smooth  # noqa: E402

FPS = 30
DUR = 301.2
NFR = int(round(DUR * FPS))
SEG = 10.0
BEAT = 0.7060                  # 84.99 BPM
BAR = 4 * BEAT
B0 = 21.306                    # a downbeat (kick on 1 and 3, snare on 2 and 4)
LEAD = 0.045                   # a cut opens this much before its syllable: the eye needs a head start

F = np.load('work/audio/features.npz')
SECS, LINES = lyr.load('work/lyrics.txt')
_tim = json.load(open(os.environ.get('LYR_TIMING', 'work/audio/lyric_timing.json')))
# a performance = one sung pass of a sheet line: {'li': line index, 'u': [[start, end] | None per unit]}
PERFS = sorted(_tim['perfs'], key=lambda p: min(u[0] for u in p['u'] if u))
for _n, _p in enumerate(PERFS):
    _us = [u for u in _p['u'] if u]
    _p['n'] = _n
    _p['t0'] = min(u[0] for u in _us)
    _p['t1'] = max(u[1] for u in _us)
    _p['sec'] = LINES[_p['li']]['sec_name']


def feat(name, t):
    a = F[name]
    x = t * FPS
    i = int(np.clip(math.floor(x), 0, len(a) - 2))
    f = min(1.0, max(0.0, x - i))
    return float(a[i] * (1 - f) + a[i + 1] * f)


def ease(x):
    return float(smooth(x))


def sat(x):
    return max(0.0, min(1.0, x))


def lerp(a, b, k):
    return a + (b - a) * k


def beat_pos(t):
    """(bar number, beat in bar 0..4)"""
    x = (t - B0) / BEAT
    return math.floor(x / 4), x % 4


# ---------------------------------------------------------------------------------------------------------
# the score: sections and their performances
# ---------------------------------------------------------------------------------------------------------
def sec_perfs(name):
    return [p for p in PERFS if p['sec'] == name]


def first_t(name):
    return sec_perfs(name)[0]['t0']


SEC_ORDER = ['Intro', 'Verse 1', 'Pre-Chorus', 'Hook', 'Verse 2', 'Build', 'Drop', 'Interlude', 'Verse 3', 'Bridge',
             'Final Hook', 'Outro']
T0 = {n: first_t(n) for n in SEC_ORDER}
for _a, _b in zip(SEC_ORDER[:-1], SEC_ORDER[1:]):
    assert T0[_a] < T0[_b], (_a, _b)
# a line leaves when the next one in its section starts, or a little after it ends if nothing follows soon
for _n, _p in enumerate(PERFS):
    nxt = PERFS[_n + 1] if _n + 1 < len(PERFS) else None
    if nxt and nxt['sec'] == _p['sec'] and nxt['t0'] - _p['t1'] < 1.6:
        _p['out'] = nxt['t0'] - LEAD - 0.07
    elif nxt:
        _p['out'] = min(_p['t1'] + 0.9, T0[nxt['sec']] - 0.12) if nxt['sec'] != _p['sec'] else _p['t1'] + 0.7
    else:
        _p['out'] = _p['t1'] + 2.5

# rows of each line, as unit counts per row (the sheet's own spaces decide the rest)
ROWS = {
    5: [6, 2, 4, 4], 6: [2, 2, 2, 5], 7: [3, 5, 5, 6], 9: [4, 5, 4, 3], 10: [6, 3, 3, 4], 11: [5, 7, 4, 3],
    12: [2, 6, 7], 15: [3, 3, 3, 4], 18: [4, 3, 6, 6],
    24: [1, 1, 2, 3, 5], 25: [1, 1, 2, 3, 6], 26: [1, 1, 2, 5, 5], 27: [1, 1, 2, 4, 7], 31: [2, 3, 2, 1],
    33: [1, 1, 3, 7], 35: [3, 3, 2, 5], 36: [4, 3, 3, 5], 37: [4, 4, 2, 4, 3], 40: [2, 1, 1, 4, 4],
    42: [6, 1, 6, 1], 43: [3, 6, 5, 3], 44: [5, 4, 5, 3], 45: [4, 4, 5], 46: [6, 3, 2, 8],
    47: [3, 5, 3], 48: [4, 4, 4], 49: [3, 4, 3], 50: [3, 4, 3], 51: [4, 1, 4, 2],
    61: [3, 7, 2, 5], 64: [5, 4, 6], 67: [5, 4, 4, 4], 68: [4, 3, 4, 4], 69: [1, 3, 3, 4], 70: [4, 4, 6, 2],
    71: [4, 5, 3, 4], 72: [3, 7, 4, 4], 75: [6, 5, 4, 6],
    76: [7, 8], 78: [4, 8], 79: [5, 6], 81: [3, 3], 92: [4, 5, 5],
}
for _k in (83, 84, 85, 86, 90):
    ROWS[_k] = ROWS[_k - 59]


def rows_of(li):
    if li not in ROWS:
        return None
    out, k = [], 0
    for n in ROWS[li]:
        out.append(list(range(k, k + n)))
        k += n
    assert k == len(LINES[li]['du']), (li, k, len(LINES[li]['du']))
    return out


S_RAP = T.Style(zh=D.F_SANS, en=D.F_ANTON, cap=300, floor=70)
S_SONG = T.Style(zh=D.F_SERIF, en=D.F_PLAY, cap=270, floor=70, resp_scale=0.50)
S_FLOOR = T.Style(zh=D.F_SERIF, en=D.F_PLAY, cap=200, floor=60, gap=0.16)
S_NEWS = T.Style(zh=D.F_SERIF, en=D.F_MONO, cap=120, floor=50, gap=0.2, en_scale=0.80)
S_CALL = T.Style(zh=D.F_SANS, en=D.F_ANTON, cap=230, floor=70)
S_BIG = T.Style(zh=D.F_SANS, en=D.F_ANTON, cap=1100, floor=70)
S_TOWER = T.Style(zh=D.F_SERIF, en=D.F_PLAY, cap=150, floor=56, gap=0.2)

BOX = (104, 205, 904, 1645)
BOXES = [(104, 205, 904, 1645), (104, 205, 904, 1300), (104, 560, 904, 1645)]
CLOSE_SECS = ('Verse 1', 'Hook', 'Verse 2', 'Build', 'Drop', 'Verse 3', 'Final Hook')
FAR_SECS = ('Intro', 'Pre-Chorus', 'Bridge', 'Outro')
RED_LINES = (68, 69, 70, 71)
FIGURES = {68: (4, 5, 6), 69: (4, 5, 6), 70: (8, 9, 12, 13), 71: (6, 7, 8)}      # the numbers in the market lines


@functools.lru_cache(maxsize=None)
def LAY(n):
    """placed units of performance n in the close shot."""
    p = PERFS[n]
    li = p['li']
    du = LINES[li]['du']
    sec = p['sec']
    k = n - sec_perfs(sec)[0]['n']
    if sec in ('Hook', 'Final Hook'):
        j = li - (24 if sec == 'Hook' else 83)
        if j < 4:
            return T.layout(du, BOX, S_SONG, rows_of(li), align='left', valign='center',
                            row_opts={0: {'cap': 270}, 1: {'cap': 270}, 2: {'cap': 270}, 3: {'cap': 250}, 4: {'cap': 250}})[0]
        if j == 4:      # the title line: call left, response right
            return T.layout(du, (104, 300, 904, 1560), T.Style(zh=D.F_SERIF, en=D.F_PLAY, cap=330, resp_scale=0.5),
                            None, align='left', valign='center', row_opts={1: {'align': 'right'}, 3: {'align': 'right'}})[0]
        if j == 5:      # ten days: leave room for the ten lamps
            return T.layout(du, (104, 330, 904, 1180), S_SONG, None, align='left', valign='center')[0]
        return T.layout(du, BOX, S_SONG, rows_of(li), align='left', valign='center')[0]
    if sec == 'Build':
        if li == 52:
            return None
        ro = {len(ROWS[li]) - 1: {'align': 'right', 'cap': 300}}
        if li == 51:
            ro = {1: {'align': 'right', 'cap': 330}, 3: {'align': 'right', 'cap': 330}}
        return T.layout(du, BOX, S_CALL, rows_of(li), align='left', valign='center', row_opts=ro)[0]
    if sec == 'Drop':
        return None
    align = {'Verse 1': 'left', 'Verse 2': 'right', 'Verse 3': 'left'}[sec]
    if sec == 'Verse 3' and k % 2:
        align = 'right'
    return T.layout(du, BOXES[k % 3], S_RAP, rows_of(li), align=align, valign='center')[0]


def ink_of(p, ui):
    li, sec = p['li'], p['sec']
    u = LINES[li]['du'][ui]
    if sec in ('Hook', 'Final Hook'):
        if u['resp']:
            return AMBER
        return WHITE if not u['cjk'] else GOLD
    if sec == 'Verse 2':
        return WHITE if not u['cjk'] else COLD
    if sec == 'Build':
        return WHITE if u['resp'] else AMBER
    if li in RED_LINES:
        return WHITE if (not u['cjk'] or ui in FIGURES.get(li, ())) else RED
    return GOLD if not u['cjk'] else AMBER


def env_on(t, s, rise=0.05, flash=1.5, tau=0.10):
    """emission of a cut that opened at s: snap on, white-hot, settle."""
    if t < s:
        return 0.0
    a = min(1.0, (t - s) / rise)
    return a * (1.0 + flash * math.exp(-(t - s) / tau))


def draw_perf(G, E, K, t, n, scar=0.15, rise=0.05, flash=1.5, hold=1.0, tau_out=0.055, placed=None, ink=None):
    p = PERFS[n]
    placed = placed if placed is not None else LAY(n)
    out = p['out']
    for q in placed:
        ut = p['u'][q.ui]
        if ut is None:
            continue
        s = ut[0] - LEAD
        if t < s:
            continue
        e = env_on(t, s, rise, flash) * hold
        g = min(1.0, (t - s) / 0.04)
        if t > out:
            d = t - out
            e *= math.exp(-d / tau_out)
            g = scar + (1 - scar) * math.exp(-d / 0.10)
        D.paste_max(G, q.mask, q.x, q.y, g)
        if e > 0.01:
            col = ink if ink is not None else ink_of(p, q.ui)
            D.paste_max(E, q.mask, q.x, q.y, e * (1.45 if col is WHITE else 1.0))
            D.paste_ink(K, q.mask, q.x, q.y, col)


_SCAR = {}


def scar_layer(sec, t, level=0.15):
    """cuts of this section whose light has long gone out, as one cached layer."""
    ps = [p for p in sec_perfs(sec) if t > p['out'] + 1.2 and LAY(p['n']) is not None]
    key = (sec, level)
    have = _SCAR.get(key)
    if have is None or have[0] > len(ps):
        have = (0, np.zeros((H, W), np.float32))
    cnt, lay = have
    for p in ps[cnt:]:
        for q in LAY(p['n']):
            if p['u'][q.ui] is not None:
                D.paste_max(lay, q.mask, q.x, q.y, level)
    _SCAR[key] = (len(ps), lay)
    return lay, len(ps)


def kick_at(t):
    return min(1.0, feat('kick', t))


def snare_at(t):
    return min(1.0, feat('snare', t))


# ---------------------------------------------------------------------------------------------------------
# close shot sections
# ---------------------------------------------------------------------------------------------------------
def rings_layer(events, t):
    """knocks on the door: expanding rings, quarter res. events: [(t0, x, y, strength, speed)]"""
    lay = None
    for t0, x, y, s, v in events:
        a = t - t0
        if a < 0 or a > 0.9:
            continue
        if lay is None:
            lay = np.zeros((H // 4, W // 4), np.float32)
        r = (26 + v * a) / 4
        cv2.circle(lay, (int(x / 4), int(y / 4)), int(r), float(s * (1 - a / 0.9) ** 2), 2, cv2.LINE_AA)
        if a < 0.12:
            cv2.circle(lay, (int(x / 4), int(y / 4)), 5, float(s * (1 - a / 0.12)), -1, cv2.LINE_AA)
    if lay is None:
        return None
    return cv2.GaussianBlur(lay, (0, 0), 0.9)


def _rnd(seed, n=1):
    return np.random.default_rng(seed).random(n)


@functools.lru_cache(maxsize=None)
def knock_events(sec):
    """(Back!) = one heavy knock; the 'hands knocking' phrase = a flurry of small ones."""
    ev, hits = [], []
    base = 24 if sec == 'Hook' else 83
    for p in sec_perfs(sec):
        j = p['li'] - base
        du = LINES[p['li']]['du']
        for ui, u in enumerate(du):
            ut = p['u'][ui]
            if ut is None:
                continue
            if u['resp'] and j < 4:
                r = _rnd(p['n'] * 31 + ui, 2)
                ev.append((ut[0], 300 + 480 * r[0], 500 + 700 * r[1], 1.0, 1500))
                hits.append(ut[0])
            elif u['resp']:
                hits.append(ut[0])
            elif j == 0 and u['cjk']:
                for m in range(3):
                    r = _rnd(p['n'] * 977 + ui * 13 + m, 3)
                    ev.append((ut[0] + 0.10 * m + 0.05 * r[2], 150 + 780 * r[0], 250 + 1350 * r[1], 0.55, 700))
    return tuple(ev), tuple(hits)


def lamps(G, E, K, t, p, y=1330):
    """ten lamps for the ten-day deadline; two of them are lit."""
    us = [u for u in p['u'] if u]
    ta, tb = us[0][0], us[len(us) // 2][0]
    span = max(0.3, tb - ta)
    out = p['out']
    for k in range(10):
        s = ta + span * k / 10.0
        if t < s:
            continue
        cx = 140 + k * 80.5
        m = np.zeros((70, 70), np.uint8)
        cv2.circle(m, (35, 35), 27, 255, -1, cv2.LINE_AA)
        g = 1.0
        e = 0.10
        if k < 2:
            s2 = us[-2 + k][0] - LEAD
            e = max(e, env_on(t, s2, 0.05, 2.0, 0.16))
        if t > out:
            d = t - out
            e *= math.exp(-d / 0.06)
            g = math.exp(-d / 0.1)
        D.paste_max(G, m, cx - 35, y - 35, g)
        if e > 0.01:
            D.paste_max(E, m, cx - 35, y - 35, e)
            D.paste_ink(K, m, cx - 35, y - 35, WHITE)


def crack_points():
    """the falling price line as a crack running down the door (Verse 3, the market lines)."""
    r = np.random.default_rng(156)
    pts = [(150.0, 300.0)]
    x, y = pts[0]
    for k in range(34):
        x += 24
        y += (r.random() - 0.38) * 70 + (36 if 8 < k < 24 else 10)
        pts.append((x, y))
    return np.array(pts, np.float32)


def draw_crack(G, E, K, t):
    ps = [p for p in sec_perfs('Verse 3') if p['li'] in RED_LINES]
    if not ps or t < ps[0]['t0']:
        return
    ta, tb = ps[0]['t0'], ps[-1]['t1']
    k = sat((t - ta) / (tb - ta))
    pts = crack_points()
    n = max(2, int(2 + k * (len(pts) - 2)))
    m = np.zeros((H, W), np.uint8)
    cv2.polylines(m, [pts[:n].astype(np.int32).reshape(-1, 1, 2)], False, 255, 6, cv2.LINE_AA)
    out = ps[-1]['out']
    e, g = 0.50 + 0.5 * math.exp(-((t - ta) % BEAT) / 0.12), 1.0
    if t > out:
        e *= math.exp(-(t - out) / 0.5)
        g = 0.5 + 0.5 * math.exp(-(t - out) / 0.5)
    mf = m.astype(np.float32) / 255 * (1 - np.minimum(1.0, E * 4))       # the crack runs behind the lit words
    np.maximum(G, mf * g, out=G)
    np.maximum(K, (mf * (E < 0.02))[..., None] * RED, out=K)
    np.maximum(E, mf * e, out=E)


def verse(t, sec):
    G, sl = scar_layer(sec, t)
    G = G.copy()
    E = np.zeros((H, W), np.float32)
    K = np.zeros((H, W, 3), np.float32)
    for p in sec_perfs(sec)[sl:]:
        if t >= p['t0'] - LEAD - 0.01:
            draw_perf(G, E, K, t, p['n'])
    kk = kick_at(t)
    st = {'light': AMBER, 'gap': 0.30 + 0.55 * kk, 'sill': 0.55 + 0.45 * kk, 'amb': 0.30, 'key': 0.3 + 0.5 * kk}
    if sec == 'Verse 1':
        drums = sat((t - 24.05) / 0.08)
        st['gap'] = 0.22 + (0.10 + 0.55 * kk) * drums
    if sec == 'Verse 2':
        # Washington, a television in the room: cold light, scanlines, a hi-hat flicker
        tri = (t - B0) / (BEAT / 3)
        fl = 0.16 * (1 - (tri % 1.0)) * (0.4 + 0.6 * snare_at(t))
        st.update(light=COLD, scan=1.0, flick=fl, shadow=0.6)
    if sec == 'Verse 3':
        draw_crack(G, E, K, t)
        red = [p for p in sec_perfs(sec) if p['li'] in RED_LINES]
        if red and red[0]['t0'] - 0.1 < t < red[-1]['out'] + 0.4:
            st['light'] = lerp(AMBER, RED, 0.8)
    return G, E, K, st


def hook(t, sec):
    G = np.zeros((H, W), np.float32)
    sl = 0
    E = np.zeros((H, W), np.float32)
    K = np.zeros((H, W, 3), np.float32)
    base = 24 if sec == 'Hook' else 83
    final = sec == 'Final Hook'
    ps = sec_perfs(sec)
    for p in ps[sl:]:
        if t < p['t0'] - LEAD - 0.01:
            continue
        j = p['li'] - base
        draw_perf(G, E, K, t, p['n'], scar=0.0, rise=0.09, flash=1.1 if j < 4 else 1.4, hold=1.15 if final else 1.0)
        if j == 5:
            lamps(G, E, K, t, p)
    ev, hits = knock_events(sec)
    kk = kick_at(t)
    st = {'light': GOLD, 'gap': 0.55 + 0.6 * kk, 'sill': 0.9 + 0.5 * kk, 'amb': 0.34, 'key': 0.6,
          'ring': rings_layer(ev, t), 'bloom': 1.25 if final else 1.1, 'rays': 1.3 if final else 1.0}
    # every (Back!) is a fist on the door: it jumps and the frame light spits
    hit = max([math.exp(-(t - h) / 0.11) for h in hits if 0 <= t - h < 0.6], default=0.0)
    st['gap'] += 1.6 * hit
    st['hit'] = hit
    # the title line: 'door not open' -> the frame light is choked off; 'light not off' -> everything floods
    for p in ps:
        if p['li'] - base == 4 and p['t0'] - 0.05 <= t < p['out'] + 0.3:
            us = p['u']
            a = us[0][0]
            b = us[5][0] if us[5] else a + 1.4
            if t < b - 0.05:
                k = sat((t - a) / 0.25)
                st['gap'] = lerp(st['gap'], 0.03, k)
                st['sill'] = lerp(st['sill'], 0.25, k)
            else:
                k = math.exp(-(t - b) / 0.9)
                st['gap'] = st['gap'] + 2.2 * k
                st['sill'] = st['sill'] + 1.6 * k
                st['flash'] = 0.10 * math.exp(-(t - b) / 0.10)
                st['flash_c'] = GOLD
    return G, E, K, st


def big_unit(du, ui, style=S_BIG, box=(100, 260, 980, 1600), cap=None, bare=False):
    one = [dict(du[ui], phrase=0, brk=False)]
    if bare:                                  # the sheet's dash leads into words that were not sung here
        one[0]['post'] = one[0]['post'].replace(' —', '')
    st = style if cap is None else T.Style(zh=style.zh, en=style.en, cap=cap)
    return T.layout(one, box, st, [[0]], align='center', valign='center')[0][0]


def build(t):
    G = np.zeros((H, W), np.float32)
    E = np.zeros((H, W), np.float32)
    K = np.zeros((H, W, 3), np.float32)
    ps = sec_perfs('Build')
    a, b = ps[0]['t0'], T0['Drop']
    rise = sat((t - a) / (b - a))
    kk = kick_at(t)
    st = {'light': AMBER, 'gap': 0.25 + 1.0 * rise ** 2 + 0.4 * kk, 'sill': 0.5 + 0.9 * rise, 'amb': 0.26 + 0.1 * rise,
          'key': 0.3 + rise}
    hit = 0.0
    for p in ps:
        if t < p['t0'] - LEAD - 0.01:
            continue
        du = LINES[p['li']]['du']
        if p['li'] == 52:
            # Ready? three, two, one: one mark at a time, each filling the door
            for ui in range(len(du)):
                ut = p['u'][ui]
                if ut is None:
                    continue
                nx = [p['u'][j][0] for j in range(ui + 1, len(du)) if p['u'][j]]
                end = (nx[0] if nx else T0['Drop']) - LEAD
                s = ut[0] - LEAD
                if s <= t < end + 0.25:
                    q = big_unit(du, ui, cap=330 if ui == 0 else 1100)
                    e = env_on(t, s, 0.04, 2.0, 0.10)
                    g = 1.0
                    if t > end:
                        e *= math.exp(-(t - end) / 0.05)
                        g = math.exp(-(t - end) / 0.08)
                    D.paste_max(G, q.mask, q.x, q.y, g)
                    D.paste_max(E, q.mask, q.x, q.y, e)
                    D.paste_ink(K, q.mask, q.x, q.y, WHITE if ui else GOLD)
                    hit = max(hit, math.exp(-(t - s) / 0.10))
            continue
        draw_perf(G, E, K, t, p['n'], scar=0.0, flash=1.6)
        for ui, u in enumerate(du):
            ut = p['u'][ui]
            if ut and u['resp'] and 0 <= t - ut[0] < 0.5:
                hit = max(hit, math.exp(-(t - ut[0]) / 0.10))
        if p['li'] == 51:
            # who lit the light? (flood)  who holds the switch? (black)
            us = p['u']
            if us[4] and t >= us[4][0] - LEAD:
                k = math.exp(-(t - us[4][0]) / 0.5)
                st['gap'] += 2.5 * k
                st['sill'] += 2.0 * k
                st['flash'] = 0.16 * math.exp(-(t - us[4][0]) / 0.09)
                st['flash_c'] = GOLD
            if us[9] and t >= us[9][0] - LEAD:
                k = sat((t - us[9][0]) / 0.06)
                st['gap'] *= (1 - 0.97 * k)
                st['sill'] *= (1 - 0.97 * k)
                st['amb'] *= (1 - 0.7 * k)
                st['key'] = 0.0
    if t >= ps[-1]['t0'] - LEAD and ps[-1]['li'] == 52:
        st['gap'], st['sill'], st['amb'], st['key'] = 0.02, 0.05, 0.10, 0.0
    st['hit'] = hit
    return G, E, K, st


def drop(t):
    """the rule flips: the leaf itself blazes and the words are what is dark."""
    G = np.zeros((H, W), np.float32)
    E = np.zeros((H, W), np.float32)
    K = np.zeros((H, W, 3), np.float32)
    ps = sec_perfs('Drop')
    kk = kick_at(t)
    st = {'light': AMBER, 'gap': 1.2 + 0.8 * kk, 'sill': 1.6 + 0.6 * kk, 'amb': 0.4, 'key': 0.0, 'blaze': 0.0,
          'shadow': 0.3}
    cur = None
    for p in ps:
        du = LINES[p['li']]['du']
        for ui in range(len(du)):
            if p['u'][ui] and p['u'][ui][0] - LEAD <= t:
                if cur is None or p['u'][ui][0] >= cur[2]:
                    cur = (p, ui, p['u'][ui][0])
    if cur is None:
        return G, E, K, st
    p, ui, s = cur
    du = LINES[p['li']]['du']
    u = du[ui]
    occ = [q['n'] for q in ps].index(p['n'])
    hot = [AMBER, lerp(AMBER, RED, 0.55), GOLD, lerp(GOLD, WHITE, 0.5), WHITE][min(occ, 4)]
    age = t - (s - LEAD)
    nxt = min([q['u'][j][0] for q in ps for j in range(len(q['u'])) if q['u'][j] and q['u'][j][0] > s + 1e-3],
              default=T0['Interlude'])
    gone = sat((t - (nxt - LEAD - 0.05)) / 0.05) if nxt - s > 0.9 else 0.0
    st['hit'] = math.exp(-age / 0.09)
    st['light'] = hot
    if p['li'] == 53 and u['resp']:
        # (Hey!): for one beat the door is a door again, and the shout is a cut of light
        first = ui if du[ui]['pre'] else ui - 1
        for uj, box in ((first, (100, 330, 980, 930)), (first + 1, (100, 950, 980, 1550))):
            if uj > ui or p['u'][uj] is None:
                continue
            q = big_unit(du, uj, cap=520, box=box)
            sj = p['u'][uj][0]
            e = env_on(t, sj - LEAD, 0.03, 2.2, 0.08) * (1 - gone)
            D.paste_max(G, q.mask, q.x, q.y, 1.0 - gone)
            D.paste_max(E, q.mask, q.x, q.y, e)
            D.paste_ink(K, q.mask, q.x, q.y, WHITE)
        st['blaze'] = 0.0
        st['gap'] = 0.5
        st['sill'] = 0.8
    else:
        cap = 1100 if p['li'] == 53 else 620
        if p['li'] == 53:
            q = big_unit(du, ui, cap=cap)
            D.paste_max(G, q.mask, q.x, q.y, 1.0)
        else:
            # BRING! JENSEN! BACK! stack up, one row each
            row_y = {0: (240, 700), 1: (700, 1160), 2: (1160, 1620)}
            for uj in range(0, ui + 1):
                if uj in row_y and p['u'][uj]:
                    qq = big_unit(du, uj, cap=620, box=(104, row_y[uj][0], 976, row_y[uj][1]),
                                  bare=(uj + 1 < len(du) and p['u'][uj + 1] is None))
                    D.paste_max(G, qq.mask, qq.x, qq.y, 1.0)
        st['blaze'] = (0.80 + 0.45 * math.exp(-age / 0.12)) * (1 - 0.55 * gone)
        st['amb'] = 0.6
    return G, E, K, st


def close_frame(t, sec):
    if sec in ('Verse 1', 'Verse 2', 'Verse 3'):
        G, E, K, st = verse(t, sec)
    elif sec in ('Hook', 'Final Hook'):
        G, E, K, st = hook(t, sec)
    elif sec == 'Build':
        G, E, K, st = build(t)
    elif sec == 'Drop':
        G, E, K, st = drop(t)
    else:
        raise ValueError(sec)
    return G, E, K, st


def idle_door(t, scars_from=None, level=0.15, heal=1.0):
    """the door with nothing being sung on it (seen from afar): old scars only."""
    if scars_from:
        G = scar_layer(scars_from, 1e9, 0.15)[0] * (heal * level / 0.15)
    else:
        G = np.zeros((H, W), np.float32)
    return G, np.zeros((H, W), np.float32), np.zeros((H, W, 3), np.float32)


# ---------------------------------------------------------------------------------------------------------
# far shot: the hall, the door, the light it spills on the floor
# ---------------------------------------------------------------------------------------------------------
CW, CH = 1080, 1500
TILE_W, TILE_H = int(round(W * D.FS)), int(round(H * D.FS))
TILE_X = int(round(540 - TILE_W / 2))
TILE_Y = int(round(D.FDY1 - D.DY1 * D.FS))
FLOOR_Y = D.FDY1 + 4
HOMO = cv2.getPerspectiveTransform(
    np.float32([[0, 0], [CW, 0], [CW, CH], [0, CH]]),
    np.float32([[D.FDX0 - 60, FLOOR_Y + 26], [D.FDX1 + 60, FLOOR_Y + 26], [W + 190, H + 60], [-190, H + 60]]))


@functools.lru_cache(maxsize=None)
def far_assets():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    wall = 0.034 + 0.018 * D.rng_noise((H, W), 21, 20) + 0.008 * D.rng_noise((H, W), 22, 1.5)
    alb = np.dstack([wall * 0.92, wall * 0.98, wall * 1.10])
    fl = (yy >= FLOOR_Y).astype(np.float32)[..., None]
    floor = 0.050 + 0.020 * D.rng_noise((H, W), 23, 26) + 0.010 * D.rng_noise((H, W), 24, 2.0)
    # floor boards receding to the door: faint lines converging on the vanishing point
    vx, vy = 540.0, FLOOR_Y - 150.0
    ang = (xx - vx) / np.maximum(yy - vy, 1.0)
    seams = (np.abs(((ang * 9.0) % 1.0) - 0.5) > 0.47).astype(np.float32)
    floor = floor * (1 - 0.25 * seams)
    alb = alb * (1 - fl) + np.dstack([floor * 0.92, floor * 0.97, floor * 1.06]) * fl
    # skirting line
    alb[int(FLOOR_Y) - 3:int(FLOOR_Y)] *= 0.5
    # door-edge light, far scale
    g = np.zeros((H, W), np.float32)
    x0, x1, y0, y1 = int(D.FDX0), int(D.FDX1), int(D.FDY0), int(D.FDY1)
    g[y0:y1, x0 - 2:x0] = 1
    g[y0:y1, x1:x1 + 2] = 1
    g[y0 - 2:y0, x0 - 2:x1 + 2] = 1
    gap = cv2.GaussianBlur(g, (0, 0), 1.0)
    gap = gap / gap.max() + 0.7 * cv2.GaussianBlur(g, (0, 0), 14) / cv2.GaussianBlur(g, (0, 0), 14).max() \
        + 0.45 * cv2.GaussianBlur(g, (0, 0), 60) / cv2.GaussianBlur(g, (0, 0), 60).max()
    s = np.zeros((H, W), np.float32)
    s[y1:y1 + 3, x0:x1] = 1
    sill = cv2.GaussianBlur(s, (0, 0), 1.4)
    sill = sill / sill.max() + 0.8 * cv2.GaussianBlur(s, (0, 0), 16) / cv2.GaussianBlur(s, (0, 0), 16).max()
    # the fan of light on the floor
    d = np.clip((yy - FLOOR_Y) / (H - FLOOR_Y), 0, 1)
    half = (D.FDX1 - D.FDX0) / 2 + 20 + d * 620
    side = np.clip(1 - np.abs(xx - 540) / half, 0, 1)
    spill = (yy > FLOOR_Y) * smooth(side * 1.6) * (0.16 + 0.84 * np.exp(-d * 3.2))
    spill = cv2.GaussianBlur(spill.astype(np.float32), (0, 0), 6)
    # feather for the door tile
    a = np.zeros((TILE_H, TILE_W), np.float32)
    a[10:-10, 10:-10] = 1
    a = cv2.GaussianBlur(a, (0, 0), 5)
    return alb.astype(np.float32), gap.astype(np.float32), sill.astype(np.float32), spill.astype(np.float32), a[..., None]


def far_perfs_of(sec):
    return sec_perfs(sec)


@functools.lru_cache(maxsize=None)
def FLAY(n):
    """a line set on the floor canvas, top at v=0."""
    p = PERFS[n]
    li = p['li']
    st = S_NEWS if li == 0 else S_FLOOR
    cap_box = 470 if li != 97 else 520
    placed, bb = T.layout(LINES[li]['du'], (100, 0, 980, cap_box), st, rows_of(li), align='center', valign='top',
                          max_rows=3)
    return placed, bb[3]


SLOT = 560


def floor_text(t, sec):
    """(mask, emission, tint) warped onto the floor, or None."""
    ps = far_perfs_of(sec)
    if not ps or t < ps[0]['t0'] - 0.3:
        return None
    # continuous line position: slides one slot in the half second before the next line starts
    c = 0.0
    for k in range(1, len(ps)):
        c += ease((t - (ps[k]['t0'] - LEAD - 0.26)) / 0.34)
    M = np.zeros((CH, CW), np.float32)
    E = np.zeros((CH, CW), np.float32)
    K = np.zeros((CH, CW, 3), np.float32)
    any_ = False
    for k, p in enumerate(ps):
        back = c - k
        if back > 2.6 or t < p['t0'] - LEAD - 0.02:
            continue
        placed, hgt = FLAY(p['n'])
        v0 = CH - 685 - back * SLOT + (470 - hgt) * 0.5
        dim = max(0.0, 1 - 0.50 * back) ** 1.5
        if sec == 'Outro' and k == len(ps) - 1:
            dim = 1.0
        if t > p['out'] + 0.0 and k == len(ps) - 1:
            dim *= math.exp(-(t - p['out']) / 0.8)
        for q in placed:
            ut = p['u'][q.ui]
            if ut is None or t < ut[0] - LEAD:
                continue
            e = env_on(t, ut[0] - LEAD, 0.07, 1.2, 0.14) * dim
            if p['li'] == 0:
                e *= 0.65 + 0.35 * (math.sin(t * 61) > -0.4)
            D.paste_max(M, q.mask, q.x, q.y + v0, 1.0)
            D.paste_max(E, q.mask, q.x, q.y + v0, e)
            col = WHITE if (p['li'] == 0 or not LINES[p['li']]['du'][q.ui]['cjk']) else GOLD
            D.paste_ink(K, q.mask, q.x, q.y + v0, col)
            any_ = True
    if not any_:
        return None
    EK = E[..., None] * (K / np.maximum(K.max(axis=2, keepdims=True), 1e-4))
    return cv2.warpPerspective(EK, HOMO, (W, H), flags=cv2.INTER_LINEAR)


def compose_far(tile_lin, t, st, text=None):
    alb, gapm, sillm, spillm, feather = far_assets()
    light = np.asarray(st.get('light', AMBER), np.float32)
    gap, sill = st.get('gap', 0.5), st.get('sill', 0.9)
    leak = (gap * gapm + sill * (sillm + 1.1 * spillm))[..., None] * light
    lin = alb * (st.get('amb_far', 0.22) + 3.0 * leak) + 0.42 * leak
    tile = cv2.resize(tile_lin, (TILE_W, TILE_H), interpolation=cv2.INTER_AREA)
    reg = lin[TILE_Y:TILE_Y + TILE_H, TILE_X:TILE_X + TILE_W]
    reg[:] = reg * (1 - feather) + tile * feather
    if text is not None:
        t4 = cv2.resize(text, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        glow = cv2.resize(0.6 * cv2.GaussianBlur(t4, (0, 0), 4) + 0.5 * cv2.GaussianBlur(t4, (0, 0), 16), (W, H),
                          interpolation=cv2.INTER_LINEAR)
        lin += text * 1.25 + alb * glow * 5.0 + glow * 0.22
    return lin


def zoom_mats(z):
    """affine of the far scene and of the full-res close frame for camera position z (0 far .. 1 close)."""
    s = (1.0 / D.FS) ** z
    k = (s - 1) / (1.0 / D.FS - 1)
    # the tile rect in far coords -> screen rect
    x0 = TILE_X * (1 - k)
    y0 = TILE_Y * (1 - k)
    A = np.float32([[s, 0, x0 - s * TILE_X], [0, s, y0 - s * TILE_Y]])
    c = s * D.FS
    B = np.float32([[c, 0, x0], [0, c, y0]])
    return A, B, c


# ---------------------------------------------------------------------------------------------------------
# interlude: another city switches a light on
# ---------------------------------------------------------------------------------------------------------
TOWER_X = 540
WATER_Y = 1330


def _tower_poly():
    """outline of a stylised eight-tier tower, as a list of polygons (base -> spire)."""
    polys = []
    polys.append([(TOWER_X - 190, WATER_Y), (TOWER_X + 190, WATER_Y), (TOWER_X + 140, 1085), (TOWER_X - 140, 1085)])
    y = 1085
    for k in range(8):
        h = 84
        polys.append([(TOWER_X - 130, y), (TOWER_X + 130, y), (TOWER_X + 158, y - h + 6), (TOWER_X - 158, y - h + 6)])
        y -= h
    polys.append([(TOWER_X - 96, y), (TOWER_X + 96, y), (TOWER_X + 70, y - 46), (TOWER_X - 70, y - 46)])
    polys.append([(TOWER_X - 46, y - 46), (TOWER_X + 46, y - 46), (TOWER_X + 28, y - 86), (TOWER_X - 28, y - 86)])
    polys.append([(TOWER_X - 6, y - 86), (TOWER_X + 6, y - 86), (TOWER_X + 2, y - 230), (TOWER_X - 2, y - 230)])
    return polys


@functools.lru_cache(maxsize=None)
def tower_assets():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    sky = np.clip(yy / WATER_Y, 0, 1)
    base = np.dstack([0.010 + 0.035 * sky ** 3, 0.016 + 0.050 * sky ** 2.5, 0.040 + 0.075 * sky ** 2])
    haze = np.exp(-((yy - WATER_Y) / 240.0) ** 2) * 0.05
    base += haze[..., None] * np.array([0.9, 0.7, 0.6], np.float32)
    # stars, and the hills behind the city
    rs = np.random.default_rng(303)
    for _ in range(260):
        sx, sy = int(rs.integers(0, W)), int(rs.integers(0, int(WATER_Y * 0.62)))
        base[sy:sy + 2, sx:sx + 2] += (0.05 + 0.25 * rs.random() ** 3) * (1 - sy / (WATER_Y * 0.62))
    hx = np.arange(W, dtype=np.float32)
    ridge = WATER_Y - 150 - 60 * np.sin(hx / 190.0 + 1.0) - 35 * np.sin(hx / 71.0) - 18 * np.sin(hx / 23.0 + 2)
    hills = (yy > ridge[None, :]) & (yy < WATER_Y)
    base = np.where(hills[..., None], base * 0.35 + np.array([0.004, 0.007, 0.014], np.float32), base)
    # distant skyline with a few lit windows
    r = np.random.default_rng(101)
    sil = np.zeros((H, W), np.float32)
    lights = np.zeros((H, W), np.float32)
    x = -10
    while x < W:
        bw = int(r.integers(34, 96))
        bh = int(r.integers(40, 210))
        if abs(x + bw / 2 - TOWER_X) < 190:
            bh = int(bh * 0.45)
        cv2.rectangle(sil, (x, WATER_Y - bh), (x + bw, WATER_Y), 1.0, -1)
        for wy in range(WATER_Y - bh + 8, WATER_Y - 6, 11):
            for wx in range(x + 6, x + bw - 6, 9):
                if r.random() < 0.20:
                    lights[wy:wy + 4, wx:wx + 4] = 0.25 + 0.75 * r.random()
        x += bw + int(r.integers(2, 10))
    tw = np.zeros((H, W), np.float32)
    for poly in _tower_poly():
        cv2.fillPoly(tw, [np.int32(poly)], 1.0, cv2.LINE_AA)
    edge = np.clip(cv2.GaussianBlur(tw, (0, 0), 1.2) - cv2.erode(tw, np.ones((5, 5), np.uint8)), 0, 1)
    # the tower's own window grid, barely on
    grid = ((xx % 8 < 4) & (yy % 9 < 4)).astype(np.float32) * tw * (yy < 1085) * (yy > 360)
    body = np.maximum(sil * 0.9, tw)
    base = base * (1 - body[..., None]) + body[..., None] * np.array([0.012, 0.016, 0.026], np.float32)
    stat = base + lights[..., None] * np.array([1.0, 0.72, 0.36], np.float32) * 0.5 * (1 - tw[..., None])
    return stat.astype(np.float32), tw, edge.astype(np.float32), grid.astype(np.float32)


@functools.lru_cache(maxsize=None)
def tower_words():
    """dot-matrix words on the tiers: [(line index, unit index, mask, x, y)]"""
    out = []
    spec = {57: [(8, 6), (9, 5), (10, 4)], 58: [(6, 2), (7, 1)]}     # unit -> tier (0 = lowest)
    for li, items in spec.items():
        du = LINES[li]['du']
        for ui, tier in items:
            txt = du[ui]['tok'].upper()
            f = D.font(D.F_ANTON, 40)
            x0, y0, x1, y1 = f.getbbox(txt, anchor='ls')
            from PIL import Image, ImageDraw
            im = Image.new('L', (x1 - x0 + 4, y1 - y0 + 4), 0)
            ImageDraw.Draw(im).text((2 - x0, 2 - y0), txt, font=f, fill=255, anchor='ls')
            m = np.asarray(im, np.float32) / 255
            tw, th = 244, 56
            m = cv2.resize(m, (tw, th), interpolation=cv2.INTER_AREA)
            # windows: keep a 4x4 cell lit out of every 6x6
            yy, xx = np.mgrid[0:th, 0:tw]
            m = m * ((xx % 5 < 4) & (yy % 5 < 4))
            ty = 1085 - 84 * tier - 70
            out.append((li, ui, m.astype(np.float32), TOWER_X - tw // 2, ty))
    return out


@functools.lru_cache(maxsize=None)
def TLAY(n):
    p = PERFS[n]
    return T.layout(LINES[p['li']]['du'], (90, WATER_Y + 40, 990, WATER_Y + 400), S_TOWER, rows_of(p['li']), align='center',
                    valign='center', max_rows=3)[0]


def tower_frame(t):
    stat, tw, edge, grid = tower_assets()
    ps = sec_perfs('Interlude')
    a = ps[0]['t0']
    on = sat((t - a + 0.5) / 1.5)
    lin = stat.copy()
    kk = kick_at(t)
    lin += edge[..., None] * TEAL * (0.10 + 0.25 * on + 0.10 * kk)
    lin += grid[..., None] * GOLD * (0.02 + 0.10 * on)
    bl = 0.5 + 0.5 * math.sin(t * 2 * math.pi / (2 * BEAT))
    cv2.circle(lin, (TOWER_X, 1085 - 84 * 8 - 230 - 6), 5, (float(1.6 * bl), float(0.10 * bl), float(0.06 * bl)), -1, cv2.LINE_AA)
    # the facade words, lit window by window as they are sung
    E = np.zeros((H, W), np.float32)
    for li, ui, m, x, y in tower_words():
        for p in ps:
            if p['li'] == li and p['u'][ui] and t >= p['u'][ui][0] - LEAD:
                s = p['u'][ui][0] - LEAD
                # sweep left to right over the word's length
                dur = max(0.15, p['u'][ui][1] - p['u'][ui][0]) * 0.7
                k = sat((t - s) / dur)
                mm = m.copy()
                mm[:, int(m.shape[1] * k):] = 0
                D.paste_max(E, mm, x, y, 1.0 + 1.2 * math.exp(-(t - s) / 0.25))
    # lyric line over the water
    TE = np.zeros((H, W), np.float32)
    TK = np.zeros((H, W, 3), np.float32)
    for p in ps:
        if t < p['t0'] - LEAD - 0.02:
            continue
        for q in TLAY(p['n']):
            ut = p['u'][q.ui]
            if ut is None or t < ut[0] - LEAD:
                continue
            e = env_on(t, ut[0] - LEAD, 0.10, 0.9, 0.18)
            if t > p['out']:
                e *= math.exp(-(t - p['out']) / 0.22)
            if e > 0.01:
                D.paste_max(TE, q.mask, q.x, q.y, e)
                D.paste_ink(TK, q.mask, q.x, q.y, WHITE if not LINES[p['li']]['du'][q.ui]['cjk'] else GOLD)
    led = E[..., None] * lerp(GOLD, WHITE, 0.3)
    txt = TE[..., None] * (TK / np.maximum(TK.max(axis=2, keepdims=True), 1e-4))
    emis = led * 1.6 + txt * 1.25
    e4 = cv2.resize(emis, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    glow = cv2.resize(0.6 * cv2.GaussianBlur(e4, (0, 0), 4) + 0.6 * cv2.GaussianBlur(e4, (0, 0), 18), (W, H),
                      interpolation=cv2.INTER_LINEAR)
    lin += emis + glow * 0.55
    # water: the city upside down, smeared and rippling; the lyric floats over it
    hgt = H - WATER_Y
    src = lin[WATER_Y - hgt:WATER_Y][::-1] - txt[WATER_Y - hgt:WATER_Y][::-1] * 0
    yy = np.arange(hgt, dtype=np.float32)[:, None]
    xx = np.arange(W, dtype=np.float32)[None, :]
    mapx = (xx + 5.0 * np.sin(yy * 0.22 + t * 2.2) * (0.3 + yy / hgt)).astype(np.float32)
    mapy = np.repeat(yy, W, axis=1).astype(np.float32)
    refl = cv2.remap(cv2.blur(src, (3, 21)), np.repeat(mapx, 1, axis=0) + np.zeros((hgt, 1), np.float32), mapy,
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    fall = np.linspace(0.55, 0.10, hgt, dtype=np.float32)[:, None, None]
    water = refl * fall
    lin[WATER_Y:] = water + (txt[WATER_Y:] * 1.25 + glow[WATER_Y:] * 0.5)
    return lin, {'exposure': 1.15, 'zoom': 1.0 + 0.02 * ease((t - a) / 11.0), 'grain': 0.7}


# ---------------------------------------------------------------------------------------------------------
# the timeline
# ---------------------------------------------------------------------------------------------------------
def cam_z(t):
    """camera position: 0 = down the hall, 1 = at the door. Moves happen in the gaps between sections."""
    v1, pre, hk = T0['Verse 1'], T0['Pre-Chorus'], T0['Hook']
    br, fh, ou = T0['Bridge'], T0['Final Hook'], T0['Outro']
    if t < v1:
        return ease((t - (v1 - 3.6)) / 3.3) ** 1.0
    if t < pre - 0.25:
        return 1.0
    if t < hk - 0.5:
        return 1.0 - ease((t - (pre - 0.25)) / 0.55)
    if t < hk:
        return sat((t - (hk - 0.5)) / 0.42) ** 3
    if t < br - 0.25:
        return 1.0
    if t < fh - 0.5:
        return 1.0 - ease((t - (br - 0.25)) / 0.55)
    if t < fh:
        return sat((t - (fh - 0.5)) / 0.42) ** 3
    if t < ou - 0.2:
        return 1.0
    return 1.0 - ease((t - (ou - 0.2)) / 2.6)


def section_at(t):
    cur = SEC_ORDER[0]
    for n in SEC_ORDER:
        if t >= T0[n] - 0.12:
            cur = n
    return cur


FAR_DOOR = {'Intro': None, 'Pre-Chorus': 'Verse 1', 'Bridge': 'Verse 3', 'Outro': 'Final Hook'}


def title_card(lin, t):
    """song title, small, on the wall above the door, in the first seconds."""
    a = sat((t - 0.9) / 0.8) * sat((4.3 - t) / 0.8)
    if a <= 0:
        return
    m = np.zeros((H, W), np.float32)
    g, ox, oy, _ = D.glyph('门没开，灯没关', D.F_SERIF, 64)
    D.paste_max(m, g, 540 - g.shape[1] // 2, 1250)
    g, ox, oy, _ = D.glyph('BRING JENSEN BACK 2.0  ·  WEEK TWO', D.F_MONO, 26)
    D.paste_max(m, g, 540 - g.shape[1] // 2, 1350, 0.75)
    lin += (m * a * 0.8)[..., None] * GOLD


def end_card(lin, t):
    a = sat((t - 296.6) / 1.2) * sat((DUR - 0.25 - t) / 0.8)
    if a <= 0:
        return
    m = np.zeros((H, W), np.float32)
    g, ox, oy, _ = D.glyph('BRING JENSEN BACK 2.0  ·  WEEK TWO', D.F_MONO, 24)
    D.paste_max(m, g, 540 - g.shape[1] // 2, 1716, 0.7)
    lin += (m * a * 0.7)[..., None] * GOLD


def render(t):
    sec = section_at(t)
    st = {}
    kk = kick_at(t)
    sn = snare_at(t)
    if sec == 'Interlude':
        lin, st = tower_frame(t)
        a, b = T0['Interlude'], T0['Verse 3']
        # in: out of the white of the drop; out: a hard cut back to the door on the downbeat
        st['flash'] = 0.9 * math.exp(-(t - (a - 0.12)) / 0.30)
        st['flash_c'] = WHITE
        st['shake'] = (0.0, 0.0)
        return D.finish(lin, t, st)
    z = cam_z(t)
    if sec in CLOSE_SECS:
        G, E, K, st = close_frame(t, sec)
        # the door heals when the section is about to end (scars fade)
    else:
        src = FAR_DOOR[sec]
        heal = 1.0
        if sec == 'Outro':
            heal = 1.0 - 0.6 * sat((t - T0['Outro']) / 12.0)
        G, E, K = idle_door(t, src, heal=heal)
        st = {'light': AMBER, 'gap': 0.34 + 0.30 * kk, 'sill': 0.75 + 0.35 * kk, 'amb': 0.26, 'key': 0.5}
        if sec == 'Intro':
            on = sat((t - 0.4) / 3.0)
            st['gap'] = (0.10 + 0.25 * sat((t - 8.5) / 8.0) + 0.2 * kk) * on
            st['sill'] = (0.55 + 0.35 * sat((t - 8.5) / 8.0)) * on * (0.82 + 0.18 * math.sin(t * 37) * (t < 8))
            st['amb'] = 0.10 + 0.16 * sat((t - 6) / 12.0)
            st['key'] = 0.5 * on
            if t > T0['Verse 1'] - 0.4:
                # the first verse line is already being cut while the camera arrives
                G, E, K, st2 = close_frame(t, 'Verse 1')
                st.update(st2)
        if sec == 'Bridge':
            st['light'] = lerp(AMBER, WHITE, 0.25)
            st['key'] = 1.2 + 0.6 * math.sin(t * 2.2)
        if sec == 'Outro':
            ps = sec_perfs('Outro')
            last = ps[-1]
            us = [u for u in last['u'] if u]
            if t >= us[0][0] - 0.05:
                half = us[len(us) // 2][0]
                if t < half - 0.05:
                    k = sat((t - us[0][0]) / 0.3)
                    st['gap'] = lerp(st['gap'], 0.02, k)
                    st['sill'] = lerp(st['sill'], 0.30, k)
                else:
                    k = sat((t - half) / 0.5)
                    st['gap'] = 0.02 + 0.9 * k
                    st['sill'] = 0.30 + 1.3 * k
            st['exposure'] = 1.0 * sat((DUR - 0.1 - t) / 1.3) ** 1.2 if t > DUR - 1.5 else 1.0
    hit = st.get('hit', 0.0)
    close_lin = D.compose_close(G, E, K, t, st)
    if z >= 0.999:
        lin = close_lin
    else:
        fst = dict(st)
        fst['amb_far'] = 0.20 if sec != 'Intro' else st['amb'] * 0.8
        text = floor_text(t, sec) if sec in FAR_SECS else None
        if sec == 'Intro' and text is not None:
            text = text * (1 - sat((t - (T0['Verse 1'] - 3.4)) / 1.2))
        far = compose_far(close_lin, t, fst, text)
        if sec == 'Intro':
            title_card(far, t)
        if sec == 'Outro':
            end_card(far, t)
        if z <= 0.001:
            lin = far
        else:
            A, B, c = zoom_mats(z)
            lin = cv2.warpAffine(far, A, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            if c > 0.42:
                k = sat((c - 0.42) / 0.25)
                near = cv2.warpAffine(close_lin, B, (W, H), flags=cv2.INTER_AREA if c < 0.8 else cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_CONSTANT, borderValue=0)
                m = cv2.warpAffine(np.ones((H, W), np.float32), B, (W, H), flags=cv2.INTER_LINEAR)
                m = cv2.erode(m, np.ones((9, 9), np.uint8))
                m = cv2.GaussianBlur(m, (0, 0), 6)[..., None] * k
                lin = lin * (1 - m) + near * m
    # camera: breathes with the kick, flinches on the snare, jumps on a knock
    bar, beat = beat_pos(t)
    slow = 1.0 + 0.012 * math.sin(t * 0.37) + 0.004 * math.sin(t * 1.3)
    drums = 1.0 if t > 24.05 else 0.0
    push = 0.0
    if sec in ('Verse 1', 'Verse 2', 'Verse 3', 'Hook', 'Final Hook', 'Build'):
        cur = [p for p in sec_perfs(sec) if p['t0'] - LEAD <= t]
        if cur:
            p = cur[-1]
            k = sat((t - p['t0']) / max(0.5, p['out'] - p['t0']))
            push = 0.030 * k if p['n'] % 2 == 0 else 0.030 * (1 - k)
    st.setdefault('zoom', slow + push + 0.010 * kk * drums + 0.030 * hit)
    jx = 2.5 * math.sin(t * 1.9) + 1.5 * math.sin(t * 3.1 + 1)
    jy = 3.0 * math.sin(t * 1.3 + 2) + 5.0 * kk * drums
    if hit > 0.02:
        r = _rnd(int(t * FPS) + 7, 2)
        jx += 26 * hit * (r[0] - 0.5)
        jy += 30 * hit * (r[1] - 0.5)
    st.setdefault('shake', (jx, jy))
    st.setdefault('roll', 0.25 * math.sin(t * 0.5) + 0.35 * sn * drums * (1 if int(beat) % 2 else -1))
    st['aberr'] = 5.0 * hit + (2.0 * kk if sec == 'Drop' else 0.0)
    if sec == 'Verse 3' and t < T0['Verse 3'] + 0.5:
        st['flash'] = max(st.get('flash', 0.0), 0.30 * math.exp(-(t - (T0['Verse 3'] - 0.12)) / 0.08))
        st['flash_c'] = GOLD
    if sec == 'Verse 1' and 24.05 <= t < 24.6:
        st['flash'] = max(st.get('flash', 0.0), 0.16 * math.exp(-(t - 24.08) / 0.07))
        st['flash_c'] = GOLD
    return D.finish(lin, t, st)


# ---------------------------------------------------------------------------------------------------------
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
    ap.add_argument('--cols', type=int, default=6)
    a = ap.parse_args()
    if a.preview:
        os.makedirs('work/preview', exist_ok=True)
        paths = []
        for s in a.preview.split(','):
            t = float(s)
            img = render(t)
            pth = f'work/preview/p_{t:07.2f}.png'
            cv2.imwrite(pth, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            paths.append(pth)
        ims = [cv2.resize(cv2.imread(q), (270, 480), interpolation=cv2.INTER_AREA) for q in paths]
        for im, q in zip(ims, paths):
            cv2.putText(im, os.path.basename(q)[2:-4], (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        cols = min(a.cols, len(ims))
        rws = int(math.ceil(len(ims) / cols))
        sheet = np.zeros((rws * 480, cols * 270, 3), np.uint8)
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
