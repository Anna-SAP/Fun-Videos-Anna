"""The whole film as a list of shots: which line is on screen when, in which look, set in which rows.

Lyric text is never written here: lines are referred to by their index in the sheet and tokens by position
(the sheet itself stays in work/src/, outside the repository).
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beat as B  # noqa: E402
from base import LEAD, Line  # noqa: E402
from kit import H, W  # noqa: E402
from lyrics import parse  # noqa: E402
from typo import auto_rows, tokens  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'work', 'src', 'lyrics.txt')
TIMING = os.path.join(ROOT, 'work', 'audio', 'lyric_timing.json')
SECS, LINES = parse(SHEET)
TOK = {l['i']: tokens(l) for l in LINES}
DUR = 266.448


def R(spec):
    """rows spec '0-1|2|3-5' -> [[0,1],[2],[3,4,5]]"""
    rows = []
    for part in spec.split('|'):
        row = []
        for seg in part.split():
            if '-' in seg:
                a, b = seg.split('-')
                row += list(range(int(a), int(b) + 1))
            else:
                row.append(int(seg))
        rows.append(row)
    return rows


# ---- rows per sheet line (token positions). Lines not listed use the sheet's own phrase breaks.
ROWS = {
    0: '0|1|2', 1: '0|1|2', 2: '0-1|2|3-4|5', 3: '0|1|2|3',
    10: '0-3|4-8|9-12|13-14', 11: '0-1|2-3|4-7|8-10|11-15', 12: '0-3|4-7|8-12|13-15', 13: '0-4|5-9|10-11|12-13',
    14: '0-4|5-8|9-12', 15: '0-3|4-7|8-10|11-15', 16: '0-3|4|5-6|7-10|11-14', 17: '0-3|4-7|8-11|12-16',
    18: '0-1|2-5|6-10|11-14|15-18', 19: '0-3|4-6|7-11|12-13|14-17', 20: '0-3|4-7|8-9|10-13|14-16',
    21: '0-3|4-9|10-14',
    22: '0-3|4-7|8-14', 23: '0|1|2',
    24: '0-1|2-7|8-10|11-14', 25: '0-3|4-7|8-13|14-17', 26: '0-5|6-10|11-13', 27: '0-4|5-9|10-13|14-16',
    28: '0|1|2-7|8-13', 29: '0-2|3-6|7-8|9-12', 30: '0-1|2-5|6-9|10-12|13-15', 31: '0-3|4-6|7-10|11-13',
    32: '0-4|5-8|9-13|14-18', 33: '0-3|4-6|7-10|11-16', 34: '0-3|4-7|8-12|13-15', 35: '0-2|3|4-7|8-9',
    36: '0-2|3-4', 37: '0-2|3-6|7-8', 38: '0-1|2|3-4|5', 39: '0|1|2|3',
    40: '0|1|2-3', 41: '0|1|2|3-4', 42: '0-4|5-6', 43: '0-2|3-6',
    44: '0-4|5-8|9-10|11-13', 45: '0-4|5-8|9-11|12-15|16-18', 46: '0-3|4-5|6-8|9-14', 47: '0-1|2-5|6-8|9-12|13-16',
    48: '0-1|2-6|7-11|12-14|15-17', 49: '0-3|4-8|9-10|11-15|16-19', 50: '0-5|6-10|11-14|15-17', 51: '0|1-5|6-8|9-11',
    52: '0-3|4-6|7-10|11-13', 53: '0-2|3-6|7-11', 54: '0-4|5-7|8-12|13-15|16-19|20-22', 55: '0-4|5-7|8-9|10-14|15-17|18-20',
    56: '0-4|5-7|8-10', 57: '0-4|5-8',
    58: '0-3|4-7|8-10|11-14', 59: '0-3|4-6|7-9|10-14', 60: '0-1|2-5|6-11', 61: '0-2|3-6|7-9|10-13', 62: '0-3|4-6|7-11|12-14', 63: '0-1|2-5',
    70: '0-4|5-9|10-13', 71: '0-2|3-9', 72: '0|1|2', 73: '0-3|4-5|6-7',
}
for _i in (4, 5, 6):
    ROWS[_i] = None      # the hooks are composed by hand in look_hook
for _i in range(64, 70):
    ROWS[_i] = None


def rows_of(i):
    spec = ROWS.get(i)
    if spec:
        rows = R(spec)
        flat = [x for r in rows for x in r]
        assert flat == list(range(len(TOK[i]))), (i, flat, len(TOK[i]))
        return rows
    return auto_rows(TOK[i])


# ---- timing
def provisional():
    """before the real alignment exists: one line per bar from the bar structure (development only)."""
    bars = {}
    plan = [(0, [0.3, 1.8, 2.9, 4.0]), (5, None)]
    seq = {0: 1.0, 1: 6.6, 2: 9.8, 3: 12.9}
    b = 5
    for i in range(4, 10):
        seq[i] = b * 3.2
        b += 1
    b = 13
    for i in range(10, 22):
        seq[i] = b * 3.2
        b += 1
    seq[22], seq[23] = 80.0, 83.4
    b = 27
    for i in range(24, 36):
        seq[i] = b * 3.2
        b += 1
    for k, i in enumerate(range(36, 40)):
        seq[i] = (39 + k) * 3.2
    for k, i in enumerate(range(40, 44)):
        seq[i] = (43 + k) * 3.2
    for k, i in enumerate(range(44, 56)):
        seq[i] = (47 + k) * 3.2
    seq[56], seq[57] = 188.8, 192.0
    for k, i in enumerate(range(58, 64)):
        seq[i] = (61 + k) * 3.2
    for k, i in enumerate(range(64, 70)):
        seq[i] = (67 + k) * 3.2
    for k, i in enumerate(range(70, 74)):
        seq[i] = (75 + k) * 3.2
    perfs = []
    for i in sorted(seq):
        n = len(TOK[i])
        span = min(2.9, 0.22 * n + 0.4)
        perfs.append({'line': i, 't': [round(seq[i] + 0.05 + span * k / max(n, 1), 3) for k in range(n)], 'end': seq[i] + span + 0.2})
    return perfs


def load_perfs():
    if os.path.exists(TIMING) and not os.environ.get('PROVISIONAL'):
        return json.load(open(TIMING))['perfs']
    return provisional()


PERFS = load_perfs()
SEC_OF = {l['i']: l['sec'] for l in LINES}
SEC_NAMES = ['intro', 'hook', 'v1', 'pre', 'v2', 'build', 'drop', 'v3', 'bridge', 'hook2', 'outro']


class Shot:
    pass


def cut_time(t_first):
    """cut on the downbeat when the line starts just after it, otherwise just ahead of the first syllable."""
    b = np.floor((t_first + 0.02) / B.BAR) * B.BAR
    if t_first - b <= 0.45:
        return float(b)
    return t_first - 0.07


def build():
    import look_bridge
    import look_drop
    import look_hook
    import look_intro
    import look_paper
    import look_crash
    LOOK = {'intro': look_intro.intro, 'hook': look_hook.hook, 'v1': look_paper.paper_line, 'pre': look_bridge.pre,
            'v2': look_crash.crash, 'build': look_drop.build, 'drop': look_drop.drop, 'v3': look_paper.paper_line,
            'bridge': look_bridge.bridge, 'hook2': look_hook.hook, 'outro': look_intro.outro}
    shots = []
    for k, pf in enumerate(PERFS):
        i = pf['line']
        s = Shot()
        s.k, s.i = k, i
        s.sec = SEC_NAMES[SEC_OF[i]]
        s.line = Line(i, TOK[i], [pf['t'][tk['u']] for tk in TOK[i]], pf.get('end', max(pf['t']) + 0.4))
        s.rows = rows_of(i) if ROWS.get(i, 'x') is not None else None
        s.fn = LOOK[s.sec]
        s.t0 = cut_time(s.line.t0) if 't0' not in pf else pf['t0']
        shots.append(s)
    shots.sort(key=lambda s: s.line.t0)
    # a cut never lands on top of the previous line's last syllable
    for a, b in zip(shots, shots[1:]):
        b.t0 = min(max(b.t0, max(a.line.times) + 0.30), b.line.t0 - 0.05)
    for a, b in zip(shots, shots[1:]):
        a.t1 = b.t0
        a.next = b
        b.prev = a
    shots[0].prev = None
    shots[-1].t1 = DUR + 1
    shots[-1].next = None
    # index within the section, and how many lines the section has
    cnt = {}
    for s in shots:
        s.n = cnt.get(s.sec, 0)
        cnt[s.sec] = s.n + 1
    for s in shots:
        s.of = cnt[s.sec]
    return shots


_SHOTS = None


def shots():
    global _SHOTS
    if _SHOTS is None:
        _SHOTS = build()
    return _SHOTS


def shot_at(t):
    ss = shots()
    lo, hi = 0, len(ss) - 1
    if t < ss[0].t0:
        return None
    while lo < hi:
        m = (lo + hi + 1) // 2
        if ss[m].t0 <= t:
            lo = m
        else:
            hi = m - 1
    return ss[lo]


def frame(t, fi):
    import look_intro
    s = shot_at(t)
    if s is None:
        return look_intro.cold_open(t, fi, shots()[0])
    return s.fn(t, fi, s)
