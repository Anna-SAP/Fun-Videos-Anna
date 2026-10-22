#!/usr/bin/env python3
"""NEON x3 — weave three versions of the same 22 seconds of A2O LITE 'NEON' into one 9:16 short.

  render_neon_three_universes.py CARTOON MV STAGE OUT.mp4 [--scale 0.5] [--fast]

  CARTOON  the Higgsfield AI-cartoon clip (filename contains "Comment [neon]"), 1276x718
  MV       A2O LITE 'NEON' Official Video.mkv, 3840x2160 23.976 fps
  STAGE    23 secondes A2O_20261022.mp4, stage performance, 1340x1080 30 fps

All three carry the same music (measured with tools/av/find_offset.py, no drift):
  stage time   = MV time + 1.0626 s        cartoon time = MV time + 0.0407 s
so one master clock T (= MV time) drives every shot, and the edit sits on the song's beat
grid (129.98 BPM; bar n starts at T = 0.196 + n * 1.8465 s).

Layouts  TRI   three stacked bands (cartoon / MV / stage), all in sync
         FULL  one version fills the frame; the crop follows the dancers
Moves    a band grows into the full frame and back (morph); neon-line sweeps between FULL
         shots; a scan line turns the cartoon into the MV where both share a framing;
         hard cut + flash on the drop; freeze-frame end card on the break.
Audio    the stage clip's live ambience for the cold open, then the MV's clean track.

--scale 0.5 --fast renders a 540x960 preview in about a minute.
requires: ffmpeg on PATH, numpy, pillow; fonts from C:/Windows/Fonts (Bahnschrift, Noto Sans SC)
"""
import argparse
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FPS = 30
P = 1.0626                                     # output time t = T + P (the stage clip starts first)
OFFSET = {'C': 0.0407, 'M': 0.0, 'S': 1.0626}  # source time = T + OFFSET
BEAT = 0.461623


def D(bar, beat=0):
    """T of beat `beat` (0-3) in bar `bar`; bar 0 starts on the song's first beat (T = 0.196)."""
    return 9.8902 + (4 * (bar - 5) - 1 + beat) * BEAT


T_START, T_FREEZE, T_END = -P, D(12), 23.5
N_FRAMES = int(round((T_END - T_START) * FPS))

# ---- look ------------------------------------------------------------------------------
CW, CH = 1080, 1920
ORDER = ('C', 'M', 'S')
COLOR = {'C': (255, 95, 210), 'M': (63, 230, 255), 'S': (170, 140, 255)}
LABEL = {'C': '① AI 卡通版', 'M': '② 官方 MV', 'S': '③ 舞台版'}
HEADER, BAND_H, GAP = 210, 540, 16
BAND = {u: (0, HEADER + i * (BAND_H + GAP), CW, BAND_H) for i, u in enumerate(ORDER)}
FULL = (0, 0, CW, CH)
TRI_VIEW = {'C': (0.5, 0.5, 1.0), 'M': (0.5, 0.5, 1.0), 'S': (0.5, 0.56, 0.82)}  # cx, cy, zoom in a band
FONT_DIR = 'C:/Windows/Fonts'
TITLE_FONT = ('bahnschrift.ttf', 'Bold')
CJK_FONT = 'Noto Sans SC Bold (TrueType).otf'

# Where a FULL shot looks: (T, cx, cy, zoom); zoom 1 = the 9:16 window just covers the frame.
# In two-shots the pair stands too far apart for a 9:16 window, so the crop follows the member
# on the right (brown hair) — the same member the stage camera favours. MV / cartoon values come
# from a dark-pixel (hair) track split into left / right clusters; the stage is framed by hand.
FOCUS = {
    'S': [(-1.1, .48, .5, 1.0), (0.2, .48, .5, 1.07), (7.5, .47, .5, 1.0), (23.5, .5, .5, 1.0)],
    'M': [(5.7, .50, .5, 1.0), (6.85, .52, .5, 1.0), (7.0, .57, .5, 1.0), (7.43, .57, .5, 1.0),
          (7.47, .27, .5, 1.0), (7.6, .27, .5, 1.0), (10.8, .39, .5, 1.0), (11.8, .40, .5, 1.0),
          (13.5, .55, .5, 1.0), (13.93, .61, .5, 1.0), (13.97, .84, .5, 1.0), (14.2, .83, .5, 1.0),
          (14.5, .72, .5, 1.0), (15.0, .68, .5, 1.0), (17.6, .69, .5, 1.0), (18.0, .67, .5, 1.0),
          (18.4, .73, .5, 1.0), (19.6, .72, .5, 1.0), (20.0, .66, .5, 1.0), (20.5, .64, .5, 1.0)],
    'C': [(9.7, .53, .5, 1.0), (10.9, .56, .5, 1.0), (12.5, .62, .5, 1.0), (12.9, .63, .5, 1.0),
          (13.3, .70, .5, 1.0), (13.8, .69, .5, 1.0), (18.5, .78, .5, 1.0), (18.8, .78, .5, 1.0),
          (19.0, .72, .5, 1.0), (19.3, .66, .5, 1.0), (19.6, .63, .5, 1.0)],
}

