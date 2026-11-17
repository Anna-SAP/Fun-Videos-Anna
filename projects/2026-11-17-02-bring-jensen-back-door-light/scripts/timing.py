#!/usr/bin/env python3
"""Final per-unit sung times: Whisper forced alignment + CTC forced alignment + vocal onsets + what was read
off the spectrogram.

  timing.py SHEET.txt WHISPER.json CTC.json OUT.json [--report]

Two aligners, two kinds of error:
  Whisper (align.py, 12 estimates per unit) is right about where a phrase starts and ends but bunches the
    characters of a word onto one instant.
  CTC (ctc_align.py, 12 estimates per unit) spaces syllables properly but lets the first and last unit of
    a line drift into the silence around it, and is lost where a choir doubles the lead (the hooks).
Per unit: take CTC when the two agree or when Whisper is bunched; take Whisper when CTC is unsure, or when
CTC puts a unit where the vocal stem is silent. Then un-bunch what is still stacked, pull every start to
the nearest syllable onset of the vocal stem (within 50 ms) and keep the order.

SEEN / PERF below are hand corrections read from onset lists and spectrograms (scripts/onsets.py,
vocal_spectrogram.py). A 'performance' is one sung pass of a sheet line; the chant at the drop is sung
several times, so its line has several. OUT.json has times only, no lyric text.
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lyrics import parse  # noqa: E402

sheet, wj, cj, out = sys.argv[1:5]
report = '--report' in sys.argv
secs, lines = parse(sheet)
Wd = {r['i']: r for r in json.load(open(wj))['lines']}
Cd = {r['i']: r for r in json.load(open(cj))['lines']}

voc, sr = sf.read('work/audio/vocals16k.wav', dtype='float32')
f, tt, Z = signal.stft(voc, sr, nperseg=1024, noverlap=1024 - 160, boundary=None, padded=False)
A = np.abs(Z[(f > 150) & (f < 6000)])
L = np.log1p(50 * A)
flux = np.concatenate([[0], np.maximum(L[:, 1:] - L[:, :-1], 0).sum(0)])
ft = (np.arange(len(flux)) * 160 + 512) / sr
flux = flux / (np.percentile(flux, 98) + 1e-9)
lev = 10 * np.log10((A ** 2).sum(0) + 1e-9)
lev = lev - np.percentile(lev, 95)


def voiced(t, win=0.10):
    """is there voice in the 100 ms after t?"""
    m = (ft >= t) & (ft <= t + win)
    return m.any() and lev[m].max() > -24


def snap(t, back=0.05, fwd=0.05, th=0.30):
    m = (ft >= t - back) & (ft <= t + fwd)
    if m.any():
        j = int(np.argmax(flux[m]))
        if flux[m][j] > th:
            return float(ft[m][j])
    return t


# ----- hand corrections --------------------------------------------------------------------------------
# (line, unit) -> start seconds, read from onsets / spectrogram
SEEN = {}
# units that are not sung in the recording (line -> unit indices)
UNSUNG = {}
# extra performances of a line: line -> list of {unit: start}
EXTRA = {}
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timing_seen.py'), encoding='utf-8').read())

HAND = dict(SEEN)
if os.environ.get('NO_SEEN'):          # for testing the automatic part against the hand-read lines
    SEEN = {}
RAP = ('Verse 1', 'Verse 2', 'Verse 3')
perfs, flags = [], []
for l in lines:
    li, n = l['i'], len(l['units'])
    if li in EXTRA and EXTRA[li] and EXTRA[li][0].get('replace'):
        continue
    w = Wd.get(li, {}).get('units')
    c = Cd.get(li, {}).get('units')
    if not w and not c:
        continue
    S = np.full(n, np.nan)
    src = [''] * n
    wsp = Wd.get(li, {}).get('spread') or [None] * n
    for u in range(n):
        wv = w[u][0] if w else None
        cv = c[u][0] if c and c[u] else None
        if (li, u) in SEEN:
            S[u], src[u] = SEEN[(li, u)], 'seen'
        elif wv is None and cv is None:
            pass
        elif wv is None and cv is not None:
            S[u], src[u] = cv, 'c'
        elif cv is None and wv is not None:
            S[u], src[u] = wv, 'w'
        elif abs(cv - wv) <= 0.09:
            S[u], src[u] = cv, 'agree'                       # an anchor
        elif l['sec_name'] not in RAP:
            # sung sections: the choir confuses CTC; keep Whisper unless it stacked this unit on its neighbour
            if not ((u > 0 and wv - w[u - 1][0] < 0.07) or (u + 1 < n and w[u + 1][0] - wv < 0.07 and u > 0)):
                S[u], src[u] = wv, 'w-sung'
        elif u == 0:
            # line starts: Whisper, unless its own estimates scatter or it points at silence
            ok_w = voiced(wv - 0.03, 0.15)
            S[u], src[u] = (wv, 'w-start') if ok_w or not voiced(cv - 0.03, 0.15) else (cv, 'c-start')
        elif u == n - 1:
            bunched = wv - w[u - 1][0] < 0.07
            if not bunched and voiced(wv - 0.03, 0.15):
                S[u], src[u] = wv, 'w-end'
    # between anchors the syllables are spread evenly (rap in steady sixteenths), then snapped to onsets
    known = [u for u in range(n) if not np.isnan(S[u])]
    if not known:
        continue
    step = None
    if len(known) > 1 and known[-1] > known[0]:
        step = (S[known[-1]] - S[known[0]]) / (known[-1] - known[0])
    step = step if step and 0.08 < step < 0.6 else 0.19
    for u in range(n):
        if not np.isnan(S[u]):
            continue
        lo = [k for k in known if k < u]
        hi = [k for k in known if k > u]
        if lo and hi:
            a_, b_ = lo[-1], hi[0]
            S[u] = S[a_] + (S[b_] - S[a_]) * (u - a_) / (b_ - a_)
        elif lo:
            S[u] = S[lo[-1]] + step * (u - lo[-1])
        else:
            S[u] = S[hi[0]] - step * (hi[0] - u)
        src[u] = 'interp'
        if w and c and c[u]:
            flags.append((li, u, round(w[u][0], 2), round(c[u][0], 2), round(float(S[u]), 2)))
    # order, un-bunch, snap
    fixed = np.array([s == 'seen' for s in src])
    for u in range(1, n):
        if S[u] < S[u - 1] + 0.02 and not fixed[u]:
            S[u] = S[u - 1] + 0.02
    u = 0
    while u < n - 1:
        v = u
        while v + 1 < n and S[v + 1] - S[v] < 0.075:
            v += 1
        if v > u:
            end = S[v + 1] if v + 1 < n else S[v] + 0.16 * (v - u + 1)
            k = v - u + 1
            for j in range(u, v + 1):
                if not fixed[j]:
                    S[j] = S[u] + (end - S[u]) * (j - u) / k
        u = v + 1
    for u in range(n):
        if not fixed[u]:
            lo = S[u - 1] + 0.07 if u else -1
            hi = S[u + 1] - 0.07 if u + 1 < n else 1e9
            s = snap(S[u])
            if lo <= s <= hi:
                S[u] = s
    for u in range(1, n):
        S[u] = max(S[u], S[u - 1] + 0.05)
    # ends
    E = np.zeros(n)
    for u in range(n):
        own = None
        if c and c[u]:
            own = c[u][1]
        if w:
            own = max(own or 0, w[u][1])
        nxt = S[u + 1] if u + 1 < n else None
        if nxt is not None and nxt - S[u] < 0.9:
            E[u] = nxt
        else:
            E[u] = min(max(own or S[u] + 0.3, S[u] + 0.18), S[u] + 1.4)
            if nxt is not None:
                E[u] = min(E[u], nxt)
    units = [[round(float(a), 3), round(float(b), 3)] for a, b in zip(S, E)]
    for u in UNSUNG.get(li, ()):
        units[u] = None
    perfs.append({'li': li, 'u': units})

for li, plist in EXTRA.items():
    n = len(lines[li]['units'])
    for pd in plist:
        st = {k: v for k, v in pd.items() if isinstance(k, int)}
        if not st:
            continue
        ks = sorted(st)
        units = [None] * n
        for j, k in enumerate(ks):
            nxt = st[ks[j + 1]] if j + 1 < len(ks) else st[k] + pd.get('last', 0.45)
            units[k] = [round(st[k], 3), round(min(nxt, st[k] + 1.2), 3)]
        perfs.append({'li': li, 'u': units})

perfs.sort(key=lambda p: min(u[0] for u in p['u'] if u))
json.dump({'perfs': perfs}, open(out, 'w'), indent=0)
print(len(perfs), 'performances;', sum(1 for p in perfs for u in p['u'] if u), 'units;', len(flags), 'interpolated')
if report:
    for fl in flags if '--all' in sys.argv else []:
        print('interp line %d unit %d  whisper %.2f  ctc %.2f  -> %.2f' % fl)
    # units that start where the vocal stem is silent
    for p in perfs:
        for k, u in enumerate(p['u']):
            if u and not voiced(u[0] - 0.02, 0.14):
                print('silent? line %d unit %d at %.2f' % (p['li'], k, u[0]))
