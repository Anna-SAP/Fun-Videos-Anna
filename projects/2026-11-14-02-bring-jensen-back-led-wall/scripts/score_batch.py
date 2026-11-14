#!/usr/bin/env python3
"""Teacher-forced scoring of alternative hearings, many stretches per model load.

  score_batch.py CANDS.json OUT.json [--models large-v2,large-v3,medium] [--audio voc,mix]

CANDS.json: [{"id": "U1", "t0": 100.6, "t1": 103.6, "prev": "previous line", "cands": ["...", "..."]}, ...]
For each stretch the audio is encoded once per (model, audio); each candidate is forced through the decoder
(optionally after the previous line as a prompt, as Whisper would have it) and scored by the mean and total
log probability of its tokens. Candidates that differ only in a few characters are compared on exactly
those characters, which is what a free transcription cannot do.
"""
import argparse
import json
import os

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from faster_whisper.tokenizer import Tokenizer

ap = argparse.ArgumentParser()
ap.add_argument('cands')
ap.add_argument('out')
ap.add_argument('--models', default='large-v2,large-v3,medium')
ap.add_argument('--audio', default='voc,mix')
a = ap.parse_args()
AUD = {'voc': 'work/audio/vocals16k.wav', 'mix': 'work/audio/mono16k.wav'}
items = json.load(open(a.cands, encoding='utf-8'))
pcms = {k: sf.read(AUD[k], dtype='float32')[0] for k in a.audio.split(',')}
res = {it['id']: {} for it in items}
for name in a.models.split(','):
    m = WhisperModel(name, device='cpu', compute_type='int8', cpu_threads=os.cpu_count(), download_root='work/models')
    tok = Tokenizer(m.hf_tokenizer, m.model.is_multilingual, task='transcribe', language='zh')
    for an, pcm in pcms.items():
        for it in items:
            clip = pcm[int(it['t0'] * 16000):int(it['t1'] * 16000)]
            feats = m.feature_extractor(clip)
            nf = feats.shape[-1]
            enc = m.encode(np.pad(feats, ((0, 0), (0, max(0, 3000 - nf))))[:, :3000])
            for c in it['cands']:
                ids = tok.encode(c.strip())
                r = m.model.align(enc, tok.sot_sequence, [ids], nf)[0]
                lp = np.log(np.maximum(np.array(r.text_token_probs), 1e-9))
                res[it['id']].setdefault(c, []).append((float(lp.sum()), float(lp.mean())))
        print('done', name, an, flush=True)
out = {}
for it in items:
    rows = []
    cs = list(res[it['id']].keys())
    tot = np.array([[x[0] for x in res[it['id']][c]] for c in cs])      # cand x run
    mean = np.array([[x[1] for x in res[it['id']][c]] for c in cs])
    wins_t = (tot == tot.max(0, keepdims=True)).sum(1)
    wins_m = (mean == mean.max(0, keepdims=True)).sum(1)
    for k, c in enumerate(cs):
        rows.append((float(tot[k].mean()), float(mean[k].mean()), int(wins_t[k]), int(wins_m[k]), c))
    rows.sort(reverse=True)
    out[it['id']] = [{'cand': c, 'total': round(t, 2), 'mean': round(mn, 3), 'wins_total': wt, 'wins_mean': wm}
                     for t, mn, wt, wm, c in rows]
    print(f"== {it['id']} {it['t0']}-{it['t1']}  runs={tot.shape[1]}")
    for t, mn, wt, wm, c in rows:
        print(f'   tot {t:8.2f} ({wt})  mean {mn:6.3f} ({wm})  {c}')
json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
