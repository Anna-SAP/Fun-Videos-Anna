"""Hand corrections for timing.py, read off onset lists (onsets.py), vocal spectrograms (vocal_spectrogram.py
with the aligners' starts drawn on top) and the free transcriptions' word times. Lines and units are referred
to by index only; no lyric text here.

SEEN[(line, unit)] = start seconds
REPLACE[line] = [[start, end] per unit]   (whole lines the aligners could not follow: chants, the robot voice)
"""


def _line(starts, last=0.3):
    out = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else s + last
        out.append([round(s, 3), round(e, 3)])
    return out


REPLACE.update({
    # intro: the robot voice counts twice, 1.85-4.3 s, one syllable every ~0.4 s
    0: _line([1.85, 3.05], last=1.2),
    # drop: chants, every line one half-bar; times from the medium transcript's words, checked against onsets
    60: _line([168.84, 169.50, 169.63, 169.76], last=0.3),
    61: _line([170.12, 171.00, 171.13, 171.25], last=0.2),
    62: _line([171.48, 171.72, 171.82, 172.04, 172.16, 172.40, 172.50, 172.72], last=0.1),
    63: _line([172.84, 173.20, 173.58, 173.74, 173.90, 174.00], last=0.12),
    64: _line([174.14, 174.98, 175.07, 175.16], last=0.25),
    65: _line([175.46, 176.16, 176.30, 176.48], last=0.25),
    66: _line([176.82, 177.06, 177.16, 177.38, 177.48, 177.74, 177.82, 178.02], last=0.14),
    67: _line([178.18], last=0.3),
    # final chorus, last two lines: Re-spawn on 279.83 / 280.49, then the place name, then a five-syllable phrase;
    # the next line's English word is a chopped sample repeated on every half beat from 284.24 (re-flipped in
    # score.ECHO), the three numbers at 286.5-287.1, then the last words over 288-289.5
    105: _line([279.83, 281.62, 281.92, 282.80, 283.05, 283.25, 283.45, 283.70, 283.94], last=0.35),
    106: _line([284.24, 286.50, 286.91, 287.10, 287.97, 288.57, 288.90, 289.18, 289.42], last=0.6),
})

SEEN.update({
    # intro, line 1: the year is spoken at 4.6-5.7 s (the CTC aligner put it 1.4 s late, onto the next phrase)
    (1, 0): 4.62, (1, 1): 4.95, (1, 2): 5.15, (1, 3): 5.30, (1, 4): 5.50,
    (1, 5): 6.68, (1, 6): 6.98, (1, 7): 7.16, (1, 8): 7.50, (1, 9): 7.72, (1, 10): 7.84,
    (1, 11): 8.02, (1, 12): 8.26,
    # intro, last line: the closing English word glides down from about 16.0 s, before verse 1 starts at 16.46
    (3, 0): 14.48, (3, 1): 14.81, (3, 2): 15.15, (3, 3): 15.82, (3, 4): 16.05,
    # verse 1, line 13: the line before ends at 40.48 (both free transcriptions); the first two syllables follow
    # at 40.69 / 40.88 and the third at 41.10 (the aligners bunched all three onto 41.0-41.2)
    (13, 0): 40.69, (13, 1): 40.88, (13, 2): 41.10,
    # pre-chorus 1, line 23: the two counts are the two arching phrases at 71.46 / 71.82; the Whisper aligner
    # took the second shout of the line before for its first word
    (23, 0): 71.46, (23, 1): 71.82,
    # bridge, line 90: the two-letter word is two syllables, onsets 240.17 / 240.52; the free transcriptions agree
    (90, 0): 240.17,
    # bridge, line 92: its last syllable is at 244.68, just before the next line's first at 244.80
    (92, 6): 244.68,
})
