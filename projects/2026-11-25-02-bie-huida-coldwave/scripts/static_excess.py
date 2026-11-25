#!/usr/bin/env python3
"""STATIC list: wideband noise that the regular drum pattern does not explain.

The snare here is a long noise snare, so plain noise detection fires on every backbeat. Instead the song is cut
into 16th-note slots on the tracked beat grid; for each slot the 1-10.5 kHz energy and spectral flatness are
compared with the median of the same slot in the 4 bars before and after (the pattern the drum machine
repeats). A slot that is >= 6 dB louder than its own pattern and noise-like (flatness >= 0.25) starts an event;
consecutive slots merge. Each event gets onset (refined to 10 ms), duration, excess dB, flatness and decay.

  static_excess.py            -> work/audio/static.json, prints the list
"""
import json
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft

sr, x = wavfile.read('work/audio/mono22k.wav')
x = x.astype(np.float32) / 32768
HOP = 220
f, t, Z = stft(x, sr, nperseg=1024, noverlap=1024 - HOP, boundary=None, padded=False)
P = np.abs(Z) ** 2 + 1e-12
fps = sr / HOP
b = (f >= 1000) & (f < 10500)
hb = (f >= 4000) & (f < 10500)
wide = 10 * np.log10(P[b].sum(0))
high = 10 * np.log10(P[hb].sum(0))
flat = np.exp(np.log(P[b]).mean(0)) / P[b].mean(0)
bj = json.load(open('work/audio/bars.json'))
B = np.array(bj['beats']); bars = bj['bar_idx']
slots = []   # (bar k, slot j, t_start, t_end)
for k, bi in enumerate(bars):
    nb = (bars[k + 1] - bi) if k + 1 < len(bars) else 4
    for q in range(nb):
        if bi + q + 1 >= len(B):
            break
        a, e = B[bi + q], B[bi + q + 1]
        for s in range(4):
            slots.append((k, q * 4 + s, a + (e - a) * s / 4, a + (e - a) * (s + 1) / 4))
E = np.array([wide[int(a * fps):max(int(e * fps), int(a * fps) + 1)].mean() for _, _, a, e in slots])
H = np.array([high[int(a * fps):max(int(e * fps), int(a * fps) + 1)].mean() for _, _, a, e in slots])
F = np.array([flat[int(a * fps):max(int(e * fps), int(a * fps) + 1)].mean() for _, _, a, e in slots])
K = np.array([s[0] for s in slots]); J = np.array([s[1] for s in slots])
ref = np.zeros(len(slots))
for i in range(len(slots)):
    m = (J == J[i]) & (np.abs(K - K[i]) <= 4) & (K != K[i])
    ref[i] = np.median(E[m]) if m.any() else E[i]
ex = E - ref
hit = (ex >= 6) & (F >= 0.25) & (H > np.percentile(H, 20))
events = []
i = 0
while i < len(slots):
    if hit[i]:
        j = i
        while j + 1 < len(slots) and (hit[j + 1] or (ex[j + 1] >= 3 and F[j + 1] >= 0.25)):
            j += 1
        a, e = slots[i][2], slots[j][3]
        # refine onset: first 10 ms frame where wideband rises within 3 dB of the event max
        fa, fe = int((a - 0.08) * fps), int(e * fps)
        seg = wide[fa:fe]
        on = fa + int(np.argmax(seg >= seg.max() - 3))
        # decay: time from max until 12 dB below max (within 2 s)
        pk = fa + int(np.argmax(seg))
        tail = wide[pk:pk + int(2 * fps)]
        dec = int(np.argmax(tail < wide[pk] - 12)) / fps if (tail < wide[pk] - 12).any() else 2.0
        k, q = slots[i][0], slots[i][1]
        events.append({'t': round(on / fps, 2), 'dur': round(e - a, 2), 'bar': k + 1, 'beat': q // 4 + 1, 'sixteenth': q % 4 + 1,
                       'excess_db': round(float(ex[i:j + 1].max()), 1), 'flat': round(float(F[i:j + 1].mean()), 2),
                       'decay_12db_s': round(dec, 2)})
        i = j + 1
    else:
        i += 1
json.dump(events, open('work/audio/static.json', 'w'), indent=1)
for ev in events:
    print(ev)
print(len(events), 'events')
