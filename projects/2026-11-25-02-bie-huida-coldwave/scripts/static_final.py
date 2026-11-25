#!/usr/bin/env python3
"""Final STATIC list. Two kinds were found by reading noise_floor.png, static_excess.py and zoomed strips:
  burst - a loud wideband noise hit held >= 0.6 s (flatness >= 0.36), always on a section head;
  bed   - a quiet noise bed (crackle) that is exposed whenever the drum machine drops out.
Rough times come from those reads; here each onset is refined to 10 ms on the instrumental stem:
burst onset = first frame whose 1-10.5 kHz energy is within 3 dB of the event max (search -0.35..+0.35 s);
bed onset = first frame after the band cut where the 0.2 s flatness exceeds 0.3. Writes work/audio/static_list.json.
"""
import json
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft
from scipy.ndimage import uniform_filter1d
sr, x = wavfile.read('work/audio/inst22k.wav'); x = x.astype(np.float32) / 32768
HOP = 220; fps = sr / HOP
f, t, Z = stft(x, sr, nperseg=1024, noverlap=1024 - HOP, boundary=None, padded=False)
P = np.abs(Z) ** 2 + 1e-12
b = (f >= 1000) & (f < 10500)
wide = 10 * np.log10(P[b].sum(0))
flat = uniform_filter1d(np.exp(np.log(P[b]).mean(0)) / P[b].mean(0), 20)
low = 10 * np.log10(P[(f >= 30) & (f < 150)].sum(0))
ROUGH = [('bed', 2.9), ('burst', 16.94), ('burst', 25.52), ('bed', 54.1), ('burst', 56.2), ('burst', 81.92),
         ('bed', 102.75), ('burst', 120.3), ('bed', 137.35), ('burst', 138.38), ('burst', 155.3), ('burst', 199.66),
         ('burst', 223.84), ('bed', 243.45), ('burst', 258.44)]
out = []
for kind, tr in ROUGH:
    a, e = int((tr - 0.35) * fps), int((tr + 0.35) * fps)
    if kind == 'burst':
        seg = wide[a:e]; on = a + int(np.argmax(seg >= seg.max() - 3))
        pk = a + int(np.argmax(seg))
        hold = int(np.argmax(wide[pk:pk + int(3 * fps)] < wide[pk] - 10)) / fps
        out.append({'kind': kind, 't': round(on / fps, 2), 'peak_db': round(float(wide[pk]), 1),
                    'held_s': round(hold, 2), 'flat': round(float(flat[pk:pk + int(0.5 * fps)].mean()), 2)})
    else:
        seg = flat[a:e]; on = a + int(np.argmax(seg > 0.3)) if (seg > 0.3).any() else int(tr * fps)
        # bed lasts while the kick/bass band stays down
        e2 = on
        while e2 < len(low) - 1 and low[e2] < -45: e2 += 1
        out.append({'kind': kind, 't': round(on / fps, 2), 'until': round(e2 / fps, 2),
                    'level_db': round(float(wide[on:e2].mean()) if e2 > on else float(wide[on]), 1),
                    'flat': round(float(flat[on:max(e2, on + 1)].mean()), 2)})
json.dump(out, open('work/audio/static_list.json', 'w'), indent=1)
for o in out: print(o)
