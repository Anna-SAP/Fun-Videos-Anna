#!/usr/bin/env python3
"""Forced word alignment of the known lyrics with several Whisper models, then a median.

  force_align.py LYRICS.json OUT.json

The lyric text is fixed (verified separately), so instead of transcribing we force it through Whisper's
cross-attention alignment (the same DTW faster-whisper uses for word timestamps). Each (model x audio x
window) combination is one independent estimate of every word's start and end; the median over estimates
is kept together with the spread, so unreliable words are visible. Audio: the full mix and the separated
vocal. Windows overlap so every line is seen from two different offsets.

Only times are written to OUT.json (line index, word index, start, end, spread, n) -- no lyric text.
"""
import json
import os
import re
import sys

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from faster_whisper.tokenizer import Tokenizer

lyr = json.load(open(sys.argv[1], encoding='utf-8'))
out = sys.argv[2]
lines = [l['en'] for l in lyr['lines']]
words = [l.split() for l in lines]

# windows (song seconds) and which lines they contain; <= 30 s each for Whisper
WINDOWS = [(10.6, 29.6, [0, 1, 2, 3]), (11.0, 33.6, [0, 1, 2, 3, 4]), (27.6, 46.6, [4, 5, 6, 7, 8]),
           (31.6, 52.6, [5, 6, 7, 8, 9]), (44.0, 65.8, [8, 9, 10, 11]), (48.0, 65.8, [9, 10, 11])]
AUDIO = {'mix': 'work/audio/mono16k.wav', 'voc': 'work/audio/vocals16k.wav'}
MODELS = ['large-v3', 'large-v2', 'medium.en', 'small.en']

est = {}  # (li, wi) -> list of (start, end)
for mname in MODELS:
    m = WhisperModel(mname, device='cpu', compute_type='int8', cpu_threads=os.cpu_count(), download_root='work/models')
    tok = Tokenizer(m.hf_tokenizer, m.model.is_multilingual, task='transcribe', language='en')
    for aname, path in AUDIO.items():
        pcm, sr = sf.read(path, dtype='float32')
        for t0, t1, lis in WINDOWS:
            clip = pcm[int(t0 * sr):int(t1 * sr)]
            feats = m.feature_extractor(clip)
            nf = feats.shape[-1]
            enc = m.encode(np.pad(feats, ((0, 0), (0, max(0, 3000 - nf))))[:, :3000])
            # punctuation would come back as separate 'words'; align the bare words
            text = ' ' + ' '.join(re.sub(r"[^\w' ]", '', lines[i]) for i in lis)
            ids = tok.encode(text)
            ws = m.find_alignment(tok, [ids], enc, nf)[0]
            flat = [(li, wi) for li in lis for wi in range(len(words[li]))]
            got = [w for w in ws if re.sub(r"[^\w']", '', w['word'])]
            if len(got) != len(flat):
                print('word count mismatch', mname, aname, t0, len(got), len(flat))
                continue
            for (li, wi), w in zip(flat, got):
                est.setdefault((li, wi), []).append((t0 + float(w['start']), t0 + float(w['end'])))
        print('done', mname, aname, flush=True)

res = []
for li in range(len(words)):
    for wi in range(len(words[li])):
        e = np.array(est.get((li, wi), []))
        s, en = np.median(e[:, 0]), np.median(e[:, 1])
        res.append({'line': li, 'word': wi, 's': round(float(s), 3), 'e': round(float(en), 3),
                    'spread_s': round(float(np.percentile(e[:, 0], 75) - np.percentile(e[:, 0], 25)), 3), 'n': len(e)})
json.dump(res, open(out, 'w'), indent=0)
for r in res:
    print(f"L{r['line'] + 1}.{r['word'] + 1:<2} {r['s']:7.2f} {r['e']:7.2f}  iqr {r['spread_s']:.2f}  n={r['n']}")
