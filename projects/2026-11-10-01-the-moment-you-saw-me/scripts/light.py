"""Lyrics that exist only as light and shadow.

The rule of this version: there is a window we never see. Its light falls into every scene as a patch, the way
low light falls through a pane onto a floor or a wall, and it bends over whatever it lands on (the patch is
thrown through each shot's depth map, so it steps down stairs and wraps a shoulder). The lyrics are lettering
on that window. We never see the letters, only what they do to the light.

  first telling    the words are shadows inside a cool patch. Each is written as it is sung, and the rain on the
                   pane washes it down again.
  pre-chorus       the held notes: the shadow of the held word grows longer, as shadows do when the light gets low
  the gap          the light goes out. The two words sung alone are the first to arrive as light instead of shadow.
  chorus           no pane any more, the sun is out: every word is a patch of gold light, and rain shows only
                   where it falls through one.
  second telling   the same shadows are already there when the line starts. Each word turns from shadow to
                   lit glass at the moment it is sung: he is seeing it.
  second chorus    the two words do not stay words: their light spreads until it is the whole frame.
  the morning      real sun through the real window, and the title line left on the bed in lit glass.

Everything that flows (rivulets on the pane, the washing away, the rain in the light) runs on timeline.phi, so it
slows under the held notes and stops in the gap. The lyric text is never typed here: lines are E1..E16 by number
(0-based in code) and words by position, read from the user's sheet by lyrics.py.
"""
import math
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import lyrics
from glass import TITLEFONT, ZHFONT, font, lerp_keys, smooth, sprite
from timeline import B, GAP1, GAP2, H, REPEAT, TOTAL, W, phi, rate

FACE = 'C:/Windows/Fonts/georgiab.ttf'
TM = lyrics.timing()
RNG = np.random.default_rng(20261111)

COOL = np.array([1.0, .95, .84], np.float32)        # BGR: overcast window light
MORN = np.array([.60, .84, 1.0], np.float32)        # the same window with the sun in it
GOLD = np.array([.40, .76, 1.0], np.float32)        # a word of light

# How a patch is thrown. sh: sideways shear of low light. squash: foreshortening on a surface seen at a glancing
# angle. tl: how much the rows climb. kx, ky: how far the pattern slides per unit of depth (this is what makes it
# bend). far: (depth where the light starts to land, ramp, what is left of it on things further than that).
PRESET = {
    'ground': dict(sh=.25, squash=1.37, tl=0.0, kx=420, ky=240, far=(.12, .2, 0.0), head=.9),
    'wall': dict(sh=.22, squash=1.0, tl=.05, kx=300, ky=160, far=(.03, .14, .5), head=.4),
    'air': dict(sh=.10, squash=1.0, tl=.035, kx=70, ky=40, far=(.0, .12, .75), head=0.0),
}

OPEN2 = GAP2[1]
# how dark the rest of the frame is while the window light is the light
AMB = [(0, 1.0), (B(3) + .6, 1.0), (B(3) + 3.4, .70), (GAP1[0] - .14, .70), (GAP1[0] + .04, .42), (GAP1[1] - .03, .42), (GAP1[1] + .07, 1.0),
       (B(27) + .6, 1.0), (B(27) + 3.2, .70), (GAP2[0] - .14, .70), (GAP2[0] + .04, .42), (GAP2[1] - .03, .42), (GAP2[1] + .07, 1.0),
       (B(51, 3) + .6, 1.0), (B(51, 3) + 3.0, .84), (TOTAL, .84)]
# the pane itself: on through the verses, out in the gap, gone in the choruses
PANE = [(0, 1.0), (GAP1[0] - .14, 1.0), (GAP1[0] + .02, 0.0), (B(26), 0.0), (B(26) + .1, 1.0), (GAP2[0] - .14, 1.0), (GAP2[0] + .02, 0.0),
        (B(50), 0.0), (B(50) + .1, 1.0), (TOTAL, 1.0)]
WARM = [(0, 0.0), (B(13), 0.0), (GAP1[0], .5), (GAP1[1], 0.0), (B(37), 0.0), (GAP2[0], .5), (GAP2[1], 0.0), (B(50), 0.0), (B(50) + .1, 1.0),
        (TOTAL, 1.0)]

GAIN, HAZE, LIFT = 1.55, .05, .10
PEN = 3.0                       # penumbra, in pattern px


@dataclass
class Mark:
    a: np.ndarray
    x: int
    y: int
    t0: float                   # starts to appear
    dur: float                  # how long appearing takes
    t1: float                   # starts to go
    out: float                  # how long going takes
    mode: str = 'shadow'        # 'shadow': lettering that blocks the pane's light.  'light': a word of light.
    how: str = 'write'          # 'write' left to right with the voice | 'fade' | 'bloom' (light switching on)
    gone: str = 'wash'          # 'wash' down the pane with the rain | 'fade' | 'slide'
    lit: float = None           # a shadow word turns to lit glass at this time
    hold: tuple = None          # (start, seconds, factor): the shadow lengthens under a held note
    slide: float = 0
    amt: float = 1.0
    col: np.ndarray = None      # how unevenly it washes down, per column
    rim: np.ndarray = None      # the lead line left around a word of lit glass


