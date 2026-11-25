#!/usr/bin/env python3
"""Plates, fog, snow and the film finish. Everything here is luminance (one float channel, 0..1) until colorize().

Plates: a keyframe is read once as luminance (plus depth, 0 far .. 1 near) and warped per frame into the
1080x1920 output through a 1040-wide window (scale 1080/1040) times the shot's push.
Fog: three noise layers at three depths, a quarter-resolution field that drifts with phi(t) and is hidden behind
anything nearer than its layer (the depth map). Snow: three layers of flakes, same clock, same occlusion.
Film: cold black and white, heavy 16 mm grain, 1-2 px gate weave, rare scratches; the grain index and the weave
read the film clock floor(phi*24), so they stop when the clock stops (the GAP).
"""
import functools
import os

import cv2
import numpy as np

cv2.setNumThreads(1)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1080, 1920
BASE = 1080 / 1040
Q = 4                       # fog / beam fields at quarter resolution
WQ, HQ = W // Q, H // Q
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
YQ, XQ = np.mgrid[0:HQ, 0:WQ].astype(np.float32) * Q


@functools.lru_cache(maxsize=8)
def plate(kf):
    im = cv2.imread(os.path.join(ROOT, 'work', 'keyframes', f'{kf}.png'), cv2.IMREAD_COLOR)
    lum = (cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0)
    d = cv2.imread(os.path.join(ROOT, 'work', 'depth', f'{kf}.png'), cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535.0
    return lum, d, im


def affine(z, c, dx=0.0, dy=0.0, rot=0.0):
    """2x3 matrix taking keyframe pixels to output pixels: scale BASE*z about keyframe point c -> output centre."""
    s = BASE * z
    a = np.deg2rad(rot)
    ca, sa = np.cos(a) * s, np.sin(a) * s
    cx, cy = c
    return np.array([[ca, -sa, W / 2 - ca * cx + sa * cy + dx],
                     [sa, ca, H / 2 - sa * cx - ca * cy + dy]], np.float32)


def warp(img, M, border=cv2.BORDER_REPLICATE, interp=cv2.INTER_LINEAR):
    return cv2.warpAffine(img, M, (W, H), flags=interp, borderMode=border)


# ---- fog ------------------------------------------------------------------------------------------
def _noise(shape, beta, seed):
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal(shape))
    ky = np.fft.fftfreq(shape[0])[:, None]
    kx = np.fft.fftfreq(shape[1])[None, :]
    k = np.sqrt(kx ** 2 + ky ** 2)
    k[0, 0] = 1
    n = np.real(np.fft.ifft2(f / k ** beta))
    n = (n - n.mean()) / n.std()
    return n.astype(np.float32)


@functools.lru_cache(maxsize=1)
def fog_tex():
    p = os.path.join(ROOT, 'work', 'fog_tex.npz')
    if os.path.exists(p):
        z = np.load(p)
        return [z[f't{i}'] for i in range(3)]
    tex = []
    for i, (beta, scale) in enumerate(((1.6, 1.0), (1.5, 1.0), (1.3, 1.0))):
        n = _noise((HQ * 2, WQ * 2), beta, 11 + i)
        tex.append(np.clip(0.55 + 0.32 * n, 0, 1.2))
    np.savez(p, **{f't{i}': t for i, t in enumerate(tex)})
    return tex


FOG_DEPTH = (0.28, 0.55, 0.82)
FOG_VEL = ((9.0, -2.0), (-14.0, -3.0), (22.0, -5.0))   # quarter-res px per second of phi


def fog_field(ph, Dq, dens=(0.35, 0.30, 0.22)):
    """Quarter-res fog density and a 'beam texture' (how much there is to light), both 0..1."""
    tex = fog_tex()
    F = np.zeros((HQ, WQ), np.float32)
    lit = np.zeros((HQ, WQ), np.float32)
    for i in range(3):
        vx, vy = FOG_VEL[i]
        ox = int(round(vx * ph)) % tex[i].shape[1]
        oy = int(round(vy * ph)) % tex[i].shape[0]
        t = np.roll(np.roll(tex[i], -oy, 0), -ox, 1)[:HQ, :WQ]
        vis = np.clip((FOG_DEPTH[i] - Dq) / 0.10 + 0.5, 0, 1)
        F += dens[i] * t * vis
        lit += t * vis * (0.5 + 0.25 * i)
    return np.clip(F, 0, 0.92), np.clip(lit, 0, 1.6)


