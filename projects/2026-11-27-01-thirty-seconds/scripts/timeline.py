#!/usr/bin/env python3
"""Time for the whole film: frame rate, the tracked beat grid, the measured events, the variable clock, the shots.

Every time here is measured (storyboard.md section 1). The tempo drifts from 133.9 to 136.1 BPM, so B(bar, beat)
looks beats up on the tracked grid (work/audio/bars.json, 534 beats, 133 bars of four) instead of multiplying.
Cuts are written as anchors: a bar, or a sung character (L('Verse 2|3') = first character of that line), snapped
to the nearest beat (or eighth, for the word-by-word cuts) and rounded to a frame.

Everything that flows (sparks, embers, sand, snow, petals, haze, the slow pushes) reads phi(t), the integral of
rate(t): 1 everywhere, 0 inside the measured stops, where the band drops out under a held voice. In the longest of
them (pre-chorus 1, the name) the whole world freezes and only the three characters being carved move.
"""
import json
import os
from dataclasses import dataclass, field

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 24
W, H = 1080, 1920
AUDIO_DUR = 237.584              # container duration of the song (3:57.58)
NFRAMES = 5703                   # ceil(237.584 * 24) + 1: the picture outlasts the audio, so -shortest keeps every packet

_bj = json.load(open(os.path.join(ROOT, 'work', 'audio', 'bars.json')))
BEATS = np.array(_bj['beats'])
BAR_IDX = _bj['bar_idx']
LT = {e['id']: e for e in json.load(open(os.path.join(ROOT, 'work', 'audio', 'lyric_timing.json')))}


def B(bar, beat=1, frac=0.0):
    """Seconds of bar (1-based) beat (1-based) + frac of a beat, on the tracked grid."""
    i = BAR_IDX[bar - 1] + beat - 1
    t = BEATS[i]
    if frac:
        t += frac * (BEATS[i + 1] - BEATS[i])
    return float(t)


def L(oid, k=0):
    """Start of sung character k of occurrence oid (lyric_timing.json)."""
    return float(LT[oid]['start'][k])


def Lend(oid):
    return float(LT[oid]['end'][-1])


def fr(t):
    return round(t * FPS) / FPS


def snap(t, div=1):
    """Nearest beat (div=1) or eighth (div=2) to t, rounded to a frame."""
    grid = BEATS if div == 1 else np.sort(np.concatenate([BEATS, (BEATS[:-1] + BEATS[1:]) / 2]))
    return fr(float(grid[np.argmin(np.abs(grid - t))]))


# ---- measured events --------------------------------------------------------------------------------------
STOPS = [(21.53, 22.73), (57.56, 59.10), (144.07, 144.73), (161.78, 162.13), (233.69, 240.0)]
NAME_STOP = STOPS[1]                       # band out 57.56-58.87, the name is sung into it; chorus hits on bar 34
SLAMS = [B(14), B(34), B(42), B(74), B(104), B(114)]     # verse 1, chorus 1, drop 1, chorus 2, final chorus, drop 2
CHANT = [81.01, 81.90, 82.79, 83.68, 84.58]                # shouts on beats 2 and 4 of bars 46-48
CHOPS = (85.47, 87.71)                                     # wordless vocal chops on eighths
SUMMITS = ['Pre-Chorus 1|3', 'Build-Up|2', 'Final Chorus|4', 'Drop 2|1#b']   # the four sung peaks near B4
MEMORY = 'Outro|2'                                         # sung an octave down (B2)
LOUDEST = 212.1                                            # end of the loudest 3 s (drop 2), short-term -11.5 LUFS


# ---- the variable clock -----------------------------------------------------------------------------------
_DT = 0.002
_tt = np.arange(0, AUDIO_DUR + 3, _DT)


def _rate_arr(t):
    r = np.ones_like(t)
    for a, b in STOPS:
        ease = 0.08 if b - a < 1.0 else 0.12
        m = (t >= a) & (t < a + ease)
        r[m] = 0.5 * (1 + np.cos(np.pi * (t[m] - a) / ease))
        r[(t >= a + ease) & (t < b)] = 0.0
    return r


_rr = _rate_arr(_tt)
_phi = np.concatenate([[0], np.cumsum(_rr[:-1]) * _DT])


def rate(t):
    return float(np.interp(t, _tt, _rr))


def phi(t):
    return float(np.interp(t, _tt, _phi))


# ---- drums and loudness -----------------------------------------------------------------------------------
_feat = np.load(os.path.join(ROOT, 'work', 'audio', 'feat.npz'))
FR = float(_feat['rate'])
KICKS = np.array(_feat['kick_t'], float)
KICKV = np.array(_feat['kick_v'], float)
_kmax = np.percentile(KICKV, 95)
_inst = _feat['inst']
_inst_s = np.convolve(_inst, np.ones(9) / 9, 'same')


