#!/usr/bin/env python3
"""Render the film.

  render.py --preview 17.2,18.0,...  [--out work/preview]      single frames (PNG) + a contact sheet
  render.py --seg N                                           one 10 s segment -> work/segments/sNNN.mkv
  render.py --all [--jobs 4]                                  every missing segment, in parallel
  render.py --range T0 T1 OUT.mp4                             a quick low-res clip with audio for checking motion
"""
import argparse
import os
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import FPS, H, W, to8  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUR = 266.448          # the mp3's duration (ffmpeg: 00:04:26.45)
NFR = int(round(DUR * FPS))
SEG = 10 * FPS


def get_frame(fi):
    import score
    return to8(score.frame(fi / FPS, fi))


def encode_cmd(out, crf=14, preset='medium', size=None):
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-']
    if size:
        cmd += ['-vf', f'scale={size[0]}:{size[1]}:flags=area']
    cmd += ['-c:v', 'libx264', '-preset', preset, '-crf', str(crf), '-pix_fmt', 'yuv420p', '-colorspace', 'bt709',
            '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv', out]
    return cmd


def render_seg(n):
    out = os.path.join(ROOT, 'work', 'segments', f's{n:03d}.mkv')
    tmp = out + '.part.mkv'
    f0, f1 = n * SEG, min(NFR, (n + 1) * SEG)
    p = subprocess.Popen(encode_cmd(tmp), stdin=subprocess.PIPE)
    t0 = time.time()
    for fi in range(f0, f1):
        p.stdin.write(get_frame(fi).tobytes())
    p.stdin.close()
    p.wait()
    os.replace(tmp, out)
    print(f'seg {n} frames {f0}-{f1} in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    ap.add_argument('--out', default=os.path.join(ROOT, 'work', 'preview'))
    ap.add_argument('--sheet', default=None)
    ap.add_argument('--seg', type=int)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--range', nargs=3)
    ap.add_argument('--only', default=None, help='with --all: comma list / a-b ranges of segments to (re)render')
    a = ap.parse_args()
    nseg = (NFR + SEG - 1) // SEG
    if a.preview:
        os.makedirs(a.out, exist_ok=True)
        ts = [float(x) for x in a.preview.split(',')]
        ims = []
        t0 = time.time()
        for t in ts:
            fi = int(round(t * FPS))
            im = get_frame(fi)
            cv2.imwrite(os.path.join(a.out, f'f{t:07.2f}.png'), im[..., ::-1])
            ims.append(im)
        print(f'{len(ts)} frames, {(time.time() - t0) / len(ts):.2f} s/frame')
        if a.sheet:
            cols = min(len(ims), 6)
            rowsn = (len(ims) + cols - 1) // cols
            tw, th = 360, 640
            sheet = np.zeros((rowsn * (th + 30), cols * tw, 3), np.uint8)
            for k, (t, im) in enumerate(zip(ts, ims)):
                r, c = divmod(k, cols)
                sm = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
                sheet[r * (th + 30) + 30:(r + 1) * (th + 30), c * tw:(c + 1) * tw] = sm
                cv2.putText(sheet, f'{t:.2f}', (c * tw + 6, r * (th + 30) + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.imwrite(a.sheet, sheet[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 88])
    elif a.seg is not None:
        render_seg(a.seg)
    elif a.all:
        todo = list(range(nseg))
        if a.only:
            todo = []
            for part in a.only.split(','):
                if '-' in part:
                    x, y = part.split('-')
                    todo += list(range(int(x), int(y) + 1))
                else:
                    todo.append(int(part))
        else:
            todo = [n for n in todo if not os.path.exists(os.path.join(ROOT, 'work', 'segments', f's{n:03d}.mkv'))]
        procs = []
        for n in todo:
            while len(procs) >= a.jobs:
                procs = [p for p in procs if p.poll() is None]
                time.sleep(0.5)
            procs.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), '--seg', str(n)]))
        for p in procs:
            p.wait()
    elif a.range:
        t0, t1, out = float(a.range[0]), float(a.range[1]), a.range[2]
        tmp = out + '.v.mkv'
        p = subprocess.Popen(encode_cmd(tmp, crf=23, preset='veryfast', size=(540, 960)), stdin=subprocess.PIPE)
        for fi in range(int(round(t0 * FPS)), int(round(t1 * FPS))):
            p.stdin.write(get_frame(fi).tobytes())
        p.stdin.close()
        p.wait()
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-ss', str(t0), '-t', str(t1 - t0), '-i',
                        os.path.join(ROOT, 'work', 'src', 'song.mp3'), '-c:v', 'copy', '-c:a', 'aac', '-shortest', out], check=True)
        os.remove(tmp)
