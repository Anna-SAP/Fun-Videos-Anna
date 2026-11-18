"""The film as data: what lands where and when on the wall, where the camera looks, how the hall is lit.

The wall (board pitches; a row is RATIO pitches tall):
  row 0         sign flaps: 厦门高崎国际机场 ............................ 出发 DEPARTURES
  rows 1-4      the counter: two big digit modules, the date on its left, 天 / DAYS LEFT on its right
  rows 6-11     the panel (flaps 1.5x larger): intro, pre-choruses, choruses, drop, bridge, build and outro
  rows 13-50    the year: four blocks ten pitches wide; verses land here line by line and stay

Story of the wall, from the lyric:
  - every verse line of the year lands in the list and stays, so the wall fills up with 2026;
  - at the end of line 73 (the "one key, cleared" line) everything on the list flips back to blank in one
    wave, except that line;
  - the rest of verse 3 lands on the empty wall;
  - at "rewrite" in the last chorus (line 104) the whole list rewrites itself: every verse and bridge line
    of the year, compact, in order; on line 105 the camera pulls back to show all of it;
  - the counter reads 43 the whole night; the drop's 42s flip it down and back; at the outro's "tomorrow"
    line (112), at dawn, it flips to 42 for good.

Lyric text is read from the user's sheet (work/lyrics.txt); this file refers to lines by index only.
"""
import json
import math

import numpy as np

from layout import layout_line
from lyrics import parse
from wall import Board, RATIO, INF

BAR = 60 / 90 * 4
DOWN0 = 0.762


def bar(n):
    """start of bar n (1-based, as in work/audio/structure.txt)."""
    return DOWN0 + (n - 1) * BAR


SECTIONS = [('intro', 0.0, 16.76), ('v1', 16.76, 62.0), ('pre1', 62.0, 72.76), ('ch1', 72.76, 93.95),
            ('v2', 93.95, 136.6), ('pre2', 136.6, 147.43), ('ch2', 147.43, 168.76), ('drop', 168.76, 179.43),
            ('v3', 179.43, 224.45), ('bridge', 224.45, 246.09), ('build', 246.09, 256.76),
            ('fch', 256.76, 291.0), ('outro', 291.0, 330.0)]


def section(t):
    for nm, a, b in SECTIONS:
        if a <= t < b:
            return nm
    return 'outro'


# geometry
WW = 45
BLOCK_X = (1, 12, 23, 34)
BW = 10
LIST_Y0, LIST_Y1 = 13, 51
PANEL = (16.5, 6, 28.5, 12)          # x0, row0, x1, row1 (exclusive)
PS = 1.5                             # the panel's flaps are 1.5x the wall's
D1 = (18.4, 1, 4.0, 4)               # counter digit modules: x, row, w, h
D2 = (22.6, 1, 4.0, 4)
DAY = (27.0, 3, 1.4, 2)              # 天 module
TOTAL_ROWS = LIST_Y1

PANEL_LINES = list(range(0, 4)) + list(range(20, 32)) + list(range(48, 68)) + list(range(86, 114))
LIVE_PRE = list(range(4, 20)) + list(range(32, 48)) + list(range(68, 74))   # land before the wipe
LIVE_POST = list(range(74, 86))                                              # after the wipe
FINAL = list(range(4, 20)) + list(range(32, 48)) + list(range(68, 94))      # the rewritten year
WIPE_LINE = 73
REWRITE_LINE = 104
RESPAWN_LINE = 105

WRAP = {8: {1: 3}, 12: {0: 2}, 70: {1: 5}, 87: {0: 8}, 109: {1: 2}}           # line -> {phrase: break offset}
GROUP = {}
# repeated shouts heard in the recording but written once in the sheet: line -> [(units, time), ...]
# (filled from the onset lists in timing_seen.py; see storyboard section 4)
ECHO = {22: [({6}, 70.16), ({6}, 70.75)],                  # (No!) shouted three times
        50: [({6}, 145.10), ({6}, 145.85)],                 # (No!) again, three times
        67: [({0}, 178.52)],
        106: [({0}, 285.16), ({0}, 285.83)],               # the chopped Countdown sample
        113: [({0}, 319.35), ({0}, 321.70), ({1}, 327.00), ({2}, 327.45)]}   # the closing call, repeated


