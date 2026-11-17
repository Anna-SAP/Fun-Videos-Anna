#!/usr/bin/env python3
"""Grab single frames from the rendered segments by song time.  grab.py OUT_DIR W T1 [T2 ...]"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import FPS  # noqa: E402

out, w = sys.argv[1], int(sys.argv[2])
os.makedirs(out, exist_ok=True)
for a in sys.argv[3:]:
    t = float(a)
    f = int(round(t * FPS))
    seg, k = divmod(f, 300)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'work/segments/s{seg:03d}.mkv', '-vf',
                    f"select=eq(n\\,{k}),scale={w}:-2", '-frames:v', '1', '-q:v', '2', f'{out}/g_{t:07.2f}.jpg'], check=True)
    print(f'{out}/g_{t:07.2f}.jpg')
