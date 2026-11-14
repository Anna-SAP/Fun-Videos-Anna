#!/usr/bin/env python3
"""Render the MV: one frame is a pure function of its index, so shots render in parallel and resume.

  render.py --preview 12.3,45.6,...       single frames -> work/preview/p_<t>.jpg
  render.py --all 4                       every missing shot segment -> work/segments/sNNN.mkv (4 processes)
  render.py --shots s012,s013             re-render these segments (delete the old .mkv first)

Frame order: scene (content time, which runs backwards during the record-scratch rewinds) -> things behind
the MC -> the MC -> things in front -> lyric stamps (real time) -> post (kick punch, snare shake / colour
split, flashes, grain, vignette).
"""
import math
import os
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from common import FPS, H, NFRAMES, W, clamp01, grain, to_u8, vignette  # noqa: E402
import timeline as TL  # noqa: E402

_VIG = None


def post(img, t, fi, sh, env):
    fx = sh.fx
    k = env['kick'][fi]
    s = env['snare'][fi]
    # kick punch: scale about the centre
    amp = fx.get('punch', 0.0) * k
    sx = sy = 0.0
    if fx.get('shake', 0.0) > 0 and s > 0.05:
        rng = np.random.default_rng(fi)
        sx, sy = rng.uniform(-1, 1, 2) * fx['shake'] * s
    if amp > 0.002 or abs(sx) + abs(sy) > 0.5:
        sc = 1 + amp
        M = np.array([[sc, 0, (1 - sc) * W / 2 + sx], [0, sc, (1 - sc) * H / 2 + sy]], np.float32)
        img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    split = fx.get('split', 0.0) * s + fx.get('split_k', 0.0) * k + fx.get('split_c', 0.0)
    if split > 0.6:
        d = int(round(split))
        img = img.copy()
        img[:, d:, 0] = img[:, :-d, 0]
        img[:, :-d, 2] = img[:, d:, 2]
    # flashes at the shot's own start (a cut flash) and wherever the score asks
    fl = 0.0
    if fx.get('flash_in'):
        u = t - sh.t0
        fl = max(fl, fx['flash_in'] * max(0.0, 1 - u / 0.12))
    for (ta, strength, dur) in fx.get('flashes', ()):
        if ta <= t < ta + dur:
            fl = max(fl, strength * (1 - (t - ta) / dur))
    if fx.get('strobe'):
        fl = max(fl, fx['strobe'] * s)
    if fl > 0:
        img = img + fl * (1.0 - img) * 0.9
    if fx.get('invert_on') and fx['invert_on'](t):
        img = 1.0 - img
    g = fx.get('grain', 0.045)
    if g:
        img = img + grain(fi, g)[..., None]
    global _VIG
    if _VIG is None:
        _VIG = vignette(0.38)
    img = img * (_VIG if fx.get('vignette', True) else 1)
    lift = fx.get('lift', 0.015)
    img = img * (1 - lift) + lift
    return img


def frame(fi, env):
    t = fi / FPS
    sh = TL.shot_at(t)
    tc = TL.content_time(t)
    img = sh.background(tc, fi, env)
    img = sh.layers(img, tc, t, fi, env)
    img = TL.lyrics_layer(img, t, fi, env, sh)
    img = sh.overlay(img, tc, t, fi, env)
    img = post(img, t, fi, sh, env)
    return np.clip(img, 0, 1)


def load_env():
    d = np.load('work/audio/env.npz')
    env = {}
    for key, tau in (('kick', 4.0), ('snare', 3.0), ('hat', 2.0)):
        on = d[key + '_on']
        val = d[key]
        e = np.zeros(NFRAMES, np.float32)
        for o in on:
            for j in range(o, min(NFRAMES, o + 24)):
                e[j] = max(e[j], min(1.0, val[o]) * math.exp(-(j - o) / tau))
        env[key] = e
    env['vocal'] = d['vocal']
    return env


def render_segment(seg, env):
    out = f'work/segments/{seg.name}.mkv'
    if os.path.exists(out):
        return
    tmp = out.replace('.mkv', '.tmp.mkv')
    f0, f1 = seg.f0, seg.f1
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-c:v', 'libx264',
           '-preset', 'veryfast', '-crf', '13', '-color_primaries', 'bt709', '-color_trc', 'bt709',
           '-colorspace', 'bt709', tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        p.stdin.write(to_u8(frame(fi, env)).tobytes())
    p.stdin.close()
    p.wait()
    os.replace(tmp, out)


def main():
    os.makedirs('work/segments', exist_ok=True)
    os.makedirs('work/preview', exist_ok=True)
    args = sys.argv[1:]
    env = load_env()
    if args and args[0] == '--preview':
        for ts in args[1].split(','):
            t = float(ts)
            fi = int(round(t * FPS))
            t0 = time.time()
            img = frame(fi, env)
            cv2.imwrite(f'work/preview/p_{t:07.2f}.jpg', cv2.cvtColor(to_u8(img), cv2.COLOR_RGB2BGR),
                        [cv2.IMWRITE_JPEG_QUALITY, 90])
            print(f'{t:7.2f}s  {time.time() - t0:.2f}s  shot {TL.shot_at(t).name}', flush=True)
        return
    segs = TL.segments()
    if args and args[0] == '--shots':
        want = set(args[1].split(','))
        segs = [s for s in segs if s.name in want]
        nproc = int(args[2]) if len(args) > 2 else 4
    else:
        nproc = int(args[1]) if len(args) > 1 else 4
    todo = [s for s in segs if not os.path.exists(f'work/segments/{s.name}.mkv')]
    todo.sort(key=lambda s: -(s.f1 - s.f0))
    print(len(todo), 'segments to render,', sum(s.f1 - s.f0 for s in todo), 'frames', flush=True)
    if nproc <= 1:
        for s in todo:
            render_segment(s, env)
            print('done', s.name, flush=True)
        return
    import multiprocessing as mp
    with mp.get_context('fork').Pool(nproc) as pool:
        for name in pool.imap_unordered(_worker, [s.name for s in todo]):
            print('done', name, flush=True)


def _worker(name):
    env = load_env()
    seg = [s for s in TL.segments() if s.name == name][0]
    t0 = time.time()
    render_segment(seg, env)
    return f'{name} ({seg.f1 - seg.f0} frames, {time.time() - t0:.0f}s)'


if __name__ == '__main__':
    main()
