"""The pane of glass between us and the story, and the lyrics written on it.

The whole lyric film runs on one rule: the glass is fogged, and the words are finger-writing on it. Where a
letter is, the fog is wiped, so the only sharp view of her is through the words. Twice the glass clears (a
sleeve wipe at the first chorus, the title words opening outward at the second) and the polarity flips:
the picture is clear and the words are what mist is left, lit by the sun.

  first telling    each line is written as it is sung, drips, and fogs over again: nobody is meant to read it
  second telling   the fog comes back and the same handwriting comes back with it, in the same places, the way
                   old finger marks do on a real window. This time it stays, and the verse stands as a page.

Everything that flows (drips, rivulets) runs on timeline.phi, so it slows under the held notes and stops in
the gap with the rain. The lyric text itself is never typed here: lines are E1..E16 by number (0-based in
code) and words by position, read from the user's sheet by lyrics.py.
"""
import math
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import lyrics
from timeline import B, GAP1, GAP2, H, REPEAT, TOTAL, W, phi

HAND = 'C:/Windows/Fonts/segoepr.ttf'
SERIF = 'C:/Windows/Fonts/BOD_I.TTF'
ZHFONT = 'C:/Windows/Fonts/NotoSerifSC-VF.ttf'
TITLEFONT = 'C:/Windows/Fonts/georgiai.ttf'
TM = lyrics.timing()
RNG = np.random.default_rng(20261110)


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp_keys(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, a), (t1, b) in zip(keys, keys[1:]):
        if t <= t1:
            return a + (b - a) * smooth((t - t0) / (t1 - t0))
    return keys[-1][1]


# ---------------------------------------------------------------- how much fog is on the glass
WIPE1 = GAP1[1]                 # first chorus downbeat: she wipes the pane with her sleeve
OPEN2 = GAP2[1]                 # second chorus downbeat: the title words open outward until nothing is left
FOG = [(0, 1.0), (B(13), 1.0), (GAP1[0], .86),                                        # pre-chorus: the air opens a little
       (WIPE1 + 1.0, .86), (B(23), .7), (B(25), .7), (B(27, 3), .93),                 # corners left over, then it fogs up again
       (B(37), .93), (GAP2[0], .8), (OPEN2, .8), (OPEN2 + 1.5, 0.0), (TOTAL, 0.0)]


# ---------------------------------------------------------------- sprites
_font = {}


def font(path, size):
    if (path, size) not in _font:
        _font[(path, size)] = ImageFont.truetype(path, size)
    return _font[(path, size)]


def sprite(text, path, size, thick):
    """Alpha mask of one word. Returns mask, pen offset (how far left of the pen the mask starts), advance."""
    f = font(path, size)
    l, t, r, b = f.getbbox(text)
    pad = thick + 14
    im = Image.new('L', (r - l + 2 * pad, int(size * 1.85) + 2 * pad), 0)
    ImageDraw.Draw(im).text((pad - l, pad), text, font=f, fill=255)
    a = np.asarray(im, np.float32) / 255
    if thick:
        a = cv2.dilate(a, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * thick + 1, 2 * thick + 1)))
    a = cv2.GaussianBlur(a, (0, 0), 1.4)
    return a, pad - l, f.getlength(text)


@dataclass
class Mark:
    a: np.ndarray
    x: int
    y: int
    t0: float                   # starts being written
    dur: float                  # how long the writing takes
    t1: float                   # starts to go
    out: float                  # how long going takes
    mode: str = 'clear'         # 'clear': wiped out of the fog.  'mist': left on clear glass.
    how: str = 'write'          # 'write' left to right with the voice, or 'fade' (old marks coming back)
    gone: str = 'fog'           # 'fog' over unevenly | 'slide' away | 'smear' wiped off | 'fade'
    amt: float = 1.0
    slide: float = 0
    gold: float = 0             # 0 cool mist, 1 sunlit
    drips: list = field(default_factory=list)
    noise: np.ndarray = None
    run: bool = False
    streak: np.ndarray = None


MARKS = []
CAPTIONS = []                   # the Chinese line under each English one: (text, x, y, size, t_in, t_out, align)


