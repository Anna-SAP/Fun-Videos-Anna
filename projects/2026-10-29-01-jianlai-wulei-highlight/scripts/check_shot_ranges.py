#!/usr/bin/env python3
"""Check that no shot in a render script runs into the trailer's next shot.

  check_shot_ranges.py RENDER_SCRIPT TRAILER

Decodes, for every shot in RENDER_SCRIPT's SHOTS table, exactly the source frames it shows
(slow motion, frame blending and a following dissolve included) and flags any hard cut inside
that range. Slow motion is where this bites: a 0.24 s source shot played at 0.4x needs 0.6 s of
source for 1.5 s of output, and the extra frames belong to someone else.
"""
import importlib.util
import subprocess
import sys

import numpy as np

FPS = 25


def main():
    script, trailer = sys.argv[1], sys.argv[2]
    spec = importlib.util.spec_from_file_location('render', script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    shots = mod.SHOTS
    bad = 0
    for k, s in enumerate(shots):
        out_in, out_out, src_in, speed = s[:4]
        if speed == 0:
            continue
        tail = shots[k + 1][8].get('dissolve', 0) if k + 1 < len(shots) else 0
        blend = 0 < speed < 0.9
        # last source time shown, plus the frame it is blended with (or rounded to)
        t_last = src_in + (out_out - out_in + tail - 1 / FPS) * speed + (1 / FPS if blend else 0.5 / FPS)
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{src_in:.3f}', '-i', trailer,
                              '-t', f'{t_last - src_in + 2 / FPS:.3f}', '-an',
                              '-vf', 'scale=96:54,format=gray', '-f', 'rawvideo', '-'],
                             capture_output=True).stdout
        f = np.frombuffer(raw, np.uint8).reshape(-1, 54, 96).astype(np.float32)
        if len(f) < 2:
            continue
        # compare contrast-normalised frames, so flares and flashes don't count as cuts
        g = (f - f.mean((1, 2), keepdims=True)) / (f.std((1, 2), keepdims=True) + 4)
        d = np.abs(np.diff(g, axis=0)).mean((1, 2))
        first = np.ceil(src_in * FPS - 1e-6) / FPS
        cuts = [round(first + (i + 1) / FPS, 2) for i, v in enumerate(d)
                if v > max(4 * np.median(d), 0.45) and first + (i + 1) / FPS <= t_last + 1e-6]
        if cuts:
            bad += 1
        print(f'{out_in:6.2f}-{out_out:6.2f}  source {src_in:7.2f}-{t_last:7.2f}'
              + (f'  CUT at {cuts}' if cuts else '  ok'))
    print('all shots clean' if not bad else f'{bad} shot(s) cross a cut')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
