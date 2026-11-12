#!/usr/bin/env python3
"""The world of the film: luminous ink in still night water, seen from above.

Everything on screen is computed here, frame by frame; no image was generated or downloaded.

  Fluid   2D incompressible flow on a 180x320 grid (6 px per cell): semi-Lagrangian advection, vorticity
          confinement, DCT pressure projection with closed walls. Driven by a slow curl-noise current, by
          buoyancy carried with the ink ("lift": a word that rises or sinks), by a ring vortex in the chorus
          and by short swirl bursts where a word is let go.
  Ink     One full-resolution field with 4 channels: RGB emission (the colour a word was written in) and a
          scattering density (how much light the ink catches). Advected with BFECC so written strokes stay
          sharp; every pixel moves with the flow times (1 - calm), so a word holds still while it is sung and
          drifts away after it is let go. "calm" also stops its decay.
  Light   Cold moonlight from the surface (top) with caustics; a warm light deep in the water ("you") whose
          position, size and strength follow the song; god rays from the warm light through the ink.
  Surface Raindrop rings: a height field whose slope refracts the whole image and catches a highlight.
  Motes   Suspended specks that ride the flow and catch the light.
  Film    Bloom, halation, a slow camera, filmic tone curve, grade, vignette, grain.
"""
import math

import cv2
import numpy as np
from scipy.fft import dctn, idctn

cv2.setNumThreads(4)

W, H = 1080, 1920
S = 6
GW, GH = W // S, H // S
QW, QH = W // 4, H // 4


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def srgb_to_lin(c):
    c = np.asarray(c, np.float32) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