# ---- edit ------------------------------------------------------------------------------
# (T of the cut, layout, universe shown full-frame, transition into this shot)
SHOTS = [
    (T_START,  'FULL', 'S', None),        # cold open: stage close-up, live ambience, title flickers on
    (D(0),     'TRI',  None, 'assemble'),  # first beat: the frame splits into three universes
    (D(3),     'FULL', 'M',  'morph'),     # MV face close-up, then the two point at the camera
    (D(4),     'FULL', 'S',  'drop'),      # the drop: hard cut to the stage rush
    (D(5, 1),  'FULL', 'C',  'sweep'),     # cuts on the accent (beat 2) and on beat 4 of each bar
    (D(5, 3),  'FULL', 'M',  'scan'),      #   same wide framing: the scan line turns cartoon into MV
    (D(6, 1),  'FULL', 'S',  'sweep'),
    (D(6, 3),  'FULL', 'C',  'sweep'),
    (D(7, 1),  'FULL', 'M',  'scan'),
    (D(8),     'TRI',  None, 'morph'),     # regroup; A2O logo and "Stage 1" play in the top bands
    (D(9, 3),  'FULL', 'S',  'morph'),     # ...and "Stage 1" pushes into the stage
    (D(10),    'FULL', 'C',  'sweep'),
    (D(10, 2), 'FULL', 'M',  'sweep'),
    (D(11),    'TRI',  None, 'morph'),     # the group formation, side by side
    (T_FREEZE, 'TRI',  None, 'freeze'),    # the break: freeze-frame end card
]
TRANS = {None: (0, 0), 'assemble': (0, 0.62), 'morph': (0, 0.40), 'drop': (0, 0),
         'sweep': (0.10, 0.24), 'scan': (0.20, 0.46), 'freeze': (0, 0)}  # (lead, duration) in s
SWEEP_ANGLE = {'sweep': (12, 192), 'scan': (90, 90)}        # alternating directions
PUNCH = [(D(4), .10, .20), (D(5), .035, .15), (D(6), .035, .15), (D(7), .035, .15)]  # (T, zoom, tau)
FLASH = [(D(4), .55, .22), (T_FREEZE, .45, .25)]          # (T, strength, duration)
RGB_SPLIT = [(D(4), 14, .22)]                              # (T, pixels, duration)
FLICKER = [(-0.99, -0.95), (-0.86, -0.83), (-0.74, -0.70), (-0.62, -0.60)]  # title off-blinks


def ease(p):                         # ease-in-out cubic
    p = min(max(p, 0.0), 1.0)
    return 4 * p ** 3 if p < .5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_out(p):
    p = min(max(p, 0.0), 1.0)
    return 1 - (1 - p) ** 3


def lerp(a, b, e):
    return tuple(x + (y - x) * e for x, y in zip(a, b))


def decay(T, events):
    """Sum of decaying pulses: events are (T0, amount, duration)."""
    v = 0.0
    for t0, amt, dur in events:
        if t0 <= T < t0 + dur:
            v += amt * (1 - (T - t0) / dur) ** 2
    return v


