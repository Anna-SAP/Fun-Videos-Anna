#!/usr/bin/env python3
"""Per-unit sung times for the lyric sheet: forced alignment with several Whisper models, then a median,
then a snap to syllable onsets in the separated vocal.

  align.py SHEET.txt MAP.json OUT.json

MAP.json (map_lines.py) gives each line a rough span. Windows of 2-4 consecutive lines (<= 28 s) are cut
from the vocal stem and the mix; each (model x audio x window) forces the known text through Whisper's
cross-attention alignment and yields one estimate per unit (CJK character or Latin word). The median over
estimates is kept with its spread. Finally each unit start is pulled to the strongest vocal onset within
-90/+60 ms, because aligners place onsets on the vowel energy and a little late or early.

OUT.json holds only times (line index, per-unit [start, end], spread, n) -- no lyric text.
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from faster_whisper.tokenizer import Tokenizer
from scipy import signal

sys.path.insert(0, os.path.dirname(__file__))
from lyrics import CJK, parse  # noqa: E402

sheet, mapf, out = sys.argv[1:4]
MODELS = os.environ.get('ALIGN_MODELS', 'large-v2,medium,small').split(',')
AUDIO = {'voc': 'work/audio/vocals16k.wav', 'mix': 'work/audio/mono16k.wav'}
COMBOS = [(m, a) for m in MODELS for a in (('voc', 'mix') if m == MODELS[0] else ('voc',))]
secs, lines = parse(sheet)
mp = {r['i']: r for r in json.load(open(mapf))['lines']}
import re  # noqa: E402

cjk = re.compile(f'[{CJK}]')


def align_text(li):
    """text fed to the aligner and each unit's [a, b) char span inside it."""
    txt = ''
    spans = []
    prev_cjk = True
    for u, _, _ in lines[li]['units']:
        is_c = bool(cjk.match(u[0]))
        sep = '' if (is_c and prev_cjk and txt) else ' '
        txt += sep
        spans.append((len(txt), len(txt) + len(u)))
        txt += u
        prev_cjk = is_c
    return txt, spans


# windows
have = [l['i'] for l in lines if 's' in mp.get(l['i'], {})]
ONLY = [int(x) for x in os.environ.get('ALIGN_ONLY', '').split(',') if x]
if ONLY:
    have = [i for i in have if i in ONLY]
wins = []
for k in range(len(have)):
    for n in tuple(int(x) for x in os.environ.get('ALIGN_N', '3').split(',')):
        grp = have[k:k + n]
        if len(grp) < n:
            continue
        if len(grp) > 1 and any(grp[j + 1] != grp[j] + 1 for j in range(len(grp) - 1)):
            continue
        t0 = mp[grp[0]]['s'] - 0.8
        t1 = mp[grp[-1]]['e'] + 0.8
        if t1 - t0 > 28 or t1 <= t0:
            continue
        wins.append((max(0, t0), t1, grp))
    if not any(w[2][0] == have[k] for w in wins):
        t0, t1 = mp[have[k]]['s'] - 0.8, mp[have[k]]['e'] + 0.8
        if 0 < t1 - t0 <= 28:
            wins.append((max(0, t0), t1, [have[k]]))
print(len(wins), 'windows', COMBOS, flush=True)

