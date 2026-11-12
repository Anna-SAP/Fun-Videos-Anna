#!/usr/bin/env python3
"""Score alternative hearings of one stretch of singing with Whisper (teacher-forced).

  score_candidates.py AUDIO16K.wav T0 T1 "cand 1" "cand 2" ... [--models large-v3,large-v2,medium.en]

The audio between T0 and T1 is encoded once per model; every candidate text is then forced through the
decoder (CTranslate2 `align`), which returns the probability of each of its tokens. A candidate's score is
the mean log probability of its tokens; the per-token table shows exactly where candidates differ. This
answers "which of these was sung" far better than free transcription, which has to invent the words.
"""
import argparse
import os

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from faster_whisper.tokenizer import Tokenizer

ap = argparse.ArgumentParser()
ap.add_argument('audio')
ap.add_argument('t0', type=float)
ap.add_argument('t1', type=float)
ap.add_argument('cands', nargs='+')
ap.add_argument('--models', default='large-v3,large-v2,medium.en')
a = ap.parse_args()

pcm, sr = sf.read(a.audio, dtype='float32')
assert sr == 16000
clip = pcm[int(a.t0 * sr):int(a.t1 * sr)]

for name in a.models.split(','):
    m = WhisperModel(name, device='cpu', compute_type='int8', cpu_threads=os.cpu_count(), download_root='work/models')
    feats = m.feature_extractor(clip)
    num_frames = feats.shape[-1]
    enc = m.encode(np.pad(feats, ((0, 0), (0, max(0, 3000 - num_frames))))[:, :3000])
    tok = Tokenizer(m.hf_tokenizer, m.model.is_multilingual, task='transcribe', language='en')
    rows = []
    for c in a.cands:
        ids = tok.encode(' ' + c.strip())
        res = m.model.align(enc, tok.sot_sequence, [ids], num_frames)[0]
        lp = np.log(np.maximum(np.array(res.text_token_probs), 1e-9))
        rows.append((lp.mean(), lp.sum(), c, [(tok.decode([i]), round(float(p), 3)) for i, p in zip(ids, res.text_token_probs)]))
    print(f'== {name}  ({a.t0}-{a.t1}s)')
    for mean, tot, c, toks in sorted(rows, reverse=True):
        print(f'  {mean:7.3f} {tot:8.2f}  {c}')
    best = sorted(rows, reverse=True)[0]
    for mean, tot, c, toks in sorted(rows, reverse=True)[:4]:
        print('     ', ' '.join(f'{t.strip()}:{p}' for t, p in toks))
