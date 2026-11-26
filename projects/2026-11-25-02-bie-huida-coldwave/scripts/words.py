#!/usr/bin/env python3
"""Typesetting for the lyric layer: one sung line at a time, rows of 2-5 characters, the widest row filling at
least 80 % of the safe width (the intro/outro light spots are smaller by design), Source Han Sans Heavy cut
into a stencil (a few thin procedural breaks through every glyph, like a sheet-metal letter mask).

Safe area in the 1080x1920 output: not above y=220, not below y=1500, not right of x=940 (left margin 50).
A Block is rendered once into a crop: mask (float32 0..1), its origin, and one box per character in output pixels.
"""
import functools
import math
import os
import re

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, 'work', 'fonts', 'SourceHanSansCN-Heavy.otf')
SAFE_X0, SAFE_X1, SAFE_Y0, SAFE_Y1 = 50, 940, 220, 1500
SAFE_W = SAFE_X1 - SAFE_X0


def rows_of(text):
    """Split a lyric line into rows of 2-5 sung characters at its own phrase breaks."""
    phrases = [''.join(c for c in p if '一' <= c <= '鿿' or c.isdigit()) for p in text.split()]
    phrases = [p for p in phrases if p]
    rows = []
    for p in phrases:
        if len(p) <= 5:
            rows.append(p)
        else:
            rows += _split(p)
    # a one-character row joins a neighbour when that keeps the row within five
    out = []
    for r in rows:
        if out and (len(r) == 1 or len(out[-1]) == 1) and len(out[-1]) + len(r) <= 5:
            out[-1] += r
        else:
            out.append(r)
    return out


PARTICLES = set('了的着过吗啊呢吧')


def _split(p):
    """Break a phrase longer than five into the fewest rows of 2-5, preferring word boundaries (jieba) and even rows."""
    import itertools
    import jieba
    jieba.setLogLevel(60)
    for w in ('看懂', '捡到', '一千八百万', '下一个', '换个'):   # common words jieba splits wrongly
        jieba.add_word(w, 2000)
    cuts, k = set(), 0
    for w in jieba.cut(p, HMM=True):
        k += len(w)
        cuts.add(k)
    best = None
    n0 = math.ceil(len(p) / 5)
    for n in (n0, n0 + 1):
        for pos in itertools.combinations(range(2, len(p) - 1), n - 1):
            edges = (0,) + pos + (len(p),)
            lens = [b - a for a, b in zip(edges, edges[1:])]
            if min(lens) < 2 or max(lens) > 5:
                continue
            cost = 0.5 * (max(lens) - min(lens)) + 3 * sum(1 for x in pos if x not in cuts) \
                + 2 * sum(1 for x in pos if p[x] in PARTICLES) + 1.0 * (n - n0)
            if best is None or cost < best[0]:
                best = (cost, edges)
    edges = best[1]
    return [p[a:b] for a, b in zip(edges, edges[1:])]


@functools.lru_cache(maxsize=64)
def _font(px):
    return ImageFont.truetype(FONT, px)


def _glyph(ch, cell, seed, cuts=True, thin=0.0):
    f = _font(int(cell * 0.92))
    im = Image.new('L', (cell, cell), 0)
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = d.textbbox((0, 0), ch, font=f)
    d.text(((cell - (x1 - x0)) / 2 - x0, (cell - (y1 - y0)) / 2 - y0), ch, font=f, fill=255)
    g = np.asarray(im, np.float32) / 255.0
    if thin > 0:
        k = max(1, int(round(cell * thin)))
        g = cv2.erode(g, np.ones((k, k), np.uint8))
    if cuts:
        rng = np.random.default_rng(seed)
        cutw = max(2, int(round(cell * 0.032)))
        m = np.ones((cell, cell), np.uint8) * 255
        # one near-horizontal and one near-vertical break, plus sometimes a short diagonal one
        y = int(cell * rng.uniform(0.38, 0.62))
        a = rng.uniform(-0.12, 0.12)
        cv2.line(m, (0, int(y - a * cell / 2)), (cell, int(y + a * cell / 2)), 0, cutw)
        x = int(cell * rng.uniform(0.33, 0.67))
        b = rng.uniform(-0.1, 0.1)
        cv2.line(m, (int(x - b * cell / 2), 0), (int(x + b * cell / 2), cell), 0, cutw)
        if rng.random() < 0.5:
            p = rng.uniform(0.15, 0.85, 4) * cell
            cv2.line(m, (int(p[0]), int(p[1])), (int(p[2]), int(p[3])), 0, cutw)
        g = g * (m.astype(np.float32) / 255.0)
    return g


