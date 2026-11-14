"""The heroine, version 2: a witness who belongs to the scene she is in.

v1 pasted her on top of every scene (white sticker border, hard drop shadow, a beat-synced neck warp, pop-art
clones). v2 composites her the way a photograph of a real person would sit in that place:

  * no local warps at all. The only body motion is what a person standing still really does: breathing (a
    0.35 % rise of the upper body every ~4.4 s) and a slow weight shift (a 0.25 deg sway about her feet,
    which are below the frame, period ~7 s). Neither follows the beat - the world reacts to the music, she
    does not. Camera moves, light changes and focus pulls do the rest.
  * she is lit by the scene's own lights: an ambient colour, a directional key (side lamp, candles from below,
    a strobe), and a rim from whatever is behind her (LED wall, green lamp, window). Rims follow the
    direction of the light, so the edge facing the light glows.
  * light wrap: the blurred background bleeds into her outer edge, the standard trick that makes a cut-out
    sit in its plate. Edges are softened by ~1 px.
  * depth of field: she is blurred by the shot's focus, and so is whatever is in front of her.
  * the print worlds print her: on newsprint or on a rally poster she becomes halftone in the same ink, paper
    and screen angle, with a slight plate misregistration - never a sticker.
  * two in-camera optical effects: a reflection in window glass (mirrored, faint, screened over what is
    outside) and a double exposure into paper (her face as ink, multiplied into the letter).

  render(img, spec, t, fi, env) composites one appearance; spec is a dict (see DEFAULTS).
"""
import math

import cv2
import numpy as np

from common import H, W, clamp01, halftone_fast, lum

SRC = 'work/assets/girl.png'
FACE = (540.0, 160.0)    # face centre in source pixels
BODY = (570.0, 420.0)    # body centre
FEET = (565.0, 1460.0)   # where her feet would be (below the crop) - the pivot of a standing sway
_C = {}

DEFAULTS = dict(
    x=540, y=1300, s=1.6, anchor='body', flip=False,
    look='photo',                 # photo | paint | print | silhouette | reflect | ghost
    amb=(0.55, 0.55, 0.55),       # ambient light colour (multiplies her albedo)
    key=None,                     # dict(color, dir=(dx, dy), k=strength, soft=0.5)
    rim=None,                     # dict(color, dir=(dx, dy) toward the light, k, width)
    wrap=0.35,                    # light-wrap strength
    dof=0.0,                      # blur sigma in output px (number or callable of t)
    sat=0.85,                     # saturation after relight (scene grade does the rest)
    opacity=1.0,
    breath=1.0, sway=1.0,         # 0 to freeze
    clip=None,                    # (x0, y0, x1, y1) only show inside
    ink=(0.04, 0.04, 0.05), paper=(0.93, 0.90, 0.84), cell=9, angle=45, misreg=(3, 2),
    t0=None, fade=0.0,            # optional fade-in starting at t0
)


