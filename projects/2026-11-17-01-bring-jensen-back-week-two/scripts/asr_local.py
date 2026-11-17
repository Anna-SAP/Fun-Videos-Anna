#!/usr/bin/env python3
"""Local Whisper (faster-whisper, CPU int8) with word timestamps.

  asr_local.py AUDIO OUT.json MODEL [--t0 S --t1 S] [--prompt TEXT] [--beam N] [--temp T]

MODEL is a faster-whisper name (large-v3, medium.en, small.en, distil-large-v3 ...). Models come from
Hugging Face (Systran/faster-whisper-*) and are cached under work/models. --t0/--t1 cut a section first;
times in the output are always song times. The output has segments and words with start/end/probability.
"""
import argparse
import json
import os
import subprocess
import tempfile

import soundfile as sf
from faster_whisper import WhisperModel

ap = argparse.ArgumentParser()
ap.add_argument('audio')
ap.add_argument('out')
ap.add_argument('model')
ap.add_argument('--t0', type=float, default=0.0)
ap.add_argument('--t1', type=float, default=None)
ap.add_argument('--prompt', default=None)
ap.add_argument('--beam', type=int, default=5)
ap.add_argument('--temp', type=float, default=0.0)
ap.add_argument('--novad', action='store_true')
ap.add_argument('--lang', default='zh')
a = ap.parse_args()

src = a.audio
if a.t0 or a.t1:
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
    cmd = ['ffmpeg', '-v', 'error', '-y', '-ss', str(a.t0)]
    if a.t1:
        cmd += ['-t', str(a.t1 - a.t0)]
    cmd += ['-i', a.audio, '-ac', '1', '-ar', '16000', tmp]
    subprocess.run(cmd, check=True)
    src = tmp

model = WhisperModel(a.model, device='cpu', compute_type='int8', cpu_threads=os.cpu_count(),
                     download_root='work/models')
pcm, _sr = sf.read(src, dtype='float32')
assert _sr == 16000, 'feed 16 kHz mono'
segs, info = model.transcribe(pcm, language=a.lang, beam_size=a.beam, temperature=a.temp, word_timestamps=True,
                              initial_prompt=a.prompt, vad_filter=not a.novad, condition_on_previous_text=False)
res = {'model': a.model, 't0': a.t0, 'prompt': bool(a.prompt), 'segments': []}
for s in segs:
    res['segments'].append({'start': round(s.start + a.t0, 3), 'end': round(s.end + a.t0, 3), 'text': s.text.strip(),
                            'avg_logprob': round(s.avg_logprob, 3),
                            'words': [{'w': w.word.strip(), 's': round(w.start + a.t0, 3), 'e': round(w.end + a.t0, 3),
                                       'p': round(w.probability, 3)} for w in (s.words or [])]})
json.dump(res, open(a.out, 'w'), indent=1)
for s in res['segments']:
    print(f"{s['start']:6.2f}-{s['end']:6.2f} [{s['avg_logprob']:+.2f}] {s['text']}")
