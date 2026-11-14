"""The MC: the user's cut-out photo, placed, nodding on the beat and printed in one of several treatments.

Source: work/assets/girl.png (1083x755 RGBA, already cut out). Landmarks in source pixels, read off a 3x crop:
face centre (540, 160), eyes y=128, chin y=200, neck pivot (545, 232), body centre (570, 420).
The source is cropped at mid-thigh, so she is always placed with her lower edge at or below the frame bottom.

The nod is a small warp of everything above the shoulders (rotation about the neck plus a dip), driven by the
measured kicks/snares through `nod` (0..1). Treatments (`style`):
  color   graded photo with a white sticker border and a hard offset shadow
  duo     duotone halftone (ink dots on a colour) - newsprint / poster print
  mono    photocopy: hard threshold with toner noise
  line    neon outline only
  sil     solid silhouette
"""
import math

import cv2
import numpy as np

from common import H, W, clamp01, halftone_fast, lum

SRC = 'work/assets/girl.png'
FACE = (540.0, 160.0)
NECK = (545.0, 232.0)
BODY = (570.0, 420.0)
_cache = {}


def _src():
    if 'rgba' not in _cache:
        im = cv2.imread(SRC, cv2.IMREAD_UNCHANGED).astype(np.float32) / 255.0
        rgb = im[..., [2, 1, 0]]
        a = im[..., 3]
        # gentle grade: a touch more contrast and warmth, lifted blacks kept
        rgb = clamp01((rgb - 0.5) * 1.08 + 0.5)
        _cache['rgba'] = np.dstack([rgb * a[..., None], a]).astype(np.float32)   # premultiplied
        h, w = a.shape
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        _cache['grid'] = (xx, yy)
        # head weight: 1 above the neck, fading to 0 across the shoulders; hair below shoulders follows less
        wy = clamp01((NECK[1] + 40 - yy) / 80.0)
        _cache['wh'] = (wy * wy * (3 - 2 * wy)).astype(np.float32)
    return _cache['rgba']


