#!/usr/bin/env python3
"""Depth maps for every keyframe that lacks one.   run_depth.py MODEL.onnx PYLIBS [ID ...]"""
import glob
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

model, pylibs = sys.argv[1:3]
want = sys.argv[3:]
here = os.path.dirname(os.path.abspath(__file__))
ids = [os.path.basename(p)[:-4] for p in sorted(glob.glob('work/keyframes/K??.png'))]
ids = [k for k in ids if (k in want if want else not os.path.exists(f'work/depth/{k}.png'))]


def run(k):
    return subprocess.run([sys.executable, '-I', f'{here}/depth.py', model, pylibs, f'work/keyframes/{k}.png', f'work/depth/{k}.png'],
                          capture_output=True, text=True).stdout.strip()


with ThreadPoolExecutor(6) as ex:
    for r in ex.map(run, ids):
        print(r)
