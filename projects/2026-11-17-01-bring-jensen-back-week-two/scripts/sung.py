"""What is actually sung, in order. Each entry points at a sheet line (see lyrics.py) with a rough start/end
read from the transcriptions (work/asr/mix_large-v2.json, work/asr/win_v2.jsonl). These are only windows for
the aligner; the real per-unit times come from align.py and live in lyric_timing.json.

Entry: (id, sheet_line, rough_start, rough_end[, unit slice])

Findings that shaped this table (from the recognisers, the vocal spectrogram and the bar grid):
  * the song follows the user's sheet in order (the MP3's embedded lyrics tag is scrambled and was ignored)
  * the call-backs in half-width parentheses are sung; the intro's 'run it back' is sung twice
    (the echo is drawn as a rewind of the same words, not as extra text)
  * the drop's first line (L68) is sung twice, one bar each, before the two BRING! JENSEN! BACK! bars
"""

SUNG = [
    # Intro: news sample, then spoken-sung lines over vinyl noise
    ('i1', 2, 2.2, 7.7),
    ('i2', 4, 8.0, 10.35),
    ('i3', 5, 10.3, 13.3),
    ('i4', 6, 13.2, 19.6),
    # Verse 1 (boom bap)
    ('v1a', 9, 21.5, 24.3), ('v1b', 10, 24.2, 27.1), ('v1c', 11, 27.0, 29.7), ('v1d', 12, 29.6, 32.6),
    ('v1e', 13, 32.5, 35.3), ('v1f', 14, 35.2, 38.0), ('v1g', 15, 37.95, 40.9), ('v1h', 16, 40.85, 43.7),
    ('v1i', 17, 43.65, 47.05), ('v1j', 18, 47.0, 49.9), ('v1k', 19, 49.85, 52.3), ('v1l', 20, 52.25, 54.95),
    ('v1m', 21, 54.9, 57.4), ('v1n', 22, 57.35, 60.15), ('v1o', 23, 60.1, 63.65), ('v1p', 24, 63.6, 66.42),
    # Pre-chorus (drums out, 808 heartbeat, riser)
    ('p1a', 27, 66.38, 69.12), ('p1b', 28, 69.08, 72.22), ('p1c', 29, 72.18, 74.8), ('p1d', 30, 74.75, 77.5),
    # Hook 1
    ('h1a', 33, 77.45, 80.58), ('h1b', 34, 80.54, 83.26), ('h1c', 35, 83.22, 86.1), ('h1d', 36, 86.06, 88.86),
    ('h1e', 37, 88.82, 91.48), ('h1f', 38, 91.44, 93.64), ('h1g', 39, 93.6, 96.4), ('h1h', 40, 96.36, 99.12),
    # Verse 2 (trap, Washington)
    ('v2a', 43, 99.08, 101.78), ('v2b', 44, 101.74, 104.36), ('v2c', 45, 104.32, 107.38), ('v2d', 46, 107.34, 110.14),
    ('v2e', 47, 110.1, 112.94), ('v2f', 48, 112.9, 115.54), ('v2g', 49, 115.5, 118.54), ('v2h', 50, 118.5, 121.36),
    ('v2i', 51, 121.32, 124.08), ('v2j', 52, 124.04, 126.82), ('v2k', 53, 126.78, 129.52), ('v2l', 54, 129.48, 132.3),
    ('v2m', 55, 132.26, 135.08), ('v2n', 56, 135.04, 137.94), ('v2o', 57, 137.9, 141.44),
    # Build: call and response
    ('b1', 60, 141.0, 143.7), ('b2', 61, 143.6, 146.24), ('b3', 62, 146.2, 147.7), ('b4', 63, 147.66, 149.02),
    ('b5', 64, 148.98, 151.16), ('b6', 65, 151.12, 153.52),
    # Drop: L68 twice, then the two BRING! JENSEN! BACK! bars
    ('d1', 68, 153.48, 156.85), ('d2', 68, 156.8, 160.16), ('d3', 70, 160.1, 162.6), ('d4', 71, 162.55, 165.2),
    # Interlude: Taipei
    ('t1', 74, 165.5, 168.52), ('t2', 75, 168.48, 171.58), ('t3', 76, 171.54, 173.92), ('t4', 77, 173.88, 176.84),
    # Verse 3 (boom bap + trap hats): board and market
    ('v3a', 80, 176.8, 179.08), ('v3b', 81, 179.04, 181.96), ('v3c', 82, 181.92, 184.54), ('v3d', 83, 184.5, 187.14),
    ('v3e', 84, 187.1, 190.0), ('v3f', 85, 189.96, 192.66), ('v3g', 86, 192.62, 195.74), ('v3h', 87, 195.7, 198.74),
    ('v3i', 88, 198.7, 201.62), ('v3j', 89, 201.58, 204.5), ('v3k', 90, 204.46, 207.38), ('v3l', 91, 207.34, 210.04),
    ('v3m', 92, 210.0, 213.38), ('v3n', 93, 213.34, 216.02), ('v3o', 94, 215.98, 218.9), ('v3p', 95, 218.86, 222.48),
    # Bridge (half time, piano + pad)
    ('r1', 98, 222.44, 225.22), ('r2', 99, 225.18, 228.02), ('r3', 100, 227.98, 230.4), ('r4', 101, 230.36, 232.9),
    ('r5', 102, 232.86, 236.98), ('r6', 103, 236.94, 239.14), ('r7', 104, 239.1, 245.36),
    # Final hook
    ('h2a', 107, 245.3, 248.32), ('h2b', 108, 248.28, 251.04), ('h2c', 109, 251.0, 254.0), ('h2d', 110, 253.96, 256.8),
    ('h2e', 111, 256.76, 259.38), ('h2f', 112, 259.34, 262.1), ('h2g', 113, 262.0, 264.64), ('h2h', 114, 264.6, 268.22),
    # Outro (synth filtered out, vinyl noise and piano); the last line is sung twice, the second time at the very end
    ('o1', 117, 268.18, 270.96), ('o2', 118, 270.92, 273.6), ('o3', 119, 273.56, 276.56), ('o4', 120, 276.52, 279.12),
    ('o5', 121, 279.08, 281.46), ('o6', 122, 281.42, 284.7), ('o7', 123, 284.9, 287.6), ('o8', 123, 296.5, 299.9),
]


def entries():
    out = []
    for e in SUNG:
        sl = e[4] if len(e) > 4 else None
        out.append({'id': e[0], 'line': e[1], 't0': e[2], 't1': e[3], 'slice': sl})
    return out
