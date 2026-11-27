#!/usr/bin/env python3
"""The lyric layer. Rule (storyboard.md section 3): every sung character is a rune, and runes are what this land
is made of. How a rune exists depends on who carves it:

  carve   the teller's rap: a white-hot point cuts each character into the surface of the scene from left to right
          while it is sung (sparks fly off the point), the groove glows gold, and after the line it cools through
          orange to a dark scar. Projected through the depth map so it folds over the terrain.
  light   the sung lines (chorus, the welcome): the crystal's teal light standing in the air, refracting the scene
          behind it, breathing with the kick; when the line is done it shatters into shards.
  stamp   shouts and the countdown: one word slammed in on its beat, with a shock ring.
  neon    the bridge's twin cities: the outline of each character as a glass tube, flickering on.
  ember   the outro: carved, but the fire is low and cools fast; 'memory' is the same, faded to sepia.
  name    the name in the stop of pre-chorus 1: carved white-hot into a frozen world, then on the chorus downbeat
          it turns to crystal light and shatters.

Lines are typeset one at a time in rows of 2-5 characters at the line's own phrase breaks, the widest row filling
82 % of the safe width. Safe area (1080x1920 output): x 50..940, y 220..1500.
No lyric text is stored anywhere but the user's file; this module reads it through lyrics.py.
"""
import functools
import itertools
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import look  # noqa: E402
import lyrics  # noqa: E402
import timeline as T  # noqa: E402
from look import W, H, XX, YY  # noqa: E402

ROOT = look.ROOT
FONTS = {'serif': os.path.join(ROOT, 'work', 'fonts', 'NotoSerifSC-VF.ttf'),
         'sans': os.path.join(ROOT, 'work', 'fonts', 'NotoSansSC-VF.ttf')}
SAFE_X0, SAFE_X1, SAFE_Y0, SAFE_Y1 = 50, 940, 220, 1500
SAFE_W = SAFE_X1 - SAFE_X0


NOSPLIT = ('叫出', '走近', '名字', '星空', '破晓', '战争', '轻重', '黎明', '肩上', '皮尔特沃夫', '咬着', '齿轮', '阳光', '霓虹', '毒雾', '站在', '最前方')


# ---- typesetting --------------------------------------------------------------------------------------------
def _split_phrase(units):
    n = len(units)
    if n <= 5:
        return [units]
    text = ''.join(u if len(u) == 1 else 'X' for u in units)
    try:
        import rjieba
        cuts, k = set(), 0
        for w in rjieba.cut(text):
            k += len(w)
            cuts.add(k)
    except Exception:  # noqa: BLE001
        cuts = set(range(n + 1))
    for wd in NOSPLIT:
        i = text.find(wd)
        while i >= 0:
            for j in range(i + 1, i + len(wd)):
                cuts.discard(j)
            i = text.find(wd, i + 1)
    best = None
    n0 = math.ceil(n / 5)
    for rows in (n0, n0 + 1):
        for pos in itertools.combinations(range(2, n - 1), rows - 1):
            edges = (0,) + pos + (n,)
            lens = [b - a for a, b in zip(edges, edges[1:])]
            if min(lens) < 2 or max(lens) > 5:
                continue
            cost = 0.5 * (max(lens) - min(lens)) + 3 * sum(1 for x in pos if x not in cuts) + (rows - n0)
            if best is None or cost < best[0]:
                best = (cost, edges)
    e = best[1]
    return [units[a:b] for a, b in zip(e, e[1:])]


def rows_of(units, phr):
    groups = []
    for u, p in zip(units, phr):
        if not groups or groups[-1][0] != p:
            groups.append([p, []])
        groups[-1][1].append(u)
    rows = []
    for _, g in groups:
        rows += _split_phrase(g)
    out = []
    for r in rows:
        if out and (len(r) == 1 or len(out[-1]) == 1) and len(out[-1]) + len(r) <= 5:
            out[-1] = out[-1] + r
        else:
            out.append(list(r))
    return out


@functools.lru_cache(maxsize=64)
def _font(face, px, wght):
    f = ImageFont.truetype(FONTS[face], px)
    try:
        f.set_variation_by_axes([wght])
    except Exception:  # noqa: BLE001
        pass
    return f


def glyph(u, cell, face='serif', wght=900):
    f = _font(face, int(cell * (0.90 if len(u) == 1 else 0.62)), wght)
    im = Image.new('L', (cell, cell), 0)
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = d.textbbox((0, 0), u, font=f)
    d.text(((cell - (x1 - x0)) / 2 - x0, (cell - (y1 - y0)) / 2 - y0), u, font=f, fill=255)
    return np.asarray(im, np.float32) / 255.0


