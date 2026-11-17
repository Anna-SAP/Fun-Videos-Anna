"""Screen-space finishing: door warp, gap light, compose, crowd silhouettes, dust, grain, vignette, glitch."""
import math

import cv2
import numpy as np

import doors
import light
from common import H, W, hash01, noise2

_vig = None
_grain = None


def vignette(k=0.55):
    global _vig
    if _vig is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = ((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.46) / (H * 0.6)) ** 2
        _vig = np.clip(1 - d, 0, 1).astype(np.float32)
    return 1 - k + k * _vig


def grain(img, t, amt=0.03):
    global _grain
    if _grain is None:
        rng = np.random.default_rng(5)
        _grain = [(rng.standard_normal((H // 2, W // 2)).astype(np.float32)) for _ in range(6)]
    g = _grain[int(t * 30) % 6]
    g = cv2.resize(g, (W, H), interpolation=cv2.INTER_NEAREST)
    return img + g[..., None] * amt


def door_view(style, cam, fill=0.8, gap_level=1.0):
    """Warp a door world through the camera. Returns (base float HxWx3, gap HxW, spill HxW)."""
    from typo import cam_xform
    w = doors.world(style)
    M = cam_xform(cam)
    base = cv2.warpAffine(w['base'], M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    base = base.astype(np.float32) * (fill / 255.0)
    gap = cv2.warpAffine(w['gap'], M, (W, H), flags=cv2.INTER_LINEAR).astype(np.float32) * (gap_level / 255.0)
    spill = cv2.warpAffine(w['spill'], M, (W, H), flags=cv2.INTER_LINEAR).astype(np.float32) / 255.0
    return base, gap, spill


def chroma(img, px):
    """Lateral chromatic split by px pixels (red right, blue left)."""
    if px < 0.5:
        return img
    p = int(round(px))
    out = img.copy()
    out[:, p:, 0] = img[:, :-p, 0]
    out[:, :-p, 2] = img[:, p:, 2]
    return out


def crowd(img, t, level, backlight, color, kick=0.0, seed=3, n=26, y0=None, raise_=0.0, scale=1.0):
    """Silhouettes of a crowd in the foreground, rim-lit by the door light. raise_ 0..1 lifts fists."""
    if level <= 0.01:
        return img
    y0 = H if y0 is None else y0
    mask = np.zeros((H // 2, W // 2), np.float32)
    rim = np.zeros((H // 2, W // 2), np.float32)
    for i in range(n):
        u = hash01(seed, i)
        x = (i + 0.5) / n * (W / 2) * 1.15 - W * 0.04 + (hash01(seed, i, 2) - 0.5) * 30
        depth = 0.7 + 0.6 * hash01(seed, i, 3)
        r = 34 * depth * scale
        bob = (kick * 10 + 3 * math.sin(t * 2.1 + i)) * depth
        hy = y0 / 2 - (95 + 70 * u) * depth * scale + bob
        cv2.ellipse(mask, (int(x), int(hy)), (int(r * 0.8), int(r)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
        cv2.ellipse(mask, (int(x), int(hy + r * 2.6)), (int(r * 2.1), int(r * 1.9)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
        cv2.rectangle(mask, (int(x - r * 2.1), int(hy + r * 2.6)), (int(x + r * 2.1), H // 2), 1.0, -1)
        # raised fists, pumping on the kick
        if hash01(seed, i, 4) < 0.6 and raise_ > 0:
            up = raise_ * (0.55 + 0.45 * hash01(seed, i, 5))
            ph = hash01(seed, i, 8)
            up *= 0.75 + 0.25 * (kick if ph > 0.3 else 1 - kick)
            side = 1 if hash01(seed, i, 6) > 0.5 else -1
            sx, sy = x + side * r * 1.4, hy + r * 1.9
            ex = sx + side * r * (0.3 + 0.5 * hash01(seed, i, 9))
            ey = sy - r * 8.5 * up
            elx, ely = sx + side * r * 1.1, sy - r * 4.0 * up
            cv2.line(mask, (int(sx), int(sy)), (int(elx), int(ely)), 1.0, max(3, int(r * 0.55)), cv2.LINE_AA)
            cv2.line(mask, (int(elx), int(ely)), (int(ex), int(ey)), 1.0, max(3, int(r * 0.45)), cv2.LINE_AA)
            cv2.ellipse(mask, (int(ex), int(ey - r * 0.25)), (int(r * 0.42), int(r * 0.5)), side * 12, 0, 360, 1.0, -1,
                        cv2.LINE_AA)
    # rim light: top edges of the shapes
    er = cv2.erode(mask, np.ones((3, 3), np.uint8))
    sh = np.zeros_like(mask)
    sh[3:] = mask[:-3]
    rim = np.clip(mask - sh, 0, 1)
    rim = cv2.GaussianBlur(rim, (0, 0), 1.2)
    mask = cv2.GaussianBlur(mask, (0, 0), 0.8)
    mask = cv2.resize(mask, (W, H)) * level
    rim = cv2.resize(rim, (W, H)) * level * backlight * 1.6
    # haze lit by the light under the door, behind the crowd, so the silhouettes read
    prof = np.clip(1 - np.abs(np.arange(H, dtype=np.float32) - (y0 - 260 * scale)) / (420 * scale), 0, 1) ** 1.5
    img = img + (prof[:, None, None] * 0.22 * level * (0.6 + 0.4 * backlight)) * np.asarray(color, np.float32)[None, None, :]
    img = img * (1 - mask[..., None] * 0.96)
    img = img + rim[..., None] * np.asarray(color, np.float32)[None, None, :] * 0.9
    _ = er
    return img


_dust = None


def dust(img, t, rays_mask, color, amt=0.6, speed=1.0):
    """Motes drifting in the beams: bright only where the rays are."""
    global _dust
    if amt <= 0:
        return img
    if _dust is None:
        rng = np.random.default_rng(9)
        _dust = rng.random((420, 4)).astype(np.float32)
    layer = np.zeros((H // 2, W // 2), np.float32)
    for i, (u, v, s, p) in enumerate(_dust):
        x = (u * W / 2 + 18 * math.sin(t * 0.3 * speed + p * 6)) % (W / 2)
        y = (v * H / 2 - t * (6 + 14 * s) * speed) % (H / 2)
        cv2.circle(layer, (int(x), int(y)), 1 if s < 0.8 else 2, 0.5 + 0.5 * s, -1)
    layer = cv2.resize(layer, (W, H))
    lit = np.clip(rays_mask, 0, 1)
    return img + (layer * lit * amt)[..., None] * np.asarray(color, np.float32)[None, None, :]


def scanlines(img, k=0.12, t=0.0):
    rows = (np.arange(H) % 4 < 2).astype(np.float32)
    return img * (1 - k * rows)[:, None, None]


def glitch(img, t, amt):
    """Horizontal slice displacement + chroma: for the broadcast intro and the scratches."""
    if amt <= 0.01:
        return img
    out = img.copy()
    nb = int(6 + 18 * amt)
    for i in range(nb):
        y0 = int(hash01(int(t * 30), i, 1) * H)
        hh = int(8 + hash01(int(t * 30), i, 2) * 90 * amt)
        dx = int((hash01(int(t * 30), i, 3) - 0.5) * 220 * amt)
        y1 = min(H, y0 + hh)
        out[y0:y1] = np.roll(img[y0:y1], dx, axis=1)
    return chroma(out, 10 * amt)


def finish(img, t, vig=0.55, gr=0.028):
    img = img * vignette(vig)[..., None]
    img = grain(img, t, gr)
    img = light.tonemap(img)
    return img
