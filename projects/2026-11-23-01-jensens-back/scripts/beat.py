"""What the drums are doing at time t, read from the measured envelopes (feat.py), plus the bar grid.

The song is 75.00 BPM throughout (0.8 s per beat, 3.2 s per bar, downbeats at multiples of 3.2 s from the first
sample; measured from the kick / snare onset histograms of the separated instrumental).
"""
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEAT, BAR = 0.8, 3.2
_d = np.load(os.path.join(ROOT, 'work', 'audio', 'feat.npz'))
RATE = float(_d['rate'])


def _env(x, tau, floor=0.22):
    n = np.percentile(x, 99.5)
    x = np.clip((x / n - floor) / (1 - floor), 0, 1).astype(np.float32)
    k = float(np.exp(-1.0 / (tau * RATE)))
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = max(float(x[i]), acc * k)
        y[i] = acc
    return y


_K = _env(_d['kick'], 0.16)
_S = _env(_d['snare'], 0.11, 0.3)
_HT = _env(_d['hat'], 0.05, 0.3)
_LOUD = _d['loud']
_LOW = _d['low']
_VOX = _d['vox']


def _at(a, t):
    i = int(t * RATE)
    return float(a[i]) if 0 <= i < len(a) else 0.0


def kick(t):
    return _at(_K, t)


def snare(t):
    return _at(_S, t)


def hat(t):
    return _at(_HT, t)


def loud(t, win=0.15):
    """mix loudness 0..1 (-40 dB .. -10 dB) smoothed over win seconds."""
    i0, i1 = int((t - win) * RATE), int(t * RATE) + 1
    i0 = max(i0, 0)
    if i1 <= i0:
        return 0.0
    return float(np.clip((np.mean(_LOUD[i0:i1]) + 40) / 30, 0, 1))


def vox(t, win=0.08):
    i0, i1 = max(int((t - win) * RATE), 0), int(t * RATE) + 1
    if i1 <= i0:
        return 0.0
    return float(np.clip((np.max(_VOX[i0:i1]) + 50) / 30, 0, 1))


def bar(t):
    """(bar index, position 0..1 inside the bar)"""
    b = t / BAR
    return int(np.floor(b)), b - np.floor(b)


def beat(t):
    b = t / BEAT
    return int(np.floor(b)), b - np.floor(b)


def pulse(t, period=BEAT, decay=0.18, phase=0.0):
    """exp-decay pulse on a grid, 1 at the grid point."""
    x = (t - phase) % period
    return float(np.exp(-x / decay))
