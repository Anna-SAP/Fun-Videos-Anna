#!/usr/bin/env python3
"""Beat tracking for a song whose tempo drifts slightly (dynamic programming, Ellis 2007 style, with a
locally re-estimated period), then a per-beat table of kick / snare / hat strength and band levels.

  beats.py FEAT.npz OUT.json [PERIOD0=0.537]
"""
import json, sys
import numpy as np
d = np.load(sys.argv[1]); out = sys.argv[2]
P0 = float(sys.argv[3]) if len(sys.argv) > 3 else 0.537
R = float(d['rate'])
env = d['kick'] / (d['kick'].std() + 1e-9) + d['snare'] / (d['snare'].std() + 1e-9) + 0.5 * d['hat'] / (d['hat'].std() + 1e-9)
env = np.maximum(env - np.median(env), 0)
n = len(env)
# local period by windowed autocorrelation (20 s windows)
def local_period(tc):
    a = int(max(0, tc - 10) * R); b = int(min(n / R, tc + 10) * R)
    s = env[a:b] - env[a:b].mean()
    best, bp = -1, P0
    for p in np.arange(P0 * 0.96, P0 * 1.04, 0.0005):
        sc = 0
        for k in (1, 2, 4, 8):
            L = int(round(p * k * R))
            sc += np.dot(s[:-L], s[L:]) / (len(s) - L)
        if sc > best: best, bp = sc, p
    return bp
tcs = np.arange(5, n / R, 5.0)
lp = np.array([local_period(t) for t in tcs])
print('local period every 5 s:', np.round(lp, 4).tolist())
per = np.interp(np.arange(n) / R, tcs, lp)
# DP
score = np.zeros(n); back = -np.ones(n, int)
TIGHT = 300.0
for i in range(n):
    p = per[i] * R
    lo, hi = int(i - 1.5 * p), int(i - 0.6 * p)
    if hi <= 0:
        score[i] = env[i]; continue
    lo = max(lo, 0)
    idx = np.arange(lo, hi)
    pen = -TIGHT * (np.log((i - idx) / p)) ** 2
    c = score[idx] + pen
    j = int(np.argmax(c))
    score[i] = env[i] + c[j]; back[i] = idx[j]
i = int(np.argmax(score[-int(1.2 * per[-1] * R):]) + n - int(1.2 * per[-1] * R))
beats = []
while i >= 0:
    beats.append(i / R); i = back[i]
beats = np.array(beats[::-1])
# refine each beat to the local onset peak within +-25 ms then smooth
def val(arr, t, w=0.03):
    a = int(max(0, (t - w) * R)); b = int((t + w) * R) + 1
    return float(arr[a:b].max()) if b > a else 0.0
rows = []
for k, t in enumerate(beats):
    rows.append({'t': round(float(t), 3), 'kick': round(val(d['kick'], t), 2), 'snare': round(val(d['snare'], t), 2), 'hat': round(val(d['hat'], t), 2)})
json.dump({'beats': [r['t'] for r in rows], 'rows': rows}, open(out, 'w'))
ib = np.diff(beats)
print('n beats', len(beats), 'first', beats[0], 'last', beats[-1], 'median period', np.median(ib))
ks = np.array([r['kick'] for r in rows]); sn = np.array([r['snare'] for r in rows])
for ph in range(4):
    print('phase', ph, 'kick', round(ks[ph::4].mean(), 2), 'snare', round(sn[ph::4].mean(), 2))
for k in range(0, len(rows), 4):
    seg = rows[k:k + 4]
    print(f"{k:4d} {seg[0]['t']:7.2f} | " + ' '.join(f"k{r['kick']:5.1f} s{r['snare']:5.1f} h{r['hat']:4.1f}" for r in seg) + f" | per {np.mean(ib[k:k+4]) if k+4<=len(ib) else 0:.4f}")