class Block:
    def __init__(self, text, cy, width=0.82, cx=None, cuts=True, thin=0.0, rot=0.0, seed=0, cap=260):
        self.rows = rows_of(text)
        nmax = max(len(r) for r in self.rows)
        cell = int(min(cap, width * SAFE_W / nmax))
        self.cell = cell
        lead = int(cell * 1.08)
        hgt = lead * len(self.rows)
        cx = (SAFE_X0 + SAFE_X1) / 2 if cx is None else cx
        top = int(round(cy - hgt / 2))
        top = max(SAFE_Y0, min(SAFE_Y1 - hgt, top))
        pad = int(cell * 0.4)
        widest = nmax * cell
        self.ox = int(cx - widest / 2) - pad
        self.oy = top - pad
        self.mask = np.zeros((hgt + 2 * pad, widest + 2 * pad), np.float32)
        self.boxes = []          # per character: (x0, y0, x1, y1) in output pixels
        rng = np.random.default_rng(seed)
        k = 0
        for ri, r in enumerate(self.rows):
            rx = int(cx - len(r) * cell / 2)
            ry = top + ri * lead
            for ch in r:
                g = _glyph(ch, cell, seed * 100 + k, cuts=cuts, thin=thin)
                if rot:
                    ang = rng.uniform(-rot, rot)
                    M = cv2.getRotationMatrix2D((cell / 2, cell / 2), ang, 1.0)
                    M[:, 2] += rng.normal(0, cell * 0.03, 2)
                    g = cv2.warpAffine(g, M, (cell, cell))
                x0, y0 = rx - self.ox, ry - self.oy
                self.mask[y0:y0 + cell, x0:x0 + cell] = np.maximum(self.mask[y0:y0 + cell, x0:x0 + cell], g)
                self.boxes.append((rx, ry, rx + cell, ry + cell))
                rx += cell
                k += 1
        self.n = k
        self.bbox = (self.ox, self.oy, self.ox + self.mask.shape[1], self.oy + self.mask.shape[0])

    def full(self, weights=None, sweep=None, dx=0.0):
        """Full-frame mask. weights: per-char multipliers; sweep: per-char reveal fraction 0..1 (left to right)."""
        from look import W, H
        out = np.zeros((H, W), np.float32)
        m = self.mask
        if sweep is not None or weights is not None:
            m = m.copy()
            xs = np.arange(m.shape[1], dtype=np.float32) + self.ox
            for i, (x0, y0, x1, y1) in enumerate(self.boxes):
                ys, ye = y0 - self.oy, y1 - self.oy
                xs0, xe = x0 - self.ox, x1 - self.ox
                w = 1.0 if weights is None else float(weights[i])
                if sweep is not None:
                    f = float(sweep[i])
                    if f <= 0:
                        m[ys:ye, xs0:xe] = 0
                        continue
                    edge = x0 + f * (x1 - x0) * 1.25 - 0.12 * (x1 - x0)
                    ramp = np.clip((edge - xs[xs0:xe]) / (0.18 * (x1 - x0)) + 0.5, 0, 1)
                    m[ys:ye, xs0:xe] *= ramp[None, :] * w
                elif w != 1.0:
                    m[ys:ye, xs0:xe] *= w
        ox = int(round(self.ox + dx))
        x0, y0 = max(0, ox), max(0, self.oy)
        x1, y1 = min(W, ox + m.shape[1]), min(H, self.oy + m.shape[0])
        if x1 > x0 and y1 > y0:
            out[y0:y1, x0:x1] = m[y0 - self.oy:y1 - self.oy, x0 - ox:x1 - ox]
        return out
