"""The departure wall: a grid of split-flap cells, their schedule, and a camera that films them.

Board coordinates: x in cell pitches (a full-width cell is 1.0 wide, a Latin half cell 0.5), y in rows.
A row is RATIO pitches tall, so on screen everything is measured in pitches.

Cells have a lifetime [t_on, t_off). Content cells (one per character slot of a lyric line) live from just
before their line starts landing until they have flipped back to blank; background cells (blank flaps on the
integer grid) fill every place and time no content cell occupies. When a Latin word needs half-width flaps
where a full blank flap was, the swap happens while both are blank.

The score only calls Board.add(...) and Cell.target(T, char, style, ...): "this cell shows this character
from time T on". build() turns each cell's targets into folds: each landing spins through a few other
characters first, the last fold ending exactly at T.
"""
import bisect
import random

import cv2
import numpy as np

from flap import HOUSING, fold, tile, is_half

RATIO = 1.39
W, H = 1080, 1920
INF = 1e9

CJK_POOL = list('一二三四五六七八九十年月日天人大中上下来去出发到达门开关时间重启倒数清空裁岗工位世界在烧找站厦高崎机场航班'
                '东西南北风雨雪云山海城市金银石油火光明暗夜星梦心手口目耳')
LAT_POOL = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
BLANK = (' ', 'k')


class Cell:
    __slots__ = ('x', 'y', 'w', 'h', 'heavy', 'targets', 'folds', 'ends', 'init', 'half', 't_on', 't_off', 'order', 'bg')

    def __init__(self, x, y, w=1.0, h=1.0, heavy=False, init=BLANK, t_on=-INF, t_off=INF):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.heavy = heavy
        self.targets = []
        self.folds = []
        self.ends = []
        self.init = init
        self.half = w < 0.75 * h
        self.t_on, self.t_off = t_on, t_off
        self.order = 0
        self.bg = False

    def target(self, T, ch, style='w', steps=3, step=0.055, pool=None, mid=None):
        """land on ch at T; mid = style of the characters spun through on the way (default: style)."""
        if ch == ' ':
            style = 'k'
        self.targets.append((T, ch, style, steps, step, pool, mid))

    def showing(self, T):
        """(char, style) of the latest target at or before T."""
        cur = self.init
        for r in sorted(self.targets, key=lambda r: r[0]):
            if r[0] <= T:
                cur = (r[1], r[2])
        return cur

    def last_T(self):
        return max((r[0] for r in self.targets), default=-INF)

    def build(self, rng):
        self.targets.sort(key=lambda r: r[0])
        cur = self.init
        prev_T = -INF
        folds = []
        for T, ch, style, steps, step, pool, mid in self.targets:
            if (ch, style) == cur and steps <= 0:
                prev_T = T
                continue
            n = steps + 1
            t0 = T - n * step
            if t0 < prev_T + 0.01:
                n = max(1, int((T - prev_T - 0.01) / step))
                t0 = T - n * step
            if pool is None:
                pool_ = LAT_POOL if (is_half(ch) and ch != ' ') or self.half else CJK_POOL
            else:
                pool_ = pool
            st_mid = mid or (style if style != 'k' else (cur[1] if cur[1] != 'k' else 'w'))
            seq = [(rng.choice(pool_), st_mid) for _ in range(n - 1)] + [(ch, style)]
            a = cur
            for k, b in enumerate(seq):
                folds.append((t0 + k * step, t0 + (k + 1) * step, a, b))
                a = b
            cur = (ch, style)
            prev_T = T
        self.folds = folds
        self.ends = [f[1] for f in folds]

    def state(self, t):
        """(a, b, p): resting on b if p >= 1."""
        if not self.folds or t < self.folds[0][0]:
            return self.init, self.init, 1.0
        k = bisect.bisect_right(self.ends, t)
        if k >= len(self.folds):
            f = self.folds[-1]
            return f[3], f[3], 1.0
        f = self.folds[k]
        if t < f[0]:
            g = self.folds[k - 1]
            return g[3], g[3], 1.0
        return f[2], f[3], (t - f[0]) / (f[1] - f[0])

    def shown(self, t):
        a, b, p = self.state(t)
        return b if p >= 1 else (a if p < 0.5 else b)


