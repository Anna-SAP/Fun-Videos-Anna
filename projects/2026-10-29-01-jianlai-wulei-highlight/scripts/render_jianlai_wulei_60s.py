#!/usr/bin/env python3
"""剑来 · 陈平安 — the 60-second cut: same rules as the 31.6 s short, with room for more of him.

  render_jianlai_wulei_60s.py TRAILER OUT.mp4 [--scale 0.5] [--fast] [--work DIR] [--frames t1,t2]

Reuses the renderer of render_jianlai_wulei.py (same folder) and swaps in this edit's tables.

Edit (output clock):
  0.00  hook      four 0.33 s glitch flashes: spark burst, snarl, hair flying in the fog, choking
  1.33  quiet     his own voice-over from the trailer's opening (source 40.8-53.4 s):
                  我原以为 / 眼前的这些人和事 / 就是这座小镇的全部 / 可这方天地 / 当真如我所见
                  over the porch, firelight, his dog, the kiln, the valley and the straw hat;
                  slow motion and dissolves, quiet captions
 14.38  impact    the debris shot in sync with its own hits, then the bloodied hand
 20.20  forge     去路不由己 / 但我还是想 / 为自己 / 争一争, as in the short version
 30.20  climax    the score from 见自由 (an accent every 1.1775 s), now 17 accents long: one shot per
                  accent, quarter-beat flashes, a slow-motion breath, then half-beat cuts
 50.21  finale    spark burst, whip pan to the face, the close-up, the silence, the title (55.67)
Audio  trailer audio in five pieces; all speech kept is Chen Ping'an's.
"""
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_jianlai_wulei as base                      # noqa: E402
from render_jianlai_wulei import (BEAT, TOP, SR, char_sprites, ease, ease_out, font,   # noqa: E402
                                  glitch_sfx, glow_sprite, impact, paste_rgba, pulse, read_wav, thump,
                                  whoosh)

T_END = 60.00
A = 2 * BEAT                     # one accent, 1.1775 s
Q = BEAT / 2                     # a quarter of an accent

# ---- audio: (output start, source start, source end, gain dB, fade in s, fade out s) ------
AUDIO = [(0.00, 39.17, 53.55, 2.0, 0.30, 0.10),      # quiet voice-over
         (14.38, 57.38, 63.20, 0.0, 0.01, 0.30),     # the debris hits
         (20.20, 116.30, 126.30, 0.0, 0.01, 0.01),   # the forge
         (30.20, 146.96, 166.97, 0.0, 0.01, 0.01),   # 见自由 and the climax, on the accent grid
         (50.21, 171.84, 181.80, 0.0, 0.01, 0.01)]   # spark burst, close-up, silence, title hit

