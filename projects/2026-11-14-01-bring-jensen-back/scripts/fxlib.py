"""Drawables used by the score. Each factory returns f(img, tc, t, fi, env) -> img.

tc is content time (it runs backwards during the scratch rewinds), t is real time. Graphics that belong to the
picture use tc; overlays that belong to 'now' (rewind stripes, stamps on sung words) use t.
"""
import math

import cv2
import numpy as np

import scenes as SC
import typo as TY
from common import (AMBER, BEAT, CREAM, GREEN, H, INK, PAPER, RED, T0, W, WHITE, clamp01, ease_out, font, glyph,
                    halftone_fast, over, over_color, sstep)


# ------------------------------------------------------------------------------------------------ props & words
def prop(name, width, cx, cy, t0=-1e9, t1=1e9, enter='pop', swing=0.0, bob=0.0, rot=0.0, alpha=1.0, drift=(0, 0),
         use_t=False, exit=None, tint=None, exit_speed=1.0):
    def f(img, tc, t, fi, env):
        tt = t if use_t else tc
        if tt < t0 or tt >= t1 + ((0.3 / exit_speed + 1.2) if exit else 0):
            return img
        u = tt - t0
        w = width
        a = alpha
        x, y = cx + drift[0] * u, cy + drift[1] * u
        r = rot + swing * math.sin(2 * math.pi * (tc - T0) / (4 * BEAT))
        if enter == 'pop':
            p = ease_out(u / 0.16, 3)
            w = width * (0.6 + 0.4 * p) * (1 + 0.15 * math.sin(min(1, u / 0.25) * math.pi))
            a *= min(1, u / 0.06)
        elif enter == 'slam':
            p = ease_out(u / 0.1, 2)
            w = width * (1 + 0.6 * (1 - p))
        elif enter == 'drop':
            p = ease_out(u / 0.3, 3)
            y -= 900 * (1 - p)
        elif enter == 'fade':
            a *= min(1, u / 0.4)
        if exit and tt >= t1:
            d = tt - t1
            if exit == 'fade':
                a *= max(0, 1 - d / 0.3)
            elif exit == 'left':
                x -= (3000 * d * d + 400 * d) * exit_speed
        y -= bob * float(env['kick'][fi]) * 30
        return SC.put(img, name, max(8, int(w)), x, y, rot=r, alpha=a, tint=tint)
    return f


def big(text, fontname='Anton', size=400, cx=540, cy=700, color=WHITE, t0=-1e9, t1=1e9, use_t=True, **kw):
    b = TY.Big(text, fontname, size, cx, cy, color, t0, t1, **kw)

    def f(img, tc, t, fi, env):
        return b.draw(img, t if use_t else tc)
    f.big = b
    return f


def counter(t0, t1, v0, v1, fmt='{:,.0f}', fontname='Anton', size=330, cx=540, cy=800, color=GREEN, ease=2.0,
            stroke=0, stroke_color=INK, hold=1e9):
    def f(img, tc, t, fi, env):
        if t < t0 or t > t1 + hold:
            return img
        u = clamp01((t - t0) / max(0.01, t1 - t0)) ** (1 / ease)
        v = v0 + (v1 - v0) * u
        txt = fmt.format(v)
        b = TY.Big(txt, fontname, size, cx, cy, color, -1e9, 1e9, enter=None, stroke=stroke, stroke_color=stroke_color)
        return b.draw(img, t)
    return f


