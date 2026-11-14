#!/usr/bin/env python3
"""Join rendered shot files and lay the original song under them, untouched.

  finish.py SONG OUT.mp4 SEGMENT_DIR [--kbps 7000] [--fps 24] [--total SECONDS] [--order s01,s02,...]
            [--share] [--title "Song title"]

SEGMENT_DIR holds one video file per shot (*.mkv). They are joined in name order unless --order is given.
The song's audio stream is copied bit for bit: no gain, no normalising, no re-encode, no time offset.
--total trims the result to the song's length (give the song's duration in seconds).
--share makes a small copy for messaging apps: 1600 kbps unless --kbps is given, with a light denoise first
  so the bitrate goes to the picture and not to film grain. Always encode the share copy from the shot
  files, never from the finished master.

Two things this script does on purpose:
  * no -itsoffset. ffmpeg prints "start: 0.0xx" for AAC sources; that is encoder priming the container
    already skips. Subtracting it puts the sound early by that amount.
  * -map_chapters -1, or a stray chapter data stream from the source rides along into the mp4.
Video is two-pass x264; -tune grain for the master because grain and rain are expensive to encode.
"""
import argparse
import glob
import os
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument('song')
ap.add_argument('out')
ap.add_argument('seg')
ap.add_argument('--kbps', type=int)
ap.add_argument('--fps', default='24')
ap.add_argument('--total', type=float)
ap.add_argument('--order')
ap.add_argument('--share', action='store_true')
ap.add_argument('--title')
ap.add_argument('--threads', default='12')
ap.add_argument('--preset', default='slow')
a = ap.parse_args()

if a.order:
    names = [f'{s}.mkv' for s in a.order.split(',')]
else:
    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(a.seg, '*.mkv')) if '.tmp.' not in p)
missing = [n for n in names if not os.path.exists(os.path.join(a.seg, n))]
if missing or not names:
    sys.exit(f'missing shot files: {missing or "none found"}')
lst = os.path.join(a.seg, 'list.txt')
with open(lst, 'w', encoding='utf-8') as f:
    f.writelines(f"file '{n}'\n" for n in names)

kbps = a.kbps or (1600 if a.share else 7000)
vf = ['-vf', 'hqdn3d=1.5:1.2:5:4'] if a.share else []
tune = [] if a.share else ['-tune', 'grain']
base = ['ffmpeg', '-hide_banner', '-y', '-f', 'concat', '-safe', '0', '-i', lst]
enc = vf + ['-c:v', 'libx264', '-preset', a.preset, '-b:v', f'{kbps}k', '-maxrate', f'{kbps * 2}k', '-bufsize', f'{kbps * 4}k',
            '-pix_fmt', 'yuv420p', '-profile:v', 'high'] + tune + ['-threads', a.threads, '-r', a.fps,
                                                                   '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709']
log = os.path.join(a.seg, 'x264pass_share' if a.share else 'x264pass')


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    if r.returncode:
        sys.exit(r.stderr[-1200:])


run(base + enc + ['-pass', '1', '-passlogfile', log, '-an', '-f', 'null', '-'])
tail = ['-t', f'{a.total}'] if a.total else ['-shortest']
meta = ['-metadata', f'title={a.title}'] if a.title else []
run(base + ['-i', a.song] + enc + ['-pass', '2', '-passlogfile', log, '-map', '0:v', '-map', '1:a', '-c:a', 'copy'] + tail +
    ['-map_chapters', '-1', '-movflags', '+faststart'] + meta + [a.out])
print('wrote', a.out, round(os.path.getsize(a.out) / 1e6, 1), 'MB,', len(names), 'shots,', kbps, 'kbps')
