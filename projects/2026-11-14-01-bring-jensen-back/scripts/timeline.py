"""The score: every shot, every lyric line's look, every prop, keyed to measured times.

Times come from two places only: the beat grid B(bar, beat) (96.00 BPM, first downbeat 0.090 s) for cuts,
and lyric_timing.json (aligned per unit) via st(id, k) / first(id) / last(id) for anything tied to a word.

Sections (bars from the measured drum grid, see storyboard.md):
  intro 1-12   diner 1993, no drums; sung title lights a neon sign; glitch; scratch rewind; call & response
  verse1 13-28 keynote stage, LED wall shows one number/thing per line - the legend
  pre 27-29    the fall: the stage drops, keynote -> headlines; bar 29 the drums cut out: 33 YEARS / ONE WEEK?
  hook1 30-36  rally: chant stamps, crowd, the MC in halftone
  verse2 37-53 newsprint: dated clippings, red candles, stamps; the jacket leaves the stage
  build 54-57  counters, petition, candles at the green panel; READY? 3 2 1 (strobe follows the snare)
  drop 58-64   pop-art grid of the MC, one chant word per screen
  verse3 65-80 the case board: rumours vs facts, redactions, cut strings, PENDING
  bridge 81-89 handwritten letters (family, colleagues, board, us) and their props
  hook2 90-97  rally again, bigger: the crew of three, the green light, the final chant
  outro 98-110 the diner again: cold coffee, flowers, green light still on; the neon relights on the last line
"""
import bisect
import json
import math

import cv2
import numpy as np

import fxlib as F
import scenes as SC
import typo as TY
from common import (AMBER, B, BAR, BEAT, CREAM, DUR, FPS, GREEN, GREEN_D, H, INK, NFRAMES, PAPER, RED, T0, W, WHITE,
                    clamp01, ease_out)

TIM = {e['id']: e for e in json.load(open('work/audio/lyric_timing.json'))}


def st(i, k=0):
    return TIM[i]['units'][k]['s']


def first(i):
    return TIM[i]['units'][0]['s']


def last(i):
    return TIM[i]['units'][-1]['e']


GIRL_STAND = dict(x=560, y=1330, s=2.05)   # body centre, full height to the frame bottom


class Shot:
    def __init__(self, name, t0, scene, p=None, girl=None, back=(), front=(), over=(), fx=None, cam=None, replay=None):
        self.name, self.t0, self.scene = name, t0, scene
        self.p = p or {}
        self.girls = girl if isinstance(girl, list) else ([girl] if girl else [])
        self.back, self.front, self.over_ = list(back), list(front), list(over)
        self.fx = fx or {}
        self.cam = cam
        self.replay = replay   # content time -> picture of whatever shot was there (rewinds)
        self.t1 = None

    def background(self, tc, fi, env):
        if self.replay:
            src = shot_at(tc)
            if src is not self:
                img = src.background(tc, fi, env)
                return src.layers(img, tc, tc, fi, env)
        return SC.SCENES[self.scene](tc, self.p, fi)

    def layers(self, img, tc, t, fi, env):
        if self.replay and shot_at(tc) is not self:
            return img
        for d in self.back:
            img = d(img, tc, t, fi, env)
        for g in self.girls:
            gg = dict(g)
            gg.setdefault('t0', self.t0)
            img = F.girl_layer(img, gg, tc, t, fi, env)
        for d in self.front:
            img = d(img, tc, t, fi, env)
        if self.cam:
            z0, z1, cx, cy = self.cam
            u = clamp01((t - self.t0) / max(0.1, (self.t1 or self.t0 + 4) - self.t0))
            z = z0 + (z1 - z0) * (u * u * (3 - 2 * u))
            if abs(z - 1) > 1e-3:
                M = np.array([[z, 0, (1 - z) * cx], [0, z, (1 - z) * cy]], np.float32)
                img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        return img

    def overlay(self, img, tc, t, fi, env):
        for d in self.over_:
            img = d(img, tc, t, fi, env)
        return img


SHOTS = []
LINES = []
REWINDS = []   # (t_start, t_end, speed): content time runs backwards from t_start at `speed`


def shot(*a, **k):
    s = Shot(*a, **k)
    SHOTS.append(s)
    return s


def line(i, **k):
    ln = TY.Line(TIM[i], **k)
    ln.id = i
    LINES.append(ln)
    return ln


def L_(i):
    """Late lookup of a Line object by entry id (for drawables built before the line)."""
    return lambda: next(x for x in LINES if x.id == i)


# ======================================================================================== styles
TOP = (60, 150, 1020, 760)
TOP_HI = (60, 120, 1020, 640)
BOTTOM = (60, 1290, 1020, 1840)


def v1style(**k):
    d = dict(fontset='heavy', box=TOP, colors=(WHITE, GREEN), stroke=0, shadow=(10, 10), shadow_color=(0, 0, 0),
             max_size=210, enter='stamp')
    d.update(k)
    return d


# ======================================================================================== INTRO
def neon_intro(t):
    if t < first('i2') - 0.06:
        return sum(clamp01((t - st('i1', k) + 0.04) / 0.08) for k in range(3))
    if t < st('i2', 0) - 0.02:
        return 0.15   # flicker off before relighting
    return sum(clamp01((t - st('i2', k) + 0.04) / 0.08) for k in range(3))


def green_i4(t):
    ton = st('i4', 5)   # "green"
    if t < ton:
        return 0.0
    u = t - ton
    if u < 0.4:
        return 1.0 if int(u * 26) % 3 else 0.15
    return 1.0