def line(li, tell, rows, x, y, width, mode='clear', *, maxsize=175, pitch=1.36, path=HAND, thick=None, how='write', until=None,
         stay=2.0, out=1.8, gone='fog', keep=None, slow=None, amt=1.0, align='l', drip=1.0, lead=.07, slope=0.0, gold=0.0,
         zh=True, zh_at=None, zh_size=36, zh_until=None, zh_split=None, t_all=None, slide=0, big=None, run=False):
    """Lay out one sung line as word marks.

    rows: the line's words grouped into rows by position, e.g. [[0, 1], [2, 3]].
    until: absolute time (first-telling clock) when the line starts to go; default is stay seconds after its last word.
    keep: {word: time} to let single words outlast the line.   slow: {word: seconds} writing time for held notes.
    t_all: write every word at this time instead of with the voice (marks that are already there).
    big: {word: factor} to set single words larger.
    """
    sh = tell * REPEAT
    words, tm = lyrics.EN[li], TM[li]
    keep, slow, big = keep or {}, slow or {}, big or {}
    probe = 100
    wid = max(sum(font(path, int(probe * big.get(w, 1))).getlength(words[w]) for w in r) + .3 * probe * (len(r) - 1) for r in rows)
    size = int(min(maxsize, probe * width / wid))
    th = int(round(size * (.05 if mode == 'clear' else .032))) if thick is None else thick
    t_out = (until if until is not None else tm[-1][1] + stay) + sh
    ry = y
    bottom = y
    for r in rows:
        rw = sum(font(path, int(size * big.get(w, 1))).getlength(words[w]) for w in r) + .3 * size * (len(r) - 1)
        pen = x if align == 'l' else (x - rw / 2 if align == 'c' else x - rw)
        x_row0 = pen
        rs = max(big.get(w, 1) for w in r)
        for w in r:
            s_w = int(size * big.get(w, 1))
            a, off, adv = sprite(words[w], path, s_w, int(round(th * big.get(w, 1))))
            s, e = tm[w]
            t0 = (t_all + sh if t_all is not None else s + sh - lead)
            dur = slow.get(w, min(.75, max(.24, (e - s) * .85))) if how == 'write' else slow.get(w, .9)
            jy = RNG.uniform(-5, 5) if path == HAND else 0
            m = Mark(a, int(pen - off), int(ry + (size * rs - s_w) * .9 + jy + slope * (pen - x_row0)) - th - 14, t0, dur,
                     keep[w] + sh if w in keep else t_out, out, mode, how, gone, amt, slide, gold)
            m.noise = cv2.resize(RNG.random((4, max(2, a.shape[1] // 60 + 2)), dtype=np.float32), (a.shape[1], a.shape[0]),
                                 interpolation=cv2.INTER_CUBIC)
            if gone == 'smear':
                m.streak = cv2.blur(a, (161, 1))
            if mode == 'clear' and drip > 0:
                cols = np.where(a.max(0) > .6)[0]
                for _ in range(RNG.poisson(drip * a.shape[1] / (230 if run else 170))):
                    c = int(RNG.choice(cols))
                    yb = int(np.where(a[:, c] > .5)[0].max())
                    if run:     # the line is read whole; it runs as it goes
                        m.drips.append((c, yb - 4, m.t1 - .3 + RNG.uniform(0, 1.5), RNG.uniform(350, 1500), RNG.uniform(1.4, 2.8),
                                        int(RNG.integers(5, 10)), RNG.uniform(0, 6.28)))
                    else:
                        m.drips.append((c, yb - 4, t0 + dur + RNG.uniform(.1, 2.6), RNG.uniform(60, 380), RNG.uniform(1.0, 2.4),
                                        int(RNG.integers(7, 13)), RNG.uniform(0, 6.28)))
                m.run = run
            MARKS.append(m)
            pen += adv + .3 * size
        ry += int(size * rs * pitch)
        bottom = ry
    if zh:
        zx, zy = zh_at if zh_at else (x, bottom + int(size * .30))
        parts = [lyrics.ZH[li]] if not zh_split else [lyrics.ZH[li][:zh_split], lyrics.ZH[li][zh_split:]]
        for k, part in enumerate(parts):
            CAPTIONS.append((part, zx, zy + int(k * zh_size * 1.6), zh_size, (t_all + sh if t_all is not None else tm[0][0] + sh - .1) + .25 * k,
                             (zh_until + sh if zh_until else t_out), align))
    return bottom


# ---------------------------------------------------------------- the score
def score():
    """Where and how every line appears. Times in `until`/`keep` are on the first telling's clock."""
    for tell in (0, 1):
        back = tell == 1
        # First telling: written with the voice, then it fogs over. Second telling: the same marks come back by
        # themselves and, instead of fogging over, run: their drips reach the sill and stay open (run=True).
        kw = dict(how='fade', run=True, out=2.2) if back else {}
        # ---- verse (E1-E6)
        line(0, tell, [[0], [1, 2]], 96, 300, 800, until=19.3, maxsize=215, **kw)
        line(1, tell, [[0, 1], [2]], 130, 1000, 800, until=21.9, big={2: 1.35}, **kw)
        line(2, tell, [[0, 1, 2], [3], [4], [5, 6, 7]], 96, 330, 700, until=27.6, big={3: 1.3, 4: 1.55}, **{**dict(out=1.2), **kw})
        line(3, tell, [[0], [1]], 96, 300, 780, until=31.6, keep={1: 40.4}, maxsize=215, **kw)
        line(4, tell, [[0, 1], [2, 3]], 130, 960, 780, until=34.4, **{**dict(out=1.0), **kw})
        line(5, tell, [[0, 1], [2, 3]], 130, 960, 800, until=41.3, **kw)
        # ---- pre-chorus (E7, E8): one long note each, so one long stroke each
        line(6, tell, [[0], [1]], 540, 320, 800, align='c', big={1: 1.75}, slow={1: 2.6}, until=48.4, drip=1.6, maxsize=150,
             **{**dict(out=1.6), **kw})
        line(7, tell, [[0], [1]], 540, 1000, 900, align='c', big={1: 1.3}, slow={1: 2.8}, until=GAP1[0] - .9, drip=1.4, maxsize=130,
             **{**kw, **dict(out=.9)})
    # ---- chorus, first telling. E9: three words in the fog, then the last two cut into the silence...
    line(8, 0, [[0, 1, 2]], 540, 560, 640, align='c', until=GAP1[1] - .1, out=.5, drip=.4)
    line(8, 0, [[3, 4]], 540, 800, 760, align='c', until=WIPE1, out=.35, gone='fade', drip=0, lead=.1, zh=False, maxsize=230,
         slow={3: .2, 4: .2}, t_all=GAP1[0] + .1)
    # ...and when the pane is wiped they are still there, turned inside out: mist where they were clear.
    line(8, 0, [[3, 4]], 540, 800, 760, 'mist', align='c', how='fade', t_all=WIPE1 + .12, slow={3: .5, 4: .5}, until=59.3, out=1.0,
         zh=False, maxsize=230, gold=.6)
    chorus(0)
    # ---- chorus, second telling: the same two words open outward and take the fog with them (see Glass.opening)
    line(8, 1, [[0, 1, 2]], 540, 560, 640, align='c', until=GAP1[1] - .1, out=.5, drip=.4)
    line(8, 1, [[3, 4]], 540, 800, 760, align='c', until=WIPE1 + .2, out=.3, gone='fade', drip=0, zh=False, maxsize=230,
         slow={3: .2, 4: .2}, t_all=GAP1[0] + .1)
    chorus(1)
    # ---- the morning after: the pane is clear, and the title line is still on it where a finger once wrote it,
    # the way old marks show when low sun comes through a window
    line(15, 0, [[0, 1], [2], [3, 4]], 770, 250, 330, 'mist', align='c', how='fade', t_all=B(51, 3) + 1.2, slow={0: 2.0, 1: 2.0, 2: 2.0, 3: 2.0, 4: 2.0},
         until=TOTAL - 5.0, out=2.6, gone='fade', gold=1.0, amt=.62, zh=False, maxsize=92)


def chorus(tell):
    """E10-E16 on clear glass: the words are the mist that is left. Placed by hand against each shot."""
    P = PLACE[tell]
    q = P[9]
    line(9, tell, q['rows'], *q['at'], 'mist', align=q.get('align', 'l'), until=q['until'], out=q.get('out', 1.0), gold=.7, maxsize=q.get('max', 150))
    # E11: the two things she shows people, set in a composed italic and wiped off one after the other
    q = P[10]
    line(10, tell, q['rows'][:1], *q['at'], 'mist', path=SERIF, thick=1, align=q.get('align', 'l'), until=62.75, out=.9, gone='smear',
         gold=.5, zh=False, maxsize=q.get('max', 120))
    line(10, tell, q['rows'][1:], q['at'][0] + q.get('dx', 60), q['at'][1] + q.get('dy', 150), q['at'][2], 'mist', path=SERIF, thick=1,
         align=q.get('align', 'l'), until=64.3, out=.9, gone='smear', gold=.5, zh_at=q.get('zh_at'), zh_until=64.6, zh_size=30, zh_split=11,
         maxsize=q.get('max', 120))
    # E12: what is left when those are gone, in her own uneven hand
    q = P[11]
    line(11, tell, q['rows'], *q['at'], 'mist', align=q.get('align', 'l'), until=q['until'], out=.7, gold=.8, big=q.get('big'),
         slope=-.035, maxsize=q.get('max', 170))
    # E13 / E14: he stayed, the others walked on. The staying word stays; the leaving words slide off and thin out.
    q = P[12]
    line(12, tell, q['rows'], *q['at'], 'mist', align=q.get('align', 'l'), until=q['until'], keep={3: q['keep']}, out=1.2, gold=.9,
         big={3: q.get('bigw', 1.9)}, maxsize=q.get('max', 110))
    q = P[13]
    line(13, tell, q['rows'][:1], *q['at'], 'mist', align=q.get('align', 'l'), until=75.0, out=1.0, gold=.9, zh=False, maxsize=q.get('max', 120))
    line(13, tell, q['rows'][1:], q['at'][0] + q.get('dx', 40), q['at'][1] + q.get('dy', 150), q['at'][2], 'mist', align=q.get('align', 'l'),
         until=74.7, out=1.9, gone='slide', slide=q.get('slide', 520), gold=.9, zh_at=q.get('zh_at'), zh_until=75.2, maxsize=q.get('max', 120))
    q = P[14]
    line(14, tell, q['rows'], *q['at'], 'mist', align='c', until=q['until'], out=1.0, gold=1.0, big={1: 1.25}, maxsize=q.get('max', 150))
    q = P[15]
    line(15, tell, q['rows'], *q['at'], 'mist', align='c', until=q['until'], out=q.get('out', 2.4), gold=1.0, big=q.get('big'),
         slow={2: 1.6}, maxsize=q.get('max', 170))


# x, y, width for each chorus line, chosen against the shot it lands on (dark, uncluttered areas; faces left alone).
# First telling: s11 him backlit, s12 her profile, s13 wiping her cheek, s14 the two pairs of feet, s15 from behind, s16 wide.
# Second telling: s27 her face, s28 her eyes, s29 the real smile, s30 the cup, s31 side by side, s32 the gold street.
PLACE = {
    0: {9: dict(rows=[[0], [1, 2]], at=(104, 1250, 560), until=62.2),
        10: dict(rows=[[0, 1, 2], [3, 4, 5]], at=(96, 300, 600), zh_at=(96, 640)),
        11: dict(rows=[[0, 1], [2, 3, 4]], at=(96, 1120, 800), until=69.1, big={2: 1.2}),
        12: dict(rows=[[0, 1, 2], [3]], at=(104, 1240, 560), until=71.4, keep=77.0),
        13: dict(rows=[[0, 1, 2], [3, 4]], at=(110, 330, 640), zh_at=(110, 690)),
        14: dict(rows=[[0], [1]], at=(540, 420, 760), until=78.6),
        15: dict(rows=[[0, 1], [2], [3, 4]], at=(540, 300, 700), until=84.6, big={2: 1.2})},
    1: {9: dict(rows=[[0], [1, 2]], at=(104, 1250, 560), until=61.2, out=.6),
        10: dict(rows=[[0, 1, 2], [3, 4, 5]], at=(96, 300, 600), zh_at=(96, 640)),
        11: dict(rows=[[0, 1], [2, 3, 4]], at=(96, 1020, 800), until=69.1, big={2: 1.2}),
        12: dict(rows=[[0, 1, 2], [3]], at=(104, 1240, 560), until=71.4, keep=77.0),
        13: dict(rows=[[0, 1, 2], [3, 4]], at=(110, 330, 640), zh_at=(110, 690)),
        14: dict(rows=[[0], [1]], at=(540, 420, 760), until=78.6),
        15: dict(rows=[[0, 1], [2], [3, 4]], at=(540, 300, 700), until=84.4, big={2: 1.2}, out=3.2)},
}


# ---------------------------------------------------------------- water running down the pane
def make_rivulets():
    out = []
    for a, b, per_s in ((.6, GAP1[1], .38), (B(25, 3), GAP2[1], .32), (GAP1[1], B(25, 3), .12)):
        pa, pb = phi(a), phi(b)
        for _ in range(int((pb - pa) * per_s)):
            out.append((RNG.uniform(pa, pb), RNG.uniform(30, W - 30), RNG.uniform(420, 900), RNG.uniform(3, 9), RNG.uniform(90, 160),
                        RNG.uniform(0, 6.28), int(RNG.integers(5, 12)), RNG.uniform(-.02, .02)))
    return out


class Glass:
    def __init__(self):
        if not MARKS:
            score()
        self.marks = MARKS
        self.riv = make_rivulets()
        r = np.random.default_rng(7)
        fine = cv2.GaussianBlur(r.random((H, W), dtype=np.float32), (0, 0), 1.1)
        fine = (fine - fine.min()) / (fine.max() - fine.min())
        self.tex = .92 + .08 * fine                                   # the grain of condensation
        beads = cv2.GaussianBlur((r.random((H, W), dtype=np.float32) > .99975).astype(np.float32), (0, 0), 2.0)
        self.beads = np.clip(beads * 9, 0, 1)                         # a few droplets heavy enough to be clear
        big = cv2.resize(r.random((9, 6), dtype=np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
        self.cloud = np.clip(big, 0, 1)                               # where it fogs over first
        # the sleeve: three passes across the pane, corners left alone
        self.sweeps = [((-200, 560), (360, 330), (760, 470), (1300, 300)), ((1300, 800), (760, 900), (330, 760), (-200, 940)),
                       ((-200, 1300), (380, 1180), (760, 1340), (1300, 1200)), ((1300, 1640), (760, 1740), (330, 1600), (-200, 1760))]
        self._open = None
        self._cap = {}
        self._title = None
        self._credits = None

    # ---- pieces of the clear mask
    def paste(self, canvas, a, x, y):
        h, w = a.shape
        x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        sl = canvas[y0:y1, x0:x1]
        np.maximum(sl, a[y0 - y:y1 - y, x0 - x:x1 - x], out=sl)

    def mark_alpha(self, m, t):
        a = m.a
        p = (t - m.t0) / m.dur
        w = a.shape[1]
        if m.how == 'write':
            if p < 1:
                e = 46
                a = a * np.clip((smooth(p) ** .8 * (w + e) - np.arange(w, dtype=np.float32)) / e, 0, 1)[None, :]
        elif p < 1:
            a = a * smooth(p)
        q = (t - m.t1) / m.out
        dx, env = 0, 1.0
        if q > 0:
            env = 1 - smooth(q)
            if m.gone == 'fog':
                a = a * np.clip((m.noise + .7 - 1.7 * q) / .7, 0, 1) * (1 - .45 * smooth(q))
            elif m.gone == 'slide':
                a = a * env
                dx = int(m.slide * q * q)
            elif m.gone == 'smear':
                e = 70
                front = q / .4 * (w + 2 * e) - e
                gone = np.clip((front - np.arange(w, dtype=np.float32)) / e, 0, 1)[None, :]
                a = a * (1 - gone) + m.streak * gone * .3 * (1 - smooth(q))
            else:
                a = a * env
        return a * m.amt, dx, env

    def drips(self, K, HL, m, t, env):
        for c, yb, ts, ln, tau, wd, ph in m.drips:
            tt = phi(t) - phi(ts)
            if tt <= 0:
                continue
            L = ln * (1 - math.exp(-tt / tau))
            if m.run:           # a track stays open a while, then mostly mists over
                env = max(.28, 1 - max(0.0, t - ts - 4.5) * .16)
            ys = np.arange(0, L + 1, 10, dtype=np.float32)
            pts = np.stack([m.x + c + 2.6 * np.sin(ys / 47 + ph) + 1.8 * np.sin(ys / 19 + 2 * ph), m.y + yb + ys], 1).astype(np.int32)
            cv2.polylines(K, [pts], False, float(env), wd, cv2.LINE_AA)
            tip = (int(pts[-1][0]), int(pts[-1][1]))
            if tt < tau * 3:
                cv2.circle(K, tip, int(wd * .8), float(env), -1, cv2.LINE_AA)
                cv2.circle(HL, (tip[0] - 1, tip[1] + 1), max(2, wd // 3), float(env), -1, cv2.LINE_AA)

    def wipe(self, t):
        """The sleeve wipe, as a mask of what it has cleared so far."""
        dt = t - WIPE1
        if dt <= 0:
            return None
        k = np.zeros((H // 4, W // 4), np.float32)
        for i, pts in enumerate(self.sweeps):
            p = smooth((dt - i * .13) / .28)
            if p <= 0:
                continue
            n = max(2, int(40 * p))
            u = np.linspace(0, p, n)[:, None]
            c = np.array(pts, np.float32)
            curve = ((1 - u) ** 3 * c[0] + 3 * (1 - u) ** 2 * u * c[1] + 3 * (1 - u) * u ** 2 * c[2] + u ** 3 * c[3]) / 4
            cv2.polylines(k, [curve.astype(np.int32)], False, 1.0, 150, cv2.LINE_AA)
        k = cv2.GaussianBlur(k, (0, 0), 7)
        k = cv2.resize(k, (W, H), interpolation=cv2.INTER_LINEAR)
        # ragged edge, and it fogs back over during the interlude
        k = np.clip((k - .35 + .25 * (self.cloud - .5)) / .3, 0, 1)
        back = smooth((t - B(25, 2)) / (B(28) - B(25, 2)))
        if back > 0:
            k = np.clip(k * (1 + .5 * self.cloud) - back * 1.5, 0, 1)
        return k

    def opening(self, t):
        """Second chorus: the two words of the title that were cut into the fog grow until the whole pane is clear."""
        dt = t - OPEN2
        if dt <= 0 or dt > 1.6:
            return None
        if self._open is None:
            k = np.zeros((H, W), np.float32)
            for m in self.marks:
                if m.mode == 'clear' and abs(m.t0 - (GAP2[0] + .1)) < 1e-3:
                    self.paste(k, m.a, m.x, m.y)
            self._open = cv2.distanceTransform((k < .5).astype(np.uint8), cv2.DIST_L2, 3)
        r = 1500 * smooth(dt / 1.35) ** 1.6
        return np.clip((r - self._open) / (30 + r * .12), 0, 1)

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
        x1, y1 = min(W, x0 + w), min(H, y0 + h)
        if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
            return
        a, sh = a[:y1 - y0, :x1 - x0, None] * alpha, sh[:y1 - y0, :x1 - x0, None] * alpha
        col = np.array([.93, .95, .96], np.float32) * (1 - warm) + np.array([.80, .92, 1.0], np.float32) * warm
        reg = f[y0:y1, x0:x1]
        reg *= 1 - .42 * np.clip(sh * 1.6, 0, 1)
        reg[:] = reg * (1 - a * .94) + col * a * .94

    # ---- the composite
    def apply(self, f, t, sh=None):
        fog = lerp_keys(FOG, t)
        sun = float(getattr(sh, 'sun', 0) or 0) if sh is not None else 0.0
        K = np.zeros((H, W), np.float32)            # wiped clear
        M = np.zeros((H, W), np.float32)            # mist left on clear glass
        G = np.zeros((H, W), np.float32)            # how sunlit that mist is
        HL = np.zeros((H, W), np.float32)           # beads of water catching light
        for m in self.marks:
            if t < m.t0:
                continue
            if t > m.t1 + m.out:
                if m.run and t < OPEN2 + 1.6:          # the word has gone; the tracks it left stay open
                    self.drips(K, HL, m, t, 1.0)
                continue
            a, dx, env = self.mark_alpha(m, t)
            if m.mode == 'clear':
                self.paste(K, a, m.x + dx, m.y)
                self.drips(K, HL, m, t, 1.0 if m.run else env)
            else:
                self.paste(M, a, m.x + dx, m.y)
                if m.gold:
                    self.paste(G, a * m.gold, m.x + dx, m.y)
        if fog > .02:
            pt = phi(t)
            for t0, x0, v, amp, lam, ph, wd, drift in self.riv:
                tt = pt - t0
                if tt <= 0 or tt > (H + 80) / v + 3.2:
                    continue
                yh = -40 + v * tt
                ys = np.arange(max(-40, yh - v * 3.2), min(yh, H + 40), 16, dtype=np.float32)
                if len(ys) < 2:
                    continue
                xs = x0 + amp * np.sin(ys / lam + ph) + .4 * amp * np.sin(ys / (lam * .37) + 2.3 * ph) + drift * ys
                age = (yh - ys) / v
                pts = np.stack([xs, ys], 1).astype(np.int32)
                for i in range(len(pts) - 1):
                    cv2.line(K, tuple(pts[i]), tuple(pts[i + 1]), float(math.exp(-age[i] / .8)), wd, cv2.LINE_AA)
                if yh < H + 20:
                    cv2.circle(K, (int(xs[-1]), int(ys[-1])), wd, 1.0, -1, cv2.LINE_AA)
                    cv2.circle(HL, (int(xs[-1]) - 1, int(ys[-1]) + 2), max(2, wd // 2), 1.0, -1, cv2.LINE_AA)
        wk = self.wipe(t)
        if wk is not None:
            np.maximum(K, wk, out=K)
        ok = self.opening(t)
        if ok is not None:
            np.maximum(K, ok, out=K)
        K = np.maximum(K, self.beads * .7)

        A = np.clip(fog * (1 - K) * self.tex * (.9 + .1 * self.cloud), 0, 1)
        # What fogged glass does to a picture: it turns it into soft patches of colour and lifts it toward a milky
        # grey, because the fog scatters whatever light is behind it. Sharpness and depth survive only in the strokes.
        small = cv2.resize(f, (W // 12, H // 12), interpolation=cv2.INTER_AREA)
        bl = cv2.resize(cv2.GaussianBlur(small, (0, 0), 3.4), (W, H), interpolation=cv2.INTER_CUBIC)
        lf = cv2.resize(cv2.GaussianBlur(small, (0, 0), 14), (W, H), interpolation=cv2.INTER_CUBIC)
        lum = float(lf.mean())
        milk = (np.array([.74, .71, .68], np.float32) * (1 - sun) + np.array([.66, .78, .90], np.float32) * sun) * min(.84, .50 + 1.1 * lum)
        fogged = bl * .40 + lf * .14 + milk * .46
        clear = np.clip((f - .5) * 1.06 + .5, 0, 1) * .94                    # through a wiped stroke: a touch deeper than bare
        w_clear = np.clip(fog * 4, 0, 1)                                     # with no fog on the pane the picture is itself
        clear = clear * w_clear + f * (1 - w_clear)
        out = clear * (1 - A[..., None]) + fogged * A[..., None]
        if M.max() > 0:
            M = cv2.GaussianBlur(M, (0, 0), 1.8)
            Am = np.clip(M * (1 - A) * (.74 + .26 * (self.tex - .92) / .08) * 1.12, 0, 1)
            warm = np.array([.70, .86, 1.0], np.float32)
            cool = np.array([.95, .95, .94], np.float32)
            g = G[..., None]
            mist = bl * .30 + (cool * (1 - g) + warm * g) * (.70 + .12 * g)
            halo = np.clip(cv2.GaussianBlur(M, (0, 0), 20) * 1.35 - M, 0, 1)
            out = out * (1 - (.26 + .42 * np.clip(bl.mean(2), 0, 1)) [..., None] * halo[..., None])     # more where the picture is bright
            out = out * (1 - .88 * Am[..., None]) + mist * .88 * Am[..., None]
            A = np.maximum(A, Am)
        # the ridge of water pushed to the lower edge of every stroke, and a bead at the tip of every drip
        E = cv2.GaussianBlur(A, (0, 0), 1.2)
        gx = np.roll(E, 2, 1) - np.roll(E, -2, 1)
        d = np.roll(E, 2, 0) - np.roll(E, -2, 0)
        rim = np.clip(np.sqrt(gx * gx + d * d) * 1.5, 0, 1)
        out = out * (1 - .28 * rim[..., None])
        d = d * np.clip(1.2 - rim, 0, 1) + d
        out = out + (np.clip(-d, 0, 1) * .16)[..., None] - (np.clip(d, 0, 1) * .10)[..., None] * out
        out = out + (cv2.GaussianBlur(HL, (0, 0), 1.3) * .3)[..., None]

        # Chinese under each line
        for text, x, y, size, t_in, t_out, align in CAPTIONS:
            if t_in < t < t_out + 1.0:
                a = smooth((t - t_in) / .9) * (1 - smooth((t - t_out) / 1.0))
                self.put_text(out, text, x, y, size, a, align, warm=.5 * sun)
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
            y = 1160
            for k, v in lyrics.CREDITS:
                self.put_text(out, f'{k}  {v}', 96, y, 29, a, 'l', warm=.3, track=.18, wght=400)
                y += 52
