#!/usr/bin/env python3
"""Render 别回答 (coldwave). One frame = plate -> exposure -> lyric layer -> fog and beams -> snow -> shot effects
-> fades -> film -> colour. All flowing things read timeline.phi(t); the lyric layer reads lyric_timing.json.

  render.py --preview 12.5,81.96,...     PNGs into work/preview/
  render.py --all 4                      every missing chunk of 200 frames, 4 processes -> work/segments/cNNN.mkv
  render.py --chunks 3,4                 these chunks only (delete the old files first)

The lyric rule (storyboard.md): verses are light through a stencil, projected with the depth map so it folds over
the scene and breaks at depth edges; choruses invert it (floodlight, the words are the only shadow); the Bridge
dissolves it into the exposure; Verse 4 is white type printed on the cyanotype; the last chorus is window light.
"""
import functools
import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import look  # noqa: E402
import lyrics  # noqa: E402
import timeline as T  # noqa: E402
import words  # noqa: E402
from look import W, H, XX, YY  # noqa: E402
from shots import SHOTS, FX, shot_at  # noqa: E402

ROOT = look.ROOT
LT = json.load(open(os.path.join(ROOT, 'work', 'audio', 'lyric_timing.json')))
SNOW = look.Snow()
CHUNK = 200


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


# ---- lyric lines --------------------------------------------------------------------------------------
class Line:
    def __init__(self, x):
        self.key = f"{x['sec']}|{x['n']}"
        self.sec, self.n, self.text = x['sec'], x['n'], x['text']
        self.s = np.array(LT[self.key]['start'])
        self.e = np.array(LT[self.key]['end'])
        self.shot = shot_at(self.s[0] + 0.35)      # a line sung just before its cut belongs to the shot after it
        P = self.shot.lyr
        self.mode = P.get('mode_line', {}).get(self.key, P['mode'])
        self.cy = P.get('cy_line', {}).get(self.key, P['cy'])
        self.src = P.get('src_line', {}).get(self.key, P.get('src', (-260, -420)))
        self.fast = P.get('fast', False)
        self.width = P.get('width', 0.82) if self.mode in ('spot',) else 0.82
        if self.mode == 'cloud':
            self.width = 0.82

    @functools.cached_property
    def block(self):
        thin = 0.07 if self.mode == 'thin' else 0.0
        rot = 5.0 if self.mode == 'thin' else 0.0
        cuts = self.mode not in ('thin', 'print')
        return words.Block(self.text, self.cy, width=self.width, cuts=cuts, thin=thin, rot=rot, seed=hash(self.key) % 997)

    @property
    def t_in(self):
        return self.s[0] - 0.12

    @property
    def t_out(self):
        hold, ex = self.exit()
        return self.e[-1] + hold + ex

    def exit(self):
        if self.mode in ('light', 'spot'):
            return (0.12, 0.25) if self.fast else (0.25, 0.45)
        if self.mode == 'cloud':
            return (99, 0.1)
        if self.mode in ('diffuse',):
            return (0.3, 0.8)
        if self.mode in ('shadow',):
            return (0.2, 0.3)
        return (0.3, 0.6)

    def sweep(self, t):
        d = np.clip(0.85 * (self.e - self.s), 0.15, 0.6) * (0.5 if self.fast else 1.0)
        return np.clip((t - (self.s - 0.07)) / d, 0, 1)

    def appear(self, t, dur=0.18):
        return np.clip((t - (self.s - 0.03)) / dur, 0, 1)

    def leave(self, t):
        hold, ex = self.exit()
        u = (t - (self.e[-1] + hold)) / ex
        return ease(u)


LINES = [Line(x) for x in lyrics.LINES]
TITLE = None


def active_lines(t):
    out = []
    for i, L in enumerate(LINES):
        if L.t_in <= t < L.t_out:
            nxt = LINES[i + 1] if i + 1 < len(LINES) else None
            # a line leaves no later than the next line's first character in the same shot
            if nxt is not None and nxt.shot is L.shot and t >= nxt.s[0] - 0.05 and L.mode != 'cloud':
                continue
            if L.shot is not shot_at(t):
                continue
            out.append(L)
    return out


