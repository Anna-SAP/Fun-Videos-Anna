"""Light, lens and film for one frame of the wall.

light_map(): the hall is dark; a few soft lights are defined in board coordinates (a pool of light on the line
being sung, a weaker wash, the dawn's window bars at the end), so they stay on the wall when the camera moves.
finish(): bloom, depth of field around the focus line, grade, vignette, grain.
"""
import cv2
import numpy as np

W, H = 1080, 1920
LW, LH = 135, 240          # light map resolution

_gy, _gx = np.mgrid[0:LH, 0:LW].astype(np.float64)
_gx = (_gx + 0.5) * W / LW
_gy = (_gy + 0.5) * H / LH
_GRID = np.stack([_gx.ravel(), _gy.ravel(), np.ones(LW * LH)])


def board_coords(Hm):
    """board pitches (bx, by) of every light-map pixel."""
    inv = np.linalg.inv(Hm)
    b = inv @ _GRID
    return (b[0] / b[2]).reshape(LH, LW), (b[1] / b[2]).reshape(LH, LW)


def rect_dist(bx, by, r):
    x0, y0, x1, y1 = r
    dx = np.maximum(np.maximum(x0 - bx, bx - x1), 0)
    dy = np.maximum(np.maximum(y0 - by, by - y1), 0)
    return np.sqrt(dx * dx + dy * dy)


def light_map(Hm, lights, ambient):
    """lights: list of dicts {rect (pitches), sigma, color (3,), gain}; also {'bars': ...} for window light.
    Returns full-res (H, W, 3) multiplier."""
    bx, by = board_coords(Hm)
    L = np.zeros((LH, LW, 3), np.float64)
    L += np.asarray(ambient, np.float64)[None, None]
    for li in lights:
        if li.get('kind') == 'bars':
            # parallel soft bars of sunlight across the wall, slanted
            ang = li.get('angle', -0.5)
            u = bx * np.cos(ang) + by * np.sin(ang)
            per = li['period']
            ph = (u - li.get('offset', 0.0)) / per
            fr = ph - np.floor(ph)
            duty = li.get('duty', 0.62)
            soft = li.get('soft', 0.06)
            bar = np.clip((duty / 2 - np.abs(fr - 0.5)) / soft + 0.5, 0, 1)
            # broad falloff of the patch of sun
            cx, cy, rad = li['centre'][0], li['centre'][1], li['radius']
            fall = np.exp(-((bx - cx) ** 2 + (by - cy) ** 2) / (2 * rad ** 2))
            L += li['gain'] * (bar * fall)[..., None] * np.asarray(li['color'])[None, None]
            continue
        d = rect_dist(bx, by, li['rect'])
        g = np.exp(-0.5 * (d / li['sigma']) ** 2)
        L += li['gain'] * g[..., None] * np.asarray(li['color'])[None, None]
    L = cv2.resize(L.astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    return L


def sheen(Hm, t, gain=0.035):
    """a slow diagonal reflection of the hall lights sliding over the flaps (screen-space, in board coords)."""
    bx, by = board_coords(Hm)
    u = (bx + 0.6 * by) * 0.08 - 0.05 * t
    s = np.exp(-((u - np.round(u)) ** 2) / (2 * 0.06 ** 2))
    return cv2.resize((gain * s).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)


def bloom(img, thr=0.7, gain=0.35):
    small = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    hi = np.maximum(small - thr, 0)
    b1 = cv2.GaussianBlur(hi, (0, 0), 3)
    b2 = cv2.GaussianBlur(hi, (0, 0), 12)
    b = cv2.resize(0.6 * b1 + 0.8 * b2, (W, H), interpolation=cv2.INTER_LINEAR)
    return img + gain * b


def dof(img, focus_y, depth, strength):
    """blur growing away from a horizontal focus band at screen y = focus_y (pixels)."""
    if strength <= 0.01:
        return img
    small = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    bl = cv2.resize(cv2.GaussianBlur(small, (0, 0), 2.2), (W, H), interpolation=cv2.INTER_LINEAR)
    y = np.arange(H, dtype=np.float32)
    m = np.clip((np.abs(y - focus_y) - depth) / (0.35 * H), 0, 1) * strength
    m = m[:, None, None]
    return img * (1 - m) + bl * m


def grade(img, lift=(0.012, 0.016, 0.026), gamma=1.0, sat=1.0, tint=(1, 1, 1)):
    """tint and saturation as one colour matrix, then a soft filmic shoulder and a coloured lift of the blacks."""
    lw = np.array([0.2126, 0.7152, 0.0722], np.float32)
    S = np.eye(3, dtype=np.float32) * sat + (1 - sat) * np.tile(lw, (3, 1))
    M = (S @ np.diag(np.asarray(tint, np.float32))).astype(np.float32)
    x = cv2.transform(img.astype(np.float32, copy=False), M)
    np.maximum(x, 0, out=x)
    d = x * 0.18
    d += 1
    x /= d
    x *= 1.18
    l = np.asarray(lift, np.float32)
    x += l * (1 - np.minimum(x, 1))
    if gamma != 1.0:
        np.power(x, gamma, out=x)
    return x


_VIG = None


def vignette(img, k=0.38):
    global _VIG
    if _VIG is None:
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((x - W / 2) / (W * 0.62)) ** 2 + ((y - H / 2) / (H * 0.62)) ** 2)
        _VIG = np.clip(1 - r ** 2.2, 0, 1)
    v = 1 - k + k * _VIG
    return img * v[..., None]