def build_intro():
    shot('i_title', 0.0, 'diner', p=dict(green=0.0, neon=neon_intro, mugs=3, steam=1.0), cam=(1.0, 1.07, 540, 560),
         fx=dict(grain=0.07, flashes=[]), over=[F.fade(0.0, 2.2, INK, to=0.0, frm=1.0)])
    t3 = first('i3') - 0.15
    shot('i_1993', t3, 'diner', p=dict(green=0.0, neon=0.0, mugs=3, steam=1.0), cam=(1.32, 1.42, 540, 1150),
         back=[], fx=dict(grain=0.07))
    line('i3', fontset='mono', box=(70, 1500, 1010, 1860), colors=(CREAM,), stroke=8, stroke_color=INK, max_size=120,
         enter='type', align='left')
    SHOTS[-1].over_.append(F.big('1993', 'Anton', 420, 540, 520, AMBER, t0=st('i3', 0), t1=first('i4') - 0.1,
                                 enter='stamp', shadow=(12, 12), shadow_color=INK))
    t4 = first('i4') - 0.1
    shot('i_33later', t4, 'diner', p=dict(green=green_i4, neon=0.0, mugs=3, steam=1.0), cam=(1.0, 1.05, 700, 500),
         fx=dict(grain=0.06))
    line('i4', fontset='heavy', box=(60, 1380, 1020, 1850), colors=(CREAM, GREEN), shadow=(8, 8), max_size=170)
    SHOTS[-1].over_.append(F.counter(st('i4', 0), st('i4', 2) + 0.3, 1993, 2026, fmt='{:.0f}', size=300, cx=540, cy=1030,
                                     color=AMBER, hold=st('i4', 3) - st('i4', 2)))
    t5 = first('i5') - 0.06
    shot('i_glitch', t5, 'diner', p=dict(green=1.0, neon=0.0, mugs=3, steam=1.0),
         back=[F.rect(0, 1160, W, 1560, RED, t0=t5, use_t=True, wipe=0.12)],
         over=[], fx=dict(grain=0.05, flash_in=0.8))
    SHOTS[-1].front.append(F.glitch(t5, st('i6', 0) - 0.05, 1.0))
    SHOTS[-1].front.append(F.tv_static(t5, st('i6', 0), 0.18))
    line('i5', fontset='mono', box=(70, 1190, 1010, 1530), colors=(WHITE,), max_size=110, enter='type', align='left',
         upper=True)
    # Hold up - run it back: the record is dragged back; the picture rewinds through the glitch to the diner
    t6 = st('i6', 0) - 0.04
    t7 = first('i7') - 0.06
    shot('i_rewind', t6, 'diner', replay=True, over=[F.vhs(t6, t7)], fx=dict(grain=0.05, flash_in=0.5))
    REWINDS.append((t6, t7, 2.6))
    line('i6', fontset='heavy', box=(60, 560, 1020, 1300), colors=(WHITE, GREEN), stroke=10, stroke_color=INK,
         shadow=(12, 12), max_size=300, enter='slam', valign='center', rows=[[0, 1], [2, 3, 4]])
    # I say "Bring him", you say "Back": first appearance of the MC
    shot('i_mc', t7, 'stage', p=dict(keys=[], beams=2), fx=dict(grain=0.04, flash_in=0.9),
         girl=dict(x=600, y=1380, s=2.0, style='color', kw=dict(border=10, shadow=(20, 16), shadow_color=GREEN),
                   enter='up', nod=0.6))
    line('i7', **v1style(box=(60, 130, 1020, 760), max_size=230, rows=[[0, 1], [2, 3], [4, 5, 6]],
                         t_end=st('i8', 0) - 0.05))
    # Bring him! (Back!) x2 : call (black, close-up) / response (green, halftone, giant BACK!)
    calls = [st('i8', 0), st('i8', 3)]
    resps = [st('i8', 2), st('i8', 5)]
    nxt = first('v1a') - 0.04
    seq = sorted([(c, 'call') for c in calls] + [(r, 'resp') for r in resps])
    for j, (ta, kind) in enumerate(seq):
        tb = seq[j + 1][0] if j + 1 < len(seq) else nxt
        if kind == 'call':
            shot(f'i_call{j}', ta - 0.04, 'void', p=dict(bg=INK),
                 girl=dict(x=540, y=980, s=4.6, anchor='face', style='color', nod=0.5),
                 over=[F.big('BRING HIM!', 'Anton', 0, 540, 1620, WHITE, t0=ta - 0.04, t1=tb - 0.04, width=960,
                             enter='slam', shadow=(10, 10), shadow_color=GREEN)], fx=dict(flash_in=0.4, punch=0.03))
        else:
            shot(f'i_resp{j}', ta - 0.04, 'rally', p=dict(bg=GREEN, burst_alpha=0.3),
                 girl=dict(x=540, y=1350, s=2.1, style='duo', kw=dict(ink=INK, paper=GREEN, cell=10), nod=1.0),
                 over=[F.big('BACK!', 'Anton', 0, 540, 560, INK, t0=ta - 0.04, t1=tb - 0.04, width=1000, enter='slam',
                             shadow=(14, 14), shadow_color=WHITE)], fx=dict(flash_in=0.6, punch=0.04))


# ======================================================================================== VERSE 1
V1_KEYS = {  # line id -> what the LED wall shows (a word/number or a prop silhouette)
    'v1a': ('boat', 'prop'), 'v1b': ('FUTURE', 'text'), 'v1c': ('$40K', 'text'), 'v1d': ('30\nDAYS', 'text'),
    'v1e': ('1999', 'text'), 'v1f': ('2006', 'text'), 'v1g': ('AI', 'text'), 'v1h': ('chip', 'prop'),
    'v1i': ('jacket', 'prop'), 'v1j': ('MORE', 'text'), 'v1k': ('FLASH', 'text'), 'v1l': ('60:1', 'text'),
    'v1m': ('33', 'text'), 'v1n': ('TOP', 'text'),
}


def build_verse1():
    keys = [(first(i) - 0.05, k, kind) for i, (k, kind) in V1_KEYS.items()]
    sp = dict(keys=keys, beams=2)
    t0 = min(B(13), first('v1a') - 0.05)
    fx = dict(punch=0.022, shake=4, grain=0.04)
    frames = [  # (start, girl, text box)
        (t0, dict(x=700, y=1380, s=1.95, style='color', kw=dict(border=10, shadow=(18, 14), shadow_color=GREEN)), TOP),
        (B(15), dict(x=540, y=1000, s=5.2, anchor='face', style='color', nod=0.5), BOTTOM),
        (B(17), dict(x=540, y=1500, s=1.55, style='color', kw=dict(border=8, shadow=(14, 12), shadow_color=GREEN)), TOP),
        (B(19), dict(x=560, y=1330, s=2.1, style='line', kw=dict(paper=GREEN)), TOP),
        (B(21), dict(x=380, y=1380, s=2.05, style='color', kw=dict(border=10, shadow=(-18, 14), shadow_color=GREEN)), TOP),
        (B(23), dict(x=540, y=860, s=7.0, anchor='face', style='color', nod=0.4), BOTTOM),
        (B(25), dict(x=560, y=1380, s=2.0, style='duo', kw=dict(ink=(0.02, 0.05, 0.02), paper=GREEN, cell=9)), TOP),
    ]
    for j, (ta, g, box) in enumerate(frames):
        shot(f'v1_{j}', ta, 'stage', p=sp, girl=g, fx=dict(fx, flash_in=0.35 if j else 0.9))
    ids = ['v1a', 'v1b', 'v1c', 'v1d', 'v1e', 'v1f', 'v1g', 'v1h', 'v1i', 'v1j', 'v1k', 'v1l', 'v1m', 'v1n']
    bounds = [f[0] for f in frames] + [1e9]
    for i in ids:
        tf = first(i)
        tm = (tf + last(i)) / 2
        k = max(0, bisect.bisect_right(bounds, tm) - 1)   # which framing is on screen for most of the line
        box = frames[min(k, len(frames) - 1)][2]
        line(i, **v1style(box=box))


# ======================================================================================== PRE-CHORUS
def build_pre():
    fall = st('p1a', 6)   # the first character of the second phrase: the fall
    shot('pre_peak', first('p1a') - 0.05, 'stage', p=dict(keys=[(first('p1a') - 0.05, 'PEAK', 'text'),
                                                              (fall, 'DROP', 'text')], led=GREEN, beams=3),
         girl=dict(x=560, y=1360, s=2.0, style='color', kw=dict(border=10, shadow=(18, 14), shadow_color=GREEN),
                   fall_at=fall), fx=dict(punch=0.03, shake=6, flash_in=0.3))
    line('p1a', **v1style(exit='fall'))
    hl = st('p1b', 5)   # "headlines"
    shot('pre_keynote', first('p1b') - 0.05, 'stage', p=dict(keys=[(first('p1b') - 0.05, 'KEYNOTE', 'text')], beams=2),
         fx=dict(punch=0.03))
    shot('pre_headlines', hl - 0.03, 'paper', p=dict(rule_red=True, seed=3),
         girl=dict(x=560, y=1390, s=1.95, style='duo', kw=dict(ink=INK, paper=PAPER, cell=8), nod=0.8),
         fx=dict(flash_in=0.5, punch=0.03, grain=0.035))
    line('p1b', **v1style(colors=(WHITE, GREEN), stroke=9, stroke_color=INK, shadow=(10, 10), shadow_color=RED,
                          exit='fall', t_end=B(29)))
    # bar 29: the drums cut out. Everything stops: 33 YEARS / ONE WEEK?
    t29 = B(29)
    shot('pre_void', t29, 'void', p=dict(bg=(0.01, 0.01, 0.01)), fx=dict(grain=0.0, vignette=False, lift=0.0))
    SHOTS[-1].over_ += [
        F.big('33 YEARS', 'Anton', 0, 540, 700, GREEN, t0=st('p1c', 0) - 0.04, t1=st('p1c', 2) - 0.03, width=940,
              enter='stamp'),
        F.big('33 YEARS', 'Anton', 0, 540, 520, GREEN_D, t0=st('p1c', 2) - 0.03, t1=B(30) - 0.6, width=600, enter=None,
              alpha=0.6),
        F.big('ONE WEEK?', 'Anton', 0, 540, 980, RED, t0=st('p1c', 2) - 0.04, t1=B(30) - 0.6, width=980, enter='slam'),
    ]


