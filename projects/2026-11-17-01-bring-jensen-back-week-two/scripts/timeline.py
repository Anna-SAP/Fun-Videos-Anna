"""The film as data: sections, one Block per sung entry with its design, and the camera.

Read top to bottom it is the lyric storyboard. Times come from work/audio/lyric_timing.json (per unit);
section boundaries snap to the measured downbeats (work/audio/beats.json).
"""
import json
import math

import numpy as np

import doors
import lyrics
import scenes
import typo
from common import DUR, FPS, H, W, clamp01, ease_out, hash01, smooth

TIM = {r['id']: r for r in json.load(open('work/audio/lyric_timing.json'))}
ORDER = [r['id'] for r in json.load(open('work/audio/lyric_timing.json'))]
BEATS = json.load(open('work/audio/beats.json'))
DOWN = np.array(BEATS['downbeats'])
BEAT_T = np.array(BEATS['beats'])
ENV = np.load('work/audio/env.npz')
KICKS = ENV['kick_on'] / FPS
SNARES = ENV['snare_on'] / FPS

DX0, DY0, DX1, DY1 = doors.DX0, doors.DY0, doors.DX0 + doors.DW, doors.DY0 + doors.DH
DCX = (DX0 + DX1) / 2


def times(eid):
    return [(u['s'], u['e']) for u in TIM[eid]['units']]


def first(eid):
    return TIM[eid]['units'][0]['s']


def last(eid):
    return TIM[eid]['units'][-1]['e']


def snap_down(t, tol=0.35):
    d = DOWN[np.argmin(np.abs(DOWN - t))]
    return float(d) if abs(d - t) < tol else t


def pulse(onsets, t, decay=0.14):
    i = np.searchsorted(onsets, t + 1e-6) - 1
    if i < 0:
        return 0.0
    return math.exp(-(t - onsets[i]) / decay)


def env(name, t):
    a = ENV[name]
    i = min(max(int(t * FPS), 0), len(a) - 1)
    return float(a[i])


# --------------------------------------------------------------------------------------------- sections
# name, first entry id, world, light colour
SEC = [
    ('intro', 'i1', 'wood', (0.55, 0.78, 1.0)),
    ('verse1', 'v1a', 'wood', (0.55, 1.0, 0.62)),
    ('pre', 'p1a', 'steel', (0.62, 0.92, 1.0)),
    ('hook1', 'h1a', 'wood', (0.55, 1.0, 0.6)),
    ('verse2', 'v2a', 'white', (0.76, 0.88, 1.0)),
    ('build', 'b1', 'steel', (1.0, 0.86, 0.6)),
    ('drop', 'd1', 'wood', (0.6, 1.0, 0.66)),
    ('taipei', 't1', 'tower', (1.0, 0.78, 0.45)),
    ('verse3', 'v3a', 'board', (1.0, 0.52, 0.32)),
    ('bridge', 'r1', 'vault', (1.0, 0.72, 0.42)),
    ('hook2', 'h2a', 'wood', (0.6, 1.0, 0.64)),
    ('outro', 'o1', 'wood', (1.0, 0.8, 0.55)),
]
SEC = [s for s in SEC if s[1] in TIM]
SEC_T0 = []
for k, s in enumerate(SEC):
    if k == 0:
        SEC_T0.append(0.0)
    else:
        SEC_T0.append(snap_down(first(s[1]) - 0.08))
SEC_T1 = SEC_T0[1:] + [DUR + 1]


def section_at(t):
    k = int(np.searchsorted(SEC_T0, t, side='right') - 1)
    return max(0, k)


def sec_name(t):
    return SEC[section_at(t)][0]


def entries_of(name):
    k = [s[0] for s in SEC].index(name)
    a = ORDER.index(SEC[k][1])
    b = ORDER.index(SEC[k + 1][1]) if k + 1 < len(SEC) else len(ORDER)
    return ORDER[a:b]


# --------------------------------------------------------------------------------------------- design
# Per-entry overrides. rows: phrase groups; w: block width; pos: world centre; rot: degrees; z: extra zoom;
# st: style dict for typo.draw; cam: camera kind ('close' default, 'wide', 'mid'); fx: extra effects
HOOK_ROWS = {
    33: [(0, 18), (19, 26), (27, 35)],
    34: [(0, 18), (19, 26), (27, 30), (31, 37)],
    35: [(0, 18), (19, 26), (27, 32), (33, 38)],
    36: [(0, 18), (19, 26), (27, 31), (32, 39)],
}


