"""Lyric type: every sung unit is a stamp that lands on the frame at the moment it is sung.

The rule of the film: words are *printed* onto the picture the instant they are sung, like a rubber stamp
or a press - a 0.1 s overshoot, never a fade-in. A line lives until the next line is sung, then leaves the
way its section dictates (cut, fall under gravity, rewind with the record, pile up as old clippings).

Layout ("stack"): a line is broken into rows at its phrase boundaries; every row is scaled to the same width
(the justified poster stack of hip-hop flyers), capped so a two-character phrase does not become a wall.

  Line(entry, style, box, ...) -> .draw(frame, t)
"""
import functools
import math
import random

import cv2
import numpy as np
from PIL import Image, ImageDraw

import lyrics
from common import H, W, clamp01, ease_out, font

# ---- font sets ----------------------------------------------------------------------------------------
# (cjk font, latin font, latin size factor, uppercase latin)
FONTSETS = {
    'heavy': ('NotoSansSC-Black', 'Anton', 1.16, True),
    'poster': ('ZCOOLQingKe', 'Anton', 1.10, True),
    'serif': ('NotoSerifSC-Black', 'ArchivoBlack', 0.86, False),
    'mono': ('NotoSansSC-Bold', 'SpaceMono', 0.92, False),
    'hand': ('ZhiMangXing', 'PermanentMarker', 0.80, False),
    'marker': ('NotoSansSC-Black', 'PermanentMarker', 0.95, True),
}


@functools.lru_cache(maxsize=8000)
def gmask(fontname, size, text):
    """Ink mask of `text` drawn at pen (0, baseline 0). Returns (mask float32, ox, oy, advance)."""
    f = font(fontname, size)
    l, t, r, b = f.getbbox(text, anchor='ls')
    pad = 3
    w, h = r - l + 2 * pad, b - t + 2 * pad
    im = Image.new('L', (max(1, w), max(1, h)), 0)
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=f, fill=255, anchor='ls')
    return np.asarray(im, np.float32) / 255.0, l - pad, t - pad, f.getlength(text)


def unit_len(u):
    return 1.0 if u['cjk'] else max(0.9, len(u['t']) * 0.42)


def make_rows(us, min_len=3.2, max_len=8.5, rows=None):
    """Group units into rows: start from phrases, merge short neighbours, split long ones."""
    if rows is not None:   # explicit [[unit idx...], ...]
        return rows
    phrases = []
    for i, u in enumerate(us):
        if u['adlib']:
            continue
        if not phrases or phrases[-1][0] != u['phrase']:
            phrases.append((u['phrase'], []))
        phrases[-1][1].append(i)
    rows = [p[1] for p in phrases]

    def L(r):
        return sum(unit_len(us[i]) for i in r)
    out = []
    for r in rows:   # split long
        while L(r) > max_len:
            tot, acc, k = L(r), 0.0, 0
            while acc + unit_len(us[r[k]]) <= tot / 2 + 0.01 and k < len(r) - 1:
                acc += unit_len(us[r[k]])
                k += 1
            k = max(1, k)
            out.append(r[:k])
            r = r[k:]
        out.append(r)
    merged = []
    for r in out:   # merge short
        if merged and (L(r) < min_len or L(merged[-1]) < min_len) and L(merged[-1]) + L(r) <= max_len:
            merged[-1] = merged[-1] + r
        else:
            merged.append(r)
    return merged


class Glyph:
    __slots__ = ('ui', 'm', 'x', 'y', 'row', 's', 'e', 'cx', 'cy', 'adlib', 'seed')