# ======================================================================================== HOOKS
def hook_line(i, bg, ink, adlib_col, rows=None, box=(50, 130, 1030, 820), **k):
    d = dict(fontset='heavy', box=box, colors=(ink, ink), stroke=0, max_size=330, enter='slam',
             adlib_box=[(620, 880)], adlib_color=adlib_col, adlib_size=170, rows=rows)
    d.update(k)
    return line(i, **d)


def hook_pair(i, chant_cols, adlib_col, shadow_color, ans_box=(80, 1110, 1000, 1390), band=WHITE, ans_ink=INK,
              chant_box=(40, 120, 1040, 690), adlib_xy=(30, 700)):
    """Hook line = the chant (BRING JENSEN / BACK!) up top + the Chinese answer on a paper sticker over the MC."""
    us = TY.lyrics.units(TIM[i]['line'])
    chant = [k for k, u in enumerate(us) if not u['cjk'] and not u['adlib']]
    adl = [k for k, u in enumerate(us) if u['adlib']]
    ans = [k for k, u in enumerate(us) if u['cjk'] and not u['adlib']]
    line(i, fontset='heavy', box=chant_box, colors=chant_cols, max_size=420, enter='slam', rows=[[0, 1], [2]],
         skip=ans, adlib_box=[adlib_xy], adlib_color=adlib_col, adlib_size=170, shadow=(12, 12),
         shadow_color=shadow_color, gap=0.02)
    ln = line(i, fontset='heavy', box=ans_box, colors=(ans_ink,), max_size=170, enter='stamp', skip=chant + adl,
              valign='center', min_len=3, max_len=7.5)
    ln.id = i + '#ans'
    SHOTS[-1].front.append(F.band_for(L_(i + '#ans'), color=band))


def build_hook(tag, ids, bar0, big=False):
    """One hook: bars bar0.. ; lines h?a-h?d chant + answer, then h?e/h?f/h?g (and h?h on the final)."""
    looks = [(GREEN, INK, RED), (INK, GREEN, WHITE), (GREEN, INK, RED), (INK, GREEN, WHITE)]
    crowd_rows = 4 if big else 3
    for j, i in enumerate(ids[:4]):
        bg, ink, ad = looks[j]
        ta = B(bar0 + j * 1) if j == 0 else first(i) - 0.05
        burst = GREEN_D if bg is GREEN else (0.06, 0.12, 0.04)
        gl = []
        # always a positive print (ink dots on green) so her face reads, on green and on black alike
        if big:   # the crew: three of her
            gl = [dict(x=290, y=1500, s=1.55, style='duo', kw=dict(ink=INK, paper=GREEN, cell=8), nod=1.0, flip=True),
                  dict(x=790, y=1500, s=1.55, style='duo', kw=dict(ink=INK, paper=GREEN, cell=8), nod=1.0),
                  dict(x=540, y=1470, s=1.95, style='duo', kw=dict(ink=INK, paper=GREEN, cell=9), nod=1.0)]
        else:
            gl = [dict(x=540, y=1480, s=2.15, style='duo', kw=dict(ink=INK, paper=GREEN, cell=9), nod=1.0)]
        back = []
        if j == 0:
            back.append(F.prop('jacket', 330, 860, 560, t0=st(i, 4) - 0.05, swing=6, enter='drop', use_t=True))
        if j == 1:
            back.append(F.prop('folder', 360, 230, 600, t0=st(i, 4) - 0.05, rot=8, enter='slam', use_t=True))
        if j == 3:
            back.append(F.big('33', 'Anton', 900, 540, 720, bg * 0.75 + ink * 0.25, t0=st(i, 4) - 0.05, enter='stamp'))
        front = [lambda img, tc, t, fi, env, ink=ink, bg=bg: SC.crowd(img, tc, float(env['kick'][fi]), color=ink,
                                                                      rows=crowd_rows, sign_color=bg if bg is not INK else PAPER,
                                                                      sign_ink=INK if bg is not INK else INK)]
        shot(f'{tag}_{j}', ta, 'rally', p=dict(bg=bg, burst_color=burst, burst_alpha=0.35), girl=gl, back=back, front=front,
             fx=dict(punch=0.035, shake=7, flash_in=0.5 if j == 0 else 0.25, grain=0.035, split=3 if big else 0))
        hook_pair(i, (INK, INK) if bg is GREEN else (GREEN, WHITE), RED if bg is GREEN else WHITE,
                  WHITE if bg is GREEN else RED, band=WHITE if bg is GREEN else GREEN,
                  adlib_xy=(20, 640) if big else (30, 700))
    # stock fell, the people didn't leave
    e, f, g = ids[4], ids[5], ids[6]
    shot(f'{tag}_stock', first(e) - 0.05, 'void', p=dict(bg=(0.06, 0.01, 0.01), burst=True, burst_color=(0.12, 0.02, 0.02)),
         back=[F.candles_chart(first(e), st(e, 3) + 0.2, ytop=300, ybot=1100, n=12)],
         girl=dict(x=540, y=1450, s=2.05, style='duo', kw=dict(ink=INK, paper=RED, cell=9), nod=1.0),
         front=[lambda img, tc, t, fi, env: SC.crowd(img, tc, float(env['kick'][fi]), color=INK, rows=crowd_rows,
                                                    sign_color=PAPER)],
         fx=dict(punch=0.035, shake=7, flash_in=0.3, split=4))
    hook_line(e, RED, WHITE, GREEN, colors=(WHITE, WHITE), shadow=(10, 10), shadow_color=INK,
              adlib_box=[(40, 760)], box=(60, 130, 1020, 660), max_size=260, adlib_size=170)
    shot(f'{tag}_green', first(f) - 0.05, 'void', p=dict(bg=(0.0, 0.02, 0.0)),
         back=[F.green_light(540, 640, 190, t0=first(f) - 0.05, use_t=True, flicker_on=0.25)],
         girl=dict(x=540, y=1380, s=2.05, style='color', kw=dict(border=10, shadow=(16, 14), shadow_color=GREEN), nod=1.0),
         front=[lambda img, tc, t, fi, env: SC.crowd(img, tc, float(env['kick'][fi]), color=INK, rows=crowd_rows,
                                                    sign_color=GREEN)],
         fx=dict(punch=0.035, shake=6, flash_in=0.3))
    hook_line(f, INK, GREEN, WHITE, colors=(INK, INK), shadow=None, adlib_box=[(640, 1420)], adlib_color=GREEN,
              box=(80, 1110, 1000, 1380), max_size=170, valign='center', adlib_size=150, min_len=3, max_len=7.5)
    SHOTS[-1].front.append(F.band_for(L_(f), color=GREEN))
    shot(f'{tag}_facts', first(g) - 0.05, 'paper', p=dict(seed=7, rule_red=True),
         girl=dict(x=560, y=1490, s=1.95, style='mono', kw=dict(ink=INK, paper=PAPER, border=8, shadow=(14, 12),
                                                                shadow_color=RED), nod=1.0),
         back=[F.prop('folder', 520, 760, 1200, t0=st(g, 10) - 0.04, rot=-6, enter='slam', use_t=True)],
         fx=dict(punch=0.03, shake=5, flash_in=0.3, grain=0.03))
    ln = hook_line(g, PAPER, INK, RED, colors=(INK, INK, RED), shadow=None, box=(60, 140, 1020, 900), max_size=260,
                   fontset='heavy')
    SHOTS[-1].over_ += [F.cross_out(L_(g), {2, 3}, last_unit(g, 3)), F.cross_out(L_(g), {6, 7}, last_unit(g, 7))]
    if len(ids) > 7:
        h = ids[7]
        shot(f'{tag}_final', first(h) - 0.05, 'rally', p=dict(bg=INK, burst_color=(0.1, 0.18, 0.06), burst_alpha=0.6),
             girl=[dict(x=290, y=1500, s=1.55, style='duo', kw=dict(ink=INK, paper=GREEN, cell=8), nod=1.0, flip=True),
                   dict(x=790, y=1500, s=1.55, style='duo', kw=dict(ink=INK, paper=GREEN, cell=8), nod=1.0),
                   dict(x=540, y=1470, s=1.95, style='color', kw=dict(border=10, shadow=(16, 14), shadow_color=GREEN), nod=1.0)],
             front=[lambda img, tc, t, fi, env: SC.crowd(img, tc, float(env['kick'][fi]), color=(0.02, 0.02, 0.02), rows=4,
                                                        sign_color=GREEN)],
             fx=dict(punch=0.04, shake=8, flash_in=0.6, split=3))
        hook_line(h, INK, GREEN, WHITE, colors=(GREEN, WHITE, GREEN), shadow=(10, 10), shadow_color=INK, max_size=300,
                  box=(50, 110, 1030, 760))


