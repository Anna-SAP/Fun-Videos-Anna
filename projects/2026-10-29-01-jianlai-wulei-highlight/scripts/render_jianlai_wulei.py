#!/usr/bin/env python3
"""剑来 · 陈平安 — cut the 3:14 trailer down to a 9:16 short of Wu Lei's solo shots only.

  render_jianlai_wulei.py TRAILER OUT.mp4 [--scale 0.5] [--fast] [--work DIR]

  TRAILER  吴磊《剑来》最新预告.mp4, 1920x1080 25 fps; the picture sits in x 150..1770
           (black side bars), bilingual subtitles are burnt in at y 895..985 and the
           Tencent Video watermark at x 1487..1790, y 50..128 (delogo'd on decode).

Edit (all times on the output clock; source times in the SHOTS table):
  0.00  hook      three 0.33 s glitch flashes: spark burst, bloodied snarl, choking face
  0.99  voice     his own lines over the forge, kinetic captions:
                  去路不由己 / 但我还是想 / 为自己 / 争一争   (source 117.5-123.3 s)
  9.42  strike    the hammer hits, sparks, zoom-blur into the climax
 10.00  beat      the score's climax (102 BPM, an accent every 1.1775 s) from 见自由 on;
                  one shot per accent, then per beat, then eight quarter-beat flashes
 22.93  finale    slow-motion spark burst, whip-pan from the fist to the face, the
                  bloodied close-up, the score's silence, then the title hit (28.39)
Audio  trailer audio in three pieces (116.30-126.30, 146.96-159.89, 171.84-180.6) — all
       speech kept is Chen Ping'an's — plus synthesized impacts, whooshes and a riser.
Crops  9:16 windows follow his face; shots with burnt-in subtitles use a window that
       ends above y 888, so the trailer's own subtitles never show.

--scale 0.5 --fast renders a 540x960 preview in about a minute.
requires: ffmpeg on PATH, numpy, scipy, pillow; fonts from C:/Windows/Fonts
(Source Han Serif SC Heavy, STXINGKA, Bahnschrift)
"""
import argparse
import json
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.signal import lfilter

FPS = 25
CW, CH = 1080, 1920
SRC_W, SRC_H = 1920, 1080
AX0, AW = 150, 1620              # active picture between the black side bars
SUB_TOP = 888                    # burnt-in subtitles start below this line
WM = (1476, 40, 1806, 138)       # Tencent Video watermark (full-frame px), removed with delogo
BEAT = 1.1775 / 2                # 101.9 BPM; accents fall on every second beat
T_END = 31.60

FONT_DIR = 'C:/Windows/Fonts'
SERIF = 'Source Han Serif SC Heavy (TrueType).ttf'
BRUSH = 'STXINGKA.TTF'
LATIN = ('bahnschrift.ttf', 'SemiBold')

# ---- audio: (output start, source start, source end) ------------------------------------
AUDIO = [(0.00, 116.30, 126.30),     # voice-over over the forge
         (10.00, 146.96, 159.89),    # 见自由 + the climax on its accent grid
         (22.93, 171.84, 180.60)]    # spark burst, close-up, silence, title hit