# ---- sources ---------------------------------------------------------------------------
class Source:
    """Decodes one clip straight onto the output clock: frame i shows source time T(i) + OFFSET."""

    def __init__(self, path, delay, size, limit=None):
        self.w, self.h = size
        vf = (f"scale={self.w}:{self.h}:flags=lanczos,setsar=1,"
              f"tpad=start_duration={delay:.4f}:start_mode=clone,fps={FPS},"
              f"tpad=stop_mode=clone:stop_duration=10")
        cmd = ['ffmpeg', '-v', 'error'] + (['-t', str(limit)] if limit else []) + \
              ['-i', path, '-an', '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=self.w * self.h * 3 * 2)

    def read(self):
        n = self.w * self.h * 3
        buf = self.proc.stdout.read(n)
        if len(buf) < n:
            raise RuntimeError('source ended early')
        img = Image.frombuffer('RGB', (self.w, self.h), buf, 'raw', 'RGB', 0, 1)
        k = max(1, self.w // 120)
        small = img.reduce(k).filter(ImageFilter.GaussianBlur(2)).point(lambda v: v * 0.78)
        return img, small


# ---- drawing helpers -------------------------------------------------------------------
def neon_text(text, font, color, core=True):
    """Neon-sign text as an RGBA image; returns (image, ink box (x0, y0, x1, y1) inside it)."""
    x0, y0, x1, y1 = font.getbbox(text)
    pad = int(font.size * 0.55) + 8
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).text((pad - x0, pad - y0), text, font=font, fill=255)
    pm = np.zeros((h, w, 3), np.float32)       # premultiplied colour
    al = np.zeros((h, w, 1), np.float32)

    def over(rgb, a):
        a = np.clip(a, 0, 1)[..., None]
        pm[:] = np.array(rgb, np.float32) * a + pm * (1 - a)
        al[:] = a + al * (1 - a)

    ma = np.asarray(m, np.float32) / 255
    for r, k in ((font.size * 0.32, 1.1), (font.size * 0.12, 1.6), (font.size * 0.04, 1.4)):
        over(color, np.asarray(m.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255 * k)
    over(color, ma)
    if core:
        er = max(3, int(font.size * 0.05) | 1)
        c = m.filter(ImageFilter.MinFilter(er)).filter(ImageFilter.GaussianBlur(max(1, font.size * 0.012)))
        over((255, 255, 255), np.asarray(c, np.float32) / 255 * 0.95)
    rgb = pm / np.maximum(al, 1e-4)
    img = Image.fromarray(np.concatenate([rgb, al * 255], 2).clip(0, 255).astype(np.uint8), 'RGBA')
    return img, (pad, pad, pad + x1 - x0, pad + y1 - y0)


def plain_text(text, font, fill=(255, 255, 255), shadow=0.75):
    x0, y0, x1, y1 = font.getbbox(text)
    pad = int(font.size * 0.4) + 4
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    sh = Image.new('L', (w, h), 0)
    ImageDraw.Draw(sh).text((pad - x0, pad - y0), text, font=font, fill=255)
    a = np.asarray(sh.filter(ImageFilter.GaussianBlur(font.size * 0.18)), np.float32) / 255 * shadow
    out = np.zeros((h, w, 4), np.float32)
    out[..., 3] = a
    t = Image.new('L', (w, h), 0)
    ImageDraw.Draw(t).text((pad - x0, pad - y0), text, font=font, fill=255)
    ta = np.asarray(t, np.float32)[..., None] / 255
    out[..., :3] = np.array(fill, np.float32) * ta
    out[..., 3:] = out[..., 3:] * (1 - ta) + ta
    out[..., 3] *= 255
    return Image.fromarray(out.clip(0, 255).astype(np.uint8), 'RGBA'), (pad, pad, pad + x1 - x0, pad + y1 - y0)


def pill(text, font, color, S):
    x0, y0, x1, y1 = font.getbbox(text)
    ph = int(round(58 * S))
    dot = int(round(15 * S))
    padx = int(round(20 * S))
    w = padx + dot + int(12 * S) + (x1 - x0) + padx
    img = Image.new('RGBA', (w, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, ph - 1], radius=ph // 2, fill=(8, 6, 22, 165),
                        outline=color + (230,), width=max(1, int(round(2 * S))))
    cy = ph // 2
    d.ellipse([padx, cy - dot // 2, padx + dot, cy + dot // 2], fill=color + (255,))
    d.text((padx + dot + int(12 * S) - x0, cy - (y0 + y1) / 2), text, font=font, fill=(255, 255, 255, 255))
    return img


class Renderer:
    def __init__(self, S, fast):
        self.S = S
        self.cw, self.ch = int(round(CW * S)), int(round(CH * S))
        self.rs = Image.BILINEAR if fast else Image.LANCZOS
        yy, xx = np.mgrid[0:self.ch, 0:self.cw].astype(np.float32)
        self.xx, self.yy = xx, yy
        self._fields = {}

        tf = ImageFont.truetype(f'{FONT_DIR}/{TITLE_FONT[0]}', int(230 * S))
        tf.set_variation_by_name(TITLE_FONT[1])
        tf_small = ImageFont.truetype(f'{FONT_DIR}/{TITLE_FONT[0]}', int(230 * 0.42 * S))
        tf_small.set_variation_by_name(TITLE_FONT[1])
        cjk = lambda px: ImageFont.truetype(f'{FONT_DIR}/{CJK_FONT}', int(round(px * S)))
        self.title = neon_text('NEON', tf, (255, 70, 200))
        self.x3 = neon_text('×3', tf_small, (63, 230, 255))
        self.sub = plain_text('同一段旋律 · 三个宇宙', cjk(54))
        self.question = neon_text('你更爱哪个宇宙？', cjk(66), (255, 90, 210))
        self.hint = plain_text('评论区打 1 / 2 / 3', cjk(34))
        self.credit = plain_text('素材：A2O LITE《NEON》官方 MV · 舞台片段 · Higgsfield AI 卡通版（版权归原作者）',
                                 cjk(21), fill=(220, 220, 235))
        self.pills = {u: pill(LABEL[u], cjk(34), COLOR[u], S) for u in ORDER}

    @staticmethod
    def vignette(arr, k):
        """Darken corners and the top strip (where the label sits) of a full-frame view by k (0-1)."""
        if k <= 0.01:
            return arr
        h, w = arr.shape[:2]
        y, x = np.ogrid[0:h, 0:w]
        r2 = (x / w - .5) ** 2 * 1.2 + (y / h - .5) ** 2
        v = (1 - 0.5 * np.clip(r2 - 0.1, 0, None)) * (1 - 0.32 * np.clip(1 - y / (0.16 * h), 0, 1))
        return arr * (1 + (v[..., None] - 1) * k)

    def cover(self, small, pw, ph):
        sw, sh = small.size
        if sw / sh > pw / ph:
            bw = sh * pw / ph
            box = ((sw - bw) / 2, 0, (sw + bw) / 2, sh)
        else:
            bh = sw * ph / pw
            box = (0, (sh - bh) / 2, sw, (sh + bh) / 2)
        return small.resize((pw, ph), Image.BILINEAR, box=box)

    # -- geometry
    def R(self, rect):
        return tuple(int(round(v * self.S)) for v in rect)

    def field(self, angle):
        if angle not in self._fields:
            a = np.deg2rad(angle)
            d = self.xx * np.cos(a) + self.yy * np.sin(a)
            self._fields[angle] = ((d - d.min()) / (d.max() - d.min()))[..., None]
        return self._fields[angle]

    # -- one universe in a pw x ph window
    def view(self, frame, pw, ph, cx, cy, z):
        src, small = frame
        W, H = src.size
        s = max(pw / W, ph / H) * z
        ww, wh = pw / s, ph / s
        x0 = min(max(cx * W - ww / 2, 0), W - ww) if ww <= W else (W - ww) / 2
        y0 = min(max(cy * H - wh / 2, 0), H - wh) if wh <= H else (H - wh) / 2
        if ww <= W + 1e-6 and wh <= H + 1e-6:
            return np.asarray(src.resize((pw, ph), self.rs, box=(x0, y0, x0 + ww, y0 + wh)), np.float32)
        # window wider/taller than the frame: blurred cover fill behind the whole frame
        bg = self.cover(small, pw, ph)
        sx0, sy0 = max(x0, 0), max(y0, 0)
        sx1, sy1 = min(x0 + ww, W), min(y0 + wh, H)
        dw, dh = int(round((sx1 - sx0) * s)), int(round((sy1 - sy0) * s))
        part = src.resize((max(dw, 1), max(dh, 1)), self.rs, box=(sx0, sy0, sx1, sy1))
        bg.paste(part, (int(round((sx0 - x0) * s)), int(round((sy0 - y0) * s))))
        return np.asarray(bg, np.float32)

    def paste(self, canvas, arr, x, y, alpha=1.0):
        h, w = arr.shape[:2]
        x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, self.cw), min(y + h, self.ch)
        if x1 <= x0 or y1 <= y0:
            return
        sub = arr[y0 - y:y1 - y, x0 - x:x1 - x]
        if sub.shape[2] == 4:
            a = sub[..., 3:] / 255 * alpha
            canvas[y0:y1, x0:x1] = canvas[y0:y1, x0:x1] * (1 - a) + sub[..., :3] * a
        elif alpha >= 1:
            canvas[y0:y1, x0:x1] = sub
        else:
            canvas[y0:y1, x0:x1] = canvas[y0:y1, x0:x1] * (1 - alpha) + sub * alpha

    def blit(self, canvas, layer, cx, cy, scale=1.0, alpha=1.0):
        """Place an RGBA text layer so that its ink centre lands on (cx, cy) canvas pixels."""
        img, (ix0, iy0, ix1, iy1) = layer
        if alpha <= 0.01:
            return
        if abs(scale - 1) > 1e-3:
            img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
            ix0, iy0, ix1, iy1 = (v * scale for v in (ix0, iy0, ix1, iy1))
        x = int(round(cx - (ix0 + ix1) / 2))
        y = int(round(cy - (iy0 + iy1) / 2))
        self.paste(canvas, np.asarray(img, np.float32), x, y, alpha)

    def border(self, canvas, rect, color, k):
        if k <= 0.02:
            return
        x, y, w, h = rect
        q = 4
        g = Image.new('RGB', (self.cw // q + 1, self.ch // q + 1))
        ImageDraw.Draw(g).rectangle([x / q, y / q, (x + w) / q, (y + h) / q], outline=color,
                                    width=max(1, int(round(2 * self.S))))
        g = g.filter(ImageFilter.GaussianBlur(max(1.0, 3 * self.S)))
        ga = np.asarray(g.resize((self.cw, self.ch), Image.BILINEAR, box=(0, 0, self.cw / q, self.ch / q)),
                        np.float32)
        canvas += ga * (1.6 * k)
        lw = max(1, int(round(3 * self.S)))
        col = np.array(color, np.float32) * 0.45 + 255 * 0.55
        # clamp both ends: a negative stop would wrap around and paint the whole row
        for y0, y1, x0, x1 in ((y, y + lw, x, x + w), (y + h - lw, y + h, x, x + w),
                               (y, y + h, x, x + lw), (y, y + h, x + w - lw, x + w)):
            y0, y1 = min(max(y0, 0), self.ch), min(max(y1, 0), self.ch)
            x0, x1 = min(max(x0, 0), self.cw), min(max(x1, 0), self.cw)
            if y1 > y0 and x1 > x0:
                canvas[y0:y1, x0:x1] = canvas[y0:y1, x0:x1] * (1 - k) + col * k

    def panel(self, canvas, frames, u, rect, view, label_alpha=1.0):
        """Draw universe u into rect (1080x1920 units) with view (cx, cy, z), plus border and label."""
        x, y, w, h = self.R(rect)
        if w < 4 or h < 4:
            return
        fullness = min(max((rect[3] - BAND_H) / (CH - BAND_H), 0), 1)
        arr = self.vignette(self.view(frames[u], w, h, *view), fullness)
        self.paste(canvas, arr, x, y)
        self.border(canvas, (x, y, w, h), COLOR[u], 1 - fullness)
        pl = self.pills[u]
        off = (22 + 140 * fullness) * self.S
        self.paste(canvas, np.asarray(pl, np.float32), x + int(24 * self.S), y + int(off), label_alpha)

    # -- the edit at master time T
    def focus(self, u, T):
        ks = FOCUS[u]
        ts = [k[0] for k in ks]
        cx, cy, z = (float(np.interp(T, ts, [k[i] for k in ks])) for i in (1, 2, 3))
        punch = 1 + decay(T, PUNCH)
        return cx, cy, z * punch

    def frame(self, T, frames):
        S = self.S
        k = max(i for i, s in enumerate(SHOTS) if T >= s[0] - TRANS[s[3]][0])
        Tcut, layout, u, trans = SHOTS[k]
        lead, dur = TRANS[trans]
        p = 1.0 if dur == 0 else (T - (Tcut - lead)) / dur
        prev = SHOTS[k - 1] if k else None

        # background: the stage, blurred and darkened (visible around the bands)
        canvas = np.asarray(self.cover(frames['S'][1], self.cw, self.ch), np.float32) * 0.42

        def tri(skip=None):
            for v in ORDER:
                if v != skip:
                    self.panel(canvas, frames, v, BAND[v], TRI_VIEW[v])

        fullness = 1.0
        if p < 1 and trans in ('assemble', 'morph'):
            e = ease(p)
            if layout == 'FULL':                       # a band grows into the full frame
                tri(skip=u)
                self.panel(canvas, frames, u, lerp(BAND[u], FULL, e), lerp(TRI_VIEW[u], self.focus(u, T), e))
                fullness = e
            else:                                      # the full frame shrinks back into its band
                v = prev[2]
                if trans == 'assemble':
                    for j, w in enumerate(('C', 'M')):
                        ej = ease_out((T - Tcut - 0.23 * j) / 0.42)
                        dx = (-1 if j == 0 else 1) * CW * (1 - ej)
                        x, y, ww, hh = BAND[w]
                        self.panel(canvas, frames, w, (x + dx, y, ww, hh), TRI_VIEW[w], label_alpha=ej)
                else:
                    tri(skip=v)
                self.panel(canvas, frames, v, lerp(FULL, BAND[v], e), lerp(self.focus(v, T), TRI_VIEW[v], e))
                fullness = 1 - e
        elif p < 1 and trans in ('sweep', 'scan'):     # neon line wipes one universe into the next
            v = prev[2]
            a_out = self.view(frames[v], self.cw, self.ch, *self.focus(v, T))
            a_in = self.view(frames[u], self.cw, self.ch, *self.focus(u, T))
            n_sw = sum(1 for s in SHOTS[:k] if s[3] == trans)
            d = self.field(SWEEP_ANGLE[trans][n_sw % 2])
            q = -0.06 + 1.12 * ease(p)
            soft = 0.004
            m = np.clip((q - d) / soft + 0.5, 0, 1)
            canvas = self.vignette(a_out * (1 - m) + a_in * m, 1.0)
            sig = 0.010 if trans == 'sweep' else 0.016
            g = np.exp(-((d - q) / sig) ** 2)
            col = np.array(COLOR[u], np.float32)
            canvas += g * (col * 0.9 + 60) * 1.4 + np.exp(-((d - q) / (sig * 5)) ** 2) * col * 0.35
            pe = ease(p)
            self.paste(canvas, np.asarray(self.pills[v], np.float32), int(24 * S), int(162 * S), 1 - pe)
            self.paste(canvas, np.asarray(self.pills[u], np.float32), int(24 * S), int(162 * S), pe)
        elif layout == 'FULL':
            self.panel(canvas, frames, u, FULL, self.focus(u, T))
        else:
            tri()
            fullness = 0.0

        # --- titles
        e_as = ease(min(max((T - D(0)) / 0.62, 0), 1))
        head_cx, head_title_y, head_sub_y = 540 * S, 84 * S, 172 * S
        x3_w = (self.x3[1][2] - self.x3[1][0])
        gap = 22 * S
        neon_w = (self.title[1][2] - self.title[1][0]) * 0.42
        neon_head_cx = head_cx - (x3_w + gap) / 2
        if T < T_FREEZE:
            tri_alpha = 1 - fullness if T >= D(0) + 0.62 else 1.0
            blink = 0.12 if any(a <= T < b for a, b in FLICKER) else 1.0
            sc = 1 + (0.42 - 1) * e_as
            self.blit(canvas, self.title, (540 * S) + (neon_head_cx - 540 * S) * e_as,
                      1330 * S + (head_title_y - 1330 * S) * e_as, sc, blink * tri_alpha)
            sub_a = min(max((T + 0.75) / 0.35, 0), 1) * tri_alpha
            self.blit(canvas, self.sub, head_cx, 1490 * S + (head_sub_y - 1490 * S) * e_as,
                      1 + (36 / 54 - 1) * e_as, sub_a)
            px = min(max((T - D(0, 1)) / 0.18, 0), 1)
            if px > 0:
                self.blit(canvas, self.x3, neon_head_cx + neon_w / 2 + gap + x3_w / 2, head_title_y,
                          1 + 0.6 * (1 - ease_out(px)), px * tri_alpha)
        else:
            a = min((T - T_FREEZE) / 0.3, 1)
            self.blit(canvas, self.question, head_cx, 80 * S, 0.8 + 0.2 * ease_out(a), a)
            self.blit(canvas, self.hint, head_cx, 166 * S, 1.0, a)
            self.blit(canvas, self.credit, head_cx, 1891 * S, 1.0, 0.85 * a)

        # --- hit effects
        sh = int(round(decay(T, RGB_SPLIT) * S))
        if sh:
            canvas[:, sh:, 0] = canvas[:, :-sh, 0].copy()
            canvas[:, :-sh, 2] = canvas[:, sh:, 2].copy()
        fl = decay(T, FLASH)
        if fl:
            canvas += (255 - canvas) * fl
        return np.clip(canvas, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cartoon')
    ap.add_argument('mv')
    ap.add_argument('stage')
    ap.add_argument('out')
    ap.add_argument('--scale', type=float, default=1.0)
    ap.add_argument('--fast', action='store_true', help='bilinear resampling + fast x264 preset')
    a = ap.parse_args()

    S = a.scale
    mv_size = (3840, 2160) if S >= 1 else (int(3840 * S) // 2 * 2, int(2160 * S) // 2 * 2)
    srcs = {
        'C': Source(a.cartoon, P - OFFSET['C'], (1276, 718)),
        'M': Source(a.mv, P - OFFSET['M'], mv_size, limit=T_END + 2),
        'S': Source(a.stage, P - OFFSET['S'], (1340, 1080)),
    }
    r = Renderer(S, a.fast)
    tmp = os.path.splitext(a.out)[0] + '.video.mp4'
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                            '-s', f'{r.cw}x{r.ch}', '-r', str(FPS), '-i', '-',
                            '-c:v', 'libx264', '-preset', 'veryfast' if a.fast else 'slow', '-crf', '18',
                            '-profile:v', 'high', '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
    frozen = None
    for i in range(N_FRAMES):
        T = T_START + i / FPS
        frames = {u: s.read() for u, s in srcs.items()}
        if T >= T_FREEZE:
            frozen = frozen or frames
            frames = frozen
        enc.stdin.write(r.frame(T, frames).tobytes())
        if i % 60 == 0:
            print(f'frame {i}/{N_FRAMES}  T={T:6.2f}', file=sys.stderr, flush=True)
    enc.stdin.close()
    enc.wait()
    for s in srcs.values():
        s.proc.kill()

    mux_audio(tmp, a.stage, a.mv, a.out)
    os.remove(tmp)
    print(f'written {a.out}  ({N_FRAMES} frames, {N_FRAMES / FPS:.2f} s)', file=sys.stderr)


def mux_audio(video, stage, mv, out):
    """Stage ambience under the cold open, then the MV track (delayed by P), faded out at the end.
    The MV is mastered hot (-10.6 LUFS, decoded peaks +2 dBFS): -3.5 dB and a -1.4 dB limiter
    bring it to -14 LUFS. AAC at 192k still overshot to +0.2 dBTP on the beat-2 snare at
    T = 9.9 s; 256k keeps the true peak at -0.6 dBTP."""
    t_end = N_FRAMES / FPS
    delay = int(round(P * 48000))
    fc = (f"[1:a]aresample=48000,atrim=0:1.30,afade=t=out:st=1.08:d=0.20,volume=0.9[a0];"
          f"[2:a]aresample=48000,atrim=0:{T_END + 0.5},adelay={delay}S:all=1,"
          f"afade=t=out:st={t_end - 0.9:.3f}:d=0.9[a1];"
          f"[a0][a1]amix=inputs=2:normalize=0:duration=longest,atrim=0:{t_end:.3f},"
          f"volume=-3.5dB,alimiter=limit=0.85:level=0[a]")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', stage, '-t', str(T_END + 2), '-i', mv,
                    '-filter_complex', fc, '-map', '0:v', '-map', '[a]', '-c:v', 'copy',
                    '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-movflags', '+faststart', out], check=True)


if __name__ == '__main__':
    main()
