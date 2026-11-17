#!/usr/bin/env python3
"""Render the film in 10-second segments with N worker processes; resumable.

  render.py [--jobs 4] [--seg 300] [--only 3,4,5] [--preview t1,t2,...] [--force]

Each segment is frames [i*seg, (i+1)*seg) piped as raw RGB into ffmpeg (x264 veryfast CRF 12, yuv420p,
BT.709 tags) -> work/segments/sNNN.mkv. Segments that already exist are skipped unless --force, so a crash
or a design change to one stretch only re-renders what is missing. --preview writes single frames.
"""
import argparse
import os
import subprocess
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))

OUT = 'work/segments'


def seg_path(i):
    return f'{OUT}/s{i:03d}.mkv'


def render_seg(args):
    i, seg, nframes = args
    import mv  # noqa: E402  (each worker builds its own caches)
    from common import FPS, H, W
    a, b = i * seg, min(nframes, (i + 1) * seg)
    tmp = seg_path(i) + '.part.mkv'
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '12', '-pix_fmt', 'yuv420p',
           '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-threads', '1', tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for f in range(a, b):
        im = mv.frame(f / FPS)
        p.stdin.write(im.tobytes())
    p.stdin.close()
    p.wait()
    os.replace(tmp, seg_path(i))
    return i, b - a, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--seg', type=int, default=300)
    ap.add_argument('--only', default=None)
    ap.add_argument('--preview', default=None)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    from common import NFRAMES
    if a.preview:
        import cv2
        import mv
        for s in a.preview.split(','):
            t = float(s)
            im = mv.frame(t)
            cv2.imwrite(f'work/preview/p_{t:07.2f}.jpg', im[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 92])
            print('preview', t)
        return
    os.makedirs(OUT, exist_ok=True)
    nseg = (NFRAMES + a.seg - 1) // a.seg
    todo = [int(x) for x in a.only.split(',')] if a.only else list(range(nseg))
    if not a.force:
        todo = [i for i in todo if not os.path.exists(seg_path(i))]
    print(f'{len(todo)} of {nseg} segments to render', flush=True)
    t0 = time.time()
    with Pool(a.jobs) as pool:
        for i, n, dt in pool.imap_unordered(render_seg, [(i, a.seg, NFRAMES) for i in todo]):
            print(f'segment {i:3d}: {n} frames in {dt:.0f}s ({dt / n:.2f}s/frame)  elapsed {time.time() - t0:.0f}s',
                  flush=True)


if __name__ == '__main__':
    main()