def last_unit(i, k):
    return TIM[i]['units'][k]['e']


# ======================================================================================== VERSE 2
def headline(i, box=(60, 150, 1020, 780), colors=(INK, INK), **k):
    d = dict(fontset='serif', box=box, colors=colors, max_size=190, enter='stamp', shadow=None, upper=True)
    d.update(k)
    return line(i, **d)


def build_verse2():
    ids = ['v2a', 'v2b', 'v2c', 'v2d', 'v2e', 'v2f', 'v2g', 'v2h', 'v2i', 'v2j', 'v2k', 'v2l', 'v2m', 'v2n', 'v2o', 'v2p']
    photo_r = dict(x=700, y=1430, s=1.75, style='duo', kw=dict(ink=INK, paper=PAPER, cell=8, border=10, border_color=INK), nod=1.0)
    photo_l = dict(x=380, y=1430, s=1.75, style='duo', kw=dict(ink=INK, paper=PAPER, cell=8, border=10, border_color=INK), nod=1.0,
                   flip=True)
    red_mono = dict(x=560, y=1400, s=1.95, style='mono', kw=dict(ink=INK, paper=PAPER, border=10, shadow=(16, 14),
                                                                 shadow_color=RED), nod=1.0)
    fx = dict(punch=0.03, shake=5, split=2, grain=0.035)
    t37 = min(B(37), first('v2a') - 0.05)
    shot('v2_0', t37, 'paper', p=dict(seed=1, rule_red=True, rule_y=110), girl=photo_r, fx=dict(fx, flash_in=0.7),
         back=[F.rubber_stamp('10.29', 250, 1180, st('v2a', 0), size=150, rot=-10)],
         over=[F.big('BANG', 'Anton', 0, 540, 1000, RED, t0=st('v2a', 13), t1=st('v2a', 13) + 0.4, width=700,
                     enter='slam')])
    headline('v2a')
    headline('v2b', colors=(INK, RED))
    shot('v2_1', B(41) if B(41) < first('v2d') else first('v2d') - 0.05, 'paper', p=dict(seed=2, tone=1), girl=photo_l, fx=fx,
         back=[F.prop('envelope', 260, 760 + 90 * k, 1050 + 40 * k, t0=st('v2d', 9) + 0.08 * k, rot=-8 + 8 * k,
                      enter='slam', use_t=True) for k in range(3)])
    headline('v2c', colors=(INK, RED))
    headline('v2d')
    shot('v2_2', first('v2e') - 0.05, 'paper', p=dict(seed=3, rule_red=True), girl=photo_r, fx=fx,
         back=[F.rubber_stamp('11.08', 260, 1180, st('v2e', 0), size=150, rot=-8),
               F.prop('envelope', 300, 300, 1450, t0=st('v2e', 5), rot=6, enter='slam', use_t=True)])
    headline('v2e')
    headline('v2f', colors=(INK, RED))
    face_ht = dict(x=540, y=1260, s=4.3, anchor='face', style='duo', kw=dict(ink=INK, paper=PAPER, cell=10), nod=0.6)
    shot('v2_3', first('v2g') - 0.05, 'paper', p=dict(seed=4, tone=1), girl=face_ht, fx=fx)
    headline('v2g')
    shot('v2_4', first('v2h') - 0.05, 'paper', p=dict(seed=5, greek_alpha=0.12), girl=dict(red_mono, x=560, y=1460, s=1.7),
         back=[F.rubber_stamp('11.09', 770, 1080, st('v2h', 0), size=120, rot=8),
               F.candles_chart(st('v2h', 7), st('v2h', 11), ytop=820, ybot=1500, n=12, x0=60, x1=1020)],
         fx=dict(fx, flash_in=0.3))
    headline('v2h', colors=(INK, RED, INK), adlib_box=[(120, 1550), (560, 1680)], adlib_color=RED, adlib_size=120)
    shot('v2_5', first('v2i') - 0.05, 'paper', p=dict(seed=6), girl=photo_r, fx=fx,
         back=[F.big('?', 'Anton', 1000, 260, 1250, RED, t0=st('v2i', 0), enter='stamp', alpha=0.9)])
    headline('v2i')
    headline('v2j', colors=(INK, RED))
    SHOTS[-1].back.append(F.big('?', 'Anton', 1300, 260, 1250, RED, t0=st('v2j', 4), enter='slam'))
    shot('v2_6', first('v2k') - 0.05, 'paper', p=dict(seed=7, tone=1), girl=photo_l, fx=dict(fx, shake=8),
         back=[F.rubber_stamp('爆料', 760 - 160 * (k % 2), 1000 + 230 * k, st('v2k', 7 + 3 * (k % 2)) + 0.15 * k, size=110,
                              rot=(-14 + 9 * k), fontname='NotoSansSC-Black') for k in range(3)])
    headline('v2k', colors=(INK, RED))
    shot('v2_7', first('v2l') - 0.05, 'void', p=dict(bg=(0.10, 0.0, 0.0)), girl=dict(red_mono, kw=dict(ink=INK, paper=RED, border=0)),
         back=[F.fire(st('v2l', 6), first('v2m'))],
         over=[F.big('-11%', 'Anton', 0, 540, 1420, WHITE, t0=st('v2l', 2), width=900, enter='slam', shadow=(16, 16),
                     shadow_color=INK)],
         fx=dict(fx, flash_in=0.5, split=5))
    headline('v2l', colors=(WHITE, RED), shadow=(8, 8), shadow_color=INK, fontset='heavy')
    shot('v2_8', first('v2m') - 0.05, 'paper', p=dict(seed=8, rule_red=True), girl=photo_r, fx=fx,
         back=[F.rubber_stamp('11.12', 260, 1150, st('v2m', 0), size=150, rot=-6),
               F.rect(140, 1320, 520, 1700, (0.97, 0.96, 0.92), t0=st('v2m', 6), use_t=True),
               F.rect(170, 1360, 490, 1376, INK, t0=st('v2m', 6), use_t=True),
               F.rect(170, 1420, 430, 1436, INK, t0=st('v2m', 6), use_t=True),
               F.rect(170, 1480, 460, 1496, INK, t0=st('v2m', 6), use_t=True)])
    headline('v2m')
    shot('v2_9', first('v2n') - 0.05, 'paper', p=dict(seed=9), girl=dict(red_mono, x=600),
         fx=dict(fx, flash_in=0.3),
         over=[F.rubber_stamp('EFFECTIVE IMMEDIATELY', 540, 1080, st('v2n', 6), size=82, rot=-9)])
    headline('v2n', colors=(INK, RED))
    shot('v2_10', first('v2o') - 0.05, 'paper', p=dict(seed=10, tone=1), girl=dict(face_ht, x=560, s=4.0), fx=fx)
    headline('v2o')
    # the jacket walks off the stage; nobody claps
    shot('v2_11', first('v2p') - 0.05, 'stage', p=dict(keys=[], beams=1, led=(0.3, 0.3, 0.3)),
         back=[F.prop('jacket', 420, 540, 1120, t0=first('v2p') - 0.05, t1=st('v2p', 2), exit='left', swing=3, enter=None,
                      use_t=True, exit_speed=0.35)],
         fx=dict(punch=0.02, grain=0.05))
    headline('v2p', colors=(WHITE, (0.7, 0.7, 0.7)), fontset='heavy', shadow=(8, 8), shadow_color=INK)


