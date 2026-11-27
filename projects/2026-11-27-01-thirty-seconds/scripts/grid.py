#!/usr/bin/env python3
"""Beat grid for the song: librosa beat tracking with a tight tempo prior, then a least-squares straight-line
fit (constant tempo) and the residual of every tracked beat against it, so drift shows up as a trend.

  grid.py MIX22K.wav OUT.json [BPM_PRIOR=134.6]
"""
import json
import sys

import librosa
import numpy as np

src, out = sys.argv[1:3]
prior = float(sys.argv[3]) if len(sys.argv) > 3 else 134.6
y, sr = librosa.load(src, sr=22050, mono=True)
HOP = 128
oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP, aggregate=np.median)
tempo, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=sr, hop_length=HOP, start_bpm=prior,
                                       tightness=400, units='time')
beats = np.asarray(beats)
print('librosa tempo', tempo, 'n beats', len(beats), 'first', beats[:4].round(3))
# straight-line fit over the beats from 10 s on (intro may be loose)
k = np.arange(len(beats))
m = beats > 5
A = np.vstack([k[m], np.ones(m.sum())]).T
(per, off), *_ = np.linalg.lstsq(A, beats[m], rcond=None)
res = beats - (k * per + off)
print(f'fit period {per:.5f}s = {60 / per:.3f} BPM, beat0 at {off:.3f}s')
for a in range(0, len(beats), 32):
    sl = slice(a, a + 32)
    print(f'  beats {a:3d}-{a + 31:3d} t={beats[a]:7.2f}  resid mean {res[sl].mean() * 1000:+6.1f} ms  sd {res[sl].std() * 1000:5.1f} ms')
# local tempo per 16-beat window
loc = []
for a in range(0, len(beats) - 16, 16):
    p = np.polyfit(np.arange(16), beats[a:a + 16], 1)[0]
    loc.append(round(60 / p, 2))
print('local BPM per 16 beats', loc)
json.dump({'beats': beats.round(4).tolist(), 'period': per, 'beat0': off}, open(out, 'w'))
