"""Lyric layout and per-frame drawing.

A Block is one sung line laid out as a justified stack of rows (hip-hop poster style): every row is scaled so
it fills the same width, capped by a maximum size, rows stacked on their real ink bounds. Characters keep
their exact display text (quotes, dashes, question marks, call-backs); each character is revealed when the
unit (CJK character / Latin word) that owns it is sung.

Blocks live in world coordinates (on the door). Drawing goes into screen-space buffers through the camera:
  holes  openings in the door (0..1)
  back   the same openings displaced along the line of sight (for the cut-wall thickness)
  inten  light intensity behind each opening
  ink    an optional RGBA overlay for text that is printed, not cut (used by a few scenes)
"""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from common import H, W, back_out, clamp01, ease_in, ease_out, font, hash01, smooth
import lyrics

LAT = 'anton'
CJK = 'sans'


def is_cjk(c):
    o = ord(c)
    return (0x3000 <= o <= 0x303f) or (0x3400 <= o <= 0x9fff) or (0xf900 <= o <= 0xfaff) or (0xff00 <= o <= 0xffef) \
        or c in '“”‘’—…'


_gcache = {}


def gmask(ch, fname, size):
    """Mask of one character drawn at its baseline origin. Returns (mask, ox, oy): the mask's top-left
    relative to (pen x, baseline y)."""
    size = int(round(size))
    key = (ch, fname, size)
    if key in _gcache:
        return _gcache[key]
    f = font(fname, size)
    l, t, r, b = f.getbbox(ch, anchor='ls')
    w, h = max(1, r - l + 6), max(1, b - t + 6)
    im = Image.new('L', (w, h), 0)
    ImageDraw.Draw(im).text((-l + 3, -t + 3), ch, font=f, fill=255, anchor='ls')
    m = np.asarray(im, np.float32) / 255.0
    out = (m, l - 3, t - 3)
    if len(_gcache) > 6000:
        _gcache.clear()
    _gcache[key] = out
    return out


