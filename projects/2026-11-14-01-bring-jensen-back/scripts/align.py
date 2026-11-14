#!/usr/bin/env python3
"""Forced alignment of the known lyric units, several independent estimates per unit, then a median.

  align.py OUT_RAW.json [model ...]

For each (model x audio x window grouping) the sung lines inside one window (<= 28 s) are forced through
Whisper's cross-attention alignment (faster-whisper find_alignment, the same DTW it uses for word
timestamps). The returned pieces are mapped back to our units by character offsets, so CJK characters and
Latin words each get a start and end. Windows come in two groupings offset by about half a group, so every
line is seen from two different window positions. Only times go into the output, never lyric text.
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from faster_whisper.tokenizer import Tokenizer

sys.path.insert(0, os.path.dirname(__file__))
import lyrics  # noqa: E402
import sung  # noqa: E402

out = sys.argv[1]
MODELS = sys.argv[2:] or ['large-v3', 'large-v3-turbo']
AUDIO = {'voc': 'work/audio/vocals16k.wav', 'mix': 'work/audio/mono16k.wav'}
ENT = sung.entries()


def unit_list(e):
    us = lyrics.units(e['line'])
    if e['slice']:
        us = us[e['slice'][0]:e['slice'][1]]
    return us


def text_of(us):
    s, spans, prev_cjk = '', [], True
    for u in us:
        if s and not (u['cjk'] and prev_cjk):
            s += ' '
        a = len(s)
        s += u['t']
        spans.append((a, len(s)))
        prev_cjk = u['cjk']
    return s, spans


def groups(offset, span=24.0):
    gs, cur = [], []
    idx = list(range(len(ENT)))
    first = idx[:offset]
    if first:
        gs.append(first)
    for i in idx[offset:]:
        if cur and ENT[i]['t1'] - ENT[cur[0]]['t0'] > span:
            gs.append(cur)
            cur = []
        cur.append(i)
    if cur:
        gs.append(cur)
    return gs


GROUPINGS = [groups(0), groups(4), groups(2, 14.0)]

est = {}  # (entry index, unit index) -> list of (s, e)
for mname in MODELS:
    m = WhisperModel(mname, device='cpu', compute_type='int8', cpu_threads=os.cpu_count())
    tok = Tokenizer(m.hf_tokenizer, m.model.is_multilingual, task='transcribe', language='zh')
    for aname, path in AUDIO.items():
        pcm, sr = sf.read(path, dtype='float32')
        nok = nbad = 0
        for gi, grouping in enumerate(GROUPINGS):
            for g in grouping:
                t0 = max(0.0, ENT[g[0]]['t0'] - 0.45)
                t1 = min(len(pcm) / sr, ENT[g[-1]]['t1'] + 0.45)
                if t1 - t0 > 29.5:
                    t1 = t0 + 29.5
                clip = pcm[int(t0 * sr):int(t1 * sr)]
                feats = m.feature_extractor(clip)
                nf = feats.shape[-1]
                enc = m.encode(np.pad(feats, ((0, 0), (0, max(0, 3000 - nf))))[:, :3000])
                full, owners = '', []
                for i in g:
                    s, spans = text_of(unit_list(ENT[i]))
                    base = len(full) + (1 if full else 0)
                    full += (' ' if full else '') + s
                    owners += [(i, k, base + a, base + b) for k, (a, b) in enumerate(spans)]
                ids = tok.encode(' ' + full)
                ws = m.find_alignment(tok, [ids], enc, nf)[0]
                rec = ''.join(w['word'] for w in ws)
                if rec.strip() != full.strip():
                    nbad += 1
                    continue
                lead = len(rec) - len(rec.lstrip())
                pos, pieces = 0, []
                for w in ws:
                    a, b = pos - lead, pos - lead + len(w['word'])
                    pieces.append((a, b, float(w['start']) + t0, float(w['end']) + t0))
                    pos += len(w['word'])
                for (i, k, a, b) in owners:
                    hit = [p for p in pieces if p[1] > a and p[0] < b]
                    if not hit:
                        continue
                    est.setdefault((i, k), []).append((hit[0][2], hit[-1][3]))
                nok += 1
        print(f'{mname} {aname}: {nok} windows ok, {nbad} text mismatches', flush=True)
    del m

res = []
for i, e in enumerate(ENT):
    us = unit_list(e)
    row = {'id': e['id'], 'line': e['line'], 'slice': e['slice'], 'units': []}
    for k in range(len(us)):
        arr = np.array(est.get((i, k), []), float)
        if len(arr):
            row['units'].append({'s': round(float(np.median(arr[:, 0])), 3), 'e': round(float(np.median(arr[:, 1])), 3),
                                 'iqr': round(float(np.percentile(arr[:, 0], 75) - np.percentile(arr[:, 0], 25)), 3),
                                 'n': len(arr)})
        else:
            row['units'].append({'s': None, 'e': None, 'iqr': None, 'n': 0})
    res.append(row)
json.dump(res, open(out, 'w'), indent=0)
for r in res:
    ss = [u['s'] for u in r['units'] if u['s'] is not None]
    iq = [u['iqr'] for u in r['units'] if u['iqr'] is not None]
    print(f"{r['id']:5s} L{r['line']:<3} {min(ss) if ss else -1:7.2f}-{max(ss) if ss else -1:7.2f}  "
          f"median iqr {np.median(iq) if iq else -1:.2f}  n={min(u['n'] for u in r['units'])}")
