#!/usr/bin/env python3
"""Render the film.

  render.py TIMING.json --preview 12.3,45.6,...   single frames -> work/preview/f_<t>.png and a sheet
  render.py TIMING.json --segments [--jobs 4]      every 10 s segment -> work/segments/sNNN.mkv (skips existing)

One frame: the wall at time t through the camera (score.Film), lit by the section's look (a key light on the
line being sung, an ambient wash, the kick drum's pump, flashes on the big downbeats, dawn's window bars in
the outro), then bloom, depth of field, grade, vignette and grain.
"""
import argparse
import math
import os
import subprocess
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')
import cv2  # noqa: E402
import numpy as np  # noqa: E402

cv2.setNumThreads(1)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post  # noqa: E402
from score import Film, SECTIONS, bar, section, WW, PANEL, D1, D2, LIST_Y0, LIST_Y1  # noqa: E402
from wall import Camera, render_board, RATIO, W, H  # noqa: E402

FPS = 30
SONG = 329.974
NFRAMES = int(math.ceil(SONG * FPS))
SEG = 300

LOOKS = {
    #          key colour            key   ambient                sigma bloom  sat   tint
    'intro':  ((1.00, 0.78, 0.50), 1.15, (0.020, 0.024, 0.036), 3.0, 0.45, 0.95, (1.00, 0.98, 0.96)),
    'v1':     ((1.00, 0.84, 0.62), 1.30, (0.060, 0.074, 0.105), 3.2, 0.35, 0.95, (1.02, 1.00, 0.96)),
    'pre1':   ((1.00, 0.76, 0.55), 1.25, (0.050, 0.052, 0.080), 3.4, 0.40, 1.00, (1.00, 0.98, 0.96)),
    'ch1':    ((1.00, 0.62, 0.40), 1.45, (0.150, 0.045, 0.110), 4.2, 0.55, 1.10, (1.04, 0.98, 0.98)),
    'v2':     ((0.80, 0.90, 1.00), 1.30, (0.035, 0.075, 0.125), 3.2, 0.35, 0.95, (0.96, 1.00, 1.04)),
    'pre2':   ((0.92, 0.86, 0.92), 1.25, (0.050, 0.050, 0.090), 3.4, 0.40, 1.00, (1.00, 0.98, 1.00)),
    'ch2':    ((1.00, 0.56, 0.46), 1.45, (0.140, 0.040, 0.140), 4.2, 0.55, 1.10, (1.03, 0.98, 1.00)),
    'drop':   ((1.00, 0.96, 0.92), 1.50, (0.070, 0.095, 0.095), 5.0, 0.60, 1.05, (1.00, 1.00, 1.00)),
    'v3':     ((0.88, 0.82, 1.00), 1.25, (0.055, 0.045, 0.115), 3.2, 0.38, 0.95, (0.99, 0.97, 1.03)),
    'bridge': ((1.00, 0.80, 0.55), 1.05, (0.012, 0.012, 0.020), 2.4, 0.45, 0.90, (1.02, 0.99, 0.95)),
    'build':  ((1.00, 0.78, 0.55), 1.25, (0.050, 0.045, 0.060), 3.6, 0.45, 1.00, (1.02, 0.99, 0.96)),
    'fch':    ((1.00, 0.72, 0.46), 1.45, (0.170, 0.110, 0.075), 4.4, 0.55, 1.08, (1.04, 1.00, 0.95)),
    'outro':  ((1.00, 0.82, 0.58), 1.20, (0.190, 0.150, 0.120), 4.0, 0.45, 1.00, (1.05, 1.00, 0.94)),
}


def look(t):
    """the section's look, cross-faded over 0.8 s at each boundary."""
    for k, (nm, a, b) in enumerate(SECTIONS):
        if a <= t < b:
            cur = LOOKS[nm]
            if k and t < a + 0.8:
                prev = LOOKS[SECTIONS[k - 1][0]]
                s = (t - a) / 0.8
                s = s * s * (3 - 2 * s)
                return tuple(mix(p, c, s) for p, c in zip(prev, cur))
            return cur
    return LOOKS['outro']