def kick(t, tau=0.12):
    m = (KICKS <= t) & (KICKS > t - 0.6)
    if not m.any():
        return 0.0
    v = np.minimum(KICKV[m] / _kmax, 1.0) * np.exp(-(t - KICKS[m]) / tau)
    return float(min(1.0, v.max()))


def band(t):
    """Instrumental level 0..1 (-48 dB .. -16 dB): dips in the chorus stutters and the stops."""
    i = min(len(_inst_s) - 1, max(0, int(t * FR)))
    return float(np.clip((_inst_s[i] + 48) / 32, 0, 1))


def _loud():
    import re
    T, S = [], []
    cur = None
    p = os.path.join(ROOT, 'work', 'audio', 'ebur_S.txt')
    for l in open(p):
        m = re.search(r'pts_time:([\d.]+)', l)
        if m:
            cur = float(m.group(1))
        m = re.search(r'lavfi.r128.S=(-?[\d.]+)', l)
        if m and cur is not None:
            T.append(cur)
            S.append(float(m.group(1)))
    T, S = np.array(T), np.array(S)
    # 3 s short-term loudness is centred 1.5 s late; shift, then smooth over 4 s
    T = T - 1.5
    k = int(4.0 / max(np.median(np.diff(T)), 1e-3))
    S = np.convolve(S, np.ones(k) / k, 'same')
    return T, S


_LT, _LS = _loud()


def energy(t):
    """The song's measured short-term loudness mapped to 0..1 (-20 LUFS .. -12 LUFS)."""
    return float(np.clip((np.interp(t, _LT, _LS) + 20) / 8, 0, 1))


# ---- shots ------------------------------------------------------------------------------------------------
@dataclass
class Shot:
    id: str
    kf: str
    t0: float
    t1: float = 0.0
    z: tuple = (1.0, 1.05)          # push: zoom at start, end (on top of the 1080/1040 base)
    c: tuple = (544, 960)           # zoom centre in keyframe pixels
    par: float = 14.0               # depth parallax over the shot, output px (near minus far)
    pdir: tuple = (1.0, -0.3)       # parallax direction
    grade: str = 'night'
    parts: tuple = ()               # particle presets
    fx: tuple = ()
    cy: int = 640                   # lyric block centre (output px)
    mode: str = ''                  # lyric rule override for lines starting in this shot
    fade_in: float = 0.0
    fade_out: float = 0.0
    punch: bool = False             # kick punch-in
    cap: int = 0                    # lyric cell size cap for this shot (0 = default)
    cx: int = 0                     # lyric block centre x (0 = middle of the safe area)
    extra: dict = field(default_factory=dict)


def S(sid, kf, at, **kw):
    return Shot(sid, kf, at, **kw)


