#!/usr/bin/env python3
"""Grab the frame at time T from the rendered segments (96 frames each) as a JPEG.
  grab.py T OUT.jpg [WIDTH]"""
import subprocess, sys
t, out = float(sys.argv[1]), sys.argv[2]
w = int(sys.argv[3]) if len(sys.argv) > 3 else 1080
fi = int(round(t * 24))
seg, off = divmod(fi, 96)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f'work/segments/s{seg:03d}.mkv', '-vf',
                f'select=eq(n\\,{off}),scale={w}:-2', '-frames:v', '1', '-q:v', '2', out], check=True)
