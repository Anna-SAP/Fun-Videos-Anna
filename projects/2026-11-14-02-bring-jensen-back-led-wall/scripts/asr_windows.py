#!/usr/bin/env python3
"""Windowed multi-model transcription (faster-whisper, CPU int8), one model loaded at a time.

  asr_windows.py OUT.jsonl MODEL[,MODEL..] AUDIO[,AUDIO..] RANGES [--win 24 --hop 12] [--prompt TEXT]

RANGES = "0-30,88-166" (song seconds). Every (model, audio, window) result is appended as one JSON line
with song-time word timestamps, so independent listens of the same stretch can be compared side by side.
No VAD (it drops sung phrases over loud beats); no conditioning on previous text (stops runaway repeats).
"""
import argparse
import json
import os

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('models')
ap.add_argument('audios')
ap.add_argument('ranges')
ap.add_argument('--win', type=float, default=24)
ap.add_argument('--hop', type=float, default=12)
ap.add_argument('--prompt', default=None)
ap.add_argument('--lang', default='zh')
a = ap.parse_args()

wins = []
for r in a.ranges.split(','):
    t0, t1 = map(float, r.split('-'))
    s = t0
    while True:
        e = min(t1, s + a.win)
        wins.append((s, e))
        if e >= t1:
            break
        s += a.hop
pcms = {p: sf.read(p, dtype='float32')[0] for p in a.audios.split(',')}
with open(a.out, 'a') as fo:
    for mname in a.models.split(','):
        m = WhisperModel(mname, device='cpu', compute_type='int8', cpu_threads=os.cpu_count(), download_root='work/models')
        for apath, pcm in pcms.items():
            for t0, t1 in wins:
                clip = pcm[int(t0 * 16000):int(t1 * 16000)]
                segs, _ = m.transcribe(clip, language=a.lang, beam_size=5, temperature=0.0, word_timestamps=True,
                                       initial_prompt=a.prompt, vad_filter=False, condition_on_previous_text=False)
                rec = {'model': mname, 'audio': os.path.basename(apath), 't0': t0, 't1': t1, 'segments': []}
                for s in segs:
                    rec['segments'].append({'start': round(s.start + t0, 2), 'end': round(s.end + t0, 2), 'text': s.text.strip(),
                                            'lp': round(s.avg_logprob, 2), 'nsp': round(s.no_speech_prob, 2),
                                            'words': [{'w': w.word.strip(), 's': round(w.start + t0, 3), 'e': round(w.end + t0, 3),
                                                       'p': round(w.probability, 2)} for w in (s.words or [])]})
                fo.write(json.dumps(rec, ensure_ascii=False) + '\n')
                fo.flush()
                print(mname, os.path.basename(apath), t0, t1, ' | '.join(s['text'] for s in rec['segments']), flush=True)