# ======================================================================================== BUILD
def build_build():
    fx = dict(punch=0.03, shake=4, grain=0.04)
    shot('b_1600', first('b1') - 0.05, 'void', p=dict(bg=INK, burst=True, burst_color=(0.05, 0.09, 0.04), burst_alpha=0.8),
         over=[F.counter(st('b1', 2), last('b1'), 0, 1600, size=360, cx=540, cy=1160, color=GREEN, hold=0.6)],
         fx=dict(fx, strobe=0.18))
    line('b1', **v1style(box=(60, 200, 1020, 780)))
    shot('b_names', first('b2') - 0.05, 'void', p=dict(bg=(0.02, 0.03, 0.02)),
         back=[F.scribbles(first('b2') - 0.05, first('b3'), color=CREAM, alpha=0.55)],
         over=[F.counter(st('b2', 2), last('b2'), 0, 30000, fmt='{:,.0f}+', size=250, cx=540, cy=1200, color=GREEN,
                         stroke=10, stroke_color=INK, hold=0.6)],
         girl=dict(x=540, y=1500, s=1.4, style='line', kw=dict(paper=GREEN), nod=1.0),
         fx=dict(fx, strobe=0.28))
    line('b2', **v1style(box=(60, 200, 1020, 760)))
    shot('b_candles', first('b3') - 0.05, 'void', p=dict(bg=(0.01, 0.015, 0.01)),
         back=[F.rect(240, 760, 840, 1240, GREEN * 0.9, t0=first('b3') - 0.05),
               lambda img, tc, t, fi, env: SC.glow(img, 540, 1000, 300, GREEN * 0.6, 0.6),
               F.prop('flowers', 300, 230, 1480, t0=st('b3', 0), enter='pop', use_t=True),
               F.prop('flowers', 300, 850, 1480, t0=st('b3', 1), enter='pop', use_t=True)]
         + [F.prop('candle', 90, 360 + 90 * k, 1520 + (k % 2) * 30, t0=st('b3', 2) + 0.05 * k, enter='pop', use_t=True)
            for k in range(5)]
         + [lambda img, tc, t, fi, env, k=k: SC.glow(img, 360 + 90 * k, 1395 + (k % 2) * 30, 26, AMBER,
                                                     (0.8 + 0.2 * math.sin(t * 13 + k)) * (t > st('b3', 2) + 0.05 * k))
            for k in range(5)],
         fx=dict(fx, strobe=0.35))
    line('b3', **v1style(box=(60, 180, 1020, 680)))
    # READY? 3 2 1
    shot('b_ready', first('b4') - 0.05, 'void', p=dict(bg=INK), fx=dict(fx, strobe=0.6, shake=8))
    ts = [st('b4', k) for k in range(4)]
    SHOTS[-1].over_ += [
        F.big('READY?', 'Anton', 0, 540, 900, WHITE, t0=ts[0] - 0.04, t1=ts[1] - 0.04, width=960, enter='slam'),
        F.big('3', 'Anton', 1300, 540, 1000, GREEN, t0=ts[1] - 0.04, t1=ts[2] - 0.04, enter='slam'),
        F.big('2', 'Anton', 1300, 540, 1000, WHITE, t0=ts[2] - 0.04, t1=ts[3] - 0.04, enter='slam'),
        F.big('1', 'Anton', 1300, 540, 1000, RED, t0=ts[3] - 0.04, t1=first('d1') - 0.04, enter='slam'),
    ]


# ======================================================================================== DROP
POP = [(GREEN, INK, GREEN), (RED, INK, RED), (PAPER, INK, PAPER), (INK, GREEN, INK), (AMBER, INK, AMBER),
       ((0.25, 0.55, 1.0), INK, (0.25, 0.55, 1.0))]


def chant_words(i, idxs, color=WHITE, y=960, shadow=INK, fontname='Anton', width=1000):
    """Each chant word fills the screen from its sung moment until the next word."""
    out = []
    ts = [st(i, k) for k in idxs] + [None]
    us = TY.lyrics.units(TIM[i]['line'])
    if TIM[i].get('slice'):
        us = us[TIM[i]['slice'][0]:TIM[i]['slice'][1]]
    for j, k in enumerate(idxs):
        tb = ts[j + 1] - 0.04 if ts[j + 1] else last(i) + 0.3
        word = us[k]['t'].upper() + ('!' if not us[k]['cjk'] else '')
        out.append(F.big(word, fontname, 0, 540, y, color, t0=ts[j] - 0.04, t1=tb, width=width, enter='slam',
                         shadow=(16, 16), shadow_color=shadow))
    return out