# ---- shots: (out_in, out_out, src_in, speed, cx, cy, h, push, extra) -----------------------
# extra 'dissolve': d mixes in from the previous shot over d seconds (that shot keeps playing)
C = 30.20                        # climax start
FL = C + 9.41                    # eight quarter-beat flashes
HB = C + 15.32                   # eight half-beat cuts
SHOTS = [
    # hook
    (0.00, 0.33, 173.10, 1.0, .62, .45, 1080, (1.06, 1.0), {}),            # spark burst
    (0.33, 0.66, 174.90, 1.0, .48, .42, 960, (1.04, 1.0), {}),             # bloodied snarl
    (0.66, 0.99, 135.12, 1.0, .52, .40, 1080, (1.05, 1.0), {}),            # hair flying in the fog
    (0.99, 1.33, 136.70, 1.0, .47, .45, 1080, (1.05, 1.0), {}),            # choking, blood thread
    # quiet: 我原以为 / 眼前的这些人和事 / 就是这座小镇的全部 / 可这方天地 / 当真如我所见
    (1.33, 3.13, 11.30, 1.0, .65, TOP, 888, (1.0, 1.06), {'top': 1}),     # porch, face to the sun
    (3.13, 4.93, 41.98, 0.75, .66, TOP, 888, (1.0, 1.05), {'top': 1, 'dissolve': .3}),   # firelight
    (4.93, 5.53, 162.00, 0.20, .56, .45, 1080, (1.02, 1.06), {'dissolve': .3}),          # his dog (6 frames)
    (5.53, 7.93, 25.66, 0.60, .40, TOP, 888, (1.0, 1.06),                                 # the kiln
     {'top': 1, 'dissolve': .3, 'pan': [(0.0, .40), (2.5, .27)]}),
    (7.93, 10.43, 47.84, 0.63, .24, .50, 1080, (1.0, 1.08), {'dissolve': .3}),           # the valley
    (10.43, 12.33, 49.66, 0.62, .56, TOP, 888, (1.0, 1.05), {'top': 1, 'dissolve': .3}), # straw hat
    (12.33, 14.38, 50.80, 0.50, .58, TOP, 700, (1.0, 1.10), {'top': 1}),  # closer on his eyes
    # impact
    (14.38, 16.84, 57.46, 1.0, .50, .50, 1080, (1.06, 1.0), {}),         # debris, his back
    (16.84, 18.91, 59.95, 1.0, .46, .50, 1080, (1.03, 1.08), {}),        # debris, his face
    (18.91, 20.20, 67.84, 1.0, .46, .45, 980, (1.0, 1.12), {}),          # bloodied hand raised
    # forge: 去路不由己 / 但我还是想 / 为自己 / 争一争
    (20.20, 22.30, 115.62, 0.80, .49, .50, 1080, (1.0, 1.08), {}),       # bloodied, head down
    (22.30, 23.40, 118.05, 1.0, .50, TOP, 888, (1.0, 1.06), {'top': 1}), # sweat, eyes up
    (23.40, 26.22, 119.55, 0.976, .49, TOP, 888, (1.0, 1.12), {'top': 1}),  # robe drops, sparks
    (26.22, 27.66, 122.33, 1.0, .56, TOP, 888, (1.02, 1.10), {'top': 1}),   # at the forge
    (27.66, 28.50, 123.80, 1.0, .50, .50, 1080, (1.0, 1.06), {}),        # shoulder, embers
    (28.50, 29.62, 124.94, 0.68, .52, .50, 1080, (1.0, 1.12), {}),       # hammer up (slow)
    (29.62, 30.20, 125.74, 1.0, .45, .55, 1080, (1.08, 1.0), {}),        # the strike
    # climax, one shot per accent
    (C + 0.00, C + 1.78, 147.06, 1.0, .52, TOP, 888, (1.0, 1.10), {'top': 1}),   # 见自由, rain
    (C + 1.78, C + 3.04, 134.96, 0.85, .52, TOP, 888, (1.0, 1.06), {'top': 1}),         # fog, flung back
    (C + 3.04, C + 3.70, 136.40, 1.0, .47, .45, 1080, (1.06, 1.0), {}),          # blood thread
    (C + 3.70, C + 4.71, 141.15, 1.0, .48, TOP, 888, (1.06, 1.0), {'top': 1}),   # mud on his face
    (C + 4.71, C + 5.89, 142.30, 0.88, .52, TOP, 888, (1.0, 1.06), {'top': 1}),   # through the door
    (C + 5.89, C + 6.48, 50.30, 1.0, .56, TOP, 888, (1.06, 1.0), {'top': 1}),    # straw hat
    (C + 6.48, C + 7.06, 61.30, 1.0, .46, .50, 1080, (1.06, 1.0), {}),           # debris, face
    (C + 7.06, C + 7.65, 42.70, 1.0, .66, TOP, 888, (1.06, 1.0), {'top': 1}),    # firelight
    (C + 7.65, C + 8.29, 118.50, 1.0, .50, TOP, 888, (1.0, 1.06), {'top': 1}),   # sweat, eyes up
    (C + 8.29, FL, 121.10, 1.0, .50, TOP, 888, (1.0, 1.08), {'top': 1}),         # his back, sparks
    # quarter-beat flashes
    (FL + 0 * Q, FL + 1 * Q, 116.60, 1.0, .49, .50, 1080, (1.08, 1.0), {}),
    (FL + 1 * Q, FL + 2 * Q, 120.30, 1.0, .50, TOP, 888, (1.08, 1.0), {'top': 1}),
    (FL + 2 * Q, FL + 3 * Q, 125.40, 1.0, .50, .50, 1080, (1.08, 1.0), {}),
    (FL + 3 * Q, FL + 4 * Q, 148.40, 1.0, .52, TOP, 888, (1.08, 1.0), {'top': 1}),
    (FL + 4 * Q, FL + 5 * Q, 141.90, 1.0, .48, TOP, 888, (1.08, 1.0), {'top': 1}),
    (FL + 5 * Q, FL + 6 * Q, 142.90, 1.0, .52, TOP, 888, (1.08, 1.0), {'top': 1}),
    (FL + 6 * Q, FL + 7 * Q, 135.30, 1.0, .50, .45, 1080, (1.08, 1.0), {}),
    (FL + 7 * Q, C + 11.76, 51.20, 1.0, .58, TOP, 888, (1.08, 1.0), {'top': 1}),
    (C + 11.76, C + 12.93, 67.96, 1.0, .46, .42, 860, (1.0, 1.16), {}),          # hand raised, closer
    # a breath: the valley in slow motion, then half-beat cuts into the finale
    (C + 12.93, HB, 47.86, 0.50, .24, .50, 1080, (1.08, 1.0), {}),
    (HB + 0 * BEAT, HB + 1 * BEAT, 120.00, 1.0, .50, TOP, 888, (1.08, 1.0), {'top': 1}),  # robe, sparks
    (HB + 1 * BEAT, HB + 2 * BEAT, 125.05, 1.0, .52, .50, 1080, (1.08, 1.0), {}),         # hammer up
    (HB + 2 * BEAT, HB + 3 * BEAT, 135.40, 1.0, .50, .45, 1080, (1.08, 1.0), {}),         # flung
    (HB + 3 * BEAT, HB + 4 * BEAT, 141.60, 1.0, .48, TOP, 888, (1.08, 1.0), {'top': 1}),  # mud
    (HB + 4 * BEAT, HB + 5 * BEAT, 148.00, 1.0, .52, TOP, 888, (1.08, 1.0), {'top': 1}),  # 见自由
    (HB + 5 * BEAT, HB + 6 * BEAT, 60.60, 1.0, .46, .50, 1080, (1.08, 1.0), {}),          # debris
    (HB + 6 * BEAT, HB + 7 * BEAT, 116.75, 1.0, .49, .50, 1080, (1.08, 1.0), {}),         # bloodied
    (HB + 7 * BEAT, 50.21, 142.70, 1.0, .52, TOP, 888, (1.08, 1.0), {'top': 1}),          # the door
    # finale (in sync with the score again)
    (50.21, 52.13, 172.32, 0.74, .66, .45, 1080, (1.04, 1.0),           # fist -> face
     {'pan': [(0.0, .24), (0.12, .24), (0.62, .66), (9.0, .68)]}),
    (52.13, 54.71, 173.78, 1.0, .48, .45, 1080, (1.0, 1.10), {}),        # the close-up
    (54.71, 55.67, 176.36, 0.25, .48, .45, 1080, (1.10, 1.22), {'silence': 1}),
    (55.67, T_END, 175.30, 0.0, .48, .42, 1080, (1.06, 1.14), {'card': 1}),
]

