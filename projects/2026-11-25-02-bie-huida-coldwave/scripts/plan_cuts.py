#!/usr/bin/env python3
"""Cut points from the measured grid: a shot that starts on a lyric line cuts on the bar line when the first
character lands within -0.35..+0.60 s of it, otherwise on the last beat at or before the first character
(the beat the sentence starts on). A bar line is only used when the previous line has finished by then and the
first character is not more than 0.05 s before it. Chorus 2 is forced to its bar line: the aligner put its first
character inside the two-beat bar with a near-zero score, and the mix transcription starts it at 138.32. Prints the shot plan with bar.beat, seconds and frame (24 fps).
"""
import json
import numpy as np
bj = json.load(open('work/audio/bars.json')); B = np.array(bj['beats']); bars = bj['bar_idx']
L = json.load(open('work/audio/line_times.json'))
def start(key):
    v, m = L[key]['voc'], L[key]['mix']
    sv = np.mean([s for *_, s in v]); sm = np.mean([s for *_, s in m])
    return (v if sv >= sm else m)[0][0]
def barbeat(t):
    i = int(np.argmin(abs(B - t)))
    k = max(j for j, bi in enumerate(bars) if bi <= i)
    return f'b{k+1}.{i - bars[k] + 1}'
FORCE = {'Chorus 2|1': 138.32}
def prev_end(key):
    sec, n = key.split('|'); n = int(n)
    keys = list(L.keys()); i = keys.index(key)
    if i == 0: return 0
    v = L[keys[i - 1]]['voc']; m = L[keys[i - 1]]['mix']
    return min(v[-1][1], m[-1][1])
def cut(key):
    s = FORCE.get(key) or start(key)
    pe = prev_end(key)
    for k, bi in enumerate(bars):
        if -0.05 <= s - B[bi] <= 0.60 and pe <= B[bi] + 0.05:
            return B[bi], s, 'bar'
    i = max(j for j in range(len(B)) if B[j] <= s + 0.05)
    return B[i], s, 'head'
PLAN = [('s02', 'K02', 'Verse 1|1'), ('s03', 'K03', 'Verse 1|3'), ('s04', 'K04', 'Verse 1|5'), ('s05', 'K05', 'Verse 1|7'),
        ('s06', 'K06', 'Pre-Chorus|1'), ('s07', 'K07', 'Pre-Chorus|3'), ('s08', 'K08', 'Pre-Chorus|5'),
        ('s09', 'K09', 'Chorus 1|1'), ('s10', 'K10', 'Chorus 1|3'),
        ('s11', 'K11', 'Verse 2|1'), ('s12', 'K12', 'Verse 2|2'), ('s13', 'K11', 'Verse 2|3'), ('s14', 'K13', 'Verse 2|5'),
        ('s15', 'K14', 'Verse 2|9'), ('s16', 'K15', 'Verse 2|12'), ('s17', 'K16', 'Chorus 2|1'),
        ('s18', 'K17', 'Verse 3|1'), ('s19', 'K18', 'Verse 3|3'), ('s20', 'K19', 'Verse 3|5'), ('s21', 'K15', 'Verse 3|7'),
        ('s23', 'K21', 'Bridge|6'), ('s24', 'K22', 'Verse 4|2'), ('s25', 'K23', 'Verse 4|3'), ('s26', 'K24', 'Verse 4|5'),
        ('s27', 'K09', 'Final Chorus|1'), ('s28', 'K25', 'Final Chorus|2'), ('s29', 'K26', 'Final Chorus|4')]
res = {}
for sid, kf, key in PLAN:
    t, s, why = cut(key)
    res[sid] = {'kf': kf, 'line': key, 'cut': round(float(t), 3), 'first_char': round(float(s), 2), 'rule': why, 'at': barbeat(t),
                'frame': int(round(t * 24))}
    print(f"{sid} {kf} {key:16s} first char {s:7.2f}  cut {t:7.3f} ({barbeat(t)}, {why}) frame {int(round(t*24))}")
json.dump(res, open('work/audio/cuts.json', 'w'), indent=1)