def green_light(cx, cy, r, t0=-1e9, t1=1e9, flicker_on=0.35, use_t=False, strength=1.0):
    def f(img, tc, t, fi, env):
        tt = t if use_t else tc
        if tt < t0 or tt > t1:
            return img
        u = tt - t0
        on = 1.0
        if u < flicker_on:
            on = 1.0 if (int(u * 30) % 3) else 0.2
        k = float(env['kick'][fi])
        s = strength * on * (1 + 0.12 * k)
        # lamp body + glow
        cv2.circle(img, (int(cx), int(cy)), int(r * 1.25), (0.05, 0.06, 0.05), -1, cv2.LINE_AA)
        cv2.circle(img, (int(cx), int(cy)), int(r), tuple(float(c) for c in (GREEN * 0.25 + GREEN * 0.75 * s)), -1, cv2.LINE_AA)
        SC.glow(img, cx, cy, r * 1.1, GREEN, 1.2 * s)
        SC.glow(img, cx, cy, r * 3.2, GREEN * 0.6, 0.45 * s)
        return img
    return f


def candles_chart(t0, t1, x0=80, x1=1000, ytop=380, ybot=1200, n=14, color=RED, seed=2, use_t=True):
    """Red candlesticks stepping down a cliff, revealed left to right over [t0, t1]."""
    rng = np.random.default_rng(seed)
    vals = [0.15]
    for i in range(n - 1):
        vals.append(vals[-1] + rng.uniform(0.02, 0.09) + (0.12 if i == n // 2 else 0))
    cand = []
    for i in range(n):
        o = vals[i] - rng.uniform(0.0, 0.02)
        c = vals[i] + rng.uniform(0.04, 0.09)
        hi = o - rng.uniform(0.0, 0.03)
        lo = c + rng.uniform(0.0, 0.03)
        cand.append((o, c, hi, lo))

    def f(img, tc, t, fi, env):
        tt = t if use_t else tc
        if tt < t0:
            return img
        m = int(clamp01((tt - t0) / max(0.01, t1 - t0)) * n + 0.999)
        cw = (x1 - x0) / n
        for i in range(m):
            o, c, hi, lo = cand[i]
            cx = x0 + (i + 0.5) * cw
            y = lambda v: ybot - (ybot - ytop) * (1 - v)  # noqa: E731
            cv2.line(img, (int(cx), int(ytop + (ybot - ytop) * hi)), (int(cx), int(ytop + (ybot - ytop) * lo)),
                     tuple(float(v) for v in color), 5, cv2.LINE_AA)
            cv2.rectangle(img, (int(cx - cw * 0.32), int(ytop + (ybot - ytop) * o)),
                          (int(cx + cw * 0.32), int(ytop + (ybot - ytop) * c)), tuple(float(v) for v in color), -1)
        return img
    return f


def cross_out(line_getter, units, t_at, color=RED, width=16, use_t=True):
    """Strike through some glyphs of a lyric line from t_at on (a fast red slash)."""
    def f(img, tc, t, fi, env):
        tt = t if use_t else tc
        if tt < t_at:
            return img
        ln = line_getter()
        if ln.t_end is not None and t >= ln.t_end:
            return img
        gs = [g for g in ln.glyphs if g.ui in units]
        if not gs:
            return img
        x0 = min(g.x for g in gs) - 10
        x1 = max(g.x + g.m.shape[1] for g in gs) + 10
        y0 = min(g.y for g in gs)
        y1 = max(g.y + g.m.shape[0] for g in gs)
        p = ease_out((tt - t_at) / 0.12, 2)
        xe = x0 + (x1 - x0) * p
        ym = (y0 + y1) / 2
        cv2.line(img, (int(x0), int(y1 - 10)), (int(xe), int(y1 - 10 - (y1 - y0 - 20) * p)), tuple(float(c) for c in color),
                 width, cv2.LINE_AA)
        cv2.line(img, (int(x0), int(y0 + 10)), (int(xe), int(y0 + 10 + (y1 - y0 - 20) * p)), tuple(float(c) for c in color),
                 width, cv2.LINE_AA)
        return img
    return f


def redact(line_getter, units, t_at, color=INK):
    """Black redaction bars over some glyphs, sliding across after they are sung."""
    def f(img, tc, t, fi, env):
        if t < t_at:
            return img
        ln = line_getter()
        if ln.t_end is not None and t >= ln.t_end:
            return img
        rows = {}
        for g in ln.glyphs:
            if g.ui in units:
                rows.setdefault(g.row, []).append(g)
        p = ease_out((t - t_at) / 0.25, 2)
        for gs in rows.values():
            x0 = min(g.x for g in gs) - 6
            x1 = max(g.x + g.m.shape[1] for g in gs) + 6
            y0 = min(g.y for g in gs) + 4
            y1 = max(g.y + g.m.shape[0] for g in gs) - 2
            img[int(y0):int(y1), int(x0):int(x0 + (x1 - x0) * p)] = color
        return img
    return f


def rubber_stamp(text, cx, cy, t0, t1=1e9, color=RED, size=120, rot=-12, fontname='ArchivoBlack', box=True):
    """A rough red rubber stamp (text in a box, worn ink)."""
    m, pad, asc, w = glyph(fontname, size, text)
    hgt = m.shape[0]
    bw, bh = m.shape[1] + 60, hgt + 20
    A = np.zeros((bh + 40, bw + 40), np.float32)
    A[20 + 30 - pad:20 + 30 - pad + hgt, 20 + 30:20 + 30 + m.shape[1]] = np.maximum(
        A[20 + 30 - pad:20 + 30 - pad + hgt, 20 + 30:20 + 30 + m.shape[1]], m)
    if box:
        cv2.rectangle(A, (20, 20), (20 + bw, 20 + bh), 1.0, 12)
    rng = np.random.default_rng(len(text))
    noise = cv2.GaussianBlur(rng.random(A.shape).astype(np.float32), (0, 0), 2.5)
    A = A * clamp01((noise - 0.32) * 4)
    M = cv2.getRotationMatrix2D((A.shape[1] / 2, A.shape[0] / 2), rot, 1)
    ext = int(math.hypot(*A.shape)) + 4
    M[0, 2] += (ext - A.shape[1]) / 2
    M[1, 2] += (ext - A.shape[0]) / 2
    A = cv2.warpAffine(A, M, (ext, ext))

    def f(img, tc, t, fi, env):
        if t < t0 or t >= t1:
            return img
        u = t - t0
        sc = 1 + 0.5 * (1 - ease_out(u / 0.09, 2))
        a = min(1, u / 0.03)
        Am = cv2.resize(A, None, fx=sc, fy=sc) if sc != 1 else A
        h, w = Am.shape
        x0, y0 = int(cx - w / 2), int(cy - h / 2)
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
        if xb > xa and yb > ya:
            sub = img[ya:yb, xa:xb]
            aa = Am[ya - y0:yb - y0, xa - x0:xb - x0][..., None] * a * 0.92
            sub[:] = sub * (1 - aa) + np.asarray(color, np.float32) * aa
        return img
    return f


def rect(x0, y0, x1, y1, color, t0=-1e9, t1=1e9, use_t=False, alpha=1.0, wipe=0.0):
    def f(img, tc, t, fi, env):
        tt = t if use_t else tc
        if tt < t0 or tt >= t1:
            return img
        xe = x1
        if wipe:
            xe = x0 + (x1 - x0) * ease_out((tt - t0) / wipe, 3)
        sub = img[int(y0):int(y1), int(x0):int(xe)]
        sub[:] = sub * (1 - alpha) + np.asarray(color, np.float32) * alpha
        return img
    return f


def fire(t0, t1, y0=1300, strength=1.0):
    """'Market cap burning': a flickering red-orange heat rising from the bottom edge."""
    def f(img, tc, t, fi, env):
        if t < t0 or t >= t1:
            return img
        rng = np.random.default_rng(fi)
        n = rng.random((H // 16, W // 16)).astype(np.float32)
        n = cv2.resize(cv2.GaussianBlur(n, (0, 0), 1.3), (W, H))
        yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        hgt = clamp01((yy * H - y0) / (H - y0))
        a = clamp01(hgt * (0.55 + 0.6 * n) * 1.2) * strength * min(1, (t - t0) / 0.3)
        col = np.dstack([np.ones_like(a), 0.25 + 0.4 * n * hgt, 0.05 * np.ones_like(a)])
        return img * (1 - a[..., None] * 0.85) + col * a[..., None]
    return f


def scribbles(t0, t1, color=CREAM, rows=40, speed=1400, alpha=0.5, seed=4):
    """Endless signatures (abstract handwriting strokes) scrolling up: a petition list."""
    rng = np.random.default_rng(seed)
    sigs = []
    for i in range(rows):
        pts = []
        x = rng.uniform(80, 300)
        L = rng.uniform(300, 760)
        for k in range(60):
            u = k / 59
            pts.append((x + L * u, 18 * math.sin(u * rng.uniform(8, 20) + rng.uniform(0, 6)) + 10 * math.sin(u * 37 + i)))
        sigs.append((np.array(pts, np.float32), rng.uniform(0.5, 1.0)))

    def f(img, tc, t, fi, env):
        if t < t0 or t >= t1:
            return img
        off = (t - t0) * speed
        A = np.zeros((H, W), np.float32)
        for i, (pts, a) in enumerate(sigs):
            y = (i * 110 - off) % (rows * 110) - 60
            if -60 < y < H + 60:
                p = pts.copy()
                p[:, 1] += y
                cv2.polylines(A, [p.astype(np.int32)], False, a, 5, cv2.LINE_AA)
        return over_color(img, A, color, alpha)
    return f


def dots_ring(cx, cy, r, n, t0, color=CREAM, rad=14, use_t=False):
    """n small figures (dots) in a ring - the sixty direct reports around one empty chair."""
    def f(img, tc, t, fi, env):
        tt = t if use_t else tc
        if tt < t0:
            return img
        m = int(min(n, (tt - t0) / 0.012))
        for i in range(m):
            a = 2 * math.pi * i / n - math.pi / 2
            rr = r * (1 + 0.08 * ((i % 3) - 1))
            x, y = cx + rr * math.cos(a), cy + rr * 0.55 * math.sin(a)
            cv2.circle(img, (int(x), int(y)), rad, tuple(float(c) for c in color), -1, cv2.LINE_AA)
            cv2.circle(img, (int(x), int(y - rad * 1.9)), int(rad * 0.75), tuple(float(c) for c in color), -1, cv2.LINE_AA)
        return img
    return f


def phone_feed(cx, cy, w, t0, t1, rows=6, hot=RED, use_t=True):
    """A generic phone showing a trending list: numbered rows with a red heat bar each (no app branding)."""
    def f(img, tc, t, fi, env):
        tt = t if use_t else tc
        if tt < t0 or tt >= t1:
            return img
        SC.put(img, 'phone', w, cx, cy)
        hh = w * 800 / 420
        x0, y0 = cx - w * 0.38, cy - hh * 0.36
        for i in range(rows):
            y = y0 + i * hh * 0.11
            k = clamp01((tt - t0 - i * 0.08) / 0.2)
            if k <= 0:
                continue
            TY.Big(str(i + 1), 'SpaceMono', 44, x0 + 14, y + 22, RED if i < 3 else np.array([0.4, 0.4, 0.4], np.float32),
                   -1e9, 1e9, enter=None).draw(img, tt)
            bw = (w * 0.62) * (1 - i * 0.08) * k
            cv2.rectangle(img, (int(x0 + 50), int(y + 8)), (int(x0 + 50 + bw), int(y + 30)), (0.3, 0.3, 0.32), -1)
            fl = 0.5 + 0.5 * math.sin(tt * 9 + i)
            cv2.rectangle(img, (int(x0 + 50), int(y + 38)), (int(x0 + 50 + bw * (0.3 + 0.2 * fl)), int(y + 46)),
                          tuple(float(c) for c in hot), -1)
        return img
    return f


def vhs(t0, t1, strength=1.0, label=True):
    """Rewind overlay: rolling tracking bars, chroma bleed, a ◀◀ glyph."""
    def f(img, tc, t, fi, env):
        if t < t0 or t >= t1:
            return img
        rng = np.random.default_rng(fi)
        img = img.copy()
        for _ in range(5):
            y = int(rng.uniform(0, H))
            h = int(rng.uniform(8, 60))
            sh = int(rng.uniform(-60, 60))
            img[y:y + h] = np.roll(img[y:y + h], sh, axis=1) * 1.15
        y = int((t * 2400) % H)
        img[y:y + 70] = img[y:y + 70] * 0.4 + 0.5
        img[:, 6:, 0] = img[:, :-6, 0]
        img += (rng.random((H // 4, W // 4)).astype(np.float32).repeat(4, 0).repeat(4, 1) - 0.5)[..., None] * 0.12 * strength
        if label:
            for k in range(2):
                pts = np.array([[150 - k * 60, 140], [150 - k * 60, 220], [90 - k * 60, 180]], np.int32) + np.array([60, 0])
                cv2.fillConvexPoly(img, pts, (1, 1, 1), cv2.LINE_AA)
            TY.Big('REW', 'SpaceMono', 72, 290, 180, WHITE, -1e9, 1e9, enter=None).draw(img, t)
        return img
    return f


def glitch(t0, t1, strength=1.0):
    """The electric glitch that cuts the piano: torn bands, colour split, scanlines, red cast."""
    def f(img, tc, t, fi, env):
        if t < t0 or t >= t1:
            return img
        rng = np.random.default_rng(fi * 3 + 1)
        u = t - t0
        s = strength * (1.0 if u < 0.5 else 0.45)
        img = img.copy()
        for _ in range(int(8 * s) + 1):
            y = int(rng.uniform(0, H))
            h = int(rng.uniform(6, 120))
            img[y:y + h] = np.roll(img[y:y + h], int(rng.uniform(-140, 140) * s), axis=1)
        d = int(14 * s) + 1
        img[:, d:, 0] = img[:, :-d, 0]
        img[:, :-d, 2] = img[:, d:, 2]
        img[::4] *= 0.55
        L = img.mean(2, keepdims=True)
        img = img * 0.35 + L * np.array([1.2, 0.35, 0.3], np.float32) * 0.65
        return img
    return f


def tv_static(t0, t1, alpha=0.35):
    def f(img, tc, t, fi, env):
        if t < t0 or t >= t1:
            return img
        rng = np.random.default_rng(fi + 99)
        n = rng.random((H // 3, W // 3)).astype(np.float32).repeat(3, 0).repeat(3, 1)
        return img * (1 - alpha) + n[..., None] * alpha
    return f


def echo_words(word, times, cx=540, cy=1300, size0=260, color=GREEN, fontname='Anton'):
    """'back... back... back...' : each vocal-chop echo stamps a smaller, fainter copy that drifts away."""
    def f(img, tc, t, fi, env):
        for i, ta in enumerate(times):
            if t < ta:
                continue
            u = t - ta
            a = max(0.0, 1 - u / 1.6) * (0.95 ** i)
            if a <= 0.01:
                continue
            s = size0 * (0.86 ** i)
            b = TY.Big(word, fontname, int(s), cx, cy + i * 70 * (1 if i % 2 else -1) * 0.6 + u * 30, color, -1e9, 1e9, enter=None,
                       alpha=a)
            b.draw(img, t)
        return img
    return f


def credits(lines, t0, t1, y=1500, color=CREAM, size=40):
    def f(img, tc, t, fi, env):
        if t < t0 or t >= t1 + 0.6:
            return img
        a = min(1.0, (t - t0) / 0.6) * (1 - clamp01((t - t1) / 0.6))
        for i, (txt, fn, sz) in enumerate(lines):
            b = TY.Big(txt, fn, sz, 540, y + i * sz * 1.5, color, -1e9, 1e9, enter=None, alpha=a)
            b.draw(img, t)
        return img
    return f


def fade(t0, t1, color=INK, to=1.0, frm=0.0):
    """Fade to (or from) a colour between t0 and t1."""
    def f(img, tc, t, fi, env):
        if t < t0:
            a = frm
        elif t >= t1:
            a = to
        else:
            a = frm + (to - frm) * (t - t0) / (t1 - t0)
        if a <= 0:
            return img
        return img * (1 - a) + np.asarray(color, np.float32) * a
    return f


def band_for(line_getter, color=WHITE, pad=(28, 18), rot=-2.0, shadow=INK):
    """A paper sticker strip behind a lyric line, slapped on when its first unit is sung."""
    def f(img, tc, t, fi, env):
        ln = line_getter()
        if t < ln.first() - ln.lead or (ln.t_end is not None and t >= ln.t_end):
            return img
        x0, y0, x1, y1 = ln.bbox
        x0, y0, x1, y1 = x0 - pad[0], y0 - pad[1], x1 + pad[0], y1 + pad[1]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        u = t - (ln.first() - ln.lead)
        sc = 1 + 0.25 * (1 - ease_out(u / 0.1, 2))
        M = cv2.getRotationMatrix2D((cx, cy), rot, sc)
        pts = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float64)
        pts = (M[:, :2] @ pts.T).T + M[:, 2]
        A = np.zeros((H, W), np.float32)
        cv2.fillConvexPoly(A, pts.astype(np.int32), 1.0, cv2.LINE_AA)
        if shadow is not None:
            over_color(img, np.roll(np.roll(A, 12, 0), 12, 1), shadow)
        return over_color(img, A, color)
    return f


# ------------------------------------------------------------------------------------------------ v2: the witness
import person as P  # noqa: E402


def her(spec, use_content_time=True):
    """Composite the heroine (person.render) with this shot's spec. Lights may be callables of t."""
    def f(img, tc, t, fi, env):
        sp = dict(spec)
        if 'strobe' in sp:   # a strobe or flash lights her only while it fires
            k = float(env['snare'][fi]) * sp.pop('strobe')
            sp['key'] = dict(color=(1.0, 1.0, 1.0), dir=(0, -1), k=k * 1.6, soft=1.0)
            sp['amb'] = tuple(np.asarray(sp.get('amb', (0.05, 0.05, 0.05)), np.float32) + k * 0.25)
        if sp.get('t_on') is not None and t < sp['t_on']:
            return img
        if sp.get('t_off') is not None and t >= sp['t_off']:
            return img
        sp.pop('t_on', None)
        sp.pop('t_off', None)
        return P.render(img, sp, tc if use_content_time else t, fi, env, now=t)
    return f


def fg_heads(specs, color=INK, blur=9.0, bob_env='kick', bob=14):
    """Out-of-focus heads and shoulders of people standing between the camera and her.
    specs: [(x, y, scale)] - y is the top of the head."""
    def f(img, tc, t, fi, env):
        A = np.zeros((H, W), np.float32)
        k = float(env[bob_env][fi]) if bob_env else 0.0
        for i, (x, y, s) in enumerate(specs):
            yb = y - bob * k * (0.6 + 0.4 * math.sin(i * 2.1))
            cv2.ellipse(A, (int(x), int(yb + 95 * s)), (int(78 * s), int(98 * s)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
            cv2.ellipse(A, (int(x), int(yb + 330 * s)), (int(230 * s), int(150 * s)), 0, 180, 360, 1.0, -1, cv2.LINE_AA)
            cv2.rectangle(A, (int(x - 230 * s), int(yb + 330 * s)), (int(x + 230 * s), H), 1.0, -1)
        if blur:
            A = cv2.GaussianBlur(A, (0, 0), blur)
        return over_color(img, A, color)
    return f


def diner_fg(mugs=1, steam=0.0, table=(), mug_w=150, dof=0.0, candle=None):
    """The near edge of the diner table (and what stands on it) drawn in front of her."""
    def f(img, tc, t, fi, env):
        top = np.array([0.86, 0.80, 0.70], np.float32) * np.array([1.06, 0.97, 0.84], np.float32)
        layer = img.copy()
        layer[1240:1330, 120:960] = top
        layer[1330:1352, 120:960] = np.array([0.80, 0.80, 0.84], np.float32) * np.array([1.06, 0.97, 0.84], np.float32)
        layer[1352:1700, 500:580] = np.array([0.45, 0.45, 0.48], np.float32) * np.array([1.06, 0.97, 0.84], np.float32)
        xs = {1: (560,), 2: (430, 690), 3: (300, 540, 780)}.get(mugs, ())
        for x in xs:
            SC.put(layer, 'mug', mug_w, x, 1240 - mug_w * 0.36)
        for name, w, cx, cy in table:
            SC.put(layer, name, w, cx, cy)
        if candle:
            SC.glow(layer, candle[0], candle[1], 40, AMBER, 0.9 + 0.15 * math.sin(t * 17) * math.sin(t * 5.1))
        m = np.zeros((H, W), np.float32)
        m[1080:1700] = 1   # only the table band is foreground
        if dof:
            layer = cv2.GaussianBlur(layer, (0, 0), dof)
        return img * (1 - m[..., None]) + layer * m[..., None]
    return f


def scene_blur(sigma, y0=0, y1=H):
    """Defocus the plate behind her (shallow depth of field when she is the subject)."""
    def f(img, tc, t, fi, env):
        s = sigma(t) if callable(sigma) else sigma
        if s < 0.3:
            return img
        img[y0:y1] = cv2.GaussianBlur(img[y0:y1], (0, 0), s)
        return img
    return f


def haze_beams(n=2, color=(0.6, 1.0, 0.5), k=0.10, t_speed=0.6):
    """Light beams through haze, drawn IN FRONT of her (depth: the haze is between her and the camera)."""
    def f(img, tc, t, fi, env):
        yy, xx = SC._yy_xx()
        acc = np.zeros((H, W), np.float32)
        for j in range(n):
            ang = math.sin(tc * t_speed + j * 2.4) * 0.35 + (j - 0.5) * 0.5
            sx = 540 + (j - 0.5) * 700
            dxl = (xx - sx) * math.cos(ang) - (yy + 100) * math.sin(ang)
            width = 60 + (yy + 100) * 0.22
            acc += np.exp(-(dxl / width) ** 2) * clamp01((yy + 100) / 900)
        img += (acc * k)[..., None] * np.asarray(color, np.float32)
        return img
    return f


def grade(mul=(1, 1, 1), lift=0.0, sat=1.0):
    """A scene-wide grade applied after she is composited, so she gets exactly the plate's colour."""
    mul = np.asarray(mul, np.float32)

    def f(img, tc, t, fi, env):
        if sat != 1.0:
            g = (img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114)[..., None]
            img = g + (img - g) * sat
        return img * mul + lift
    return f


def flash_lights(colors, env_key='kick'):
    """Concert wash lights that change colour on each beat (the strobe-revealed crowd)."""
    def f(img, tc, t, fi, env):
        i = int((t - T0) / BEAT) % len(colors)
        k = float(env[env_key][fi])
        img += np.asarray(colors[i], np.float32) * 0.18 * k
        return img
    return f


def spotlight(sx, tx, ty, t_on, t_off=1e9, r=170, color=(1.0, 1.0, 0.95), k=0.55, sweep=(-260, 0), sweep_dur=0.3):
    """A follow spot: a soft cone from above to (tx, ty), swinging in over sweep_dur. Drawn in front (haze)."""
    def f(img, tc, t, fi, env):
        if t < t_on or t >= t_off:
            return img
        u = ease_out((t - t_on) / sweep_dur, 3)
        x = tx + sweep[0] * (1 - u)
        y = ty + sweep[1] * (1 - u)
        yy, xx = SC._yy_xx()
        v = clamp01((yy + 100) / (y + 100))
        cx = sx + (x - sx) * v
        width = 30 + r * v
        cone = np.exp(-((xx - cx) / width) ** 2) * (0.25 + 0.75 * v) * (yy < y + r)
        pool = np.exp(-(((xx - x) / (r * 1.3)) ** 2 + ((yy - y) / (r * 1.1)) ** 2))
        a = clamp01(cone * 0.35 + pool * 0.6) * k * min(1.0, (t - t_on) / 0.06)
        img += a[..., None] * np.asarray(color, np.float32)
        return img
    return f


def near_table(items=(), far=1330, dof=0.0, tone=(0.82, 0.74, 0.62)):
    """Across-the-table view: the near tabletop fills the bottom of the frame and hides everything below its far
    edge (the camera sits above table height). items: [(prop, width, cx, cy)] standing on it."""
    tone = np.asarray(tone, np.float32)

    def f(img, tc, t, fi, env):
        layer = np.zeros((H, W, 3), np.float32)
        yy = np.arange(H, dtype=np.float32)[:, None, None]
        layer[:] = tone * (0.86 + 0.18 * clamp01((yy - far) / (H - far)))
        layer[far:far + 10] = np.array([0.80, 0.80, 0.84], np.float32)          # chrome trim on the far edge
        layer[H - 40:] = np.array([0.70, 0.70, 0.74], np.float32)                # and the near edge
        A = np.zeros((H, W), np.float32)
        poly = np.array([[40, far], [W - 40, far], [W + 300, H], [-300, H]], np.int32)
        cv2.fillConvexPoly(A, poly, 1.0, cv2.LINE_AA)
        for name, w, cx, cy in items:
            SC.put(layer, name, w, cx, cy)
            rgb, a = SC.prop(name, int(w))
            h, ww = a.shape
            x0, y0 = int(cx - ww / 2), int(cy - h / 2)
            xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + ww), min(H, y0 + h)
            A[ya:yb, xa:xb] = np.maximum(A[ya:yb, xa:xb], a[ya - y0:yb - y0, xa - x0:xb - x0])
        # a soft reflection of the room's light on the formica
        if dof:
            layer = cv2.GaussianBlur(layer, (0, 0), dof)
            A = cv2.GaussianBlur(A, (0, 0), dof * 0.6)
        return img * (1 - A[..., None]) + layer * A[..., None]
    return f


def vox_photo(x0, y0, x1, y1, spec, t_on, ink=INK, paper=PAPER):
    """A small street-interview photo in the newspaper: a box, a hairline frame, her printed inside, caption lines."""
    def f(img, tc, t, fi, env):
        if t < t_on:
            return img
        p = ease_out((t - t_on) / 0.12, 2)
        if p < 1:
            yc = (y0 + y1) / 2
            ya, yb = int(yc - (yc - y0) * p), int(yc + (y1 - yc) * p)
        else:
            ya, yb = y0, y1
        img[ya:yb, x0:x1] = np.asarray(paper, np.float32) * 0.985
        if p >= 1:
            sp = dict(spec)
            sp.update(look='print', ink=ink, paper=paper, clip=(x0 + 8, y0 + 8, x1 - 8, y1 - 70))
            P.render(img, sp, tc, fi, env, now=t)
            img[y0:y0 + 3, x0:x1] = ink
            img[y1 - 66:y1 - 64, x0 + 8:x1 - 8] = ink * 0.8
            for k in range(2):
                img[y1 - 52 + 22 * k:y1 - 44 + 22 * k, x0 + 8:x1 - 8 - 90 * k] = ink * 0.45
        return img
    return f
