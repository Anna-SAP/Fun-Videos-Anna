#!/usr/bin/env python3
"""The Moment You Saw Me: turn the keyframes into a 9:16 film.

  render.py PYLIBS --preview 1.2,56.5     write preview frames to work/preview/
  render.py PYLIBS --shots s01,s02        render only these shots to work/segments/
  render.py PYLIBS --all [N]              render every missing shot with N workers

Each still is moved by its depth map, so a slow push reads as a real camera move. The rain is not in the
stills: it is drawn here as particles on a warped clock (timeline.phi), which lets it slow under the long
held notes of the pre-chorus, hang in the air for the half second the band stops, and come back lit by the
sun on the first downbeat of the chorus.
"""
import math
import os
import subprocess
import sys

PYLIBS = sys.argv[1]
sys.path.insert(0, PYLIBS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from timeline import B, FPS, FXGEO, GAP1, GAP2, H, PULSES, SHOTS, TOTAL, W, phi, rate  # noqa: E402

cv2.setNumThreads(1)
KF, DEP, SEG, PREV = 'work/keyframes', 'work/depth', 'work/segments', 'work/preview'
FONT_TITLE = 'C:/Windows/Fonts/georgiai.ttf'
SAT = .93

xx, yy = np.meshgrid(np.arange(W, dtype=np.float32) - W / 2, np.arange(H, dtype=np.float32) - H / 2)
VIG = (1 - .2 * ((xx / (W / 2)) ** 2 * .7 + (yy / (H / 2)) ** 2 * .5)).astype(np.float32)[..., None]
FLOODS = (GAP1[1], GAP2[1])


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def wobble(t, seed):
    """Smooth, repeatable noise in about -1..1, weighted to slow drift."""
    r = np.random.default_rng(seed)
    f = r.uniform(.1, .8, 7)
    p = r.uniform(0, 6.28, 7)
    a = 1 / f
    return float(np.sum(a * np.sin(2 * np.pi * f * t + p)) / np.sum(a)) * 1.8


def imread(path, flags=cv2.IMREAD_COLOR):
    return cv2.imdecode(np.fromfile(path, np.uint8), flags)


_plates, _depths = {}, {}


def plate(kf):
    if kf not in _plates:
        _plates[kf] = imread(f'{KF}/{kf}.png')
    return _plates[kf]


def depth(kf):
    if kf not in _depths:
        d = imread(f'{DEP}/{kf}.png', cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535
        _depths[kf] = cv2.GaussianBlur(d, (0, 0), 5)
    return _depths[kf]


def pulse(t, decay=.28):
    """1 just after a brushed tick on beats 2 and 4, falling back to 0."""
    best = 0.0
    for p in PULSES:
        if p <= t < p + 1.2:
            best = max(best, math.exp(-(t - p) / decay))
    return best


# ---------------------------------------------------------------- plate effects (in keyframe space)
_twk = {}


def twinkle(img, kf, t):
    """Small bright points breathe: water beads and wet leaves catching the sun."""
    if kf not in _twk:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        top = g - cv2.GaussianBlur(g, (0, 0), 9)
        m = np.clip((top - 12) / 40, 0, 1)
        r = np.random.default_rng(sum(map(ord, kf)))
        _twk[kf] = (cv2.GaussianBlur(m, (0, 0), 1.2), r.uniform(0, 6.28, (img.shape[0] // 10, img.shape[1] // 10)).astype(np.float32),
                    r.uniform(.25, .8, (img.shape[0] // 10, img.shape[1] // 10)).astype(np.float32))
    m, ph, fr = _twk[kf]
    g = np.sin(2 * np.pi * fr * t + ph) * .3
    g = cv2.resize(g, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
    return np.clip(img.astype(np.float32) * (1 + m * g)[..., None], 0, 255).astype(np.uint8)


_steam = {}


def steam(img, kf, t):
    """A thread of steam above the paper cup. geo: x, y of the cup mouth, width, height, strength."""
    x, y, w, h, amt = FXGEO[kf]['steam']
    x0, y0 = int(x - w / 2), int(y - h)
    x0, y0 = max(0, x0), max(0, y0)
    w, h = min(w, img.shape[1] - x0), min(h, img.shape[0] - y0)
    if kf not in _steam:
        r = np.random.default_rng(5)
        tile = sum(cv2.resize(r.random((n, n), dtype=np.float32), (512, 1024), interpolation=cv2.INTER_CUBIC) * a
                   for n, a in ((6, .6), (14, .3), (30, .1)))
        tile = np.clip((tile - .35) * 2.6, 0, 1)
        yy_, xx_ = np.mgrid[0:h, 0:w].astype(np.float32)
        up = 1 - yy_ / h
        spread = w * .07 + up * w * .3
        cone = np.exp(-((xx_ - w * .5 - w * .05 * np.sin(up * 7)) / spread) ** 2) * np.clip(up * 6, 0, 1) * (1 - up) ** 1.4
        _steam[kf] = tile, cone.astype(np.float32)
    tile, cone = _steam[kf]
    n = np.roll(tile, int(t * 70) % tile.shape[0], axis=0)
    n = cv2.resize(n[:min(h, 1024) * 1, :], (w, h), interpolation=cv2.INTER_LINEAR) if (h > 1024 or w > 512) else n[:h, :w]
    out = img.copy()
    out[y0:y0 + h, x0:x0 + w] = np.clip(img[y0:y0 + h, x0:x0 + w].astype(np.float32) + (n * cone * amt)[..., None], 0, 255).astype(np.uint8)
    return out


_rings = {}


def rings(img, sh, t, plink=False):
    """Raindrop rings on water seen from above (or beads struck on the umbrella skin, with plink=True).

    Drops are scheduled on the warped clock, so the rings widen slowly under the held notes and stop in the gap.
    geo: x0, y0, x1, y1 of the water, drops per second, and a (start, end) density ramp across the shot.
    """
    kf = sh.kf
    x0, y0, x1, y1, per_s, ramp = FXGEO[kf]['plinks' if plink else 'rings']
    key = (kf, plink)
    if key not in _rings:
        r = np.random.default_rng(sum(map(ord, kf)) + 3)
        span = phi(sh.t1) - phi(sh.t0) + 2
        n = int(per_s * span)
        born = np.sort(r.uniform(-1.5, span, n))
        if plink:      # most strikes land with the brushed tick on beats 2 and 4
            ticks = np.array([phi(p) - phi(sh.t0) for p in PULSES if sh.t0 - 1 <= p < sh.t1])
            snap = r.random(n) < .6
            born[snap] = r.choice(ticks, int(snap.sum())) + r.normal(0, .035, int(snap.sum()))
        keep = r.random(n) < ramp[0] + (ramp[1] - ramp[0]) * np.clip(born / max(span - 2, 1e-3), 0, 1)
        _rings[key] = born[keep], r.uniform(x0, x1, n)[keep], r.uniform(y0, y1, n)[keep], r.uniform(.6, 1.3, n)[keep]
    born, px, py, sz = _rings[key]
    age = (phi(t) - phi(sh.t0)) - born
    life = .55 if plink else 1.5
    live = (age > 0) & (age < life)
    if not live.any():
        return img
    lay = np.zeros(img.shape[:2], np.float32)
    for a, x, y, s in zip(age[live], px[live], py[live], sz[live]):
        k = a / life
        if plink:
            rad = 4 + 26 * s * k ** .6
            cv2.circle(lay, (int(x), int(y)), int(rad), float((1 - k) ** 2 * 1.0), 2, cv2.LINE_AA)
            cv2.circle(lay, (int(x), int(y)), max(1, int(5 * s * (1 - k))), float((1 - k) ** 3 * 1.6), -1, cv2.LINE_AA)
        else:
            for j, w in ((1.0, 1.0), (.6, .55)):
                rad = (6 + 120 * s * k ** .7) * j
                cv2.circle(lay, (int(x), int(y)), int(rad), float((1 - k) ** 1.6 * w), 3, cv2.LINE_AA)
    lay = cv2.GaussianBlur(lay, (0, 0), 1.6)
    amp = 46 if plink else 30
    # a ring is a ridge: lit on one side, shaded on the other
    sh_ = np.roll(lay, 3, axis=0) - np.roll(lay, -3, axis=0)
    out = img.astype(np.float32) + (lay * amp * .55 + sh_ * amp)[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- rain (in output space)
class Rain:
    """Three depths of falling drops. Positions follow the warped clock; streak length follows its speed."""
    LAYERS = (  # count, speed px/s, thickness, brightness, blur, hidden behind near things
        (1500, 1350, 1, .50, .7, 1.0),
        (520, 2200, 1, .85, .8, .6),
        (60, 3600, 3, .9, 2.6, 0.0),
    )

    def __init__(self, seed):
        r = np.random.default_rng(seed)
        self.p = []
        for n, speed, th, br, blur, occ in self.LAYERS:
            self.p.append(dict(x=r.uniform(-200, W + 200, n), y=r.uniform(0, H + 400, n), v=speed * r.uniform(.8, 1.2, n),
                               b=r.uniform(.35, 1.0, n) ** 1.5, glint=r.random(n), ph=r.uniform(0, 6.28, n)))
        self.slant = r.uniform(.04, .09) * r.choice([-1, 1])

    def draw(self, t, d_near, amount, sun, rnear=1.0):
        """Returns an additive light layer (H, W, 3) float."""
        ph, sp = phi(t), rate(t)
        out = np.zeros((H, W, 3), np.float32)
        cool = np.array([.86, .80, .74], np.float32)          # BGR, grey-blue
        gold = np.array([.40, .76, 1.0], np.float32)
        tint = cool * (1 - sun) + gold * sun
        tick = pulse(t)
        for j, ((n, speed, th, br, blur, occ), p) in enumerate(zip(self.LAYERS, self.p)):
            k = int(n * min(1.0, amount))
            lay = np.zeros((H, W), np.float32)
            y = (p['y'][:k] + p['v'][:k] * ph) % (H + 400) - 200
            x = p['x'][:k] + self.slant * y
            ln = np.maximum(p['v'][:k] * sp / 34, th * 2.0)            # a long shutter; a bead when time nearly stops
            # in the sun a share of the drops flash as they cross the light; a hanging bead holds more light than a streak
            flash = np.where(p['glint'][:k] < .2 * sun, 2.0 + 1.3 * np.sin(p['ph'][:k] + ph * 9), 1.0) * (1 + 1.6 * (1 - sp) * (.4 + sun))
            if sp < .12 and j:          # time has all but stopped: the drops hang as round beads
                for xi, yi, bi in zip(x, y, br * p['b'][:k] * flash):
                    cv2.circle(lay, (int(xi), int(yi)), th + 1, float(bi), -1, cv2.LINE_AA)
            else:
                for xi, yi, li, bi in zip(x, y, ln, br * p['b'][:k] * flash):
                    cv2.line(lay, (int(xi), int(yi)), (int(xi + self.slant * li), int(yi + li)), float(bi), th, cv2.LINE_AA)
            lay = cv2.GaussianBlur(lay, (0, 0), blur)
            if j == 2:
                lay *= rnear
            else:
                lay *= 1 - min(1.0, occ + (1 - rnear)) * d_near
            out += lay[..., None] * tint
        strength = (.2 + .22 * sun) * (1 + .12 * tick * sun)
        return out * strength


_rain = {}


# ---------------------------------------------------------------- one shot at one moment
def view(sh, k):
    vs = sh.views
    if k <= vs[0][0]:
        return vs[0][1:]
    for (k0, *a), (k1, *b) in zip(vs, vs[1:]):
        if k <= k1:
            e = (k - k0) / (k1 - k0)
            return [x + (y - x) * e for x, y in zip(a, b)]
    return vs[-1][1:]


def lerp2(pair, k):
    return pair[0] + (pair[1] - pair[0]) * min(max(k, 0.0), 1.0)


def layer(sh, t):
    kf = sh.kf
    # the camera runs on the warped clock too, so it also holds its breath in the gap
    tw = sh.t0 + (phi(t) - phi(sh.t0)) * (sh.t1 - sh.t0) / max(phi(sh.t1) - phi(sh.t0), 1e-6) if t <= sh.t1 else t
    k = (tw - sh.t0) / (sh.t1 - sh.t0)
    kc = min(max(k, -.3), 1.35)
    cxn, cyn, z = view(sh, kc)
    src = plate(kf)
    sh_h, sh_w = src.shape[:2]
    cx, cy = cxn * sh_w, cyn * sh_h
    scale = (1040 / z) / W
    th = phi(t)
    hx = sh.hand * 6.0 * wobble(th, 11 + sh.idx)
    hy = sh.hand * 5.0 * wobble(th, 12 + sh.idx)
    rot = math.radians(sh.hand * .12 * wobble(th, 13 + sh.idx) + sh.spin * (kc - .5))
    c, s = math.cos(rot), math.sin(rot)
    u = cx + scale * (c * xx - s * yy + hx)
    v_ = cy + scale * (s * xx + c * yy + hy)
    img = src
    if 'twinkle' in sh.fx:
        img = twinkle(img, kf, th)
    if 'steam' in sh.fx:
        img = steam(img, kf, th)
    if 'rings' in sh.fx:
        img = rings(img, sh, t)
    if 'plinks' in sh.fx:
        img = rings(img, sh, t, plink=True)
    d = cv2.remap(depth(kf), u, v_, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    rel = d - sh.focus
    sl = kc - .5
    px = (sh.par * sl + 1.3 * hx) * scale
    py = (sh.parv * sl + 1.3 * hy) * scale
    U = u + px * rel + (u - cx) * rel * sh.dolly * sl
    V = v_ + py * rel + (v_ - cy) * rel * sh.dolly * sl
    f = cv2.remap(img, U, V, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT101).astype(np.float32) / 255

    # defocus (the muffled opening, the last chord dying away)
    if sh.blur != (0.0, 0.0) and sh.blur != (0, 0):
        if 'blur_end' in sh.extra:
            sig = sh.blur[0] * (1 - smooth(t / sh.extra['blur_end']))
        else:
            sig = sh.blur[1] * smooth((t - sh.extra['blur_start']) / (sh.extra['end'] - sh.extra['blur_start']))
        if sig > .3:
            f = cv2.GaussianBlur(f, (0, 0), sig)

    # white balance and exposure travel across the shot
    wb = lerp2(sh.warm, k)
    f = f * lerp2(sh.gain, k) * np.array([1 - .09 * wb, 1.0, 1 + .09 * wb], np.float32)

    if sh.rain > 0:
        if sh.idx not in _rain:
            _rain[sh.idx] = Rain(100 + sh.idx)
        near = np.clip((d - .45) / .25, 0, 1)
        sun = sh.sun if sh.sun in (0, 1) else sh.sun * smooth(k * 1.2)
        f = f + _rain[sh.idx].draw(t, near, sh.rain, sun, sh.rnear) * (1.15 - .6 * np.clip(f.mean(2, keepdims=True), 0, 1))

    if 'flood' in sh.fx:
        # the band comes back in and the sun with it: a soft surge that settles over two seconds
        dt = t - sh.t0
        if dt >= 0:
            a = math.exp(-dt / 1.05) * smooth(dt / .09)
            f = f * (1 + .5 * a) + a * np.array([.035, .075, .12], np.float32)
    return f


# ---------------------------------------------------------------- finishing
_title = None


def title_layer(f, t):
    global _title
    t0, t1 = SHOTS[0].extra['title']
    if not (t0 < t < t1):
        return f
    if _title is None:
        font = ImageFont.truetype(FONT_TITLE, 40)
        text = 'The Moment You Saw Me'
        track = 5
        w = int(sum(font.getlength(c) + track for c in text)) + 20
        im = Image.new('L', (w, 80), 0)
        dr = ImageDraw.Draw(im)
        x = 10
        for c in text:
            dr.text((x, 12), c, font=font, fill=255)
            x += font.getlength(c) + track
        _title = np.asarray(im, np.float32) / 255
    a = smooth((t - t0) / 1.4) * smooth((t1 - t) / 1.4) * .78
    h, w = _title.shape
    x0, y0 = (W - w) // 2, 1180
    m = (_title * a)[..., None]
    f[y0:y0 + h, x0:x0 + w] = f[y0:y0 + h, x0:x0 + w] * (1 - m) + np.array([.86, .90, .93], np.float32) * m
    return f


def gap_hold(t):
    """0..1 inside the half second where the band stops."""
    for g0, g1 in (GAP1, GAP2):
        if g0 - .12 <= t < g1:
            return smooth((t - (g0 - .12)) / .2)
    return 0.0


def finish(f, t, n):
    g = gap_hold(t)
    if g:
        luma = f.mean(2, keepdims=True)
        f = (luma + (f - luma) * (1 - .35 * g)) * (1 - .14 * g)
    small = cv2.resize(f, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    hal = cv2.GaussianBlur(np.clip(small - .8, 0, 1), (0, 0), 7)
    f = f + cv2.resize(hal, (W, H), interpolation=cv2.INTER_LINEAR) * np.array([.10, .22, .46], np.float32)
    f = f * .965 + .018
    luma = f.mean(2, keepdims=True)
    f = (luma + (f - luma) * SAT) * VIG
    r = np.random.default_rng(n * 7 + 1)
    gr = cv2.GaussianBlur(r.standard_normal((H // 2 + 1, W // 2 + 1), dtype=np.float32), (0, 0), .7)
    gr = cv2.resize(gr, (W, H), interpolation=cv2.INTER_LINEAR)
    l2 = np.clip(luma[..., 0], 0, 1)
    f = f + (gr * (.030 * (1 - np.abs(l2 - .42) * 1.25)))[..., None]
    return np.clip(f, 0, 1)


def frame(i, n):
    sh = SHOTS[i]
    t = n / FPS
    f = layer(sh, t)
    if sh.dis and t < sh.t0 + sh.dis:
        a = smooth((t - sh.t0) / sh.dis)
        f = layer(SHOTS[i - 1], t) * (1 - a) + f * a
    env = 1.0
    if sh.fade_in:
        env = min(env, smooth((t - .35) / sh.fade_in))
    if sh.fade_out:
        env = min(env, smooth((sh.extra['end'] - t) / sh.fade_out))
    f = finish(f * env, t, n)
    if i == 0:
        f = title_layer(f, t)
    return f


def bgr8(f):
    return (np.clip(f, 0, 1) * 255 + .5).astype(np.uint8)


def render_shot(i):
    sh = SHOTS[i]
    os.makedirs(SEG, exist_ok=True)
    n0, n1 = round(sh.t0 * FPS), round(sh.t1 * FPS)
    out = f'{SEG}/{sh.id}.mkv'
    tmp = f'{SEG}/{sh.id}.tmp.mkv'
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '13', '-pix_fmt', 'yuv420p', '-threads', '2', tmp], stdin=subprocess.PIPE)
    for n in range(n0, n1):
        ff.stdin.write(bgr8(frame(i, n)).tobytes())
    ff.stdin.close()
    ff.wait()
    os.replace(tmp, out)
    print(sh.id, sh.kf, n1 - n0, 'frames', flush=True)


if __name__ == '__main__':
    mode = sys.argv[2]
    if mode == '--preview':
        os.makedirs(PREV, exist_ok=True)
        for x in sys.argv[3].split(','):
            t = float(x)
            n = round(t * FPS)
            i = next(k for k, s in enumerate(SHOTS) if round(s.t0 * FPS) <= n < round(s.t1 * FPS))
            ok, b = cv2.imencode('.jpg', bgr8(frame(i, n)), [cv2.IMWRITE_JPEG_QUALITY, 90])
            b.tofile(f'{PREV}/p_{t:07.2f}.jpg')
            print(x, SHOTS[i].id, SHOTS[i].kf, flush=True)
    elif mode == '--worker':
        render_shot(int(sys.argv[3]))
    elif mode == '--shots':
        want = sys.argv[3].split(',')
        for k in [k for k, s in enumerate(SHOTS) if s.id in want]:
            render_shot(k)
    elif mode == '--all':
        workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
        todo = [k for k, s in enumerate(SHOTS) if not os.path.exists(f'{SEG}/{s.id}.mkv')]
        # longest shots first so the pool drains evenly
        todo.sort(key=lambda k: SHOTS[k].t0 - SHOTS[k].t1)
        print('to render', len(todo), 'of', len(SHOTS), flush=True)
        procs = []
        while todo or procs:
            while todo and len(procs) < workers:
                procs.append(subprocess.Popen([sys.executable, __file__, PYLIBS, '--worker', str(todo.pop(0))]))
            procs[0].wait()
            procs = [p for p in procs if p.poll() is None]
        print('done', TOTAL)
