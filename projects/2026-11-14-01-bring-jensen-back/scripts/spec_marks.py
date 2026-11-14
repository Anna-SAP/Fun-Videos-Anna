#!/usr/bin/env python3
"""Draw the vocal spectrogram of [t0, t1] with every aligned unit start marked (labels are id.k, no words).
  spec_marks.py T0 T1 OUT.png [timing.json]"""
import json, subprocess, sys
t0, t1, out = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
tim = json.load(open(sys.argv[4] if len(sys.argv) > 4 else 'work/audio/lyric_timing.json'))
marks = [[u['s'], f"{e['id']}.{k}"] for e in tim for k, u in enumerate(e['units']) if t0 <= u['s'] <= t1]
json.dump(marks, open('work/qc/_marks.json', 'w'))
subprocess.run(['python3', 'scripts/vocal_spectrogram.py', 'work/audio/vocals22k.wav', out, str(t0), str(t1), '200',
                'work/qc/_marks.json'], check=True)
