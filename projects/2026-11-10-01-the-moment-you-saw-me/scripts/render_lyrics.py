#!/usr/bin/env python3
"""The lyric version: the same shots as render.py, seen through a fogged pane with the lyrics written on it.

  render_lyrics.py PYLIBS --preview 17.3,56.3     write preview frames to work/preview_lyrics/
  render_lyrics.py PYLIBS --shots s01,s02         render only these shots to work/segments_lyrics/
  render_lyrics.py PYLIBS --all [N]               render every missing shot with N workers

The picture pipeline (depth parallax, rain, light) is render.py's, untouched. glass.py goes between the
camera and the film finish, so grain, halation and vignette sit on top of the glass like a real lens would.
"""
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R  # noqa: E402  (reads PYLIBS from argv[1])
import cv2  # noqa: E402
import glass  # noqa: E402
from timeline import FPS, H, SHOTS, TOTAL, W  # noqa: E402

SEG, PREV = 'work/segments_lyrics', 'work/preview_lyrics'
G = None


def frame(i, n):
    global G
    if G is None:
        G = glass.Glass()
    sh = SHOTS[i]
    t = n / FPS
    f = R.layer(sh, t)
    if sh.dis and t < sh.t0 + sh.dis:
        a = R.smooth((t - sh.t0) / sh.dis)
        f = R.layer(SHOTS[i - 1], t) * (1 - a) + f * a
    f = G.apply(f, t, sh)
    env = 1.0
    if sh.fade_in:
        env = min(env, R.smooth((t - .35) / sh.fade_in))
    if sh.fade_out:
        env = min(env, R.smooth((sh.extra['end'] - t) / sh.fade_out))
    return R.finish(f * env, t, n)


def render_shot(i):
    sh = SHOTS[i]
    os.makedirs(SEG, exist_ok=True)
    n0, n1 = round(sh.t0 * FPS), round(sh.t1 * FPS)
    out, tmp = f'{SEG}/{sh.id}.mkv', f'{SEG}/{sh.id}.tmp.mkv'
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '13', '-pix_fmt', 'yuv420p', '-threads', '2', tmp], stdin=subprocess.PIPE)
    for n in range(n0, n1):
        ff.stdin.write(R.bgr8(frame(i, n)).tobytes())
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
            ok, b = cv2.imencode('.jpg', R.bgr8(frame(i, n)), [cv2.IMWRITE_JPEG_QUALITY, 90])
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
        todo.sort(key=lambda k: SHOTS[k].t0 - SHOTS[k].t1)
        print('to render', len(todo), 'of', len(SHOTS), flush=True)
        procs = []
        while todo or procs:
            while todo and len(procs) < workers:
                procs.append(subprocess.Popen([sys.executable, __file__, sys.argv[1], '--worker', str(todo.pop(0))]))
            procs[0].wait()
            procs = [p for p in procs if p.poll() is None]
        print('done', TOTAL)
