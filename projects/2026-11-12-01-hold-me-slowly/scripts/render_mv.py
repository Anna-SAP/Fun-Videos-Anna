#!/usr/bin/env python3
"""Render the lyric film frame by frame.

  render_mv.py --preview 7.5,15.0,...      single frames -> work/preview/p_<t>.png (simulates from 0)
  render_mv.py --all OUT.mkv               every frame, piped to ffmpeg (x264 CRF 12, a master for finish)
  render_mv.py --range T0 T1 OUT.mkv       part of the film (still simulates from 0, composes from T0)

The flow is a simulation, so every frame depends on all the frames before it: rendering is sequential.
"""
import argparse
import math
import os
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inkwater as iw  # noqa: E402
import score as sc  # noqa: E402
from inkwater import GH, GW, H, QH, QW, S, W  # noqa: E402

ROOT = sc.ROOT


def soft_blob(h, w, cx, cy, sig):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sig * sig))


class Film:
    def __init__(self):
        self.fl = iw.Fluid(seed=7)
        self.burstnoise = iw.Fluid(seed=99)
        self.burstnoise.k *= 1.3                       # finer swirls for letting go
        self.ink = iw.Ink()
        self.ring = iw.Ink(scale=2)              # the embrace: its own long-lived layer
        self.caus = iw.Caustics()
        self.motes = iw.Motes()
        self.film = iw.Film()
        self.words, self.caps = sc.score()
        eyes = [w for w in self.words if w.line == 8 and w.idx == 6][0]
        bb = eyes.bbox()
        self.rip = iw.Ripples(sc.drops() + [sc.last_drop(((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2))])
        for w in self.words:
            self._prep(w)
        # vortex template (counter-clockwise on screen), ring radius ~372 px
        yy, xx = np.mgrid[0:GH, 0:GW].astype(np.float32)
        dx, dy = xx - GW / 2, yy - GH / 2
        r = np.sqrt(dx * dx + dy * dy) + 1e-3
        prof = np.exp(-((r - 64) / 26.0) ** 2) + 0.18 * np.clip(r / 64, 0, 1)
        self.vu = (dy / r) * prof
        self.vv = (-dx / r) * prof
        self.ry = (np.arange(QH, dtype=np.float32) * 4 + 2) / H
        self.moon_q = (0.18 + 0.82 * (1 - self.ry) ** 1.6)[:, None] * np.ones((1, QW), np.float32)
        self.yfull = (np.arange(H, dtype=np.float32) / H)[:, None, None]
        self.t_prev = -1.0 / sc.FPS
        self.fi = -1
        self.released = set()

    # ----------------------------------------------------------------- per-word precomputation
    def _place(self, m, px, py):
        """A full-frame-sized coverage mask at sim resolution for a mask placed at (px, py)."""
        out = np.zeros((GH, GW), np.float32)
        h, w = m.shape
        small = cv2.resize(m, (max(1, w // S), max(1, h // S)), interpolation=cv2.INTER_AREA)
        x0, y0 = px // S, py // S
        sh, sw = small.shape
        a0, b0 = max(0, y0), max(0, x0)
        a1, b1 = min(GH, y0 + sh), min(GW, x0 + sw)
        if a1 > a0 and b1 > b0:
            out[a0:a1, b0:b1] = small[a0 - y0:a1 - y0, b0 - x0:b1 - x0]
        return out

    def _prep(self, w):
        area = self._place(w.m, w.px, w.py)
        w.area = area / max(area.max(), 1e-6)
        st = cv2.dilate((w.area > 0.04).astype(np.float32), np.ones((7, 7), np.uint8))
        w.still_m = np.clip(cv2.GaussianBlur(st, (0, 0), 1.6) * 1.4, 0, 1)
        er = cv2.dilate((w.area > 0.04).astype(np.float32), np.ones((11, 11), np.uint8))
        w.erase_m = np.clip(cv2.GaussianBlur(er, (0, 0), 2.5) * 1.3, 0, 1)
        if w.unclench:
            n = len(w.text)
            c = (n - 1) / 2
            w.states = []
            for k in range(25):
                a = sc.ease(k / 24)
                spread = [((i - c) / max(c, 1)) * (-0.42 * (1 - a) + 0.035 * a) for i in range(n)]
                m, by, lx, adv = sc.glyphs(w.text, w.fnt, spread=spread)
                w.states.append((m, int(round(w.x - lx)), int(round(w.base - by))))
            m, px, py = w.states[0]
            w.m_tight = m
            w.px_t, w.py_t = px, py

    # ----------------------------------------------------------------- deposits
    def deposit(self, m, px, py, color, emis, scat, bleed=0.4):
        f = self.ink.f
        h, w = m.shape
        x0, y0 = max(px, 0), max(py, 0)
        x1, y1 = min(px + w, W), min(py + h, H)
        if x1 <= x0 or y1 <= y0:
            return
        d = m[y0 - py:y1 - py, x0 - px:x1 - px]
        if bleed:
            d = d + bleed * cv2.GaussianBlur(d, (0, 0), 7.0)
        f[y0:y1, x0:x1, :3] += d[..., None] * (color * emis)
        f[y0:y1, x0:x1, 3] += d * scat

    def blob(self, cx, cy, sig, color, emis, scat):
        r = int(sig * 3)
        x0, y0 = int(cx - r), int(cy - r)
        m = soft_blob(2 * r, 2 * r, cx - x0, cy - y0, sig)
        self.deposit(m, x0, y0, color, emis, scat, bleed=0)

    def unclench_state(self, w, t):
        a0 = w.t0 - 0.07 + w.write_span()[1]
        k = sc.ease((t - a0) / 1.1)
        return w.states[int(round(k * 24))], k

    # ----------------------------------------------------------------- one frame of simulation
    def step(self):
        self.fi += 1
        t = self.fi / sc.FPS
        tp = self.t_prev
        fl = self.fl
        still = np.zeros((GH, GW), np.float32)
        for w in self.words:
            s = w.still(t)
            if s > 0:
                np.maximum(still, w.still_m * s, out=still)

        # current: slow curl noise + chorus ring vortex
        nu, nv = fl.noise(t)
        A, V = sc.ambient(t), sc.vortex(t)
        tu, tv = A * nu + V * self.vu, A * nv + V * self.vv
        relax = 0.05
        bu = np.zeros((GH, GW), np.float32)
        bv = np.zeros((GH, GW), np.float32)
        busy = False
        for w in self.words:
            if w.hold <= t and (w.line, w.idx) not in self.released:
                self.released.add((w.line, w.idx))
                lift = w.area * w.lift
                if w.streaks:
                    cols = np.arange(GW, dtype=np.float32)
                    lift = lift * (0.55 + 0.45 * np.sin(cols * 1.9) ** 2)[None, :]
                fl.lift += lift
            if w.burst and w.hold <= t < w.hold + 1.0:
                e = math.sin(math.pi * (t - w.hold) / 1.0) * w.burst
                bu += e * w.still_m
                busy = True
        if busy:
            n2u, n2v = self.burstnoise.noise(t * 2.0)
            bu, bv = bu * n2u * 0.03, bu * n2v * 0.03
        # warm plume into the pre-chorus, breath in the intro
        p = sc.plume(t)
        if p:
            x, y, k = p
            g = soft_blob(GH, GW, x / S, y / S, 30)
            tv = tv - g * 1.5 * k
            fl.lift += g * 0.012 * k
        e = sc.exhale(t)
        if e:
            x, y, k = e
            g = soft_blob(GH, GW, x / S, y / S, 12)
            tv = tv - g * 0.5 * k
        fl.step(tu, tv, relax, 0.03, 0.12, 0.985, bu if busy else None, bv if busy else None)

        # ink: carried by the flow except where held; released ink fades
        base = 0.5 ** (1.0 / (sc.half_life(t) * sc.FPS))
        decay = 1.0 - (1.0 - base) * (1.0 - still)
        # what stays where a word was fades fast once it is let go; what drifted away lingers as smoke
        for w in self.words:
            if w.erase and w.hold + 0.25 <= t < w.hold + w.release + 3.0:
                ef = 0.5 ** (1.0 / (w.erase * sc.FPS))
                env = sc.ease((t - w.hold - 0.25) / 0.6)
                np.minimum(decay, 1.0 - (1.0 - ef) * w.erase_m * env * (1.0 - still), out=decay)
        self.ink.advect(fl.u, fl.v, still, decay.astype(np.float32), diffuse=0.32, edecay=0.5 ** (1.0 / (sc.half_life(t) * 0.55 * sc.FPS)))

        # sources
        if p:
            x, y, k = p
            for dx in (-90, 80):
                self.blob(x + dx, y - 40, 60, sc.AMBER * 0.6 + sc.ROSE * 0.25, 0.034 * k, 0.02 * k)
        if e:
            x, y, k = e
            self.blob(x, y, 30, sc.MOON, 0.0035 * k, 0.012 * k)
        if sc.vortex(t) > 0:
            zero = np.zeros((GH, GW), np.float32)
            rb = 0.5 ** (1.0 / (5.0 * sc.FPS))
            self.ring.advect(fl.u, fl.v, zero, np.full((GH, GW), rb, np.float32), diffuse=0.08)
            for x, y, col, k in sc.ring_sources(t):
                r = 12
                xs, ys = x / 2, y / 2
                x0, y0 = int(xs - r), int(ys - r)
                m = soft_blob(2 * r, 2 * r, xs - x0, ys - y0, 3.5)
                self.ring.f[y0:y0 + 2 * r, x0:x0 + 2 * r, :3] += m[..., None] * col * (0.2 * k)

        # writing
        for w in self.words:
            if w.unclench:
                a, d = w.write_span()
                if a <= t:
                    if t < a + d:      # written tight
                        p0, p1 = w.reveal(tp), w.reveal(t)
                        if p1 > p0:
                            pass       # drawn as an overlay in compose(); deposited when it has opened
                    else:
                        (m, px, py), k = self.unclench_state(w, t)
                        if k < 1.0:
                            self.deposit(m, px, py, w.color, w.emis * 0.008, w.scat * 0.01, bleed=1.0)
                        elif not getattr(w, 'done', False):
                            w.done = True
                            self.deposit(m, px, py, w.color, w.emis, w.scat)
                continue
            p0, p1 = w.reveal(tp), w.reveal(t)
            if p1 > p0:
                d = w.m * (w.wipe(p1) - w.wipe(p0))
                self.deposit(d, w.px, w.py, w.color, w.emis, w.scat)
        np.minimum(self.ink.f, 3.0, out=self.ink.f)
        self.motes.step(fl.u, fl.v, still, 0.35 + 2.2 * A)
        self.still = still
        self.t_prev = t
        return t

    # ----------------------------------------------------------------- compose a frame
    def compose(self, t):
        f = self.ink.f
        cool = sc.cool_light(t)
        wx, wy, wr, wi = sc.warm(t)
        top, bot = sc.water_tint(t)
        warm_col = np.float32([1.0, 0.62, 0.32])
        glow = iw.glow_q(wx, wy, wr) * wi
        light_q = (self.moon_q * cool)[..., None] * sc.MOON * 0.55 + glow[..., None] * warm_col * 0.9
        # water
        bg = (top * (1 - self.ry[:, None, None]) + bot * self.ry[:, None, None]) * np.ones((1, QW, 1), np.float32)
        caus = self.caus(t)
        caus = cv2.GaussianBlur(caus, (0, 0), 1.2)
        bg = bg + (caus * self.moon_q ** 1.5 * cool * 0.016)[..., None] * sc.MOON
        bg = bg + glow[..., None] * warm_col * 0.07 + (iw.glow_q(wx, wy, wr * 0.22) * wi * 0.35)[..., None] * warm_col
        # ink at quarter res for occlusion and rays
        fq = cv2.resize(f, (QW, QH), interpolation=cv2.INTER_AREA)
        dens_q = 1 - np.exp(-fq[..., 3] * 1.3)
        g = sc.rays_gain(t)
        if g > 0:
            src = (iw.glow_q(wx, wy, wr * 0.45) * wi * (1 - dens_q))[..., None] * warm_col * 0.6
            src = src + (1 - np.exp(-fq[..., :3] * 1.3)) * 0.18
            rays = iw.radial_blur(src, wx, wy, n=24, reach=0.6) * g * 0.42
            bg = bg + rays
        # moonlight shafts from above the surface, broken by the ink
        msrc = (caus * self.moon_q ** 3 * cool * (1 - dens_q))[..., None] * sc.MOON * 0.05
        bg = bg + iw.radial_blur(msrc, 0.38 * W, -0.35 * H, n=20, reach=0.5) * 0.9
        bg = bg * (1 - 0.45 * dens_q[..., None])
        lin = cv2.resize(bg, (W, H), interpolation=cv2.INTER_LINEAR)
        # ink: its own light plus the light it catches
        E = f[..., :3]
        D = f[..., 3:4]
        light = cv2.resize(light_q, (W, H), interpolation=cv2.INTER_LINEAR)
        lin += (1 - np.exp(-E * 1.25)) * 1.05 + (1 - np.exp(-D * 1.1)) * light * 0.38
        if sc.vortex(t) > 0:
            R = cv2.resize(self.ring.f[..., :3], (W, H), interpolation=cv2.INTER_LINEAR)
            lin += (1 - np.exp(-R * 1.25)) * 1.05
        # overlays: 'unclench' while it is being written tight and while it opens
        for w in self.words:
            if w.unclench:
                a, d = w.write_span()
                if a <= t and not getattr(w, 'done', False) and t < a + d + 1.2:
                    if t < a + d:
                        m, px, py = w.m_tight, w.px_t, w.py_t
                        cols = (np.arange(m.shape[1], dtype=np.float32) - px * 0) / m.shape[1]
                        wipe = np.clip(((t - a) / d * 1.2 - cols) / 0.2, 0, 1)[None, :]
                        m = m * wipe
                    else:
                        (m, px, py), _ = self.unclench_state(w, t)
                    h, ww = m.shape
                    x0, y0, x1, y1 = max(px, 0), max(py, 0), min(px + ww, W), min(py + h, H)
                    mm = m[y0 - py:y1 - py, x0 - px:x1 - px]
                    lin[y0:y1, x0:x1] += (1 - np.exp(-mm[..., None] * w.color * w.emis * 1.25)) * 1.05
        # motes
        mo = self.motes.render(t, light_q, 0.55 * (0.4 + 0.6 * cool) + 0.3 * wi)
        lin += cv2.resize(mo, (W, H), interpolation=cv2.INTER_LINEAR)
        # surface: raindrop rings refract and catch the moon
        h, spark = self.rip.field(t)
        if h is not None:
            gy, gx = np.gradient(h)
            dx = cv2.resize(gx * 22.0, (W, H), interpolation=cv2.INTER_LINEAR)
            dy = cv2.resize(gy * 22.0, (W, H), interpolation=cv2.INTER_LINEAR)
            lin = cv2.remap(lin, self.ink.X + dx, self.ink.Y + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            spec = np.clip(-gx * 0.5 - gy * 0.85, 0, None) ** 2 * 1.6 + spark * 0.5
            spec = spec * (0.35 + 0.65 * cool) * (0.5 + 0.5 * self.moon_q)
            lin += cv2.resize(spec, (W, H), interpolation=cv2.INTER_LINEAR)[..., None] * np.float32([0.75, 0.82, 1.0])
        # camera
        z = sc.zoom(t)
        cx, cy = sc.cam_center(t)
        M = np.float32([[z, 0, W / 2 - z * cx], [0, z, H / 2 - z * cy]])
        lin = cv2.warpAffine(lin, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        # quiet printed translation
        for c in self.caps:
            a = c.alpha(t)
            if a > 0:
                h_, w_ = c.m.shape
                x0, y0 = c.px, c.py
                lin[y0:y0 + h_, x0:x0 + w_] += c.m[..., None] * (a * 0.42) * np.float32([0.92, 0.84, 0.76])
        warmth = sc.kf(t, [(0, 0.0), (21, 0.2), (sc.T_PRE, 0.8), (sc.B(12), 1.0)])
        out = self.film(lin, max(self.fi, 0), 1.0, sc.fade(t), warmth)
        return (out * 255 + 0.5).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview', default=None)
    ap.add_argument('--all', default=None)
    ap.add_argument('--range', nargs=3, default=None)
    a = ap.parse_args()
    fm = Film()
    if a.preview:
        ts = sorted(float(x) for x in a.preview.split(','))
        want = {int(round(x * sc.FPS)): x for x in ts}
        os.makedirs(os.path.join(ROOT, 'work/preview'), exist_ok=True)
        t0 = time.time()
        while fm.fi < max(want):
            fm.step()
            if fm.fi in want:
                img = fm.compose(fm.fi / sc.FPS)
                p = os.path.join(ROOT, f'work/preview/p_{want[fm.fi]:06.2f}.png')
                cv2.imwrite(p, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
                print('wrote', p, f'{time.time() - t0:.0f}s', flush=True)
        return
    out = a.all or a.range[2]
    f0 = 0 if a.all else int(round(float(a.range[0]) * sc.FPS))
    f1 = sc.NFRAMES if a.all else int(round(float(a.range[1]) * sc.FPS))
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(sc.FPS),
           '-i', '-', '-vf', 'scale=out_color_matrix=bt709:out_range=tv', '-c:v', 'libx264', '-preset', 'medium', '-crf', '12',
           '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', out + '.tmp.mkv']
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    while fm.fi < f1 - 1:
        fm.step()
        if fm.fi >= f0:
            pr.stdin.write(fm.compose(fm.fi / sc.FPS).tobytes())
        if fm.fi % 60 == 0:
            el = time.time() - t0
            print(f'frame {fm.fi}/{f1} {el:.0f}s  eta {el / (fm.fi + 1) * (f1 - fm.fi - 1):.0f}s', flush=True)
    pr.stdin.close()
    pr.wait()
    os.replace(out + '.tmp.mkv', out)
    print('done', out, f'{time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
