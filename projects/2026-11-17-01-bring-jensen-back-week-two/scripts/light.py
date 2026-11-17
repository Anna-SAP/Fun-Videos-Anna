"""The film's one rule, as an image operation: the door is closed, the light behind it is on, and every
sung character is a hole the light gets through.

compose(base, holes, inner, inten, color, ...) takes
  base   HxWx3  the front of the door (dark, lit only by a weak fill from our side)
  holes  HxW    0..1 openings (the characters, the gap under the door, cracks)
  inner  HxW    0..1 the part of each opening where we see the cut wall of the door instead of the light
                (holes minus the hole shifted along the line of sight: it gives the letters a thickness)
  inten  HxW    light intensity behind each opening (1 = normal; a knock flashes it to ~2.5)
and returns the lit frame: white-hot cores, the light's colour at the rim, a bloom in the haze in front of
the door and volumetric rays streaming towards the camera (a zoom blur of the openings, done at 1/4 size).
"""
import cv2
import numpy as np

from common import H, W

Q = 4  # bloom / rays are computed at 1/Q resolution


def _small(a):
    return cv2.resize(a, (W // Q, H // Q), interpolation=cv2.INTER_AREA)


def _big(a):
    return cv2.resize(a, (W, H), interpolation=cv2.INTER_LINEAR)


def zoom_blur(s, cx, cy, length=0.35, n=12):
    """Radial (zoom) blur of a small single-channel image about (cx, cy) in small-image pixels."""
    acc = np.zeros_like(s)
    tot = 0.0
    h, w = s.shape
    for i in range(n):
        k = 1.0 + length * i / (n - 1)
        M = np.float32([[k, 0, cx * (1 - k)], [0, k, cy * (1 - k)]])
        wgt = (1 - i / n) ** 1.6
        acc += cv2.warpAffine(s, M, (w, h), flags=cv2.INTER_LINEAR) * wgt
        tot += wgt
    return acc / tot


def compose(base, holes, inner, inten, color, glow=1.0, rays=0.55, ray_len=0.35, center=(W / 2, H * 0.42),
            core=0.9, wallc=None, haze=0.0, bounce=2.2):
    """See the module doc. bounce: how much the escaping light lights up the door face around the openings."""
    color = np.asarray(color, np.float32)
    L = holes * inten
    open_ = np.clip(holes - inner * 0.85, 0, 1)
    vis = open_ * inten
    # the brighter the light, the closer to white (white-hot core, coloured rim)
    h = np.clip((inten - 0.55) * core, 0, 1)[..., None]
    lightc = vis[..., None] * (color[None, None, :] * (1 - h) + 0.97 * h)
    if wallc is None:
        wallc = color * 0.3 + 0.04
    wall = (inner * holes)[..., None] * (np.asarray(wallc, np.float32)[None, None, :] * np.clip(inten, 0, 1.6)[..., None])
    s = _small(L)
    lit = None
    add = np.zeros_like(s)
    if glow > 0:
        g1 = cv2.GaussianBlur(s, (0, 0), 3.0)
        g2 = cv2.GaussianBlur(s, (0, 0), 14.0)
        add += glow * (0.5 * g1 + 0.55 * g2)
    if bounce > 0:
        lit = cv2.GaussianBlur(s, (0, 0), 30.0) * bounce
    if rays > 0:
        add += rays * zoom_blur(s, center[0] / Q, center[1] / Q, ray_len)
    if haze > 0:
        add += haze * cv2.GaussianBlur(s, (0, 0), 40.0)
    face = base * (1 - holes[..., None])
    if lit is not None:
        face = face * (1 + _big(lit)[..., None] * (0.4 + 0.6 * color[None, None, :]))
    out = face + lightc + wall + _big(add)[..., None] * color[None, None, :]
    return out


def bevel_shift(cx, cy, depth, center=(W / 2, H * 0.42)):
    """Offset of a hole's far edge for a glyph centred at (cx, cy): the line of sight goes outwards from
    the optical centre, so the cut wall shows on the side facing the centre."""
    dx, dy = cx - center[0], cy - center[1]
    r = max(1.0, (dx * dx + dy * dy) ** 0.5)
    k = depth * min(1.0, r / (0.5 * H))
    return dx / r * k, dy / r * k


def grade(img, lift=0.0, gamma=1.0, sat=1.0, tint=(1, 1, 1)):
    out = img * np.asarray(tint, np.float32)[None, None, :]
    if sat != 1.0:
        g = out.mean(2, keepdims=True)
        out = g + (out - g) * sat
    out = np.clip(out, 0, None)
    if gamma != 1.0:
        out = out ** (1.0 / gamma)
    return out + lift


def tonemap(img):
    """Soft shoulder on luminance (keeps hue: per-channel compression turned green-white cores pink)."""
    lum = img.max(axis=2, keepdims=True)
    k = np.where(lum > 0.8, (0.8 + (1 - np.exp(-(lum - 0.8) * 2.2)) * 0.2) / np.maximum(lum, 1e-6), 1.0)
    return img * k