# ---- shots ------------------------------------------------------------------------------
# (out_in, out_out, src_in, speed, cx, cy, h, push, extra)
#   cx, cy  window centre as a fraction of the active picture (1620 x 1080)
#   h       window height in source px (1080 = full height); 'top' shots keep their bottom
#           edge above the burnt-in subtitles
#   push    zoom at the start and end of the shot
#   extra   'pan' keyframes [(local t, cx)], 'top', 'freeze', 'sharp'
TOP = SUB_TOP / 2 / SRC_H        # cy that puts an 888-px window flush with the top
Q = BEAT / 2                     # quarter of an accent
FL = 19.41                       # start of the eight quarter-beat flashes
SHOTS = [
    # hook
    (0.00, 0.33, 173.10, 1.0, .62, .45, 1080, (1.06, 1.0), {}),           # spark burst
    (0.33, 0.66, 174.90, 1.0, .48, .42, 960, (1.04, 1.0), {}),            # bloodied snarl
    (0.66, 0.99, 136.70, 1.0, .47, .45, 1080, (1.05, 1.0), {}),           # choking, blood thread
    # voice-over: 去路不由己 / 但我还是想 / 为自己 / 争一争
    (0.99, 2.10, 115.95, 1.0, .49, .50, 1080, (1.0, 1.08), {}),          # bloodied, head down
    (2.10, 3.20, 118.05, 1.0, .50, TOP, 888, (1.0, 1.06), {'top': 1}),   # sweat, eyes up
    (3.20, 6.02, 119.55, 0.976, .49, TOP, 888, (1.0, 1.12), {'top': 1}), # robe drops, sparks
    (6.02, 7.46, 122.33, 1.0, .56, TOP, 888, (1.02, 1.10), {'top': 1}),  # at the forge
    (7.46, 8.30, 123.80, 1.0, .50, .50, 1080, (1.0, 1.06), {}),          # shoulder, embers
    (8.30, 9.42, 124.94, 0.68, .52, .50, 1080, (1.0, 1.12), {}),         # hammer up (slow)
    (9.42, 10.00, 125.74, 1.0, .45, .55, 1080, (1.08, 1.0), {}),         # the strike
    # climax, one shot per accent
    (10.00, 11.78, 147.06, 1.0, .52, TOP, 888, (1.0, 1.10), {'top': 1}), # 见自由, rain
    (11.78, 13.04, 50.00, 1.0, .56, TOP, 888, (1.0, 1.08), {'top': 1}),  # straw hat
    (13.04, 13.70, 57.80, 1.0, .50, .50, 1080, (1.06, 1.0), {}),         # debris, back
    (13.70, 14.71, 60.10, 1.0, .50, .50, 1080, (1.06, 1.0), {}),         # debris, face
    (14.71, 15.89, 47.90, 0.60, .24, .50, 1080, (1.0, 1.05), {}),        # above the valley
    (15.89, 16.48, 135.00, 1.0, .47, .45, 1080, (1.06, 1.0), {}),        # thrown in the fog
    (16.48, 17.06, 136.50, 1.0, .47, .45, 1080, (1.06, 1.0), {}),        # blood thread
    (17.06, 17.65, 141.35, 1.0, .48, TOP, 888, (1.06, 1.0), {'top': 1}), # mud on his face
    (17.65, 18.29, 142.55, 1.0, .52, TOP, 888, (1.0, 1.06), {'top': 1}), # through the door
    (18.29, 19.41, 42.00, 1.0, .70, TOP, 888, (1.0, 1.06), {'top': 1}),  # firelight
    # quarter-beat flashes
    (FL + 0 * Q, FL + 1 * Q, 118.60, 1.0, .50, TOP, 888, (1.08, 1.0), {'top': 1}),
    (FL + 1 * Q, FL + 2 * Q, 121.40, 1.0, .50, TOP, 888, (1.08, 1.0), {'top': 1}),
    (FL + 2 * Q, FL + 3 * Q, 125.55, 1.0, .50, .50, 1080, (1.08, 1.0), {}),
    (FL + 3 * Q, FL + 4 * Q, 51.00, 1.0, .56, TOP, 888, (1.08, 1.0), {'top': 1}),
    (FL + 4 * Q, FL + 5 * Q, 148.40, 1.0, .52, TOP, 888, (1.08, 1.0), {'top': 1}),
    (FL + 5 * Q, FL + 6 * Q, 61.50, 1.0, .50, .50, 1080, (1.08, 1.0), {}),
    (FL + 6 * Q, FL + 7 * Q, 141.90, 1.0, .48, TOP, 888, (1.08, 1.0), {'top': 1}),
    (FL + 7 * Q, 21.76, 116.80, 1.0, .49, .50, 1080, (1.08, 1.0), {}),
    (21.76, 22.93, 67.95, 1.0, .46, .45, 980, (1.0, 1.16), {}),          # hand raised
    # finale (in sync with the score again)
    (22.93, 24.85, 172.32, 0.74, .66, .45, 1080, (1.04, 1.0),            # fist -> face
     {'pan': [(0.0, .24), (0.12, .24), (0.62, .66), (9.0, .68)]}),
    (24.85, 27.43, 173.78, 1.0, .48, .45, 1080, (1.0, 1.10), {}),        # the close-up
    (27.43, 28.39, 176.36, 0.25, .48, .45, 1080, (1.10, 1.22), {'silence': 1}),
    (28.39, T_END, 175.30, 0.0, .48, .42, 1080, (1.06, 1.14), {'card': 1}),
]

# ---- hits: (T, flash, punch, shake px, rgb px) ------------------------------------------
HITS = [(0.00, .55, .12, 22, 18), (0.33, .35, .08, 16, 14), (0.66, .35, .08, 16, 14),
        (0.99, .25, .06, 0, 6), (2.10, 0, .03, 0, 0), (3.20, .12, .04, 0, 4),
        (6.02, .12, .04, 6, 4), (6.62, 0, .06, 16, 8), (7.46, 0, .03, 0, 0), (8.30, .08, .03, 0, 0),
        (9.42, .60, .10, 22, 12), (10.00, .70, .10, 18, 14),
        (11.78, .15, .05, 0, 4), (13.04, .30, .07, 14, 8), (13.70, .30, .07, 14, 8),
        (14.71, .15, .04, 0, 4), (15.89, .22, .05, 10, 6), (16.48, .22, .05, 10, 6),
        (17.06, .25, .06, 10, 6), (17.65, .18, .05, 8, 5), (18.29, .22, .05, 8, 5),
        (21.76, .25, .06, 10, 8), (22.93, .75, .12, 24, 18), (24.85, .65, .12, 22, 16),
        (28.39, .95, .15, 30, 20)]