SHOTS = [
    # intro: blue hour, the teller and the newcomer at the edge of the valley
    S('s01', 'K01', 0.0, z=(1.08, 1.0), c=(544, 1150), par=8, fade_in=2.4, parts=('motes',), cy=620),
    S('s02', 'K02', snap(L('Intro|1')), z=(1.0, 1.07), c=(544, 1100), par=10, grade='dusk', parts=('motes',), cy=560),
    S('s03', 'K03', snap(L('Intro|2')), z=(1.0, 1.06), c=(544, 960), par=12, parts=('sand_neck', 'motes'), cy=560),
    S('s04', 'K04', snap(L('Intro|3')), z=(1.0, 1.05), c=(544, 1250), par=10, grade='dusk', parts=('embers_small', 'steam'), cy=380, cap=140),
    S('s05', 'K05', snap(L('Intro|4')), z=(1.0, 1.06), c=(560, 1000), par=16, grade='dusk', parts=('motes',), cy=420, cap=170),
    # verse 1: the world, one region per line; the gold carving rule
    S('s06', 'K06', snap(L('Verse 1|1')), z=(1.0, 1.08), par=10, parts=('embers',), cy=700, punch=True),
    S('s07', 'K07', snap(L('Verse 1|2')), z=(1.0, 1.06), par=18, grade='fire', parts=('spray',), cy=1150),
    S('s08', 'K08', snap(L('Verse 1|2', 7), 2), z=(1.0, 1.06), par=10, parts=('stars',), cy=560),
    S('s09', 'K09', snap(L('Verse 1|3')), z=(1.0, 1.06), par=16, grade='fire', parts=('embers',), cy=560),
    S('s10', 'K10', snap(L('Verse 1|4')), z=(1.0, 1.06), par=12, parts=('motes',), cy=1180),
    S('s11', 'K11', snap(L('Verse 1|5')), z=(1.0, 1.10), par=8, grade='dusk', cy=640),
    S('s12', 'K12', snap(L('Verse 1|5', 5), 2), z=(1.02, 1.08), par=14, parts=('snow',), cy=640, punch=True),
    S('s13', 'K13', snap(L('Verse 1|5', 7), 2), z=(1.02, 1.08), par=14, grade='day', parts=('sand',), cy=640, punch=True),
    S('s14', 'K14', snap(L('Verse 1|5', 9), 2), z=(1.02, 1.08), par=14, grade='day', cy=640, punch=True),
    S('s15', 'K15', snap(L('Verse 1|5', 11), 2), z=(1.02, 1.08), par=14, grade='dusk', cy=640, punch=True),
    S('s16', 'K16', snap(L('Verse 1|5', 13), 2), z=(1.0, 1.05), par=10, grade='dusk', cy=600, punch=True),
    S('s17', 'K17', snap(L('Verse 1|6')), z=(1.0, 1.07), par=18, grade='dusk', parts=('motes',), cy=560, punch=True),
    S('s18', 'K18', snap(L('Verse 1|7')), z=(1.0, 1.10), c=(544, 1150), par=14, grade='dusk', parts=('motes',), cy=520, punch=True),
    # pre-chorus 1: bass out; then the name in the stop
    S('s19', 'K19', snap(L('Pre-Chorus 1|1')), z=(1.0, 1.05), par=20, grade='dusk', cy=470),
    S('s20', 'K20', snap(L('Pre-Chorus 1|2')), z=(1.0, 1.08), c=(544, 1000), par=10, parts=('teal_motes',), cy=520, fx=('palm',)),
    S('s21', 'K21', fr(NAME_STOP[0]), z=(1.0, 1.0), par=0, parts=('teal_motes',), cy=760, fx=('crystal_flare',)),
    # chorus 1: before the battle, from outside; the teal light rule
    S('s22', 'K22', fr(B(34)), z=(1.10, 1.0), par=6, parts=('teal_motes',), cy=760, punch=True),
    S('s23', 'K23', snap(L('Chorus 1|2')), z=(1.0, 1.05), c=(544, 1100), par=14, parts=('teal_motes',), cy=430, punch=True),
    S('s24', 'K24', snap(L('Chorus 1|3')), z=(1.0, 1.08), par=12, parts=('embers_red',), cy=430, punch=True),
    S('s25', 'K25', snap(L('Chorus 1|4')), z=(1.0, 1.05), par=16, parts=('teal_motes',), cy=380, punch=True),
    S('s26', 'K26', snap(L('Chorus 1|5')), z=(1.0, 1.10), par=12, parts=('motes',), cy=520, punch=True, fx=('gate_light',)),
    # drop 1: the charge, then one role per shout, then the beacons on the vocal chops
    S('s27', 'K27', fr(B(42)), z=(1.04, 1.12), par=8, parts=('embers',), cy=1180, punch=True),
    S('s28', 'K28', snap(L('Chorus 1|5#echo')), z=(1.0, 1.08), par=18, parts=('teal_motes', 'dust'), cy=520, punch=True),
    S('s29', 'K29', snap(L('Chorus 1|5#again')), z=(1.0, 1.08), par=18, parts=('spray',), cy=520, punch=True),
    S('s30', 'K30', fr(CHANT[0]), z=(1.04, 1.10), par=14, cy=400, punch=True),
    S('s31', 'K31', fr(CHANT[1]), z=(1.04, 1.10), par=14, cy=400, punch=True),
    S('s32', 'K32', fr(CHANT[2]), z=(1.04, 1.10), par=14, cy=400, punch=True),
    S('s33', 'K33', fr(CHANT[3]), z=(1.04, 1.10), par=14, cy=400, punch=True),
    S('s34', 'K34', fr(CHANT[4]), z=(1.04, 1.10), par=14, cy=400, punch=True),
    S('s35', 'K35', fr(CHOPS[0]), z=(1.0, 1.06), par=10, parts=('embers',), cy=640, fx=('beacons',)),
    # verse 2: the thirteen lands, one per line
    S('s36', 'K36', fr(B(50)), z=(1.0, 1.06), par=12, grade='day', cy=760, punch=True),
    S('s37', 'K37', snap(L('Verse 2|2')), z=(1.0, 1.06), par=10, grade='dusk', parts=('gold_motes',), cy=520),
    S('s38', 'K38', snap(L('Verse 2|3')), z=(1.0, 1.06), par=14, grade='fire', parts=('embers',), cy=560, punch=True),
    S('s39', 'K39', snap(L('Verse 2|4')), z=(1.0, 1.05), par=16, grade='dusk', parts=('petals',), cy=600),
    S('s40', 'K40', snap(L('Verse 2|5')), z=(1.0, 1.06), par=14, cy=330, cap=150),
    S('s41', 'K41', snap(L('Verse 2|6')), z=(1.0, 1.06), par=12, grade='ghost', parts=('mist_green',), cy=560),
    S('s42', 'K42', snap(L('Verse 2|7')), z=(1.0, 1.07), par=12, grade='day', parts=('sand',), cy=430, punch=True),
    S('s43', 'K43', snap(L('Verse 2|8')), z=(1.0, 1.07), par=10, parts=('stars',), cy=330, cap=160, fx=('star_fall',)),
    S('s44', 'K44', snap(L('Verse 2|9')), z=(1.0, 1.06), par=14, parts=('snow',), cy=520),
    S('s45', 'K45', snap(L('Verse 2|10')), z=(1.0, 1.08), par=12, grade='void', parts=('void_motes',), cy=560, punch=True),
    # pre-chorus 2
    S('s46', 'K46', snap(L('Pre-Chorus 2|1')), z=(1.0, 1.06), par=8, cy=1240),
    S('s47', 'K47', snap(L('Pre-Chorus 2|2')), z=(1.0, 1.06), par=6, parts=('stars',), cy=1100),
    S('s48', 'K21', snap(L('Pre-Chorus 2|3')), z=(1.12, 1.16), c=(544, 900), par=4, parts=('teal_motes',), cy=760),
    # chorus 2: the same words, now inside the night battle
    S('s49', 'K49', fr(B(74)), z=(1.06, 1.0), par=16, grade='fire', parts=('embers',), cy=600, punch=True),
    S('s50', 'K50', snap(L('Chorus 2|2')), z=(1.0, 1.05), par=14, grade='fire', parts=('embers',), cy=400, punch=True),
    S('s51', 'K51', snap(L('Chorus 2|3')), z=(1.0, 1.08), par=10, grade='fire', parts=('embers_red',), cy=1380, cap=170, punch=True),
    S('s52', 'K52', snap(L('Chorus 2|4')), z=(1.0, 1.05), par=16, grade='fire', parts=('embers',), cy=560, cap=110, cx=310, punch=True),
    S('s53', 'K53', snap(L('Chorus 2|5')), z=(1.0, 1.08), par=14, grade='fire', parts=('embers',), cy=520, punch=True),
    # bridge: the twin cities, soft; neon rule
    S('s54', 'K54', fr(B(82)), z=(1.0, 1.06), par=10, grade='day', parts=('gold_motes',), cy=640),
    S('s55', 'K55', snap(L('Bridge|2')), z=(1.0, 1.06), par=12, grade='neon', parts=('mist_green',), cy=560),
    S('s56', 'K56', snap(L('Bridge|3')), z=(1.0, 1.05), par=14, grade='neon', parts=('mist_green',), cy=520),
    S('s57', 'K57', snap(L('Bridge|4')), z=(1.0, 1.08), c=(544, 1000), par=8, grade='neon', cy=520, fx=('blast',)),
    S('s58', 'K58', snap(L('Bridge|5')), z=(1.0, 1.05), par=14, grade='neon', cy=560),
    S('s59', 'K59', snap(L('Bridge|6')), z=(1.0, 1.06), par=8, grade='neon', cy=480),
    # verse 3: seventeen years
    S('s60', 'K60', fr(STOPS[3][0]), z=(1.0, 1.06), par=10, grade='lamp', cy=560, punch=True),
    S('s61', 'K61', snap(L('Verse 3|2')), z=(1.0, 1.06), par=10, grade='arena', parts=('confetti',), cy=560, punch=True),
    S('s62', 'K62', snap(L('Verse 3|3')), z=(1.0, 1.08), par=10, grade='arena', cy=480, cx=720, cap=110, punch=True),
    S('s63', 'K63', snap(L('Verse 3|4')), z=(1.0, 1.06), par=10, grade='arena', parts=('confetti',), cy=560, punch=True),
    S('s64', 'K64', snap(L('Verse 3|5')), z=(1.0, 1.06), par=8, grade='arena', parts=('confetti',), cy=1260, punch=True),
    S('s65', 'K65', snap(L('Verse 3|6')), z=(1.0, 1.06), par=10, grade='dawn', parts=('motes',), cy=560),
    S('s66', 'K66', snap(L('Verse 3|7')), z=(1.0, 1.05), par=12, grade='dawn', parts=('motes',), cy=560),
    # build-up
    S('s67', 'K67', fr(B(100)), z=(1.0, 1.10), par=6, parts=('teal_motes',), cy=560, fx=('crystal_pulse',)),
    S('s68', 'K68', snap(L('Build-Up|2')), z=(1.0, 1.0), par=4, parts=('sand_neck',), cy=600, fx=('count',)),
    # final chorus: dawn; the newcomer in front
    S('s69', 'K69', fr(B(104)), z=(1.10, 1.0), par=8, grade='dawn', parts=('gold_motes',), cy=760, punch=True),
    S('s70', 'K70', snap(L('Final Chorus|2')), z=(1.0, 1.05), par=14, grade='dawn', parts=('teal_motes',), cy=420, cap=130, punch=True),
    S('s71', 'K51', snap(L('Final Chorus|3')), z=(1.04, 1.12), par=10, grade='fire', parts=('embers_red',), cy=1380, cap=170, punch=True),
    S('s72', 'K72', snap(L('Final Chorus|4')), z=(1.0, 1.10), par=16, grade='dawn', parts=('gold_motes',), cy=1300, cx=730, cap=100, punch=True),
    S('s73', 'K73', snap(L('Final Chorus|5')), z=(1.0, 1.06), par=12, grade='dawn', parts=('embers',), cy=600, punch=True),
    # drop 2: the loudest stretch, a cut every bar
    S('s74', 'K74', fr(B(114)), z=(1.04, 1.12), par=20, grade='dawn', parts=('embers', 'dust'), cy=600, punch=True),
    S('s75', 'K75', fr(B(115)), z=(1.04, 1.10), par=16, grade='dawn', parts=('spray', 'embers'), cy=1340, punch=True),
    S('s76', 'K69', fr(B(116)), z=(1.06, 1.14), par=8, grade='dawn', parts=('gold_motes', 'embers'), cy=1180, punch=True),
    S('s77', 'K76', snap(L('Drop 2|1#b')), z=(1.04, 1.12), par=18, grade='dawn', parts=('embers',), cy=1240, punch=True),
    S('s78', 'K73', fr(B(118)), z=(1.14, 1.24), c=(544, 760), par=12, grade='dawn', parts=('embers',), cy=1180, punch=True),
    S('s79', 'K71', fr(B(119)), z=(1.04, 1.12), c=(600, 900), par=10, grade='dawn', parts=('shards',), cy=1240, punch=True),
    # outro: the crystal goes, you turn round, the memory, the passing on
    S('s80', 'K77', snap(L('Outro|1')), z=(1.0, 1.04), par=10, grade='dawn', parts=('shards',), cy=1420, cap=150, fx=('explode',)),
    S('s81', 'K78', snap(L('Outro|1', 4)), z=(1.0, 1.04), c=(544, 900), par=8, grade='dawn', parts=('gold_motes',), cy=1420, cap=150),
    S('s82', 'K79', fr(B(121, 4)), z=(1.0, 1.05), par=8, grade='sepia', cy=560),
    S('s83', 'K80', snap(L('Outro|3')), z=(1.0, 1.06), par=10, parts=('embers_small',), cy=560),
    S('s84', 'K81', snap(L('Outro|4')), z=(1.0, 1.05), par=12, grade='dusk', parts=('embers_small', 'sand_neck'), cy=560),
    S('s85', 'K65', fr(B(128)), z=(1.0, 1.12), par=10, grade='dawn', parts=('gold_motes',), cy=560),
    S('s86', 'K01', fr(B(132)), z=(1.0, 1.0), par=0, parts=('motes', 'sand_neck'), cy=620, fade_out=0.8),
]
for _a, _b in zip(SHOTS, SHOTS[1:]):
    assert _b.t0 > _a.t0, (_a.id, _a.t0, _b.id, _b.t0)
    _a.t1 = _b.t0
SHOTS[-1].t1 = NFRAMES / FPS + 0.1
SHOTS[-1].extra['end_black'] = 237.50


def shot_at(t):
    lo, hi = 0, len(SHOTS) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if SHOTS[mid].t0 <= t:
            lo = mid
        else:
            hi = mid - 1
    return SHOTS[lo]


if __name__ == '__main__':
    for s in SHOTS:
        print(f'{s.id} {s.kf:4s} {s.t0:7.3f} - {s.t1:7.3f}  ({s.t1 - s.t0:5.2f} s)')
    print(len(SHOTS), 'shots;', len({s.kf for s in SHOTS}), 'keyframes')
