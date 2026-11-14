"""Lyric lines on the LED wall: layout into rows and bulb-by-bulb lighting from per-unit sung times.

A line's characters belong to timing units (one CJK character or one Latin word). A unit's bulbs switch
on column by column across the unit, starting just before its sung onset, with a short over-bright flash
(the bulb warming up) that settles to steady light. Punctuation lights with the unit before it.
"""
import re

import numpy as np

from led import GW, WHITE, row_mask

LEAD = 0.05          # light a little before the onset: the eye needs the lead
FLASH, FLASH_TAU = 0.85, 0.10


def char_units(text, units):
    """unit index for every character of text (punctuation -> previous unit, leading -> first)."""
    own = [-1] * len(text)
    for ui, (_, a, b) in enumerate(units):
        for k in range(a, b):
            own[k] = ui
    last = None
    for k in range(len(text)):
        if own[k] >= 0:
            last = own[k]
        elif last is not None:
            own[k] = last
    nxt = None
    for k in range(len(text) - 1, -1, -1):
        if own[k] >= 0:
            nxt = own[k]
        elif nxt is not None:
            own[k] = nxt
    return own


def phrases(text):
    """split points: spaces and dashes; returns list of (start, end) char ranges incl. trailing space."""
    out = []
    a = 0
    for m in re.finditer(r'\s+—\s+|\s+', text):
        out.append((a, m.start()))
        a = m.start() if '—' in m.group(0) else m.end()
    out.append((a, len(text)))
    return [(s, e) for s, e in out if text[s:e].strip()]


def layout(text, maxw, hmax, hmin=10, max_rows=3, prefer_rows=None):
    """pack phrases into rows that fit maxw bulbs; choose the biggest height <= hmax that fits in max_rows,
    allowing one more row if nothing fits. returns (h, [(start, end), ...])"""
    for mr in (max_rows, max_rows + 1, max_rows + 2):
        r = _layout(text, maxw, hmax, hmin, mr)
        if r is not None:
            return r
    return _layout(text, maxw, hmin, hmin, 99)


def _layout(text, maxw, hmax, hmin, max_rows):
    ph = phrases(text)
    for h in range(hmax, hmin - 1, -1):
        rows = []
        cur = None
        ok = True
        for s, e in ph:
            if cur is None:
                cand = (s, e)
            else:
                cand = (cur[0], e)
            if row_mask(text[cand[0]:cand[1]].strip(), h)[0].shape[1] <= maxw:
                cur = cand
            else:
                if cur is not None:
                    rows.append(cur)
                if row_mask(text[s:e].strip(), h)[0].shape[1] > maxw:
                    # split a long phrase by characters
                    k0 = s
                    for k in range(s + 1, e + 1):
                        if row_mask(text[k0:k].strip(), h)[0].shape[1] > maxw:
                            rows.append((k0, k - 1))
                            k0 = k - 1
                    cur = (k0, e)
                else:
                    cur = (s, e)
        if cur is not None:
            rows.append(cur)
        if len(rows) <= max_rows and ok:
            return h, rows
    return None


class Line:
    """one lyric line placed on the wall."""

    def __init__(self, text, units, times, x0, y0, w, hmax, hmin=10, align='center', max_rows=3, gap=4,
                 rows=None, h=None, zh_font=None, en_font=None, upper=True):
        self.text, self.units, self.times = text, units, times
        if rows is None:
            h, rows = layout(text, w, hmax, hmin, max_rows)
        self.h = h
        own = char_units(text, units)
        self.rows = []
        y = y0
        for s, e in rows:
            # strip spaces at the ends but keep the char index mapping
            while s < e and text[s] == ' ':
                s += 1
            while e > s and text[e - 1] == ' ':
                e -= 1
            seg = text[s:e]
            m, spans = row_mask(seg, h, zh_font, en_font, 0.06, upper)
            rw = m.shape[1]
            x = x0 + (w - rw) / 2 if align == 'center' else (x0 if align == 'left' else x0 + w - rw)
            # per-column on time
            on = np.full(rw, np.inf, np.float32)
            for k, (c0, c1) in enumerate(spans):
                ui = own[s + k]
                if ui < 0 or ui >= len(times):
                    continue
                us, ue = times[ui]
                # whole-word wipe for Latin words, quick per-character for CJK
                a_, b_ = units[ui][1], units[ui][2]
                first = max(a_, s) - s
                last = min(b_, e) - s - 1
                if first < 0 or last >= len(spans):
                    continue
                wx0, wx1 = spans[first][0], spans[last][1]
                wd = float(np.clip(0.5 * (ue - us), 0.05, 0.22 if (b_ - a_) > 1 else 0.10))
                cols = np.arange(int(np.floor(c0)), int(np.ceil(c1)))
                cols = cols[(cols >= 0) & (cols < rw)]
                frac = (cols + 0.5 - wx0) / max(1e-3, wx1 - wx0)
                on[cols] = np.minimum(on[cols], us - LEAD + np.clip(frac, 0, 1) * wd)
            # fill unlit gaps (spaces) with the neighbour's time so nothing stays dark by accident
            if np.isinf(on).all():
                on[:] = 1e9
            else:
                idx = np.where(np.isfinite(on))[0]
                on = np.interp(np.arange(rw), idx, on[idx]).astype(np.float32)
            self.rows.append({'mask': m, 'x': x, 'y': y, 'on': on, 's': s, 'e': e})
            y += m.shape[0] - 6 + gap
        self.height = y - y0 - gap
        self.t_on = min(float(r['on'].min()) for r in self.rows) if self.rows else 0
        self.t_end = max(t[1] for t in times) if times else 0

    def light(self, t, flash=True):
        """per-row column brightness (0..1+flash) and whiteness for the flash."""
        out = []
        for r in self.rows:
            tau = t - r['on']
            lit = (tau >= 0).astype(np.float32)
            fl = np.where(tau >= 0, np.exp(-np.maximum(tau, 0) / FLASH_TAU), 0).astype(np.float32) if flash else 0 * lit
            out.append((lit, fl))
        return out

    def draw(self, field, t, color, gain=1.0, dx=0, dy=0, flash=True, clip_rows=None):
        if gain <= 0.003:
            return
        col = np.asarray(color, np.float32)
        for r, (lit, fl) in zip(self.rows, self.light(t, flash)):
            if not lit.any():
                continue
            m = r['mask']
            x, y = int(round(r['x'] + dx)), int(round(r['y'] + dy)) - 3
            h, w = m.shape
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(GW, x + w), min(field.shape[0], y + h)
            if clip_rows is not None:
                y0, y1 = max(y0, clip_rows[0]), min(y1, clip_rows[1])
            if x1 <= x0 or y1 <= y0:
                continue
            mm = m[y0 - y:y1 - y, x0 - x:x1 - x]
            li = lit[x0 - x:x1 - x]
            ff = fl[x0 - x:x1 - x]
            amt = mm * (li * (1 + FLASH * ff))[None, :] * gain
            whit = (ff * 0.6)[None, :, None]
            field[y0:y1, x0:x1] += amt[..., None] * (col * (1 - whit) + WHITE * whit)