def _src():
    if 'rgb' not in _C:
        im = cv2.imread(SRC, cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0
        rgb = im[..., [2, 1, 0]]
        a = im[..., 3]
        # soften the hard cut edge a touch, and hold colour under the soft edge (straight alpha)
        a = cv2.GaussianBlur(a, (0, 0), 0.7)
        _C['rgb'], _C['a'] = rgb, a
        # 'paint' version for the illustrated diner: edge-preserving smoothing + soft tonal steps
        b = cv2.bilateralFilter((rgb * 255).astype(np.uint8), 9, 40, 7)
        b = cv2.bilateralFilter(b, 7, 30, 5).astype(np.float32) / 255
        L = lum(b)
        steps = 7
        q = np.floor(L * steps) / steps
        frac = L * steps - np.floor(L * steps)
        q = q + clamp01((frac - 0.75) * 4) / steps          # soft step edges
        k = (q + 0.04) / (L + 0.04)
        _C['paint'] = clamp01(b * (0.55 + 0.45 * k[..., None]))
    return _C['rgb'], _C['a']


def _pose_matrix(sp, t):
    """Affine source->canvas: scale, mirror, a slow standing sway about the feet, breathing about the hips."""
    ax, ay = FACE if sp['anchor'] == 'face' else BODY
    s = sp['s']
    sw = math.radians(0.25 * sp['sway'] * math.sin(2 * math.pi * t / 7.1 + 0.8))
    br = 0.0035 * sp['breath'] * (0.5 + 0.5 * math.sin(2 * math.pi * t / 4.4))
    # breathing: scale y about the waist line (source y 520) by (1 + br) above it, nothing below
    # (applied as a whole-image vertical scale about y=520 - small enough to read as the chest rising)
    by = 520.0
    B = np.array([[1, 0, 0], [0, 1 + br, -by * br], [0, 0, 1]], np.float64)
    # sway: rotate about the feet
    fx, fy = FEET
    c, si = math.cos(sw), math.sin(sw)
    R = np.array([[c, -si, fx - c * fx + si * fy], [si, c, fy - si * fx - c * fy], [0, 0, 1]], np.float64)
    sx = -s if sp['flip'] else s
    S = np.array([[sx, 0, 0], [0, s, 0], [0, 0, 1]], np.float64)
    M = S @ R @ B
    p = M @ np.array([ax, ay, 1.0])
    M[0, 2] += sp['x'] - p[0]
    M[1, 2] += sp['y'] - p[1]
    return M[:2].astype(np.float32)


def _warp(sp, t, which='rgb'):
    rgb, a = _src()
    src = _C['paint'] if which == 'paint' else rgb
    M = _pose_matrix(sp, t)
    flags = cv2.INTER_CUBIC if sp['s'] > 1.3 else cv2.INTER_AREA
    A = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
    C = cv2.warpAffine(src, M, (W, H), flags=flags, borderMode=cv2.BORDER_REPLICATE)
    return np.clip(C, 0, 1), clamp01(A)


def _bbox(a, pad):
    ys = np.where(a.max(1) > 0.01)[0]
    xs = np.where(a.max(0) > 0.01)[0]
    if len(ys) == 0:
        return None
    return max(0, xs[0] - pad), max(0, ys[0] - pad), min(W, xs[-1] + 1 + pad), min(H, ys[-1] + 1 + pad)


def _edge_terms(A, width):
    """Inner edge band and the outward normal of the silhouette (unit vectors)."""
    Ab = cv2.GaussianBlur(A, (0, 0), max(1.0, width))
    band = clamp01((A - Ab) * 2.6) * A
    gx = cv2.Sobel(Ab, cv2.CV_32F, 1, 0, ksize=5)
    gy = cv2.Sobel(Ab, cv2.CV_32F, 0, 1, ksize=5)
    n = np.sqrt(gx * gx + gy * gy) + 1e-6
    return band, -gx / n, -gy / n


def render(img, spec, t, fi, env, now=None):
    sp = dict(DEFAULTS)
    sp.update(spec)
    now = t if now is None else now
    op = sp['opacity']
    if sp['t0'] is not None and sp['fade'] > 0:
        op *= clamp01((now - sp['t0']) / sp['fade'])
    if op <= 0.003:
        return img
    look = sp['look']
    C, A = _warp(sp, t, 'paint' if look == 'paint' else 'rgb')
    if sp['clip'] is not None:
        x0, y0, x1, y1 = sp['clip']
        m = np.zeros_like(A)
        m[int(y0):int(y1), int(x0):int(x1)] = 1
        A = A * m
    dof = sp['dof'](now) if callable(sp['dof']) else sp['dof']
    bb = _bbox(A, int(12 + 3 * dof))
    if bb is None:
        return img
    x0, y0, x1, y1 = bb
    C, A = C[y0:y1, x0:x1], A[y0:y1, x0:x1]
    bg = img[y0:y1, x0:x1]
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)

    if look in ('photo', 'paint', 'silhouette'):
        L0 = lum(C)
        if look == 'silhouette':
            out = np.zeros_like(C) + np.asarray(sp['amb'], np.float32) * 0.15
        else:
            g = L0[..., None]
            sat = sp['sat']
            base = g + (C - g) * sat
            light = np.zeros_like(C) + np.asarray(sp['amb'], np.float32)
            key = sp['key']
            if key:
                dx, dy = key.get('dir', (1, 0))
                nrm = math.hypot(dx, dy) or 1
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                half = max(x1 - x0, y1 - y0) / 2
                u = ((xx - cx) * dx + (yy - cy) * dy) / nrm / half
                shape = clamp01(0.5 + 0.5 * u / max(0.15, key.get('soft', 0.5)))
                shape = shape ** key.get('gamma', 1.4)
                k = key['k'](now) if callable(key['k']) else key['k']
                light = light + shape[..., None] * np.asarray(key['color'], np.float32) * k
            out = base * light
        rim = sp['rim']
        if rim:
            band, nx, ny = _edge_terms(A, rim.get('width', 5) * max(1.0, sp['s'] / 1.6))
            dx, dy = rim.get('dir', (0, -1))
            nrm = math.hypot(dx, dy) or 1
            facing = clamp01((nx * dx + ny * dy) / nrm)
            w = rim.get('omni', 0.3) + (1 - rim.get('omni', 0.3)) * facing
            k = rim['k'](now) if callable(rim['k']) else rim['k']
            out = out + (band * w * k)[..., None] * np.asarray(rim['color'], np.float32)
        if sp['wrap'] > 0:   # light wrap from the plate behind her
            bgb = cv2.GaussianBlur(cv2.resize(bg, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA), (0, 0), 3)
            bgb = cv2.resize(bgb, (bg.shape[1], bg.shape[0]), interpolation=cv2.INTER_LINEAR)
            band2, _, _ = _edge_terms(A, 4 * max(1.0, sp['s'] / 1.6))
            out = out + bgb * (band2 * sp['wrap'])[..., None]
        rgb = out
    elif look == 'print':
        L0 = lum(C)
        L2 = clamp01((L0 - 0.10) * 1.25)
        cov = halftone_fast(L2, cell=sp['cell'], angle=sp['angle'])
        ink = np.asarray(sp['ink'], np.float32)
        paper = np.asarray(sp['paper'], np.float32)
        mx, my = sp['misreg']
        cov2 = np.roll(np.roll(cov, my, 0), mx, 1)
        rgb = paper * (1 - cov[..., None]) + ink * cov[..., None]
        # a second, slightly offset plate: real presses are never in perfect register
        rgb = rgb * (1 - 0.18 * cov2[..., None]) + 0.18 * cov2[..., None] * ink
    elif look == 'reflect':
        g = lum(C)
        tint = np.asarray(sp.get('tint', (0.75, 0.85, 1.0)), np.float32)
        rgb = (g ** 1.2)[..., None] * tint
    elif look == 'ghost':
        g = lum(C)
        ink = np.asarray(sp['ink'], np.float32)
        dark = clamp01((0.85 - g) * 1.4)
        rgb = None
    else:
        raise ValueError(look)

    if dof > 0.3:
        if look == 'ghost':
            dark = cv2.GaussianBlur(dark, (0, 0), dof)
        else:
            rgb = cv2.GaussianBlur(rgb, (0, 0), dof)
        A = cv2.GaussianBlur(A, (0, 0), dof)

    if sp.get('vignette'):   # feathered oval mask (double exposure / reflection never shows a hard cut)
        cx, cy = sp['vignette'][0] - x0, sp['vignette'][1] - y0
        rx, ry = sp['vignette'][2], sp['vignette'][3]
        hh, ww = A.shape
        vy, vx = np.mgrid[0:hh, 0:ww].astype(np.float32)
        d = np.sqrt(((vx - cx) / rx) ** 2 + ((vy - cy) / ry) ** 2)
        A = A * clamp01((1.0 - d) / 0.45)

    a3 = (A * op)[..., None]
    if look == 'reflect':
        sub = img[y0:y1, x0:x1]
        sub[:] = 1 - (1 - sub) * (1 - rgb * a3)          # screen: glass adds light, never darkens
    elif look == 'ghost':
        sub = img[y0:y1, x0:x1]
        d3 = (dark * A * op)[..., None]
        sub[:] = sub * (1 - d3) + sub * ink * d3 * 1.0    # multiply in ink
    else:
        sub = img[y0:y1, x0:x1]
        sub[:] = sub * (1 - a3) + np.clip(rgb, 0, 1.4) * a3
    return img


def alpha(spec, t):
    """Her coverage on the canvas (for occlusion tests / debugging)."""
    sp = dict(DEFAULTS)
    sp.update(spec)
    return _warp(sp, t)[1]