@functools.lru_cache(maxsize=1)
def title_block():
    ch = ''.join(lyrics.line('Chorus 1', 1)['chars'][:3])       # the title is the chorus's first phrase
    return words.Block(ch, 1060, width=0.82, seed=7)


# ---- helpers ----------------------------------------------------------------------------------------------
def project(mask, D, kx, ky):
    """Throw the slide mask onto the scene: nearer surfaces displace it (the projector sits off the camera)."""
    if kx == 0 and ky == 0:
        return mask
    ys, xs = np.nonzero(mask[::8, ::8] > 0.05)
    if len(ys) == 0:
        return mask
    d0 = float(np.median(D[ys * 8, xs * 8]))
    mx = (XX - kx * (D - d0)).astype(np.float32)
    my = (YY - ky * (D - d0)).astype(np.float32)
    return cv2.remap(mask, mx, my, cv2.INTER_LINEAR, borderValue=0)


def cone(src, dst, r0, r1, length_pad=1.1):
    """Quarter-res soft cone from src to dst (output px)."""
    sx, sy = src
    tx, ty = dst
    vx, vy = tx - sx, ty - sy
    Lr = np.hypot(vx, vy) + 1e-6
    ux, uy = vx / Lr, vy / Lr
    px, py = look.XQ - sx, look.YQ - sy
    along = (px * ux + py * uy) / Lr
    perp = np.abs(px * uy - py * ux)
    r = r0 + (r1 - r0) * np.clip(along, 0, 1.3)
    a = np.clip(1 - perp / r, 0, 1) ** 1.6
    a *= np.clip(along * 6, 0, 1) * np.clip((length_pad - along) * 4, 0, 1)
    return a.astype(np.float32)


def blur(m, s):
    return cv2.GaussianBlur(m, (0, 0), s)


def qblur(m, s):
    return look.up(cv2.GaussianBlur(look.down(m), (0, 0), s / look.Q))


def shear_mask(mask, cx, cy, sh, sy=0.92):
    M = np.float32([[1, sh, -sh * cy], [0, sy, (1 - sy) * cy]])
    return cv2.warpAffine(mask, M, (W, H), borderValue=0)


def disk(cx, cy, r, soft=4.0):
    return np.clip((r - np.hypot(XX - cx, YY - cy)) / soft + 0.5, 0, 1).astype(np.float32)


def kf_to_out(M, x, y):
    return (M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2])


# ---- per-shot plate preparation (keyframe space) ------------------------------------------------------------
@functools.lru_cache(maxsize=2)
def suns_parts():
    lum, d, im = look.plate('K06')
    mask = np.zeros(lum.shape, np.uint8)
    sprites = []
    for x, y, r, dx, dy in FX['suns']:
        cv2.circle(mask, (x, y), r + 8, 255, -1)
        R = r + 14
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
        a = np.clip((r + 4 - np.hypot(xx, yy)) / 6 + 0.5, 0, 1).astype(np.float32)
        sprites.append((x, y, R, lum[y - R:y + R + 1, x - R:x + R + 1].copy(), a, dx, dy))
    base = cv2.inpaint((lum * 255).astype(np.uint8), mask, 9, cv2.INPAINT_TELEA).astype(np.float32) / 255
    return base, sprites


@functools.lru_cache(maxsize=2)
def ship_lights():
    lum, d, im = look.plate('K11')
    m = (lum > 0.55).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    pts = [(cen[i][0], cen[i][1], i) for i in range(1, n) if 2 <= st[i][4] <= 400]
    return lab, pts


@functools.lru_cache(maxsize=2)
def ship_kills():
    """Rows of running lights, nearest first, one row per strong snare in Verse 2 lines 3-4."""
    lab, pts = ship_lights()
    sn = T.snares_between(110.70, 119.20, strong=0.55)
    k = max(1, len(sn))
    ys = np.array([p[1] for p in pts])
    order = np.argsort(-ys)
    groups = np.array_split(order, k)
    lum = look.plate('K11')[0]
    masks = []
    for g in groups:
        ids = np.array([pts[j][2] for j in g])
        mk = np.isin(lab, ids).astype(np.uint8)
        mk = cv2.dilate(mk, np.ones((7, 7), np.uint8)).astype(np.float32)
        masks.append(cv2.GaussianBlur(mk, (0, 0), 2))
    return list(sn), masks