class Glyph:
    __slots__ = ('ch', 'unit', 'font', 'size', 'x', 'y', 'w', 'h', 'row', 'k')

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class Block:
    """One lyric line laid out.

    line     sheet line number
    times    list of (start, end) per unit of that line (from lyric_timing.json); None entries = unit not sung
    rows     list of lists of phrase indices (default: one phrase per row, short phrases merged)
    width    target row width in world px
    maxsize  cap on the CJK size; latin rows use LAT at lat_k times the size
    pos      (x, y) world position of the block's anchor; anchor 'c' centre, 'tl' top-left, 'bl', ...
    align    'justify' (every row same width), 'left', 'center', 'right'
    fonts    (cjk_font, latin_font)
    """

    def __init__(self, line, times, rows=None, width=900, maxsize=230, minsize=60, pos=(W / 2, H / 2),
                 anchor='c', align='justify', fonts=(CJK, LAT), lat_k=1.2, gap=0.16, chars=None, row_sizes=None,
                 row_dx=None, diag=None, row_fonts=None):
        self.line = line
        self.text = lyrics.display(line) if chars is None else chars
        self.units = lyrics.units(line) if chars is None else []
        self.owner = lyrics.owner_map(line) if chars is None else [0] * len(self.text)
        self.times = times
        ph = lyrics.phrases(line) if chars is None else [(0, len(self.text))]
        if rows is None:
            rows = [[i] for i in range(len(ph))]
        if rows and isinstance(rows[0], tuple):
            # rows given as (start, end) character spans of the display text (a block may cover part of a line)
            self.rowspans = [tuple(r) for r in rows]
        elif rows and isinstance(rows[0], str):
            # rows given as consecutive substrings of the display text (a block may cover part of a line)
            spans, p0 = [], 0
            for r in rows:
                k = self.text.find(r, p0)
                if k < 0:
                    raise ValueError(f'row {r!r} not found in line {line} after {p0}')
                spans.append((k, k + len(r)))
                p0 = k + len(r)
            self.rowspans = spans
        else:
            self.rowspans = [(ph[r[0]][0], ph[r[-1]][1]) for r in rows]
        self.fonts = fonts
        self.row_fonts = row_fonts or {}
        self.lat_k = lat_k
        self.glyphs = []
        y = 0.0
        heights = []
        layout = []
        for ri, (a, b) in enumerate(self.rowspans):
            seg = self.text[a:b]
            # measure at 100 px
            adv = []
            for c in seg:
                fn, sz = self._fs(c, 100, ri)
                adv.append(font(fn, sz).getlength(c))
            rw = sum(adv)
            if row_sizes is not None and row_sizes[ri]:
                size = row_sizes[ri]
            else:
                size = max(minsize, min(maxsize, 100 * width / max(rw, 1)))
            k = size / 100.0
            # ink bounds of this row at this size
            top, bot = 0, 0
            for c in seg:
                if c.isspace():
                    continue
                fn, sz = self._fs(c, size, ri)
                l, t, r, bb = font(fn, int(round(sz))).getbbox(c, anchor='ls')
                top, bot = min(top, t), max(bot, bb)
            if top == 0:
                top = -0.8 * size
            layout.append((a, seg, adv, k, size, top, bot, rw * k))
        self.size0 = layout[0][4] if layout else 100
        for ri, (a, seg, adv, k, size, top, bot, rwk) in enumerate(layout):
            if ri:
                y += gap * size
            base_y = y - top
            ralign = align
            if align == 'justify' and row_sizes is not None and row_sizes[ri]:
                ralign = 'center'
            if ralign == 'justify' or ralign == 'left':
                x = 0.0
            elif ralign == 'center':
                x = (width - rwk) / 2
            else:
                x = width - rwk
            if row_dx is not None and ri < len(row_dx):
                x += row_dx[ri]
            nchar = 0
            for i, c in enumerate(seg):
                ci = a + i
                if not c.isspace():
                    fn, sz = self._fs(c, size, ri)
                    m, ox, oy = gmask(c, fn, sz)
                    gy = base_y + oy
                    gx = x + ox
                    if diag is not None and diag[0] == ri:
                        gx += nchar * diag[1]
                        gy += nchar * diag[2]
                    self.glyphs.append(Glyph(ch=c, unit=self.owner[ci], font=fn, size=sz, x=gx, y=gy,
                                             w=m.shape[1], h=m.shape[0], row=ri, k=ci))
                    nchar += 1
                x += adv[i] * k
            y = base_y + bot
            heights.append(y)
        self.bw = width if align == 'justify' else max([g.x + g.w for g in self.glyphs] + [1])
        if diag is not None:
            ys = [g.y for g in self.glyphs] + [g.y + g.h for g in self.glyphs]
            y0 = min(ys)
            for g in self.glyphs:
                g.y -= y0
            y = max(ys) - y0
        self.bh = y
        ax, ay = pos
        if anchor == 'c':
            self.ox, self.oy = ax - width / 2, ay - self.bh / 2
        elif anchor == 'tl':
            self.ox, self.oy = ax, ay
        elif anchor == 'bl':
            self.ox, self.oy = ax, ay - self.bh
        elif anchor == 'tc':
            self.ox, self.oy = ax - width / 2, ay
        elif anchor == 'bc':
            self.ox, self.oy = ax - width / 2, ay - self.bh
        else:
            raise ValueError(anchor)
        self.width = width

    def _fs(self, c, size, ri=None):
        fonts = self.row_fonts.get(ri, self.fonts)
        if is_cjk(c):
            return fonts[0], size
        return fonts[1], size * self.lat_k

    def t_of(self, g):
        if self.times is None:
            return 0.0
        tt = self.times[g.unit] if g.unit < len(self.times) else None
        return tt[0] if tt else None

    def start(self):
        ts = [tt[0] for tt in self.times if tt] if self.times else [0]
        return min(ts)

    def end(self):
        ts = [tt[1] for tt in self.times if tt] if self.times else [0]
        return max(ts)

    def centre(self):
        return self.ox + self.width / 2, self.oy + self.bh / 2