HITS += [(FL + i * Q, .10, .06, 8, 8) for i in range(8)]   # keep the strobe gentle
GLITCH = [(0.00, 0.20), (0.33, 0.16), (0.66, 0.16)]
ZOOM_BLUR = [(10.00, 0.14)]
EMBERS = [(3.20, 10.00), (22.93, T_END)]

# ---- captions: (in, out, 中文, English, style) -------------------------------------------
CAPTIONS = [
    (1.22, 3.10, '去路不由己', 'Our path is not ours to choose.', 'ember'),
    (3.24, 4.74, '但我还是想', 'Still, I want to try.', 'ember'),
    (4.80, 6.42, '为自己', 'To fight', 'fire'),
    (6.62, 8.30, '争一争', 'for my own fate.', 'slam'),
    (10.30, 11.70, '见自由', 'To see freedom.', 'teal'),   # vertical, beside his face
]
VERTICAL = {'teal'}
HEADER = (1.05, 9.30)           # 《剑来》 · 吴磊 饰 陈平安 at the top during the voice-over
STYLE = {'ember': (255, 150, 60), 'fire': (255, 120, 40), 'slam': (255, 176, 64), 'teal': (80, 220, 255)}


def ease(p):
    p = min(max(p, 0.0), 1.0)
    return 4 * p ** 3 if p < .5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_out(p):
    p = min(max(p, 0.0), 1.0)
    return 1 - (1 - p) ** 3


def back_out(p, s=1.8):
    p = min(max(p, 0.0), 1.0) - 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def pulse(T, t0, dur):
    """1 at t0, falling to 0 at t0 + dur (quadratic)."""
    return (1 - (T - t0) / dur) ** 2 if t0 <= T < t0 + dur else 0.0


def font(name, px, var=None):
    f = ImageFont.truetype(f'{FONT_DIR}/{name}', max(1, int(round(px))))
    if var:
        f.set_variation_by_name(var)
    return f


# ---- text sprites -----------------------------------------------------------------------
def advance(fnt, c):
    # the CJK fonts map ' ' and '·' to a tofu box: draw those two ourselves
    return fnt.size * 0.4 if c in ' ·' else fnt.getlength(c)


def glow_sprite(text, fnt, fill, glow, glow_r, glow_k=1.0, shadow=0.9, stroke=0, tracking=0):
    """RGBA sprite: dark shadow for legibility, coloured glow, then the letters."""
    widths = [advance(fnt, c) for c in text]
    tw = sum(widths) + tracking * (len(text) - 1)
    asc, desc = fnt.getmetrics()
    pad = int(glow_r * 2.2 + stroke + 6)
    w, h = int(tw + 2 * pad), int(asc + desc + 2 * pad)
    m = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(m)
    x = pad
    mid = pad + (fnt.getbbox('一')[1] + fnt.getbbox('一')[3]) / 2
    for c, cw in zip(text, widths):
        if c == '·':
            r = fnt.size * 0.07
            d.ellipse([x + cw / 2 - r, mid - r, x + cw / 2 + r, mid + r], fill=255)
        elif c != ' ':
            d.text((x, pad), c, font=fnt, fill=255, stroke_width=stroke, stroke_fill=255)
        x += cw + tracking
    ma = np.asarray(m, np.float32) / 255
    sh = np.asarray(m.filter(ImageFilter.GaussianBlur(glow_r * 0.6)), np.float32) / 255
    gl = np.asarray(m.filter(ImageFilter.GaussianBlur(glow_r)), np.float32) / 255
    pm = np.zeros((h, w, 3), np.float32)
    al = np.zeros((h, w), np.float32)

    def over(rgb, a):
        a = np.clip(a, 0, 1)
        pm[:] = np.array(rgb, np.float32) * a[..., None] + pm * (1 - a[..., None])
        al[:] = a + al * (1 - a)

    over((0, 0, 0), sh * 1.6 * shadow)
    if glow:
        over(glow, gl * 1.3 * glow_k)
    over(fill, ma)
    rgb = pm / np.maximum(al, 1e-4)[..., None]
    return Image.fromarray(np.dstack([rgb, al * 255]).clip(0, 255).astype(np.uint8), 'RGBA')


