#!/usr/bin/env python3
"""The 30 shots (storyboard.md section 6). Cuts come from work/audio/cuts.json (the measured line starts on the
tracked grid) except the fixed ones: chorus downbeats, the Bridge (bar 82) and the outro. Geometry in FX is
read off the keyframes in keyframe pixels (1088x1920); lyric placement (cy) is in output pixels.

expo: night = the verse rule (plate 2.5 stops down, fog), flood = chorus floodlight, dark = K13,
      black = K20 in the dark, blue = the cyanotype stretch, warm = window light (still black and white).
"""
import timeline as T
from timeline import Shot, c, B

SRC_UL, SRC_UR, SRC_L, SRC_R, SRC_B = (-260, -420), (1340, -420), (-420, 700), (1500, 760), (495, 2300)

SHOTS = [
    Shot('s01', 'K01', 0.0, c('s02'), z=(1.0, 1.02), c=(544, 1000), fade_in=2.89, fog=0.30,
         lyr=dict(mode='spot', cy=1090, width=0.5, src=SRC_UL, expo='night')),
    Shot('s02', 'K02', c('s02'), c('s03'), snow=1.0, fog=0.30,
         lyr=dict(mode='light', cy=800, src=SRC_UR, expo='night')),
    Shot('s03', 'K03', c('s03'), c('s04'), z=(1.0, 1.04), c=(544, 760), snow=0.6, fog=0.30,
         lyr=dict(mode='light', cy=1080, src=SRC_UL, expo='night')),
    Shot('s04', 'K04', c('s04'), c('s05'), fog=0.22,
         lyr=dict(mode='light', cy=720, src=SRC_UR, expo='night', cy_line={'Verse 1|6': 1270}, src_line={'Verse 1|6': SRC_UL})),
    Shot('s05', 'K05', c('s05'), c('s06'), fog=0.0, fx=('flash@50.30',),
         lyr=dict(mode='light', cy=560, src=SRC_UL, expo='night')),
    Shot('s06', 'K06', c('s06'), c('s07'), fog=0.30, fx=('suns',),
         lyr=dict(mode='light', cy=1090, src=SRC_UR, expo='night', fast=True, air=0.10)),
    Shot('s07', 'K07', c('s07'), c('s08'), fog=0.25,
         lyr=dict(mode='light', cy=780, src=SRC_L, expo='night', fast=True, air=0.20)),
    Shot('s08', 'K08', c('s08'), B(39), z=(1.0, 1.04), c=(527, 866), fog=0.22, fx=('point',),
         lyr=dict(mode='light', cy=500, src=SRC_UL, expo='night', fast=True)),
    Shot('s09', 'K09', B(39), c('s10'), fog=0.20,
         lyr=dict(mode='shadow', cy=860, expo='flood', flood_on=B(39), shear=0.42)),
    Shot('s10', 'K10', c('s10'), c('s11'), fog=0.15, fx=('filament',),
         lyr=dict(mode='shadow', cy=860, expo='flood', flood_on=c('s10'), shear=0.0, lens=(527, 860, 330))),
    Shot('s11', 'K11', c('s11'), c('s12'), fog=0.18,
         lyr=dict(mode='light', cy=900, src=SRC_B, expo='night', air=0.16)),
    Shot('s12', 'K12', c('s12'), c('s13'), fog=0.15,
         lyr=dict(mode='light', cy=1250, src=SRC_R, expo='night', air=0.22)),
    Shot('s13', 'K11', c('s13'), c('s14'), fog=0.18, fx=('ships',),
         lyr=dict(mode='light', cy=900, src=SRC_B, expo='night', air=0.16)),
    Shot('s14', 'K13', c('s14'), c('s15'), fog=0.55,
         lyr=dict(mode='dark', cy=820, expo='dark')),
    Shot('s15', 'K14', c('s15'), c('s16'), fog=0.30,
         lyr=dict(mode='light', cy=600, src=SRC_UR, expo='night', kick=True)),
    Shot('s16', 'K15', c('s16'), B(66), fog=0.20,
         lyr=dict(mode='light', cy=800, src=SRC_L, expo='night', kick=True)),
    Shot('s17', 'K16', B(66), c('s18'), fog=0.30, fx=('twin',),
         lyr=dict(mode='shadow', cy=1180, expo='flood', flood_on=B(66), shear=0.38, twin=True)),
    Shot('s18', 'K17', c('s18'), c('s19'), z=(1.0, 1.04), c=(560, 980), fog=0.15,
         lyr=dict(mode='light', cy=420, src=SRC_UL, expo='night')),
    Shot('s19', 'K18', c('s19'), c('s20'), fog=0.18, fx=('lamps',),
         lyr=dict(mode='light', cy=640, src=SRC_UL, expo='night')),
    Shot('s20', 'K19', c('s20'), c('s21'), fog=0.30, fx=('rings', 'burst'),
         lyr=dict(mode='light', cy=1060, src=SRC_L, expo='night', air=0.12)),
    Shot('s21', 'K15', c('s21'), B(82), fade_out=0.40, fade_out_at=T.GAP[0], fog=0.20, fx=('halfwin',),
         lyr=dict(mode='light', cy=800, src=SRC_L, expo='night')),
    Shot('s22', 'K20', B(82), c('s23'), fade_in=1.70, fade_in_at=T.GAP[0], fog=0.12, fx=('fall', 'whitepush'),
         lyr=dict(mode='diffuse', cy=1150, expo='black')),
    Shot('s23', 'K21', c('s23'), c('s24'), z=(0.93, 0.93), fog=0.0, fx=('develop', 'dot'),
         lyr=dict(mode='print', cy=1150, expo='blue', proj=(0, 0), mode_line={'Verse 4|1': 'thin'})),
    Shot('s24', 'K22', c('s24'), c('s25'), z=(1.0, 1.04), c=(630, 916), fog=0.08,
         lyr=dict(mode='thin', cy=1260, expo='blue', proj=(0, 0))),
    Shot('s25', 'K23', c('s25'), c('s26'), fog=0.08,
         lyr=dict(mode='thin', cy=1250, expo='blue', proj=(0, 0))),
    Shot('s26', 'K24', c('s26'), B(107), fog=0.12, fx=('trails',),
         lyr=dict(mode='thin', cy=820, expo='blue', proj=(0, 0))),
    Shot('s27', 'K09', B(107), c('s28'), fog=0.20,
         lyr=dict(mode='shadow', cy=860, expo='flood', flood_on=B(107), shear=0.42, flood_off=(B(107) + 0.3, 227.86))),
    Shot('s28', 'K25', c('s28'), c('s29'), z=(1.25, 1.25), c=(544, 1180), snow=0.9, fog=0.18,
         lyr=dict(mode='window', cy=880, expo='warm', glow_at=(533, 1501))),
    Shot('s29', 'K26', c('s29'), 246.60, z=(1.0, 1.04), c=(620, 1000), fade_out=1.15, fog=0.10, fx=('fish',),
         lyr=dict(mode='window', cy=430, expo='warm')),
    Shot('s30', 'K01', 246.60, T.AUDIO_DUR + 0.5, z=(1.0, 1.0), c=(544, 1000), fade_in=1.6, fade_in_at=246.9, fog=0.30,
         fx=('outro',), lyr=dict(mode='spot', cy=1090, width=0.5, src=SRC_UL, expo='night',
                                 mode_line={'Outro|2': 'cloud'}, cy_line={'Outro|2': 470})),
]
T.SHOTS[:] = SHOTS

# keyframe-pixel geometry read off the keyframes (gridview.py)
FX = {
    'suns': [(220, 410, 50, -20, 6), (586, 214, 40, 12, -5), (912, 476, 24, 36, 9)],   # x, y, r, dx, dy over the shot
    'point': (527, 866),
    'filament': (527, 900),
    'lamp_region': (150, 0, 900, 1300),
    'mast_top': (244, 860),
    'disc': (718, 370),
    'star': (502, 420),
    'k16_lamps': [(181, 707, +1), (899, 707, -1)],
    'paper_fall': 28.0,          # output px per second of the clock
    'lamp_off': 263.75,
    'black_at': 264.04,
}


def shot_at(t):
    for s in SHOTS:
        if s.t0 <= t < s.t1:
            return s
    return SHOTS[-1]
