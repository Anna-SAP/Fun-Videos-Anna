"""The world of this film: one closed door with the light still on behind it.

Everything is computed; there are no photographs or generated images.

Close shot (compose_close): the frame is the door. A lyric character is a cut through the door, so the only
way to see the light inside is through the words. Three float maps describe a frame:

  G  geometry  where the door is cut through (0..1). Cuts stay after their light goes out, as scars.
  E  emission  how much room light comes through each cut right now.
  K  ink       RGB tint of that light.

Far shot (compose_far): the same door seen from down the hall; the words are the light it spills on the floor.

Nothing here knows the song; mv.py drives it.
"""
import functools
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONTS = 'work/fonts/'
F_SANS = FONTS + 'NotoSansSC-Black.ttf'
F_SANSB = FONTS + 'NotoSansSC-Bold.ttf'
F_SANSM = FONTS + 'NotoSansSC-Medium.ttf'
F_SERIF = FONTS + 'NotoSerifSC-Black.ttf'
F_SERIFS = FONTS + 'NotoSerifSC-SemiBold.ttf'
F_HY = FONTS + 'ZCOOLQingKeHuangYou.ttf'
F_ANTON = FONTS + 'Anton-Regular.ttf'
F_PLAY = FONTS + 'PlayfairDisplay-BlackItalic.ttf'
F_MONO = FONTS + 'JetBrainsMono-Bold.ttf'

AMBER = np.array([1.00, 0.47, 0.10], np.float32)
GOLD = np.array([1.00, 0.66, 0.24], np.float32)
COLD = np.array([0.36, 0.66, 1.00], np.float32)
WHITE = np.array([1.00, 0.90, 0.76], np.float32)
RED = np.array([1.00, 0.022, 0.010], np.float32)
TEAL = np.array([0.12, 0.90, 0.62], np.float32)

# door leaf in the close shot
DX0, DX1, DY0, DY1 = 66, 1014, 112, 1742
# door leaf in the far shot (same proportions, 0.3x)
FS = 0.30
FDX0, FDX1 = 540 - (DX1 - DX0) * FS / 2, 540 + (DX1 - DX0) * FS / 2
FDY1 = 742.0
FDY0 = FDY1 - (DY1 - DY0) * FS


@functools.lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, int(size))


def rng_noise(shape, seed, blur=0.0):
    r = np.random.default_rng(seed).random(shape, dtype=np.float32)
    if blur:
        r = cv2.GaussianBlur(r, (0, 0), blur)
        r = (r - r.min()) / (r.max() - r.min() + 1e-9)
    return r


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------------------------------------------------
# static surfaces
# ---------------------------------------------------------------------------------------------------------
def _rrect(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)


