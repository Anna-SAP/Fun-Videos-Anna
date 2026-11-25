#!/usr/bin/env python3
"""For every line: where the vocal stem's level actually rises after the gap before the phrase, next to the
merged estimate of the first character; and where it falls after the last one.  qc_starts.py TIMING.json"""
import json, sys
import numpy as np
from scipy.io import wavfile
sr, v = wavfile.read('work/audio/voc22k.wav'); v = v.astype(np.float32) / 32768
H = 220
env = np.array([np.sqrt((v[i:i + 2 * H] ** 2).mean()) for i in range(0, len(v) - 2 * H, H)])
db = 20 * np.log10(env + 1e-6); dt = H / sr
T = json.load(open(sys.argv[1]))
for i in range(len(T)):
    ts = T[str(i)]['t']
    a = int((ts[0] - 1.0) / dt); b = int((ts[0] + 0.5) / dt)
    seg = db[a:b]
    quiet = seg < -40
    on = None
    for j in range(len(seg) - 1, 5, -1):       # last quiet->loud crossing before est+0.5 that follows >=0.12 s of quiet
        if seg[j] >= -36 and quiet[max(0, j - 14):j - 1].mean() > 0.8:
            on = (a + j) * dt; break
    c = int((ts[-1]) / dt)
    off = None
    for j in range(c + 8, c + 400):
        if (db[j:j + 12] < -40).all():
            off = j * dt; break
    prof = ' '.join(f'{db[int((ts[0] + o) / dt)]:4.0f}' for o in (-0.5, -0.4, -0.3, -0.2, -0.1, 0, 0.1, 0.2))
    print(f"L{i:2d} first {ts[0]:7.2f}  level-rise {on if on is None else round(on, 2)}  d {'' if on is None else round(on - ts[0], 2)}   last {ts[-1]:7.2f} voice-ends {off if off is None else round(off, 2)}   dB@-.5..+.2: {prof}")