@functools.lru_cache(maxsize=2)
def window_masks():
    lum = look.plate('K15')[0]
    m = (lum > 0.6).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    rng = np.random.default_rng(4)
    off = [i for i in range(1, n) if st[i][4] >= 20 and rng.random() < 0.5]
    mk = np.isin(lab, off).astype(np.uint8)
    mk = cv2.dilate(mk, np.ones((9, 9), np.uint8)).astype(np.float32)
    return cv2.GaussianBlur(mk, (0, 0), 3)


@functools.lru_cache(maxsize=2)
def lamp_mask():
    lum = look.plate('K18')[0]
    x0, y0, x1, y1 = FX['lamp_region']
    m = np.zeros(lum.shape, np.float32)
    m[y0:y1, x0:x1] = np.clip((lum[y0:y1, x0:x1] - 0.45) / 0.25, 0, 1)
    return cv2.GaussianBlur(m, (0, 0), 3)


@functools.lru_cache(maxsize=2)
def k24_sky():
    lum, d, im = look.plate('K24')
    sky = ((d < 0.22) & (np.arange(lum.shape[0])[:, None] < 1385)).astype(np.float32)
    return cv2.GaussianBlur(sky, (0, 0), 3)


@functools.lru_cache(maxsize=2)
def fish_parts():
    lum, d, im = look.plate('K26')
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[..., 0] * 2, hsv[..., 1] / 255, hsv[..., 2] / 255
    m = ((h > 2) & (h < 42) & (s > 0.45) & (v > 0.25)).astype(np.float32)
    m = cv2.GaussianBlur(m, (0, 0), 1.5)
    rgb = im[..., ::-1].astype(np.float32) / 255
    return m, rgb


def shot_plate(sh, t):
    lum, d, im = look.plate(sh.kf)
    p0, p1 = T.phi(sh.t0), T.phi(max(sh.t1 - 1e-3, sh.t0 + 1e-3))
    u = (T.phi(t) - p0) / max(p1 - p0, 1e-6)
    z = sh.z[0] + (sh.z[1] - sh.z[0]) * u
    dy = 0.0
    if 'suns' in sh.fx:
        base, spr = suns_parts()
        lum = base.copy()
        for x, y, R, sp, a, dx, ddy in spr:
            ox, oy = int(round(x + dx * u)), int(round(y + ddy * u))
            sl = lum[oy - R:oy + R + 1, ox - R:ox + R + 1]
            sl[:] = sl * (1 - a) + sp * a
    if 'ships' in sh.fx:
        sn, masks = ship_kills()
        lum = lum.copy()
        for ts, mk in zip(sn, masks):
            if t >= ts:
                lum = lum * (1 - 0.92 * mk)
    if 'halfwin' in sh.fx:
        lum = lum * (1 - 0.9 * window_masks())
    if 'trails' in sh.fx:
        sky = k24_sky()
        sx, sy = FX['star']
        R = cv2.getRotationMatrix2D((sx, sy), -2.2 * u, 1.0)
        rot = cv2.warpAffine(lum, R, (lum.shape[1], lum.shape[0]), borderMode=cv2.BORDER_REFLECT)
        lum = rot * sky + lum * (1 - sky)
    if 'fall' in sh.fx:
        dy = FX['paper_fall'] * (T.phi(t) - p0)
    c = sh.c
    M = look.affine(z, c, dy=dy)
    border = cv2.BORDER_CONSTANT if sh.kf in ('K21', 'K20') else cv2.BORDER_REPLICATE
    P = look.warp(lum, M, border=border)
    D = look.warp(d, M)
    return P, D, M


