#!/usr/bin/env python3
"""Compose and render the film.

  render.py --preview 12.5,43.0,...  [--tag NAME]     stills into work/preview/
  render.py --seg K                                   render segment K (10 s each) to work/segments/segK.mkv
  render.py --all [--jobs 4]                          render every missing segment in parallel
"""
import argparse
import math
import os
import subprocess
import sys

import cv2
import numpy as np
import skia

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disc as D          # noqa: E402
import scenes as S        # noqa: E402
import score              # noqa: E402
import water              # noqa: E402
from kit import *         # noqa: E402,F401,F403

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEG = 10.0
SEC = score.SEC
G = score.grid


# ---- timeline of the camera and of "are we inside the memory or looking at the record" ----------------------
def obj_at(t):
    """1 = the record is an object on the turntable, 0 = we are inside a place"""
    return kf(t, [(0, 1), (SEC['title'][0], 1), (SEC['title'][0] + 3.6, 0), (G(10) - 1.35, 0), (G(10), 1), (G(14) - 0.45, 1), (G(14) + 0.75, 0),
                  (G(20) - 0.95, 0), (G(20), 1)])


def macro_at(t):
    return bump(t, G(20) - 0.95, G(20) + 0.1, G(22) - 0.5, G(22) + 0.55)


def cam_at(t):
    z = kf(t, [(0, 0.78), (SEC['title'][0], 0.78), (SEC['title'][0] + 4.5, 1.0), (G(8), 1.07), (G(10) - 1.9, 0.92), (G(10), 0.78),
               (G(14) - 0.45, 0.78), (G(14) + 0.9, 1.0), (G(15), 1.04), (G(15) + 0.01, 0.94), (G(16), 0.98), (G(16) + 0.01, 0.96), (G(18), 1.0),
               (G(20) - 1.0, 0.93), (G(20), 0.78)])
    cy = kf(t, [(0, 850), (SEC['title'][0], 850), (SEC['title'][0] + 4.5, 830), (G(10) - 1.9, 830), (G(10), 850), (G(14) - 0.45, 850), (G(14) + 0.9, 830),
                (G(20) - 1.0, 830), (G(20), 850)])
    # a breath on every bar in the choruses
    if SEC['ch1'][0] <= t < SEC['ch1'][1] or G(22) <= t < SEC['ch2'][1]:
        z *= 1 + 0.010 * score.pulse(t, 4, 3.0)
    m = macro_at(t)
    if m > 0:
        z = lerp(z, 1.55, m)
        cy = lerp(cy, 420, m)
    return D.Cam(z, 540, cy)


PLACES = (('v1', '五角场'), ('pre1', '五角场'), ('home', '周浦'), ('dinner', '松江'), ('track', '青浦万达茂'), ('pre2', '青浦万达茂'))


def scene_at(t):
    """-> (painter, style, painter_next, style_next, iris radius of the next scene or None)"""
    if t < G(14) - 2:
        return S.wujiaochang, S.STYLES['night'], None, None, None
    if t < G(15) - 0.12:
        return S.home, S.STYLES['home'], None, None, None
    if t < G(15) + 0.5:
        return S.home, S.STYLES['home'], S.dinner, S.STYLES['dinner'], (t - (G(15) - 0.12)) / 0.62
    if t < G(16) - 0.12:
        return S.dinner, S.STYLES['dinner'], None, None, None
    if t < G(16) + 0.5:
        return S.dinner, S.STYLES['dinner'], S.track, S.STYLES['track'], (t - (G(16) - 0.12)) / 0.62
    tp = SEC['pre2'][0]
    return S.track, S.blend(S.STYLES['track'], S.STYLES['park'], ramp(t, tp - 0.3, tp + 2.0)), None, None, None


def draw_scene(cv, cam, fn, t, extra_scale=1.0):
    cv.save()
    cam.apply(cv)
    if fn is S.dinner:
        cv.scale(0.86, 0.86)
    fn(cv, t, {})
    cv.restore()


def place_tag(cv, t, st, alpha):
    name = None
    for k, nm in PLACES:
        a, b = SEC[k]
        if a <= t < b:
            name = nm
            a0 = SEC['v1'][0] - 3.5 if k == 'v1' else a
            al = ramp(t, a0 + 0.3, a0 + 0.9) * (1 - ramp(t, b - 0.5, b - 0.1) if k in ('pre1', 'home', 'dinner', 'pre2') else 1)
            if k == 'pre1' or k == 'pre2':
                al = 1 - ramp(t, b - 1.6, b - 1.0)
    if t >= SEC['v1'][0] - 3.5 and t < SEC['v1'][0]:
        name, al = '五角场', ramp(t, SEC['v1'][0] - 3.2, SEC['v1'][0] - 2.6)
    if not name or alpha * al <= 0.01:
        return
    a = alpha * al
    w = text_w(name, SERIF_M, 34, 0.12)
    x = W - 70
    if st.get('halo'):
        text(cv, name, x, 150, SERIF_M, 34, paint(st['halo'][0], st['halo'][1] * a, blur=st['halo'][2]), align='r', track=0.12)
    text(cv, name, x, 150, SERIF_M, 34, paint(st['ui'], 0.95 * a), align='r', track=0.12)
    cv.drawCircle(x - w - 26, 150, 9, paint(st['ui'], 0.9 * a, stroke=2.4))
    cv.drawCircle(x - w - 26, 150, 2.6, paint(st['ui'], 0.9 * a))