class Line:
    """One sung line laid out in a box. `timing` is the entry dict from lyric_timing.json."""

    def __init__(self, timing, fontset='heavy', box=(60, 120, 1020, 760), valign='top', align='justify',
                 max_size=230, min_size=40, colors=((1, 1, 1),), stroke=0, stroke_color=(0, 0, 0),
                 shadow=None, shadow_color=(0, 0, 0), rows=None, gap=0.10, rot=0.0, upper=None,
                 enter='stamp', exit='cut', t_end=None, adlib_box=None, adlib_color=None, adlib_size=None,
                 size=None, hold=0.0, invert=False, seed=0, lead=0.05, keep_adlib=True, min_len=2.5, max_len=7.5, skip=()):
        self.tm = timing
        self.us = lyrics.units(timing['line'])
        if timing.get('slice'):
            a, b = timing['slice']
            self.us = self.us[a:b]
        self.times = [(u['s'], u['e']) for u in timing['units']]
        assert len(self.times) == len(self.us), (timing['id'], len(self.times), len(self.us))
        if skip:   # units not shown at all (e.g. a repeat the aligner could not place)
            keep = [k for k in range(len(self.us)) if k not in set(skip)]
            self.us = [self.us[k] for k in keep]
            self.times = [self.times[k] for k in keep]
        cjk, lat, lfac, up = FONTSETS[fontset]
        self.upper = up if upper is None else upper
        self.box = box
        self.colors = [np.asarray(c, np.float32) for c in colors]
        self.stroke, self.stroke_color = stroke, np.asarray(stroke_color, np.float32)
        self.shadow, self.shadow_color = shadow, np.asarray(shadow_color, np.float32)
        self.enter, self.exit = enter, exit
        self.rot = rot
        self.invert = invert
        self.lead = lead
        self.t0 = min(s for s, _ in self.times) - lead
        self.t_end = t_end   # set by the score: when the line leaves
        self.hold = hold
        rng = random.Random(seed + hash(timing['id']) % 1000)
        rws = make_rows(self.us, min_len, max_len, rows)

        def txt(u):
            return u['t'].upper() if (self.upper and not u['cjk']) else u['t']

        def meas(r, size):
            wsum = 0.0
            for k, i in enumerate(r):
                u = self.us[i]
                fn, sz = (cjk, size) if u['cjk'] else (lat, size * lfac)
                if k and (u['space'] or not u['cjk'] or not self.us[r[k - 1]]['cjk']):
                    wsum += sz * 0.24
                wsum += font(fn, int(sz)).getlength(txt(u))
            return wsum
        bw, bh = box[2] - box[0], box[3] - box[1]
        sizes = []
        for r in rws:
            if size:
                sizes.append(size)
            elif align == 'justify':
                w100 = meas(r, 100)
                sizes.append(min(max_size, max(min_size, 100 * bw / max(w100, 1))))
            else:
                sizes.append(None)
        if align != 'justify' and not size:
            # one size for all rows: the widest row fills the box
            s = min(max_size, min(100 * bw / max(meas(r, 100), 1) for r in rws))
            sizes = [max(min_size, s)] * len(rws)
        def build_row(r, s):
            """Glyphs of one row relative to its own baseline (y=0); returns (glyphs, ink top, ink bottom)."""
            s = int(round(s))
            wrow = meas(r, s)
            x = box[0] if align == 'left' else (box[2] - wrow if align == 'right' else (box[0] + box[2] - wrow) / 2)
            out, top, bot = [], 0.0, 0.0
            for k, i in enumerate(r):
                u = self.us[i]
                fn, sz = (cjk, s) if u['cjk'] else (lat, int(round(s * lfac)))
                if k and (u['space'] or not u['cjk'] or not self.us[r[k - 1]]['cjk']):
                    x += sz * 0.24
                m, ox, oy, adv = gmask(fn, sz, txt(u))
                out.append((i, m, x + ox, oy, x + adv / 2, s))
                top = min(top, oy + 3)
                bot = max(bot, oy + m.shape[0] - 3)
                x += adv
            return out, top, bot

        for _ in range(3):   # stack rows by their real ink extents; shrink everything if it overflows the box
            built = [build_row(r, s) for r, s in zip(rws, sizes)]
            total = sum(b - t for _, t, b in built) + sum(gap * s for s in sizes[:-1])
            if total <= bh + 1:
                break
            sizes = [s * bh / total for s in sizes]
        y = box[1] if valign == 'top' else (box[3] - total if valign == 'bottom' else (box[1] + box[3] - total) / 2)
        self.glyphs = []
        for ri, ((row, top, bot), s) in enumerate(zip(built, sizes)):
            base = y - top
            for (i, m, gx, oy, cx, s_) in row:
                g = Glyph()
                g.ui, g.m, g.x, g.y, g.row = i, m, gx, base + oy, ri
                g.s, g.e = self.times[i]
                g.cx, g.cy = cx, base - s_ * 0.4
                g.adlib = False
                g.seed = rng.random()
                self.glyphs.append(g)
            y += (bot - top) + gap * s
        # ad-libs: stamped separately (call-and-response)
        ad = [i for i, u in enumerate(self.us) if u['adlib']]
        if ad and adlib_box:
            groups = []
            for i in ad:
                if groups and i == groups[-1][-1] + 1 and self.us[i]['phrase'] == self.us[groups[-1][-1]]['phrase']:
                    groups[-1].append(i)
                else:
                    groups.append([i])
            asz = adlib_size or 150
            for gi, grp in enumerate(groups):
                bx = adlib_box[gi % len(adlib_box)]
                x, base = bx[0], bx[1] + asz * 0.88
                for i in grp:
                    u = self.us[i]
                    fn, sz = (cjk, asz) if u['cjk'] else (lat, int(asz * lfac))
                    m, ox, oy, adv = gmask(fn, sz, txt(u) + ('!' if i == grp[-1] and not u['cjk'] else ''))
                    g = Glyph()
                    g.ui, g.m, g.x, g.y, g.row = i, m, x + ox, base + oy, -1
                    g.s, g.e = self.times[i]
                    g.cx, g.cy = x + adv / 2, base - asz * 0.4
                    g.adlib = True
                    g.seed = rng.random()
                    self.glyphs.append(g)
                    x += adv + sz * 0.05
        self.adlib_color = np.asarray(adlib_color if adlib_color is not None else self.colors[0], np.float32)
        self.bbox = self._bbox()

    def _bbox(self):
        xs0 = [g.x for g in self.glyphs] + [W]
        ys0 = [g.y for g in self.glyphs] + [H]
        xs1 = [g.x + g.m.shape[1] for g in self.glyphs] + [0]
        ys1 = [g.y + g.m.shape[0] for g in self.glyphs] + [0]
        return min(xs0), min(ys0), max(xs1), max(ys1)

    def first(self):
        return min(g.s for g in self.glyphs)

    def last(self):
        return max(g.e for g in self.glyphs)

    # ---- animation ---------------------------------------------------------------------------------------
    def _state(self, g, t):
        """(alpha, scale, dx, dy, angle) of a glyph at time t, or None if invisible."""
        ts = g.s - self.lead
        if t < ts:
            return None
        u = t - ts
        a, sc, dx, dy, ang = 1.0, 1.0, 0.0, 0.0, 0.0
        if self.enter == 'stamp':
            p = ease_out(u / 0.11, 3)
            sc = 1.0 + 0.45 * (1 - p)
            ang = (g.seed - 0.5) * 14 * (1 - p)
            a = min(1.0, u / 0.035)
        elif self.enter == 'type':
            a = 1.0
        elif self.enter == 'rise':
            p = ease_out(u / 0.16, 3)
            dy = 60 * (1 - p)
            a = min(1.0, u / 0.08)
        elif self.enter == 'write':
            a = min(1.0, u / 0.18)
            dy = 10 * (1 - min(1.0, u / 0.25))
        elif self.enter == 'slam':
            p = ease_out(u / 0.08, 2)
            sc = 1.0 + 1.6 * (1 - p)
            a = min(1.0, u / 0.03)
        if self.t_end is not None and t >= self.t_end:
            v = t - self.t_end
            if self.exit == 'cut':
                return None
            if self.exit == 'fade':
                a *= max(0.0, 1 - v / 0.35)
            elif self.exit == 'fall':
                d = v - g.seed * 0.15
                if d > 0:
                    dy += 2600 * d * d + 120 * d
                    ang += (g.seed - 0.5) * 220 * d
            elif self.exit == 'rewind':
                # units vanish in reverse order of singing, quickly
                order = (g.s - self.first()) / max(0.1, self.last() - self.first())
                if v > (1 - order) * 0.28:
                    return None
            elif self.exit == 'push':
                dy -= 1400 * v * v + 400 * v
                a *= max(0.0, 1 - v / 0.4)
            elif self.exit == 'pile':
                p = min(1.0, v / 0.25)
                a *= 1 - 0.55 * p
            if a <= 0.01:
                return None
        return a, sc, dx, dy, ang

    def visible(self, t):
        return t >= self.t0 and (self.t_end is None or t < self.t_end + 2.0)

    def draw(self, img, t, kick=0.0, alpha=1.0, dx=0.0, dy=0.0):
        if not self.visible(t):
            return img
        planes = {}
        Aall = np.zeros((H, W), np.float32)
        any_ = False
        for g in self.glyphs:
            st = self._state(g, t)
            if st is None:
                continue
            a, sc, gx, gy, ang = st
            a *= alpha
            if a <= 0.01:
                continue
            ci = -1 if g.adlib else (g.row % len(self.colors))
            P = planes.get(ci)
            if P is None:
                P = planes[ci] = np.zeros((H, W), np.float32)
            ang += self.rot
            sc *= 1 + 0.04 * kick
            _paste(P, g.m, g.x + gx + dx, g.y + gy + dy, sc, ang, a, g.cx + gx + dx, g.cy + gy + dy, self.rot != 0)
            any_ = True
        if not any_:
            return img
        for P in planes.values():
            np.maximum(Aall, P, out=Aall)
        x0, y0, x1, y1 = _bounds(Aall)
        pad = int(self.stroke + (abs(self.shadow[0]) + abs(self.shadow[1]) if self.shadow else 0) + 4)
        x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
        sub = img[y0:y1, x0:x1]
        A = Aall[y0:y1, x0:x1]
        S = A
        if self.stroke > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * self.stroke + 1, 2 * self.stroke + 1))
            S = cv2.dilate(A, k)
        if self.shadow:
            sx, sy = int(self.shadow[0]), int(self.shadow[1])
            Sh = np.zeros_like(S)
            h, w = S.shape
            Sh[max(0, sy):h + min(0, sy), max(0, sx):w + min(0, sx)] = S[max(0, -sy):h - max(0, sy), max(0, -sx):w - max(0, sx)]
            _over(sub, Sh, self.shadow_color)
        if self.stroke > 0:
            _over(sub, S, self.stroke_color)
        for ci, P in planes.items():
            Pa = P[y0:y1, x0:x1]
            if self.invert and ci >= 0:
                sub[:] = sub * (1 - Pa[..., None]) + (1 - sub) * Pa[..., None]
            else:
                col = self.adlib_color if ci < 0 else self.colors[ci]
                _over(sub, Pa, col)
        return img


