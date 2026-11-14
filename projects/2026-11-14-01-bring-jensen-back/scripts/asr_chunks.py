#!/usr/bin/env python3
"""Transcribe short chunks (to stop Whisper looping on dense chant) in zh and en. Prints text per chunk.
  asr_chunks.py AUDIO16K T0 T1 STEP MODEL"""
import os, sys
import soundfile as sf
from faster_whisper import WhisperModel
a, t0, t1, step, mname = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
m = WhisperModel(mname, device='cpu', compute_type='int8', cpu_threads=os.cpu_count())
pcm, sr = sf.read(a, dtype='float32')
t = t0
while t < t1 - 0.5:
    clip = pcm[int(t * sr):int(min(t1, t + step) * sr)]
    row = []
    for lang in ('zh', 'en'):
        segs, _ = m.transcribe(clip, language=lang, beam_size=5, vad_filter=False, condition_on_previous_text=False,
                               word_timestamps=True)
        ws = [f"{w.word.strip()}@{w.start + t:.2f}" for s in segs for w in (s.words or [])]
        row.append(' '.join(ws))
    print(f'{t:6.1f} zh: {row[0]}\n       en: {row[1]}', flush=True)
    t += step