def title_card(cv, t, st):
    a0 = SEC['title'][0]
    al = ramp(t, a0 + 0.25, a0 + 1.0) * (1 - ramp(t, a0 + 5.2, a0 + 6.0))
    if al <= 0.01:
        return
    y = 250
    for k, ch in enumerate('兜一圈'):
        u = ease_out(clamp((t - (a0 + 0.25 + k * score.beat_time(16) * 0 + k * 0.27)) / 0.6))
        if u <= 0:
            continue
        x = 540 + (k - 1) * 190
        if st.get('halo'):
            glyph(cv, ch, x, y + 24 * (1 - u), SERIF_K, 150, paint(st['halo'][0], st['halo'][1] * al * u, blur=14))
        glyph(cv, ch, x, y + 24 * (1 - u), SERIF_K, 150, paint(st['ink'], al * u))
    a2 = al * ramp(t, a0 + 1.2, a0 + 1.9)
    if st.get('halo'):
        text(cv, '万达入沪二十载', 540, y + 128, SERIF_M, 40, paint(st['halo'][0], st['halo'][1] * a2, blur=8), track=0.42)
    text(cv, '万达入沪二十载', 540, y + 128, SERIF_M, 40, paint(st['ink'], a2), track=0.42)
    text(cv, '2006 — 2026', 540, y + 188, PLAY_I, 36, paint(st['ink'], 0.8 * a2), track=0.10)


def main_part(cv, t):
    """everything up to the bridge: places seen through the record, and the record as an object"""
    cam = cam_at(t)
    obj = obj_at(t)
    fn, st_s, fn2, st2, iris2 = scene_at(t)
    if fn2 is not None:
        st_s = S.blend(st_s, st2, smooth(iris2))
    st = S.blend(st_s, S.STYLES['obj'], smooth(obj))
    cx, cy = cam.pt(0, 0)
    psi = score.ride_rot(t)
    if obj > 0:
        cv.save()
        cv.rotate(-math.degrees(psi), cx, cy)
        S.deck(cv, t, {'cam': cam}, 'A')
        cv.restore()
    if obj < 1:
        rc = D.RL * (1800.0 / D.RL) ** (1 - smoother(obj))
        cv.save()
        if obj > 0:
            clip = skia.Path()
            clip.addCircle(cx, cy, rc * cam.z)
            cv.clipPath(clip, True)
        draw_scene(cv, cam, fn, t)
        if fn2 is not None:
            r2 = 1500 * ease_in(clamp(iris2), 2) * cam.z
            cv.save()
            c2 = skia.Path()
            c2.addCircle(cx, cy, r2)
            cv.clipPath(c2, True)
            draw_scene(cv, cam, fn2, t)
            cv.restore()
            cv.drawCircle(cx, cy, r2, paint('#ffffff', 0.9 * (1 - clamp(iris2)), stroke=5))
            cv.drawCircle(cx, cy, r2, paint('#ffffff', 0.35 * (1 - clamp(iris2)), stroke=22, blur=12))
        cv.restore()
        if obj > 0:
            cv.drawCircle(cx, cy, rc * cam.z, paint('#ffffff', 0.9 * min(1, obj * 6), stroke=3.0))
    D.body(cv, cam, obj, st, score.rings_done(t), t, sheen_rot=-math.degrees(psi))
    la = ramp(obj, 0.86, 1.0)
    if la > 0:
        S.label(cv, cam, t, 'A', kid=ramp(t, G(20), G(20) + 0.1), alpha=la, rot=-psi)
    D.spindle(cv, cam, st)
    D.quan_rings(cv, cam, t, st)
    D.draw_lines(cv, cam, t, st)
    # tonearm
    ta = ramp(obj, 0.35, 0.9) * (1 - macro_at(t))
    if ta > 0:
        lift = 1 - ramp(obj, 0.75, 1.0)
        if t < 3:
            lift = 1 - ramp(t, -0.4, score.NEEDLE_DOWN)
        rs = D.ring_r(max(1.0, score.rings_done(t) + 1)) if t > 3 else lerp(D.R + 40, D.ring_r(1), ramp(t, -0.8, score.NEEDLE_DOWN - 0.05))
        D.tonearm(cv, cam, rs, lift, st, ta)
    if t < 2.5:   # the needle lands: a ring of light
        u = (t - score.NEEDLE_DOWN) / 1.4
        if 0 < u < 1:
            sx, sy = D.stylus_at(D.ring_r(1))
            X, Y = cam.pt(sx, sy)
            cv.drawCircle(X, Y, 10 + 150 * ease_out(u), paint('#ffffff', 0.9 * (1 - u), stroke=3))
    D.counter(cv, t, st, alpha=1.0)
    place_tag(cv, t, st, 1 - smooth(obj))
    if SEC['title'][0] <= t < SEC['v1'][0]:
        title_card(cv, t, st)
    if t < 9:
        D.said(cv, score.LINES[0], t, 540, 1490, st, size=62, hold=1.0)
    return st


