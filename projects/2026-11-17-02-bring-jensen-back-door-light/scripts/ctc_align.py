#!/usr/bin/env python3
"""A second, Whisper-independent timing for every unit: CTC forced alignment with the MMS aligner.

  ctc_align.py SHEET.txt ROUGH.json OUT.json

The MMS forced-alignment model (wav2vec2, torchaudio.pipelines.MMS_FA) emits a letter posterior every 20 ms.
Each unit is romanised (CJK -> toneless pinyin, Latin words -> their letters) and the line's letter sequence
is forced through the emissions of the stretch where the line is sung (ROUGH.json: per-line start/end from
the Whisper alignment). Windows of one, two and three consecutive lines on both the vocal stem and the full
mix give several estimates per unit; the median is kept with its spread and the mean posterior of the path.

OUT.json holds only times: {'lines': [{'i', 'units': [[start, end]...], 'spread': [...], 'score': [...]}]}.
"""
import json
import os
import re
import sys

import numpy as np
import soundfile as sf
import torch
import torchaudio
from pypinyin import lazy_pinyin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lyrics import CJK, parse  # noqa: E402

sheet, rough, out = sys.argv[1:4]
torch.hub.set_dir('work/models/torchhub')
torch.set_num_threads(os.cpu_count())
bundle = torchaudio.pipelines.MMS_FA
model = bundle.get_model(with_star=True)
model.eval()
DIC = bundle.get_dict(star='*')
HOP = 0.02
secs, lines = parse(sheet)
R = {r['i']: r for r in json.load(open(rough))['lines'] if r.get('units') or 's' in r}
cjk = re.compile(f'[{CJK}]')


def span(i):
    r = R[i]
    if 'units' in r and r['units']:
        return r['units'][0][0], r['units'][-1][1]
    return r['s'], r['e']


def romanise(line):
    """per unit: list of dictionary ids."""
    toks = [u[0] for u in line['units']]
    zh = ''.join(t for t in toks if cjk.match(t[0]))
    py = lazy_pinyin(zh) if zh else []
    assert len(py) == len(zh), (zh, py)
    out, k = [], 0
    for t in toks:
        if cjk.match(t[0]):
            s = py[k].lower().replace('ü', 'u').replace('v', 'u')
            k += 1
        else:
            s = t.lower().replace('’', "'")
        s = re.sub(r"[^a-z']", '', s)
        out.append([DIC[c] for c in s] or [DIC['*']])
    return out


def emissions(path):
    pcm, sr = sf.read(path, dtype='float32')
    assert sr == 16000
    n = len(pcm)
    CH, OV = 20 * sr, 2 * sr
    frames = int(np.ceil(n / (sr * HOP)))
    em = np.full((frames, len(DIC)), -1e9, np.float32)
    pos = 0
    with torch.inference_mode():
        while pos < n:
            a, b = max(0, pos - OV), min(n, pos + CH + OV)
            e, _ = model(torch.from_numpy(pcm[a:b])[None])
            e = torch.log_softmax(e[0], -1).numpy()
            f0 = int(round(a / (sr * HOP)))
            keep_a = int(round((pos - a) / (sr * HOP)))
            keep_b = min(len(e), int(round((min(n, pos + CH) - a) / (sr * HOP))))
            em[f0 + keep_a:f0 + keep_b] = e[keep_a:keep_b]
            pos += CH
    return em


EM = {'voc': emissions('work/audio/vocals16k.wav'), 'mix': emissions('work/audio/mono16k.wav')}
print('emissions', {k: v.shape for k, v in EM.items()}, flush=True)
ROM = {l['i']: romanise(l) for l in lines}
have = sorted(R)
est = {}
for name, em in EM.items():
    for k in range(len(have)):
        for nwin in (1, 2, 3):
            grp = have[k:k + nwin]
            if len(grp) < nwin or any(grp[j + 1] != grp[j] + 1 for j in range(len(grp) - 1)):
                continue
            t0 = max(0.0, span(grp[0])[0] - 1.0)
            t1 = span(grp[-1])[1] + 1.0
            f0, f1 = int(t0 / HOP), min(len(em), int(t1 / HOP))
            targets, owner = [], []
            for li in grp:
                for ui, ids in enumerate(ROM[li]):
                    targets += ids
                    owner += [(li, ui)] * len(ids)
            e = torch.from_numpy(em[f0:f1])[None]
            if e.shape[1] < len(targets) + 2:
                continue
            try:
                path, score = torchaudio.functional.forced_align(e, torch.tensor([targets], dtype=torch.int32), blank=0)
            except Exception as ex:  # noqa: BLE001
                print('fail', grp, ex)
                continue
            path, score = path[0].numpy(), score[0].exp().numpy()
            # token spans: runs of the same non-blank label, in order
            spans = []
            prev = 0
            for f, lab in enumerate(path):
                if lab != 0 and lab != prev:
                    spans.append([f, f, [score[f]]])
                elif lab != 0:
                    spans[-1][1] = f
                    spans[-1][2].append(score[f])
                prev = lab
            if len(spans) != len(targets):
                # a repeated letter without a blank between merges; fall back to skipping this window
                continue
            cur = {}
            for (li, ui), (a, b, sc) in zip(owner, spans):
                c = cur.setdefault((li, ui), [a, b, []])
                c[1] = b
                c[2] += sc
            for key, (a, b, sc) in cur.items():
                est.setdefault(key, []).append((t0 + a * HOP, t0 + (b + 1) * HOP, float(np.mean(sc))))
    print('done', name, flush=True)

res = []
for l in lines:
    li = l['i']
    U, SP, SC, N = [], [], [], []
    for ui in range(len(l['units'])):
        e = np.array(est.get((li, ui), []), np.float64)
        if len(e):
            U.append([round(float(np.median(e[:, 0])), 3), round(float(np.median(e[:, 1])), 3)])
            SP.append(round(float(np.percentile(e[:, 0], 75) - np.percentile(e[:, 0], 25)), 3))
            SC.append(round(float(np.median(e[:, 2])), 3))
            N.append(len(e))
        else:
            U.append(None)
            SP.append(None)
            SC.append(None)
            N.append(0)
    res.append({'i': li, 'units': U, 'spread': SP, 'score': SC, 'n': N})
json.dump({'lines': res}, open(out, 'w'), indent=0)
for r in res:
    u = [x for x in r['units'] if x]
    if not u:
        print(r['i'], 'none')
        continue
    sp = [x for x in r['spread'] if x is not None]
    sc = [x for x in r['score'] if x is not None]
    print(f"{r['i']:3d} {u[0][0]:7.2f}-{u[-1][1]:7.2f} n~{int(np.median(r['n']))} iqr~{np.median(sp):.2f} score~{np.median(sc):.2f}")