# ---- hits: (T, flash, punch, shake px, rgb px) ------------------------------------------
HITS = [(0.00, .55, .12, 22, 18), (0.33, .35, .08, 16, 14), (0.66, .35, .08, 16, 14), (0.99, .35, .08, 16, 14),
        (1.33, .45, .06, 0, 8), (12.33, .10, .03, 0, 0),
        (14.38, .55, .10, 20, 12), (16.84, .20, .05, 8, 5), (18.91, .50, .10, 20, 12), (19.39, .25, .06, 12, 8),
        (20.20, .20, .05, 0, 6), (22.30, 0, .03, 0, 0), (23.40, .12, .04, 0, 4), (26.22, .12, .04, 6, 4),
        (26.82, 0, .06, 16, 8), (27.66, 0, .03, 0, 0), (28.50, .08, .03, 0, 0), (29.62, .60, .10, 22, 12),
        (C + 0.00, .70, .10, 18, 14), (C + 1.78, .15, .05, 0, 4), (C + 3.04, .30, .07, 14, 8),
        (C + 3.70, .30, .07, 14, 8), (C + 4.71, .15, .04, 0, 4), (C + 5.89, .22, .05, 10, 6),
        (C + 6.48, .22, .05, 10, 6), (C + 7.06, .25, .06, 10, 6), (C + 7.65, .18, .05, 8, 5),
        (C + 8.29, .22, .05, 8, 5), (C + 11.76, .25, .06, 10, 8), (C + 12.93, .55, .10, 18, 12),
        (50.21, .75, .12, 24, 18), (52.13, .65, .12, 22, 16), (55.67, .95, .15, 30, 20)]