def hook_line(n, k, final=False):
    rows = HOOK_ROWS[n]
    rs = [None, 125] + [None] * (len(rows) - 2)
    y = DY0 + 700 + (k % 2) * 260
    return dict(rows=rows, row_sizes=rs, w=900, pos=(DCX + (-30 if k % 2 else 30), y), rot=(-1.5 if k % 2 else 1.5),
                st=dict(slam_units={0, 1, 2}, kin=1.2, out='shatter' if final else 'dim', dout=0.28),
                cam='close', cy=260, z=0.97)


D = {
    # ---- intro: a TV is on behind the door
    'i1': dict(rows=[(0, 5), (6, 17), (18, 26), (27, 40)], w=820, pos=(DCX, DY0 + 1250), align='center',
               fonts=('sans', 'mono'), lat_k=0.95, st=dict(inn='flick', flash=1.0, out='flicker', dout=0.35), z=0.9),
    'i2': dict(rows=[(0, 9), (10, 16)], w=860, pos=(DCX, DY0 + 1050), st=dict(kin=1.4)),
    'i3': dict(rows=[(0, 8), (9, 13), (14, 18)], w=860, pos=(DCX + 30, DY0 + 1600), rot=1.2),
    'i4': dict(rows=[(0, 5), (6, 25), (26, 30)], w=900, pos=(DCX - 20, DY0 + 1100), rot=-1.0,
               echo_units=(15.55, 16.35, {8, 9, 10}), st=dict(hold={12: 0.5, 13: 0.5, 14: 0.5, 15: 0.5})),
    # ---- verse 1: the front door fills up with pinholes
    'v1a': dict(rows=[(0, 2), (3, 5), (6, 9), (10, 16)], row_sizes=[150, 200, 260, None], w=860),
    'v1b': dict(rows=[(0, 6), (7, 12), (13, 21)], w=880),
    'v1c': dict(rows=[(0, 9), (10, 16), (17, 26), (27, 32)], w=820, align='left'),
    'v1d': dict(rows=[(0, 8), (9, 14), (14, 20)], w=880),
    'v1e': dict(rows=[(0, 4), (5, 10), (11, 20)], w=860),
    'v1f': dict(rows=[(0, 4), (4, 9), (10, 17)], w=860),
    'v1g': dict(rows=[(0, 6), (6, 9), (10, 18)], w=880),
    'v1h': dict(rows=[(0, 6), (6, 12), (13, 20)], w=880),
    'v1i': dict(rows=[(0, 5), (6, 12), (13, 20)], w=860, st=dict(out='shatter', dout=0.45)),
    'v1j': dict(rows=[(0, 6), (7, 9), (10, 16)], w=860),
    'v1k': dict(rows=[(0, 3), (4, 7), (8, 15)], w=860),
    'v1l': dict(rows=[(0, 6), (7, 14)], w=880),
    'v1m': dict(rows=[(0, 2), (3, 7), (8, 17)], w=860, st=dict(out='shatter', dout=0.4)),
    'v1n': dict(rows=[(0, 7), (8, 11), (12, 15)], w=860),
    'v1o': dict(rows=[(0, 9), (10, 16), (17, 23)], w=900, st=dict(slam_units={14})),
    'v1p': dict(rows=[(0, 5), (6, 11), (12, 18)], w=860),
    # ---- pre-chorus: the war-room door, a heartbeat
    'p1a': dict(rows=[(0, 4), (4, 8), (9, 16)], w=860, st=dict(inn='flick')),
    'p1b': dict(rows=[(0, 18), (19, 34), (35, 41)], w=880, lat_k=1.1, st=dict(inn='flick')),
    'p1c': dict(rows=[(0, 6), (7, 9), (9, 16)], w=860, st=dict(inn='flick')),
    'p1d': dict(rows=[(0, 3), (4, 7), (8, 15)], w=860, st=dict(inn='flick', out='dim', dout=0.15)),
    # ---- hook 1
    'h1a': hook_line(33, 0), 'h1b': hook_line(34, 1), 'h1c': hook_line(35, 2), 'h1d': hook_line(36, 3),
    'h1e': dict(rows=[(0, 3), (4, 9), (10, 13), (14, 19)], row_sizes=[250, 120, 250, 120], w=860,
                pos=(DCX, DY0 + 1000), cam='close', st=dict(slam_units={0, 1, 2, 5, 6, 7}, kin=1.3)),
    'h1f': dict(rows=[(0, 5), (6, 11)], w=860, pos=(DCX, DY0 + 380), cam='lamps', lamps=True),
    'h1g': dict(rows=[(0, 3), (4, 9), (10, 17)], w=880, pos=(DCX, DY0 + 1250)),
    'h1h': dict(rows=[(0, 10), (11, 24), (25, 43)], w=900, pos=(DCX, DY0 + 900),
                st=dict(slam_units={5, 6, 7}, kin=1.4), rewind=True),
    # ---- verse 2: Washington (white double door, cold light, trap hats)
    'v2a': dict(rows=[(0, 4), (5, 10), (11, 18)], w=860),
    'v2b': dict(rows=[(0, 9), (10, 20), (21, 24), (25, 32)], w=860, lat_k=1.15),
    'v2c': dict(rows=[(0, 4), (5, 11), (12, 18)], w=860),
    'v2d': dict(rows=[(0, 6), (7, 14)], w=880),
    'v2e': dict(rows=[(0, 9), (10, 13), (13, 18)], w=860, redact={7, 8, 9}),
    'v2f': dict(rows=[(0, 4), (4, 8), (9, 18)], w=880),
    'v2g': dict(rows=[(0, 2), (3, 10), (11, 17)], w=860),
    'v2h': dict(rows=[(0, 18), (19, 22), (23, 30)], w=880, lat_k=1.1),
    'v2i': dict(rows=[(0, 3), (3, 22), (23, 31)], w=880, lat_k=1.1, st=dict(inn='flick')),
    'v2j': dict(rows=[(0, 6), (7, 12), (13, 20)], w=880),
    'v2k': dict(rows=[(0, 7), (8, 15)], w=900, row_dx=[-60, 60]),
    'v2l': dict(rows=[(0, 3), (4, 10), (11, 19)], w=880, plug_units={12, 13}),
    'v2m': dict(rows=[(0, 5), (5, 9), (10, 18)], w=880),
    'v2n': dict(rows=[(0, 4), (4, 8), (9, 14)], w=860),
    'v2o': dict(rows=[(0, 9), (10, 15), (15, 20)], w=900, st=dict(out='dim', dout=0.2)),
    # ---- build: call and response, the camera climbs closer each line
    'b1': dict(rows=[(0, 4), (4, 10), (11, 28)], row_sizes=[110, None, None], w=880, z=0.92),
    'b2': dict(rows=[(0, 5), (5, 10), (11, 30)], row_sizes=[110, None, None], w=880, z=0.98),
    'b3': dict(rows=[(0, 4), (4, 9), (10, 27)], row_sizes=[110, None, None], w=880, z=1.04),
    'b4': dict(rows=[(0, 4), (4, 10), (11, 25)], row_sizes=[110, None, None], w=880, z=1.1),
    'b5': dict(rows=[(0, 5), (5, 14), (15, 20), (20, 32)], row_sizes=[None, 150, None, 150], w=860,
               z=1.12),
    'b6': dict(rows=[(0, 6), (7, 14)], w=900, st=dict(slam_units={1, 2, 3}, kin=1.5, out='dim', dout=0.1), z=1.15),
    # ---- drop
    'd1': dict(rows=[(0, 6), (7, 18), (19, 25), (26, 37)], row_sizes=[None, 110, None, 110],
               w=1000, pos=(DCX, DY0 + 1000),
               rot=-2.5, st=dict(inn='slam', kin=1.6, out='shatter', dout=0.25)),
    'd2': dict(rows=[(0, 6), (7, 18), (19, 25), (26, 37)], row_sizes=[None, 110, None, 110],
               w=1000, pos=(DCX, DY0 + 1500),
               rot=2.5, st=dict(inn='slam', kin=1.6, out='shatter', dout=0.25)),
    'd3': dict(rows=[(0, 6), (7, 14), (15, 22), (23, 27)], w=820, pos=(DCX, DY0 + 1000), rot=-2.0,
               st=dict(inn='slam', kin=1.6, out='shatter', dout=0.25)),
    'd4': dict(rows=[(0, 6), (7, 14), (15, 22), (23, 27)], w=820, pos=(DCX, DY0 + 1500), rot=2.0,
               st=dict(inn='slam', kin=1.6, out='dim', dout=0.2)),
    # ---- Taipei: the city lights up across the water; the wall of light is the tower
    't1': dict(rows=[(0, 6), (7, 15)], w=1400, pos=(1150, 330), cam='tower',
               st=dict(inn='fade', din=0.5, flash=0.2)),
    't2': dict(rows=[(0, 5), (6, 9)], w=560, pos=(1150, 780), camt=(1.45, 1150, 1080, 0.0),
               st=dict(inn='fade', din=0.4, flash=0.2),
               sub=[dict(rows=[(10, 17), (18, 23), (24, 31)], w=330, pos=(1150, 1150), led=True,
                         st=dict(inn='flick', flash=1.0, level=2.1))]),
    't3': dict(rows=[(0, 8)], w=560, pos=(1150, 1420), camt=(1.45, 1150, 1640, 0.0),
               st=dict(inn='fade', din=0.4, flash=0.2),
               sub=[dict(rows=[(9, 16), (17, 26)], w=330, pos=(1150, 1720), led=True,
                         st=dict(inn='flick', flash=1.0, level=2.1))]),
    't4': dict(rows=[(0, 5), (5, 12)], w=1300, pos=(1150, 330), cam='tower', st=dict(inn='fade', din=0.4, flash=0.2)),
    # ---- verse 3: the board room; the market cracks the door
    'v3a': dict(rows=[(0, 5), (6, 9), (10, 14)], w=860),
    'v3b': dict(rows=[(0, 3), (3, 10), (11, 18)], w=880),
    'v3c': dict(rows=[(0, 14), (15, 18), (19, 23)], w=880),
    'v3d': dict(rows=[(0, 5), (6, 9), (10, 16)], w=860),
    'v3e': dict(rows=[(0, 5), (6, 13), (14, 20)], w=860),
    'v3f': dict(rows=[(0, 3), (4, 11), (12, 18)], w=880),
    'v3g': dict(rows=[(0, 5), (6, 11), (12, 19)], w=880, row_dx=[-50, 50, 0]),
    'v3h': dict(rows=[(0, 5), (5, 9), (10, 19)], w=880, st=dict(inn='flick')),
    'v3i': dict(rows=[(0, 4), (5, 8), (9, 17)], row_sizes=[None, 260, None], w=880),
    'v3j': dict(rows=[(0, 11), (12, 26), (27, 30), (31, 35)], w=860, st=dict(out='blow', dout=0.6)),
    'v3k': dict(rows=[(0, 8), (9, 15), (16, 18)], w=880, st=dict(out='drop')),
    'v3l': dict(rows=[(0, 4), (4, 9), (10, 17)], w=860, st=dict(out='drop')),
    'v3m': dict(rows=[(0, 3), (4, 11), (12, 20)], w=880),
    'v3n': dict(rows=[(0, 4), (5, 9), (10, 17)], w=860),
    'v3o': dict(rows=[(0, 3), (4, 10), (11, 18)], w=860),
    'v3p': dict(rows=[(0, 6), (7, 12), (12, 16), (17, 23)], w=860, st=dict(inn='flick', out='dim', dout=0.2)),
    # ---- bridge: the closed room in Congress; half time, the light warms
    'r1': dict(rows=[(0, 4), (5, 8), (9, 14), (15, 18)], w=820, st=dict(slam_units={4})),
    'r2': dict(rows=[(0, 7), (8, 15)], w=880, st=dict(inn='rise')),
    'r3': dict(rows=[(0, 4), (4, 12)], w=880, st=dict(inn='type'), cursor=True),
    'r4': dict(rows=[(0, 5), (5, 11)], w=860, st=dict(inn='rise'), cam='wideslow'),
    'r5': dict(rows=[(0, 6), (7, 12), (13, 17)], w=860, st=dict(inn='rise')),
    'r6': dict(rows=[(0, 13), (14, 28)], w=860, lat_k=1.15, st=dict(inn='rise')),
    'r7': dict(rows=[(0, 3), (4, 8), (9, 15)], row_sizes=[None, None, 92], row_dx=[0, 0, -75], w=760,
               diag=(2, 30, -20), gap=1.0, st=dict(inn='rise', out='dim', dout=0.4)),
    # ---- final hook
    'h2a': hook_line(33, 0, True), 'h2b': hook_line(34, 1, True), 'h2c': hook_line(35, 2, True),
    'h2d': hook_line(36, 3, True),
    'h2e': dict(rows=[(0, 3), (4, 9), (10, 13), (14, 19)], row_sizes=[250, 120, 250, 120], w=860,
                pos=(DCX, DY0 + 1000), cam='close', st=dict(slam_units={0, 1, 2, 5, 6, 7}, kin=1.4)),
    'h2f': dict(rows=[(0, 5), (6, 11)], w=860, pos=(DCX, DY0 + 380), cam='lamps', lamps=True),
    'h2g': dict(rows=[(0, 3), (4, 9), (10, 17)], w=880, pos=(DCX, DY0 + 1250)),
    'h2h': dict(rows=[(0, 10), (11, 24), (25, 43)], w=900, pos=(DCX, DY0 + 900),
                st=dict(slam_units={5, 6, 7}, kin=1.4, out='dim', dout=0.15), rewind=True),
    # ---- outro: the light stays on
    'o1': dict(rows=[(0, 4), (5, 12), (13, 26)], w=840, st=dict(inn='rise')),
    'o2': dict(rows=[(0, 7), (8, 13), (14, 19)], w=840, st=dict(inn='rise')),
    'o3': dict(rows=[(0, 6), (7, 13), (14, 20)], w=860, st=dict(inn='rise')),
    'o4': dict(rows=[(0, 5), (6, 11), (12, 17)], w=840, st=dict(inn='rise')),
    'o5': dict(rows=[(0, 5), (6, 12)], w=860, pos=(DCX, DY0 + 380), cam='lamps', lamps=True,
               st=dict(inn='rise')),
    'o6': dict(rows=[(0, 12), (13, 16), (17, 20)], w=860, pos=(DCX, DY0 + 1100), st=dict(kin=1.3)),
    'o7': dict(rows=[(0, 5), (6, 10)], w=760, pos=(DCX, DY0 + 1100),
               st=dict(inn='rise', out='dim', dout=1.6, t_out=290.9)),
    'o8': dict(rows=[(0, 5), (6, 10)], w=700, pos=(DCX, DY0 + 1150), cam='wideslow', move_start=291.6, move=5.2,
               st=dict(inn='fade', din=0.6, flash=0.3, out='dim', dout=2.0)),
}

