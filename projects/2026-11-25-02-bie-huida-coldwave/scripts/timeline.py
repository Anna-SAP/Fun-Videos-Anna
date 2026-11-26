#!/usr/bin/env python3
"""Time for the whole film: frame rate, the tracked beat grid, measured events, the variable clock, the shot list.

Every time in here is measured (storyboard.md): the grid comes from work/audio/bars.json (498 tracked beats; the
tempo drifts 111 -> 114.5 BPM and bar 65 has two beats), so B(bar, beat) looks the beat up instead of multiplying.
Everything that flows (fog, snow, grain, gate weave, slow pushes) reads phi(t), the integral of rate(t):
1 everywhere, easing to 0 over the first 2 s of the Bridge GAP and held at 0 until the band returns (option A).
"""
import json
import os
from dataclasses import dataclass, field

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 24
W, H = 1080, 1920
AUDIO_DUR = 264.46             # the song's container duration
NFRAMES = 6348                 # ceil(264.46 * 24): the picture outlasts the audio by < 1 frame, so every audio packet is kept

_bj = json.load(open(os.path.join(ROOT, 'work', 'audio', 'bars.json')))
BEATS = np.array(_bj['beats'])
BAR_IDX = _bj['bar_idx']


def B(bar, beat=1, frac=0.0):
    """Seconds of bar (1-based) beat (1-based) + frac of a beat, on the tracked grid."""
    i = BAR_IDX[bar - 1] + beat - 1
    t = BEATS[i]
    if frac:
        t += frac * (BEATS[i + 1] - BEATS[i])
    return float(t)


# ---- measured events -------------------------------------------------------------------------------
GAP = (172.67, 187.04)                 # Bridge: band out (sparse layer only) until the drums return on bar 89
BAND_BACK = 187.04
OUTRO_PULSES = [245.88, 250.07, 254.26, 258.44, 262.62]   # 4.19 s = two bars; the last two are the band
STATIC_BURST = [16.90, 25.52, 56.20, 81.95, 103.28, 120.30, 138.37, 155.32, 199.66, 223.84, 258.94]
STATIC_BED = [2.89, 54.10, 102.98, 137.30, 243.45]
CHORUS_ONE = [B(39), B(66), B(107)]     # 81.954, 138.396, 224.874
TICKS = [100.06, 100.34, 100.59, 101.05]  # chorus 1 line 5: floodlight off, on, off, on
HEART_STOP = (131.2, 133.08)            # drum machine stops for bar 62 (Verse 2 line 10)

# ---- the variable clock ----------------------------------------------------------------------------
_DT = 0.001
_tt = np.arange(0, AUDIO_DUR + 2, _DT)


def _rate_arr(t):
    r = np.ones_like(t)
    a, b = GAP[0], GAP[0] + 2.0
    m = (t >= a) & (t < b)
    u = (t[m] - a) / 2.0
    r[m] = 0.5 * (1 + np.cos(np.pi * u))          # smooth 1 -> 0
    r[(t >= b) & (t < GAP[1])] = 0.0
    return r


_rr = _rate_arr(_tt)
_phi = np.concatenate([[0], np.cumsum(_rr[:-1]) * _DT])


def rate(t):
    return float(np.interp(t, _tt, _rr))


def phi(t):
    return float(np.interp(t, _tt, _phi))


def frozen(t):
    return GAP[0] + 2.0 <= t < GAP[1]


# ---- drums -----------------------------------------------------------------------------------------
_feat = np.load(os.path.join(ROOT, 'work', 'audio', 'feat.npz'))
KICKS = np.array(_feat['kick_t'], float)
KICKV = np.array(_feat['kick_v'], float)
SNARES = np.array(_feat['snare_t'], float)
SNAREV = np.array(_feat['snare_v'], float)
_kmax = np.percentile(KICKV, 95)
_smax = np.percentile(SNAREV, 95)


def kick(t, tau=0.13):
    """Decaying pulse of the detected kicks (0..~1)."""
    m = (KICKS <= t) & (KICKS > t - 0.6)
    if not m.any():
        return 0.0
    v = np.minimum(KICKV[m] / _kmax, 1.0) * np.exp(-(t - KICKS[m]) / tau)
    return float(min(1.0, v.max()))


def snares_between(a, b, strong=0.45):
    m = (SNARES >= a) & (SNARES < b) & (SNAREV / _smax >= strong)
    return SNARES[m]


# ---- tone ------------------------------------------------------------------------------------------
def prussian(t):
    """0 = cold neutral black and white, 1 = white-to-Prussian-blue mapping."""
    a0, a1 = 194.5, 196.5            # ramps in while the white push has the frame almost white (Bridge line 5)
    if t < a0:
        return 0.0
    if t < a1:
        return (t - a0) / (a1 - a0)
    a, b = CHORUS_ONE[2], 236.403
    if t < a:
        return 1.0
    if t < b:
        u = (t - a) / (b - a)
        return 0.5 * (1 + np.cos(np.pi * u))
    return 0.0


# ---- shots -----------------------------------------------------------------------------------------
@dataclass
class Shot:
    id: str
    kf: str
    t0: float
    t1: float
    z: tuple = (1.0, 1.0)          # push: zoom at start, end (on top of the 1080/1040 base)
    c: tuple = (544, 960)          # zoom centre in keyframe pixels
    fade_in: float = 0.0
    fade_out: float = 0.0
    fade_in_at: float = None       # fade starts here instead of t0
    fade_out_at: float = None      # fade ends here instead of t1
    fog: float = 0.35              # fog density
    dark: float = 1.0              # ambient exposure multiplier for the plate
    snow: float = 0.0
    fx: tuple = ()
    lyr: dict = field(default_factory=dict)   # lyric-layer placement and mode overrides


def _f(t):
    return round(t * FPS) / FPS


CUT = json.load(open(os.path.join(ROOT, 'work', 'audio', 'cuts.json')))


def c(sid):
    return _f(CUT[sid]['cut'])


SHOTS = []          # filled by shots.py (geometry is read off the keyframes)