HITS += [(FL + i * Q, .10, .06, 8, 8) for i in range(8)]       # keep the strobe gentle
HITS += [(HB + i * BEAT, .12, .06, 10, 8) for i in range(8)]
GLITCH = [(0.00, 0.20), (0.33, 0.16), (0.66, 0.16), (0.99, 0.16)]
ZOOM_BLUR = [(C, 0.14), (C + 12.93, 0.12)]
EMBERS = [(23.40, C), (50.21, T_END)]

# ---- captions: (in, out, 中文, English, style) -------------------------------------------
CAPTIONS = [
    (1.63, 2.95, '我原以为', 'I used to believe', 'calm'),
    (3.03, 5.35, '眼前的这些人和事', 'the people and things before me', 'calm'),
    (5.63, 8.30, '就是这座小镇的全部', 'were all this town had to offer.', 'calm'),
    (9.03, 11.40, '可这方天地', 'But this world,', 'calmteal'),
    (11.83, 14.30, '当真如我所见', 'is it really as it seems?', 'calmteal'),
    (21.42, 23.30, '去路不由己', 'Our path is not ours to choose.', 'ember'),
    (23.44, 24.94, '但我还是想', 'Still, I want to try.', 'ember'),
    (25.00, 26.62, '为自己', 'To fight', 'fire'),
    (26.82, 28.50, '争一争', 'for my own fate.', 'slam'),
    (C + 0.30, C + 1.70, '见自由', 'To see freedom.', 'teal'),   # vertical, beside his face
]
CALM = {'calm', 'calmteal'}
HEADER = (1.45, 5.70)           # 《剑来》 · 吴磊 饰 陈平安 at the top over the first quiet shots
STYLE = dict(base.STYLE, calm=(255, 196, 120), calmteal=(110, 210, 230))

for name in ('T_END', 'SHOTS', 'HITS', 'GLITCH', 'ZOOM_BLUR', 'EMBERS', 'CAPTIONS', 'HEADER', 'STYLE'):
    setattr(base, name, globals()[name])


class Renderer(base.Renderer):
    """Adds dissolves (two shots decoding at once) and the quiet caption style."""

    def _texts(self):
        super()._texts()
        S = self.S
        zh, en = font(base.SERIF, 96 * S), font(base.LATIN[0], 36 * S, base.LATIN[1])
        for k, c in enumerate(CAPTIONS):
            if c[4] in CALM:
                sprites = char_sprites(c[2], zh, (250, 246, 238), STYLE[c[4]], 12 * S, 12 * S)
                eng = glow_sprite(c[3].upper(), en, (230, 230, 230), None, 6 * S, tracking=4 * S)
                self.caps[k] = (c, sprites, eng)

    # -- picture, with dissolves
    def reader_for(self, k):
        readers = self.__dict__.setdefault('readers', {})
        if k not in readers:
            s = SHOTS[k]
            nxt = SHOTS[k + 1][8].get('dissolve', 0) if k + 1 < len(SHOTS) else 0
            readers[k] = base.Shot(self.path, s[2], (s[1] - s[0] + nxt) * s[3] + 0.1, self.ss)
        return readers[k]

    def shot_picture(self, k, T):
        s = SHOTS[k]
        local = T - s[0]
        img = self.reader_for(k).get(s[2] + local * s[3], blend=0 < s[3] < 0.9)
        x0, y0, x1, y1 = self.window(s, local, T)
        box = tuple(v * self.ss for v in (x0, y0, x1, y1))
        pic = base.Image.fromarray(img).resize((self.cw, self.ch), self.rs, box=box)
        if not self.fast and (y1 - y0) < 1000:
            pic = pic.filter(base.ImageFilter.UnsharpMask(radius=2.2 * self.S, percent=55, threshold=2))
        return np.asarray(pic, np.float32)

    def picture(self, T):
        k = max(i for i, s in enumerate(SHOTS) if T >= s[0] - 1e-6)
        readers = self.__dict__.setdefault('readers', {})
        if self.shot_idx is None:                 # --frames: start every still from a fresh decode
            for r in readers.values():
                r.close()
            readers.clear()
        self.shot_idx = k
        for j in [j for j in readers if j not in (k, k - 1)]:
            readers.pop(j).close()
        s = SHOTS[k]
        local = T - s[0]
        a = self.shot_picture(k, T)
        d = s[8].get('dissolve', 0)
        if d and local < d:
            w = ease(local / d)
            a = self.shot_picture(k - 1, T) * (1 - w) + a * w
        self.reader = None
        return a, s, local

    def close(self):
        for r in self.__dict__.get('readers', {}).values():
            r.close()

    # -- captions: the quiet lines rise and fade in, letter by letter
    def captions(self, dst, T):
        S = self.S
        loud = []
        for cap in self.caps:
            (t_in, t_out, zh, en, style), sprites, eng = cap
            if style not in CALM:
                loud.append(cap)
                continue
            if not (t_in <= T < t_out + 0.01):
                continue
            out_p = ease((T - (t_out - 0.30)) / 0.30)
            for i, (spr, xo) in enumerate(sprites):
                p = (T - t_in - i * 0.07) / 0.40
                rise = 22 * S * (1 - ease_out(p))
                paste_rgba(dst, spr, self.cw / 2 + xo, 1300 * S + rise, ease(p) * (1 - out_p), 1.10 - 0.10 * ease_out(p))
            pe = ease((T - t_in - 0.30) / 0.40) * (1 - out_p)
            paste_rgba(dst, eng, self.cw / 2, 1384 * S + 10 * S * (1 - pe), pe * 0.85)
        all_caps, self.caps = self.caps, loud
        super().captions(dst, T)
        self.caps = all_caps