POS_CYCLE = [(-40, 760, -1.5), (50, 1250, 1.2), (-30, 1750, -0.8), (40, 1050, 1.6), (-50, 1500, -1.2),
             (30, 2000, 0.8)]


def design(eid, idx_in_sec, sec):
    d = dict(D.get(eid, {}))
    line = TIM[eid]['line']
    if 'rows' not in d:
        d['rows'] = None
    d.setdefault('w', 880)
    if 'pos' not in d:
        dx, y, rot = POS_CYCLE[idx_in_sec % len(POS_CYCLE)]
        d['pos'] = (DCX + dx, DY0 + y)
        d.setdefault('rot', rot)
    d.setdefault('rot', 0.0)
    d.setdefault('st', {})
    d.setdefault('cam', 'close')
    d['line'] = line
    return d


class Shot:
    """A block plus everything needed to draw and frame it."""

    def __init__(self, eid, sec_k, idx):
        sec = SEC[sec_k]
        self.eid = eid
        self.sec = sec_k
        self.d = design(eid, idx, sec)
        d = self.d
        lat_k = d.get('lat_k', 1.2)
        fonts = d.get('fonts', (typo.CJK, typo.LAT))
        sl = TIM[eid]['slice']
        tt = times(eid)
        if sl:
            full = [None] * len(lyrics.units(d['line']))
            for k, v in zip(range(sl[0], sl[1]), tt):
                full[k] = v
            tt = full
        self.blk = typo.Block(d['line'], tt, rows=d['rows'], width=d['w'], maxsize=d.get('maxsize', 250),
                              pos=d['pos'], fonts=fonts, lat_k=lat_k, gap=d.get('gap', 0.16),
                              align=d.get('align', 'justify'), row_sizes=d.get('row_sizes'),
                              row_dx=d.get('row_dx'), diag=d.get('diag'))
        self.subs = []
        for sd in d.get('sub', []):
            b = typo.Block(d['line'], tt, rows=sd['rows'], width=sd['w'], maxsize=sd.get('maxsize', 250), pos=sd['pos'],
                           fonts=sd.get('fonts', fonts), lat_k=sd.get('lat_k', lat_k), row_sizes=sd.get('row_sizes'))
            self.subs.append((b, sd))
        self.t0 = self.blk.start()
        self.t1 = self.blk.end()
        self.st = dict(d['st'])
        if d.get('plug_units'):
            pu = d['plug_units']
            self.st['plug'] = (pu, max(tt[u][1] for u in pu if tt[u]) + 0.35)

    def target(self):
        """Camera target that frames this block."""
        cx, cy = self.blk.centre()
        kind = self.d['cam']
        if 'camt' in self.d:
            return self.d['camt']
        if kind == 'wide' or kind == 'wideslow':
            return (0.6, DCX, DY0 + 1330, 0.0)
        if kind == 'tower':
            return (0.55, 1150, 1500, 0.0)
        if kind == 'lamps':
            return (0.78, DCX, DY0 + 420, 0.0)
        z = min(0.86 * W / self.blk.width * self.d.get('z', 1.0), 0.94 * W / self.blk.width)
        hz = 0.66 * H / max(self.blk.bh, 1)
        z = min(z, hz)
        if kind == 'mid':
            z *= 0.8
        return (z, cx, cy + self.d.get('cy', 0), self.d['rot'])


