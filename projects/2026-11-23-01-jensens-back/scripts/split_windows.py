#!/usr/bin/env python3
"""Turn windowed transcripts (asr_windows.py JSONL) into continuous transcripts for map_lines.py.

  split_windows.py IN.jsonl OUTPREFIX

Windows overlap by half, so every second is heard by two windows. Output 0 takes each window's first half,
output 1 each window's second half: every second of the song is covered once per output, and the two outputs
come from different windows' listening.
"""
import json
import sys

recs = [json.loads(l) for l in open(sys.argv[1])]
by = {}
for r in recs:
    by.setdefault((r['model'], r['audio']), []).append(r)
for (m, a), rs in by.items():
    rs.sort(key=lambda r: r['t0'])
    for variant in (0, 1):
        segs = []
        for k, r in enumerate(rs):
            hop = rs[1]['t0'] - rs[0]['t0'] if len(rs) > 1 else 1e9
            if variant == 0:      # each window keeps its first half (the last window keeps everything)
                lo = r['t0']
                hi = r['t0'] + hop if k < len(rs) - 1 else 1e9
            else:                 # each window keeps its second half (the first window also its first)
                lo = r['t0'] + hop if k > 0 else 0
                hi = r['t0'] + 2 * hop if k < len(rs) - 1 else 1e9
            for s in r['segments']:
                ws = [w for w in s['words'] if lo <= (w['s'] + w['e']) / 2 < hi]
                if ws:
                    segs.append({'start': ws[0]['s'], 'end': ws[-1]['e'], 'text': ''.join(w['w'] for w in ws), 'words': ws})
        segs.sort(key=lambda s: s['start'])
        out = f"{sys.argv[2]}_{m}_{a.split('.')[0]}_{variant}.json"
        json.dump({'segments': segs}, open(out, 'w'), ensure_ascii=False)
        print(out, len(segs))