# --------------------------------------------------------------------------------------------- fluid
class Fluid:
    def __init__(self, seed=7):
        rng = np.random.default_rng(seed)
        self.u = np.zeros((GH, GW), np.float32)
        self.v = np.zeros((GH, GW), np.float32)
        self.lift = np.zeros((GH, GW), np.float32)
        self.X, self.Y = np.meshgrid(np.arange(GW, dtype=np.float32), np.arange(GH, dtype=np.float32))
        kx = np.pi * np.arange(GW) / GW
        ky = np.pi * np.arange(GH) / GH
        den = (2 * np.cos(kx)[None, :] - 2) + (2 * np.cos(ky)[:, None] - 2)
        den[0, 0] = 1.0
        self.den = den
        # curl-noise modes: wavelengths 20-110 cells, unit speed each
        n = 14
        lam = np.exp(rng.uniform(np.log(20), np.log(110), n))
        ang = rng.uniform(0, 2 * np.pi, n)
        self.k = np.stack([np.cos(ang), np.sin(ang)], 1) * (2 * np.pi / lam)[:, None]
        self.ph = rng.uniform(0, 2 * np.pi, n)
        self.om = rng.uniform(0.05, 0.22, n) * rng.choice([-1, 1], n)    # radians per second of song
        self.amp = (lam / lam.max()) ** 0.5
        self.amp /= np.sqrt((self.amp ** 2).sum() / 2)

    def noise(self, phase):
        u = np.zeros((GH, GW), np.float32)
        v = np.zeros((GH, GW), np.float32)
        for (kx, ky), p, om, a in zip(self.k, self.ph, self.om, self.amp):
            c = np.cos(kx * self.X + ky * self.Y + p + om * phase).astype(np.float32)
            kn = math.hypot(kx, ky)
            u += a * (ky / kn) * c
            v -= a * (kx / kn) * c
        return u, v

    def adv(self, f, u, v):
        return cv2.remap(f, self.X - u, self.Y - v, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def project(self):
        u, v = self.u, self.v
        u[:, 0] = u[:, -1] = 0
        v[0, :] = v[-1, :] = 0
        div = np.zeros_like(u)
        div[:, 1:-1] += (u[:, 2:] - u[:, :-2]) * .5
        div[1:-1, :] += (v[2:, :] - v[:-2, :]) * .5
        ph = dctn(div, type=2, norm='ortho') / self.den
        ph[0, 0] = 0
        p = idctn(ph, type=2, norm='ortho').astype(np.float32)
        gx = np.zeros_like(p)
        gy = np.zeros_like(p)
        gx[:, 1:-1] = (p[:, 2:] - p[:, :-2]) * .5
        gy[1:-1, :] = (p[2:, :] - p[:-2, :]) * .5
        self.u = u - gx
        self.v = v - gy

    def confine(self, eps):
        u, v = self.u, self.v
        w = np.zeros_like(u)
        w[1:-1, 1:-1] = (v[1:-1, 2:] - v[1:-1, :-2]) * .5 - (u[2:, 1:-1] - u[:-2, 1:-1]) * .5
        aw = np.abs(w)
        nx = np.zeros_like(u)
        ny = np.zeros_like(u)
        nx[:, 1:-1] = (aw[:, 2:] - aw[:, :-2]) * .5
        ny[1:-1, :] = (aw[2:, :] - aw[:-2, :]) * .5
        nn = np.sqrt(nx * nx + ny * ny) + 1e-5
        self.u += eps * (ny / nn) * w
        self.v -= eps * (nx / nn) * w

    def step(self, target_u, target_v, relax, lift_g, confine, damp, burst_u=None, burst_v=None):
        self.u += relax * (target_u - self.u)
        self.v += relax * (target_v - self.v)
        self.v -= lift_g * self.lift
        if burst_u is not None:
            self.u += burst_u
            self.v += burst_v
        self.confine(confine)
        u0, v0 = self.u.copy(), self.v.copy()
        self.u = self.adv(u0, u0, v0)
        self.v = self.adv(v0, u0, v0)
        self.lift = self.adv(self.lift, u0, v0) * 0.996
        self.project()
        self.u *= damp
        self.v *= damp
        sp = np.sqrt(self.u ** 2 + self.v ** 2)
        lim = 1.6
        f = np.minimum(1.0, lim / (sp + 1e-6))
        self.u *= f
        self.v *= f


# --------------------------------------------------------------------------------------------- ink
class Ink:
    def __init__(self, scale=1):
        self.sc = scale
        self.w, self.h = W // scale, H // scale
        self.f = np.zeros((self.h, self.w, 4), np.float32)
        self.X, self.Y = np.meshgrid(np.arange(self.w, dtype=np.float32), np.arange(self.h, dtype=np.float32))

    def _adv(self, f, dx, dy):
        return cv2.remap(f, self.X - dx, self.Y - dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    def advect(self, u, v, still, decay, diffuse=0.0, edecay=None):
        """u, v: sim velocity (cells/frame); still: sim-res 0..1 (1 = held); decay: sim-res per-frame factor.
        diffuse: how much free ink spreads per frame (a 1-px blur mixed in where the ink is not held);
        edecay: extra per-frame factor on the emission only, so let-go ink dims before it disappears."""
        mv = (1.0 - still).astype(np.float32)
        k = S / self.sc
        dx = cv2.resize(u * mv * k, (self.w, self.h), interpolation=cv2.INTER_LINEAR)
        dy = cv2.resize(v * mv * k, (self.w, self.h), interpolation=cv2.INTER_LINEAR)
        f = self.f
        if np.abs(dx).max() + np.abs(dy).max() > 1e-3:
            f1 = self._adv(f, dx, dy)
            f2 = self._adv(f1, -dx, -dy)
            fc = f + 0.5 * (f - f2)
            fn = self._adv(fc, dx, dy)
            k = np.ones((3, 3), np.uint8)
            fn = np.minimum(np.maximum(fn, cv2.erode(f1, k)), cv2.dilate(f1, k))
            f = fn
        dk = cv2.resize(decay, (self.w, self.h), interpolation=cv2.INTER_LINEAR)
        f *= dk[..., None]
        if diffuse > 0 or edecay is not None:
            free = cv2.resize(1.0 - still, (self.w, self.h), interpolation=cv2.INTER_LINEAR)
            if diffuse > 0:
                # spreading at half resolution: let-go strokes soften into smoke instead of wobbling
                hf = cv2.resize(f, (self.w // 2, self.h // 2), interpolation=cv2.INTER_AREA)
                hb = cv2.resize(cv2.GaussianBlur(hf, (0, 0), 1.6), (self.w, self.h), interpolation=cv2.INTER_LINEAR)
                f += (hb - f) * (free * diffuse)[..., None]
            if edecay is not None:
                f[..., :3] *= (1.0 - (1.0 - edecay) * free)[..., None]
        self.f = f


# --------------------------------------------------------------------------------------------- helpers
_qX, _qY = np.meshgrid(np.arange(QW, dtype=np.float32) * 4 + 2, np.arange(QH, dtype=np.float32) * 4 + 2)


def glow_q(cx, cy, r):
    """Soft light falloff at quarter resolution; cx, cy, r in frame pixels."""
    d2 = ((_qX - cx) ** 2 + (_qY - cy) ** 2) / (r * r)
    return (1.0 / (1.0 + d2 * 1.6)) * np.exp(-d2 * 0.08)


def radial_blur(img, cx, cy, n=28, reach=0.55):
    """God rays: average of copies of img scaled toward (cx, cy). img at quarter resolution."""
    acc = img.copy()
    qx, qy = cx / 4, cy / 4
    for i in range(1, n):
        s = 1.0 - reach * i / n
        M = np.float32([[s, 0, qx * (1 - s)], [0, s, qy * (1 - s)]])
        acc += cv2.warpAffine(img, M, (QW, QH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT) * (1 - i / n)
    return acc / (n * 0.5)


class Caustics:
    """Slowly crawling light web from the surface, quarter resolution."""

    def __init__(self, seed=3):
        rng = np.random.default_rng(seed)
        self.k = []
        for _ in range(5):
            a = rng.uniform(0, np.pi)
            lam = rng.uniform(70, 140)
            self.k.append((np.cos(a) * 2 * np.pi / lam, np.sin(a) * 2 * np.pi / lam, rng.uniform(0, 6.3), rng.uniform(.3, .6)))

    def __call__(self, t):
        h = np.zeros((QH, QW), np.float32)
        for kx, ky, p, om in self.k:
            h += np.sin(kx * _qX + ky * _qY + p + om * t)
        h2 = np.zeros((QH, QW), np.float32)
        for kx, ky, p, om in self.k:
            h2 += np.sin(-ky * _qX * 1.3 + kx * _qY * 1.3 + p * 2 - om * t * .8)
        c = np.exp(-np.abs(h) * 2.2) + 0.6 * np.exp(-np.abs(h2) * 2.6)
        return c


class Ripples:
    """Rings on the water surface from raindrops. drops: list of (t0, x, y, amp)."""

    def __init__(self, drops):
        self.drops = sorted(drops)

    def field(self, t):
        h = np.zeros((QH, QW), np.float32)
        spark = np.zeros((QH, QW), np.float32)
        live = False
        for t0, x, y, a in self.drops:
            tau = t - t0
            if tau < 0 or tau > 4.0:
                continue
            live = True
            r = np.sqrt((_qX - x) ** 2 + (_qY - y) ** 2)
            front = 230.0 * tau + 6
            env = a * math.exp(-tau / 1.5) / (1 + 0.004 * front)
            for k, lag in enumerate((0, 34, 66)):
                fr = front - lag
                if fr <= 0:
                    continue
                h += env * (0.75 ** k) * np.exp(-((r - fr) / 16.0) ** 2) * np.cos((r - fr) / 4.2)
            if tau < 0.25:
                spark += (1 - tau / 0.25) * np.exp(-(r / 14.0) ** 2) * a
        return (h if live else None), spark


class Motes:
    def __init__(self, n=1600, seed=11):
        rng = np.random.default_rng(seed)
        self.p = np.stack([rng.uniform(0, W, n), rng.uniform(0, H, n)], 1).astype(np.float32)
        self.b = rng.uniform(.25, 1.0, n).astype(np.float32) ** 2
        self.tw = rng.uniform(0, 6.3, n).astype(np.float32)
        self.tws = rng.uniform(.6, 2.2, n).astype(np.float32)
        self.depth = rng.uniform(.4, 1.0, n).astype(np.float32)
        self.rng = rng

    def step(self, u, v, still, speed):
        ix = np.clip((self.p[:, 0] / S).astype(int), 0, GW - 1)
        iy = np.clip((self.p[:, 1] / S).astype(int), 0, GH - 1)
        m = (1 - 0.6 * still[iy, ix]) * self.depth * speed
        self.p[:, 0] += u[iy, ix] * S * m + self.rng.normal(0, .12, len(m)) * speed
        self.p[:, 1] += v[iy, ix] * S * m + self.rng.normal(0, .12, len(m)) * speed - 0.06 * speed
        self.p[:, 0] %= W
        self.p[:, 1] %= H

    def render(self, t, light_q, gain):
        """Splat into a half-resolution buffer; light_q is the quarter-res light (H/4, W/4, 3)."""
        hw, hh = W // 2, H // 2
        buf = np.zeros((hh, hw), np.float32)
        x = self.p[:, 0] / 2
        y = self.p[:, 1] / 2
        tw = 0.55 + 0.45 * np.sin(self.tw + t * self.tws)
        val = self.b * tw * gain
        xi = np.clip(x.astype(int), 0, hw - 2)
        yi = np.clip(y.astype(int), 0, hh - 2)
        fx = x - xi
        fy = y - yi
        np.add.at(buf, (yi, xi), val * (1 - fx) * (1 - fy))
        np.add.at(buf, (yi, xi + 1), val * fx * (1 - fy))
        np.add.at(buf, (yi + 1, xi), val * (1 - fx) * fy)
        np.add.at(buf, (yi + 1, xi + 1), val * fx * fy)
        buf = cv2.GaussianBlur(buf, (0, 0), 0.7)
        lq = cv2.resize(light_q, (hw, hh), interpolation=cv2.INTER_LINEAR)
        return buf[..., None] * (0.15 + lq)


def aces(x):
    return np.clip((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0, 1)


class Film:
    def __init__(self, seed=5):
        rng = np.random.default_rng(seed)
        g = rng.normal(0, 1, (8, H // 2, W // 2)).astype(np.float32)
        self.grain = [cv2.resize(cv2.GaussianBlur(x, (0, 0), 0.6), (W, H), interpolation=cv2.INTER_LINEAR) for x in g]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.48) / (H * 0.6)) ** 2)
        self.vig = np.clip(1.0 - 0.55 * np.clip(r - 0.35, 0, None) ** 1.6, 0.3, 1).astype(np.float32)[..., None]
        self.rng = rng

    def __call__(self, lin, fi, exposure, fade, warmth):
        x = lin * exposure
        q = cv2.resize(x, (QW, QH), interpolation=cv2.INTER_AREA)
        b1 = cv2.GaussianBlur(q, (0, 0), 3.0)
        b2 = cv2.GaussianBlur(cv2.resize(q, (QW // 2, QH // 2), interpolation=cv2.INTER_AREA), (0, 0), 9.0)
        bright = np.maximum(q - 0.55, 0)
        hal = cv2.GaussianBlur(bright, (0, 0), 5.0)
        hal = hal.mean(2, keepdims=True) * np.float32([1.0, 0.42, 0.22])
        add = 0.16 * b1 + 0.22 * cv2.resize(b2, (QW, QH), interpolation=cv2.INTER_LINEAR) + 0.35 * hal
        x = x + cv2.resize(add, (W, H), interpolation=cv2.INTER_LINEAR)
        x = aces(x * 1.15)
        # grade: lift shadows toward ink blue, roll highlights warm
        lum = x.mean(2, keepdims=True)
        x = x + (0.020 * (1 - lum) ** 3) * np.float32([0.35, 0.55, 1.0])
        x = x * (1 + warmth * lum * np.float32([0.06, 0.015, -0.05]))
        x = np.clip(x, 0, 1) ** (1 / 2.2)
        x = x * self.vig
        g = self.grain[fi % 8]
        g = np.roll(g, (int(self.rng.integers(0, H)), int(self.rng.integers(0, W))), (0, 1))
        lm = x.mean(2, keepdims=True)
        x = x + g[..., None] * (0.012 + 0.03 * lm * (1 - lm))
        x = np.clip(x * fade, 0, 1)
        return x
