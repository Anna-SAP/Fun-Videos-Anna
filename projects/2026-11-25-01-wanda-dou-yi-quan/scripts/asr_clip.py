#!/usr/bin/env python3
"""Transcribe short stretches several ways (independent listens).  asr_clip.py MODEL_DIR "wav1,wav2" "t0-t1,t0-t1" [PROMPT]"""
import os, sys
import soundfile as sf
from faster_whisper import WhisperModel
m = WhisperModel(sys.argv[1], device='cpu', compute_type='int8', cpu_threads=os.cpu_count())
prompt = sys.argv[4] if len(sys.argv) > 4 else None
for wav in sys.argv[2].split(','):
    pcm = sf.read(wav, dtype='float32')[0]
    for r in sys.argv[3].split(','):
        t0, t1 = map(float, r.split('-'))
        for temp in (0.0, 0.4):
            segs, _ = m.transcribe(pcm[int(t0*16000):int(t1*16000)], language='zh', beam_size=5, temperature=temp, word_timestamps=True,
                                   initial_prompt=prompt, vad_filter=False, condition_on_previous_text=False)
            for s in segs:
                print(os.path.basename(wav), r, 'T', temp, round(s.start+t0,2), round(s.end+t0,2), s.text, ' '.join(f"{w.word}@{w.start+t0:.2f}" for w in s.words), flush=True)