def frame(t):
    arr = np.zeros((H, W, 4), np.uint8)
    surf = skia.Surface(arr)
    cv = surf.getCanvas()
    if t < SEC['bridge'][0] - 1.2:
        st = main_part(cv, t)
    else:
        st = water.late_part(cv, t, main_part)
    surf.flushAndSubmit()
    return post(arr, st, t)


# ---- finishing: bloom, vignette, grain ---------------------------------------------------------------------
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_VIG = np.clip(1 - (((_xx - W / 2) / (W * 0.95)) ** 2 + ((_yy - H / 2) / (H * 0.80)) ** 2) * 1.0, 0, 1)
_VIG = cv2.merge([(_VIG * 255).astype(np.uint8)] * 3)
_gr = np.random.default_rng(1)
_GRAIN = [cv2.merge([np.clip(128 + cv2.GaussianBlur(_gr.normal(0, 46, (H, W)).astype(np.float32), (0, 0), 0.7), 0, 255).astype(np.uint8)] * 3) for _ in range(6)]


def post(arr, st, t):
    img = arr[:, :, :3]
    b = st.get('bloom', 0.1)
    if b > 0.01:
        sm = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        br = cv2.subtract(sm, (170, 170, 170, 0))
        br = cv2.GaussianBlur(br, (0, 0), 9)
        up = cv2.resize(br, (W, H), interpolation=cv2.INTER_LINEAR)
        img = cv2.addWeighted(img, 1.0, up, b * 2.4, 0)
    v = st.get('vig', 0.1)
    if v > 0.01:
        dark = cv2.multiply(img, _VIG, scale=1 / 255.0)
        img = cv2.addWeighted(img, 1 - v * 1.6, dark, v * 1.6, 0)
    g = st.get('grain', 0.03)
    if g > 0:
        n = _GRAIN[int(t * 30) % len(_GRAIN)]
        img = cv2.addWeighted(img, 1.0, n, g * 2.0, -128 * g * 2.0)
    return img


def render_seg(k):
    os.makedirs(os.path.join(ROOT, 'work', 'segments'), exist_ok=True)
    f0 = int(round(k * SEG * FPS))
    f1 = min(score.NFRAMES, int(round((k + 1) * SEG * FPS)))
    out = os.path.join(ROOT, 'work', 'segments', f'seg{k:02d}.mkv')
    tmp = out + '.part.mkv'
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '12', '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
    for f in range(f0, f1):
        ff.stdin.write(np.ascontiguousarray(frame(f / FPS)).tobytes())
    ff.stdin.close()
    ff.wait()
    os.replace(tmp, out)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    ap.add_argument('--tag', default='p')
    ap.add_argument('--seg', type=int)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--jobs', type=int, default=4)
    a = ap.parse_args()
    nseg = int(math.ceil(score.NFRAMES / (SEG * FPS)))
    if a.preview:
        from PIL import Image
        os.makedirs(os.path.join(ROOT, 'work', 'preview'), exist_ok=True)
        import time
        for s in a.preview.split(','):
            t = float(s)
            t0 = time.time()
            im = frame(t)
            Image.fromarray(im).save(os.path.join(ROOT, 'work', 'preview', f'{a.tag}_{t:07.2f}.png'))
            print(f'{t:.2f} {time.time() - t0:.2f}s', flush=True)
    elif a.seg is not None:
        print(render_seg(a.seg))
    elif a.all:
        todo = [k for k in range(nseg) if not os.path.exists(os.path.join(ROOT, 'work', 'segments', f'seg{k:02d}.mkv'))]
        procs = []
        import time
        while todo or procs:
            procs = [p for p in procs if p.poll() is None]
            while todo and len(procs) < a.jobs:
                k = todo.pop(0)
                procs.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), '--seg', str(k)]))
            time.sleep(1.0)
        print('done')