def _nodded(nod, tilt=0.0):
    """Source image with the head dipped by `nod` (0..1) and tilted by `tilt` degrees."""
    src = _src()
    if abs(nod) < 1e-3 and abs(tilt) < 1e-3:
        return src
    xx, yy = _cache['grid']
    wh = _cache['wh']
    ang = math.radians(4.0 * nod + tilt) * wh
    dy = 5.0 * nod * wh
    # inverse map: rotate back about the neck pivot and undo the dip
    cx, cy = NECK
    x0, y0 = xx - cx, yy - cy - dy
    c, s = np.cos(-ang), np.sin(-ang)
    mx = (c * x0 - s * y0 + cx).astype(np.float32)
    my = (s * x0 + c * y0 + cy).astype(np.float32)
    return cv2.remap(src, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def place(cx, cy, scale, rot=0.0, anchor=BODY, nod=0.0, tilt=0.0, flip=False, squash=0.0, size=(W, H)):
    """Premultiplied RGB + alpha of the girl on a canvas. (cx, cy) is where `anchor` lands; scale is
    output px per source px; squash compresses vertically about her lower edge (beat bounce)."""
    src = _nodded(nod, tilt)
    ax, ay = anchor
    sx = -scale if flip else scale
    sy = scale * (1 - squash)
    r = math.radians(rot)
    c, s = math.cos(r), math.sin(r)
    # forward affine: out = R * diag(sx, sy) * (p - anchor) + (cx, cy)
    M = np.array([[c * sx, -s * sy, 0], [s * sx, c * sy, 0]], np.float32)
    M[:, 2] = np.array([cx, cy], np.float32) - M[:, :2] @ np.array([ax, ay], np.float32)
    out = cv2.warpAffine(src, M, size, flags=cv2.INTER_CUBIC if scale > 1.2 else cv2.INTER_AREA,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    a = clamp01(out[..., 3])
    rgb = np.clip(out[..., :3], 0, None)
    rgb = np.minimum(rgb, a[..., None])
    return rgb, a


def bbox(a):
    ys = np.where(a.max(1) > 0.02)[0]
    xs = np.where(a.max(0) > 0.02)[0]
    if len(ys) == 0:
        return None
    return xs[0], ys[0], xs[-1] + 1, ys[-1] + 1


def _disk(r):
    r = max(1, int(round(r)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def stylize(rgb, a, style='color', ink=(0.04, 0.04, 0.05), paper=(0.55, 1.0, 0.18), cell=9, border=0,
            border_color=(1, 1, 1), shadow=None, shadow_color=(0, 0, 0), angle=45, frame_idx=0, gain=1.0):
    """Turn the placed photo into a print treatment. Returns premultiplied rgb and alpha (full canvas)."""
    ink = np.asarray(ink, np.float32)
    paper = np.asarray(paper, np.float32)
    bb = bbox(a)
    if bb is None:
        return rgb, a
    x0, y0, x1, y1 = bb
    pad = int(border + (abs(shadow[0]) + abs(shadow[1]) if shadow else 0) + 4)
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(a.shape[1], x1 + pad), min(a.shape[0], y1 + pad)
    A = a[y0:y1, x0:x1]
    C = rgb[y0:y1, x0:x1]
    un = C / np.maximum(A[..., None], 1e-4)
    if style == 'color':
        F = C.copy()
        FA = A.copy()
    else:
        L = lum(un)
        if style == 'duo':
            L2 = clamp01((L - 0.12) * 1.35 * gain)
            cov = halftone_fast(L2, cell=cell, angle=angle)
            col = paper[None, None] * (1 - cov[..., None]) + ink[None, None] * cov[..., None]
        elif style == 'mono':
            rng = np.random.default_rng(frame_idx // 2)
            n = cv2.GaussianBlur(rng.random(L.shape).astype(np.float32), (0, 0), 1.2)
            th = clamp01((L - 0.42 + (n - 0.5) * 0.25) * 9 + 0.5)
            col = ink[None, None] * (1 - th[..., None]) + paper[None, None] * th[..., None]
        elif style == 'line':
            g = cv2.GaussianBlur(L, (0, 0), 1.2)
            gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
            e = clamp01(np.sqrt(gx * gx + gy * gy) * 3.0)
            ae = cv2.morphologyEx(A, cv2.MORPH_GRADIENT, _disk(2))
            e = np.maximum(e * A, clamp01(ae * 1.5))
            glow = cv2.GaussianBlur(e, (0, 0), 6)
            FA = clamp01(e + glow * 0.8)
            col = paper[None, None] * np.ones_like(un)
            F = col * FA[..., None]
            out_rgb = np.zeros_like(rgb)
            out_a = np.zeros_like(a)
            out_rgb[y0:y1, x0:x1] = F
            out_a[y0:y1, x0:x1] = FA
            return out_rgb, out_a
        elif style == 'sil':
            col = ink[None, None] * np.ones_like(un)
        else:
            raise ValueError(style)
        F = col * A[..., None]
        FA = A.copy()
    # sticker border and hard shadow, built from the alpha
    if border > 0:
        As = cv2.GaussianBlur(A, (0, 0), max(1.0, border * 0.35))  # smooth away flyaway hairs first
        Ab = cv2.dilate((As > 0.45).astype(np.float32), _disk(border))
        Ab = cv2.GaussianBlur(Ab, (0, 0), 0.8)
        bc = np.asarray(border_color, np.float32)
        F = F + bc[None, None] * (Ab - FA)[..., None].clip(0, 1)
        FA = np.maximum(FA, Ab)
    if shadow:
        dx, dy = int(shadow[0]), int(shadow[1])
        S = np.zeros_like(FA)
        hh, ww = FA.shape
        S[max(0, dy):hh + min(0, dy), max(0, dx):ww + min(0, dx)] = FA[max(0, -dy):hh - max(0, dy), max(0, -dx):ww - max(0, dx)]
        sc = np.asarray(shadow_color, np.float32)
        Sa = S * (1 - FA)
        F = F + sc[None, None] * Sa[..., None]
        FA = FA + Sa
    out_rgb = np.zeros_like(rgb)
    out_a = np.zeros_like(a)
    out_rgb[y0:y1, x0:x1] = F
    out_a[y0:y1, x0:x1] = FA
    return out_rgb, out_a
