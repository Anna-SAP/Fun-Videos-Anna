#!/usr/bin/env python3
"""Independent Chinese listens with sherpa-onnx: SenseVoice and Paraformer (CPU, int8).

  asr_sherpa.py AUDIO16K.wav OUT.jsonl RANGES [--win 10 --hop 5]

Windows of WIN seconds every HOP seconds over RANGES ("88-166,212-315"). Paraformer also returns a time for
every character, which gives a second, Whisper-independent timing estimate.
"""
import argparse
import glob
import json

import numpy as np
import sherpa_onnx
import soundfile as sf

ap = argparse.ArgumentParser()
ap.add_argument('audio')
ap.add_argument('out')
ap.add_argument('ranges')
ap.add_argument('--win', type=float, default=10)
ap.add_argument('--hop', type=float, default=5)
a = ap.parse_args()


def mdir(name):
    return glob.glob(f'work/models/models--csukuangfj--{name}/snapshots/*/')[0]


sv = mdir('sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17')
pf = mdir('sherpa-onnx-paraformer-zh-2024-03-09')
recs = {
    'sensevoice': sherpa_onnx.OfflineRecognizer.from_sense_voice(model=sv + 'model.int8.onnx', tokens=sv + 'tokens.txt',
                                                                 language='zh', use_itn=False, num_threads=4),
    'paraformer': sherpa_onnx.OfflineRecognizer.from_paraformer(paraformer=pf + 'model.int8.onnx', tokens=pf + 'tokens.txt',
                                                                num_threads=4),
}
pcm, sr = sf.read(a.audio, dtype='float32')
assert sr == 16000
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
with open(a.out, 'a') as fo:
    for name, rec in recs.items():
        for t0, t1 in wins:
            st = rec.create_stream()
            st.accept_waveform(sr, pcm[int(t0 * sr):int(t1 * sr)])
            rec.decode_stream(st)
            res = st.result
            ts = [round(t0 + float(x), 3) for x in (res.timestamps or [])]
            row = {'model': name, 't0': t0, 't1': t1, 'text': res.text, 'tokens': list(res.tokens), 'ts': ts}
            fo.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(f'{name[:5]} {t0:6.1f} {res.text}', flush=True)
