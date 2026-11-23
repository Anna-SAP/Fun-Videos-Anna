"""Hand-set unit times for the chanted performances (seconds). See timing2.py.

Sources: transcript word times (asr_windows.py, several windows per stretch), the vocal onset list (onsets.py),
spectrogram strips (vocal_spectrogram.py) and two measured repeats:
  - the final hook is the first hook pasted again, exactly 198.40 s (62 bars) later (onset-envelope correlation 0.7);
  - in the drop the same bar of chant repeats every 3.20 s.
Each entry: (sheet line, [onset per unit], snap to the nearest vocal onset within 40 ms?).
"""
H1 = [
    (4, [15.52, 16.00, 16.44, 16.72, 16.95, 17.20, 17.56, 17.75, 18.10, 18.43]),
    (5, [18.72, 19.15, 19.54, 19.93, 20.15, 20.35, 20.55, 20.80, 20.98, 21.20, 21.62]),
    (6, [21.93, 22.40, 22.76, 23.00, 23.15, 23.30, 23.45, 23.57, 24.12, 24.24, 24.36, 24.48]),
    (7, [25.10, 25.43, 25.68, 25.88, 26.10, 26.37, 26.55, 26.75, 26.97, 27.17, 27.37, 27.60, 27.80]),
    (8, [28.37, 28.47, 28.56, 28.68, 29.15, 29.30, 29.45, 29.97, 30.22, 30.55, 30.80, 31.05, 31.33, 31.53, 31.85]),
    (9, [32.13, 32.46, 32.75, 33.20, 33.60, 33.98, 34.23, 34.50, 34.74]),
    (9, [35.34, 35.76, 35.94, 36.42, 36.80, 37.18, 37.42, 37.66, 37.98]),
]
LAG = 198.40
DROP0, BAR = 137.6, 3.2
D40 = [0.28, 0.84, 1.20, 1.38]
D41 = [1.62, 2.01, 2.46, 2.77, 2.97]
HAND = [
    (0, [1.58, 2.00, 2.40], False),
    (1, [7.48, 7.60, 7.80], False),
    (2, [8.20, 8.60, 9.00, 9.60, 10.00, 10.50], False),
    (2, [10.80, 11.00, 11.20, 11.62, 11.80, 12.00], False),
    (3, [12.76, 13.45, 13.98, 14.66], False),
] + [(i, ts, False) for i, ts in H1] + [
    (36, [123.93, 124.17, 124.40, 124.99, 125.59], False),
    (37, [125.99, 126.23, 126.42, 126.57, 126.80, 127.01, 127.22, 127.61, 127.98], False),
    (38, [128.40, 128.79, 129.15, 129.81, 130.01, 130.40], False),
    (39, [131.24, 136.40, 136.78, 137.19], False),
] + [(40, [DROP0 + BAR * k + d for d in D40], False) for k in range(4)] \
  + [(41, [DROP0 + BAR * k + d for d in D41], False) for k in range(3)] + [
    (63, [210.80, 211.18, 211.64, 212.25, 212.60, 212.85], True),
] + [(i + 60, [t + LAG for t in ts], False) for i, ts in H1] + [
    (72, [245.20, 245.62, 246.00], False),
    (72, [248.20, 248.83, 249.20], False),
    (73, [251.00, 251.20, 251.50, 251.78, 251.98, 252.19, 252.40, 252.80], False),
]
# single-unit corrections on top of the aligner: {(line, performance#, unit): t}
FIX = {(22, 0, 0): 79.93, (53, 0, 0): 177.58, (53, 0, 1): 177.68}
# the same word repeated by the track after the sheet line is over (stutter / echo), used for picture only
ECHO = {
    'ready': [132.03, 132.45, 132.87, 133.24, 133.63, 134.04, 134.44, 134.63, 134.82, 135.03, 135.23, 135.43, 135.63, 135.99],
    'back1': [38.80, 39.20, 39.61, 40.00, 40.21, 40.41, 40.62, 40.78],
    'back2': [237.20, 237.60, 238.01, 238.40, 238.61, 238.81, 239.02, 239.18],
}
