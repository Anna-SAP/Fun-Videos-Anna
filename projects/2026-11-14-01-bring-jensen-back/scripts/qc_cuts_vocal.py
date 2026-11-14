#!/usr/bin/env python3
"""Where do the hard cuts land? On the beat grid, or on a sung unit / vocal chop?

  qc_cuts_vocal.py FILM [SCENE_THRESHOLD]

In this film a cut is meant to sit either on the 96 BPM grid (bar lines, beats) or on the moment a word is
sung (hook pickups, call and response, the 17 vocal chops). For each cut found by ffmpeg's scene detector this
prints the distance in frames to the nearest beat and to the nearest sung-unit start / chop onset, and a
summary of how many cuts are within 2 frames of either.
"""
import json
import re
import subprocess
import sys

sys.path.insert(0, 'scripts')
from common import BEAT, FPS, T0  # noqa: E402

film = sys.argv[1]
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.30
r = subprocess.run(['ffmpeg', '-hide_banner', '-i', film, '-vf', f"select='gt(scene,{thr})',showinfo", '-an', '-f', 'null', '-'],
                   capture_output=True, text=True, errors='replace')
cuts = [float(m) for m in re.findall(r'pts_time:([\d.]+)', r.stderr)]
units = sorted(u['s'] for e in json.load(open('work/audio/lyric_timing.json')) for u in e['units'])
chops = json.load(open('work/audio/chop_onsets.json'))
vocal = sorted(units + chops)
on_beat = on_voc = 0
for c in cuts:
    k = round((c - T0) / BEAT)
    db = (c - (T0 + k * BEAT)) * FPS
    dv = min((c - v) * FPS for v in vocal if abs(c - v) < 2) if any(abs(c - v) < 2 for v in vocal) else 99
    dv = min(((c - v) * FPS for v in vocal), key=abs)
    tag = 'beat' if abs(db) <= 2 else ('vocal' if abs(dv) <= 3 else '-')
    on_beat += tag == 'beat'
    on_voc += tag == 'vocal'
    print(f'{c:8.3f}s  beat {db:+5.1f} f   sung {dv:+5.1f} f   {tag}')
print(f'{len(cuts)} hard cuts: {on_beat} within 2 frames of a beat, {on_voc} more within 3 frames of a sung unit / chop, '
      f'{len(cuts) - on_beat - on_voc} neither')