def char_sprites(text, fnt, fill, glow, glow_r, tracking):
    """One sprite per character plus its centre x offset from the centre of the line."""
    widths = [advance(fnt, c) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    out, x = [], -total / 2
    for c, w in zip(text, widths):
        out.append((glow_sprite(c, fnt, fill, glow, glow_r), x + w / 2))
        x += w + tracking
    return out


def paste_rgba(dst, spr, cx, cy, alpha=1.0, scale=1.0):
    """Alpha-composite sprite centred on (cx, cy) into the RGBA image dst, clipped to it."""
    if alpha <= 0.01:
        return
    if abs(scale - 1) > 1e-3:
        spr = spr.resize((max(1, int(spr.width * scale)), max(1, int(spr.height * scale))), Image.BILINEAR)
    if alpha < 0.999:
        a = np.asarray(spr).copy()
        a[..., 3] = (a[..., 3] * alpha).astype(np.uint8)
        spr = Image.fromarray(a, 'RGBA')
    x, y = int(round(cx - spr.width / 2)), int(round(cy - spr.height / 2))
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + spr.width, dst.width), min(y + spr.height, dst.height)
    if x1 <= x0 or y1 <= y0:
        return
    dst.alpha_composite(spr, dest=(x0, y0), source=(x0 - x, y0 - y, x1 - x, y1 - y))


# ---- sources ----------------------------------------------------------------------------
class Shot:
    """Streams one shot's source frames; frame i is source time first + i / FPS."""

    def __init__(self, path, src_in, src_len, ss):
        self.ss = ss
        self.w, self.h = int(SRC_W * ss), int(SRC_H * ss)
        self.first = np.ceil(src_in * FPS - 1e-6) / FPS
        vf = f'delogo=x={WM[0]}:y={WM[1]}:w={WM[2] - WM[0]}:h={WM[3] - WM[1]}'
        if ss != 1:
            vf += f',scale={self.w}:{self.h}:flags=lanczos'
        cmd = ['ffmpeg', '-v', 'error', '-ss', f'{src_in:.3f}', '-i', path, '-t', f'{src_len + 0.2:.3f}',
               '-an', '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=self.w * self.h * 3 * 2)
        self.frames = []      # (index, array)
        self.next = 0

    def _read(self):
        n = self.w * self.h * 3
        buf = self.proc.stdout.read(n)
        if len(buf) < n:
            return False
        self.frames.append((self.next, np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)))
        self.frames = self.frames[-3:]
        self.next += 1
        return True

    def get(self, t, blend):
        p = max((t - self.first) * FPS, 0.0)
        i = int(np.floor(p))
        while self.next <= i + 1 and self._read():
            pass
        have = {k: a for k, a in self.frames}
        i = min(i, self.next - 1)
        a = have.get(i, self.frames[-1][1])
        b = have.get(i + 1)
        f = p - i
        if blend and b is not None and f > 0.02:
            return (a.astype(np.float32) * (1 - f) + b.astype(np.float32) * f).astype(np.uint8)
        if not blend and b is not None and f >= 0.5:
            return b
        return a

    def close(self):
        self.proc.kill()           # kill first, or ffmpeg reports the broken pipe
        self.proc.stdout.close()
        self.proc.wait()


