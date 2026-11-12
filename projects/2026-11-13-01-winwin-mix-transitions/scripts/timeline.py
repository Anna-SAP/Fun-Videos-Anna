"""Shared timeline for the re-edit of winwin_V2_mixure_clip.mp4.

Source: 1920x1080, 30 fps, 2091 frames (69.70 s), three spliced MVs:
  A1  frames   0-169  letterbox 2.35:1 (black bars 130/131 px), song 1 (~103 BPM)
  A2  frames 170-306  full frame 16:9, same song 1
  B   frames 307-900  letterbox ~3.06:1 with WHITE bars (picture rows 226-853), song 2 (~97.5 BPM, F# minor)
  C   frames 901-2090 letterbox 2.35:1 (picture rows 129-950), SM logo in top bar, song 3 (~77 BPM, A major)

Output timeline (frames at 30 fps):
  out    0-875  -> src o              (A1, A2, B)
  out  876-900  -> B src o  dissolving into C src o+25   (25-frame overlap = 0.833 s)
  out  901-2065 -> src o+25           (C)
  out 2066-2077 -> black tail (0.4 s)
"""
FPS = 30
W, H = 1920, 1080
N_SRC = 2091

A2_START = 170          # first garage frame
B_START = 307           # first frame of song 2 / white-bar MV
C_START = 901           # first frame of song 3 / SM MV
OVERLAP = 25            # B->C dissolve length in frames (aligns song 3 onsets with song 2 eighths)
DISS_OUT0 = C_START - OVERLAP          # 876: first output frame of the dissolve
C_LAST_SRC = N_SRC - 1                 # 2090
C_LAST_OUT = C_LAST_SRC - OVERLAP      # 2065
TAIL = 12
N_OUT = C_LAST_OUT + 1 + TAIL          # 2078

# native bar sizes (px, each side)
BAR_A1 = 131
BAR_B = 228   # 2 px inset inside the white-bar edge so no white fringe survives
BAR_C = 129
LOGO_BOX = (0, 129, 1640, 1920)        # rows, cols holding the SM logo in C's top bar

# key musical times (s, source timeline)
T_DROP = 185 / FPS        # song-1 drop after the stop (6.17 s)
T_B_DOWNBEAT = 317 / FPS  # first downbeat of song 2 (10.565 s)