def build_drop():
    fx = dict(punch=0.05, shake=10, split=4, grain=0.03)
    # d1 / d2: BRING! JENSEN! BACK! (Hey! Hey!) 给个说法! / Facts first!
    for tag, i, cols in (('d1', 'd1', POP), ('d2', 'd2', POP[2:] + POP[:2])):
        us = TY.lyrics.units(TIM[i]['line'])
        n_chant = 3
        words = chant_words(i, [0, 1, 2], color=WHITE, shadow=INK)
        for k in range(n_chant):
            ta = st(i, k) - 0.04
            n = (1, 2, 3)[k]
            shot(f'{tag}_{k}', ta, 'void', p=dict(bg=INK), back=[F.grid(n, cols[k:] + cols[:k])],
                 fx=dict(fx, flash_in=0.8 if k == 2 else 0.4), over=list(words))
        # Hey! Hey! + the answer
        ta = st(i, 3) - 0.04
        shot(f'{tag}_hey', ta, 'rally', p=dict(bg=cols[3][0] if cols[3][0] is not INK else GREEN, burst_alpha=0.4,
                                               burst_color=INK if cols[3][0] is not INK else GREEN_D),
             girl=[dict(x=270, y=1380, s=1.5, style='duo', kw=dict(ink=INK, paper=WHITE, cell=8), flip=True, nod=1.0),
                   dict(x=810, y=1380, s=1.5, style='duo', kw=dict(ink=INK, paper=WHITE, cell=8), nod=1.0)],
             fx=dict(fx, flash_in=0.4))
        SHOTS[-1].over_ += [F.big('HEY!', 'Anton', 300, 300 + 480 * j, 330 + 60 * j, INK, t0=st(i, 3 + j) - 0.04,
                                  t1=last(i) + 0.2, enter='slam', rot=(-8 + 16 * j), shadow=(10, 10), shadow_color=WHITE)
                            for j in range(2)]
        line(i, fontset='heavy', box=(50, 620, 1030, 1000), colors=(WHITE,), stroke=12, stroke_color=INK,
             shadow=(14, 14), shadow_color=RED, max_size=330, enter='slam', rows=[list(range(5, len(us)))],
             keep_adlib=True)
    # Stand with x3 Jensen: the crew of three, one per "stand with"
    i = 'd3'
    shot('d3', first(i) - 0.05, 'rally', p=dict(bg=INK, burst_color=(0.1, 0.18, 0.06), burst_alpha=0.6),
         girl=[dict(x=200, y=1420, s=1.3, style='duo', kw=dict(ink=INK, paper=GREEN, cell=7), nod=1.0, enter='pop', t0=st(i, 0)),
               dict(x=540, y=1420, s=1.3, style='duo', kw=dict(ink=INK, paper=PAPER, cell=7), nod=1.0, enter='pop', t0=st(i, 2)),
               dict(x=880, y=1420, s=1.3, style='duo', kw=dict(ink=INK, paper=RED, cell=7), nod=1.0, enter='pop', t0=st(i, 4))],
         fx=dict(fx, flash_in=0.6))
    line(i, fontset='heavy', box=(60, 110, 1020, 980), colors=(GREEN, PAPER, RED, WHITE), max_size=300, enter='slam',
         rows=[[0, 1], [2, 3], [4, 5], [6]], shadow=(10, 10), shadow_color=INK)
    # Thirty-three, thirty-three, 要个答案
    i = 'd4'
    shot('d4', first(i) - 0.05, 'void', p=dict(bg=GREEN, burst=True, burst_color=GREEN_D, burst_alpha=0.5),
         back=[F.grid(2, [POP[0], POP[3], POP[2], POP[1]])], fx=dict(fx, flash_in=0.5))
    SHOTS[-1].over_ += [F.big('33', 'Anton', 600, (330, 750)[j], (520, 900)[j], (WHITE, INK)[j], t0=st(i, j) - 0.04,
                              enter='slam', shadow=(18, 18), shadow_color=(INK, WHITE)[j], rot=(-6, 6)[j]) for j in range(2)]
    line(i, fontset='heavy', box=(60, 1300, 1020, 1800), colors=(WHITE,), rows=[[2, 3, 4, 5]], stroke=14,
         stroke_color=INK, shadow=(14, 14), shadow_color=RED, max_size=330, enter='slam')
    # second half: the supersaw bars are vocal chops (measured onsets, ~8th notes). The picture chops with them;
    # no words are printed because the chops are not words the aligner could place.
    chops = json.load(open('work/audio/chop_onsets.json'))
    ns = [1, 2, 3, 2, 1, 3, 2, 3]
    for k, ta in enumerate(chops):
        cols = POP[k % len(POP):] + POP[:k % len(POP)]
        if k % 4 == 3:
            shot(f'd5_{k}', ta - 0.03, 'rally', p=dict(bg=cols[0][0], burst_color=INK, burst_alpha=0.25),
                 girl=dict(x=540, y=1330, s=2.15, style='line', kw=dict(paper=cols[0][1] if cols[0][0] is INK else INK)),
                 fx=dict(fx, flash_in=0.35, split=6))
        else:
            shot(f'd5_{k}', ta - 0.03, 'void', p=dict(bg=INK), back=[F.grid(ns[k % len(ns)], cols)],
                 fx=dict(fx, flash_in=0.3, split=6))
    i = 'd6'
    shot('d6', st(i, 1) - 0.05, 'rally', p=dict(bg=RED, burst_color=(0.6, 0.05, 0.05), burst_alpha=0.5),
         girl=[dict(x=330, y=1380, s=1.9, style='duo', kw=dict(ink=INK, paper=RED, cell=9), nod=1.0, flip=True),
               dict(x=750, y=1380, s=1.9, style='duo', kw=dict(ink=INK, paper=RED, cell=9), nod=1.0)],
         fx=dict(fx, flash_in=0.6))
    SHOTS[-1].over_ += [F.big('33', 'Anton', 900, 540, 640, WHITE, t0=st(i, 1) - 0.04, enter='slam',
                              shadow=(18, 18), shadow_color=INK, rot=-4)]
    line(i, fontset='heavy', box=(60, 1280, 1020, 1780), colors=(WHITE,), rows=[[1, 2, 3, 4]], stroke=14,
         stroke_color=INK, shadow=(14, 14), shadow_color=GREEN, max_size=330, enter='slam', skip=(0,))


# ======================================================================================== VERSE 3
def evidence(i, box=(60, 130, 1020, 780), colors=(CREAM, GREEN), **k):
    d = dict(fontset='mono', box=box, colors=colors, max_size=180, enter='stamp', shadow=(6, 6), shadow_color=INK,
             max_len=6.5)
    d.update(k)
    return line(i, **d)


def build_verse3():
    fx = dict(punch=0.025, shake=4, grain=0.04)
    pinned = dict(x=720, y=1460, s=1.6, style='mono', kw=dict(ink=INK, paper=CREAM, border=12, border_color=(0.97, 0.96, 0.92)),
                  nod=1.0, rot=3)
    pinned_l = dict(pinned, x=360, rot=-3, flip=True)
    t65 = min(B(65), first('v3a') - 0.05)
    shot('v3_0', t65, 'board', p=dict(), girl=pinned, fx=dict(fx, flash_in=0.7),
         back=[F.phone_feed(250, 1300, 330, first('v3a'), first('v3b') - 0.05)])
    evidence('v3a', colors=(CREAM, RED, CREAM))
    shot('v3_1', first('v3b') - 0.05, 'board', p=dict(), fx=fx,
         back=[lambda img, tc, t, fi, env: cv2.line(img, (300, 760), (300, 1900), (0.7, 0.7, 0.72), 12, cv2.LINE_AA),
               F.prop('jacket', 300, 300, 900, t0=first('v3b') - 0.05, use_t=True, drift=(0, 0), enter=None,
                      swing=2)],
         girl=dict(pinned, x=760))
    # the jacket slides to half-mast along the pole during "降半杆"
    SHOTS[-1].back[-1] = _halfmast(first('v3b') - 0.05, st('v3b', 8), st('v3b', 11) + 0.2)
    evidence('v3b')
    face_mono = dict(x=540, y=1240, s=4.6, anchor='face', style='mono', kw=dict(ink=INK, paper=CREAM, border=0), nod=0.5)
    small_c = dict(pinned, x=540, y=1560, s=1.25, rot=0)
    shot('v3_2', first('v3c') - 0.05, 'board', p=dict(strings=[(220, 1100, 520, 1500)]), girl=dict(pinned, x=800, s=1.35, y=1560), fx=fx,
         back=[F.big('TAIPEI?', 'Anton', 150, 330, 1000, GREEN, t0=st('v3c', 0), enter='stamp', rot=-6)])
    evidence('v3c', colors=(CREAM, GREEN))
    shot('v3_3', first('v3d') - 0.05, 'board', p=dict(), girl=pinned_l, fx=fx,
         back=[F.prop('heart', 260, 790, 980, t0=first('v3d') - 0.05, use_t=True, drift=(0, 120), enter=None, swing=4)])
    evidence('v3d', colors=(CREAM, RED))
    shot('v3_4', first('v3e') - 0.05, 'board', p=dict(), girl=face_mono, fx=fx,
         back=[F.scribbles(first('v3e') - 0.05, first('v3f'), color=CREAM, alpha=0.35, speed=300, seed=8)])
    evidence('v3e')
    shot('v3_5', first('v3f') - 0.05, 'board', p=dict(), girl=pinned_l, fx=fx,
         back=[F.prop('card', 190, 640 + 140 * k, 1080 + 30 * (k % 2), rot=-10 + 10 * k, t0=st('v3f', 8) + 0.08 * k,
                      enter='slam', use_t=True) for k in range(3)])
    evidence('v3f', colors=(CREAM, GREEN))
    shot('v3_6', first('v3g') - 0.05, 'board', p=dict(), girl=dict(small_c, x=760), fx=fx,
         back=[F.big('5 DAYS', 'Anton', 230, 300, 1050, GREEN, t0=st('v3g', 7), enter='stamp', rot=-5)])
    evidence('v3g')
    shot('v3_7', first('v3h') - 0.05, 'board', p=dict(), girl=pinned_l, fx=fx,
         over=[F.big('12 YEARS', 'Anton', 190, 770, 1080, AMBER, t0=st('v3h', 8), enter='stamp', rot=5, shadow=(8, 8),
                     shadow_color=INK)])
    evidence('v3h')
    # her own stance: straight to camera
    shot('v3_8', first('v3i') - 0.05, 'void', p=dict(bg=(0.05, 0.06, 0.08)),
         girl=dict(x=540, y=860, s=6.2, anchor='face', style='color', nod=0.35), fx=dict(fx, flash_in=0.4))
    evidence('v3i', box=(60, 1340, 1020, 1840), colors=(WHITE, GREEN), max_size=160, shadow=(8, 8))
    shot('v3_9', first('v3j') - 0.05, 'board', p=dict(), girl=pinned, fx=fx)
    evidence('v3j', colors=(CREAM, CREAM))
    SHOTS[-1].over_.append(F.redact(L_('v3j'), set(range(7, 13)), last_unit('v3j', 12) - 0.25))
    shot('v3_10', first('v3k') - 0.05, 'board', p=dict(), girl=face_mono, fx=fx,
         back=[F.scribbles(first('v3k') - 0.05, first('v3l'), color=CREAM, alpha=0.3, speed=200, seed=9, rows=14)])
    evidence('v3k', colors=(CREAM, AMBER))
    shot('v3_11', first('v3l') - 0.05, 'board', p=dict(), girl=pinned, fx=fx,
         over=[F.rubber_stamp('COPY', 300, 1120, st('v3l', 9), size=150, rot=-12),
               F.rubber_stamp('2023', 330, 1330, st('v3l', 12), size=110, rot=-7, color=AMBER)])
    evidence('v3l')
    shot('v3_12', first('v3m') - 0.05, 'board', p=dict(), girl=dict(small_c, x=320), fx=fx,
         back=[F.big('<10%', 'Anton', 300, 760, 1080, GREEN, t0=st('v3m', 10), enter='stamp')])
    evidence('v3m', colors=(CREAM, GREEN))
    shot('v3_13', first('v3n') - 0.05, 'board', p=dict(), girl=pinned, fx=fx,
         back=[F.prop('chip', 300, 290, 1180, t0=st('v3n', 8), enter='pop', use_t=True),
               F.prop('lock', 220, 360, 1310, t0=st('v3n', 12), enter='slam', use_t=True)])
    evidence('v3n')
    strings = [(120, 900, 520, 1300), (520, 1300, 900, 950), (900, 950, 300, 1700), (300, 1700, 960, 1750)]
    shot('v3_14', first('v3o') - 0.05, 'board', p=dict(strings=strings), girl=dict(pinned, x=560, y=1520, s=1.45), fx=fx,
         over=[F.big('X', 'Anton', 1200, 540, 1300, RED, t0=st('v3o', 13), enter='slam', alpha=0.9)])
    evidence('v3o', colors=(CREAM, RED))
    shot('v3_15', first('v3p') - 0.05, 'board', p=dict(), girl=pinned, fx=fx,
         over=[F.rubber_stamp('PENDING', 330, 1150, st('v3p', 7), size=120, rot=-9, color=AMBER),
               _cursor(560, 1150, st('v3p', 14) + 0.2, B(81))])
    evidence('v3p')


