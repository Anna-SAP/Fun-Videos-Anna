#!/usr/bin/env python3
"""Timing check sheets: the vocal spectrogram of each line with the final unit starts drawn on it.

  qc_strips.py TIMING.json OUT_PREFIX LINES [PER_IMAGE] [PX_PER_S]

LINES = "24-31" or "0,1,2". Labels are unit positions only (line.unit), never lyric text.
"""
import json
import os
import subprocess
import sys

from PIL import Image

tim, prefix, spec = sys.argv[1:4]
per = int(sys.argv[4]) if len(sys.argv) > 4 else 3
pps = sys.argv[5] if len(sys.argv) > 5 else '300'
want = []
for part in spec.split(','):
    if '-' in part:
        a, b = part.split('-')
        want += list(range(int(a), int(b) + 1))
    else:
        want.append(int(part))
P = [p for p in json.load(open(tim))['perfs'] if p['li'] in want]
here = os.path.dirname(os.path.abspath(__file__))
ims = []
for n, p in enumerate(P):
    us = [(k, u) for k, u in enumerate(p['u']) if u]
    t0, t1 = us[0][1][0] - 0.45, us[-1][1][1] + 0.35
    marks = [[u[0], f"{k}"] for k, u in us]
    json.dump(marks, open('work/qc/_m.json', 'w'))
    out = f'work/qc/_s{n}.png'
    subprocess.run([sys.executable, os.path.join(here, 'vocal_spectrogram.py'), 'work/audio/vocals22k.wav', out, str(t0), str(t1),
                    pps, 'work/qc/_m.json'], check=True, capture_output=True)
    ims.append((p['li'], Image.open(out).convert('RGB')))
for k in range(0, len(ims), per):
    grp = ims[k:k + per]
    w = max(im.width for _, im in grp)
    sheet = Image.new('RGB', (w, sum(im.height for _, im in grp)))
    y = 0
    for li, im in grp:
        sheet.paste(im, (0, y))
        y += im.height
    name = f"{prefix}_{'_'.join(str(li) for li, _ in grp)}.png"
    sheet.save(name)
    print(name, sheet.size)
