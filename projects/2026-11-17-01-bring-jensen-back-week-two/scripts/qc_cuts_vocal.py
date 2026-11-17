#!/usr/bin/env python3
"""Where do the hard cuts land? On a tracked beat, or on the moment a line is sung?

  qc_cuts_vocal.py FILM [SCENE_THRESHOLD]

The tempo drifts after the interlude (86.8 -> 84 BPM), so beats come from work/audio/beats.json (dynamic
programming tracker), not from a fixed grid. In this film a cut is meant to sit on a downbeat (section
changes) or just before a sung line (the camera whips to the next line ~0.3 s ahead of its first syllable).
For each cut found by ffmpeg's scene detector this prints the distance in frames to the nearest tracked beat
and to the nearest sung-unit start, and a summary.
"""
import json
import re
import subprocess
import sys

import numpy as np

FPS = 30
film = sys.argv[1]
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.30
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', film, '-vf', f"select='gt(scene,{thr})',showinfo", '-an', '-f', 'null', '-'],
                   capture_output=True, text=True, errors='replace')
cuts = [float(m) for m in re.findall(r'pts_time:([\d.]+)', r.stderr)]
beats = np.array(json.load(open('work/audio/beats.json'))['beats'])
units = np.array(sorted(u['s'] for e in json.load(open('work/audio/lyric_timing.json')) for u in e['units']))
on_beat = on_voc = 0
for c in cuts:
    db = (c - beats[np.argmin(np.abs(beats - c))]) * FPS
    dv = (c - units[np.argmin(np.abs(units - c))]) * FPS
    tag = 'beat' if abs(db) <= 2 else ('sung' if -12 <= dv <= 3 else '-')
    on_beat += tag == 'beat'
    on_voc += tag == 'sung'
    print(f'{c:8.3f}s  beat {db:+5.1f} f   sung {dv:+6.1f} f   {tag}')
print(f'{len(cuts)} hard cuts: {on_beat} within 2 frames of a tracked beat, {on_voc} more within 12 frames before '
      f'(or 3 after) a sung unit, {len(cuts) - on_beat - on_voc} neither')