def _halfmast(t0, ta, tb):
    def f(img, tc, t, fi, env):
        if t < t0:
            return img
        u = clamp01((t - ta) / max(0.01, tb - ta))
        y = 900 + 520 * ease_out(u, 2)
        return SC.put(img, 'jacket', 300, 300, y, rot=2 * math.sin(t * 3))
    return f


def _cursor(x, y, t0, t1):
    def f(img, tc, t, fi, env):
        if t < t0 or t >= t1:
            return img
        if int((t - t0) * 2.4) % 2 == 0:
            img[int(y - 60):int(y + 60), int(x):int(x + 26)] = GREEN
        return img
    return f


# ======================================================================================== BRIDGE
INKB = np.array([0.08, 0.10, 0.18], np.float32)


def letter_line(i, **k):
    d = dict(fontset='hand', box=(150, 140, 1010, 900), colors=(INKB, INKB), max_size=230, enter='write',
             shadow=None, align='left', valign='top', max_len=5.5, min_len=2.0)
    d.update(k)
    return line(i, **d)


def build_bridge():
    fx = dict(punch=0.012, grain=0.035)
    pol = dict(x=540, y=1330, s=1.45, style='color', nod=0.45, sway=0.6)
    t81 = min(B(81), first('r1') - 0.05)
    shot('r_family', t81, 'letter', fx=dict(fx, flash_in=0.3),
         back=[F.polaroid(dict(pol, x=720, y=1500), 720, 1360, 520, 640, rot=-5),
               F.prop('mug', 300, 260, 1250, t0=st('r1', 4), enter='pop', use_t=True)])
    letter_line('r1')
    shot('r_team', first('r2') - 0.05, 'letter', fx=fx,
         back=[F.prop('chair', 300, 540, 1290, t0=first('r2') - 0.05, enter='pop', use_t=True),
               F.dots_ring(540, 1420, 400, 60, st('r2', 3), color=INKB, rad=11, use_t=True)])
    letter_line('r2')
    shot('r_board', first('r3') - 0.05, 'letter', fx=fx,
         back=[F.prop('door', 300, 300, 1330, t0=first('r3') - 0.05, enter='pop', use_t=True),
               F.polaroid(dict(pol, x=760, y=1500), 760, 1360, 480, 600, rot=4)])
    letter_line('r3')
    shot('r_us', first('r4') - 0.05, 'letter', fx=fx,
         back=[F.phone_feed(320, 1330, 320, first('r4'), first('r5')),
               F.polaroid(dict(pol, x=780, y=1500), 780, 1380, 440, 560, rot=-3)])
    letter_line('r4')
    SHOTS[-1].over_.append(F.cross_out(L_('r4'), set(range(3, 9)), last_unit('r4', 8), color=RED, width=10))
    shot('r_flaw', first('r5') - 0.05, 'letter', fx=fx,
         back=[F.polaroid(dict(pol, x=540, y=1520), 540, 1380, 560, 680, rot=2),
               F.prop('halo', 360, 540, 1020, t0=first('r5'), enter='pop', use_t=True)],
         over=[F.big('X', 'Anton', 500, 540, 1020, RED, t0=st('r5', 5), enter='slam', alpha=0.85)])
    letter_line('r5')
    shot('r_law', first('r6') - 0.05, 'letter', fx=fx,
         back=[F.prop('scale', 520, 540, 1320, t0=st('r6', 9), enter='pop', use_t=True)])
    letter_line('r6')
    shot('r_trust', first('r7') - 0.05, 'letter', fx=fx,
         back=[F.prop('gauge', 560, 540, 1300, t0=first('r7'), enter='pop', use_t=True),
               _needle(540, 1300 + 105, first('r7'), st('r7', 9) + 0.6)])
    letter_line('r7')
    # If he's wrong — show the proof / If he's not — run it back, bring him back
    shot('r_wrong', first('r8') - 0.05, 'void', p=dict(bg=(0.12, 0.01, 0.01)),
         girl=dict(x=540, y=1360, s=2.0, style='mono', kw=dict(ink=INK, paper=RED, border=0), nod=0.6),
         fx=dict(punch=0.03, flash_in=0.4))
    line('r8', fontset='heavy', box=(60, 160, 1020, 760), colors=(WHITE, RED), shadow=(10, 10), shadow_color=INK,
         max_size=260, enter='slam')
    shot('r_not', first('r9') - 0.05, 'void', p=dict(bg=(0.0, 0.05, 0.0)),
         girl=dict(x=540, y=1360, s=2.0, style='duo', kw=dict(ink=INK, paper=GREEN, cell=9), nod=1.0),
         fx=dict(punch=0.03, flash_in=0.4))
    line('r9', fontset='heavy', box=(60, 160, 1020, 760), colors=(WHITE, GREEN, WHITE), shadow=(10, 10), shadow_color=INK,
         max_size=260, enter='slam', exit='rewind')
    # "run it back": a short rewind of the picture before the final hook slams in
    ra = st('r9', 3) - 0.03
    rb = st('r9', 6) - 0.03
    shot('r_rew', ra, 'void', replay=True, over=[F.vhs(ra, rb, label=True)], fx=dict(grain=0.04))
    REWINDS.append((ra, rb, 3.0))
    shot('r_bring', rb, 'rally', p=dict(bg=GREEN, burst_alpha=0.35),
         girl=dict(x=540, y=1480, s=2.15, style='duo', kw=dict(ink=INK, paper=GREEN, cell=9), nod=1.0),
         fx=dict(punch=0.04, flash_in=0.6))