class Board:
    def __init__(self, seed=43):
        self.cells = []
        self.rng = random.Random(seed)
        self.grid = None

    def add(self, x, y, w=1.0, h=1.0, heavy=False, init=BLANK, t_on=-INF, t_off=INF):
        c = Cell(x, y, w, h, heavy, init, t_on, t_off)
        c.order = len(self.cells)
        self.cells.append(c)
        return c

    def fill_background(self, x0, x1, y0, y1, exclude=(), sx=1.0, sy=1.0):
        """blank flaps of size (sx, sy) tiling [x0, x1) x [y0, y1), alive wherever and whenever no other cell
        overlaps them. exclude: rects (x0, y0, x1, y1) left untiled (modules, the panel)."""
        content = [c for c in self.cells if not getattr(c, 'bg', False)]
        buckets = {}
        for c in content:
            for ry in range(int(np.floor(c.y)), int(np.ceil(c.y + c.h - 1e-6))):
                for gx in range(int(np.floor(c.x)), int(np.ceil(c.x + c.w - 1e-6))):
                    buckets.setdefault((gx, ry), []).append(c)
        n = 0
        ny = int(round((y1 - y0) / sy))
        nx = int(round((x1 - x0) / sx))
        for j in range(ny):
            for i in range(nx):
                cx0, cy0 = x0 + i * sx, y0 + j * sy
                cx1, cy1 = cx0 + sx, cy0 + sy
                mx, my = cx0 + sx / 2, cy0 + sy / 2
                if any(ex[0] <= mx < ex[2] and ex[1] <= my < ex[3] for ex in exclude):
                    continue
                near = set()
                for ry in range(int(np.floor(cy0)), int(np.ceil(cy1 - 1e-6))):
                    for gx in range(int(np.floor(cx0)), int(np.ceil(cx1 - 1e-6))):
                        for c in buckets.get((gx, ry), ()):
                            near.add(c)
                iv = sorted((c.t_on, c.t_off) for c in near
                            if c.x < cx1 - 1e-6 and c.x + c.w > cx0 + 1e-6 and c.y < cy1 - 1e-6 and c.y + c.h > cy0 + 1e-6)
                t = -INF
                for a, b in iv:
                    if a > t + 1e-6:
                        c = self.add(cx0, cy0, sx, sy, t_on=t, t_off=a)
                        c.bg = True
                        n += 1
                    t = max(t, b)
                if t < INF:
                    c = self.add(cx0, cy0, sx, sy, t_on=t, t_off=INF)
                    c.bg = True
                    n += 1
        return n

    def at(self, x, y, t):
        """cells covering board point (x, y rows) alive at t."""
        return [c for c in self.cells if c.x <= x < c.x + c.w and c.y <= y < c.y + c.h and c.t_on <= t < c.t_off]

    def build(self):
        for c in self.cells:
            c.build(self.rng)
        self.grid = {}
        for c in self.cells:
            for ry in range(int(np.floor(c.y)), int(np.ceil(c.y + c.h))):
                for bx in range(int(np.floor(c.x / 4)), int(np.ceil((c.x + c.w) / 4))):
                    self.grid.setdefault((ry, bx), []).append(c)

    def visible(self, x0, y0, x1, y1, t):
        out = {}
        for ry in range(int(np.floor(y0)) - 4, int(np.ceil(y1)) + 1):
            for bx in range(int(np.floor(x0 / 4)) - 1, int(np.ceil(x1 / 4)) + 1):
                for c in self.grid.get((ry, bx), ()):
                    if c.t_on <= t < c.t_off and c.x + c.w > x0 and c.x < x1 and c.y + c.h > y0 and c.y < y1:
                        out[c.order] = c
        return [out[k] for k in sorted(out)]


LEVELS = (152, 114, 76, 56, 38, 28, 20)