def load_timing(path):
    d = json.load(open(path))
    return {r['i']: r['units'] for r in d['lines'] if r.get('units')}


class Film:
    def __init__(self, sheet='work/lyrics.txt', timing='work/audio/lyric_timing.json'):
        self.secs, self.lines = parse(sheet)
        self.T = load_timing(timing)
        self.board = Board()
        self.place = {}          # line -> dict(x, y, w, n, cells)
        self.cam_keys = []       # (t_arrive, move_dur, cx, cy, vw, roll, tilt_x, tilt_y)
        self.focus = []          # (t, rect pitches) where the key light sits
        self.events = {}
        self.kicks = np.load('work/audio/env.npz')
        self.compose()

    # ---------------------------------------------------------------- timing helpers
    def u(self, li, ui):
        return self.T[li][ui]

    def start(self, li):
        return self.T[li][0][0]

    def end(self, li):
        return max(e for s, e in self.T[li])

    def land_times(self, li, slots):
        """per slot: when it lands. Latin letters spread over their word, punctuation rides its unit."""
        line = self.lines[li]
        out = []
        for k, (dx, r, w, ch, ui, kind) in enumerate(slots):
            s, e = self.T[li][ui]
            tok = line['units'][ui][0]
            if len(tok) > 1 and ch.isascii() and ch.isalnum():
                letters = [j for j, sl in enumerate(slots) if sl[4] == ui and sl[3].isascii() and sl[3].isalnum()]
                idx = letters.index(k)
                span = min(max(e - s, 0.12), 0.06 * len(letters) + 0.12)
                out.append(s + span * idx / len(letters))
            elif ch.isascii() and not ch.isalnum() or ch in '《》“”…':
                if ch in '(《"“':
                    out.append(s - 0.03)
                else:
                    out.append(min(e, s + 0.3) + 0.02)
            else:
                out.append(s)
        return out

    @staticmethod
    def style_of(line, slot):
        dx, r, w, ch, ui, kind = slot
        tok = line['units'][ui][0]
        if tok == 'AI':
            return 'r'
        if tok in ('Reset', 'Respawn') or (kind == 'back' and ch in '重启'):
            return 'g'
        if kind == 'back':
            return 'a'
        return 'w'

    # ---------------------------------------------------------------- placement
    def put(self, li, x0, y0, slots, t_on, t_off=INF, early=0.0, steps=3, step=0.05, sc=1.0):
        """place a line's slots; each cell is born just before its own spin starts (cells sharing one blank
        flap of the grid are born together), so the wall does not show the line's shape before it is sung."""
        line = self.lines[li]
        lt = self.land_times(li, slots)
        cells = []
        born = {}
        for sl, T in zip(slots, lt):
            dx, r, w, ch, ui, kind = sl
            c = self.board.add(x0 + dx * sc, y0 + r * sc, w * sc, sc, t_on=t_on, t_off=t_off)
            st = self.style_of(line, sl)
            c.target(T - early, ch, st, steps=steps, step=step)
            cells.append((c, T - early, ch, st))
            g = (int(np.floor(dx + 1e-6)), r)
            spin0 = T - early - (steps + 1) * step - 0.03
            born[g] = min(born.get(g, INF), spin0)
        for (c, T, ch, st), sl in zip(cells, slots):
            g = (int(np.floor(sl[0] + 1e-6)), sl[1])
            c.t_on = max(t_on, born[g])
        return cells

    def clear(self, cells, T, spread=0.25, order='ltr', steps=1):
        """flip a placement back to blank starting at T; returns when the last cell is blank."""
        if not cells:
            return T
        xs = [c.x + c.y * 0.35 for c, *_ in cells]
        lo, hi = min(xs), max(xs)
        last = T
        for (c, *_), x in zip(cells, xs):
            d = 0 if hi == lo else (x - lo) / (hi - lo) * spread
            if order == 'rtl':
                d = spread - d
            tt = T + d + (steps + 1) * 0.05
            c.target(tt, ' ', 'k', steps=steps, step=0.05)
            c.t_off = tt + 0.01
            last = max(last, tt)
        return last

    # ---------------------------------------------------------------- the wall's story
    def compose(self):
        L = self.lines
        b = self.board
        # --- counter, date, sign: modules that live all film long
        self.d1 = b.add(D1[0], D1[1], D1[2], D1[3])
        self.d2 = b.add(D2[0], D2[1], D2[2], D2[3])
        self.day = b.add(DAY[0], DAY[1], DAY[2], DAY[3])

        # --- panel lines (intro, pre, chorus, drop, bridge, build, outro)
        pl = [i for i in PANEL_LINES if i in self.T]
        t_ins = {}
        for k, li in enumerate(pl):
            t_ins[li] = self.start(li) - 0.42
        for k, li in enumerate(pl):
            PW = (PANEL[2] - PANEL[0]) / PS
            slots, w, n = layout_line(L[li], maxw=PW, wrap=WRAP.get(li), merge_short=2.6, back_align='centre')
            # centre each row inside the panel, centre the block vertically
            rows = {}
            for s in slots:
                rows.setdefault(s[1], []).append(s)
            cslots = []
            for r, rs in rows.items():
                rw = max(s[0] + s[2] for s in rs) - min(s[0] for s in rs)
                off = round((PW - rw) / 2 * 2) / 2 - min(s[0] for s in rs)
                cslots += [(s[0] + off, s[1], s[2], s[3], s[4], s[5]) for s in rs]
            PR = int(round((PANEL[3] - PANEL[1]) / PS))
            assert n <= PR, ('panel overflow', li, n)
            y0 = PANEL[1] + ((PR - n) // 2) * PS
            t_in = t_ins[li]
            nxt = pl[k + 1] if k + 1 < len(pl) else None
            cells = self.put(li, PANEL[0], y0, cslots, t_on=t_in, sc=PS)
            self.place[li] = dict(x=PANEL[0], y=y0, w=PANEL[2] - PANEL[0], n=n, cells=cells, where='panel',
                                  units=[sl[4] for sl in cslots])

        # the panel keeps a line whole until the next one starts: the old row under the next line's first
        # row flips away just before that row's flaps start spinning, the rest of the old line goes the moment
        # the next line's first syllable lands; a line left alone for long clears after 7 s
        for k, li in enumerate(pl[:-1]):
            nxt = pl[k + 1]
            old = self.place[li]['cells']
            new = self.place[nxt]['cells']
            rows_new = {}
            for c, T, ch, st in new:
                rows_new.setdefault(round(c.y, 3), []).append(c.t_on)
            T0 = min(T for c, T, ch, st in new)
            for c, T, ch, st in old:
                hit = [min(v) for y, v in rows_new.items() if y < c.y + c.h - 1e-6 and y + PS > c.y + 1e-6]
                tb = min(hit + [T0 + 0.1])
                tb = min(tb, max(self.end(li) + 7.0, T + 1.0))
                tt = tb - 0.03 - 0.12 * ((c.x - PANEL[0]) / (PANEL[2] - PANEL[0]))
                tt = max(tt, T + 0.2)        # never before the flap has shown its character
                c.target(tt, ' ', 'k', steps=1, step=0.05)
                c.t_off = tt + 0.005

        # --- echoes: a shout sung again re-flips the same flaps (nothing is added to the text)
        for li, reps in ECHO.items():
            if li not in self.place:
                continue
            cells = self.place[li]['cells']
            slots_units = [c[0] for c in cells]
            for ui_list, T in reps:
                j = 0
                for (c, Tl, ch, st), sl_u in zip(cells, self.place[li]['units']):
                    if sl_u in ui_list and c.t_on < T - 0.3 < T + 0.1 < c.t_off and T > Tl + 0.2:
                        c.target(T + 0.03 * j, ch, st, steps=3, step=0.045)
                        j += 1

        # --- live list, before the wipe
        y = LIST_Y0
        blk = 0
        self.wipe_T = self.T[WIPE_LINE][-1][0] + 0.15
        for li in LIVE_PRE + ['WIPE'] + LIVE_POST:
            if li == 'WIPE':
                self.do_wipe()
                y, blk = LIST_Y0, 0
                continue
            if li not in self.T:
                continue
            slots, w, n = layout_line(L[li], maxw=BW, wrap=WRAP.get(li), merge_short=2.6)
            if y + n > LIST_Y1:
                blk += 1
                y = LIST_Y0
            assert blk < 4, ('list overflow at line', li)
            x0 = BLOCK_X[blk]
            t_on = self.start(li) - 0.6
            cells = self.put(li, x0, y, slots, t_on=t_on)
            self.place[li] = dict(x=x0, y=y, w=w, n=n, cells=cells, where='list', blk=blk)
            y += n + 1

        # --- line 85 ends "revised once, and again": on 又, its words already written flip once more
        li = 85
        if li in self.place:
            units = self.lines[li]['units']
            k = [j for j, u in enumerate(units) if u[0] == '又'][0]
            T = self.T[li][k][0]
            for j, (c, Tl, ch, st) in enumerate(self.place[li]['cells']):
                if Tl < T - 0.25 and c.t_on < T < c.t_off:
                    c.target(T + 0.035 * j, ch, st, steps=3, step=0.045)

        # --- the rewrite: the whole year, compact
        self.do_rewrite()

        # --- counter and decorations
        self.counter_story()

        # background flaps everywhere else
        ex = [(D1[0], D1[1], D2[0] + D2[2], D1[1] + D1[3]), (DAY[0], DAY[1], DAY[0] + DAY[2], DAY[1] + DAY[3])]
        self.decorations()
        b.fill_background(PANEL[0], PANEL[2], PANEL[1], PANEL[3], sx=PS, sy=PS)
        ex.append((PANEL[0], PANEL[1], PANEL[2], PANEL[3]))
        b.fill_background(0, WW, 0, TOTAL_ROWS, exclude=ex)
        self.waves()
        b.build()
        self.camera_story()

    def list_cells_alive(self, t):
        out = []
        for li, p in self.place.items():
            if p['where'] != 'list':
                continue
            for c, T, ch, st in p['cells']:
                if c.t_on <= t < c.t_off:
                    out.append((li, c))
        return out

    def do_wipe(self):
        """line 73 ("one key, cleared"): every line on the list except this one flips to blank, in a wave."""
        p = self.place[WIPE_LINE]
        cx, cy = p['x'] + p['w'] / 2, (p['y'] + p['n'] / 2) * RATIO
        T0 = self.wipe_T
        self.events['wipe'] = T0
        far = 0
        for li, c in self.list_cells_alive(T0):
            if li == WIPE_LINE:
                continue
            d = math.hypot(c.x + c.w / 2 - cx, (c.y + 0.5) * RATIO - cy)
            far = max(far, d)
            tt = T0 + 0.05 + d / 38.0
            c.target(tt, ' ', 'k', steps=2, step=0.05)
            c.t_off = tt + 0.01
        self.events['wipe_end'] = T0 + 0.05 + far / 38.0

    def final_layout(self):
        """slots of the rewritten year: block by block, phrases packed, a blank row between sections."""
        out = []
        y, blk = LIST_Y0, 0
        prev_sec = None
        for li in FINAL:
            if li not in self.T:
                continue
            line = self.lines[li]
            slots, w, n = layout_line(line, maxw=BW, wrap=WRAP.get(li), merge_short=99)
            if prev_sec is not None and line['sec'] != prev_sec:
                y += 1
            prev_sec = line['sec']
            if y + n > LIST_Y1:
                blk += 1
                y = LIST_Y0
            assert blk < 4, ('final overflow', li)
            out.append((li, BLOCK_X[blk], y, slots, n))
            y += n
        return out

    def do_rewrite(self):
        """line 104 ("rewrite"): the list rewrites itself as the whole year, in a diagonal wave from the top left."""
        units = self.lines[REWRITE_LINE]['units']
        k = [j for j, u in enumerate(units) if u[0] == '重'][0]
        T0 = self.T[REWRITE_LINE][k][0]
        self.events['rewrite'] = T0
        speed = 26.0
        def tw(x, y):
            return T0 + (x * 0.55 + y * RATIO * 0.75) / speed
        # old content leaves
        for li, c in self.list_cells_alive(T0):
            tt = tw(c.x, c.y - LIST_Y0)
            c.target(tt, ' ', 'k', steps=1, step=0.05)
            c.t_off = tt + 0.01
        last = T0
        self.final = {}
        for li, x0, y0, slots, n in self.final_layout():
            line = self.lines[li]
            cells = []
            for sl in slots:
                dx, r, w, ch, ui, kind = sl
                x, yy = x0 + dx, y0 + r
                tt = tw(x, yy - LIST_Y0) + 0.06
                c = self.board.add(x, yy, w, 1.0, t_on=tt - 0.05, t_off=INF)
                st = self.style_of(line, sl)
                c.target(tt + 0.25, ch, st, steps=4, step=0.05)
                cells.append((c, tt + 0.25, ch, st))
                last = max(last, tt + 0.25)
            self.final[li] = dict(x=x0, y=y0, n=n, cells=cells)
        self.events['rewrite_end'] = last

    def counter_story(self):
        d1, d2, day = self.d1, self.d2, self.day
        # intro: the robot voice counts; the counter wakes and lands 4, 3 on each count
        t0 = self.T.get(0)
        if t0:
            d1.target(t0[0][0] + 0.10, '4', 'a', steps=8, step=0.06)
            d2.target(t0[0][1] - 0.05 if len(t0[0]) > 1 else t0[0][0] + 0.35, '3', 'a', steps=10, step=0.06)
            if len(t0) > 1:
                d1.target(t0[1][0] + 0.10, '4', 'a', steps=3, step=0.06)
                d2.target(t0[1][0] + 0.40, '3', 'a', steps=3, step=0.06)
        # line 2 ("43 days left"): 天 lands with its word, the digits re-land on the sung number
        if 2 in self.T:
            units = self.lines[2]['units']
            idx = [k for k, u in enumerate(units) if u[0] in '四十三天']
            if idx:
                d1.target(self.T[2][idx[0]][0] + 0.02, '4', 'a', steps=4, step=0.05)
                d2.target(self.T[2][idx[2]][0] + 0.02, '3', 'a', steps=4, step=0.05)
                day.target(self.T[2][idx[3]][0] + 0.02, '天', 'a', steps=5, step=0.05)
        # every chorus downbeat and every sung 43 in a chorus line spins the counter back to 43
        for li in (24, 26, 52, 54, 97, 99, 106, 31, 59, 104, 25, 53, 98):
            if li not in self.T:
                continue
            units = self.lines[li]['units']
            for k in range(len(units) - 2):
                if units[k][0] == '四' and units[k + 1][0] == '十' and units[k + 2][0] == '三':
                    d1.target(self.T[li][k][0] + 0.02, '4', 'a', steps=3, step=0.05)
                    d2.target(self.T[li][k + 2][0] + 0.02, '3', 'a', steps=5, step=0.05)
        for T in (bar(28), bar(56), bar(97)):
            d1.target(T, '4', 'a', steps=12, step=0.05)
            d2.target(T + 0.04, '3', 'a', steps=13, step=0.05)
        # drop: Four-three! / Four-two!
        for li, dig in ((60, '3'), (61, '2'), (64, '3'), (65, '2')):
            if li in self.T:
                s, e = self.T[li][0]
                d1.target(s + 0.02, '4', 'a', steps=3, step=0.04)
                d2.target(s + min(0.45, (e - s) * 0.6), dig, 'a', steps=5, step=0.04)
        if 67 in self.T:     # the last Reset puts it back to 43
            d2.target(self.T[67][0][0] + 0.2, '3', 'a', steps=6, step=0.05)
        # bridge, line 92 ("43 is a prime"): the counter re-lands slowly
        if 92 in self.T:
            d1.target(self.T[92][0][0] + 0.02, '4', 'a', steps=2, step=0.09)
            d2.target(self.T[92][2][0] + 0.02, '3', 'a', steps=2, step=0.09)
        # outro, lines 111-112 (today 43 / tomorrow 42)
        if 111 in self.T:
            d1.target(self.T[111][2][0] + 0.02, '4', 'a', steps=2, step=0.07)
            d2.target(self.T[111][4][0] + 0.02, '3', 'a', steps=2, step=0.07)
        if 112 in self.T:
            d2.target(self.T[112][4][0] + 0.02, '2', 'a', steps=3, step=0.08)
            self.events['forty_two'] = self.T[112][4][0]

    def decorations(self):
        """the sign row and the date: set dressing, landing with the spoken intro."""
        b = self.board
        def flap_text(x, y, text, style, T, gap=0.06, steps=4):
            cells = []
            for k, ch in enumerate(text):
                w = 0.5 if ch.isascii() else 1.0
                if ch != ' ':
                    c = b.add(x, y, w, 1.0)
                    c.target(T + k * gap, ch, style, steps=steps, step=0.05)
                    cells.append(c)
                x += w
            return cells
        t_place = self.T[1][-1][0] if 1 in self.T else 8.0
        t_year = self.T[1][0][0] if 1 in self.T else 5.0
        self.sign_cells = flap_text(1.0, 0, '厦门高崎国际机场', 'd', t_place - 0.1)
        self.sign_cells += flap_text(WW - 8.5, 0, '出发 DEPARTURES', 'd', t_place + 0.1, gap=0.03)
        self.date_cells = flap_text(12.0, 3, '2026.11.18', 'd', t_year, gap=0.12)
        self.dl_cells = flap_text(28.6, 4, 'DAYS LEFT', 'd', (self.T[2][-1][0] if 2 in self.T else 11) + 0.2, gap=0.03)

    def waves(self):
        """Reset! / Respawn!: a green wave runs over every flap; each spins and comes back to what it showed."""
        b = self.board
        trig = []
        for li in (63, 67):
            if li in self.T:
                for k, u in enumerate(self.lines[li]['units']):
                    if u[0] == 'Reset':
                        trig.append((self.T[li][k][0], 'lr'))
        self.events['waves'] = [t for t, _ in trig]
        # bridge, line 86 ("it wasn't only me"): all over the dark wall, single flaps start turning, here, there,
        # through the four lines that count the others (graduates, buyout letters, jobs, all of us)
        if 86 in self.T and 89 in self.T:
            rng = np.random.default_rng(12)
            k = [j for j, u in enumerate(self.lines[86]['units']) if u[0] == '不'][0]
            a, z = self.T[86][k][0], self.end(89) + 1.0
            self.events['others'] = (a, z)
            pool = [c for c in b.cells if c.bg and LIST_Y0 - 1 <= c.y < LIST_Y1 and c.t_on <= a and c.t_off > z]
            for j in range(900):
                c = pool[int(rng.integers(len(pool)))]
                tt = a + (z - a) * float(rng.random()) ** 0.7
                if not any(abs(r[0] - tt) < 0.9 for r in c.targets):
                    c.target(tt, ' ', 'k', steps=int(rng.integers(4, 9)), step=0.08, mid='a')

        # choruses and the drop: on every beat a few blank flaps around the header flutter and settle again
        rng = np.random.default_rng(9)
        hdr = [c for c in b.cells if c.bg and c.y < LIST_Y0 + 4]
        beat = 60 / 90
        for nm, a, z in SECTIONS:
            if nm not in ('ch1', 'ch2', 'fch', 'drop'):
                continue
            n_per = 10 if nm == 'drop' else 5
            t = a
            while t < z - 0.2:
                for c in rng.choice(len(hdr), n_per, replace=False):
                    c = hdr[c]
                    tt = t + float(rng.uniform(0.05, 0.3))
                    if c.t_on <= tt - 0.3 and tt + 0.05 < c.t_off and not any(abs(r[0] - tt) < 0.5 for r in c.targets):
                        c.target(tt, ' ', 'k', steps=int(rng.integers(2, 5)), step=0.045, mid='d')
                t += beat
        for T0, kind in trig:
            for c in b.cells:
                if c in (self.d1, self.d2, self.day):
                    continue
                if kind == 'lr':
                    d = (c.x / WW) * 0.55 + (c.y / TOTAL_ROWS) * 0.15
                else:
                    d = math.hypot(c.x - WW / 2, (c.y - 8) * RATIO) / 70.0
                tt = T0 + d + 0.25
                if not (c.t_on <= tt - 0.3 and tt + 0.05 < c.t_off):
                    continue
                if any(tt - 0.35 < r[0] <= tt + 0.45 for r in c.targets):
                    continue
                cur = c.showing(tt - 0.3)
                c.target(tt, cur[0], cur[1], steps=5, step=0.045, mid='g')

    # ---------------------------------------------------------------- camera
    def frame_rect(self, x0, y0, x1, y1, pad=1.2, vmin=8.0, vmax=14.0, above=0.0):
        w = x1 - x0 + 2 * pad
        h = (y1 - y0) * RATIO + 2 * pad
        vw = max(vmin, min(vmax, max(w, h * 9 / 16)))
        return (x0 + x1) / 2, (y0 + y1) / 2 * RATIO - above, vw

    def camera_story(self):
        K = self.cam_keys
        P = self.place
        def key(t, dur, cx, cy, vw, roll=0.0, tx=0.0, ty=0.0):
            K.append((t, dur, cx, cy, vw, roll, tx, ty))
        hdr_cx = WW / 2
        # intro: from a close look at the counter, back to the header; down to the list on "let's go"
        key(-1.0, 0.0, hdr_cx, 2.9 * RATIO, 6.2, 0.0, 0.0, 0.0)
        key(4.4, 3.6, hdr_cx, 6.3 * RATIO, 13.5, 0.0, 0.02, 0.0)
        key(11.4, 4.5, hdr_cx, 7.0 * RATIO, 15.5, 0.0, 0.03, -0.04)
        self.focus.append((-1.0, (D1[0], D1[1] * RATIO, D2[0] + D2[2], (D1[1] + D1[3]) * RATIO)))
        self.focus.append((4.4, (PANEL[0], 1 * RATIO, PANEL[2], PANEL[3] * RATIO)))
        tilt = 0.06
        prev_where = {'where': 'panel', 'blk': None}

        def timed_key(li, arrive, dur, frame, rect, far):
            """the camera may only leave once the previous line's last syllable has landed (+0.15 s); if that
            leaves too little time, the move ends a little after the new line has started."""
            lp = max(u[0] for u in self.T[li - 1]) if (li - 1) in self.T else -1e9
            start = max(arrive - dur, lp + 0.15)
            arrive2 = max(arrive, start + (0.5 if far else 0.32))
            dur2 = max(0.05, arrive2 - start)
            key(arrive2, dur2, *frame)
            self.focus.append((start, rect))

        for li in sorted(P):
            p = P[li]
            t = self.start(li)
            if p['where'] == 'list':
                x0, y0 = p['x'], p['y']
                x1, y1 = p['x'] + p['w'], p['y'] + p['n']
                vw = max(8.6, min(12.5, p['w'] + 1.9))
                vw = max(vw, ((y1 - y0) * RATIO + 3.0) * 9 / 16)
                cx = x0 - 0.95 + vw / 2
                cy = ((y0 + y1) / 2 + 0.35) * RATIO
                tilt = -tilt
                dur = 0.55 if section(t) != 'bridge' else 1.6
                if li == LIVE_POST[0]:
                    prev_where = {'where': 'list', 'blk': p['blk']}
                    continue          # framed by the wipe override below
                far = prev_where['where'] != 'list' or prev_where['blk'] != p['blk']
                timed_key(li, t - 0.12, dur, (cx, cy, vw, 0.0, 0.025, tilt),
                          (x0 - 0.2, y0 * RATIO, x1 + 0.2, y1 * RATIO), far)
                prev_where = {'where': 'list', 'blk': p['blk']}
            else:
                sec = section(t)
                x0, y0 = PANEL[0], 1
                x1, y1 = PANEL[2], PANEL[3]
                if sec in ('ch1', 'ch2', 'fch', 'drop'):
                    vw = 13.6 if li % 2 else 12.8
                    cy = 6.7 * RATIO
                    dur = 0.35
                    roll = 0.012 if li % 2 else -0.012
                elif sec in ('pre1', 'pre2', 'build'):
                    vw = 14.0
                    cy = 6.8 * RATIO
                    dur = 0.8
                    roll = 0.0
                elif sec == 'bridge':
                    vw = 13.0 if li not in (87, 88, 89) else 17.0
                    cy = 7.6 * RATIO if li not in (87, 88, 89) else 10.6 * RATIO
                    dur = 2.0 if li not in (87, 88) else 2.6
                    roll = 0.0
                elif sec == 'outro':
                    vw = 14.0
                    cy = 6.9 * RATIO
                    dur = 2.5
                    roll = 0.0
                else:
                    vw = 13.5
                    cy = 6.7 * RATIO
                    dur = 1.0
                    roll = 0.0
                if li in (0, 1, 2, 3):
                    continue
                far = prev_where['where'] != 'panel'
                timed_key(li, t - 0.2, dur, (hdr_cx, cy, vw, roll, 0.02, 0.0),
                          (PANEL[0] - 0.5, 0.6 * RATIO, PANEL[2] + 0.5, PANEL[3] * RATIO), far)
                prev_where = {'where': 'panel', 'blk': None}
        # ---- overrides: the wipe, the rewrite and respawn, the ending
        def cut_window(t0, t1):
            K[:] = [k for k in K if not (t0 < k[0] <= t1)]
            self.focus[:] = [f for f in self.focus if not (t0 < f[0] <= t1)]
        R = RATIO
        tw = self.events['wipe']
        cut_window(tw - 0.1, tw + 2.1)
        key(tw + 0.75, 0.75, WW / 2, 31 * R, 46.0, 0.0, 0.02, 0.0)
        p = P[LIVE_POST[0]]
        vw = max(8.6, min(12.5, p['w'] + 1.9))
        cx, cy = p['x'] - 0.95 + vw / 2, (p['y'] + p['n'] / 2 + 0.35) * R
        key(tw + 2.1, 1.1, cx, cy, vw, 0.0, 0.025, 0.06)
        self.focus.append((tw + 1.2, (p['x'] - 0.2, p['y'] * R, p['x'] + p['w'] + 0.2, (p['y'] + p['n']) * R)))
        self.focus.append((tw - 0.05, (0, LIST_Y0 * R, WW, LIST_Y1 * R)))
        tr = self.events['rewrite']
        t105 = self.start(RESPAWN_LINE) if RESPAWN_LINE in self.T else tr + 3
        t106 = self.start(106) if 106 in self.T else t105 + 5
        cut_window(tr - 0.1, t106 + 1.2)
        key(tr + 1.4, 1.4, WW / 2, 15.5 * R, 26.0, 0.0, 0.04, 0.0)
        key(t105 + 3.0, 1.8, WW / 2, 25.0 * R, 52.0, 0.0, 0.03, 0.0)
        key(t106 + 1.0, 1.6, hdr_cx, 6.7 * R, 13.2, 0.0, 0.02, 0.0)
        self.focus.append((tr - 0.05, (0, 0, WW, LIST_Y1 * R)))
        self.focus.append((t106 - 0.6, (PANEL[0] - 0.5, 0.6 * R, PANEL[2] + 0.5, PANEL[3] * R)))
        if 113 in self.T:
            te = self.end(113)
            cut_window(te, 1e9)
            key(te + 10.0, 9.0, WW / 2, 24.0 * R, 50.0, 0.0, 0.05, -0.03)
            self.focus.append((te + 1.0, (0, 0, WW, LIST_Y1 * R)))
        K.sort(key=lambda k: k[0])
        self.focus.sort(key=lambda f: f[0])

    def camera(self, t):
        K = self.cam_keys
        prev = K[0]
        cur = np.array(prev[2:], np.float64)
        for k in K:
            ta, dur = k[0], k[1]
            tgt = np.array(k[2:], np.float64)
            if t >= ta:
                cur = tgt
                continue
            if t > ta - dur:
                s = (t - (ta - dur)) / dur
                s = s * s * (3 - 2 * s)
                cur = cur + (tgt - cur) * s
            break
        return cur