def mix(a, b, s):
    if isinstance(a, tuple):
        return tuple(x + (y - x) * s for x, y in zip(a, b))
    return a + (b - a) * s


class Pump:
    """kick-drum pump from the instrumental's low band: instant attack, ~120 ms release."""

    def __init__(self):
        e = np.load('work/audio/env.npz')
        k = e['kick'].astype(np.float64)
        k = k / (np.percentile(k[k > 0], 99) + 1e-9)
        p = np.zeros_like(k)
        acc = 0.0
        for n, v in enumerate(k):
            acc = max(min(v, 1.2), acc * 0.86)
            p[n] = acc
        self.p = p
        self.lo = e['lo_db']

    def __call__(self, t):
        n = int(t * 100)
        return float(self.p[n]) if 0 <= n < len(self.p) else 0.0


def noise(t, seed):
    return (math.sin(t * 0.73 + seed) * 0.5 + math.sin(t * 1.37 + seed * 2.1) * 0.3 + math.sin(t * 2.91 + seed * 3.7) * 0.2)


class Renderer:
    def __init__(self, timing):
        self.film = Film(timing=timing)
        self.pump = Pump()
        f = self.film
        self.flashes = [(bar(28), 0.9), (bar(56), 0.9), (bar(97), 1.0), (bar(64), 0.8)]
        for li in (60, 61, 64, 65):
            if li in f.T:
                self.flashes.append((f.T[li][0][0], 0.5))
        for T in f.events.get('waves', []):
            self.flashes.append((T + 0.3, 0.35))
        self.flashes.append((f.events['wipe'], 0.25))
        self.flashes.append((f.events['rewrite'] + 0.4, 0.3))
        self.focus = f.focus

    def focus_rect(self, t):
        F = self.focus
        cur = np.array(F[0][1], np.float64)
        for k, (tf, r) in enumerate(F):
            if t >= tf + 0.7:
                cur = np.array(r, np.float64)
            elif t > tf:
                s = (t - tf) / 0.7
                s = s * s * (3 - 2 * s)
                cur = cur + (np.array(r) - cur) * s
                break
            else:
                break
        return tuple(cur)

    def focus_lights(self, t):
        """[(rect, weight)]: the key light slides to a neighbouring line (0.7 s), but for a long jump (another
        column of the wall, or between the list and the panel) it fades out where it was and in where it goes,
        over 0.35 s, so the first characters of the new line are already lit."""
        F = self.focus
        k = None
        for j, (tf, r) in enumerate(F):
            if tf <= t:
                k = j
            else:
                break
        if k is None:
            return [(tuple(F[0][1]), 1.0)]
        tf, r = F[k]
        if k == 0:
            return [(tuple(r), 1.0)]
        prev = self.focus_rect(tf - 1e-6)
        far = abs((r[0] + r[2]) / 2 - (prev[0] + prev[2]) / 2) + abs((r[1] + r[3]) / 2 - (prev[1] + prev[3]) / 2) > 8.0
        if not far:
            return [(self.focus_rect(t), 1.0)]
        s = min(1.0, (t - tf) / 0.35)
        s = s * s * (3 - 2 * s)
        if s >= 1.0:
            return [(tuple(r), 1.0)]
        return [(tuple(prev), 1.0 - s), (tuple(r), s)]

    def camera(self, t):
        cx, cy, vw, roll, tx, ty = self.film.camera(t)
        sec = section(t)
        pump = self.pump(t)
        punch = {'ch1': 0.022, 'ch2': 0.022, 'fch': 0.022, 'drop': 0.03, 'build': 0.012}.get(sec, 0.007)
        vw *= 1 - punch * pump
        vw *= 1 + 0.012 * math.sin(t * 2 * math.pi / 11.0)
        amp = vw / 11.0
        hand = 0.05 if sec != 'bridge' else 0.03
        cx += hand * amp * noise(t, 1.0)
        cy += hand * amp * noise(t, 2.0)
        roll += 0.004 * noise(t, 3.0)
        if sec in ('ch1', 'ch2', 'fch', 'drop'):
            roll += 0.006 * pump * (1 if int(t / (60 / 90)) % 2 else -1)
        return Camera(cx, cy, vw, roll, tx, ty)

    def frame(self, n):
        t = n / FPS
        f = self.film
        cam = self.camera(t)
        img, cov, Hm = render_board(f.board, t, cam)
        key_c, key_g, amb, sigma, bl, sat, tint = look(t)
        sec = section(t)
        pump = self.pump(t)
        # key light on the focus rect; pump and flicker by section
        g = key_g
        if sec in ('ch1', 'ch2', 'fch', 'drop'):
            g *= 1 + 0.22 * pump
        elif sec in ('pre1', 'pre2', 'build'):
            a, b = [(s0, s1) for nm, s0, s1 in SECTIONS if nm == sec][0]
            prog = (t - a) / (b - a)
            g *= 1 + 0.18 * prog * math.sin(t * 2 * math.pi * 6.0) ** 2
        else:
            g *= 1 + 0.08 * pump
        if sec == 'v2' and 120.0 < t < 125.6:          # the typhoon lines: the power is unsteady
            g *= 0.75 + 0.25 * (0.5 + 0.5 * math.sin(t * 37.0) * math.sin(t * 13.0))
        fl_ = self.focus_lights(t)
        r = max(fl_, key=lambda x: x[1])[0]
        lights = [{'rect': rr, 'sigma': sigma, 'gain': g * wgt, 'color': key_c} for rr, wgt in fl_ if wgt > 0.001]
        ambient = np.array(amb, np.float64)
        # build: the hall's lights come back on
        if sec == 'build':
            a, b = 246.09, 256.76
            ambient = ambient * (0.4 + 1.6 * (t - a) / (b - a))
        # final chorus after the rewrite and the outro: the whole wall is lit, warm
        tr = f.events['rewrite']
        if t > tr:
            s = min(1.0, (t - tr) / 3.0)
            lights.append({'rect': (0, 0, WW, LIST_Y1 * RATIO), 'sigma': 6.0, 'gain': 0.55 * s, 'color': (1.0, 0.80, 0.55)})
        if sec == 'outro':
            # dawn builds through the outro and is full by line 110 ("November: me too")
            t_full = f.start(110) if 110 in f.T else 308.0
            s = 0.15 + 0.85 * min(1.0, max(0.0, (t - 291.0) / (t_full - 291.0))) ** 1.3
            lights.append({'kind': 'bars', 'angle': -0.62, 'period': 7.5, 'duty': 0.55, 'soft': 0.10,
                           'offset': 0.35 * (t - 291.0), 'centre': (WW * 0.45, 22 * RATIO), 'radius': 34.0,
                           'gain': 0.85 * s, 'color': (1.0, 0.74, 0.42)})
        oth = f.events.get('others')
        if oth and oth[0] - 0.5 < t < oth[1] + 1.5:
            s = min(1.0, (t - oth[0] + 0.5) / 2.5) * min(1.0, (oth[1] + 1.5 - t) / 1.5)
            lights.append({'rect': (0, (LIST_Y0 - 1) * RATIO, WW, LIST_Y1 * RATIO), 'sigma': 10.0, 'gain': 0.30 * s,
                           'color': (1.0, 0.75, 0.45)})
        # wipe: the hall dims for a moment while the year flips away
        tw = f.events['wipe']
        if tw - 0.1 < t < tw + 2.4:
            ambient = ambient * 0.6
            lights.append({'rect': (0, 12 * RATIO, WW, LIST_Y1 * RATIO), 'sigma': 8.0, 'gain': 0.35, 'color': (0.8, 0.85, 1.0)})
        L = post.light_map(Hm, lights, ambient)
        img = img * L
        # flashes
        fl = 0.0
        for tf, a in self.flashes:
            if tf - 0.02 <= t < tf + 0.4:
                fl = max(fl, a * math.exp(-(t - tf) / 0.09))
        if fl > 0:
            img = img * (1 + 1.2 * fl) + 0.10 * fl
        # outside the wall: the dark hall, its far lights, the floor
        outside = (1 - cov)[..., None]
        base = np.array(amb, np.float32)[None, None] * 0.25
        img = img * cov[..., None] + base * outside
        if cov.min() < 0.99:
            warm = 1.0 if sec in ('fch', 'outro') else 0.3
            hg = 0.55 if sec in ('fch', 'outro') else (0.12 if sec == 'bridge' else 0.35)
            img = img + post.hall(Hm, cam.vw, warm, hg) * outside
            img = img + post.reflection(img, Hm, LIST_Y1 * RATIO, cov)
        img = post.bloom(img, thr=0.55, gain=bl)
        fy = self.focus_screen_y(Hm, r)
        strength = 0.0 if cam.vw > 20 else (0.55 if sec != 'bridge' else 0.8)
        img = post.dof(img, fy, 0.20 * H, strength)
        img = post.grade(img, sat=sat, tint=tint)
        img = post.vignette(img, 0.42 if sec != 'bridge' else 0.55)
        img = post.grain(img, n, 0.013)
        # fade in, fade out
        if t < 1.0:
            img = img * (t / 1.0) ** 1.5
        if t > SONG - 2.2:
            img = img * max(0.0, (SONG - t) / 2.2) ** 1.2
        return post.to_u8(img)

    @staticmethod
    def focus_screen_y(Hm, r):
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        p = Hm @ np.array([cx, cy, 1.0])
        return float(np.clip(p[1] / p[2], 0, H))