def cam_xform(cam):
    """cam = (zoom, cx, cy, rot_deg): world point (cx, cy) maps to the screen centre."""
    z, cx, cy, r = cam
    a = math.radians(r)
    ca, sa = math.cos(a) * z, math.sin(a) * z
    return np.float32([[ca, -sa, W / 2 - ca * cx + sa * cy], [sa, ca, H / 2 - sa * cx - ca * cy]])


def to_screen(M, x, y):
    return M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2]


def new_buffers():
    return {'holes': np.zeros((H, W), np.float32), 'back': np.zeros((H, W), np.float32),
            'inten': np.zeros((H, W), np.float32)}


def _blit(dst, m, x, y, k):
    h, w = m.shape
    x0, y0 = int(round(x)), int(round(y))
    cx0, cy0 = max(0, x0), max(0, y0)
    cx1, cy1 = min(W, x0 + w), min(H, y0 + h)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    sub = m[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    np.maximum(dst[cy0:cy1, cx0:cx1], sub * k, out=dst[cy0:cy1, cx0:cx1])


def _xmask(m, s, rot):
    if abs(s - 1) < 0.01 and abs(rot) < 0.2:
        return m
    h, w = m.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rot, s)
    nw, nh = int(w * s + abs(math.sin(math.radians(rot))) * h * s) + 6, int(h * s + abs(math.sin(math.radians(rot))) * w * s) + 6
    M[0, 2] += nw / 2 - w / 2
    M[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(m, M, (nw, nh), flags=cv2.INTER_LINEAR)


def draw(buf, blk, t, cam, st):
    """Draw block `blk` at time t through camera `cam` with style dict `st`:
      lead      reveal this many seconds before the sung start (default 0.04)
      inn       'knock' | 'slam' | 'flick' | 'type' | 'rise' | 'fade'
      kin       knock strength (scale overshoot), default 1
      flash     intensity flash on reveal (default 1.6 extra)
      level     resting intensity (default 1)
      t_out     time the block starts leaving (None: never)
      out       'dim' | 'drop' | 'rewind' | 'slide' | 'shatter' | 'flicker' | 'blow'
      dout      leaving duration
      depth     cut-wall depth in px (default 9)
      hold      {unit index: extra level} for words that stay brighter
      pulse     array-like f(t) multiplier (e.g. heartbeat), callable
      jitter    trap triplet nudge amplitude
    """
    M = cam_xform(cam)
    z = cam[0]
    lead = st.get('lead', 0.04)
    inn = st.get('inn', 'knock')
    t_out = st.get('t_out')
    out = st.get('out', 'dim')
    dout = st.get('dout', 0.35)
    level = st.get('level', 1.0)
    flash = st.get('flash', 1.6)
    kin = st.get('kin', 1.0)
    depth = st.get('depth', 9.0) * z
    pulse = st.get('pulse')
    pv = pulse(t) if callable(pulse) else 1.0
    hold = st.get('hold', {})
    only = st.get('units')
    offx, offy = st.get('off', (0.0, 0.0))
    order = sorted(range(len(blk.glyphs)), key=lambda i: blk.glyphs[i].k)
    if only is not None:
        order = [i for i in order if blk.glyphs[i].unit in only]
    n = len(order)
    for rank, gi in enumerate(order):
        g = blk.glyphs[gi]
        ts = blk.t_of(g)
        if ts is None:
            continue
        a = t - (ts - lead)
        if a < 0:
            continue
        # ---- entering
        s, alpha, inten, dx, dy, rot = 1.0, 1.0, level, 0.0, 0.0, 0.0
        ginn = inn
        if g.unit in st.get('slam_units', ()):
            ginn = 'slam'
        if ginn == 'knock':
            s = 1 + 0.32 * kin * (1 - back_out(a / 0.16, 2.6)) if a < 0.16 else 1.0
            alpha = clamp01(a / 0.04)
            inten = level + flash * math.exp(-a / 0.12)
        elif ginn == 'slam':
            s = 1 + 1.4 * kin * (1 - ease_out(a / 0.09, 3)) if a < 0.09 else 1.0
            alpha = clamp01(a / 0.03)
            inten = level + flash * 1.3 * math.exp(-a / 0.09)
        elif ginn == 'flick':
            on = 1.0 if a > 0.18 else (1.0 if hash01(g.k, int(a * 60)) > 0.45 else 0.15)
            alpha = on
            inten = level + flash * 0.6 * math.exp(-a / 0.2)
        elif ginn == 'type':
            alpha = 1.0
            inten = level + flash * 0.5 * math.exp(-a / 0.08)
        elif ginn == 'rise':
            e = ease_out(a / 0.35)
            dy = (1 - e) * 60
            alpha = e
            inten = level + flash * 0.4 * math.exp(-a / 0.2)
        elif ginn == 'fade':
            alpha = smooth(a / st.get('din', 0.6))
            inten = level
        inten += hold.get(g.unit, 0.0)
        plug = st.get('plug')
        if plug is not None and g.unit in plug[0]:
            tp = plug[1] + 0.13 * sorted(plug[0]).index(g.unit)
            if t > tp:
                alpha *= max(0.0, 1 - (t - tp) / 0.05)
        # ---- leaving
        if t_out is not None and t > t_out:
            b = (t - t_out) / dout
            if out == 'dim':
                alpha *= 1 - smooth(b)
                inten *= 1 - 0.6 * smooth(b)
            elif out == 'rewind':
                # characters leave last-first
                lb = (t - t_out) / dout * n - (n - 1 - rank)
                alpha *= 1 - clamp01(lb)
                dx += -40 * ease_in(clamp01(lb))
            elif out == 'drop':
                d0 = hash01(g.k, 7) * 0.25
                bb = max(0.0, t - t_out - d0)
                dy += 2600 * bb * bb
                rot += (hash01(g.k, 3) - 0.5) * 220 * bb
                inten *= max(0.0, 1 - bb * 1.5)
                alpha *= 1.0 if bb < 0.6 else max(0.0, 1 - (bb - 0.6) * 4)
            elif out == 'slide':
                e = ease_in(clamp01(b))
                dy += -e * st.get('slide', 300)
                alpha *= 1 - smooth(b)
            elif out == 'shatter':
                e = clamp01(b)
                ang = hash01(g.k, 5) * 6.283
                dx += math.cos(ang) * 500 * e * e
                dy += math.sin(ang) * 500 * e * e - 0 * e
                rot += (hash01(g.k, 9) - 0.5) * 300 * e
                s *= 1 + 0.6 * e
                alpha *= 1 - smooth(b)
            elif out == 'flicker':
                alpha *= (1.0 if hash01(g.k, int((t - t_out) * 40)) > clamp01(b) else 0.0)
            elif out == 'blow':
                e = ease_in(clamp01(b - hash01(g.k, 2) * 0.3))
                dy -= e * 260
                dx += (hash01(g.k, 4) - 0.5) * 300 * e
                alpha *= 1 - e
        if alpha <= 0.003:
            continue
        jit = st.get('jitter', 0.0)
        if jit:
            dx += (hash01(g.k, int(t * 12)) - 0.5) * jit
        m, _, _ = gmask(g.ch, g.font, g.size * z * s) if abs(z * s - 1) > 0.02 else gmask(g.ch, g.font, g.size)
        if abs(rot) > 0.2:
            m = _xmask(m, 1.0, rot)
        # glyph centre in world -> screen
        wx = blk.ox + g.x + g.w / 2 + dx + offx
        wy = blk.oy + g.y + g.h / 2 + dy + offy
        sx, sy = to_screen(M, wx, wy)
        hh, ww = m.shape
        x0, y0 = sx - ww / 2, sy - hh / 2
        _blit(buf['holes'], m, x0, y0, alpha)
        # back face: displaced along the line of sight (outward from the optical centre)
        ddx, ddy = sx - W / 2, sy - H * 0.42
        r = max(1.0, math.hypot(ddx, ddy))
        kk = depth * min(1.0, r / (0.5 * H)) + depth * 0.25
        _blit(buf['back'], m, x0 - ddx / r * kk, y0 - ddy / r * kk, alpha)
        _blit(buf['inten'], m, x0, y0, inten * pv)
