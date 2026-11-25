#!/usr/bin/env python3
"""Whole-song transcription with faster-whisper (CPU int8), word timestamps.
  asr_full.py MODEL_DIR AUDIO16K.wav OUT.json [PROMPT_FILE]
"""
import json, os, sys
import soundfile as sf
from faster_whisper import WhisperModel
mdir, wav, out = sys.argv[1:4]
prompt = open(sys.argv[4], encoding='utf-8').read() if len(sys.argv) > 4 else None
pcm = sf.read(wav, dtype='float32')[0]
m = WhisperModel(mdir, device='cpu', compute_type='int8', cpu_threads=os.cpu_count())
segs, info = m.transcribe(pcm, language='zh', beam_size=5, temperature=0.0, word_timestamps=True,
                          initial_prompt=prompt, vad_filter=False, condition_on_previous_text=False)
res = []
for s in segs:
    res.append({'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip(), 'lp': round(s.avg_logprob, 2),
                'nsp': round(s.no_speech_prob, 2),
                'words': [{'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3), 'p': round(w.probability, 2)} for w in (s.words or [])]})
    print(res[-1]['start'], res[-1]['end'], res[-1]['text'], flush=True)
json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)