# ---- the frame ---------------------------------------------------------------------------------------------
def flood_level(sh, t):
    P = sh.lyr
    on = P.get('flood_on', sh.t0)
    lv = 1.0 if t >= on else 0.0
    if 'filament' in sh.fx:                       # chorus 1 line 5: off, on, off, on on the four sung onsets
        k = sum(1 for x in T.TICKS if t >= x)
        if k in (1, 3):
            lv = 0.0
    if sh.id == 's17' and 152.15 <= t < 155.30:   # the accompaniment gates in eighths under line 4
        z = T._feat
        i = int(t * float(z['rate']))
        lv = float(np.clip((z['inst'][i] + 46) / 16, 0, 1))
    if 'flood_off' in P:
        a, b = P['flood_off']
        lv *= 1 - ease((t - a) / (b - a))
    return lv


def frame(t):
    sh = shot_at(t)
    ph = T.phi(t)
    fk = int(np.floor(ph * T.FPS + 1e-6))
    P, D, M = shot_plate(sh, t)
    Dq = look.down(D)
    expo = sh.lyr.get('expo', 'night')
    lines = active_lines(t)
    beams = []

    # --- exposure of the scene
    flv = flood_level(sh, t) if expo == 'flood' else 0.0
    if expo == 'night':
        base = P * 0.18 + np.clip(P - 0.78, 0, 1) * 2.2      # light sources (suns, windows, lamps) keep their glow
    elif expo == 'dark':
        base = P * 0.13
    elif expo == 'flood':
        night = P * 0.30
        lit = 1 - (1 - np.clip(P * 1.55 + 0.20, 0, 1)) ** 2.2
        base = night * (1 - flv) + lit * flv
    elif expo == 'black':
        base = P * 0.85
    elif expo == 'blue':
        base = P
        if sh.kf == 'K21':
            base = np.clip((P - 0.20) / 0.62, 0, 1)
        if sh.kf == 'K22':
            base = P * 0.60
    else:  # warm: window light at night
        base = P * 0.55
    out = base.copy()

    # --- fog veil (before the words: the light lands on the surface we see through the fog)
    dens = tuple(sh.fog * k for k in (1.0, 0.85, 0.6))
    F = ftex = None
    if sh.fog > 0:
        F, ftex = look.fog_field(ph, Dq, dens)
        fogcol = {'night': 0.11, 'dark': 0.34, 'flood': 0.10 + 0.55 * flv, 'black': 0.02, 'blue': 0.5, 'warm': 0.14}[expo]
        out = out * (1 - look.up(F)) + fogcol * look.up(F)

    # --- lyric layer
    for L in lines:
        lyr = sh.lyr
        kx, ky = lyr.get('proj', (-70, -45))
        mode = L.mode
        if mode in ('light', 'spot'):
            sw = L.sweep(t)
            u = L.leave(t)
            dx = 380 * u
            alpha = 1 - u
            gain = 1.0
            if lyr.get('kick'):
                gain = 0.45 + 0.55 * T.kick(t)
            m = L.block.full(sweep=sw, dx=dx) * alpha * gain
            pm = project(m, D, kx, ky)
            air = lyr.get('air', 0.10)
            lit = np.clip(P * 1.40 + air, 0, 1.15)
            out = out * (1 - pm) + lit * pm
            out += qblur(pm, 10) * 0.08
            x0, y0, x1, y1 = L.block.bbox
            beams.append((L.src, ((x0 + x1) / 2 + dx, (y0 + y1) / 2), (x1 - x0) * 0.42, 0.11 * alpha * gain))
        elif mode == 'shadow':
            ap = L.appear(t, 0.08) * (1 - L.leave(t)) * flv
            m = L.block.full(weights=ap)
            cx = (L.block.bbox[0] + L.block.bbox[2]) / 2
            cy = (L.block.bbox[1] + L.block.bbox[3]) / 2
            sh_ = lyr.get('shear', 0.4)
            if lyr.get('twin'):
                S = 0.58 * shear_mask(m, cx, cy, sh_) + 0.58 * shear_mask(m, cx, cy, -sh_)
            else:
                S = shear_mask(m, cx, cy, sh_)
            pen = 5.0
            if 'flood_off' in lyr:
                a, b = lyr['flood_off']
                pen += 30 * ease((t - a) / (b - a))
            S = 0.75 * blur(S, pen) + 0.25 * qblur(S, pen * 4)
            if 'lens' in lyr:
                lx, ly, lr = lyr['lens']
                ox, oy = kf_to_out(M, lx, ly)
                S *= disk(ox, oy, lr * look.BASE, 12)
            S = np.clip(S, 0, 0.95)
            out = out * (1 - S) + (P * 0.42) * S
        elif mode == 'dark':
            ap = L.appear(t, 0.25) * (1 - L.leave(t))
            m = project(L.block.full(weights=ap), D, kx, ky)
            out = out * (1 - 0.5 * blur(m, 2.0))
            # Verse 2 line 8: the last three characters are caught by a beam, blown out, then gone
            if L.key == 'Verse 2|8':
                n = L.block.n
                ts = L.s[n - 3]
                env = np.clip((t - ts) / 0.06, 0, 1) * np.exp(-max(0.0, t - ts - 0.06) / 0.35)
                if env > 0.002:
                    w = np.zeros(n)
                    w[n - 3:] = 1
                    m3 = project(L.block.full(weights=w), D, kx, ky)
                    grow = 2 + 40 * min(1.0, max(0.0, t - ts) / 0.8)
                    out = out + env * (1.6 * blur(m3, grow * 0.3) + 0.9 * qblur(m3, grow * 2))
        elif mode == 'diffuse':
            a = np.clip((t - (L.s[0] - 0.1)) / 0.6, 0, 1) * (1 - L.leave(t))
            m = L.block.full() * a
            out = out + 0.30 * blur(m, 2.5) + 0.12 * qblur(m, 22)
        elif mode in ('print', 'thin'):
            ap = L.appear(t, 0.35) * (1 - L.leave(t))
            m = L.block.full(weights=ap)
            ms = blur(m, 1.6 if mode == 'thin' else 2.4)
            halo = qblur(cv2.dilate(m, np.ones((15, 15), np.uint8)), 26)
            out = out * (1 - 0.42 * np.clip(halo - ms, 0, 1))
            out = np.maximum(out, ms * 0.95)
        elif mode == 'window':
            ap = L.appear(t, 0.30) * (1 - L.leave(t))
            m = project(L.block.full(weights=ap), D, kx * 0.6, ky * 0.6)
            ms = blur(m, 4.0)
            lit = np.clip(P * 1.35 + 0.16, 0, 1.1)
            out = out * (1 - ms) + lit * ms + qblur(ms, 26) * 0.07
        elif mode == 'cloud':
            ap = L.appear(t, 0.45) * outro_beam(t)
            m = L.block.full(weights=ap)
            pm = project(m, D, 0, -60)
            lit = np.clip(P * 1.5 + 0.12, 0, 1.15)
            out = out * (1 - pm) + lit * pm + qblur(pm, 18) * 0.10

    if sh.id == 's01' and 16.88 <= t < 25.52:                # the title, once, between two bursts of static
        tb = title_block()
        m = project(tb.full(), D, -70, -45)
        lit = np.clip(P * 1.40 + 0.10, 0, 1.15)
        out = out * (1 - m) + lit * m
        out += qblur(m, 10) * 0.08
        x0, y0, x1, y1 = tb.bbox
        beams.append((sh.lyr['src'], ((x0 + x1) / 2, (y0 + y1) / 2), (x1 - x0) * 0.42, 0.11))

    # --- shot effects that light the plate
    if 'point' in sh.fx:
        px, py = kf_to_out(M, *FX['point'])
        k = T.kick(t)
        r2 = (XX - px) ** 2 + (YY - py) ** 2
        out += (0.35 + 0.65 * k) * np.exp(-r2 / (2 * 5 ** 2)) + (0.05 + 0.18 * k) * np.exp(-r2 / (2 * 38 ** 2))
    if 'filament' in sh.fx:
        px, py = kf_to_out(M, *FX['filament'])
        r2 = (XX - px) ** 2 + (YY - py) ** 2
        out += 0.22 * np.exp(-r2 / (2 * 14 ** 2)) + 0.5 * flv * np.exp(-r2 / (2 * 160 ** 2))
    if 'lamps' in sh.fx:
        lm = look.warp(lamp_mask(), M)
        L3 = next(L for L in LINES if L.key == 'Verse 3|3')
        L4 = next(L for L in LINES if L.key == 'Verse 3|4')
        if L3.s[0] - 0.05 <= t < L4.s[0]:
            i = np.searchsorted(T.BEATS, t) - 1
            b0, b1 = T.BEATS[i], T.BEATS[i + 1]
            half = (b1 - b0) / 2
            ph8 = (t - b0) % half
            pulse = np.exp(-ph8 / 0.07)
            out = out + lm * (0.25 + 1.6 * P) * pulse + qblur(lm, 14) * 0.35 * pulse
        else:
            out = out + lm * P * 0.25
    if 'twin' in sh.fx:
        for (lx, ly, dirn) in FX['k16_lamps']:
            ox, oy = kf_to_out(M, lx, ly)
            beams.append(((ox, oy), (ox + dirn * 900, oy + 40), 180, 0.20 * flv))
            r2 = (XX - ox) ** 2 + (YY - oy) ** 2
            out += flv * (0.8 * np.exp(-r2 / (2 * 10 ** 2)))

    # --- beams through the fog
    if beams and ftex is not None:
        acc = np.zeros_like(ftex)
        for src, dst, r1, inten in beams:
            if inten <= 0.002:
                continue
            acc += cone(src, dst, 26, r1) * inten
        out += look.up(acc * (0.35 + ftex))
    if sh.snow > 0:
        out += SNOW.draw(ph, D, sh.snow) * (0.55 if expo == 'night' else 0.9)

    # --- shot effects over everything
    if 'rings' in sh.fx:
        L5 = next(L for L in LINES if L.key == 'Verse 3|5')
        if L5.s[0] - 0.1 <= t < L5.e[-1] + 1.5:
            mx, my = kf_to_out(M, *FX['mast_top'])
            r = np.hypot(XX - mx, YY - my)
            for bt in T.BEATS[(T.BEATS >= L5.s[0] - 0.05) & (T.BEATS < min(t, L5.e[-1]))]:
                age = t - bt
                if age > 1.6:
                    continue
                R = 30 + 650 * age / 1.6
                out += 0.32 * (1 - age / 1.6) * np.exp(-((r - R) / 2.2) ** 2)
    if 'burst' in sh.fx:
        tb = T.B(79, 3)
        if t >= tb:
            age = t - tb
            beat = T.B(79, 4) - tb
            dx_, dy_ = kf_to_out(M, *FX['disc'])
            R = 12 + 4000 * min(1.0, age / 0.18) ** 2
            g = np.exp(-np.hypot(XX - dx_, YY - dy_) / max(R * 0.35, 1))
            lvl = 1.0 if age < beat else np.exp(-(age - beat) / 0.45)
            out = out + (1 - out) * np.clip(g * 3, 0, 1) * lvl
    if 'whitepush' in sh.fx and t >= T.BAND_BACK:
        u = (t - T.BAND_BACK) / (sh.t1 - T.BAND_BACK - 0.5)
        yf = -400 + (H + 1200) * ease(u)
        Wm = np.clip((yf - YY) / 650, 0, 1) * (0.55 + 0.45 * ease(u))
        out = out + (1 - out) * Wm
        if u >= 1:
            out = np.ones_like(out)
    if 'develop' in sh.fx:
        dv = (t - sh.t0) / 1.9
        if dv < 1.6:
            k = np.clip(dv * 1.6 - np.clip(out, 0, 1) * 0.6, 0, 1)
            out = 1 - (1 - out) * k
    if 'dot' in sh.fx:
        td = T.B(95)
        if td <= t < td + 3.0:
            u = ease((t - td) / 2.6)
            x0_, y0_ = kf_to_out(M, 380, 300)
            x1_ = W + 40
            px, py = x0_ + (x1_ - x0_) * u, y0_ + 40 * u
            r2 = (XX - px) ** 2 + (YY - py) ** 2
            outside = 1.0 if px < W - 40 else 0.4
            out = np.maximum(out, 0.95 * np.exp(-r2 / (2 * 3.2 ** 2)) * outside)
    if 'outro' in sh.fx:
        ob = outro_beam(t)
        if ob > 0:
            acc = cone(FX_SRC_B, (495, 470), 40, 380, 1.12) * 0.40 * ob
            F, ftex = look.fog_field(ph, Dq, dens)
            out += look.up(acc * (0.3 + ftex))

    # --- fades
    a = 1.0
    if sh.fade_in:
        st = sh.fade_in_at if sh.fade_in_at is not None else sh.t0
        a *= ease((t - st) / sh.fade_in)
    if sh.fade_out:
        en = sh.fade_out_at if sh.fade_out_at is not None else sh.t1
        a *= 1 - ease((t - (en - sh.fade_out)) / sh.fade_out)
    out = out * a

    out = look.halation(np.clip(out, 0, 1.4), 0.16)
    out = look.film(np.clip(out, 0, 1.2), fk, amp=0.055, weave=True)

    # --- static: bursts flash white for one frame, beds slip the gate one frame
    f = int(round(t * T.FPS))
    flashes = list(T.STATIC_BURST) + [50.30]
    if any(int(round(x * T.FPS)) == f for x in flashes):
        out = 1 - (1 - np.clip(out, 0, 1)) * 0.10
    if 'ships' in sh.fx:
        sn, _ = ship_kills()
        if any(int(round(x * T.FPS)) == f for x in sn):
            out = 1 - (1 - np.clip(out, 0, 1)) * 0.55
    if any(int(round(x * T.FPS)) == f for x in T.STATIC_BED):
        out = np.roll(out, 64, 0)
        out[:64] = 0.0
    if t >= FX['black_at']:
        out = np.zeros_like(out)

    rgb = look.colorize(out, T.prussian(t))
    if 'fish' in sh.fx:
        fm, frgb = fish_parts()
        fmw = look.warp(fm, M)[..., None] * a
        cw = cv2.warpAffine(frgb, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE) * 0.85
        rgb = (rgb.astype(np.float32) * (1 - fmw) + cw * 255 * fmw).clip(0, 255).astype(np.uint8)
    return rgb