def _over(sub, a, col):
    a3 = a[..., None]
    sub *= (1 - a3)
    sub += a3 * col


def _bounds(A):
    ys = np.where(A.max(1) > 0)[0]
    xs = np.where(A.max(0) > 0)[0]
    if len(ys) == 0:
        return 0, 0, 1, 1
    return xs[0], ys[0], xs[-1] + 1, ys[-1] + 1


def _paste(P, m, x, y, sc, ang, a, cx, cy, about_center):
    if sc == 1.0 and abs(ang) < 0.05:
        xi, yi = int(round(x)), int(round(y))
        h, w = m.shape
        xa, ya, xb, yb = max(0, xi), max(0, yi), min(W, xi + w), min(H, yi + h)
        if xb > xa and yb > ya:
            np.maximum(P[ya:yb, xa:xb], m[ya - yi:yb - yi, xa - xi:xb - xi] * a, out=P[ya:yb, xa:xb])
        return
    h, w = m.shape
    # transform about the glyph's own centre (cx, cy in canvas coords)
    lx, ly = cx - x, cy - y
    M = cv2.getRotationMatrix2D((lx, ly), -ang, sc)
    ext = int(max(w, h) * sc * 0.75 + 8)
    x0, y0 = int(cx - ext), int(cy - ext)
    M[0, 2] += -x0 + x
    M[1, 2] += -y0 + y
    # M maps mask coords -> local coords of a (2ext x 2ext) patch at (x0, y0)
    M2 = M.copy()
    M2[0, 2] -= x
    M2[1, 2] -= y
    M2[0, 2] += x
    M2[1, 2] += y
    patch = cv2.warpAffine(m, M, (2 * ext, 2 * ext), flags=cv2.INTER_LINEAR)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + 2 * ext), min(H, y0 + 2 * ext)
    if xb > xa and yb > ya:
        np.maximum(P[ya:yb, xa:xb], patch[ya - y0:yb - y0, xa - x0:xb - x0] * a, out=P[ya:yb, xa:xb])