_GRAIN = None


def grain(img, frame, amt=0.018):
    global _GRAIN
    if _GRAIN is None:
        rng = np.random.default_rng(13)
        _GRAIN = [cv2.resize(rng.standard_normal((H // 2 + 64, W // 2 + 64)).astype(np.float32), (W + 128, H + 128),
                             interpolation=cv2.INTER_LINEAR) for _ in range(6)]
    g = _GRAIN[frame % 6]
    ox, oy = (frame * 37) % 128, (frame * 71) % 128
    n = g[oy:oy + H, ox:ox + W]
    lum = np.clip(img[..., 1], 0, 1)
    k = (amt * (0.4 + 0.6 * (1 - lum))) * n
    return img + k[..., None]


_LUT = (np.power(np.linspace(0, 1, 4096), 1 / 1.12) * 255 + 0.5).astype(np.uint8)


def to_u8(img):
    idx = np.clip(img * 4095, 0, 4095).astype(np.uint16)
    return _LUT[idx]


# ---------------------------------------------------------------- the hall around the wall (wide shots)
_rng = np.random.default_rng(2026)
BOKEH = [(float(_rng.uniform(-60, 103)), float(_rng.uniform(-50, 120)), float(_rng.uniform(0.5, 1.6)),
          float(_rng.uniform(0.25, 1.0)), int(_rng.integers(0, 3))) for _ in range(70)]
BOKEH_COL = (np.array((1.0, 0.72, 0.42)), np.array((0.55, 0.70, 1.0)), np.array((1.0, 0.92, 0.80)))


def hall(Hm, cam_vw, warm, gain):
    """out-of-focus hall lights on a plane far behind the wall (it moves less than the wall: parallax)."""
    small = np.zeros((H // 4, W // 4, 3), np.float32)
    inv = np.linalg.inv(Hm)
    c = inv @ np.array([W / 2, H / 2, 1.0])
    cx, cy = c[0] / c[2], c[1] / c[2]
    s = (W / 4) / (cam_vw * 2.2)          # the far plane appears 2.2x smaller
    for bx, by, r, a, k in BOKEH:
        x = (bx - (cx * 0.45 + 22.5 * 0.55)) * s + W / 8
        y = (by - (cy * 0.45 + 35.0 * 0.55)) * s + H / 8
        rad = max(1.5, r * s * 1.2)
        if -rad < x < W / 4 + rad and -rad < y < H / 4 + rad:
            col = BOKEH_COL[k] * (1 - warm) + BOKEH_COL[0] * warm
            cv2.circle(small, (int(x), int(y)), int(rad), tuple(float(v * a * gain) for v in col), -1, cv2.LINE_AA)
    small = cv2.GaussianBlur(small, (0, 0), 1.2)
    return cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)


def reflection(img, Hm, y_bottom, cov, gain=0.22, fall=7.0):
    """the polished floor under the wall: the lit wall mirrored about its bottom edge, blurred, fading."""
    M = np.array([[1, 0, 0], [0, -1, 2 * y_bottom], [0, 0, 1]], np.float64)
    S = Hm @ M @ np.linalg.inv(Hm)
    small = cv2.resize(img, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    Sh = np.diag([0.5, 0.5, 1.0]) @ S @ np.diag([2.0, 2.0, 1.0])
    r = cv2.warpPerspective(small, Sh, (W // 2, H // 2), flags=cv2.INTER_LINEAR)
    r = cv2.GaussianBlur(r, (0, 0), 3.0)
    bx, by = board_coords(Hm)
    d = np.clip(by - y_bottom, 0, None)
    f = np.where(by > y_bottom, np.exp(-d / fall), 0).astype(np.float32)
    f = cv2.resize(f, (W // 2, H // 2), interpolation=cv2.INTER_LINEAR)
    r = cv2.resize(r * f[..., None], (W, H), interpolation=cv2.INTER_LINEAR)
    return r * gain * (1 - cov)[..., None]