est = {}
pcms = {k: sf.read(v, dtype='float32')[0] for k, v in AUDIO.items()}
for mname in MODELS:
    m = WhisperModel(mname, device='cpu', compute_type='int8', cpu_threads=os.cpu_count(), download_root='work/models')
    tok = Tokenizer(m.hf_tokenizer, m.model.is_multilingual, task='transcribe', language='zh')
    for aname in [a for mm, a in COMBOS if mm == mname]:
        pcm = pcms[aname]
        for t0, t1, grp in wins:
            clip = pcm[int(t0 * 16000):int(t1 * 16000)]
            feats = m.feature_extractor(clip)
            nf = feats.shape[-1]
            enc = m.encode(np.pad(feats, ((0, 0), (0, max(0, 3000 - nf))))[:, :3000])
            full = ''
            owners = []
            for li in grp:
                txt, spans = align_text(li)
                base = len(full) + (1 if full else 0)
                full += (' ' if full else '') + txt
                owners += [(li, ui, base + a, base + b) for ui, (a, b) in enumerate(spans)]
            ids = tok.encode(' ' + full)
            try:
                ws = m.find_alignment(tok, [ids], enc, nf)[0]
            except Exception as e:  # noqa: BLE001
                print('align fail', e)
                continue
            # char offsets of the aligner's words within ' ' + full
            pos = -1
            wspan = []
            for w in ws:
                s = w['word']
                wspan.append((pos, pos + len(s), float(w['start']), float(w['end'])))
                pos += len(s)
            for li, ui, a, b in owners:
                hit = [(s_, e_) for (p0, p1, s_, e_) in wspan if p1 > a and p0 < b]
                if not hit:
                    continue
                s_, e_ = min(h[0] for h in hit), max(h[1] for h in hit)
                est.setdefault((li, ui), []).append((t0 + s_, t0 + e_))
        print('done', mname, aname, flush=True)

# vocal onset envelope for the final snap
voc, sr = sf.read('work/audio/vocals16k.wav', dtype='float32')
f, tt, Z = signal.stft(voc, sr, nperseg=1024, noverlap=1024 - 160, boundary=None, padded=False)
L = np.log1p(50 * np.abs(Z[(f > 150) & (f < 6000)]))
flux = np.concatenate([[0], np.maximum(L[:, 1:] - L[:, :-1], 0).sum(0)])
ft = (np.arange(len(flux)) * 160 + 512) / sr
flux = flux / (np.percentile(flux, 98) + 1e-9)

res = []
for l in lines:
    li = l['i']
    n = len(l['units'])
    S, E, SP, N = [], [], [], []
    for ui in range(n):
        e = np.array(est.get((li, ui), []), np.float64)
        if len(e):
            S.append(float(np.median(e[:, 0])))
            E.append(float(np.median(e[:, 1])))
            SP.append(float(np.percentile(e[:, 0], 75) - np.percentile(e[:, 0], 25)))
            N.append(len(e))
        else:
            S.append(np.nan)
            E.append(np.nan)
            SP.append(np.nan)
            N.append(0)
    S, E = np.array(S), np.array(E)
    if np.isnan(S).all():
        if 's' in mp.get(li, {}):
            S = np.linspace(mp[li]['s'], mp[li]['e'], n + 1)[:-1]
            E = S + (mp[li]['e'] - mp[li]['s']) / n
        else:
            res.append({'i': li, 'units': [], 'missing': True})
            continue
    idx = np.arange(n)
    ok = ~np.isnan(S)
    S = np.interp(idx, idx[ok], S[ok])
    E = np.where(np.isnan(E), S + 0.15, E)
    # snap starts to vocal onsets
    for ui in range(n):
        m_ = (ft >= S[ui] - 0.09) & (ft <= S[ui] + 0.06)
        if m_.any():
            j = np.argmax(flux[m_])
            if flux[m_][j] > 0.35:
                S[ui] = ft[m_][j]
    # monotone, min gap, ends = next start
    for ui in range(1, n):
        S[ui] = max(S[ui], S[ui - 1] + 0.04)
    for ui in range(n - 1):
        E[ui] = min(max(E[ui], S[ui] + 0.08), S[ui + 1]) if S[ui + 1] - S[ui] < 0.6 else max(E[ui], S[ui] + 0.12)
    E[-1] = max(E[-1], S[-1] + 0.15)
    res.append({'i': li, 'units': [[round(float(a), 3), round(float(b), 3)] for a, b in zip(S, E)],
                'spread': [None if np.isnan(x) else round(x, 3) for x in SP], 'n': N})
json.dump({'lines': res}, open(out, 'w'), indent=0)
for r, l in zip(res, lines):
    if r.get('missing'):
        print(f"{l['i']:3d} MISSING")
        continue
    u = r['units']
    sp = [x for x in r['spread'] if x is not None]
    print(f"{l['i']:3d} {u[0][0]:7.2f}-{u[-1][1]:7.2f} n~{int(np.median(r['n']))} iqr~{(np.median(sp) if sp else -1):.2f}  {l['text'][:28]}")