# ---- renderer ---------------------------------------------------------------------------
class Renderer:
    def __init__(self, path, S, fast):
        self.path, self.S = path, S
        self.ss = 1.0 if S > 0.75 else 0.5          # decode at half size for previews
        self.cw, self.ch = int(round(CW * S)), int(round(CH * S))
        self.rs = Image.BILINEAR if fast else Image.LANCZOS
        self.fast = fast
        yy, xx = np.mgrid[0:self.ch, 0:self.cw].astype(np.float32)
        r2 = ((xx / self.cw - .5) * 1.25) ** 2 + ((yy / self.ch - .5) * 0.95) ** 2
        self.vig = (1 - 0.55 * np.clip(r2 - 0.06, 0, None) / 0.32).clip(0.45, 1)[..., None]
        rng = np.random.default_rng(7)
        gw, gh = max(1, self.cw // 2), max(1, self.ch // 2)
        self.grain = [np.repeat(np.repeat(rng.normal(0, 4.5, (gh, gw, 1)).astype(np.float32), 2, 0), 2, 1)
                      [:self.ch, :self.cw] for _ in range(6)]
        self.shot_idx, self.reader = None, None
        self.embers = self._make_embers(np.random.default_rng(11))
        self._texts()

    # -- text
    def _texts(self):
        S = self.S
        zh = font(SERIF, 148 * S)
        en = font(LATIN[0], 40 * S, LATIN[1])
        self.caps = []
        for c in CAPTIONS:
            col = STYLE[c[4]]
            fill = (255, 246, 232) if c[4] != 'slam' else (255, 226, 160)
            sprites = char_sprites(c[2], zh, fill, col, 16 * S, 14 * S)
            eng = glow_sprite(c[3].upper(), en, (235, 235, 235), None, 6 * S, tracking=4 * S)
            self.caps.append((c, sprites, eng))
        self.head_title = glow_sprite('剑来', font(BRUSH, 112 * S), (255, 222, 150), (255, 140, 40), 14 * S)
        self.head_sub = glow_sprite('吴磊 饰 陈平安', font(SERIF, 38 * S), (245, 240, 230), None, 8 * S,
                                    tracking=8 * S)
        self.card_title = [glow_sprite(c, font(BRUSH, 420 * S), (255, 214, 130), (255, 110, 30), 34 * S,
                                       glow_k=1.1) for c in '剑来']
        self.card_name = glow_sprite('吴磊  饰  陈平安', font(SERIF, 60 * S), (250, 244, 232), (255, 140, 50),
                                     10 * S, glow_k=0.5, tracking=10 * S)
        self.card_line = glow_sprite('为自己 · 争一争', font(SERIF, 46 * S), (255, 200, 120), None, 8 * S,
                                     tracking=12 * S)

    # -- embers: (x, y0, speed, sway, phase, size, flicker)
    def _make_embers(self, rng, n=90):
        return np.stack([rng.uniform(0, 1, n), rng.uniform(0, 1, n), rng.uniform(0.10, 0.34, n),
                         rng.uniform(0.01, 0.04, n), rng.uniform(0, 6.3, n), rng.uniform(0.6, 2.6, n),
                         rng.uniform(2, 9, n)], 1)

    def ember_layer(self, T, k):
        q = 4
        w, h = self.cw // q, self.ch // q
        img = Image.new('L', (w, h), 0)
        d = ImageDraw.Draw(img)
        for x, y0, sp, sw, ph, sz, fl in self.embers:
            y = (y0 - sp * T) % 1.15 - 0.075
            xx = (x + sw * np.sin(ph + T * 1.7)) * w
            r = sz * self.S * 1.6
            b = int(200 * (0.6 + 0.4 * np.sin(ph * 3 + T * fl)))
            d.ellipse([xx - r, y * h - r, xx + r, y * h + r], fill=b)
        img = img.filter(ImageFilter.GaussianBlur(1.1))
        a = np.asarray(img.resize((self.cw, self.ch), Image.BILINEAR), np.float32)[..., None] / 255
        return a * np.array([255, 150, 55], np.float32) * (1.4 * k)

    # -- picture
    def reader_for(self, k):
        if self.shot_idx != k:
            if self.reader:
                self.reader.close()
            s = SHOTS[k]
            src_len = (s[1] - s[0]) * s[3] + 0.1
            self.reader = Shot(self.path, s[2], src_len, self.ss)
            self.shot_idx = k
        return self.reader

    def shake(self, T):
        amp = sum(h[3] * pulse(T, h[0], 0.30) for h in HITS)
        if amp < 0.3:
            return 0.0, 0.0
        r = np.random.default_rng(int(T * FPS * 7919) % 2 ** 31)
        return tuple(r.uniform(-1, 1, 2) * amp * self.S)

    def window(self, s, local, T):
        out_in, out_out, src_in, speed, cx, cy, h, push, ex = s
        dur = out_out - out_in
        z = push[0] + (push[1] - push[0]) * ease(local / dur) if dur > 0 else push[0]
        z *= 1 + sum(hh[2] * (1 - ease_out((T - hh[0]) / 0.28)) for hh in HITS if hh[0] <= T < hh[0] + 0.28)
        if 'pan' in ex:
            ks = ex['pan']
            i = max(j for j, kk in enumerate(ks) if local >= kk[0])
            if i + 1 < len(ks):
                a, b = ks[i], ks[i + 1]
                cx = a[1] + (b[1] - a[1]) * ease((local - a[0]) / (b[0] - a[0]))
            else:
                cx = ks[-1][1]
        hh = h / z
        ww = hh * 9 / 16
        x = AX0 + cx * AW
        y = cy * SRC_H
        dx, dy = self.shake(T)
        x -= dx * hh / CH
        y -= dy * hh / CH
        ybot = SUB_TOP if ex.get('top') else SRC_H
        x = min(max(x, AX0 + ww / 2), AX0 + AW - ww / 2)
        y = min(max(y, hh / 2), ybot - hh / 2)
        return x - ww / 2, y - hh / 2, x + ww / 2, y + hh / 2

    def picture(self, T):
        k = max(i for i, s in enumerate(SHOTS) if T >= s[0] - 1e-6)
        s = SHOTS[k]
        local = T - s[0]
        rd = self.reader_for(k)
        t_src = s[2] + local * s[3]
        img = rd.get(t_src, blend=s[3] < 0.9 and s[3] > 0)
        x0, y0, x1, y1 = self.window(s, local, T)
        box = tuple(v * self.ss for v in (x0, y0, x1, y1))
        pic =Image.fromarray(img).resize((self.cw, self.ch), self.rs, box=box)
        if not self.fast and (y1 - y0) < 1000:
            pic = pic.filter(ImageFilter.UnsharpMask(radius=2.2 * self.S, percent=55, threshold=2))
        return np.asarray(pic, np.float32), s, local

    # -- effects
    def grade(self, a, s, local, T):
        a = a / 255
        lum = (a * np.array([.299, .587, .114], np.float32)).sum(2, keepdims=True)
        sat = 1.10
        if s[8].get('silence'):
            sat = 1.10 - 0.75 * ease(local / (s[1] - s[0]))
        if s[8].get('card'):
            sat = 0.55
        a = lum + (a - lum) * sat
        a = (a - 0.5) * 1.07 + 0.5 - 0.01
        a = np.clip(a, 0, 1) * 255
        if s[8].get('silence'):
            a *= 1 - 0.35 * ease(local / (s[1] - s[0]))
        if s[8].get('card'):                     # the close-up, frozen and pushed back
            a *= 0.30 + 0.25 * pulse(T, s[0], 0.5)
            a[..., 0] *= 1.10
        return a

    def rgb_split(self, a, T):
        px = int(round(sum(h[4] * pulse(T, h[0], 0.22) for h in HITS) * self.S))
        if px < 1:
            return a
        out = a.copy()
        out[:, px:, 0] = a[:, :-px, 0]
        out[:, :-px, 2] = a[:, px:, 2]
        return out

    def glitch(self, a, T):
        g = max((pulse(T, t0, d) for t0, d in GLITCH), default=0)
        if g < 0.05:
            return a
        r = np.random.default_rng(int(T * FPS) + 3)
        out = a.copy()
        for _ in range(int(4 + 8 * g)):
            y0 = int(r.uniform(0, self.ch))
            hh = int(r.uniform(8, 90) * self.S)
            sh = int(r.uniform(-140, 140) * g * self.S)
            out[y0:y0 + hh] = np.roll(a[y0:y0 + hh], sh, axis=1)
            if r.uniform() < 0.3:
                out[y0:y0 + hh, :, int(r.integers(0, 3))] *= 0.4
        return out

    def zoom_blur(self, a, T):
        for t0, d in ZOOM_BLUR:
            k = 1 - abs(T - t0) / d
            if k > 0:
                im = Image.fromarray(a.clip(0, 255).astype(np.uint8))
                acc = a.copy()
                n = 6
                for j in range(1, n):
                    z = 1 + 0.045 * j * k
                    w, h = self.cw / z, self.ch / z
                    box = ((self.cw - w) / 2, (self.ch - h) / 2, (self.cw + w) / 2, (self.ch + h) / 2)
                    acc += np.asarray(im.resize((self.cw, self.ch), Image.BILINEAR, box=box), np.float32)
                return acc / n
        return a

    # -- overlays
    def captions(self, dst, T):
        S = self.S
        cy, ey = 1300 * S, 1408 * S
        for (t_in, t_out, zh, en, style), sprites, eng in self.caps:
            if not (t_in <= T < t_out + 0.01):
                continue
            out_p = ease((T - (t_out - 0.18)) / 0.18)
            dx, dy = self.shake(T)
            vert = style in VERTICAL
            col_x, step = 0.82 * self.cw, 164 * S
            for i, (spr, xo) in enumerate(sprites):
                if style == 'slam':
                    p = (T - t_in) / 0.12
                    sc = 2.4 - 1.4 * ease_out(p)
                    al = min(p * 3, 1)
                else:
                    p = (T - t_in - i * 0.06) / 0.16
                    sc = 1.6 - 0.6 * back_out(p)
                    al = min(max(p, 0) * 1.6, 1)
                sc *= 1 + 0.10 * out_p
                al *= 1 - out_p
                if vert:
                    y = 780 * S + (i - (len(sprites) - 1) / 2) * step * (1 + 0.15 * out_p)
                    paste_rgba(dst, spr, col_x + dx * 0.5, y + dy * 0.5, al, sc)
                else:
                    paste_rgba(dst, spr, self.cw / 2 + xo * (1 + 0.25 * out_p) + dx * 0.5,
                               cy + dy * 0.5 - 14 * S * out_p, al, sc)
            pe = ease((T - t_in - 0.20) / 0.25) * (1 - out_p)
            if vert:
                paste_rgba(dst, eng, min(col_x, self.cw - eng.width / 2 - 24 * S),
                           780 * S + (len(sprites) / 2 + 0.2) * step + 10 * S * (1 - pe), pe * 0.9)
            else:
                paste_rgba(dst, eng, self.cw / 2, ey + 10 * S * (1 - pe), pe * 0.9)

    def header(self, dst, T):
        a = ease((T - HEADER[0]) / 0.35) * (1 - ease((T - (HEADER[1] - 0.3)) / 0.3))
        if a <= 0.01 or T >= HEADER[1]:
            return
        paste_rgba(dst, self.head_title, self.cw / 2, 228 * self.S, a)
        paste_rgba(dst, self.head_sub, self.cw / 2, 330 * self.S, a * 0.95)

    def end_card(self, dst, T, t0):
        S = self.S
        p = (T - t0) / 0.16
        sc = 1.7 - 0.7 * ease_out(p)
        al = min(max(p, 0) * 2, 1)
        dx, dy = self.shake(T)
        for i, spr in enumerate(self.card_title):
            paste_rgba(dst, spr, self.cw / 2 + (i - 0.5) * 330 * S * sc + dx, 820 * S + dy, al, sc)
        pn = ease((T - t0 - 0.45) / 0.4)
        paste_rgba(dst, self.card_name, self.cw / 2, (1130 + 16 * (1 - pn)) * S, pn)
        pl = ease((T - t0 - 0.85) / 0.4)
        paste_rgba(dst, self.card_line, self.cw / 2, (1225 + 16 * (1 - pl)) * S, pl)

    def frame(self, n):
        T = n / FPS
        a, s, local = self.picture(T)
        a = self.grade(a, s, local, T)
        for t0, t1 in EMBERS:
            if t0 <= T < t1:
                k = min(1, (T - t0) / 0.4, (t1 - T) / 0.3)
                if s[8].get('card'):
                    k *= 1.6
                a = a + self.ember_layer(T, 0.42 * k)
        a = self.zoom_blur(a, T)
        a = self.glitch(a, T)
        a = self.rgb_split(a, T)
        a = a * self.vig
        fl = sum(h[1] * pulse(T, h[0], 0.20) for h in HITS)
        if fl > 0:
            a = a + (255 - a) * min(fl, 1)
        a = a + self.grain[n % len(self.grain)]
        img = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert('RGBA')
        self.header(img, T)
        self.captions(img, T)
        if s[8].get('card'):
            self.end_card(img, T, s[0])
        out = np.asarray(img.convert('RGB'))
        if T > T_END - 0.45:                     # fade the titles out with the picture
            out = (out * (1 - ease((T - (T_END - 0.45)) / 0.45))).astype(np.uint8)
        return out


# ---- audio ------------------------------------------------------------------------------
SR = 48000


def read_wav(path):
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return x.reshape(-1, w.getnchannels())


def onepole(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    return lfilter([1 - a], [1, -a], x).astype(np.float32)


def impact(strength, rng, dur=1.8):
    t = np.arange(int(dur * SR)) / SR
    f = 36 + 80 * np.exp(-t / 0.045)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.42)
    body = onepole(rng.normal(0, 1, len(t)).astype(np.float32), 900) * np.exp(-t / 0.07) * 2.5
    click = rng.normal(0, 1, len(t)) * np.exp(-t / 0.004) * 0.5
    tail = onepole(rng.normal(0, 1, (len(t))).astype(np.float32), 2200) * np.exp(-t / 0.55) * 0.35
    m = (sub * 0.9 + body + click)[:, None] + np.stack([tail, np.roll(tail, 397)], 1)
    return (m * strength).astype(np.float32)


def whoosh(dur, rng, up=True):
    n = int(dur * SR)
    t = np.arange(n) / n
    env = (t if up else 1 - t) ** 2.2
    noise = rng.normal(0, 1, n).astype(np.float32)
    fc = 300 + 5000 * (t if up else 1 - t) ** 2
    # time-varying one-pole low-pass minus a slower one = moving band
    y1, y2 = np.empty(n, np.float32), np.empty(n, np.float32)
    s1 = s2 = 0.0
    for i in range(n):
        a1 = np.exp(-2 * np.pi * fc[i] / SR)
        a2 = np.exp(-2 * np.pi * fc[i] * 0.25 / SR)
        s1 = (1 - a1) * noise[i] + a1 * s1
        s2 = (1 - a2) * noise[i] + a2 * s2
        y1[i], y2[i] = s1, s2
    y = (y1 - y2) * env * 3.0
    return np.stack([y, np.roll(y, 211)], 1)


def glitch_sfx(dur, rng):
    n = int(dur * SR)
    step = rng.integers(40, 160)
    v = np.repeat(rng.uniform(-1, 1, n // step + 1), step)[:n]
    tone = np.sign(np.sin(2 * np.pi * rng.uniform(300, 900) * np.arange(n) / SR))
    env = np.exp(-np.arange(n) / (0.35 * n))
    y = (0.6 * v + 0.3 * tone) * env
    return np.stack([y, y], 1).astype(np.float32)


def thump(rng):
    t = np.arange(int(0.35 * SR)) / SR
    y = np.sin(2 * np.pi * (48 + 30 * np.exp(-t / 0.03)) * t) * np.exp(-t / 0.09)
    return np.stack([y, y], 1).astype(np.float32)


def build_audio(src_wav, out_wav):
    x = read_wav(src_wav)
    n = int(T_END * SR) + SR
    mix = np.zeros((n, 2), np.float32)
    fade = int(0.012 * SR)
    for i, (o, s0, s1) in enumerate(AUDIO):
        seg = x[int(s0 * SR):int(s1 * SR)].copy()
        r = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
        seg[:fade] *= r
        seg[-fade:] *= r[::-1]
        a = int(o * SR)
        seg = seg[:max(0, n - a)]
        mix[a:a + len(seg)] += seg
    end = int((T_END - 0.8) * SR)
    mix[end:int(T_END * SR)] *= np.linspace(1, 0, int(T_END * SR) - end, dtype=np.float32)[:, None]
    mix[int(T_END * SR):] = 0

    rng = np.random.default_rng(5)
    fx = np.zeros_like(mix)

    def add(T, clip, gain):
        a = int(T * SR)
        b = min(a + len(clip), n)
        if a < 0:
            clip, a = clip[-a:], 0
        fx[a:b] += clip[:b - a] * gain

    add(0.00, impact(1.0, rng), 0.55)
    for T in (0.00, 0.33, 0.66):
        add(T, glitch_sfx(0.14, rng), 0.10)
    for T in (0.33, 0.66):
        add(T, impact(0.5, rng, 0.8), 0.35)
    add(0.99 - 0.30, whoosh(0.30, rng), 0.12)
    add(10.00 - 0.45, whoosh(0.45, rng), 0.16)
    add(10.00, impact(1.0, rng), 0.50)
    for i in range(8):
        add(FL + i * Q, whoosh(0.09, rng, up=False) * 0.6, 0.10)
    add(21.76, whoosh(22.93 - 21.76, rng), 0.20)
    add(22.93, impact(1.0, rng), 0.55)
    add(24.85, impact(0.8, rng), 0.35)
    for T in (27.60, 27.98):
        add(T, thump(rng), 0.35)
    add(28.39, impact(1.0, rng, 2.4), 0.55)
    out = mix + fx
    out = np.tanh(out * 1.1) / np.tanh(1.1)          # soft clip the summed peaks
    with wave.open(out_wav, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out[:int(T_END * SR)] * 32767).clip(-32768, 32767).astype(np.int16).tobytes())


# ---- main -------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('trailer')
    ap.add_argument('out')
    ap.add_argument('--scale', type=float, default=1.0)
    ap.add_argument('--fast', action='store_true')
    ap.add_argument('--work', default=None)
    ap.add_argument('--frames', default=None, help='comma-separated output times to dump as JPEG only')
    ap.add_argument('--maxrate', default='14M', help='video bitrate cap (bufsize is twice this)')
    args = ap.parse_args()
    work = args.work or os.path.dirname(os.path.abspath(args.out))
    os.makedirs(work, exist_ok=True)

    r = Renderer(args.trailer, args.scale, args.fast)
    if args.frames:
        for t in (float(v) for v in args.frames.split(',')):
            r.shot_idx = None
            Image.fromarray(r.frame(int(round(t * FPS)))).save(os.path.join(work, f'still_{t:05.2f}.jpg'), quality=88)
        return

    src_wav = os.path.join(work, 'trailer_48k.wav')
    if not os.path.exists(src_wav):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', args.trailer, '-vn', '-ac', '2', '-ar', str(SR),
                        src_wav], check=True)
    mix_wav = os.path.join(work, 'mix.wav')
    build_audio(src_wav, mix_wav)
    # two-pass loudnorm: measure, then apply one linear gain (no pumping) to -14 LUFS
    ln = 'loudnorm=I=-14:TP=-2:LRA=11'        # AAC adds ~1 dB of overshoot on top
    err = subprocess.run(['ffmpeg', '-hide_banner', '-i', mix_wav, '-af', ln + ':print_format=json',
                          '-f', 'null', '-'], capture_output=True, encoding='utf-8', errors='replace').stderr
    m = json.loads(err[err.rindex('{'):err.rindex('}') + 1])
    ln += (f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
           f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true"
           ",aresample=48000,alimiter=limit=0.79:level=false")   # loudnorm alone left peaks at -0.7

    n_frames = int(round(T_END * FPS))
    enc = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{r.cw}x{r.ch}',
           '-r', str(FPS), '-i', '-', '-i', mix_wav,
           '-af', ln,
           # the film grain is new noise every frame: cap the rate or it runs to 30 Mbps
           '-c:v', 'libx264', '-preset', 'veryfast' if args.fast else 'slow', '-crf', '20',
           '-maxrate', args.maxrate, '-bufsize', f'{2 * float(args.maxrate.rstrip("M")):g}M',
           '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
           '-movflags', '+faststart', '-shortest', args.out]
    p = subprocess.Popen(enc, stdin=subprocess.PIPE)
    for i in range(n_frames):
        p.stdin.write(r.frame(i).tobytes())
        if i % 50 == 0:
            print(f'{i}/{n_frames}', flush=True)
    p.stdin.close()
    p.wait()
    if r.reader:
        r.reader.close()
    print('written', args.out)


if __name__ == '__main__':
    main()
