#!/usr/bin/env python3
"""Locate where one recording appears inside another by audio cross-correlation.

Typical uses in this repo
  * NEON (project 02): where does the 23 s AI-cartoon clip sit inside the official MV?
  * Project 01: which parts of the merged video came from plan 3 / plan 4?
  * Project 03: confirm that split source parts line up with the transcription track.

How it works
  1. Both files are decoded to mono float32 PCM at --sr Hz with ffmpeg.
  2. The needle is cut into windows (--win seconds, every --step seconds).
  3. Each window is matched against the whole haystack with FFT cross-correlation,
     normalised by the haystack's local energy (true NCC, 1.0 = identical).
     Quiet haystack regions are masked so silence cannot win.
  4. For every window the best haystack time and implied offset are printed.
     A constant offset across windows = clean alignment; a drifting offset = speed
     difference; NCC < ~0.5 = that window is not in the haystack.

usage: find_offset.py NEEDLE HAYSTACK [--sr 8000] [--win 3] [--step 2]
requires: ffmpeg on PATH, numpy, scipy
"""
import argparse
import subprocess
import sys

import numpy as np
from scipy.signal import fftconvolve


def decode(path, sr):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def best_match(seg, hay, sr):
    seg = seg - seg.mean()
    n = np.linalg.norm(seg)
    if n < 1e-6:
        return None
    r = fftconvolve(hay, seg[::-1], mode="valid")
    w = len(seg)
    cs = np.concatenate([[0.0], np.cumsum(hay ** 2)])
    loc = np.sqrt(np.maximum(cs[w:] - cs[:-w], 0.0)) + 1e-9
    ncc = r / (loc * n)
    ncc[loc < 0.3 * n] = 0.0          # ignore near-silent stretches of the haystack
    k = int(np.argmax(ncc))
    return k / sr, float(ncc[k])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("needle")
    ap.add_argument("haystack")
    ap.add_argument("--sr", type=int, default=8000)
    ap.add_argument("--win", type=float, default=3.0, help="window length in seconds")
    ap.add_argument("--step", type=float, default=2.0, help="window hop in seconds")
    a = ap.parse_args()

    needle, hay = decode(a.needle, a.sr), decode(a.haystack, a.sr)
    print(f"needle {len(needle)/a.sr:.2f}s  haystack {len(hay)/a.sr:.2f}s")
    print(f"{'needle_t':>9} {'haystack_t':>11} {'offset(h-n)':>12} {'ncc':>6}")
    offsets = []
    t = 0.0
    while t + a.win <= len(needle) / a.sr:
        seg = needle[int(t * a.sr):int((t + a.win) * a.sr)]
        m = best_match(seg, hay, a.sr)
        if m is None:
            print(f"{t:9.2f} {'(silent)':>11}")
        else:
            ht, c = m
            print(f"{t:9.2f} {ht:11.3f} {ht - t:12.4f} {c:6.2f}")
            if c > 0.5:
                offsets.append(ht - t)
        t += a.step
    if offsets:
        o = np.array(offsets)
        print(f"\nconfident windows: {len(o)}  median offset {np.median(o):.4f}s  spread {o.max()-o.min():.4f}s")
    else:
        print("\nno confident match", file=sys.stderr)


if __name__ == "__main__":
    main()