class Camera:
    """centre (cx, cy) in board pitches (y = rows * RATIO), vw = pitches across the screen width,
    roll in radians, (tilt_x, tilt_y) small perspective angles in radians."""

    def __init__(self, cx, cy, vw, roll=0.0, tilt_x=0.0, tilt_y=0.0):
        self.cx, self.cy, self.vw, self.roll, self.tilt_x, self.tilt_y = cx, cy, vw, roll, tilt_x, tilt_y

    def matrix(self):
        s = W / self.vw
        c, sn = np.cos(self.roll), np.sin(self.roll)
        T0 = np.array([[1, 0, -self.cx], [0, 1, -self.cy], [0, 0, 1]], np.float64)
        S = np.array([[s * c, -s * sn, 0], [s * sn, s * c, 0], [0, 0, 1]], np.float64)
        f = 2.2 * W
        P = np.array([[1, 0, 0], [0, 1, 0], [np.tan(self.tilt_y) / f, np.tan(self.tilt_x) / f, 1]], np.float64)
        T1 = np.array([[1, 0, W / 2], [0, 1, H / 2], [0, 0, 1]], np.float64)
        return T1 @ P @ S @ T0


def render_board(board, t, cam, mb=3, mb_span=0.5 / 30):
    """the board as seen by cam at time t: image (H, W, 3), coverage (H, W), board->screen homography."""
    Hm = cam.matrix()
    inv = np.linalg.inv(Hm)
    corners = np.array([[0, 0, 1], [W, 0, 1], [W, H, 1], [0, H, 1]], np.float64).T
    bc = inv @ corners
    bc = bc[:2] / bc[2]
    x0, x1 = bc[0].min() - 0.5, bc[0].max() + 0.5
    y0, y1 = bc[1].min() / RATIO - 0.5, bc[1].max() / RATIO + 0.5
    # pixels per pitch where the board is closest to the camera
    scale = W / cam.vw * 1.08
    k = LEVELS[0]
    for lv in LEVELS:
        if lv >= scale:
            k = lv
    PYK = int(round(k * RATIO))
    cells = board.visible(x0, y0, x1, y1, t)
    if cells:
        bx0 = max(min(c.x for c in cells), x0 - 4)
        by0 = max(min(c.y for c in cells), y0 - 4)
        bx1 = min(max(c.x + c.w for c in cells), x1 + 4)
        by1 = min(max(c.y + c.h for c in cells), y1 + 4)
    else:
        bx0, by0, bx1, by1 = x0, y0, x0 + 1, y0 + 1
    bx0 = np.floor(bx0 * 2) / 2
    by0 = np.floor(by0)
    cw = int(np.ceil((bx1 - bx0) * k)) + 2
    ch = int(np.ceil((by1 - by0) * PYK)) + 2
    canvas = np.empty((ch, cw, 3), np.float32)
    canvas[:] = HOUSING
    for c in cells:
        px = int(round((c.x - bx0) * k))
        py = int(round((c.y - by0) * PYK))
        w = int(round(c.w * k))
        h = int(round(c.h * PYK))
        a, b, p = c.state(t)
        if p >= 1:
            img = tile(b[0], b[1], w, h, c.heavy)[0]
        else:
            acc = None
            for j in range(mb):
                tj = t + (j - (mb - 1) / 2) * mb_span / max(1, mb - 1)
                aa, bb, pp = c.state(tj)
                im = fold(aa[0], aa[1], bb[0], bb[1], w, h, min(1.0, max(0.0, pp)), c.heavy)
                acc = im if acc is None else acc + im
            img = acc / mb
        sx0, sy0 = max(0, -px), max(0, -py)
        ex, ey = min(w, cw - px), min(h, ch - py)
        if ex > sx0 and ey > sy0:
            canvas[py + sy0:py + ey, px + sx0:px + ex] = img[sy0:ey, sx0:ex]
    C2B = np.array([[1 / k, 0, bx0], [0, RATIO / PYK, by0 * RATIO], [0, 0, 1]], np.float64)
    M = Hm @ C2B
    out = cv2.warpPerspective(canvas, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                              borderValue=(0, 0, 0))
    cov = cv2.warpPerspective(np.ones(canvas.shape[:2], np.float32), M, (W, H), flags=cv2.INTER_LINEAR)
    return out, cov, Hm