class Big:
    """A non-lyric graphic word (a date, a number, a stamp), positioned by its centre."""

    def __init__(self, text, fontname='Anton', size=400, cx=540, cy=600, color=(1, 1, 1), t0=0, t1=1e9,
                 enter='slam', exit='cut', rot=0.0, stroke=0, stroke_color=(0, 0, 0), outline=0, alpha=1.0,
                 shadow=None, shadow_color=(0, 0, 0), width=None):
        if width:
            f = font(fontname, 100)
            size = int(100 * width / max(1, f.getlength(text)))
        m, ox, oy, adv = gmask(fontname, int(size), text)
        if outline:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * outline + 1, 2 * outline + 1))
            m = np.clip(cv2.dilate(m, k) - cv2.erode(m, k), 0, 1)
        self.m = m
        self.w, self.h = m.shape[1], m.shape[0]
        self.cx, self.cy = cx, cy
        self.color = np.asarray(color, np.float32)
        self.t0, self.t1 = t0, t1
        self.enter, self.exit = enter, exit
        self.rot, self.alpha = rot, alpha
        self.stroke, self.stroke_color = stroke, np.asarray(stroke_color, np.float32)
        self.shadow, self.shadow_color = shadow, np.asarray(shadow_color, np.float32)

    def draw(self, img, t, sc=1.0, dx=0.0, dy=0.0, alpha=1.0):
        if t < self.t0 or t >= self.t1 + (0.4 if self.exit == 'fade' else 0):
            return img
        u = t - self.t0
        a = self.alpha * alpha
        s = sc
        if self.enter == 'slam':
            p = ease_out(u / 0.1, 2)
            s *= 1 + 0.8 * (1 - p)
            a *= min(1.0, u / 0.04)
        elif self.enter == 'fade':
            a *= min(1.0, u / 0.3)
        elif self.enter == 'stamp':
            p = ease_out(u / 0.12, 3)
            s *= 1 + 0.35 * (1 - p)
        if t >= self.t1:
            a *= max(0.0, 1 - (t - self.t1) / 0.4)
        if a <= 0.01:
            return img
        P = np.zeros((H, W), np.float32)
        x = self.cx - self.w / 2 + dx
        y = self.cy - self.h / 2 + dy
        _paste(P, self.m, x, y, s, self.rot, a, self.cx + dx, self.cy + dy, True)
        x0, y0, x1, y1 = _bounds(P)
        pad = int(self.stroke + (abs(self.shadow[0]) + abs(self.shadow[1]) if self.shadow else 0) + 4)
        x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
        sub = img[y0:y1, x0:x1]
        A = P[y0:y1, x0:x1]
        S = A
        if self.stroke:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * self.stroke + 1, 2 * self.stroke + 1))
            S = cv2.dilate(A, k)
        if self.shadow:
            sx, sy = int(self.shadow[0]), int(self.shadow[1])
            Sh = np.zeros_like(S)
            h, w = S.shape
            Sh[max(0, sy):h + min(0, sy), max(0, sx):w + min(0, sx)] = S[max(0, -sy):h - max(0, sy), max(0, -sx):w - max(0, sx)]
            _over(sub, Sh, self.shadow_color)
        if self.stroke:
            _over(sub, S, self.stroke_color)
        _over(sub, A, self.color)
        return img
