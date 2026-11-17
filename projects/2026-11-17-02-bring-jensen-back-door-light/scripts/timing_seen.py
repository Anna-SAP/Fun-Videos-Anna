# Hand corrections for timing.py: times only, read from scripts/onsets.py lists and vocal_spectrogram.py sheets.

# Hooks: "Bring / Jensen / Back! / (Back!)" has the same shape every bar. Bring starts where Whisper says
# (the four starts are exactly one bar apart); the held "Back!" note starts 0.68 s later on the spectrogram.
for _li in (24, 25, 26, 27, 83, 84, 85, 86):
    _t = Wd[_li]['units'][0][0]
    SEEN[(_li, 0)] = _t
    SEEN[(_li, 1)] = _t + 0.33
    SEEN[(_li, 2)] = _t + 0.68
    SEEN[(_li, 3)] = _t + 0.89
SEEN[(24, 4)] = 81.32

# Build: the calls and the shouted answers (onset list 145-158 s)
SEEN.update({(47, 0): 147.02, (47, 1): 147.19, (47, 2): 147.37, (47, 3): 147.57, (47, 4): 147.74, (47, 5): 147.93,
             (47, 6): 148.11, (47, 7): 148.28, (47, 8): 148.78, (47, 9): 148.95, (47, 10): 149.13})
# countdown
SEEN.update({(52, 0): 157.66, (52, 1): 158.37, (52, 2): 158.70, (52, 3): 159.06})

# Drop: the chant is sung three times, one bar each (2.824 s), then once more cut short and answered by the
# hook line. One "Hey" is shouted per answer; the sheet writes two, the second is shown as its echo.
_B = 2.824
_c = {0: 159.66, 1: 160.12, 2: 160.45, 3: 160.83, 4: 161.00, 5: 161.19, 6: 161.56, 7: 161.88, 8: 162.25, 9: 162.42}
EXTRA[53] = []
for _n in range(3):
    _d = {k: v + _B * _n for k, v in _c.items()}
    _d['replace'] = True
    EXTRA[53].append(_d)
EXTRA[53].append({1: 168.63, 2: 168.97, 'last': 0.33})
EXTRA[54] = [{'replace': True, 0: 169.36, 1: 169.67, 2: 170.00, 'last': 0.5}]
EXTRA[55] = [{'replace': True}]

# Build: two caller tags ("the board answers:", "the White House says:") are not audible as separate
# syllables; they are shown as a tag just before the answer they introduce.
SEEN.update({(48, 0): 149.28, (48, 1): 149.33, (48, 2): 149.38, (48, 3): 149.43,
             (48, 4): 149.49, (48, 5): 149.66, (48, 6): 149.84, (48, 7): 150.01,
             (49, 0): 151.38, (49, 1): 151.43, (49, 2): 151.48,
             (49, 3): 151.57, (49, 4): 151.74, (49, 5): 151.95, (49, 6): 152.12,
             (49, 7): 152.31, (49, 8): 152.47, (49, 9): 152.62})

# the hook's last line (onset list): run / Bring sit on clear onsets
SEEN.update({(31, 2): 100.73, (31, 5): 101.47, (90, 2): 272.85, (90, 5): 273.59})
SEEN.update({(3, 11): 17.29, (96, 1): 290.06})

# the last line is sung twice: once spoken-sung, then once more as a held melody (spectrogram 292-298 s)
SEEN.update({(97, 0): 293.00, (97, 1): 293.35, (97, 2): 293.68, (97, 3): 294.45, (97, 4): 294.63, (97, 5): 294.78})
EXTRA[97] = [{0: 295.52, 1: 295.90, 2: 296.28, 3: 296.62, 4: 297.00, 5: 297.38, 'last': 0.75}]

# Bridge (spectrogram): the three phrases each end on a held note; "No side door / no back door"
SEEN.update({(80, 0): 239.85, (80, 1): 240.03, (80, 2): 240.22, (80, 3): 240.40, (80, 4): 240.95, (80, 5): 241.30,
             (80, 6): 241.68, (80, 7): 241.90, (80, 8): 242.05, (80, 9): 242.62, (80, 10): 242.78,
             (80, 11): 243.50, (80, 12): 243.72, (80, 13): 243.95, (80, 14): 244.25})
SEEN.update({(81, 0): 245.02, (81, 1): 245.42, (81, 2): 245.72, (81, 3): 246.45, (81, 4): 246.82, (81, 5): 247.20})
# Interlude: the second facade line
SEEN.update({(58, 6): 177.50, (58, 7): 178.05})

# Verse 1, first line (spectrogram 21.5-25.9 s): three counts before the drums, the rest on the downbeat
SEEN.update({(4, 0): 21.64, (4, 1): 21.96, (4, 2): 22.36, (4, 3): 22.88, (4, 4): 23.36, (4, 5): 23.55, (4, 6): 23.96,
             (4, 7): 24.16, (4, 8): 24.47, (4, 9): 24.66, (4, 10): 24.82, (4, 11): 24.95, (4, 12): 25.08})

# Verse 3, first two lines (spectrogram 181.5-188.4 s): both aligners started the second line inside the
# first; the first ends on a held falling note at 183.72 and the second starts after it.
SEEN.update({(60, 0): 181.97, (60, 1): 182.09, (60, 2): 182.16, (60, 3): 182.30, (60, 4): 182.44, (60, 5): 182.65,
             (60, 6): 182.80, (60, 7): 182.97, (60, 8): 183.20, (60, 9): 183.36, (60, 10): 183.52, (60, 11): 183.72})
SEEN.update({(61, 0): 184.25, (61, 1): 184.42, (61, 2): 184.62, (61, 3): 184.80, (61, 4): 185.00, (61, 5): 185.18,
             (61, 6): 185.35, (61, 7): 185.50, (61, 8): 185.68, (61, 9): 185.85, (61, 10): 186.05, (61, 11): 186.22,
             (61, 12): 186.40, (61, 13): 186.75, (61, 14): 186.97, (61, 15): 187.14, (61, 16): 187.32})

# Final hook (onset list): Bring / Jensen / Back! on clear onsets, the answer a fifth of a second after
for _li, _t, _b in ((83, 251.70, 252.42), (84, 254.62, 255.33), (85, 257.52, 258.25), (86, 260.47, 261.17)):
    SEEN.update({(_li, 0): _t, (_li, 1): _t + 0.33, (_li, 2): _b, (_li, 3): _b + 0.21})

# Intro (spectrogram 4-11 s): the news sample is two spoken phrases with a pause between them
SEEN.update({(0, 0): 4.30, (0, 1): 4.65, (0, 2): 5.70, (0, 3): 6.20, (0, 4): 6.85, (1, 4): 10.02, (1, 5): 10.45})

# The title line in both hooks (spectrogram). The first answer has no onset of its own (four transcriptions
# of each hook hear only the second answer); it is shown as an echo while the called word is still held.
SEEN.update({(28, 0): 91.40, (28, 1): 91.55, (28, 2): 91.87, (28, 3): 92.06, (28, 4): 92.16,
             (28, 5): 92.40, (28, 6): 92.55, (28, 7): 92.95, (28, 8): 93.50, (28, 9): 93.70})
SEEN.update({(87, 0): 263.47, (87, 1): 263.62, (87, 2): 263.80, (87, 3): 263.98, (87, 4): 264.08,
             (87, 5): 264.25, (87, 6): 264.40, (87, 7): 264.75, (87, 8): 265.35, (87, 9): 265.60})

# line-final syllables that sit on a held note (spectrogram)
SEEN.update({(21, 12): 73.92, (70, 14): 212.57, (70, 15): 212.95})
