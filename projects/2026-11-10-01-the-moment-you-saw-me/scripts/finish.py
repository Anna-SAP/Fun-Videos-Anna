#!/usr/bin/env python3
"""Join the rendered shots and lay the original song under them, untouched.

  finish.py SONG.m4a OUT.mp4 [video kbps] [segment folder]

The song's AAC stream is copied bit for bit: no gain, no normalising, no re-encode, no time offset. ffmpeg
reports "start: 0.0595" for the source, but that is only the encoder priming, which the container already
skips: sample 0 of the decoded song is at t = 0, the clock every cut was measured on. (An earlier build
subtracted that 59.5 ms and put the sound 1.4 frames early; work/qc checks caught it.)
Video: two-pass x264 from the high-quality shot files, because film grain and rain are expensive.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timeline import SHOTS, TOTAL  # noqa: E402

song, out = sys.argv[1], sys.argv[2]
kbps = sys.argv[3] if len(sys.argv) > 3 else '7000'
seg = sys.argv[4] if len(sys.argv) > 4 else 'work/segments'


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, errors='replace')


lst = f'{seg}/list.txt'
with open(lst, 'w', encoding='utf-8') as f:
    for s in SHOTS:
        f.write(f"file '{s.id}.mkv'\n")
base = ['ffmpeg', '-hide_banner', '-y', '-f', 'concat', '-safe', '0', '-i', lst]
enc = ['-c:v', 'libx264', '-preset', 'slow', '-b:v', f'{kbps}k', '-maxrate', f'{int(kbps) * 2}k', '-bufsize', f'{int(kbps) * 4}k',
       '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-tune', 'grain', '-threads', '12', '-r', '24',
       '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709']
log = f'{seg}/x264pass'
r = run(base + enc + ['-pass', '1', '-passlogfile', log, '-an', '-f', 'null', '-'])
if r.returncode:
    print(r.stderr[-800:])
    sys.exit(1)
r = run(base + ['-i', song] + enc +
        ['-pass', '2', '-passlogfile', log, '-map', '0:v', '-map', '1:a', '-c:a', 'copy', '-t', f'{TOTAL}',
         '-map_chapters', '-1', '-movflags', '+faststart', '-metadata', 'title=The Moment You Saw Me', out])
if r.returncode:
    print(r.stderr[-800:])
    sys.exit(1)
print('wrote', out, round(os.path.getsize(out) / 1e6, 1), 'MB')