def build_audio(src_wav, out_wav):
    x = read_wav(src_wav)
    n = int(T_END * SR) + SR
    mix = np.zeros((n, 2), np.float32)
    for o, s0, s1, gain, fi, fo in AUDIO:
        seg = x[int(s0 * SR):int(s1 * SR)].copy() * 10 ** (gain / 20)
        a, b = int(fi * SR), int(fo * SR)
        seg[:a] *= np.linspace(0, 1, a, dtype=np.float32)[:, None]
        seg[len(seg) - b:] *= np.linspace(1, 0, b, dtype=np.float32)[:, None]
        i = int(o * SR)
        seg = seg[:max(0, n - i)]
        mix[i:i + len(seg)] += seg
    end = int((T_END - 0.8) * SR)
    mix[end:int(T_END * SR)] *= np.linspace(1, 0, int(T_END * SR) - end, dtype=np.float32)[:, None]
    mix[int(T_END * SR):] = 0

    rng = np.random.default_rng(5)
    fx = np.zeros_like(mix)

    def add(T, clip, gain):
        a = int(T * SR)
        b = min(a + len(clip), n)
        fx[a:b] += clip[:b - a] * gain

    add(0.00, impact(1.0, rng), 0.55)
    for T in (0.00, 0.33, 0.66, 0.99):
        add(T, glitch_sfx(0.14, rng), 0.10)
    for T in (0.33, 0.66, 0.99):
        add(T, impact(0.5, rng, 0.8), 0.35)
    add(1.33, impact(0.6, rng, 1.6), 0.30)
    add(14.38 - 0.45, whoosh(0.45, rng), 0.14)
    add(14.42, impact(1.0, rng), 0.45)
    add(18.91, impact(0.8, rng), 0.40)
    add(19.39, impact(0.6, rng, 0.8), 0.25)
    add(C - 0.45, whoosh(0.45, rng), 0.16)
    add(C, impact(1.0, rng), 0.50)
    for i in range(8):
        add(FL + i * Q, whoosh(0.09, rng, up=False) * 0.6, 0.10)
    add(C + 11.76, whoosh(1.17, rng), 0.20)
    add(C + 12.93, impact(0.9, rng), 0.45)
    for i in range(8):
        add(HB + i * BEAT, whoosh(0.09, rng, up=False) * 0.6, 0.08)
    add(HB + 7 * BEAT, whoosh(50.21 - (HB + 7 * BEAT), rng), 0.18)
    add(50.21, impact(1.0, rng), 0.55)
    add(52.13, impact(0.8, rng), 0.35)
    for T in (54.88, 55.26):
        add(T, thump(rng), 0.35)
    add(55.67, impact(1.0, rng, 2.4), 0.55)
    out = mix + fx
    out = np.tanh(out * 1.1) / np.tanh(1.1)          # soft clip the summed peaks
    with wave.open(out_wav, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out[:int(T_END * SR)] * 32767).clip(-32768, 32767).astype(np.int16).tobytes())


base.Renderer = Renderer
base.build_audio = build_audio

if __name__ == '__main__':
    made = []
    base.Renderer = lambda *a: made.append(Renderer(*a)) or made[-1]
    base.main()
    for r in made:
        r.close()
