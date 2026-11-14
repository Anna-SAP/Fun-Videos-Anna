"""The score: every shot, every lyric line's look, every prop, keyed to measured times.

Times come from two places only: the beat grid B(bar, beat) (96.00 BPM, first downbeat 0.090 s) for cuts,
and lyric_timing.json (aligned per unit) via st(id, k) / first(id) / last(id) for anything tied to a word.

Sections (bars from the measured drum grid, see storyboard.md):
  intro 1-12   diner 1993, no drums; sung title lights a neon sign; glitch; scratch rewind; call & response
  verse1 13-28 keynote stage, LED wall shows one number/thing per line - the legend
  pre 27-29    the fall: the stage drops, keynote -> headlines; bar 29 the drums cut out: 33 YEARS / ONE WEEK?
  hook1 30-36  rally: chant stamps, crowd; she is one of the crowd, printed like the poster
  verse2 37-53 newsprint: dated clippings, red candles, stamps; the jacket leaves the stage
  build 54-57  counters, petition, candles at the green panel; READY? 3 2 1 (strobe follows the snare)
  drop 58-64   one chant word per screen over the crowd; the strobe shows her for a frame or two
  verse3 65-80 the case board: rumours vs facts, redactions, cut strings, PENDING
  bridge 81-89 handwritten letters (family, colleagues, board, us) and their props
  hook2 90-97  rally again, bigger; she has moved to the front row
  outro 98-110 the diner again: cold coffee, flowers, green light still on; the neon relights on the last line

The heroine (v2) is a witness, not a performer: she is the "us" of the song. She is lit by each scene's own
lights and printed by its own press (person.py), appears where the lyrics leave room and recedes where they are
dense, and never moves except as a person standing still does. Her arc: a reflection in the 1993 window ->
backlit in front of the keynote wall -> one of the crowd -> a street photo in the paper -> at the vigil ->
glimpsed in the strobe -> a soft figure at the case board who comes into focus for "I won't whitewash" ->
printed into the letter at "to us" -> across the diner table at the end.
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


def her(x, y, s, anchor='body', **k):
    d = dict(x=x, y=y, s=s, anchor=anchor)
    d.update(k)
    return d


def ramp(t0, dur, a, b):
    """A value going from a to b over [t0, t0 + dur] (for lights and focus pulls)."""
    return lambda t: a + (b - a) * clamp01((t - t0) / max(1e-3, dur)) ** 1.0


# light set-ups (person.py) - each is the scene's own light, not a studio look
LED_BACK = dict(amb=(0.15, 0.20, 0.14), key=dict(color=(0.50, 0.56, 0.46), dir=(-1, -0.3), k=0.45),
                rim=dict(color=(0.6, 1.0, 0.35), dir=(0, -1), k=1.6, width=6, omni=0.5), wrap=0.5, sat=0.8)
LAMP_L = dict(amb=(0.20, 0.22, 0.28), key=dict(color=(1.0, 0.78, 0.5), dir=(-1, -0.2), k=0.75),
              rim=dict(color=(0.55, 0.7, 1.0), dir=(1, -0.5), k=0.8, width=6), wrap=0.4, sat=0.8)
LAMP_R = dict(amb=(0.20, 0.22, 0.28), key=dict(color=(1.0, 0.78, 0.5), dir=(1, -0.2), k=0.75),
              rim=dict(color=(0.55, 0.7, 1.0), dir=(-1, -0.5), k=0.8, width=6), wrap=0.4, sat=0.8)


class Shot:
    def __init__(self, name, t0, scene, p=None, girl=None, back=(), front=(), over=(), fx=None, cam=None, replay=None):
        self.name, self.t0, self.scene = name, t0, scene
        self.p = p or {}
        self.girls = [F.her(g) for g in (girl if isinstance(girl, list) else ([girl] if girl else []))]
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
            img = g(img, tc, t, fi, env)
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


WINDOW = (110, 170, 970, 930)


def reflection(t0, opacity=0.5, tint=(0.75, 0.85, 1.0)):
    """Her, as the night window of the 1993 diner reflects whoever stands in the room today."""
    return her(700, 600, 2.2, anchor='face', look='reflect', flip=True, opacity=opacity, dof=1.4, clip=WINDOW,
               tint=tint, vignette=(700, 640, 320, 400), t0=t0, fade=1.6, sway=1.0, breath=1.0)


def build_intro():
    shot('i_title', 0.0, 'diner', p=dict(green=0.0, neon=neon_intro, mugs=3, steam=1.0), cam=(1.0, 1.07, 540, 560),
         fx=dict(grain=0.07, flashes=[]), over=[F.fade(0.0, 2.2, INK, to=0.0, frm=1.0)])
    t3 = first('i3') - 0.15
    shot('i_1993', t3, 'diner', p=dict(green=0.0, neon=0.0, mugs=3, steam=1.0), cam=(1.32, 1.42, 540, 1150),
         girl=reflection(first('i3') + 0.3, 0.42), fx=dict(grain=0.07))
    line('i3', fontset='mono', box=(70, 1500, 1010, 1860), colors=(CREAM,), stroke=8, stroke_color=INK, max_size=120,
         enter='type', align='left')
    SHOTS[-1].over_.append(F.big('1993', 'Anton', 420, 540, 520, AMBER, t0=st('i3', 0), t1=first('i4') - 0.1,
                                 enter='stamp', shadow=(12, 12), shadow_color=INK))
    t4 = first('i4') - 0.1
    # the green light comes on outside, right behind her reflection
    shot('i_33later', t4, 'diner', p=dict(green=green_i4, neon=0.0, mugs=3, steam=1.0), cam=(1.0, 1.05, 700, 500),
         girl=dict(reflection(t4 - 2.0, 0.55, tint=(0.72, 0.95, 0.8))), fx=dict(grain=0.06))
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
    # I say "Bring him", you say "Back": the first time we see her - standing in front of the keynote wall,
    # lit from behind as the wall comes up
    nxt = first('v1a') - 0.04
    lit = dict(LED_BACK, rim=dict(LED_BACK['rim'], k=ramp(t7, 0.8, 0.0, 1.6)))
    shot('i_mc', t7, 'stage', p=dict(keys=[], beams=0, led=GREEN), fx=dict(grain=0.04, flash_in=0.5),
         girl=her(790, 1520, 1.55, **lit), front=[F.haze_beams(2, k=0.07)])
    line('i7', **v1style(box=(60, 130, 1020, 760), max_size=230, rows=[[0, 1], [2, 3], [4, 5, 6]],
                         t_end=st('i8', 0) - 0.05))
    # Bring him! (Back!) x2 : the wall answers in white / green; the light on her answers with it
    calls = [st('i8', 0), st('i8', 3)]
    resps = [st('i8', 2), st('i8', 5)]
    seq = sorted([(c, 'call') for c in calls] + [(r, 'resp') for r in resps])
    for j, (ta, kind) in enumerate(seq):
        tb = seq[j + 1][0] if j + 1 < len(seq) else nxt
        call = kind == 'call'
        col = (0.95, 0.95, 0.9) if call else GREEN
        rim = dict(color=tuple(col), dir=(0, -1), k=1.7, width=6, omni=0.55)
        shot(f'i_{kind}{j}', ta - 0.04, 'stage', p=dict(keys=[(ta - 0.04, 'BRING\nHIM' if call else 'BACK!', 'text')],
                                                       beams=0, led=col),
             girl=her(790, 1520, 1.55, **dict(LED_BACK, rim=rim)),
             over=[F.big('BRING HIM!' if call else 'BACK!', 'Anton', 0, 540, 520 if call else 560,
                         WHITE if call else GREEN, t0=ta - 0.04, t1=tb - 0.04, width=960 if call else 1000,
                         enter='slam', shadow=(12, 12), shadow_color=INK)],
             fx=dict(flash_in=0.35, punch=0.03))


# ======================================================================================== VERSE 1
V1_KEYS = {  # line id -> what the LED wall shows (a word/number or a prop silhouette)
    'v1a': ('boat', 'prop'), 'v1b': ('FUTURE', 'text'), 'v1c': ('$40K', 'text'), 'v1d': ('30\nDAYS', 'text'),
    'v1e': ('1999', 'text'), 'v1f': ('2006', 'text'), 'v1g': ('AI', 'text'), 'v1h': ('chip', 'prop'),
    'v1i': ('jacket', 'prop'), 'v1j': ('MORE', 'text'), 'v1k': ('FLASH', 'text'), 'v1l': ('60:1', 'text'),
    'v1m': ('33', 'text'), 'v1n': ('TOP', 'text'),
}


def build_verse1():
    """The legend is told by the wall. She is in three of the seven framings, always lit by that wall."""
    keys = [(first(i) - 0.05, k, kind) for i, (k, kind) in V1_KEYS.items()]
    t0 = min(B(13), first('v1a') - 0.05)
    fx = dict(punch=0.022, shake=4, grain=0.04)
    close = dict(LED_BACK, rim=dict(color=(0.6, 1.0, 0.35), dir=(1, -0.6), k=1.4, width=7, omni=0.4),
                 key=dict(color=(0.55, 0.6, 0.5), dir=(-1, 0), k=0.55))
    frames = [  # (start, scene params, her, back, front)
        (t0, dict(keys=keys, beams=2), None, [], []),
        (B(15), dict(keys=keys, beams=0), her(800, 1510, 1.6, **LED_BACK), [], [F.haze_beams(2, k=0.08)]),
        (B(17), dict(keys=keys, beams=2), None, [], []),
        (B(19), dict(keys=keys, beams=0), her(700, 1270, 3.3, anchor='face', **close), [F.scene_blur(6.5)], []),
        (B(21), dict(keys=keys, beams=2), None, [], []),
        (B(23), dict(keys=keys, beams=0), her(300, 1500, 1.65, **dict(LED_BACK, key=dict(color=(0.5, 0.56, 0.46),
                                                                                       dir=(1, -0.3), k=0.45))),
         [], [F.haze_beams(2, k=0.09, t_speed=0.8)]),
        (B(25), dict(keys=keys, beams=2), None, [], []),
    ]
    for j, (ta, sp, g, back, front) in enumerate(frames):
        shot(f'v1_{j}', ta, 'stage', p=sp, girl=g, back=back, front=front, fx=dict(fx, flash_in=0.3 if j else 0.9))
    for i in ['v1a', 'v1b', 'v1c', 'v1d', 'v1e', 'v1f', 'v1g', 'v1h', 'v1i', 'v1j', 'v1k', 'v1l', 'v1m', 'v1n']:
        line(i, **v1style(box=TOP))


# ======================================================================================== PRE-CHORUS
def build_pre():
    fall = st('p1a', 6)   # the first character of the second phrase: the fall
    # the wall that lit her goes dark at "the fall"; she stays, losing her light
    dim = dict(LED_BACK, rim=dict(LED_BACK['rim'], k=lambda t: 1.6 if t < fall else max(0.15, 1.6 - 3.0 * (t - fall))),
               key=dict(LED_BACK['key'], k=lambda t: 0.45 if t < fall else max(0.08, 0.45 - 0.8 * (t - fall))))
    shot('pre_peak', first('p1a') - 0.05, 'stage', p=dict(keys=[(first('p1a') - 0.05, 'PEAK', 'text'),
                                                              (fall, 'DROP', 'text')], led=GREEN, beams=0),
         girl=her(560, 1510, 1.7, **dim), front=[F.haze_beams(2, k=0.06)],
         fx=dict(punch=0.03, shake=6, flash_in=0.3))
    line('p1a', **v1style(exit='fall'))
    hl = st('p1b', 5)   # "headlines"
    shot('pre_keynote', first('p1b') - 0.05, 'stage', p=dict(keys=[(first('p1b') - 0.05, 'KEYNOTE', 'text')], beams=2),
         fx=dict(punch=0.03))
    shot('pre_headlines', hl - 0.03, 'paper', p=dict(rule_red=True, seed=3),
         back=[F.rubber_stamp('HEADLINES', 540, 1300, hl, size=120, rot=-8, color=RED)],
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


def hook_pair(i, chant_cols, adlib_col, shadow_color, ans_box=(70, 690, 690, 900), band=WHITE, ans_ink=INK,
              chant_box=(40, 110, 1040, 620), adlib_xy=(720, 720)):
    """Hook line = the chant (BRING JENSEN / BACK!) up top + the Chinese answer on a paper strip under it."""
    us = TY.lyrics.units(TIM[i]['line'])
    chant = [k for k, u in enumerate(us) if not u['cjk'] and not u['adlib']]
    adl = [k for k, u in enumerate(us) if u['adlib']]
    ans = [k for k, u in enumerate(us) if u['cjk'] and not u['adlib']]
    line(i, fontset='heavy', box=chant_box, colors=chant_cols, max_size=420, enter='slam', rows=[[0, 1], [2]],
         skip=ans, adlib_box=[adlib_xy], adlib_color=adlib_col, adlib_size=118, shadow=(12, 12),
         shadow_color=shadow_color, gap=0.02)
    ln = line(i, fontset='heavy', box=ans_box, colors=(ans_ink,), max_size=150, enter='stamp', skip=chant + adl,
              valign='center', min_len=3, max_len=7.5)
    ln.id = i + '#ans'
    SHOTS[-1].front.append(F.band_for(L_(i + '#ans'), color=band))


def crowd_of(ink, rows, sign_color, sign_ink=INK):
    return lambda img, tc, t, fi, env: SC.crowd(img, tc, float(env['kick'][fi]), color=ink, rows=rows,
                                                sign_color=sign_color, sign_ink=sign_ink)


def build_hook(tag, ids, bar0, big=False):
    """She is one of the crowd: printed in the poster's own ink, partly hidden by the people in front of her.
    In the second hook (big) she has moved forward."""
    looks = [(GREEN, INK, RED), (INK, GREEN, WHITE), (GREEN, INK, RED), (INK, GREEN, WHITE)]
    crowd_rows = 4 if big else 3
    # (x, y, s, anchor, fg heads)
    if big:
        place = [(560, 1540, 1.75, 'body', [(130, 1520, 1.7), (960, 1470, 1.9)]),
                 (640, 1600, 1.35, 'body', [(950, 1560, 1.5)]),
                 (480, 1540, 1.8, 'body', [(980, 1500, 1.8), (110, 1580, 1.5)]),
                 (560, 1230, 3.0, 'face', [(140, 1500, 2.0), (950, 1540, 2.1)])]
    else:
        place = [(560, 1570, 1.45, 'body', [(140, 1460, 1.6), (950, 1420, 1.8)]),
                 (660, 1680, 1.05, 'body', [(950, 1600, 1.4)]),
                 (470, 1580, 1.5, 'body', [(980, 1440, 1.8), (120, 1520, 1.5)]),
                 (570, 1280, 2.5, 'face', [(130, 1520, 1.9), (960, 1560, 2.0)])]
    for j, i in enumerate(ids[:4]):
        bg, ink, ad = looks[j]
        ta = B(bar0 + j * 1) if j == 0 else first(i) - 0.05
        burst = GREEN_D if bg is GREEN else (0.06, 0.12, 0.04)
        x, y, s, anchor, heads = place[j]
        # on green she is ink on the green poster; on black she is the same print in green light
        g = her(x, y, s, anchor=anchor, look='print', ink=INK, paper=GREEN, cell=8 if s < 2 else 10,
                dof=1.2 if j % 2 else 0.0)
        back = []
        if j == 0:
            back.append(F.prop('jacket', 300, 880, 900, t0=st(i, 4) - 0.05, swing=6, enter='drop', use_t=True))
        if j == 1:
            back.append(F.prop('folder', 300, 200, 1000, t0=st(i, 4) - 0.05, rot=8, enter='slam', use_t=True))
        if j == 3:
            back.append(F.big('33', 'Anton', 900, 540, 1100, bg * 0.75 + ink * 0.25, t0=st(i, 4) - 0.05, enter='stamp'))
        front = [crowd_of(ink, crowd_rows, bg if bg is not INK else PAPER),
                 F.fg_heads(heads, color=ink if bg is GREEN else (0.02, 0.02, 0.02), blur=11)]
        shot(f'{tag}_{j}', ta, 'rally', p=dict(bg=bg, burst_color=burst, burst_alpha=0.35), girl=g, back=back, front=front,
             fx=dict(punch=0.035, shake=7, flash_in=0.5 if j == 0 else 0.25, grain=0.035, split=3 if big else 0))
        hook_pair(i, (INK, INK) if bg is GREEN else (GREEN, WHITE), RED if bg is GREEN else WHITE,
                  WHITE if bg is GREEN else RED, band=WHITE if bg is GREEN else GREEN)
    # stock fell, the people didn't leave: red light on the same crowd
    e, f, g = ids[4], ids[5], ids[6]
    shot(f'{tag}_stock', first(e) - 0.05, 'void', p=dict(bg=(0.06, 0.01, 0.01), burst=True, burst_color=(0.12, 0.02, 0.02)),
         back=[F.candles_chart(first(e), st(e, 3) + 0.2, ytop=760, ybot=1250, n=12)],
         girl=her(600, 1600 if not big else 1560, 1.4 if not big else 1.7, look='print', ink=INK, paper=RED, cell=8),
         front=[crowd_of(INK, crowd_rows, PAPER), F.fg_heads([(130, 1500, 1.7), (960, 1460, 1.8)], color=INK, blur=11)],
         fx=dict(punch=0.035, shake=7, flash_in=0.3, split=4))
    hook_line(e, RED, WHITE, GREEN, colors=(WHITE, WHITE), shadow=(10, 10), shadow_color=INK,
              adlib_box=[(560, 640)], box=(60, 130, 1020, 620), max_size=260, adlib_size=150)
    # "the green light is still on": it hangs over the crowd and lights her from above
    gl = dict(amb=(0.10, 0.14, 0.10), key=dict(color=(0.45, 0.85, 0.3), dir=(0, -1), k=0.9, soft=0.7),
              rim=dict(color=(0.6, 1.0, 0.35), dir=(0, -1), k=1.6, width=6, omni=0.35), wrap=0.5, sat=0.75)
    shot(f'{tag}_green', first(f) - 0.05, 'void', p=dict(bg=(0.0, 0.02, 0.0)),
         back=[F.green_light(540, 560, 180, t0=first(f) - 0.05, use_t=True, flicker_on=0.25)],
         girl=her(560, 1610 if not big else 1560, 1.55 if not big else 1.8, **gl),
         front=[crowd_of(INK, crowd_rows, GREEN), F.fg_heads([(150, 1560, 1.7), (940, 1520, 1.8)], color=INK, blur=11)],
         fx=dict(punch=0.035, shake=6, flash_in=0.3))
    hook_line(f, INK, GREEN, WHITE, colors=(INK, INK), shadow=None, adlib_box=[(640, 960)], adlib_color=GREEN,
              box=(80, 790, 1000, 950), max_size=150, valign='center', adlib_size=130, min_len=3, max_len=7.5)
    SHOTS[-1].front.append(F.band_for(L_(f), color=GREEN))
    # "not a pardon, not a show trial - evidence first": the paper; she is a small street photo
    shot(f'{tag}_facts', first(g) - 0.05, 'paper', p=dict(seed=7, rule_red=True),
         back=[F.vox_photo(600, 1150, 1000, 1700, her(800, 1500, 0.95, cell=6), first(g) + 0.3),
               F.prop('folder', 480, 300, 1420, t0=st(g, 10) - 0.04, rot=-6, enter='slam', use_t=True)],
         fx=dict(punch=0.03, shake=5, flash_in=0.3, grain=0.03))
    hook_line(g, PAPER, INK, RED, colors=(INK, INK, RED), shadow=None, box=(60, 140, 1020, 900), max_size=260,
              fontset='heavy')
    SHOTS[-1].over_ += [F.cross_out(L_(g), {2, 3}, last_unit(g, 3)), F.cross_out(L_(g), {6, 7}, last_unit(g, 7))]
    if len(ids) > 7:
        # the final chant: she is in the front row now, the crowd behind her, white flashes on the snare
        h = ids[7]
        fin = dict(amb=(0.24, 0.28, 0.22), rim=dict(color=(0.6, 1.0, 0.35), dir=(0, -1), k=1.5, width=7, omni=0.45),
                   wrap=0.5, sat=0.8, strobe=0.9)
        shot(f'{tag}_final', first(h) - 0.05, 'rally', p=dict(bg=INK, burst_color=(0.1, 0.18, 0.06), burst_alpha=0.6),
             back=[crowd_of((0.06, 0.12, 0.04), 4, GREEN)],
             girl=her(560, 1240, 3.0, anchor='face', **fin),
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
    """The news is about him, not her. She only turns up as a small street-interview photo, three times."""
    fx = dict(punch=0.03, shake=5, split=2, grain=0.035)
    t37 = min(B(37), first('v2a') - 0.05)
    shot('v2_0', t37, 'paper', p=dict(seed=1, rule_red=True, rule_y=110), fx=dict(fx, flash_in=0.7),
         back=[F.rubber_stamp('10.29', 300, 1250, st('v2a', 0), size=190, rot=-10)],
         over=[F.big('BANG', 'Anton', 0, 540, 1000, RED, t0=st('v2a', 13), t1=st('v2a', 13) + 0.4, width=700,
                     enter='slam')])
    headline('v2a')
    headline('v2b', colors=(INK, RED))
    shot('v2_1', B(41) if B(41) < first('v2d') else first('v2d') - 0.05, 'paper', p=dict(seed=2, tone=1), fx=fx,
         back=[F.vox_photo(80, 1120, 460, 1640, her(270, 1450, 0.9, cell=6), B(41) + 0.1)]
         + [F.prop('envelope', 260, 720 + 90 * k, 1150 + 60 * k, t0=st('v2d', 9) + 0.08 * k, rot=-8 + 8 * k,
                   enter='slam', use_t=True) for k in range(3)])
    headline('v2c', colors=(INK, RED))
    headline('v2d')
    shot('v2_2', first('v2e') - 0.05, 'paper', p=dict(seed=3, rule_red=True), fx=fx,
         back=[F.rubber_stamp('11.08', 300, 1200, st('v2e', 0), size=170, rot=-8),
               F.prop('envelope', 420, 640, 1460, t0=st('v2e', 5), rot=6, enter='slam', use_t=True)])
    headline('v2e')
    headline('v2f', colors=(INK, RED))
    shot('v2_3', first('v2g') - 0.05, 'paper', p=dict(seed=4, tone=1), fx=fx,
         back=[F.prop('folder', 620, 540, 1360, t0=st('v2g', 3), rot=-4, enter='slam', use_t=True)])
    headline('v2g')
    shot('v2_4', first('v2h') - 0.05, 'paper', p=dict(seed=5, greek_alpha=0.12),
         back=[F.rubber_stamp('11.09', 800, 1080, st('v2h', 0), size=130, rot=8),
               F.candles_chart(st('v2h', 7), st('v2h', 11), ytop=1150, ybot=1800, n=12, x0=60, x1=1020)],
         fx=dict(fx, flash_in=0.3))
    headline('v2h', colors=(INK, RED, INK), adlib_box=[(120, 900), (600, 960)], adlib_color=RED, adlib_size=110)
    shot('v2_5', first('v2i') - 0.05, 'paper', p=dict(seed=6), fx=fx,
         back=[F.big('?', 'Anton', 1000, 300, 1350, RED, t0=st('v2i', 0), enter='stamp', alpha=0.9),
               F.vox_photo(600, 1120, 1000, 1660, her(800, 1440, 0.95, cell=6), first('v2i') + 0.25)])
    headline('v2i')
    headline('v2j', colors=(INK, RED))
    SHOTS[-1].back.append(F.big('?', 'Anton', 1300, 300, 1350, RED, t0=st('v2j', 4), enter='slam'))
    shot('v2_6', first('v2k') - 0.05, 'paper', p=dict(seed=7, tone=1), fx=dict(fx, shake=8),
         back=[F.rubber_stamp('爆料', 700 - 260 * (k % 2), 1050 + 250 * k, st('v2k', 7 + 3 * (k % 2)) + 0.15 * k, size=130,
                              rot=(-14 + 9 * k), fontname='NotoSansSC-Black') for k in range(3)])
    headline('v2k', colors=(INK, RED))
    shot('v2_7', first('v2l') - 0.05, 'void', p=dict(bg=(0.10, 0.0, 0.0)),
         back=[F.fire(st('v2l', 6), first('v2m'))],
         over=[F.big('-11%', 'Anton', 0, 540, 1250, WHITE, t0=st('v2l', 2), width=960, enter='slam', shadow=(16, 16),
                     shadow_color=INK)],
         fx=dict(fx, flash_in=0.5, split=5))
    headline('v2l', colors=(WHITE, RED), shadow=(8, 8), shadow_color=INK, fontset='heavy')
    shot('v2_8', first('v2m') - 0.05, 'paper', p=dict(seed=8, rule_red=True), fx=fx,
         back=[F.rubber_stamp('11.12', 300, 1150, st('v2m', 0), size=170, rot=-6),
               F.rect(440, 1300, 940, 1760, (0.97, 0.96, 0.92), t0=st('v2m', 6), use_t=True),
               F.rect(480, 1350, 900, 1368, INK, t0=st('v2m', 6), use_t=True),
               F.rect(480, 1420, 840, 1438, INK, t0=st('v2m', 6), use_t=True),
               F.rect(480, 1490, 870, 1508, INK, t0=st('v2m', 6), use_t=True)])
    headline('v2m')
    shot('v2_9', first('v2n') - 0.05, 'paper', p=dict(seed=9), fx=dict(fx, flash_in=0.3),
         back=[F.big('1993 — 2026', 'Anton', 0, 540, 1500, INK, t0=st('v2n', 0), width=820, enter='stamp', alpha=0.85)],
         over=[F.rubber_stamp('EFFECTIVE IMMEDIATELY', 540, 1150, st('v2n', 6), size=82, rot=-9)])
    headline('v2n', colors=(INK, RED))
    shot('v2_10', first('v2o') - 0.05, 'paper', p=dict(seed=10, tone=1), fx=fx,
         back=[F.vox_photo(80, 1120, 460, 1640, her(270, 1450, 0.9, cell=6), first('v2o') + 0.2),
               F.prop('chair', 300, 760, 1420, t0=st('v2o', 6), enter='pop', use_t=True)])
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
         fx=dict(fx, strobe=0.28))
    line('b2', **v1style(box=(60, 200, 1020, 760)))
    # the vigil: she stands behind the candles, lit from below by them and from behind by the green panel
    t3 = first('b3') - 0.05
    candle_k = lambda t: 0.95 + 0.12 * math.sin(t * 13.0) * math.sin(t * 4.7)   # noqa: E731
    vig = dict(amb=(0.10, 0.11, 0.10), key=dict(color=(1.0, 0.62, 0.28), dir=(0, 1), k=candle_k, soft=0.55, gamma=1.8),
               rim=dict(color=(0.6, 1.0, 0.35), dir=(0, -1), k=1.4, width=6, omni=0.5), wrap=0.6, sat=0.8,
               t0=t3, fade=0.5)
    shot('b_candles', t3, 'void', p=dict(bg=(0.01, 0.015, 0.01)),
         back=[F.rect(240, 700, 840, 1180, GREEN * 0.9, t0=t3),
               lambda img, tc, t, fi, env: SC.glow(img, 540, 940, 300, GREEN * 0.6, 0.6)],
         girl=her(540, 1530, 1.55, **vig),
         front=[F.prop('flowers', 300, 200, 1570, t0=st('b3', 0), enter='pop', use_t=True),
                F.prop('flowers', 300, 880, 1570, t0=st('b3', 1), enter='pop', use_t=True)]
         + [F.prop('candle', 90, 360 + 90 * k, 1600 + (k % 2) * 30, t0=st('b3', 2) + 0.05 * k, enter='pop', use_t=True)
            for k in range(5)]
         + [lambda img, tc, t, fi, env, k=k: SC.glow(img, 360 + 90 * k, 1475 + (k % 2) * 30, 26, AMBER,
                                                     (0.8 + 0.2 * math.sin(t * 13 + k)) * (t > st('b3', 2) + 0.05 * k))
            for k in range(5)],
         fx=dict(fx, strobe=0.30))
    line('b3', **v1style(box=(60, 150, 1020, 620)))
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
WASH = [GREEN, RED, (0.95, 0.93, 0.86), (0.25, 0.55, 1.0), AMBER, GREEN_D]


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


def strobe_her(x, y, s, anchor='body', k=1.0):
    """Her in a dark jumping crowd: a silhouette, until the snare strobe fires and shows her face."""
    return her(x, y, s, anchor=anchor, amb=(0.04, 0.04, 0.05), strobe=k, wrap=0.3, sat=0.7,
               rim=dict(color=(0.9, 0.9, 1.0), dir=(0, -1), k=0.5, width=5, omni=0.4))


def build_drop():
    """No more grids or copies of her: the drop is the crowd under coloured wash lights and a strobe."""
    fx = dict(punch=0.05, shake=10, split=4, grain=0.03, strobe=0.25)
    for tag, i, off in (('d1', 'd1', 0), ('d2', 'd2', 3)):
        us = TY.lyrics.units(TIM[i]['line'])
        words = chant_words(i, [0, 1, 2], color=WHITE, shadow=INK)
        for k in range(3):
            ta = st(i, k) - 0.04
            bg = WASH[(off + k) % len(WASH)]
            g = strobe_her(560, 1610, 1.35) if k == 2 else None
            shot(f'{tag}_{k}', ta, 'rally', p=dict(bg=bg, burst_color=INK, burst_alpha=0.18), girl=g,
                 front=[crowd_of(INK, 4, PAPER)] + ([F.fg_heads([(140, 1500, 1.8), (940, 1470, 1.9)], color=INK, blur=10)]
                                                    if g else []),
                 fx=dict(fx, flash_in=0.8 if k == 2 else 0.4), over=list(words))
        # Hey! Hey! + the answer
        ta = st(i, 3) - 0.04
        bg = WASH[(off + 3) % len(WASH)]
        shot(f'{tag}_hey', ta, 'rally', p=dict(bg=bg, burst_alpha=0.4, burst_color=INK),
             front=[crowd_of(INK, 4, PAPER)], fx=dict(fx, flash_in=0.4))
        SHOTS[-1].over_ += [F.big('HEY!', 'Anton', 300, 300 + 480 * j, 330 + 60 * j, INK, t0=st(i, 3 + j) - 0.04,
                                  t1=last(i) + 0.2, enter='slam', rot=(-8 + 16 * j), shadow=(10, 10), shadow_color=WHITE)
                            for j in range(2)]
        line(i, fontset='heavy', box=(50, 620, 1030, 1000), colors=(WHITE,), stroke=12, stroke_color=INK,
             shadow=(14, 14), shadow_color=RED, max_size=330, enter='slam', rows=[list(range(5, len(us)))],
             keep_adlib=True)
    # Stand with x3 Jensen: three follow spots search the crowd; the third finds her
    i = 'd3'
    s3 = st(i, 4)
    found = her(600, 1600, 1.4, amb=(0.04, 0.05, 0.04), wrap=0.4, sat=0.8,
                key=dict(color=(1.0, 1.0, 0.95), dir=(0, -1), k=ramp(s3, 0.25, 0.0, 1.3), soft=0.8),
                rim=dict(color=(0.6, 1.0, 0.35), dir=(0, -1), k=1.0, width=5, omni=0.4))
    shot('d3', first(i) - 0.05, 'void', p=dict(bg=(0.015, 0.02, 0.015)), girl=found,
         front=[crowd_of((0.0, 0.0, 0.0), 4, (0.3, 0.3, 0.3)),
                F.spotlight(120, 260, 1450, st(i, 0) - 0.04, r=150, sweep=(300, -100)),
                F.spotlight(960, 860, 1480, st(i, 2) - 0.04, r=150, sweep=(-300, -100)),
                F.spotlight(540, 600, 1240, s3 - 0.04, r=190, sweep=(-260, 120), k=0.45)],
         fx=dict(fx, flash_in=0.6, strobe=0.0))
    line(i, fontset='heavy', box=(60, 110, 1020, 900), colors=(GREEN, PAPER, RED, WHITE), max_size=300, enter='slam',
         rows=[[0, 1], [2, 3], [4, 5], [6]], shadow=(10, 10), shadow_color=INK)
    # Thirty-three, thirty-three, 要个答案
    i = 'd4'
    shot('d4', first(i) - 0.05, 'void', p=dict(bg=GREEN, burst=True, burst_color=GREEN_D, burst_alpha=0.5),
         front=[crowd_of(INK, 3, PAPER)], fx=dict(fx, flash_in=0.5))
    SHOTS[-1].over_ += [F.big('33', 'Anton', 600, (330, 750)[j], (520, 900)[j], (WHITE, INK)[j], t0=st(i, j) - 0.04,
                              enter='slam', shadow=(18, 18), shadow_color=(INK, WHITE)[j], rot=(-6, 6)[j]) for j in range(2)]
    line(i, fontset='heavy', box=(60, 1150, 1020, 1500), colors=(WHITE,), rows=[[2, 3, 4, 5]], stroke=14,
         stroke_color=INK, shadow=(14, 14), shadow_color=RED, max_size=330, enter='slam')
    # the supersaw bars are vocal chops (measured onsets, ~8th notes): the wash light changes on every chop;
    # three times the strobe catches her - wide, closer, closest
    chops = json.load(open('work/audio/chop_onsets.json'))
    seen = {4: (600, 1620, 1.25, 'body'), 9: (520, 1520, 1.75, 'body'), 14: (570, 1230, 2.8, 'face')}
    for k, ta in enumerate(chops):
        bg = WASH[k % len(WASH)]
        g = None
        front = [crowd_of(INK, 4, PAPER)]
        if k in seen:
            x, y, s, anchor = seen[k]
            g = her(x, y, s, anchor=anchor, amb=(0.12, 0.12, 0.12),
                    key=dict(color=(1.0, 1.0, 0.97), dir=(0, -1), k=lambda t, ta=ta: 1.4 * math.exp(-4 * max(0.0, t - ta)),
                             soft=1.0),
                    rim=dict(color=tuple(bg), dir=(0, -1), k=1.2, width=6, omni=0.5), wrap=0.5, sat=0.8)
            front.append(F.fg_heads([(150, 1520, 1.8), (930, 1480, 1.9)], color=INK, blur=11))
        shot(f'd5_{k}', ta - 0.03, 'rally', p=dict(bg=bg, burst_color=INK, burst_alpha=0.2), girl=g, front=front,
             fx=dict(fx, flash_in=0.45 if g else 0.3, split=6))
    i = 'd6'
    shot('d6', st(i, 1) - 0.05, 'rally', p=dict(bg=RED, burst_color=(0.6, 0.05, 0.05), burst_alpha=0.5),
         front=[crowd_of(INK, 4, PAPER)], fx=dict(fx, flash_in=0.6))
    SHOTS[-1].over_ += [F.big('33', 'Anton', 900, 540, 640, WHITE, t0=st(i, 1) - 0.04, enter='slam',
                              shadow=(18, 18), shadow_color=INK, rot=-4)]
    line(i, fontset='heavy', box=(60, 1180, 1020, 1520), colors=(WHITE,), rows=[[1, 2, 3, 4]], stroke=14,
         stroke_color=INK, shadow=(14, 14), shadow_color=GREEN, max_size=330, enter='slam', skip=(0,))


# ======================================================================================== VERSE 3
def evidence(i, box=(60, 130, 1020, 780), colors=(CREAM, GREEN), **k):
    d = dict(fontset='mono', box=box, colors=colors, max_size=180, enter='stamp', shadow=(6, 6), shadow_color=INK,
             max_len=6.5)
    d.update(k)
    return line(i, **d)


def build_verse3():
    """The debate is on the board. She is a soft figure between us and the board, lit by the desk lamp - until
    "I won't whitewash it, I won't pretend not to see": focus leaves the board and finds her."""
    fx = dict(punch=0.025, shake=4, grain=0.04)
    fg_r = her(930, 1360, 2.7, dof=10, **LAMP_L)
    fg_l = her(150, 1360, 2.7, dof=10, **LAMP_R)
    t65 = min(B(65), first('v3a') - 0.05)
    shot('v3_0', t65, 'board', p=dict(), girl=fg_r, fx=dict(fx, flash_in=0.7),
         back=[F.phone_feed(330, 1300, 360, first('v3a'), first('v3b') - 0.05)])
    evidence('v3a', colors=(CREAM, RED, CREAM))
    shot('v3_1', first('v3b') - 0.05, 'board', p=dict(), fx=fx,
         back=[lambda img, tc, t, fi, env: cv2.line(img, (540, 760), (540, 1900), (0.7, 0.7, 0.72), 12, cv2.LINE_AA),
               _halfmast(first('v3b') - 0.05, st('v3b', 8), st('v3b', 11) + 0.2)])
    evidence('v3b')
    shot('v3_2', first('v3c') - 0.05, 'board', p=dict(strings=[(220, 1100, 520, 1500), (520, 1500, 820, 1180)]), fx=fx,
         back=[F.big('TAIPEI?', 'Anton', 190, 420, 1040, GREEN, t0=st('v3c', 0), enter='stamp', rot=-6)])
    evidence('v3c', colors=(CREAM, GREEN))
    shot('v3_3', first('v3d') - 0.05, 'board', p=dict(), girl=fg_l, fx=fx,
         back=[F.prop('heart', 280, 680, 980, t0=first('v3d') - 0.05, use_t=True, drift=(0, 120), enter=None, swing=4)])
    evidence('v3d', colors=(CREAM, RED))
    shot('v3_4', first('v3e') - 0.05, 'board', p=dict(), fx=fx,
         back=[F.scribbles(first('v3e') - 0.05, first('v3f'), color=CREAM, alpha=0.35, speed=300, seed=8)])
    evidence('v3e')
    shot('v3_5', first('v3f') - 0.05, 'board', p=dict(), fx=fx,
         back=[F.prop('card', 220, 300 + 240 * k, 1200 + 40 * (k % 2), rot=-10 + 10 * k, t0=st('v3f', 8) + 0.08 * k,
                      enter='slam', use_t=True) for k in range(3)])
    evidence('v3f', colors=(CREAM, GREEN))
    shot('v3_6', first('v3g') - 0.05, 'board', p=dict(), girl=fg_r, fx=fx,
         back=[F.big('5 DAYS', 'Anton', 190, 270, 800, GREEN, t0=st('v3g', 7), enter='stamp', rot=-5)])
    evidence('v3g')
    shot('v3_7', first('v3h') - 0.05, 'board', p=dict(), fx=fx,
         back=[F.big('12 YEARS', 'Anton', 240, 540, 1150, AMBER, t0=st('v3h', 8), enter='stamp', rot=5)])
    evidence('v3h')
    # rack focus: the board goes soft, she comes sharp - her own stance
    t8 = first('v3i') - 0.05
    sharp = her(640, 1250, 3.3, anchor='face', dof=ramp(t8 + 0.1, 0.55, 9.0, 0.0), **LAMP_L)
    shot('v3_8', t8, 'board', p=dict(), back=[F.scene_blur(ramp(t8 + 0.1, 0.55, 0.0, 7.0))], girl=sharp,
         fx=dict(fx, flash_in=0.0))
    evidence('v3i', box=(60, 140, 1020, 700), colors=(WHITE, GREEN), max_size=160, shadow=(8, 8))
    # ...and back to the evidence
    t9 = first('v3j') - 0.05
    back_soft = her(640, 1250, 3.3, anchor='face', dof=ramp(t9, 0.5, 0.0, 10.0), **LAMP_L)
    shot('v3_9', t9, 'board', p=dict(), back=[F.scene_blur(ramp(t9, 0.5, 7.0, 0.0))], girl=back_soft, fx=fx)
    evidence('v3j', colors=(CREAM, CREAM))
    SHOTS[-1].over_.append(F.redact(L_('v3j'), set(range(7, 13)), last_unit('v3j', 12) - 0.25))
    shot('v3_10', first('v3k') - 0.05, 'board', p=dict(), fx=fx,
         back=[F.scribbles(first('v3k') - 0.05, first('v3l'), color=CREAM, alpha=0.3, speed=200, seed=9, rows=14)])
    evidence('v3k', colors=(CREAM, AMBER))
    shot('v3_11', first('v3l') - 0.05, 'board', p=dict(), fx=fx,
         over=[F.rubber_stamp('COPY', 330, 1180, st('v3l', 9), size=170, rot=-12),
               F.rubber_stamp('2023', 700, 1420, st('v3l', 12), size=130, rot=-7, color=AMBER)])
    evidence('v3l')
    shot('v3_12', first('v3m') - 0.05, 'board', p=dict(), girl=fg_l, fx=fx,
         back=[F.big('<10%', 'Anton', 330, 640, 1150, GREEN, t0=st('v3m', 10), enter='stamp')])
    evidence('v3m', colors=(CREAM, GREEN))
    shot('v3_13', first('v3n') - 0.05, 'board', p=dict(), fx=fx,
         back=[F.prop('chip', 360, 470, 1250, t0=st('v3n', 8), enter='pop', use_t=True),
               F.prop('lock', 260, 560, 1400, t0=st('v3n', 12), enter='slam', use_t=True)])
    evidence('v3n')
    strings = [(120, 900, 520, 1300), (520, 1300, 900, 950), (900, 950, 300, 1700), (300, 1700, 960, 1750)]
    shot('v3_14', first('v3o') - 0.05, 'board', p=dict(strings=strings), fx=fx,
         over=[F.big('X', 'Anton', 1200, 540, 1300, RED, t0=st('v3o', 13), enter='slam', alpha=0.9)])
    evidence('v3o', colors=(CREAM, RED))
    shot('v3_15', first('v3p') - 0.05, 'board', p=dict(), girl=fg_r, fx=fx,
         over=[F.rubber_stamp('PENDING', 400, 1200, st('v3p', 7), size=140, rot=-9, color=AMBER),
               _cursor(660, 1200, st('v3p', 14) + 0.2, B(81))])
    evidence('v3p')


def _halfmast(t0, ta, tb):
    def f(img, tc, t, fi, env):
        if t < t0:
            return img
        u = clamp01((t - ta) / max(0.01, tb - ta))
        y = 900 + 520 * ease_out(u, 2)
        return SC.put(img, 'jacket', 300, 540, y, rot=2 * math.sin(t * 3))
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
    """Four letters. She is in none of the first three - and then, at "to us", her face is in the ink of the
    letter itself: she is the "us"."""
    fx = dict(punch=0.012, grain=0.035)
    t81 = min(B(81), first('r1') - 0.05)
    shot('r_family', t81, 'letter', fx=dict(fx, flash_in=0.3),
         back=[F.prop('mug', 340, 540, 1400, t0=st('r1', 4), enter='pop', use_t=True)])
    letter_line('r1')
    shot('r_team', first('r2') - 0.05, 'letter', fx=fx,
         back=[F.prop('chair', 300, 540, 1350, t0=first('r2') - 0.05, enter='pop', use_t=True),
               F.dots_ring(540, 1480, 400, 60, st('r2', 3), color=INKB, rad=11, use_t=True)])
    letter_line('r2')
    shot('r_board', first('r3') - 0.05, 'letter', fx=fx,
         back=[F.prop('door', 340, 540, 1400, t0=first('r3') - 0.05, enter='pop', use_t=True)])
    letter_line('r3')
    t4 = first('r4') - 0.05
    shot('r_us', t4, 'letter', fx=fx,
         girl=her(560, 1330, 3.6, anchor='face', look='ghost', ink=(0.08, 0.10, 0.18), opacity=0.6, dof=1.0,
                  vignette=(560, 1350, 380, 500), t0=t4 + 0.2, fade=1.0, sway=0.5))
    letter_line('r4')
    SHOTS[-1].over_.append(F.cross_out(L_('r4'), set(range(3, 9)), last_unit('r4', 8), color=RED, width=10))
    shot('r_flaw', first('r5') - 0.05, 'letter', fx=fx,
         back=[F.prop('halo', 420, 540, 1300, t0=first('r5'), enter='pop', use_t=True)],
         over=[F.big('X', 'Anton', 560, 540, 1300, RED, t0=st('r5', 5), enter='slam', alpha=0.85)])
    letter_line('r5')
    shot('r_law', first('r6') - 0.05, 'letter', fx=fx,
         back=[F.prop('scale', 560, 540, 1380, t0=st('r6', 9), enter='pop', use_t=True)])
    letter_line('r6')
    shot('r_trust', first('r7') - 0.05, 'letter', fx=fx,
         back=[F.prop('gauge', 600, 540, 1360, t0=first('r7'), enter='pop', use_t=True),
               _needle(540, 1360 + 112, first('r7'), st('r7', 9) + 0.6)])
    letter_line('r7')
    # If he's wrong - show the proof / If he's not - run it back: a red light from one side, a green from the other
    t8 = first('r8') - 0.05
    red = dict(amb=(0.05, 0.02, 0.02), key=dict(color=(1.0, 0.18, 0.12), dir=(-1, 0), k=ramp(t8, 0.3, 0.2, 1.5), soft=0.35),
               rim=dict(color=(1, 0.3, 0.2), dir=(-1, 0), k=0.8, width=6), sat=0.6, wrap=0.2)
    shot('r_wrong', t8, 'void', p=dict(bg=(0.05, 0.0, 0.0)), girl=her(600, 1260, 3.4, anchor='face', **red),
         fx=dict(punch=0.02, flash_in=0.2))
    line('r8', fontset='heavy', box=(60, 160, 1020, 700), colors=(WHITE, RED), shadow=(10, 10), shadow_color=INK,
         max_size=260, enter='slam')
    t9 = first('r9') - 0.05
    grn = dict(amb=(0.02, 0.05, 0.02), key=dict(color=(0.45, 1.0, 0.25), dir=(1, 0), k=ramp(t9, 0.3, 0.2, 1.4), soft=0.35),
               rim=dict(color=(0.5, 1.0, 0.3), dir=(1, 0), k=0.8, width=6), sat=0.6, wrap=0.2)
    shot('r_not', t9, 'void', p=dict(bg=(0.0, 0.04, 0.0)), girl=her(600, 1260, 3.4, anchor='face', **grn),
         fx=dict(punch=0.02, flash_in=0.2))
    line('r9', fontset='heavy', box=(60, 160, 1020, 700), colors=(WHITE, GREEN, WHITE), shadow=(10, 10), shadow_color=INK,
         max_size=260, enter='slam', exit='rewind')
    # "run it back": a short rewind of the picture before the final hook slams in
    ra = st('r9', 3) - 0.03
    rb = st('r9', 6) - 0.03
    shot('r_rew', ra, 'void', replay=True, over=[F.vhs(ra, rb, label=True)], fx=dict(grain=0.04))
    REWINDS.append((ra, rb, 3.0))
    shot('r_bring', rb, 'rally', p=dict(bg=GREEN, burst_alpha=0.35), front=[crowd_of(INK, 4, PAPER)],
         fx=dict(punch=0.04, flash_in=0.6))


def _needle(cx, cy, t0, t1):
    def f(img, tc, t, fi, env):
        if t < t0:
            return img
        u = ease_out(clamp01((t - t0) / max(0.1, t1 - t0)), 2)
        a = math.pi * (1 - 0.92 * u) + 0.03 * math.sin(t * 40) * u
        x, y = cx + 250 * math.cos(a), cy - 250 * math.sin(a)
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
    """Back in the diner. First the place on its own; then, across the table, she is standing in the booth - the
    window, the green light and (at the last line) the relit neon are behind her and light her edges."""
    table = (('flowers', 230, 300, 1130), ('candle', 70, 760, 1170))
    p = dict(green=1.0, neon=neon_outro, mugs=1, steam=0.0, table=table, candle=(760, 1040))
    across = dict(green=1.0, neon=neon_outro, mugs=0, steam=0.0, variant=1)
    fx = dict(grain=0.065, punch=0.008)
    near = F.near_table(items=(('mug', 300, 600, 1560), ('flowers', 280, 230, 1450), ('candle', 84, 880, 1500)),
                        far=1330)
    candle_glow = lambda img, tc, t, fi, env: SC.glow(img, 880, 1355, 46, AMBER, 0.9 + 0.12 * math.sin(t * 17))  # noqa: E731

    def booth(**k):
        neon_rim = lambda t: 0.9 + 0.9 * clamp01(neon_outro(t) / 3)   # noqa: E731
        d = dict(look='paint', amb=(0.50, 0.38, 0.28), key=dict(color=(1.0, 0.70, 0.40), dir=(1, 0.3), k=0.55),
                 rim=dict(color=(0.75, 0.95, 0.5), dir=(0.5, -1), k=neon_rim, width=5, omni=0.35), wrap=0.55, sat=0.85)
        d.update(k)
        return her(560, 1215, 1.28, **d)
    t98 = max(B(98), last('h2h') + 0.05)   # let the final chant finish on the rally
    shot('o_window', t98, 'diner', p=p, cam=(1.0, 1.06, 700, 520), fx=dict(fx, flash_in=0.3),
         back=[F.prop('jacket', 250, 960, 1000, swing=1.5, enter=None)])
    line('o1', fontset='mono', box=(70, 1420, 1010, 1860), colors=(CREAM, GREEN), stroke=8, stroke_color=INK,
         max_size=110, enter='type', align='left')
    shot('o_cold', first('o2') - 0.05, 'diner', p=p, cam=(1.45, 1.6, 540, 1180), fx=fx)
    line('o2', fontset='mono', box=(70, 1450, 1010, 1860), colors=(CREAM, CREAM), stroke=8, stroke_color=INK,
         max_size=120, enter='type', align='left')
    t3 = first('o3') - 0.05
    shot('o_vote', t3, 'diner', p=across, cam=(1.0, 1.03, 560, 1000), fx=fx,
         back=[F.prop('jacket', 230, 990, 980, swing=1.5, enter=None)],
         girl=booth(dof=3.0, t0=t3, fade=0.6), front=[near, candle_glow])
    line('o3', fontset='mono', box=(70, 120, 1010, 420), colors=(CREAM, AMBER), stroke=8, stroke_color=INK,
         max_size=110, enter='type', align='left')
    t4 = first('o4') - 0.05
    shot('o_us', t4, 'diner', p=across, cam=(1.03, 1.08, 560, 1000), fx=fx,
         back=[F.prop('jacket', 230, 990, 980, swing=1.5, enter=None)],
         girl=booth(dof=ramp(t4 + 0.2, 0.7, 3.0, 0.0)), front=[F.near_table(
             items=(('mug', 300, 600, 1560), ('flowers', 280, 230, 1450), ('candle', 84, 880, 1500)), far=1330, dof=2.5),
             candle_glow])
    line('o4', fontset='mono', box=(70, 120, 1010, 420), colors=(CREAM, GREEN), stroke=8, stroke_color=INK,
         max_size=110, enter='type', align='left')
    # (scratch) 先让真相回来 — : the picture rewinds once more
    ta = first('o5') - 0.05
    tb = first('o6') - 0.05
    shot('o_scratch', ta, 'diner', replay=True, over=[F.vhs(ta, tb, label=False)], fx=dict(grain=0.05))
    REWINDS.append((ta, tb, 1.6))
    line('o5', fontset='heavy', box=(60, 1400, 1020, 1800), colors=(WHITE,), stroke=10, stroke_color=INK,
         shadow=(10, 10), shadow_color=GREEN, max_size=180, enter='slam')
    # Then bring Jensen... back. : the neon behind her relights word by word and edges her in red and green
    neon_lit = dict(rim=dict(color=(1.0, 0.45, 0.5), dir=(0, -1), k=lambda t: 0.6 + 1.0 * clamp01(neon_outro(t) / 3),
                             width=6, omni=0.45))
    shot('o_neon', tb, 'diner', p=across, cam=(1.08, 1.08, 560, 1000), fx=dict(fx, flash_in=0.25),
         back=[F.prop('jacket', 230, 990, 980, swing=1.5, enter=None)],
         girl=booth(**neon_lit), front=[F.near_table(
             items=(('mug', 300, 600, 1560), ('flowers', 280, 230, 1450), ('candle', 84, 880, 1500)), far=1330, dof=2.5),
             candle_glow])
    line('o6', fontset='mono', box=(70, 1640, 1010, 1780), colors=(CREAM,), stroke=8, stroke_color=INK, max_size=90,
         enter='type', align='left', t_end=ECHO_TIMES[0] - 0.05)
    SHOTS[-1].over_.append(F.echo_words('back', ECHO_TIMES, cx=800, cy=1700, size0=150, color=GREEN, fontname='PermanentMarker'))
    # the tail: the camera pushes past her into the window; the green light stays on; credits; fade
    t_end = 262.2
    shot('o_tail', t_end, 'diner', p=dict(across, neon=3.0), cam=(1.08, 1.6, 800, 430), fx=dict(fx, punch=0.0),
         back=[F.prop('jacket', 230, 990, 980, swing=1.5, enter=None)],
         girl=booth(**neon_lit), front=[F.near_table(
             items=(('mug', 300, 600, 1560), ('flowers', 280, 230, 1450), ('candle', 84, 880, 1500)), far=1330, dof=2.5)],
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