def up(q):
    return cv2.resize(q, (W, H), interpolation=cv2.INTER_LINEAR)


def down(img):
    return cv2.resize(img, (WQ, HQ), interpolation=cv2.INTER_AREA)


# ---- snow -----------------------------------------------------------------------------------------
class Snow:
    LAYERS = ((2600, 0.18, 1.0, 38.0, 0.25), (900, 0.40, 1.6, 70.0, 0.55), (140, 0.75, 3.2, 150.0, 0.9))

    def __init__(self, seed=5):
        rng = np.random.default_rng(seed)
        self.layers = []
        for n, br, size, vy, z in self.LAYERS:
            self.layers.append(dict(x=rng.uniform(0, W, n), y=rng.uniform(0, H + 200, n), vx=rng.normal(6, 6, n),
                                    vy=rng.normal(vy, vy * 0.18, n), a=rng.uniform(0.5, 1.0, n) * br,
                                    ph=rng.uniform(0, 6.3, n), size=size, z=z))

    def draw(self, ph, D, amount=1.0):
        acc = np.zeros((H, W), np.float32)
        for L in self.layers:
            x = (L['x'] + L['vx'] * ph + 14 * np.sin(L['ph'] + ph * 0.7)) % W
            y = (L['y'] + L['vy'] * ph) % (H + 200) - 100
            m = (y >= 0) & (y < H)
            xi, yi = x[m].astype(int), y[m].astype(int)
            vis = D[yi, xi] < L['z']
            buf = np.zeros((H, W), np.float32)
            np.add.at(buf, (yi[vis], xi[vis]), L['a'][m][vis])
            k = L['size']
            buf = cv2.GaussianBlur(buf, (0, 0), k * 0.6) * (k * k * 0.9)
            acc += buf
        return np.clip(acc * amount, 0, 1)


# ---- film -----------------------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def grain_bank():
    rng = np.random.default_rng(3)
    out = []
    for i in range(16):
        g = rng.standard_normal((H // 2, W // 2)).astype(np.float32)
        g = cv2.GaussianBlur(g, (0, 0), 0.7)
        g = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)
        out.append(g / g.std())
    return out


@functools.lru_cache(maxsize=1)
def vignette():
    r = np.sqrt(((XX - W / 2) / (W * 0.62)) ** 2 + ((YY - H / 2) / (H * 0.62)) ** 2)
    return (1 - 0.22 * np.clip(r, 0, 1.4) ** 2.2).astype(np.float32)


def film(L, k, amp=0.075, weave=True):
    """k = film-clock frame index (stops when the clock stops)."""
    rng = np.random.default_rng(1000 + k)
    g = grain_bank()[rng.integers(16)]
    if rng.random() < 0.5:
        g = g[:, ::-1]
    w = 4 * L * (1 - L) + 0.06
    L = L + g * amp * w
    # rare scratches: a thin vertical line living a few frames
    srng = np.random.default_rng(77 + k // 5)
    if srng.random() < 0.18:
        x = int(srng.uniform(60, W - 60) + (k % 5) * srng.normal(0, 1.5))
        y0, y1 = sorted(srng.uniform(0, H, 2).astype(int))
        val = srng.choice([0.22, -0.18])
        L[y0:y1, x:x + 1] += val
        L[y0:y1, x + 1:x + 2] += val * 0.4
    L = L * vignette()
    if weave:
        dy = float(np.clip(rng.normal(0, 0.7), -1.8, 1.8))
        dx = float(np.clip(rng.normal(0, 0.25), -0.6, 0.6))
        L = cv2.warpAffine(L, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderMode=cv2.BORDER_REPLICATE)
    return L


def halation(L, amt=0.18):
    q = down(np.clip(L - 0.72, 0, 1))
    q = cv2.GaussianBlur(q, (0, 0), 6)
    return L + amt * up(q)


PRUSSIAN = np.array([11, 60, 93], np.float32) / 255.0


def colorize(L, prus=0.0):
    """Luminance -> RGB uint8. Cold neutral black and white, blended toward the white-to-Prussian-blue map."""
    L = np.clip(L, 0, 1)
    r = L * 0.955
    g = L * 0.985 + 0.004
    b = L * 1.0 + 0.018 * (1 - L)
    rgb = np.stack([r, g, b], -1)
    if prus > 0:
        t = L[..., None] ** 0.85
        pb = PRUSSIAN[None, None, :] * (1 - t) + t
        rgb = rgb * (1 - prus) + pb * prus
    return (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