FX_SRC_B = (495, 2150)


def outro_beam(t):
    """The upward beam of the last shot: on with Outro line 2, breathing on the 4.19 s pulse, off at the end."""
    L2 = next(L for L in LINES if L.key == 'Outro|2')
    if t < L2.s[0] - 0.3 or t >= FX['lamp_off']:
        return 0.0
    on = ease((t - (L2.s[0] - 0.3)) / 0.5)
    p = 0.0
    for tp in T.OUTRO_PULSES:
        if t >= tp:
            p = max(p, np.exp(-(t - tp) / 1.6))
    return on * (0.72 + 0.28 * p)


# ---- driver -------------------------------------------------------------------------------------------
def render_chunk(k):
    f0, f1 = k * CHUNK, min(T.NFRAMES, (k + 1) * CHUNK)
    out = os.path.join(ROOT, 'work', 'segments', f'c{k:03d}.mkv')
    tmp = out[:-4] + '.tmp.mkv'
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(T.FPS), '-i', '-',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-threads', '1', tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(frame(f / T.FPS).tobytes())
    p.stdin.close()
    p.wait()
    os.replace(tmp, out)
    return k


def main():
    a = sys.argv[1:]
    if a[0] == '--preview':
        os.makedirs(os.path.join(ROOT, 'work', 'preview'), exist_ok=True)
        for s in a[1].split(','):
            t = float(s)
            im = frame(t)
            p = os.path.join(ROOT, 'work', 'preview', f'p_{t:07.2f}.jpg')
            cv2.imwrite(p, im[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 90])
            print(p, flush=True)
        return
    os.makedirs(os.path.join(ROOT, 'work', 'segments'), exist_ok=True)
    n = -(-T.NFRAMES // CHUNK)
    if a[0] == '--chunks':
        todo = [int(x) for x in a[1].split(',')]
        procs = 4
    else:
        procs = int(a[1]) if len(a) > 1 else 4
        todo = [k for k in range(n) if not os.path.exists(os.path.join(ROOT, 'work', 'segments', f'c{k:03d}.mkv'))]
    from multiprocessing import Pool
    with Pool(procs) as pool:
        for k in pool.imap_unordered(render_chunk, todo):
            print('chunk', k, 'done', flush=True)


if __name__ == '__main__':
    main()