SHOTS = []
for k, s in enumerate(SEC):
    if s[2] == 'tower':
        pass
    for i, eid in enumerate(entries_of(s[0])):
        SHOTS.append(Shot(eid, k, i))
for i, sh in enumerate(SHOTS):
    nxt = SHOTS[i + 1] if i + 1 < len(SHOTS) else None
    sec_end = SEC_T1[sh.sec]
    if nxt is not None and nxt.sec == sh.sec:
        sh.st.setdefault('t_out', nxt.t0 - 0.12)
    else:
        sh.st.setdefault('t_out', min(sec_end - 0.18, max(sh.t1 + 0.3, sec_end - 0.6)))
    sh.st.setdefault('dout', 0.3)
SHOT_T = np.array([s.t0 for s in SHOTS])
CAM_T = np.array([s.d.get('move_start', s.t0 - 0.3) for s in SHOTS])


def shots_at(t):
    out = []
    for s in SHOTS:
        if s.t0 - 0.3 <= t <= s.st['t_out'] + s.st['dout'] + 2.5:
            out.append(s)
    return out


def camera(t):
    """Eased moves between shot targets, plus slow push, kick bumps and (in hooks) shake."""
    i = int(np.searchsorted(CAM_T, t, side='right') - 1)
    if i < 0:
        # opening: from the whole closed door in the dark, a slow push to where the first line will be
        tgt = SHOTS[0].target()
        e = smooth(t / CAM_T[0])
        wide = (0.6, DCX, DY0 + 1330, 0.0)
        return tuple(wide[k] + (tgt[k] - wide[k]) * e for k in range(4))
    cur = SHOTS[i]
    tg = cur.target()
    prev = SHOTS[i - 1] if i > 0 else None
    move = cur.d.get('move', 0.32)
    a0 = CAM_T[i]
    if prev is not None and prev.sec == cur.sec and t < a0 + move:
        pg = prev.target()
        # where the previous shot's slow push had got to
        pg = (pg[0] * (1 + 0.03 * clamp01((a0 - prev.t0) / 3.0)), pg[1], pg[2], pg[3])
        e = ease_out((t - a0) / move, 4) if move < 1 else smooth((t - a0) / move)
        tg = tuple(pg[k] + (tg[k] - pg[k]) * e for k in range(4))
    z, cx, cy, r = tg
    # slow push while the line is up
    if move < 1:
        z *= 1 + 0.03 * clamp01((t - cur.t0) / 3.0)
    name = SEC[cur.sec][0]
    kb = pulse(KICKS, t, 0.11)
    if name in ('verse1', 'verse2', 'verse3', 'hook1', 'hook2', 'drop', 'build'):
        z *= 1 + 0.012 * kb
    sh = 0.0
    if name in ('hook1', 'hook2', 'drop'):
        sh = 14 * kb + 10 * pulse(SNARES, t, 0.09)
    if sh:
        cx += (hash01(int(t * 30), 1) - 0.5) * sh / z
        cy += (hash01(int(t * 30), 2) - 0.5) * sh / z
        r += (hash01(int(t * 30), 3) - 0.5) * sh * 0.05
    return (z, cx, cy, r)