@functools.lru_cache(maxsize=None)
def close_assets():
    """albedo (H,W,3), frame-gap light map, sill light map, hardware mask + hardware albedo."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # wall: dark plaster
    wall = 0.030 + 0.020 * rng_noise((H, W), 1, 14) + 0.010 * rng_noise((H, W), 2, 1.2)
    alb = np.dstack([wall * 0.92, wall * 0.98, wall * 1.10])
    # door leaf: dark lacquer with a vertical grain
    grain = rng_noise((H // 2, W), 3, 0)
    grain = cv2.GaussianBlur(grain, (0, 0), sigmaX=1.6, sigmaY=60)
    grain = cv2.resize(grain, (W, H), interpolation=cv2.INTER_LINEAR)
    grain = (grain - grain.mean()) / (grain.std() + 1e-9)
    blot = rng_noise((H, W), 4, 60)
    leaf = 0.085 + 0.007 * grain + 0.030 * (blot - 0.5)
    leaf = np.dstack([leaf * 0.86, leaf * 0.97, leaf * 1.08])
    m = ((xx >= DX0) & (xx < DX1) & (yy >= DY0) & (yy < DY1)).astype(np.float32)
    m = cv2.GaussianBlur(m, (0, 0), 0.8)
    alb = alb * (1 - m[..., None]) + leaf * m[..., None]
    # architrave: a lighter band around the leaf
    arch = ((xx >= DX0 - 30) & (xx < DX1 + 30) & (yy >= DY0 - 30) & (yy < DY1 + 2)).astype(np.float32) - \
           ((xx >= DX0 - 5) & (xx < DX1 + 5) & (yy >= DY0 - 5) & (yy < DY1 + 2)).astype(np.float32)
    alb = alb + 0.030 * np.clip(arch, 0, 1)[..., None]
    # floor: polished, a little lighter, below the sill
    fl = (yy >= DY1 + 6).astype(np.float32)
    floor = 0.050 + 0.02 * rng_noise((H, W), 5, 30)
    alb = alb * (1 - fl[..., None]) + np.dstack([floor * 0.9, floor * 0.95, floor * 1.05]) * fl[..., None]

    # light leaking round the leaf: hairline gaps left/right/top, a wider one at the sill
    def line(mask, core, wide):
        a = cv2.GaussianBlur(mask, (0, 0), core)
        b = cv2.GaussianBlur(mask, (0, 0), wide)
        return a / (a.max() + 1e-9) + 0.55 * b / (b.max() + 1e-9)

    g = np.zeros((H, W), np.float32)
    g[DY0:DY1, DX0 - 3:DX0] = 1
    g[DY0:DY1, DX1:DX1 + 3] = 1
    g[DY0 - 3:DY0, DX0 - 3:DX1 + 3] = 1
    gap = line(g, 1.6, 22)
    s = np.zeros((H, W), np.float32)
    s[DY1:DY1 + 6, DX0 - 2:DX1 + 2] = 1
    sill = line(s, 2.2, 34)
    # the sill light fans out over the floor
    fan = np.clip((yy - DY1) / (H - DY1), 0, 1)
    spread = np.clip(1 - np.abs(xx - W / 2) / (W * 0.50 + 600 * fan), 0, 1)
    sill = sill + 0.9 * (yy > DY1 + 4) * np.exp(-fan * 2.2) * smooth(spread) ** 1.5

    # hardware: lever handle, escutcheon, keyhole, three hinges, a small plate -- always in front of the light
    hw = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(hw)
    hx, hy = DX1 - 50, 1010
    _rrect(d, (hx - 22, hy - 120, hx + 22, hy + 150), 11, 255)           # back plate
    _rrect(d, (hx - 60, hy - 76, hx + 16, hy - 48), 14, 255)            # lever
    d.ellipse((hx - 26, hy - 88, hx + 26, hy - 36), fill=255)            # rose
    for y in (DY0 + 150, (DY0 + DY1) // 2, DY1 - 150):
        _rrect(d, (DX0 + 2, y - 46, DX0 + 16, y + 46), 4, 255)
    hwm = np.asarray(hw, np.float32) / 255
    key = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(key)
    d.ellipse((hx - 9, hy + 62, hx + 9, hy + 80), fill=255)
    d.polygon([(hx - 5, hy + 74), (hx + 5, hy + 74), (hx + 8, hy + 104), (hx - 8, hy + 104)], fill=255)
    keym = np.asarray(key, np.float32) / 255
    # brushed metal: lit from above-left
    sh = cv2.GaussianBlur(hwm, (0, 0), 3)
    bev = np.clip(sh - np.roll(np.roll(sh, 3, 0), 3, 1), 0, 1) * 3.0
    hwalb = (0.10 + 0.25 * bev)[..., None] * np.array([1.0, 0.96, 0.9], np.float32)
    return alb.astype(np.float32), gap.astype(np.float32), sill.astype(np.float32), hwm, hwalb.astype(np.float32), keym


@functools.lru_cache(maxsize=None)
def vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (W * 0.62), (yy - H / 2) / (H * 0.62))
    return (1 - 0.55 * smooth((r - 0.55) / 0.75))[..., None].astype(np.float32)


# ---------------------------------------------------------------------------------------------------------
# glyphs
# ---------------------------------------------------------------------------------------------------------
@functools.lru_cache(maxsize=4096)
def glyph(text, path, size, stroke=0, spacing=0):
    """(mask uint8 hxw, x offset, y offset from the pen origin (left, baseline), advance)"""
    f = font(path, size)
    x0, y0, x1, y1 = f.getbbox(text, anchor='ls', stroke_width=stroke)
    pad = 2
    w, h = max(1, x1 - x0) + 2 * pad, max(1, y1 - y0) + 2 * pad
    im = Image.new('L', (w, h), 0)
    ImageDraw.Draw(im).text((pad - x0, pad - y0), text, font=f, fill=255, anchor='ls', stroke_width=stroke,
                            stroke_fill=255)
    return np.asarray(im), x0 - pad, y0 - pad, f.getlength(text)


def paste_max(dst, src, x, y, gain=1.0):
    """dst (H,W) float32 = max(dst, src*gain) at integer (x,y); clips."""
    h, w = src.shape[:2]
    x, y = int(round(x)), int(round(y))
    X0, Y0, X1, Y1 = max(0, x), max(0, y), min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if X1 <= X0 or Y1 <= Y0:
        return
    s = src[Y0 - y:Y1 - y, X0 - x:X1 - x]
    d = dst[Y0:Y1, X0:X1]
    if s.dtype == np.uint8:
        s = s.astype(np.float32) * (gain / 255.0)
    elif gain != 1.0:
        s = s * gain
    np.maximum(d, s, out=d)


def paste_ink(K, src, x, y, color, gain=1.0):
    """K (H,W,3) float32 += src * color (additive tint map; normalised later by the geometry)."""
    h, w = src.shape[:2]
    x, y = int(round(x)), int(round(y))
    X0, Y0, X1, Y1 = max(0, x), max(0, y), min(K.shape[1], x + w), min(K.shape[0], y + h)
    if X1 <= X0 or Y1 <= Y0:
        return
    s = src[Y0 - y:Y1 - y, X0 - x:X1 - x].astype(np.float32) * (gain / 255.0 if src.dtype == np.uint8 else gain)
    d = K[Y0:Y1, X0:X1]
    np.maximum(d, s[..., None] * color, out=d)


# ---------------------------------------------------------------------------------------------------------
# the room behind the door
# ---------------------------------------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def _room_noise():
    return rng_noise((H // 4 + 64, W // 4 + 64), 11, 9), rng_noise((H // 4 + 64, W // 4 + 64), 12, 3)


def room(t, flick=0.0, shadow=1.0, scan=0.0):
    """(H/4, W/4) brightness of the lit room seen through the cuts: haze drifting, somebody walking past."""
    a, b = _room_noise()
    h, w = H // 4, W // 4
    ox, oy = int(16 + 14 * math.sin(t * 0.21)), int(16 + 14 * math.cos(t * 0.17))
    ox2, oy2 = int(32 + 30 * math.sin(t * 0.53 + 1)), int(32 + 30 * math.cos(t * 0.47 + 2))
    r = 0.80 + 0.30 * a[oy:oy + h, ox:ox + w] + 0.16 * (b[oy2:oy2 + h, ox2:ox2 + w] - 0.5)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    r = r * (1.08 - 0.22 * yy)                                   # ceiling light: brighter at the top
    if shadow:
        # a figure crossing the room every few seconds: a soft dark column sweeping sideways
        xs = np.linspace(0, 1, w, dtype=np.float32)[None, :]
        for k, (per, wid, ph) in enumerate(((7.3, 0.16, 0.0), (11.9, 0.11, 0.4))):
            u = ((t / per + ph) % 1.0) * 1.6 - 0.3
            if k:
                u = 1.0 - u
            r = r * (1 - 0.50 * shadow * np.exp(-((xs - u) / wid) ** 2))
    if scan:
        r = r * (1 - scan * 0.35 * (0.5 + 0.5 * np.sin((np.arange(h, dtype=np.float32)[:, None] * 4 + t * 90) * 0.9)))
    if flick:
        r = r * (1 - flick)
    return r.astype(np.float32)


@functools.lru_cache(maxsize=None)
def _dust_seed():
    r = np.random.default_rng(77)
    n = 260
    return r.random(n), r.random(n), 0.3 + r.random(n), r.random(n) * 6.28, 0.4 + 0.6 * r.random(n)


def dust(t):
    """(H/4, W/4) motes: slow rise and sideways drift, each twinkling a little."""
    x0, y0, sp, ph, br = _dust_seed()
    h, w = H // 4, W // 4
    x = (x0 * w + 6 * np.sin(t * 0.3 * sp + ph) + t * 1.2 * (sp - 0.8)) % w
    y = (y0 * h - t * 2.2 * sp) % h
    lay = np.zeros((h, w), np.float32)
    np.add.at(lay, (y.astype(int), x.astype(int)), br * (0.6 + 0.4 * np.sin(t * 1.7 * sp + ph)))
    return cv2.GaussianBlur(lay, (0, 0), 0.7) * 2.2


# ---------------------------------------------------------------------------------------------------------
# close shot
# ---------------------------------------------------------------------------------------------------------
def rays_of(e4, cx, cy, n=18, step=0.022):
    """zoom-blur of the quarter-res emission away from (cx,cy): shafts of light through the cuts."""
    h, w = e4.shape[:2]
    acc = np.zeros_like(e4)
    wsum = 0.0
    for k in range(1, n + 1):
        s = 1 + k * step
        M = np.float32([[s, 0, cx * (1 - s)], [0, s, cy * (1 - s)]])
        wk = (1 - k / (n + 1)) ** 1.5
        acc += wk * cv2.warpAffine(e4, M, (w, h), flags=cv2.INTER_LINEAR)
        wsum += wk
    return acc / wsum


def compose_close(G, E, K, t, st):
    """st: dict of scene state.
       light  RGB of the room light           gap    frame-gap brightness      sill  sill brightness
       amb    ambient fill on the door        rays   strength of the shafts    bloom glow strength
       flick  room flicker 0..1               scan   TV scanlines 0..1         shadow passing figures 0..1
       blaze  0..1: the leaf itself glows through (polarity flip) -- cuts read as dark
       key    keyhole light 0..1
    """
    alb, gapm, sillm, hwm, hwalb, keym = close_assets()
    light = st.get('light', AMBER)
    R = room(t, st.get('flick', 0.0), st.get('shadow', 1.0), st.get('scan', 0.0))
    R = cv2.resize(R, (W, H), interpolation=cv2.INTER_LINEAR)

    Kn = K / np.maximum(K.max(axis=2, keepdims=True), 1e-4)      # tint, normalised
    has = (K.max(axis=2, keepdims=True) > 1e-3)
    Kn = np.where(has, Kn, light)

    # quarter-res emission for bloom and shafts (tinted)
    EK4 = cv2.resize(E[..., None] * Kn, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    g1 = cv2.GaussianBlur(EK4, (0, 0), 5)
    g2 = cv2.GaussianBlur(EK4, (0, 0), 22)
    cx, cy = st.get('ray_c', (W / 8, H / 8))
    ry = rays_of(cv2.GaussianBlur(EK4, (0, 0), 1.2), cx, cy)
    glow4 = st.get('bloom', 1.0) * (0.50 * g1 + 0.40 * g2) + st.get('rays', 1.0) * 0.30 * ry
    glow = cv2.resize(glow4, (W, H), interpolation=cv2.INTER_LINEAR)

    gap = st.get('gap', 0.5)
    sill = st.get('sill', 0.8)
    leak = (gap * gapm + sill * sillm)[..., None] * light
    amb = st.get('amb', 0.30)
    # the door's own surface, lit by the leak and by the glow of its cuts
    surf = alb * (amb + 2.2 * leak + 2.6 * glow) + 0.55 * leak + 0.11 * glow
    ring = st.get('ring')
    if ring is not None:
        rg = cv2.resize(ring, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
        surf = surf + alb * rg * (10.0 * light) + rg * (0.10 * light)

    blaze = st.get('blaze', 0.0)
    if blaze > 0:
        yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        leafm = np.zeros((H, W, 1), np.float32)
        leafm[DY0:DY1, DX0:DX1] = 1
        xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :, None]
        rad = np.exp(-(xx ** 2 * 1.3 + ((yy - 0.47) * 2.2) ** 2) * 1.25)
        hotc = light ** st.get('blaze_sat', 1.7)
        hot = hotc * (0.55 + 0.6 * R[..., None]) * (0.55 + 3.2 * rad)
        surf = surf * (1 - blaze * leafm) + hot * blaze * leafm + blaze * (1 - leafm) * light * 0.10

    # inside the cuts: the room (or, when the leaf blazes, the dark)
    inside = (R[..., None] * Kn) * (E[..., None] * (1.25 - blaze)) * 0.95
    core = np.clip(E - 0.9, 0, 3)[..., None]
    inside = inside + core * 0.7                                   # white-hot overshoot when a cut opens
    # thickness of the leaf: a shaded lip on the upper-left inside edge of every cut
    lip = np.clip(G - np.roll(np.roll(G, 5, 0), 4, 1), 0, 1)[..., None]
    inside = inside * (1 - 0.55 * lip) + lip * alb * (0.5 + 4.0 * glow)
    # a thin bright rim just outside the cut where light grazes the edge
    Gm = G[..., None]
    out = surf * (1 - Gm) + inside * Gm

    # dust drifting in front of the door, visible only where there is light to catch
    d4 = dust(t)
    lum4 = glow4.max(axis=2) + 0.25 * cv2.resize((gap * gapm + sill * sillm), (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    out += cv2.resize((d4 * np.minimum(lum4, 1.5))[..., None] * light, (W, H), interpolation=cv2.INTER_LINEAR) * st.get('dust', 1.0)

    # hardware in front of everything
    hwl = hwalb * (amb * 1.3 + 2.0 * leak + 2.4 * glow)
    out = out * (1 - hwm[..., None]) + hwl * hwm[..., None]
    k = st.get('key', 0.35)
    out = out * (1 - keym[..., None]) + keym[..., None] * light * (0.08 + 2.2 * k)

    # the floor mirrors the bottom of the door, dimly
    fh = H - (DY1 + 6)
    refl = out[DY1 - fh:DY1][::-1]
    fall = np.linspace(0.34, 0.04, fh, dtype=np.float32)[:, None, None]
    out[DY1 + 6:] += cv2.blur(refl, (9, 3)) * fall
    return out


def tone(x, exposure=1.0):
    """filmic shoulder + gamma, to uint8."""
    x = 1.0 - np.exp(-np.maximum(x, 0) * (1.55 * exposure))
    np.sqrt(x, out=x)                # gamma 2.0
    return x


def finish(lin, t, st, seed=0):
    """vignette, tone, grain, shake, aberration, flash -> uint8 RGB"""
    lin = lin * vignette()
    fl = st.get('flash', 0.0)
    if fl > 0:
        lin = lin + fl * np.asarray(st.get('flash_c', WHITE), np.float32)
    img = tone(lin, st.get('exposure', 1.0))
    # grain
    r = np.random.default_rng(int(t * 1000) + seed)
    g = r.standard_normal((H // 2, W // 2)).astype(np.float32)
    g = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)
    img = img + (0.030 * st.get('grain', 1.0)) * g[..., None] * (1.1 - img)
    # camera: zoom about the centre, shift, roll
    z = st.get('zoom', 1.0)
    dx, dy = st.get('shake', (0.0, 0.0))
    rot = st.get('roll', 0.0)
    if z != 1.0 or dx or dy or rot:
        M = cv2.getRotationMatrix2D((W / 2, H * 0.48), rot, z)
        M[0, 2] += dx
        M[1, 2] += dy
        img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    ab = st.get('aberr', 0.0)
    if ab > 0.3:
        a = int(round(ab))
        img[..., 0] = np.roll(img[..., 0], a, 1)
        img[..., 2] = np.roll(img[..., 2], -a, 1)
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