class Block:
    """One line typeset: a crop mask, its origin in output px, one box per sung unit."""

    def __init__(self, units, phr, cy, face='serif', wght=900, width=0.82, cap=230, single_row=False, column_x=None, cx=None):
        if column_x is not None:
            self._column(units, cy, face, wght, cap, column_x)
            return
        self.rows = [list(units)] if single_row else rows_of(units, phr)
        nmax = max(len(r) for r in self.rows)
        cell = int(min(cap, width * SAFE_W / nmax))
        self.cell = cell
        lead = int(cell * 1.10)
        hgt = lead * (len(self.rows) - 1) + cell
        cx = (SAFE_X0 + SAFE_X1) / 2 if not cx else cx
        top = int(round(cy - hgt / 2))
        top = max(SAFE_Y0, min(SAFE_Y1 - hgt, top))
        pad = int(cell * 0.5)
        widest = nmax * cell
        self.ox = int(cx - widest / 2) - pad
        self.oy = top - pad
        self.mask = np.zeros((hgt + 2 * pad, widest + 2 * pad), np.float32)
        self.boxes = []
        for ri, r in enumerate(self.rows):
            rx = int(cx - len(r) * cell / 2)
            ry = top + ri * lead
            for u in r:
                g = glyph(u, cell, face, wght)
                x0, y0 = rx - self.ox, ry - self.oy
                self.mask[y0:y0 + cell, x0:x0 + cell] = np.maximum(self.mask[y0:y0 + cell, x0:x0 + cell], g)
                self.boxes.append((rx, ry, rx + cell, ry + cell))
                rx += cell
        self.n = len(self.boxes)
        self.bbox = (self.ox, self.oy, self.ox + self.mask.shape[1], self.oy + self.mask.shape[0])
        self.center = ((self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2)

    def _column(self, units, cy, face, wght, cell, cx):
        """One vertical column, like an inscription on a stele."""
        self.cell = cell
        lead = int(cell * 1.06)
        hgt = lead * (len(units) - 1) + cell
        top = int(round(cy - hgt / 2))
        pad = int(cell * 0.5)
        self.ox = int(cx - cell / 2) - pad
        self.oy = top - pad
        self.mask = np.zeros((hgt + 2 * pad, cell + 2 * pad), np.float32)
        self.boxes = []
        for i, u in enumerate(units):
            g = glyph(u, cell, face, wght)
            y0 = pad + i * lead
            self.mask[y0:y0 + cell, pad:pad + cell] = np.maximum(self.mask[y0:y0 + cell, pad:pad + cell], g)
            rx, ry = self.ox + pad, self.oy + y0
            self.boxes.append((rx, ry, rx + cell, ry + cell))
        self.rows = [[u] for u in units]
        self.n = len(self.boxes)
        self.bbox = (self.ox, self.oy, self.ox + self.mask.shape[1], self.oy + self.mask.shape[0])
        self.center = ((self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2)

    def crop(self, sweep=None, weights=None):
        m = self.mask
        if sweep is None and weights is None:
            return m
        m = m.copy()
        xs = np.arange(m.shape[1], dtype=np.float32) + self.ox
        for i, (x0, y0, x1, y1) in enumerate(self.boxes):
            ys, ye, xs0, xe = y0 - self.oy, y1 - self.oy, x0 - self.ox, x1 - self.ox
            w = 1.0 if weights is None else float(weights[i])
            if sweep is not None:
                f = float(sweep[i])
                if f <= 0:
                    m[ys:ye, xs0:xe] = 0
                    continue
                if f < 1:
                    edge = x0 + f * (x1 - x0) * 1.2 - 0.1 * (x1 - x0)
                    ramp = np.clip((edge - xs[xs0:xe]) / (0.10 * (x1 - x0)) + 0.5, 0, 1)
                    m[ys:ye, xs0:xe] *= ramp[None, :]
            if w != 1.0:
                m[ys:ye, xs0:xe] *= w
        return m

    def full(self, crop=None, dx=0.0, dy=0.0):
        m = self.mask if crop is None else crop
        out = np.zeros((H, W), np.float32)
        ox, oy = int(round(self.ox + dx)), int(round(self.oy + dy))
        x0, y0 = max(0, ox), max(0, oy)
        x1, y1 = min(W, ox + m.shape[1]), min(H, oy + m.shape[0])
        if x1 > x0 and y1 > y0:
            out[y0:y1, x0:x1] = m[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
        return out


# ---- which rule each sung occurrence follows ----------------------------------------------------------------
def mode_of(oid):
    sec = oid.split('|')[0]
    if oid in ('Intro|1', 'Outro|5'):
        return 'light'
    if oid == 'Pre-Chorus 1|3':
        return 'name'
    if oid == 'Outro|2':
        return 'memory'
    if oid in ('Outro|1', 'Outro|3', 'Outro|5#again'):
        return 'ember'
    if sec in ('Chorus 1', 'Chorus 2', 'Final Chorus', 'Build-Up') and oid != 'Build-Up|2':
        return 'light'
    if oid in ('Pre-Chorus 2|2', 'Pre-Chorus 2|3'):
        return 'light'
    if sec in ('Drop 1', 'Drop 2') or oid == 'Build-Up|2':
        return 'stamp'
    if sec == 'Bridge':
        return 'neon'
    return 'carve'


GOLD = np.array([1.0, 0.70, 0.28], np.float32)
WHITEHOT = np.array([1.0, 0.95, 0.82], np.float32)
EMBER = np.array([0.95, 0.30, 0.06], np.float32)
TEAL = np.array([0.30, 1.0, 0.90], np.float32)
TEAL_CORE = np.array([0.80, 1.0, 0.98], np.float32)
PINK = np.array([1.0, 0.30, 0.62], np.float32)
BRASS = np.array([1.0, 0.78, 0.40], np.float32)
SEPIA = np.array([0.95, 0.80, 0.58], np.float32)


def heat_color(h):
    """h 1 = white-hot, 0.6 gold, 0.3 ember red, 0 = cold."""
    if h >= 0.6:
        u = (h - 0.6) / 0.4
        return GOLD * (1 - u) + WHITEHOT * u
    if h >= 0.3:
        u = (h - 0.3) / 0.3
        return EMBER * (1 - u) + GOLD * u
    return EMBER * (h / 0.3)


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


class Line:
    def __init__(self, e):
        self.id = e['id']
        x = lyrics.line(e['sec'], e['n'])
        self.units = x['chars'][e['a']:e['b']]
        self.phr = x['phr'][e['a']:e['b']]
        self.s = np.array(e['start'])
        self.e = np.array(e['end'])
        self.mode = mode_of(self.id)
        self.shot = T.shot_at(self.s[0] + 0.2)
        self.summit = self.id in T.SUMMITS
        self.next_s = None

    @functools.cached_property
    def pages(self):
        """[(first unit index, Block)]: lines of more than four rows turn pages of at most three rows; the land
        list of verse 1 line 5 is one phrase per page, so each land word stands alone on its own cut."""
        rows = rows_of(self.units, self.phr)
        if self.mode in ('stamp', 'name') or (len(rows) <= 3 and self.id not in PHRASE_PAGES and self.id not in HALF_PAGES):
            return [(0, self.block)]
        if self.id in HALF_PAGES:
            cut = HALF_PAGES[self.id]
            idx = [0, cut, len(self.units)]
        elif self.id in PHRASE_PAGES:
            groups = []
            for i, p in enumerate(self.phr):
                if not groups or self.phr[groups[-1][-1]] != p:
                    groups.append([])
                groups[-1].append(i)
            idx = [g[0] for g in groups] + [len(self.units)]
        else:
            n = len(rows)
            per = [len(r) for r in rows]
            k = math.ceil(n / 3)
            sizes = [n // k + (1 if i < n % k else 0) for i in range(k)]
            idx, acc, r0 = [0], 0, 0
            for sz in sizes:
                acc += sum(per[r0:r0 + sz])
                r0 += sz
                idx.append(acc)
        out = []
        for a, b in zip(idx, idx[1:]):
            sh = T.shot_at(self.s[a] + 0.05)
            out.append((a, self._mk(self.units[a:b], self.phr[a:b], cap=280 if self.id in PHRASE_PAGES else None, shot=sh)))
        return out

    def page_at(self, t):
        cur = self.pages[0]
        for a, b in self.pages:
            if t >= self.s[a] - 0.06:
                cur = (a, b)
        return cur

    def _mk(self, units, phr, cap=None, shot=None):
        sh = shot or self.shot
        face = 'serif' if self.mode in ('carve', 'ember', 'memory', 'name') else 'sans'
        wght = 900 if self.mode != 'neon' else 700
        c = cap or (260 if self.summit else 230)
        if sh.cap:
            c = min(c, sh.cap)
        return Block(units, phr, sh.cy, face=face, wght=wght, cap=c, cx=sh.cx)

    @functools.cached_property
    def block(self):
        cy = self.shot.cy
        if self.mode == 'stamp':
            return None
        face = 'serif' if self.mode in ('carve', 'ember', 'memory', 'name') else 'sans'
        wght = 900 if self.mode != 'neon' else 700
        cap = 230
        if self.mode == 'name':
            cap, cy = 300, 760
        if self.summit:
            cap = 260
        if self.shot.cap:
            cap = min(cap, self.shot.cap)
        if self.mode == 'name':
            return Block(self.units, self.phr, 800, face=face, wght=wght, cap=250, column_x=200)
        return Block(self.units, self.phr, cy, face=face, wght=wght, cap=cap, single_row=False, cx=self.shot.cx)

    @functools.lru_cache(maxsize=16)
    def stamp_block(self, k):
        """Stamps: the chant shows each shout (two characters) alone; the countdown one number at a time; the
        drop-2 shout whole."""
        if self.id.startswith('Drop 1'):
            u, p = self.units[2 * k:2 * k + 2], [0, 0]
        elif self.id == 'Build-Up|2':
            u, p = self.units[k:k + 1], [0]
        else:
            u, p = self.units, [0] * len(self.units)
        cap = 420 if self.id == 'Build-Up|2' else (300 if self.summit else 260)
        ts = self.stamp_parts()[k][0]
        cy = T.shot_at(ts + 0.02).cy if self.id != 'Build-Up|2' else 760
        return Block(u, p, cy, face='sans', wght=420 if self.id == 'Build-Up|2' else 900,
                     width=0.92 if len(u) <= 2 else 0.86, cap=cap, single_row=len(u) <= 4)

    def stamp_parts(self):
        if self.id.startswith('Drop 1'):
            return [(self.s[2 * k], k) for k in range(len(self.units) // 2)]
        if self.id == 'Build-Up|2':
            return [(self.s[k], k) for k in range(len(self.units))]
        return [(self.s[0], 0)]

    # lifetimes
    def t_in(self):
        c = next_cut(self.s[0] - 0.12)
        if c is not None and c - self.s[0] < 0.26:
            return c
        return self.s[0] - 0.10

    def t_cut_out(self):
        """The first cut after this line's last character: a finished line does not ride onto a new shot."""
        c = next_cut(self.s[-1] + 0.25)
        return c if c is not None else 1e9

    def natural_end(self):
        tail = {'carve': 1.7, 'ember': 1.5, 'memory': 1.2, 'light': 1.1, 'neon': 0.9, 'stamp': 0.6, 'name': 0.0}[self.mode]
        if self.id == 'Outro|5#again':
            return 999.0
        if self.mode == 'name':
            return T.B(34) + 0.9
        return self.e[-1] + tail

    def t_exit(self):
        """When this line starts leaving and how long it takes."""
        nat = self.natural_end()
        dur = {'carve': 0.5, 'ember': 0.5, 'memory': 0.6, 'light': 0.6, 'neon': 0.3, 'stamp': 0.25, 'name': 0.9}[self.mode]
        if self.mode in ('light', 'neon'):
            # a sung line ends with its shot: the first cut after its last character ends it there
            c = next_cut(self.s[-1] - 0.02)
            if c is not None and c < nat and (self.next_s is None or c <= self.next_s + 0.02):
                te = max(self.s[-1] + 0.12, c - dur)
                return te, max(0.04, c - te)
        if self.next_s is not None and self.next_s - 0.04 < nat:
            # leave as the next line comes in, but never before the last character has been seen for 0.12 s
            te = min(max(self.next_s - 0.16, self.s[-1] + 0.12), self.next_s + 0.06)
            return te, max(0.08, self.next_s + 0.12 - te)
        return nat - dur, dur

    def t_out(self):
        a, d = self.t_exit()
        return a + d

    def sweep(self, t):
        d = np.clip(0.85 * (self.e - self.s), 0.10, 0.45)
        if self.mode == 'name':
            d = np.clip(0.9 * (self.e - self.s), 0.2, 0.7)
        return np.clip((t - (self.s - 0.05)) / d, 0, 1)


def _assign():
    lines = [Line(e) for e in T.LT.values()]
    lines.sort(key=lambda l: l.s[0])
    for a, b in zip(lines, lines[1:]):
        a.next_s = b.s[0]
    return lines


PHRASE_PAGES = {'Verse 1|5'}
FLAT = {'K78', 'K37', 'K46'}         # no fold through the depth map on these plates (faces, hands, a flat wall)
HALF_PAGES = {'Verse 1|2': 7}        # the two halves are sung over two shots (sea, then summit)
LINES = _assign()


_CUTS = np.array([sh.t0 for sh in T.SHOTS[1:]])


def next_cut(t):
    i = int(np.searchsorted(_CUTS, t, side='right'))
    return float(_CUTS[i]) if i < len(_CUTS) else None


def active(t):
    out = []
    for l in LINES:
        if not (l.t_in() <= t < l.t_out()):
            continue
        if t >= l.t_cut_out() and l.mode not in ('name',) and l.id != 'Outro|5#again':
            continue
        out.append(l)
    return out


# ---- helpers ------------------------------------------------------------------------------------------------
def project(mask, D, kx, ky):
    """Fold the rune onto the terrain: nearer surfaces displace it (the carving follows the depth relief)."""
    if kx == 0 and ky == 0:
        return mask
    ys, xs = np.nonzero(mask[::8, ::8] > 0.05)
    if len(ys) == 0:
        return mask
    d0 = float(np.median(D[ys * 8, xs * 8]))
    mx = (XX - kx * (D - d0)).astype(np.float32)
    my = (YY - ky * (D - d0)).astype(np.float32)
    return cv2.remap(mask, mx, my, cv2.INTER_LINEAR, borderValue=0)


def qblur(m, s):
    return look.up(cv2.GaussianBlur(look.down(m), (0, 0), max(0.5, s / look.Q)))


def glow3(m, color, s):
    return qblur(m, s)[..., None] * color


def _sparks(l, t, buf):
    """Sparks thrown off the cutting point while each character is carved (variable clock: they hang in stops)."""
    ph = T.phi(t)
    for k, (x0, y0, x1, y1) in enumerate(l.block.boxes):
        s = l.s[k] - 0.05
        d = float(np.clip(0.85 * (l.e[k] - l.s[k]), 0.10, 0.45))
        if t < s or t > s + d + 0.9:
            continue
        rng = np.random.default_rng(hash((l.id, k)) % (2 ** 32))
        n = 16 if l.mode != 'name' else 40
        birth = s + rng.uniform(0, d, n)
        vx = rng.normal(0, 140, n)
        vy = rng.uniform(-320, -60, n)
        life = rng.uniform(0.25, 0.6, n)
        yb = rng.uniform(y0 + 0.2 * (y1 - y0), y1 - 0.2 * (y1 - y0), n)
        for i in range(n):
            if birth[i] > t:
                continue
            age = ph - T.phi(birth[i])
            if age > life[i]:
                continue
            xb = x0 + (birth[i] - s) / d * (x1 - x0)
            px = xb + vx[i] * age
            py = yb[i] + vy[i] * age + 0.5 * 900 * age * age
            if 0 <= px < W and 0 <= py < H:
                buf[int(py), int(px)] += 1.0 - age / life[i]


_SHARDS = {}


def shard_set(block, crop, seed):
    """Cut the line's glyph mask into irregular Voronoi shards (computed once per line and page)."""
    key = (id(block), seed)
    if key in _SHARDS:
        return _SHARDS[key]
    from scipy.spatial import cKDTree
    hh, ww = crop.shape
    rng = np.random.default_rng(seed)
    n = max(30, int(block.n * 14))
    pts = rng.uniform([0, 0], [ww, hh], (n, 2))
    gy, gx = np.mgrid[0:hh:2, 0:ww:2]
    lab = cKDTree(pts).query(np.stack([gx.ravel(), gy.ravel()], 1))[1].reshape(gy.shape)
    lab = cv2.resize(lab.astype(np.float32), (ww, hh), interpolation=cv2.INTER_NEAREST).astype(np.int32)
    out = []
    cx, cy = block.center
    for i in range(n):
        m = (lab == i)
        if not m.any():
            continue
        piece = crop * m
        ys, xs = np.nonzero(piece > 0.04)
        if len(ys) < 12:
            continue
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        pc = piece[y0:y1, x0:x1].copy()
        gxw, gyw = block.ox + (x0 + x1) / 2, block.oy + (y0 + y1) / 2
        dx, dy = gxw - cx, gyw - cy
        nrm = math.hypot(dx, dy) + 1e-3
        sp = rng.uniform(220, 620)
        out.append(dict(x=block.ox + x0, y=block.oy + y0, pc=pc, vx=dx / nrm * sp + rng.normal(0, 90),
                        vy=dy / nrm * sp + rng.normal(-80, 90), w=rng.normal(0, 220), fade=rng.uniform(0.6, 1.0)))
    _SHARDS[key] = out
    return out


def shatter(block, crop, t, te, dur, ph_te, color, seed):
    """Break the line into crystal shards that spin outward, fall and fade (variable clock)."""
    out = np.zeros((H, W), np.float32)
    u = T.phi(t) - ph_te
    a0 = 1 - ease((t - te) / dur)
    if a0 <= 0:
        return out
    for sd in shard_set(block, block.mask, seed):
        a = a0 * (sd['fade'] if u > 0.15 else 1.0)
        pc = sd['pc']
        h_, w_ = pc.shape
        ang = sd['w'] * u
        if abs(ang) > 0.5:
            pad = int(max(h_, w_) * 0.45)
            big = cv2.copyMakeBorder(pc, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
            M = cv2.getRotationMatrix2D((big.shape[1] / 2, big.shape[0] / 2), ang, 1.0 - 0.25 * min(1.0, u / dur))
            pc = cv2.warpAffine(big, M, (big.shape[1], big.shape[0]))
            h_, w_ = pc.shape
            ox, oy = sd['x'] - pad, sd['y'] - pad
        else:
            ox, oy = sd['x'], sd['y']
        px = int(round(ox + sd['vx'] * u))
        py = int(round(oy + sd['vy'] * u + 420 * u * u))
        x0, y0, x1, y1 = max(0, px), max(0, py), min(W, px + w_), min(H, py + h_)
        if x1 <= x0 or y1 <= y0:
            continue
        sub = pc[y0 - py:y1 - py, x0 - px:x1 - px]
        out[y0:y1, x0:x1] = np.maximum(out[y0:y1, x0:x1], sub * a)
    return cv2.GaussianBlur(out, (0, 0), 0.8)


def bg_bright(img, b):
    x0, y0, x1, y1 = [int(v) for v in b.bbox]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float(np.clip((img[y0:y1:8, x0:x1:8].mean() - 0.30) / 0.40, 0, 1))


def shade(img, l, t):
    """Light does not read on a bright plate: where a rune burns, the scene around it dims, more so the brighter
    the scene is under it (measured per frame from the plate under the line's box)."""
    if l.mode == 'neon':
        return img                       # the tube darkens its own glass (and follows its flicker)
    if l.mode == 'stamp':
        parts = l.stamp_parts()
        cur = [idx for ts, idx in parts if t >= ts - 0.02]
        if not cur:
            return img
        b = l.stamp_block(cur[-1])
    else:
        b = l.block
    x0, y0, x1, y1 = [int(v) for v in b.bbox]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0:
        return img
    bg = float(img[y0:y1:8, x0:x1:8].mean())
    k = float(np.clip((bg - 0.18) * 1.8, 0, 0.80))
    if k <= 0.01:
        return img
    te, dur = l._line.t_exit() if hasattr(l, '_line') else l.t_exit()
    a = np.clip((t - (l.s[0] - 0.15)) / 0.25, 0, 1) * (1.0 - ease((t - te) / dur) if t >= te else 1.0)
    if l.mode == 'stamp':
        crop = b.mask
    elif l.mode in ('carve', 'ember', 'memory', 'name'):
        crop = b.crop(sweep=l.sweep(t))                                # follows the cutting point
    else:
        crop = b.crop(weights=np.clip((t - (l.s - 0.06)) / 0.12, 0, 1))
    m = b.full(cv2.dilate(crop, np.ones((15, 15), np.uint8)))
    halo = np.clip(qblur(m, 24) * 1.5, 0, 1)
    lum = img.mean(axis=2)
    bright = np.clip((lum - 0.30) / 0.45, 0, 1)                      # dim only what is bright; dark sky stays clean
    return img * (1 - (k * a) * halo * bright)[..., None]


# ---- the layer ----------------------------------------------------------------------------------------------
class _Page:
    def __init__(self, l, a, b):
        self.__dict__.update({k: v for k, v in l.__dict__.items() if k not in ('block', 'pages')})
        n = b.n
        self.s, self.e = l.s[a:a + n], l.e[a:a + n]
        self.units = l.units[a:a + n]
        self.block = b
        self._line = l
        self.mode, self.id, self.summit = l.mode, l.id, l.summit

    def sweep(self, t):
        if self.id in PHRASE_PAGES:
            return np.full(len(self.s), float(np.clip((t - (self.s[0] - 0.06)) / 0.04, 0, 1)))
        return Line.sweep(self, t)


def apply(img, t, D, sh):
    """img: float RGB frame after plate, grade and particles; returns it with the runes."""
    lines = active(t)
    if not lines:
        return img
    kick = T.kick(t)
    for l0 in lines:
        l = l0
        if l0.mode not in ('stamp', 'name') and len(l0.pages) > 1:
            a, b = l0.page_at(t)
            l = _Page(l0, a, b)
        img = shade(img, l, t)
        te, dur = l0.t_exit()
        alpha = 1.0 - ease((t - te) / dur) if t >= te else 1.0
        if l.mode in ('carve', 'ember', 'memory'):
            img = _carve(img, l, t, D, alpha)
        elif l.mode == 'name':
            img = _name(img, l, t, D)
        elif l.mode == 'light':
            img = _light(img, l, t, D, te, dur, kick)
        elif l.mode == 'neon':
            img = _neon(img, l, t, alpha)
        elif l.mode == 'stamp':
            img = _stamp(img, l, t, te, dur)
    return img


def _carve(img, l, t, D, alpha):
    b = l.block
    sw = l.sweep(t)
    crop = b.crop(sweep=sw)
    kx, ky = (0, 0) if T.shot_at(t).kf in FLAT else (-12, -8)
    m = project(b.full(crop), D, kx, ky)
    if m.max() <= 0:
        return img
    cool_start = l.e[-1] + 0.25
    hot = {'carve': 1.0, 'ember': 0.62, 'memory': 0.45}[l.mode]
    tau = {'carve': 0.9, 'ember': 0.6, 'memory': 0.8}[l.mode]
    h = hot if t < cool_start else hot * math.exp(-(t - cool_start) / tau)
    if l.id == 'Outro|5#again':
        h = 0.75 + 0.1 * math.sin(T.phi(t) * 3.0)       # this one does not go out
    # per-character heat: a character is white-hot the moment it is cut, then settles to the line's heat
    n = b.n
    w = np.ones(n, np.float32)
    for k in range(n):
        since = t - l.s[k]
        w[k] = 1.0 + 0.5 * math.exp(-max(0.0, since) / 0.22) if since > -0.05 else 1.0
    if l.id == 'Outro|3':      # the last three characters keep their fire
        for k in range(n - 3, n):
            w[k] = max(w[k], 0.8 / max(h, 0.05))
    mh = project(b.full(b.crop(sweep=sw, weights=w)), D, kx, ky)
    col = heat_color(min(1.0, h * 0.85))
    if l.mode == 'memory':
        col = SEPIA * h
    # a groove cut into the surface: scorched lip outside the stroke, molten core along the stroke's middle
    m3 = m[..., None]
    lip = np.clip(cv2.dilate(m, np.ones((7, 7), np.uint8)) - m, 0, 1)
    lip = cv2.GaussianBlur(lip, (0, 0), 1.5)
    core = np.clip((cv2.GaussianBlur(mh, (0, 0), 3.0) - 0.45) * 2.2, 0, 1.6)
    img = img * (1 - lip[..., None] * 0.55 * alpha)
    img = img * (1 - m3 * 0.65 * alpha) + m3 * col * 0.10 * alpha
    em = (mh * 0.55 + core * 0.75)[..., None] * col * alpha * (0.5 + 0.5 * min(1.0, h * 2))
    img = img + em
    img = img + glow3(mh, col, 8) * (0.45 * alpha * h) + glow3(mh, col, 26) * (0.22 * alpha * h)
    # the cutting point and its sparks
    if l.mode == 'carve' or (l.mode == 'ember' and l.id != 'Outro|5#again'):
        buf = np.zeros((H, W), np.float32)
        _sparks(l, t, buf)
        if buf.any():
            sp = cv2.GaussianBlur(buf, (0, 0), 1.3) * 6.0
            img = img + sp[..., None] * WHITEHOT + glow3(sp, GOLD, 8) * 0.8
    return img


def _name(img, l, t, D):
    """Pre-chorus 1: carved white-hot into the frozen world, then crystal light on the downbeat, then shards."""
    b = l.block
    tb = T.B(34)
    if t < tb:
        sw = l.sweep(t)
        crop = b.crop(sweep=sw)
        m = b.full(crop)
        img = img * (1 - m[..., None] * 0.55)
        img = img * (1 - m[..., None] * 0.75) + m[..., None] * WHITEHOT * 0.95 + glow3(m, GOLD, 9) * 0.55 + glow3(m, GOLD, 34) * 0.30
        buf = np.zeros((H, W), np.float32)
        _sparks(l, t, buf)
        if buf.any():
            sp = cv2.GaussianBlur(buf, (0, 0), 1.3) * 6.0
            img = img + sp[..., None] * WHITEHOT + glow3(sp, GOLD, 8)
        return img
    m = shatter(b, b.mask, t, tb, 0.9, T.phi(tb), TEAL, 7)
    return img + m[..., None] * TEAL_CORE * 1.2 + glow3(m, TEAL, 14) * 0.9


def _light(img, l, t, D, te, dur, kick):
    b = l.block
    ap = np.clip((t - (l.s - 0.06)) / 0.12, 0, 1)
    crop = b.crop(weights=ap)
    pulse = 0.85 + 0.35 * kick
    if l.summit:
        pulse *= 1.2
    if t >= te:
        m = shatter(b, crop, t, te, dur, T.phi(te), TEAL, hash(l.id) % 9973)
        flash = math.exp(-(t - te) / 0.08)
        return img + m[..., None] * TEAL_CORE * (pulse + 0.8 * flash) + glow3(m, TEAL, 10) * 0.9 + glow3(m, TEAL, 30) * 0.3
    m = b.full(crop)
    if m.max() <= 0:
        return img
    pulse *= 1.0 - 0.55 * bg_bright(img, b)
    # crystal: the scene behind refracted through the letter, tinted teal, a bright inner edge and a halo
    bl = cv2.GaussianBlur(look.down(m), (0, 0), 2.0)
    gy, gx = np.gradient(bl)
    dx = look.up(gx) * 160
    dy = look.up(gy) * 160
    ref = cv2.remap(img, (XX + dx).astype(np.float32), (YY + dy).astype(np.float32), cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REFLECT)
    m3 = m[..., None]
    body = ref * 0.80 + TEAL * 0.16 + 0.04
    img = img * (1 - m3 * 0.85) + body * m3 * 0.85
    er = cv2.erode(m, np.ones((7, 7), np.uint8))
    edge = cv2.GaussianBlur(np.clip(m - er, 0, 1), (0, 0), 0.8)
    img = img + edge[..., None] * TEAL_CORE * 1.0 * pulse
    # a glint sweeping across the line, like light running over a cut facet
    gx0 = b.bbox[0] + ((T.phi(t) * 0.55 + hash(l.id) % 7 * 0.13) % 1.6) * (b.bbox[2] - b.bbox[0]) - 0.3 * (b.bbox[2] - b.bbox[0])
    band = np.exp(-(((XX + 0.45 * YY) - (gx0 + 0.45 * b.center[1])) / 40.0) ** 2)
    img = img + (m * band)[..., None] * TEAL_CORE * 0.55
    # arrival flash per character
    fl = np.exp(-np.clip(t - l.s, 0, None) / 0.10) * (t >= l.s - 0.06)
    if fl.max() > 0.02:
        mf = b.full(b.crop(weights=fl))
        img = img + mf[..., None] * TEAL_CORE * 0.8
    img = img + glow3(m, TEAL, 12) * 0.55 * pulse + glow3(m, TEAL, 40) * 0.30 * pulse
    return img


def _neon(img, l, t, alpha):
    b = l.block
    # flicker on: off-on-off-on in the first 0.28 s of each character
    w = np.zeros(b.n, np.float32)
    for k in range(b.n):
        a = t - (l.s[k] - 0.04)
        if a < 0:
            continue
        if a < 0.28:
            w[k] = 1.0 if (a < 0.05 or 0.10 < a < 0.14 or a > 0.20) else 0.15
        else:
            w[k] = 1.0
    crop = b.crop(weights=w)
    m = b.full(crop)
    if m.max() <= 0:
        return img
    dil = cv2.dilate(m, np.ones((5, 5), np.uint8))
    ero = cv2.erode(m, np.ones((9, 9), np.uint8))
    tube = cv2.GaussianBlur(np.clip(dil - ero, 0, 1), (0, 0), 1.2)
    col = BRASS if l.id == 'Bridge|1' else PINK
    hum = 0.92 + 0.08 * math.sin(t * 110.0)
    lum = float(img[int(b.bbox[1]):int(b.bbox[3]):8, max(0, int(b.bbox[0])):int(b.bbox[2]):8].mean())
    back = 0.35 + 0.55 * float(np.clip((lum - 0.3) / 0.35, 0, 1))
    img = img * (1 - back * cv2.GaussianBlur(dil, (0, 0), 4)[..., None] * alpha)
    img = img + tube[..., None] * (col * 0.5 + 0.55) * alpha * hum
    img = img + glow3(tube, col, 10) * 1.1 * alpha * hum + glow3(tube, col, 36) * 0.5 * alpha
    img = img + tube[..., None] * col * 0.6 * alpha * float(np.clip((lum - 0.3) / 0.35, 0, 1))
    return img


def _stamp(img, l, t, te, dur):
    parts = l.stamp_parts()
    cur = None
    for k, (ts, idx) in enumerate(parts):
        if t >= ts - 0.02:
            cur = (ts, idx, parts[k + 1][0] if k + 1 < len(parts) else None)
    if cur is None:
        return img
    ts, idx, nxt = cur
    b = l.stamp_block(idx)
    age = max(0.0, t - ts)
    sc = 1.0 + 0.30 * math.exp(-age / 0.06)
    a = 1.0
    if nxt is not None and t >= nxt - 0.10:
        a = max(0.0, 1 - (t - (nxt - 0.10)) / 0.08)
    if t >= te:
        a *= 1.0 - ease((t - te) / dur)
    crop = b.mask
    if sc != 1.0:
        hh, ww = crop.shape
        M = cv2.getRotationMatrix2D((ww / 2, hh / 2), 0, sc)
        crop = cv2.warpAffine(crop, M, (ww, hh))
    m = b.full(crop) * a
    gold = l.id == 'Build-Up|2'
    col = GOLD if gold else TEAL
    core = WHITEHOT if gold else TEAL_CORE
    flash = math.exp(-age / 0.10)
    kb = bg_bright(img, b)
    img = img * (1 - (0.6 + 0.3 * kb) * m[..., None])
    img = img + m[..., None] * core * (0.85 + 0.45 * flash) * (1 - 0.3 * kb) \
        + glow3(m, col, 5 if gold else 8) * (0.40 + 0.5 * flash) * (1 - 0.5 * kb) + glow3(m, col, 40) * 0.22 * (1 - 0.5 * kb)
    # shock ring and a short white lift of the whole frame on the hit
    if age < 0.6:
        cx, cy = b.center
        R = 60 + 1400 * age
        r = np.hypot(XX - cx, YY - cy)
        ring = np.exp(-((r - R) / (6 + 30 * age)) ** 2) * (1 - age / 0.6) * a
        img = img + ring[..., None] * col * 0.6
        img = img + (0.10 if not l.summit else 0.22) * math.exp(-age / 0.08)
    return img
