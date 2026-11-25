#!/usr/bin/env python3
"""Which tracked beat is beat 1? Folds harmonic change (bass chroma novelty), kick/snare/hat flux and
vocal onsets over beat-index mod 4, in windows, and prints a 16th-note drum pattern per section.

  downbeat.py
"""
import json
import numpy as np
from scipy.io import wavfile
from scipy.signal import stft

B = np.array(json.load(open('work/audio/beats.json'))['beats'])
d = np.load('work/audio/feat.npz')
R = float(d['rate'])
sr, x = wavfile.read('work/audio/inst22k.wav')
x = x.astype(np.float32) / 32768
f, t, Z = stft(x, sr, nperseg=4096, noverlap=4096 - 512, boundary=None, padded=False)
A = np.abs(Z)
fr = sr / 512
def chroma(lo, hi):
    b = (f >= lo) & (f < hi)
    midi = 69 + 12 * np.log2(f[b] / 440)
    pc = np.round(midi).astype(int) % 12
    C = np.zeros((12, A.shape[1]))
    for k in range(12):
        C[k] = A[b][pc == k].sum(0)
    return C / (C.sum(0, keepdims=True) + 1e-9)
Cb = chroma(40, 250)
Ch = chroma(130, 1500)
def beat_mean(C, i):
    a = int(B[i] * fr); b = int(B[i + 1] * fr)
    return C[:, a:b].mean(1)
nb = len(B) - 1
cb = np.array([beat_mean(Cb, i) for i in range(nb)])
ch = np.array([beat_mean(Ch, i) for i in range(nb)])
nov = np.zeros(nb)
for i in range(1, nb):
    nov[i] = np.abs(cb[i] - cb[i - 1]).sum() + 0.5 * np.abs(ch[i] - ch[i - 1]).sum()
def val(arr, tt, w=0.03):
    a = int(max(0, (tt - w) * R)); b = int((tt + w) * R) + 1
    return float(arr[a:b].max())
kick = np.array([val(d['kick'], B[i]) for i in range(nb)])
snare = np.array([val(d['snare'], B[i]) for i in range(nb)])
hat = np.array([val(d['hat'], B[i]) for i in range(nb)])
# crash proxy: hat-band energy integrated 0-300 ms after the beat
crash = np.array([d['hat'][int(B[i] * R):int((B[i] + 0.3) * R)].sum() for i in range(nb)])
print('window   beats      novelty by idx%4            crash by idx%4')
for a in range(0, nb - 32, 32):
    sl = slice(a, a + 32)
    nv = [nov[sl][k::4].mean() for k in range(4)]
    cr = [crash[sl][k::4].mean() for k in range(4)]
    print(f'{B[a]:6.1f}s {a:4d}-{a+31:4d}  ' + ' '.join(f'{v:5.2f}' for v in nv) + '   ' + ' '.join(f'{v:6.1f}' for v in cr))
np.savez('work/audio/beatfeat.npz', nov=nov, kick=kick, snare=snare, hat=hat, crash=crash, cb=cb, ch=ch)