def render_segment(args):
    timing, k = args
    out = f'work/segments/s{k:03d}.mkv'
    if os.path.exists(out):
        return out
    R = Renderer(timing)
    n0, n1 = k * SEG, min(NFRAMES, (k + 1) * SEG)
    tmp = out + '.part.mkv'
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '15',
                          '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
    for n in range(n0, n1):
        p.stdin.write(R.frame(n).tobytes())
    p.stdin.close()
    p.wait()
    os.replace(tmp, out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('timing')
    ap.add_argument('--preview', default=None)
    ap.add_argument('--segments', action='store_true')
    ap.add_argument('--only', default=None)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--sheet', default='work/preview/sheet.jpg')
    a = ap.parse_args()
    if a.preview:
        R = Renderer(a.timing)
        ims = []
        for tt in a.preview.split(','):
            n = int(round(float(tt) * FPS))
            im = R.frame(n)
            cv2.imwrite(f'work/preview/f_{float(tt):07.2f}.png', im[..., ::-1])
            ims.append(cv2.resize(im, (360, 640), interpolation=cv2.INTER_AREA))
            print('frame', tt, flush=True)
        cols = min(6, len(ims))
        rows = []
        for i in range(0, len(ims), cols):
            row = ims[i:i + cols]
            row += [np.zeros_like(ims[0])] * (cols - len(row))
            rows.append(np.concatenate(row, 1))
        cv2.imwrite(a.sheet, np.concatenate(rows, 0)[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 88])
        return
    if a.segments:
        os.makedirs('work/segments', exist_ok=True)
        ks = list(range(int(math.ceil(NFRAMES / SEG))))
        if a.only:
            ks = [int(x) for x in a.only.split(',')]
        from multiprocessing import Pool
        with Pool(a.jobs) as pool:
            for out in pool.imap_unordered(render_segment, [(a.timing, k) for k in ks]):
                print('done', out, flush=True)


if __name__ == '__main__':
    main()
