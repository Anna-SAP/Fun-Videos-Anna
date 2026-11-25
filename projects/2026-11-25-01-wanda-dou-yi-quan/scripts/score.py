#!/usr/bin/env python3
"""The film's clock: tracked beats, the record's rotation, per-line timing and when each line is cut into
the record. Everything here is measured from the song; no lyric text is stored in this file.

Measured facts used here
  * beats are tracked, not gridded: the song speeds up from 0.541 s to 0.5285 s per beat
  * a sung line lasts two bars (8 beats); the record turns once per 8 beats, so one line = one revolution
  * phrase downbeats are beats 1 + 8n up to the bridge and 229 + 8n in the final chorus
  * the band stops under the voice at 40.98-41.52 s and at 143.87-144.94 s
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lyrics  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUR = 167.221
FPS = 30
NFRAMES = int(round(DUR * FPS))
TAU = 2 * math.pi

BEATS = np.array(json.load(open(os.path.join(ROOT, 'work', 'audio', 'beats.json')))['beats'])
_per = float(np.median(np.diff(BEATS[-40:-12])))
BEATS = np.concatenate([BEATS, BEATS[-1] + _per * np.arange(1, 12)])
_IDX = np.arange(len(BEATS))

SIL1 = (40.98, 41.52)          # band stops under the voice in the first pre-chorus
SIL2 = (143.87, 144.94)        # band stops under the spoken goodbye
BAND_IN = 8.02                 # the full band enters
NEEDLE_DOWN = 0.28             # first thump of the recording: the needle lands
BAND_OUT = 160.81              # the band's last hit
DROP_T = 106.66                # bridge: the drop lands (last syllable of the first half-line)
THUMPS = (160.93, 162.90)      # two low thumps in the tail


def bp(t):
    """fractional beat index at time t"""
    return float(np.interp(t, BEATS, _IDX))


def beat_time(b):
    return float(np.interp(b, _IDX, BEATS))


def pulse(t, div=1.0, sharp=6.0):
    """1 on each beat (or every `div` beats), decaying"""
    x = bp(t) / div
    return math.exp(-sharp * (x - math.floor(x)))


# ---- clocks -----------------------------------------------------------------------------------------------
_DT = 1 / 240
_tt = np.arange(0, DUR + 1, _DT)


def _gate(tt, a, b, w=0.10):
    return 1 - np.clip((tt - a) / w, 0, 1) * np.clip((b - tt) / w, 0, 1)


# record clock: beat position that coasts to a stop in the last silence and starts again with the band
_rate = np.gradient(np.interp(_tt, BEATS, _IDX), _DT)
_stop = np.clip((_tt - SIL2[0]) / 0.75, 0, 1) * (_tt < SIL2[1])
_rate_rec = _rate * (1 - _stop) ** 2
_REC = np.cumsum(_rate_rec) * _DT
_REC += bp(30.0) - float(np.interp(30.0, _tt, _REC))       # agree with the beat index during the song
# flow clock for particles, traffic, water: seconds that stand still in both silences
_FLOW = np.cumsum(_gate(_tt, *SIL1) * _gate(_tt, SIL2[0], SIL2[1], 0.2)) * _DT


def rec(t):
    return float(np.interp(t, _tt, _REC))


def flow(t):
    return float(np.interp(t, _tt, _FLOW))


def theta(t, disc='A'):
    """rotation of the record (radians, clockwise on screen); 0 at every phrase downbeat"""
    return TAU * (rec(t) - (1 if disc == 'A' else 229)) / 8.0


def grid(n, disc='A'):
    """time of phrase downbeat n"""
    return beat_time((1 if disc == 'A' else 229) + 8 * n)


# ---- lines ------------------------------------------------------------------------------------------------
LINES = lyrics.load()
_T = json.load(open(os.path.join(ROOT, 'work', 'audio', 'lyric_timing.json')))
N_RINGS_A = 20
for _l in LINES:
    _l['t'] = _T[str(_l['i'])]['t']
    _l['t0'], _l['t1'] = _l['t'][0], _l['t'][-1]
    r = _l['ring']
    _l['disc'] = None
    if r is not None and r <= 20:
        _l['disc'], _l['slot'] = 'A', r
    elif r is not None and r >= 23:
        _l['disc'], _l['slot'] = 'B', r - 22
    if _l['disc']:
        n = 0
        while grid(n, _l['disc']) < _l['t1'] + 0.2:
            n += 1
        _l['rel'] = grid(n, _l['disc'])          # the downbeat on which this line is cut into the record
SUNG = [l for l in LINES if not l['spoken']]
SPOKEN = [l for l in LINES if l['spoken']]
BY_RING = {l['ring']: l for l in SUNG}
EXTRA_SAY = (143.68, 143.88)     # the voice says the first word of the goodbye a second time here (not in the sheet)


def line_at(t, pre=0.6):
    """the sung line on the arc at time t (from `pre` before its first character until it is released)"""
    for l in SUNG:
        end = l.get('rel', l['t1'] + 1.2) + 0.35
        if l['t0'] - pre <= t < end:
            return l
    return None


def rings_done(t, disc='A'):
    """how many rings of a disc have been cut at time t (fractional during the cut)"""
    n = 0.0
    for l in SUNG:
        if l['disc'] == disc:
            n += min(1.0, max(0.0, (t - (l['rel'] - 0.38)) / 0.68))
    return n


RIDE = (grid(20), grid(22))       # first half of the second chorus: the camera turns with the record


def ride_rot(t):
    """how far the camera has turned with the record (radians)"""
    return theta(t) - theta(RIDE[0]) if RIDE[0] <= t < RIDE[1] else 0.0


# ---- sections ---------------------------------------------------------------------------------------------
G = lambda n: grid(n)            # noqa: E731
SEC = {
    'intro': (0.0, BAND_IN),
    'title': (BAND_IN, G(4)),
    'v1': (G(4), G(8)),
    'pre1': (G(8), G(10)),
    'ch1': (G(10), G(14)),
    'home': (G(14), G(15)),
    'dinner': (G(15), G(16)),
    'track': (G(16), G(18)),
    'pre2': (G(18), G(20)),
    'ch2': (G(20), beat_time(196)),
    'bridge': (beat_time(196), 114.6),
    'said': (114.6, grid(0, 'B') - 0.5),
    'ch3': (grid(0, 'B') - 0.5, 141.6),
    'bye': (141.6, SIL2[1]),
    'map': (SIL2[1], BAND_OUT),
    'tail': (BAND_OUT, DUR),
}

if __name__ == '__main__':
    print('frames', NFRAMES)
    for k, (a, b) in SEC.items():
        print(f'{k:7s} {a:7.2f} {b:7.2f}  beats {bp(a):6.1f}-{bp(b):6.1f}')
    for l in LINES:
        print(l['i'], l['sec'], 'spoken' if l['spoken'] else f"ring {l['ring']} disc {l['disc']} t0 {l['t0']:.2f} t1 {l['t1']:.2f} rel {l.get('rel', 0):.2f}",
              f"theta/2pi at rel {theta(l['rel'], l['disc']) / TAU:.3f}" if l['disc'] else '')
    print('theta at 143.9, 144.5, 144.94, 146:', [round(theta(x) / TAU, 3) for x in (143.9, 144.5, 144.94, 146)])
