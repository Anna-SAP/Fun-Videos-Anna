#!/usr/bin/env python3
"""Plates, grades, particles, bloom and the finish. Images are float32 RGB 0..1 (linear-ish display values).

Plates: a keyframe is read once (RGB + depth, 0 far .. 1 near) and resampled per frame into the 1080x1920 output
through a 1040-wide window (scale 1080/1040) times the shot's push, with depth parallax: near pixels slide further
than far ones along the shot's parallax direction as the shot's clock runs.
Particles: every flowing thing (sparks, embers, sand, snow, petals, spray, confetti, shards) is a field of points
whose positions read phi(t), the variable clock, so they freeze in the song's stops; they are hidden behind
anything nearer than their own layer (the depth map).
"""
import functools
import os

import cv2
import numpy as np

cv2.setNumThreads(1)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1080, 1920
BASE = 1080 / 1040
Q = 4
WQ, HQ = W // Q, H // Q
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)


@functools.lru_cache(maxsize=6)
def plate(kf):
    im = cv2.imread(os.path.join(ROOT, 'work', 'keyframes', f'{kf}.png'), cv2.IMREAD_COLOR)
    rgb = im[..., ::-1].astype(np.float32) / 255.0
    d = cv2.imread(os.path.join(ROOT, 'work', 'depth', f'{kf}.png'), cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535.0
    d = cv2.GaussianBlur(d, (0, 0), 2.0)
    return rgb, d


def affine(z, c, dx=0.0, dy=0.0):
    s = BASE * z
    cx, cy = c
    return np.array([[s, 0, W / 2 - s * cx + dx], [0, s, H / 2 - s * cy + dy]], np.float32)


def render_plate(kf, z, c, par_vec, focus=0.45, shake=(0.0, 0.0)):
    """Resample keyframe kf into the output with push z about c and depth parallax par_vec (output px, near-far)."""
    rgb, d = plate(kf)
    M = affine(z, c, shake[0], shake[1])
    Minv = cv2.invertAffineTransform(M)
    D = cv2.warpAffine(d, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    px, py = par_vec
    s = BASE * z
    # output pixel (x, y) shows keyframe point Minv*(x - par*(D-focus)); one Jacobi step with the warped depth
    ox = XX - px * (D - focus)
    oy = YY - py * (D - focus)
    mx = (Minv[0, 0] * ox + Minv[0, 1] * oy + Minv[0, 2]).astype(np.float32)
    my = (Minv[1, 0] * ox + Minv[1, 1] * oy + Minv[1, 2]).astype(np.float32)
    out = cv2.remap(rgb, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    Dn = cv2.remap(d, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return out, Dn, M


# ---- grades -------------------------------------------------------------------------------------------------
GRADES = {
    #          lift (rgb)            gain (rgb)          sat   contrast
    'night': ((0.010, 0.016, 0.030), (0.96, 1.00, 1.06), 1.00, 1.06),
    'dusk': ((0.012, 0.014, 0.028), (1.03, 1.00, 1.02), 1.05, 1.06),
    'day': ((0.000, 0.004, 0.010), (1.02, 1.01, 0.98), 1.04, 1.05),
    'fire': ((0.020, 0.008, 0.004), (1.07, 0.98, 0.92), 1.08, 1.08),
    'dawn': ((0.014, 0.008, 0.012), (1.06, 1.00, 0.93), 1.08, 1.06),
    'ghost': ((0.004, 0.016, 0.012), (0.92, 1.02, 0.96), 0.78, 1.08),
    'void': ((0.020, 0.004, 0.030), (0.98, 0.92, 1.08), 1.06, 1.10),
    'neon': ((0.012, 0.006, 0.020), (1.04, 0.98, 1.04), 1.14, 1.08),
    'lamp': ((0.016, 0.010, 0.006), (1.06, 1.00, 0.92), 1.00, 1.05),
    'arena': ((0.006, 0.006, 0.016), (1.00, 1.00, 1.04), 1.06, 1.10),
    'sepia': ((0.040, 0.030, 0.016), (1.02, 0.94, 0.80), 0.30, 0.92),
}


def grade(img, name, energy=0.5):
    if name == 'sepia':
        # a faded old photograph: monochrome, toned warm after desaturating, low contrast, softened, lifted blacks
        lum = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        lum = (lum - 0.45) * 0.80 + 0.47
        out = lum[..., None] * np.array([1.10, 0.93, 0.70], np.float32) + np.array([0.05, 0.035, 0.015], np.float32)
        soft = cv2.GaussianBlur(out, (0, 0), 5.0)
        return out * 0.55 + soft * 0.45
    lift, gain, sat, con = GRADES.get(name, GRADES['night'])
    img = img * np.array(gain, np.float32) + np.array(lift, np.float32)
    lum = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    s = sat * (0.90 + 0.22 * energy)
    img = lum[..., None] + (img - lum[..., None]) * s
    c = con * (0.97 + 0.06 * energy)
    img = (img - 0.45) * c + 0.45
    return img


# ---- particles ----------------------------------------------------------------------------------------------
# preset: list of layers (n, size px, brightness, vx, vy (px per clock-second), wobble px, depth z (hidden behind
# nearer), colour, flicker, additive)
C_GOLD = (1.0, 0.70, 0.30)
C_EMBER = (1.0, 0.48, 0.14)
C_RED = (1.0, 0.25, 0.18)
C_TEAL = (0.35, 1.0, 0.92)
C_WHITE = (1.0, 0.97, 0.92)
C_SNOW = (0.92, 0.96, 1.0)
C_SAND = (1.0, 0.80, 0.52)
C_PINK = (1.0, 0.72, 0.82)
C_VIOLET = (0.72, 0.45, 1.0)
PRESETS = {
    'motes': [(160, 2.2, 0.25, 4, -10, 18, 0.7, C_WHITE, 0.5, True), (40, 4.0, 0.22, 6, -16, 30, 0.95, C_WHITE, 0.5, True)],
    'gold_motes': [(220, 2.0, 0.35, 5, -14, 20, 0.7, C_GOLD, 0.6, True), (60, 4.0, 0.30, 8, -22, 30, 0.95, C_GOLD, 0.6, True)],
    'teal_motes': [(240, 2.0, 0.40, 3, -18, 20, 0.7, C_TEAL, 0.6, True), (60, 4.2, 0.35, 5, -28, 34, 0.95, C_TEAL, 0.6, True)],
    'embers': [(420, 1.6, 0.55, 14, -90, 26, 0.6, C_EMBER, 0.9, True), (160, 2.8, 0.70, 20, -150, 40, 0.85, C_EMBER, 0.9, True),
               (30, 5.0, 0.55, 30, -240, 60, 1.01, C_GOLD, 0.9, True)],
    'embers_small': [(90, 1.6, 0.55, 6, -60, 18, 0.7, C_EMBER, 0.9, True), (20, 3.0, 0.6, 8, -90, 26, 1.01, C_EMBER, 0.9, True)],
    'embers_red': [(380, 1.6, 0.55, 10, -80, 26, 0.6, C_RED, 0.9, True), (120, 3.0, 0.65, 16, -130, 40, 0.9, C_RED, 0.9, True)],
    'snow': [(1600, 1.2, 0.35, 10, 40, 16, 0.5, C_SNOW, 0.1, True), (500, 2.2, 0.5, 16, 70, 26, 0.8, C_SNOW, 0.1, True),
             (60, 5.0, 0.55, 24, 140, 40, 1.01, C_SNOW, 0.1, True)],
    'sand': [(2400, 1.3, 0.30, 320, 20, 8, 0.75, C_SAND, 0.2, True), (500, 2.2, 0.35, 520, 30, 12, 0.95, C_SAND, 0.2, True)],
    'petals': [(140, 3.0, 0.55, 120, 50, 40, 0.75, C_PINK, 0.3, False), (40, 6.0, 0.6, 200, 80, 60, 1.01, C_PINK, 0.3, False)],
    'spray': [(500, 1.4, 0.45, 20, -40, 30, 0.8, C_WHITE, 0.4, True), (80, 3.0, 0.4, 30, -60, 40, 1.01, C_WHITE, 0.4, True)],
    'stars': [(260, 1.4, 0.7, 0, 0, 0, 0.35, C_WHITE, 1.0, True)],
    'void_motes': [(320, 1.8, 0.45, 0, 60, 30, 0.8, C_VIOLET, 0.8, True)],
    'mist_green': [],
    'confetti': [(260, 3.2, 0.7, 20, 90, 50, 0.8, C_GOLD, 1.0, False), (160, 3.2, 0.7, 20, 110, 50, 0.9, (0.85, 0.9, 1.0), 1.0, False)],
    'shards': [(300, 2.4, 0.7, 0, 0, 0, 1.01, C_RED, 0.6, True)],
    'dust': [(260, 2.0, 0.18, 60, -10, 20, 1.01, (0.9, 0.75, 0.55), 0.0, False)],
    'steam': [],
    'sand_neck': [],
}


class Field:
    def __init__(self, preset, seed):
        rng = np.random.default_rng(seed)
        self.layers = []
        for (n, size, br, vx, vy, wob, z, col, flick, add) in PRESETS[preset]:
            self.layers.append(dict(x=rng.uniform(0, W, n), y=rng.uniform(0, H, n), vx=rng.normal(vx, abs(vx) * 0.3 + 3, n),
                                    vy=rng.normal(vy, abs(vy) * 0.3 + 3, n), a=rng.uniform(0.4, 1.0, n) * br,
                                    ph=rng.uniform(0, 6.3, n), fq=rng.uniform(0.5, 3.0, n), size=size, wob=wob, z=z,
                                    col=np.array(col, np.float32), flick=flick, add=add))
        self.preset = preset

    def draw(self, ph, D, amount=1.0, rate=1.0):
        add = np.zeros((H, W, 3), np.float32)
        for L in self.layers:
            x = (L['x'] + L['vx'] * ph + L['wob'] * np.sin(L['ph'] + ph * L['fq'] * 0.7)) % W
            y = (L['y'] + L['vy'] * ph + 0.5 * L['wob'] * np.cos(L['ph'] * 1.3 + ph * L['fq'] * 0.5)) % H
            xi, yi = x.astype(np.int32), y.astype(np.int32)
            vis = D[yi, xi] < L['z']
            if self.preset == 'sand':
                vis &= yi > int(H * 0.52)
            a = L['a'] * (1 - L['flick'] * 0.5 * (1 + np.sin(L['ph'] * 7 + ph * L['fq'] * 9)))
            buf = np.zeros((H, W), np.float32)
            np.add.at(buf, (yi[vis], xi[vis]), a[vis])
            k = L['size']
            if self.preset == 'sand':
                # motion streaks along the wind, length from the clock's speed
                ln = int(max(1, 7 * rate))
                buf = cv2.blur(buf, (ln * 2 + 1, 1)) * (ln * 2 + 1) * 0.5
            buf = cv2.GaussianBlur(buf, (0, 0), max(0.6, k * 0.55)) * (k * k * 1.2)
            add += buf[..., None] * L['col'] * amount
        return add


@functools.lru_cache(maxsize=32)
def field(preset, seed=0):
    return Field(preset, 17 + seed * 31 + sum(map(ord, preset)))


# ---- haze (green mist, steam) ------------------------------------------------------------------------------
def _noise(shape, beta, seed):
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal(shape))
    ky = np.fft.fftfreq(shape[0])[:, None]
    kx = np.fft.fftfreq(shape[1])[None, :]
    k = np.sqrt(kx ** 2 + ky ** 2)
    k[0, 0] = 1
    n = np.real(np.fft.ifft2(f / k ** beta))
    return ((n - n.mean()) / n.std()).astype(np.float32)


@functools.lru_cache(maxsize=1)
def haze_tex():
    return [np.clip(0.5 + 0.35 * _noise((HQ * 2, WQ * 2), 1.5, 40 + i), 0, 1.2) for i in range(2)]


def haze(ph, Dq, vel=((10, -3), (-16, -5)), depth=(0.45, 0.8)):
    tex = haze_tex()
    F = np.zeros((HQ, WQ), np.float32)
    for i in range(2):
        ox = int(round(vel[i][0] * ph)) % tex[i].shape[1]
        oy = int(round(vel[i][1] * ph)) % tex[i].shape[0]
        t = np.roll(np.roll(tex[i], -oy, 0), -ox, 1)[:HQ, :WQ]
        F += t * np.clip((depth[i] - Dq) / 0.1 + 0.5, 0, 1) * 0.5
    return F


def up(q):
    return cv2.resize(q, (W, H), interpolation=cv2.INTER_LINEAR)


def down(img):
    return cv2.resize(img, (WQ, HQ), interpolation=cv2.INTER_AREA)


# ---- finish -------------------------------------------------------------------------------------------------
def bloom(img, thr=0.72, amt=0.35, sigma=7.0):
    q = down(img)
    lum = q.max(axis=2, keepdims=True)
    b = q * np.clip((lum - thr) / (1 - thr + 1e-6), 0, 1)
    b = cv2.GaussianBlur(b, (0, 0), sigma) + 0.5 * cv2.GaussianBlur(b, (0, 0), sigma * 3)
    return img + amt * up(b)


@functools.lru_cache(maxsize=1)
def grain_bank():
    rng = np.random.default_rng(3)
    out = []
    for i in range(12):
        g = rng.standard_normal((H // 2, W // 2)).astype(np.float32)
        g = cv2.resize(cv2.GaussianBlur(g, (0, 0), 0.6), (W, H), interpolation=cv2.INTER_LINEAR)
        out.append(g / g.std())
    return out


@functools.lru_cache(maxsize=1)
def vignette():
    r = np.sqrt(((XX - W / 2) / (W * 0.66)) ** 2 + ((YY - H / 2) / (H * 0.62)) ** 2)
    return (1 - 0.30 * np.clip(r, 0, 1.4) ** 2.0).astype(np.float32)[..., None]


def finish(img, k):
    img = img * vignette()
    g = grain_bank()[k % 12]
    lum = img.mean(axis=2, keepdims=True)
    img = img + g[..., None] * 0.012 * (0.25 + 4 * lum * (1 - lum).clip(0, 1))
    # soft shoulder instead of hard clipping
    img = np.where(img > 0.85, 0.85 + (1 - np.exp(-(img - 0.85) / 0.15)) * 0.15, img)
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
