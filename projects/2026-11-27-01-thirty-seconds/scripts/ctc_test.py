#!/usr/bin/env python3
"""Hypothesis test: force candidate texts through the CTC emissions of one window and compare mean posteriors.
  ctc_test.py T0 T1 TEXT [TEXT ...]      (texts are passed in memory only; nothing is written)"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctc
from pypinyin import lazy_pinyin
t0, t1 = float(sys.argv[1]), float(sys.argv[2])
for i, txt in enumerate(sys.argv[3:]):
    ids = [ctc.romanise_py(p) for p in lazy_pinyin(txt)]
    for src in ('voc', 'mix'):
        r = ctc.align(ids, t0, t1, src)
        if r:
            print(f'H{i} {src}: mean {np.mean([s for _, _, s in r]):.3f} min {min(s for _, _, s in r):.2f} starts ' + ' '.join(f'{a:.2f}' for a, _, _ in r))
        else:
            print(f'H{i} {src}: no path')
