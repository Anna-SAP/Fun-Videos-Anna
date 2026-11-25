#!/usr/bin/env python3
"""Prove the film carries the song untouched and in sync.

  qc_audio.py SONG FILM [T1,T2,...]

1. MD5 of the audio packets of both files (stream copy, no decode). Equal means the film's audio stream is the
   song's, bit for bit.
2. Decodes both by container timestamps and cross-correlates a 4 s window at each T (default: four points
   spread over the song). Prints the offset in ms; positive means the film's sound is late.

Why both: the MD5 says the samples are the same, the correlation says they sit at the same time. A wrong
-itsoffset passes the first check and fails the second.
numpy only, plus ffmpeg on PATH.
"""
import subprocess
import sys

import numpy as np

song, film = sys.argv[1:3]
SR = 8000


def md5(path):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:a:0', '-c', 'copy', '-f', 'md5', '-'], capture_output=True, text=True)
    return r.stdout.strip().replace('MD5=', '')


def pcm(path):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:a:0', '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'], capture_output=True)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768


a, b = md5(song), md5(film)
print('audio packet MD5  song', a)
print('audio packet MD5  film', b, ' -> ', 'identical' if a == b else 'DIFFERENT (re-encoded, trimmed or a different stream)')

x, y = pcm(song), pcm(film)
dur = min(len(x), len(y)) / SR
times = [float(t) for t in sys.argv[3].split(',')] if len(sys.argv) > 3 else [dur * k for k in (.1, .35, .6, .85)]
WIN, PAD = 4.0, .5
worst = 0.0
for t in times:
    i0 = int(t * SR)
    ref = x[i0:i0 + int(WIN * SR)]
    j0 = max(0, i0 - int(PAD * SR))
    seg = y[j0:i0 + int((WIN + PAD) * SR)]
    if len(ref) < SR or len(seg) < len(ref) or np.abs(ref).max() < 1e-3:
        print(f't={t:7.2f}s  skipped (too short or silent)')
        continue
    c = np.correlate(seg - seg.mean(), ref - ref.mean(), mode='valid')
    k = int(c.argmax())
    frac = 0.0
    if 0 < k < len(c) - 1:
        d = c[k - 1] - 2 * c[k] + c[k + 1]
        frac = .5 * (c[k - 1] - c[k + 1]) / d if d else 0.0
    off = (j0 + k + frac - i0) / SR * 1000
    peak = c[k] / (np.linalg.norm(ref - ref.mean()) * np.linalg.norm(seg[k:k + len(ref)] - seg[k:k + len(ref)].mean()) + 1e-9)
    worst = max(worst, abs(off))
    print(f't={t:7.2f}s  offset {off:+7.2f} ms   correlation {peak:.3f}')
print('worst offset', round(worst, 2), 'ms ->', 'in sync' if worst < 5 else 'OUT OF SYNC: look for -itsoffset, a trimmed head, or a re-encode')