@dataclass
class Group:
    """One line of the song: its own patch of light, thrown somewhere in the frame."""
    cx: float
    cy: float
    ax: float
    ay: float
    sh: float
    tl: float
    kx: float
    ky: float
    far: tuple
    uc: float                   # pattern coordinates of the point that lands on (cx, cy)
    vc: float
    box: tuple                  # half size on screen of the area whose depth the patch is anchored to
    base: np.ndarray = None     # the pane: glass, bars, beads of water. None for words of light with no window.
    size: tuple = (0, 0)
    block: tuple = (0, 0)       # room for the words, in pattern px
    rect: tuple = None          # the pane in pattern coordinates
    t_in: float = 0
    t_out: float = 0
    fade: tuple = (.8, .9)
    drift: tuple = (0, 0)       # screen px per second
    kshot: dict = field(default_factory=dict)       # shot id: how much less (or more) it bends in that shot
    marks: list = field(default_factory=list)
    riv: list = field(default_factory=list)


GROUPS = []
CAPTIONS = []                   # the Chinese line by each patch: (text, x, y, size, t_in, t_out, align)


def line(li, tell, rows, at, wpx, style='wall', mode='shadow', *, tw=1000, maxsize=330, pitch=1.16, big=None, how=None, gone=None,
         until=None, stay=1.4, out=1.4, keep=None, hold=None, lead=.06, t_all=None, lit=None, pre=.7, slide=0, k=1.0, drift=(0, 0),
         head=None, foot=0.0, far=None, zh=True, zh_at=None, zh_size=36, zh_until=None, zh_split=None, amt=1.0, linger=.3, bars=True,
         sh=None, squash=None, slow=None, into=None, reserve=None, kshot=None):
    """Lay out one sung line as a patch of light with its words.

    rows: the line's words grouped into rows by position.  at: where the middle of the words lands on screen.
    wpx: how wide the patch is on screen (for words of light: how wide the words are).
    until: time (first telling's clock) when the words start to go; default is `stay` after the last word.
    keep: {word: time} lets single words outlast the line.  hold: {word: (seconds, factor)} for held notes.
    t_all: every word appears at this time instead of with the voice.  lit: True turns each word to lit glass as
    it is sung (the words are then already there `pre` seconds before the line), or a list of times per word.
    into: an earlier line's Group. The words are then written on that same pane, where its words were.
    reserve: (width, height) in pattern px to keep free for later lines that will share this pane.
    """
    P = dict(PRESET[style])
    shift = tell * REPEAT
    words, tm = lyrics.EN[li], TM[li]
    keep, hold, big, slow = keep or {}, hold or {}, big or {}, slow or {}
    shadow = mode == 'shadow'
    how = how or ('write' if shadow else 'bloom')
    gone = gone or ('wash' if shadow else 'fade')
    if not shadow:
        tw = wpx
    if into is not None:
        tw = into.block[0]
    probe = 100
    gap = .28
    wid = max(sum(font(FACE, int(probe * big.get(w, 1))).getlength(words[w]) for w in r) + gap * probe * (len(r) - 1) for r in rows)
    size = int(min(maxsize, probe * tw / wid))
    if into is not None:
        units = sum(max(big.get(w, 1) for w in r) * pitch * max((hold[w][1] for w in r if w in hold), default=1.0) for r in rows)
        size = int(min(size, into.block[1] / units))
    thick = 2 if shadow else 1
    pad = thick + 14
    t_out = (until if until is not None else tm[-1][1] + stay) + shift
    # rows, in block coordinates
    laid, ry, bw = [], 0.0, 0.0
    for r in rows:
        rs = max(big.get(w, 1) for w in r)
        rw = sum(font(FACE, int(size * big.get(w, 1))).getlength(words[w]) for w in r) + gap * size * (len(r) - 1)
        laid.append((r, ry, rs, rw))
        bw = max(bw, rw)
        grow = max((hold[w][1] for w in r if w in hold), default=1.0)
        ry += size * rs * pitch * grow
    bh = ry
    if into is not None:
        g = into
        ox, oy = g.uc - bw / 2, g.vc - bh / 2
    else:
        fw, fh = (max(bw, reserve[0]), max(bh, reserve[1])) if reserve else (bw, bh)       # the room the pane is built around
        mx, my = (110, 96) if shadow else (90, 90)
        hd = (P['head'] if head is None else head) * fh if shadow else 0
        ft = foot * fh if shadow else 0
        cw, ch = int(fw + 2 * mx + 120), int(fh + 2 * my + hd + ft + 120)
        ax = (fw + 2 * mx) / wpx if shadow else 1.0
        g = Group(at[0], at[1], ax, ax * (P['squash'] if squash is None else squash), P['sh'] if sh is None else sh, P['tl'], P['kx'] * k,
                  P['ky'] * k, far or P['far'], mx + 60 + fw / 2, my + hd + 60 + fh / 2, (max(120, fw / ax * .4), max(90, fh / ax * .45)),
                  size=(cw, ch), block=(fw, fh), drift=drift, kshot=kshot or {})
        ox, oy = g.uc - bw / 2, g.vc - bh / 2
        if shadow:
            g.rect = (60, 60, cw - 60, ch - 60)
            g.base = pane(cw, ch, g.rect, (my + hd + 60) - my * .45 if hd else None, (my + hd + 60 + fh) + my * .45 if ft else None, bars)
    firsts = []
    for r, ry, rs, rw in laid:
        pen = ox + (bw - rw) / 2
        for w in r:
            s_w = int(size * big.get(w, 1))
            a, off, adv = sprite(words[w], FACE, s_w, thick)
            s, e = tm[w]
            if lit and t_all is None:
                t0 = tm[0][0] + shift - pre
            else:
                t0 = t_all + shift if t_all is not None else s + shift - lead
            dur = slow.get(w, .7 if how == 'fade' else (.16 if how == 'bloom' else min(.6, max(.22, (e - s) * .8))))
            m = Mark(a, int(pen - off), int(oy + ry + (size * rs - s_w) * .9) - pad, t0, dur, keep[w] + shift if w in keep else t_out, out,
                     mode, how, gone, amt=amt, slide=slide)
            if lit:
                m.lit = (s + shift) if lit is True else lit[w]
                m.rim = np.clip(cv2.dilate(a, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))) - a * 1.5, 0, 1)
            if w in hold:
                m.hold = (s + shift + .2, hold[w][0], hold[w][1])
            if gone == 'wash':
                n = cv2.resize(RNG.random((1, max(3, a.shape[1] // 26)), dtype=np.float32), (a.shape[1], 1), interpolation=cv2.INTER_CUBIC)[0]
                m.col = np.clip(.12 + n, .1, 1.1).astype(np.float32)
            g.marks.append(m)
            firsts.append(t0)
            pen += adv + gap * size
    t_in = min(firsts) - (pre if shadow and not lit else (.25 if shadow else 0))
    g.t_in = t_in if into is None else min(g.t_in, t_in)
    g.t_out = max(m.t1 + m.out for m in g.marks) + linger
    if shadow:
        g.riv = rivulets(g)
    if into is None:
        GROUPS.append(g)
    if zh:
        if zh_at:
            zx, zy = zh_at
        else:           # just under the patch (or under the words of light)
            dv = (g.rect[3] - g.vc if shadow else bh / 2) / g.ay
            zx, zy = g.cx - g.sh * dv, g.cy + dv + (22 if shadow else 8)
        parts = [lyrics.ZH[li]] if not zh_split else [lyrics.ZH[li][:zh_split], lyrics.ZH[li][zh_split:]]
        for i, part in enumerate(parts):
            CAPTIONS.append((part, zx, zy + int(i * zh_size * 1.6), zh_size, min(firsts) + (pre if lit and t_all is None else 0) + .15 + .25 * i,
                             (zh_until + shift if zh_until else t_out), 'c', g.drift, g.t_in))
    return g


def pane(cw, ch, rect, bar_y, bar_y2, bars):
    """The window as a pattern of light: uneven glass, the bars between the panes, beads of rain sitting on it."""
    x0, y0, x1, y1 = rect
    r = np.random.default_rng(cw * 7 + ch)
    # the light is never even: stronger toward one corner, and old glass is not flat
    yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
    fall = 1.06 - .30 * np.hypot((xx - (x0 + (x1 - x0) * .38)) / (x1 - x0), (yy - (y0 + (y1 - y0) * .55)) / (y1 - y0)) ** 1.5
    wave = cv2.resize(r.random((7, 7), dtype=np.float32), (cw, ch), interpolation=cv2.INTER_CUBIC)
    p = np.zeros((ch, cw), np.float32)
    cv2.rectangle(p, (x0, y0), (x1, y1), 1.0, -1)
    p *= fall * (.9 + .2 * wave)
    if bars:
        for fx in (.355, .69):
            x = int(x0 + (x1 - x0) * fx)
            cv2.rectangle(p, (x - 11, y0), (x + 11, y1), .08, -1)
        for by in (bar_y, bar_y2):
            if by:
                cv2.rectangle(p, (x0, int(by) - 15), (x1, int(by) + 15), .05, -1)
    drops = np.zeros((ch, cw), np.float32)
    core = np.zeros((ch, cw), np.float32)
    for _ in range(int((x1 - x0) * (y1 - y0) / 4200)):
        x, y, rad = int(r.uniform(x0, x1)), int(r.uniform(y0, y1)), int(r.uniform(4, 11) * (1.6 if r.random() < .08 else 1))
        cv2.circle(drops, (x, y), rad, float(r.uniform(.45, .8)), -1, cv2.LINE_AA)
        cv2.circle(core, (x + rad // 3, y + rad // 3), max(1, rad // 3), 1.0, -1, cv2.LINE_AA)      # each bead is a small lens
    return p * (1 - drops) + p * core * .9


def rivulets(g):
    """Rain running down this pane while it is lit, on the warped clock."""
    x0, y0, x1, y1 = g.rect
    pa, pb = phi(g.t_in - 2.5), phi(g.t_out)
    out = []
    for _ in range(int(max(4, (pb - pa) * (x1 - x0) / 300))):
        out.append((RNG.uniform(pa, pb), RNG.uniform(x0 + 10, x1 - 10), RNG.uniform(y0, y0 + (y1 - y0) * .5), RNG.uniform(260, 620),
                    RNG.uniform(5, 12), RNG.uniform(60, 110), RNG.uniform(0, 6.28), int(RNG.integers(6, 14))))
    return out


# ---------------------------------------------------------------- the score
def score():
    """Where each line's light falls. Chosen against the shot it lands on: `until` is on the first telling's clock."""
    # ---- verse and pre-chorus, first telling: shadows written with the voice and washed off by the rain.
    # The first patch is already on her floor before anyone sings: it comes from the window she is sitting at.
    line(0, 0, [[0], [1, 2]], (560, 1450), 1000, 'ground', until=18.5, out=1.1, pre=4.6, head=.6, kshot={'s03': .22})
    line(1, 0, [[0, 1], [2]], (560, 830), 860, until=21.9, big={2: 1.25}, k=.35, head=0, kshot={'s03': 0})
    line(2, 0, [[0, 1, 2], [3], [4], [5, 6, 7]], (585, 580), 760, until=27.4, out=1.1, big={3: 1.25, 4: 1.45}, head=.12, k=.3)
    g = line(3, 0, [[0], [1]], (540, 1500), 1040, 'ground', until=31.0, out=.9, reserve=(1000, 770), zh_at=(540, 1810),
             kshot={'s05': .25, 's06': .1, 's07': .45})
    line(4, 0, [[0, 1], [2, 3]], None, 0, until=34.2, out=1.1, into=g, zh_at=(540, 1810))
    line(5, 0, [[0, 1], [2, 3]], None, 0, until=41.3, into=g, zh_at=(540, 1810))
    line(6, 0, [[0], [1]], (540, 900), 800, until=48.2, hold={1: (3.0, 1.5)}, big={1: 1.4}, drift=(-9, 3))
    g = line(7, 0, [[0], [1]], (500, 1480), 940, until=53.75, out=.6, hold={1: (3.4, 1.4)}, drift=(-7, 2))
    line(8, 0, [[0, 1], [2]], None, 0, until=GAP1[0] + .2, out=.3, gone='fade', into=g)
    # ---- the same, second telling: the shadows are waiting, and each word lights as it is sung
    kw = dict(how='fade', gone='fade', lit=True, pre=1.0, out=1.3)
    line(0, 1, [[0], [1, 2]], (440, 360), 700, until=18.2, k=.3, head=0, **{**kw, 'out': .8})
    line(1, 1, [[0, 1], [2]], (560, 830), 860, until=21.9, big={2: 1.25}, k=.35, head=0, **{**kw, 'pre': .5})
    line(2, 1, [[0, 1, 2], [3], [4], [5, 6, 7]], (540, 1440), 1000, 'ground', until=27.3, big={3: 1.25, 4: 1.45}, head=.25, kshot={'s20': 0, 's21': .5}, far=(.02, .1, 0.0), zh_at=(540, 1810), **{**kw, 'out': .9, 'pre': .6})
    g = line(3, 1, [[0], [1]], (540, 1500), 1040, 'ground', until=31.0, reserve=(1000, 770), zh_at=(540, 1810),
             kshot={'s21': .5, 's22': .1, 's23': .3, 's24': .6}, **{**kw, 'out': .8, 'pre': .6})
    line(4, 1, [[0, 1], [2, 3]], None, 0, until=34.2, into=g, zh_at=(540, 1810), **{**kw, 'out': 1.0, 'pre': .5})
    line(5, 1, [[0, 1], [2, 3]], None, 0, until=41.2, into=g, zh_at=(540, 1810), **{**kw, 'pre': .8})
    line(6, 1, [[0], [1]], (540, 1000), 800, until=48.2, hold={1: (3.0, 1.5)}, big={1: 1.4}, drift=(-9, 3), kshot={'s24': .3, 's25': .12}, **kw)
    g = line(7, 1, [[0], [1]], (540, 1250), 900, until=53.75, hold={1: (3.4, 1.4)}, drift=(-7, 2), kshot={'s25': .2, 's26': .3},
             **{**kw, 'out': .6})
    line(8, 1, [[0, 1], [2]], None, 0, until=GAP1[0] + .2, into=g, **{**kw, 'out': .3, 'pre': .3})
    # ---- the gap: the two words sung alone arrive as light. First time they stay on into the sun...
    line(8, 0, [[3], [4]], (600, 900), 400, 'air', 'light', t_all=GAP1[0] + .07, until=59.2, out=1.0, zh=False, maxsize=250, k=.4)
    chorus(0)
    # ...second time their light spreads until it is the whole frame (see Light.flood)
    line(8, 1, [[3], [4]], (600, 1160), 400, 'air', 'light', t_all=GAP1[0] + .07, until=GAP1[1] + .05, out=.55, zh=False, maxsize=250, k=.4)
    chorus(1)
    # ---- the morning after: sun through the real window, the title line left on the bed in lit glass
    t = B(51, 3) + 1.2
    line(15, 0, [[0, 1, 2], [3, 4]], (540, 1690), 1010, 'ground', how='fade', gone='fade', t_all=t, lit=[t + 2.0 + .55 * i for i in range(5)],
         until=TOTAL - 4.6, out=2.4, zh=False, head=.12, linger=1.0, k=.25, far=(0.0, .05, 1.0))


def chorus(tell):
    """E10-E16 as words of light. Placed by hand against each shot: on dark, quiet areas, faces left alone."""
    P = PLACE[tell]
    L = lambda li, rows, q, **kw: line(li, tell, rows, q['at'], q['w'], 'air', 'light', maxsize=q.get('max', 170), **kw)
    q = P[9]
    L(9, q['rows'], q, until=q['until'], out=q.get('out', 1.0))
    q = P[10]       # E11: the two things she shows people go out one after the other
    L(10, q['rows'][:1], q, until=62.75, out=.8, zh=False)
    line(10, tell, q['rows'][1:], (q['at'][0] + q.get('dx', 50), q['at'][1] + q.get('dy', 170)), q['w'], 'air', 'light', until=64.3, out=.8,
         zh_until=64.6, zh_size=30, zh_split=11, zh_at=q.get('zh_at'), maxsize=q.get('max', 170))
    q = P[11]
    L(11, q['rows'], q, until=q['until'], out=.7, big=q.get('big'))
    q = P[12]       # E13 / E14: he stayed, the others walked on. The staying word stays lit; the leaving words slide away.
    L(12, q['rows'], q, until=q['until'], keep={3: q['keep']}, out=1.2, big={3: q.get('bigw', 1.7)}, linger=.2)
    q = P[13]
    L(13, q['rows'][:1], q, until=75.0, out=1.0, zh=False)
    line(13, tell, q['rows'][1:], (q['at'][0] + q.get('dx', 40), q['at'][1] + q.get('dy', 170)), q['w'], 'air', 'light', until=74.7, out=1.9,
         gone='slide', slide=q.get('slide', 520), zh_until=75.2, maxsize=q.get('max', 170))
    q = P[14]
    L(14, q['rows'], q, until=q['until'], out=1.0, big={1: 1.2}, zh_at=q.get('zh_at'))
    q = P[15]
    L(15, q['rows'], q, until=q['until'], out=q.get('out', 2.4), big=q.get('big'), slow={2: 1.2})


# Centre and width of each chorus line.
# First telling: s11 him backlit, s12 her profile, s13 wiping her cheek, s14 the two pairs of feet, s15 from behind, s16 wide.
# Second telling: s27 her face, s28 her eyes, s29 the real smile, s30 the cup, s31 side by side, s32 the gold street.
PLACE = {
    0: {9: dict(rows=[[0], [1, 2]], at=(330, 1420), w=470, until=62.2),
        10: dict(rows=[[0, 1, 2], [3, 4, 5]], at=(400, 330), w=540, zh_at=(400, 150)),
        11: dict(rows=[[0, 1], [2, 3, 4]], at=(400, 300), w=560, until=69.1, big={2: 1.15}),
        12: dict(rows=[[0, 1, 2], [3]], at=(400, 1480), w=520, until=71.4, keep=77.0),
        13: dict(rows=[[0, 1, 2], [3, 4]], at=(420, 380), w=600),
        14: dict(rows=[[0], [1]], at=(540, 560), w=720, until=78.6),
        15: dict(rows=[[0, 1], [2], [3, 4]], at=(540, 560), w=660, until=84.6, big={2: 1.2})},
    1: {9: dict(rows=[[0], [1, 2]], at=(330, 1500), w=470, until=61.2, out=.6),
        10: dict(rows=[[0, 1, 2], [3, 4, 5]], at=(370, 300), w=500, zh_at=(370, 130)),
        11: dict(rows=[[0, 1], [2, 3, 4]], at=(420, 1250), w=640, until=69.1, big={2: 1.15}),
        12: dict(rows=[[0, 1, 2], [3]], at=(400, 1620), w=520, until=71.4, keep=77.0),
        13: dict(rows=[[0, 1, 2], [3, 4]], at=(430, 150), w=540, dy=135),
        14: dict(rows=[[0], [1]], at=(540, 510), w=720, until=78.6, zh_at=(200, 720)),
        15: dict(rows=[[0, 1], [2], [3, 4]], at=(540, 520), w=660, until=84.4, big={2: 1.2}, out=3.2)},
}


def shoulder(x, k=.80):
    return np.where(x < k, x, k + (1 - k) * np.tanh((x - k) / (1 - k)))


class Light:
    def __init__(self):
        if not GROUPS:
            score()
        self.groups = GROUPS
        self.X, self.Y = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        r = np.random.default_rng(11)
        # rain crossing a word of light: streaks while it falls, beads when time stops
        self.TH = 2400
        st = np.zeros((self.TH, W), np.float32)
        bd = np.zeros((self.TH, W), np.float32)
        for _ in range(2600):
            x, y, ln, b = int(r.uniform(0, W)), int(r.uniform(0, self.TH)), int(r.uniform(24, 80)), float(r.uniform(.35, 1.0))
            cv2.line(st, (x, y), (x + 2, y + ln), b, 1, cv2.LINE_AA)
            cv2.circle(bd, (x, y), 2, b, -1, cv2.LINE_AA)
        self.streak, self.bead = cv2.GaussianBlur(st, (0, 0), .8), cv2.GaussianBlur(bd, (0, 0), .9)
        self.rad = np.hypot(self.X - W / 2, self.Y - 950)
        self._cap = {}

    # ---- one word at one moment
    def alpha(self, m, t):
        """Returns the word's mask, how far it has slid, how bright it burns, how much of it is lit glass, its envelope."""
        a = m.a
        w = a.shape[1]
        p = (t - m.t0) / m.dur
        gain, env = 1.0, 1.0
        if m.how == 'write':
            if p < 1:
                e = 60
                a = a * np.clip((smooth(p) * (w + e) - np.arange(w, dtype=np.float32)) / e, 0, 1)[None, :]
        else:
            if p < 1:
                env = smooth(p)
            if m.how == 'bloom':
                gain = 1 + .9 * math.exp(-max(0.0, t - m.t0) / .28)
        if m.hold:
            k = 1 + (m.hold[2] - 1) * smooth((t - m.hold[0]) / m.hold[1])
            if k > 1.004:
                a = cv2.resize(a, (w, int(a.shape[0] * k)), interpolation=cv2.INTER_LINEAR)
        dx = 0
        if t > m.t1:
            if m.gone == 'wash':            # the rain takes it down the pane, unevenly, on the rain's clock
                q = min(1.0, (phi(t) - phi(m.t1)) / m.out)
                D = 330 * q ** 1.5
                a2 = np.vstack([a, np.zeros((int(D) + 4, w), np.float32)])
                ys = (np.arange(a2.shape[0], dtype=np.float32)[:, None] - D * m.col[None, :]).astype(np.float32)
                xs = np.ascontiguousarray(np.broadcast_to(np.arange(w, dtype=np.float32)[None, :], ys.shape))
                a = cv2.remap(a2, xs, ys, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
                a = cv2.blur(a, (1, 1 + 2 * int(36 * q))) * (1 - smooth(q)) ** 1.3
            else:
                q = (t - m.t1) / m.out
                env *= 1 - smooth(q)
                if m.gone == 'slide':
                    dx = int(m.slide * q * q)
        lit = smooth((t - m.lit) / .4) if m.lit is not None else 0.0
        return a * (m.amt * env), dx, gain, lit, env

    @staticmethod
    def paste(canvas, a, x, y):
        h, w = a.shape
        ch, cw = canvas.shape
        x0, y0, x1, y1 = max(0, x), max(0, y), min(cw, x + w), min(ch, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        sl = canvas[y0:y1, x0:x1]
        np.maximum(sl, a[y0 - y:y1 - y, x0 - x:x1 - x], out=sl)

    def wet(self, g, t):
        k = np.zeros(g.base.shape, np.float32)
        pt = phi(t)
        y1 = g.rect[3]
        for t0, x0, ys0, v, amp, lam, ph, wd in g.riv:
            tt = pt - t0
            if tt <= 0 or tt > (y1 - ys0) / v + 3.0:
                continue
            yh = ys0 + v * tt
            ys = np.arange(max(ys0, yh - v * 3.0), min(yh, y1), 12, dtype=np.float32)
            if len(ys) < 2:
                continue
            xs = x0 + amp * np.sin(ys / lam + ph) + .4 * amp * np.sin(ys / (lam * .37) + 2.3 * ph)
            age = (yh - ys) / v
            pts = np.stack([xs, ys], 1).astype(np.int32)
            for i in range(len(pts) - 1):
                cv2.line(k, tuple(pts[i]), tuple(pts[i + 1]), float(math.exp(-age[i] / 1.1)), wd, cv2.LINE_AA)
            if yh < y1:
                cv2.circle(k, (int(xs[-1]), int(ys[-1])), wd, 1.0, -1, cv2.LINE_AA)
        return k

    def flood(self, t):
        """Second chorus: the light of the two words spreads until it is the whole frame, then is just daylight."""
        dt = t - OPEN2
        if dt <= 0 or dt > 1.7:
            return None
        r = 1700 * smooth(dt / .8) ** 1.4
        return np.clip((r - self.rad) / (60 + r * .2), 0, 1) * (1 - smooth(dt / 1.7)) ** 1.5 * .8

    # ---- small luminous type: the Chinese line, the title, the credits
    def text_sprite(self, text, size, path=ZHFONT, track=.16, wght=420):
        key = (text, size, path)
        if key not in self._cap:
            f = ImageFont.truetype(path, size)
            if path == ZHFONT:
                f.set_variation_by_axes([wght])
            tr = size * track
            w = int(sum(f.getlength(c) + tr for c in text)) + 60
            im = Image.new('L', (w, int(size * 1.7) + 40), 0)
            d = ImageDraw.Draw(im)
            x = 30
            for c in text:
                d.text((x, 20), c, font=f, fill=255)
                x += f.getlength(c) + tr
            a = np.asarray(im, np.float32) / 255
            self._cap[key] = (a, cv2.GaussianBlur(a, (0, 0), 7))
        return self._cap[key]

    def put_text(self, f, text, x, y, size, alpha, align='l', warm=0.0, **kw):
        a, sh = self.text_sprite(text, size, **kw)
        h, w = a.shape
        x0 = int(x - 30 if align == 'l' else (x - w / 2 if align == 'c' else x - w + 30))
        y0 = int(y - 20)
        x0 = max(0, min(W - w, x0))
        x1, y1 = min(W, x0 + w), min(H, y0 + h)
        if y0 < 0 or x1 <= x0 or y1 <= y0:
            return
        a, sh = a[:y1 - y0, :x1 - x0, None] * alpha, sh[:y1 - y0, :x1 - x0, None] * alpha
        col = np.array([.93, .95, .96], np.float32) * (1 - warm) + np.array([.80, .92, 1.0], np.float32) * warm
        reg = f[y0:y1, x0:x1]
        reg *= 1 - .55 * np.clip(sh * 1.7, 0, 1)
        reg[:] = reg * (1 - a * .94) + col * a * .94

    # ---- the composite
    def apply(self, f, d, t, sh=None):
        """f: the picture (BGR float). d: its depth in the same frame, 0 far .. 1 near."""
        amb, pane_on, warm = lerp_keys(AMB, t), lerp_keys(PANE, t), lerp_keys(WARM, t)
        rain = float(getattr(sh, 'rain', 0) or 0) if sh is not None else 0.0
        ds = cv2.resize(d, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
        Lp = np.zeros((H, W), np.float32)           # window light landing in the scene
        G = np.zeros((H, W), np.float32)            # words of light
        for g in self.groups:
            if not (g.t_in <= t <= g.t_out + g.fade[1]):
                continue
            cx, cy = g.cx + g.drift[0] * (t - g.t_in), g.cy + g.drift[1] * (t - g.t_in)
            bx, by = g.box
            ref = float(ds[int(max(0, cy - by) / 8):int(min(H, cy + by) / 8) + 1, int(max(0, cx - bx) / 8):int(min(W, cx + bx) / 8) + 1].mean())
            xs, ys, dd = self.X - cx, self.Y - cy, d - ref
            kk = g.kshot.get(getattr(sh, 'id', ''), 1.0)
            mapx = g.ax * (xs + g.sh * ys) + g.kx * kk * dd + g.uc
            mapy = g.ay * (ys + g.tl * xs) + g.ky * kk * dd + g.vc
            f0, f1, f2 = g.far
            far = f2 + (1 - f2) * np.clip((d - f0) / f1, 0, 1)
            S = np.zeros((g.size[1], g.size[0]), np.float32)
            Gc = None
            for m in g.marks:
                if t < m.t0 or t > m.t1 + m.out:
                    continue
                a, dx, gain, lit, env = self.alpha(m, t)
                if m.mode == 'shadow':
                    self.paste(S, a * (1 - lit), m.x, m.y)
                    if lit > 0:
                        self.paste(S, m.rim * (lit * env * .8), m.x, m.y)
                        if Gc is None:
                            Gc = np.zeros_like(S)
                        self.paste(Gc, a * lit, m.x, m.y)
                else:
                    if Gc is None:
                        Gc = np.zeros_like(S)
                    self.paste(Gc, a * gain, m.x + dx, m.y)
            env_g = 1.0
            if g.base is not None:
                env_g = smooth((t - g.t_in) / g.fade[0]) * (1 - smooth((t - g.t_out) / g.fade[1])) * pane_on
                if env_g > .004:
                    P = g.base * (1 - .94 * S) * (1 - .6 * np.clip(self.wet(g, t), 0, 1))
                    P = cv2.GaussianBlur(P, (0, 0), PEN)
                    Lp = np.maximum(Lp, cv2.remap(P, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0) * far * env_g)
            if Gc is not None and env_g > .004:
                G += cv2.remap(cv2.GaussianBlur(Gc, (0, 0), 1.5), mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0) \
                    * far * env_g
        fl = self.flood(t)

        small = cv2.resize(f, (W // 12, H // 12), interpolation=cv2.INTER_AREA)
        lb = np.clip(cv2.resize(cv2.GaussianBlur(small, (0, 0), 4).mean(2), (W, H), interpolation=cv2.INTER_LINEAR), 0, 1)
        out = f * amb
        lit_any = np.zeros((H, W), np.float32)
        if Lp.max() > .004:
            tint = COOL * (1 - warm) + MORN * warm
            l3 = Lp[..., None]
            out = out + (f * (GAIN * (1 - .72 * lb))[..., None] + HAZE + (LIFT * (1 - lb) ** 2)[..., None]) * l3 * tint
            lit_any = Lp
        if G.max() > .004 or fl is not None:
            Gn = np.clip(G, 0, 1)
            # a word of light needs the light around it to be a little less: the shade of whatever it came through
            halo = cv2.resize(cv2.GaussianBlur(cv2.resize(Gn, (W // 8, H // 8), interpolation=cv2.INTER_AREA), (0, 0), 8), (W, H),
                              interpolation=cv2.INTER_LINEAR)
            shade = np.clip(halo * 2.4, 0, 1) * (1 - Gn)
            out = out * (1 - ((.20 + .34 * lb) * shade)[..., None])
            if fl is not None:
                G = G + fl
            g3 = np.clip(G, 0, 2.0)[..., None]
            out = out + (f * 1.4 + .09 + (.20 * (1 - lb) ** 1.5)[..., None]) * g3 * GOLD
            if rain > 0:
                sp = rate(t)
                off = int(phi(t) * 1500) % self.TH
                rows = (np.arange(H) - off) % self.TH
                tex = self.streak[rows] * min(1.0, sp * 1.4) + self.bead[rows] * (1 - min(1.0, sp * 1.4))
                out = out + (tex * np.clip(G, 0, 1.4) * (.75 * min(1.0, rain + .3)))[..., None] * np.array([.75, .9, 1.0], np.float32)
            lit_any = np.maximum(lit_any, np.clip(G, 0, 1))
        if lit_any.max() > 0:
            w3 = np.clip(lit_any * 1.5, 0, 1)[..., None]
            out = out * (1 - w3) + shoulder(out) * w3

        for text, x, y, size, t_in, t_out, align, drift, tref in CAPTIONS:
            if t_in < t < t_out + 1.0:
                a = smooth((t - t_in) / .9) * (1 - smooth((t - t_out) / 1.0)) * (.9 if pane_on > .5 or amb > .9 else .0)
                self.put_text(out, text, x + drift[0] * (t - tref), y + drift[1] * (t - tref), size, a, align, warm=.4 * (amb > .9))
        self.small_print(out, t)
        return out

    def small_print(self, out, t):
        t0, t1 = B(1) + .8, B(3) - .3
        if t0 < t < t1:
            a = smooth((t - t0) / 1.4) * smooth((t1 - t) / 1.4) * .82
            self.put_text(out, 'The Moment You Saw Me', W // 2, 1150, 42, a, 'c', path=TITLEFONT, track=.12)
        t0, t1 = B(51, 3) + 1.6, TOTAL - 3.6
        if t0 < t < t1:
            a = smooth((t - t0) / 1.6) * smooth((t1 - t) / 1.6) * .8
            y = 1000
            for k, v in lyrics.CREDITS:
                self.put_text(out, f'{k}  {v}', 96, y, 29, a, 'l', warm=.3, track=.18, wght=400)
                y += 52