def _needle(cx, cy, t0, t1):
    def f(img, tc, t, fi, env):
        if t < t0:
            return img
        u = ease_out(clamp01((t - t0) / max(0.1, t1 - t0)), 2)
        a = math.pi * (1 - 0.92 * u) + 0.03 * math.sin(t * 40) * u
        x, y = cx + 230 * math.cos(a), cy - 230 * math.sin(a)
        cv2.line(img, (int(cx), int(cy)), (int(x), int(y)), (0.05, 0.05, 0.05), 12, cv2.LINE_AA)
        return img
    return f


# ======================================================================================== OUTRO
def neon_outro(t):
    i = 'o6'
    if t < st(i, 1) - 0.05:
        return 0.0
    return sum(clamp01((t - st(i, k + 1) + 0.04) / 0.08) for k in range(3))


ECHO_TIMES = [257.89, 258.50, 259.07, 259.67, 260.50, 260.94, 261.24]   # chopped "back" echoes (chunked ASR)


def build_outro():
    table = (('flowers', 230, 300, 1130), ('candle', 70, 760, 1170))
    p = dict(green=1.0, neon=neon_outro, mugs=1, steam=0.0, table=table, candle=(760, 1040))
    fx = dict(grain=0.065, punch=0.008)
    t98 = max(B(98), last('h2h') + 0.05)   # let the final chant finish on the rally
    shot('o_window', t98, 'diner', p=p, cam=(1.0, 1.06, 700, 520), fx=dict(fx, flash_in=0.3),
         back=[F.prop('jacket', 250, 960, 1000, swing=1.5, enter=None)])
    line('o1', fontset='mono', box=(70, 1420, 1010, 1860), colors=(CREAM, GREEN), stroke=8, stroke_color=INK,
         max_size=110, enter='type', align='left')
    shot('o_cold', first('o2') - 0.05, 'diner', p=p, cam=(1.45, 1.6, 540, 1180), fx=fx)
    line('o2', fontset='mono', box=(70, 1450, 1010, 1860), colors=(CREAM, CREAM), stroke=8, stroke_color=INK,
         max_size=120, enter='type', align='left')
    shot('o_vote', first('o3') - 0.05, 'diner', p=p, cam=(1.06, 1.1, 540, 900), fx=fx,
         back=[F.prop('jacket', 250, 960, 1000, swing=1.5, enter=None)])
    line('o3', fontset='mono', box=(70, 1420, 1010, 1860), colors=(CREAM, AMBER), stroke=8, stroke_color=INK,
         max_size=110, enter='type', align='left')
    shot('o_us', first('o4') - 0.05, 'diner', p=p, cam=(1.0, 1.03, 540, 960), fx=fx,
         back=[F.prop('jacket', 250, 960, 1000, swing=1.5, enter=None)],
         girl=dict(x=330, y=1500, s=1.5, style='color', kw=dict(border=8, shadow=(12, 10), shadow_color=GREEN_D),
                   nod=0.35, enter='pop', t0=first('o4') - 0.05))
    line('o4', fontset='mono', box=(70, 150, 1010, 560), colors=(CREAM, GREEN), stroke=8, stroke_color=INK,
         max_size=110, enter='type', align='left')
    # (scratch) 先让真相回来 — : the picture rewinds once more
    ta = first('o5') - 0.05
    tb = first('o6') - 0.05
    shot('o_scratch', ta, 'diner', replay=True, over=[F.vhs(ta, tb, label=False)], fx=dict(grain=0.05))
    REWINDS.append((ta, tb, 1.6))
    line('o5', fontset='heavy', box=(60, 1400, 1020, 1800), colors=(WHITE,), stroke=10, stroke_color=INK,
         shadow=(10, 10), shadow_color=GREEN, max_size=180, enter='slam')
    # Then bring Jensen... back. : the neon sign from the first bars relights, word by word
    shot('o_neon', tb, 'diner', p=p, cam=(1.0, 1.0, 540, 600), fx=dict(fx, flash_in=0.25),
         back=[F.prop('jacket', 250, 960, 1000, swing=1.5, enter=None)],
         girl=dict(x=330, y=1500, s=1.5, style='color', kw=dict(border=8, shadow=(12, 10), shadow_color=GREEN_D), nod=0.2))
    line('o6', fontset='mono', box=(70, 1500, 1010, 1640), colors=(CREAM,), stroke=8, stroke_color=INK, max_size=90,
         enter='type', align='right', t_end=ECHO_TIMES[0] - 0.05)
    SHOTS[-1].over_.append(F.echo_words('back', ECHO_TIMES, cx=790, cy=1560, size0=170, color=GREEN, fontname='PermanentMarker'))
    # the tail: slow push into the window, the green light stays on; credits; fade
    t_end = 262.2
    shot('o_tail', t_end, 'diner', p=dict(p, neon=3.0), cam=(1.0, 1.55, 800, 430), fx=dict(fx, punch=0.0),
         over=[F.rect(0, 1380, W, H, INK, t0=264.4, use_t=True, alpha=0.72),
               F.credits([('BRING JENSEN BACK', 'Anton', 96), ('词曲 / 演唱  annasu82 / Suno', 'NotoSansSC-Bold', 42),
                          ('MV  逐帧程序渲染', 'NotoSansSC-Bold', 42)], 265.0, 272.0, y=1520),
               F.fade(272.6, DUR, INK, to=1.0)])


# ======================================================================================== assemble
build_intro()
build_verse1()
build_pre()
build_hook('h1', ['h1a', 'h1b', 'h1c', 'h1d', 'h1e', 'h1f', 'h1g'], 30)
build_verse2()
build_build()
build_drop()
build_verse3()
build_bridge()
build_hook('h2', ['h2a', 'h2b', 'h2c', 'h2d', 'h2e', 'h2f', 'h2g', 'h2h'], 90, big=True)
build_outro()

SHOTS.sort(key=lambda s: s.t0)
for a, b in zip(SHOTS, SHOTS[1:]):
    a.t1 = b.t0
SHOTS[-1].t1 = DUR + 1
_STARTS = [s.t0 for s in SHOTS]

# a line leaves when the next one starts (unless it set its own end)
LINES.sort(key=lambda l: l.first())
_ENTRY_START = sorted((e['units'][0]['s'], eid) for eid, e in TIM.items())
for a in LINES:
    if a.t_end is None:
        nxt = [ts for ts, eid in _ENTRY_START if eid != a.tm['id'] and ts > a.tm['units'][0]['s']]
        a.t_end = (min(nxt) - 0.05) if nxt else 262.0
# lines never outlive the section change by more than their own exit
_LSTART = [l.t0 for l in LINES]


def shot_at(t):
    i = bisect.bisect_right(_STARTS, t) - 1
    return SHOTS[max(0, i)]


def content_time(t):
    for (a, b, speed) in REWINDS:
        if a <= t < b:
            return a - (t - a) * speed
    return t


def lyrics_layer(img, t, fi, env, sh):
    k = float(env['kick'][fi]) * sh.fx.get('text_kick', 0.6)
    for ln in LINES:
        if ln.t0 <= t and (ln.t_end is None or t < ln.t_end + 1.2):
            ln.draw(img, t, kick=k)
    return img


class Seg:
    def __init__(self, name, f0, f1):
        self.name, self.f0, self.f1 = name, f0, f1


def segments(chunk=96):
    out = []
    for i, f0 in enumerate(range(0, NFRAMES, chunk)):
        out.append(Seg(f's{i:03d}', f0, min(NFRAMES, f0 + chunk)))
    return out


def segs_for(t0, t1, chunk=96):
    return [s.name for s in segments(chunk) if s.f1 / FPS > t0 and s.f0 / FPS < t1]
