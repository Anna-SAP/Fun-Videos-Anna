"""The Moment You Saw Me: timeline, shared by render.py and finish.py. All times are seconds.

The song is exactly 72 BPM, so at 24 fps one beat is 20 frames and one bar is 80 frames. Bar 1 starts on
frame 74 (3.083 s, the first piano attack is at 3.095 s). Every cut sits on that grid.

The second half of the recording (bars 29-52) is a sample-exact repeat of bars 5-28, 80.000 s later. The
film answers that by telling the same rainy afternoon twice: first what she hid, then what he saw.

A view is (position in the shot 0..1, centre x 0..1, centre y 0..1, zoom). Zoom 1 is a 1040 px wide window
into the 1088 px wide keyframe.
"""
from dataclasses import dataclass, field

FPS = 24
W, H = 1080, 1920
BAR0, BAR, BEAT = 74, 80, 20
TOTAL = 183.0
REPEAT = 80.0                       # the second telling starts exactly this much later


def B(bar, beat=1.0):
    """Time of a bar (and beat within it), both counted from 1."""
    return (BAR0 + BAR * (bar - 1) + BEAT * (beat - 1)) / FPS


# The one real event in a song with 4 dB of dynamic range: before the chorus the band stops dead for
# 0.44 s (55.97-56.41 s) while the voice crosses alone into the title line.
GAP1 = (55.96, B(17))
GAP2 = (GAP1[0] + REPEAT, B(41))
SLOW = ((B(13), GAP1), (B(37), GAP2))          # pre-chorus: two long held notes, the rain slows down
PULSES = [B(b, k) for b in range(1, 53) for k in (2, 4)]      # a soft brushed tick on beats 2 and 4, all the way through


def rate(t):
    """How fast time runs for the rain and the handheld drift: 1 normally, slow under the held notes, 0 in the gap."""
    for s0, (g0, g1) in SLOW:
        if s0 <= t < g1:
            if t >= g0:
                return 0.0
            if t > g0 - .5:
                return .3 * (g0 - t) / .5
            return 1 - .7 * min(1.0, (t - s0) / 2.2)
    return 1.0


_phi = [0.0]
for _n in range(int(TOTAL * FPS) + 48):
    _phi.append(_phi[-1] + rate(_n / FPS) / FPS)


def phi(t):
    """Warped time: the integral of rate()."""
    x = max(0.0, t) * FPS
    i = min(int(x), len(_phi) - 2)
    return _phi[i] + (_phi[i + 1] - _phi[i]) * (x - i)


@dataclass
class Shot:
    id: str
    kf: str
    t0: float
    views: list
    par: float = 16          # sideways parallax, output px over the shot, at full depth difference
    parv: float = 0          # vertical parallax
    dolly: float = .03       # near things grow faster than far things
    focus: float = .6        # depth that stays put
    hand: float = .35        # handheld amount: this is a still song
    gain: tuple = (1.0, 1.0)     # exposure at the start and end of the shot
    warm: tuple = (0.0, 0.0)     # white balance shift at start and end: + is warmer
    spin: float = 0          # degrees of roll over the shot
    rain: float = 0          # 0 none, 1 steady rain
    rnear: float = 1.0       # rain between the lens and a close subject: turn down for faces
    sun: float = 0           # 0 grey rain, 1 backlit golden rain
    fx: tuple = ()
    extra: dict = field(default_factory=dict)
    fade_in: float = 0
    fade_out: float = 0
    dis: float = 0           # dissolve in from the previous shot
    blur: tuple = (0.0, 0.0)     # defocus sigma at start and end
    t1: float = 0
    idx: int = 0


def V(*v):
    return [tuple(x) for x in v]


SHOTS = [
    # ---- before the piano, and the intro: a muffled pad, then piano in the dark, a wordless hum
    Shot('s01', 'K01', 0.0, V((0, .5, .5, 1.0), (1, .5, .49, 1.07)), par=10, hand=.15, fade_in=2.9, blur=(16, 0),
         extra={'blur_end': B(1) + .5, 'title': (B(1) + .8, B(3) - .5)}),
    Shot('s02', 'K02', B(3), V((0, .5, .5, 1.0), (1, .5, .5, 1.06)), par=12, hand=.2, dis=1.5),

    # ---- verse, first telling: the hidden part
    Shot('s03', 'K03', B(5), V((0, .5, .5, 1.07), (1, .5, .5, 1.01)), par=-10, hand=.3),
    Shot('s04', 'K04', B(6), V((0, .5, .5, 1.02), (1, .5, .5, 1.08)), par=14, hand=.3, gain=(1.0, .78)),
    Shot('s05', 'K05', B(7), V((0, .5, .5, 1.0), (1, .5, .52, 1.08)), par=18, hand=.25, gain=(1.3, 1.4)),
    Shot('s06', 'K06', B(9), V((0, .47, .5, 1.04), (1, .53, .5, 1.04)), par=24, hand=.5, rain=1),
    Shot('s07', 'K07', B(10), V((0, .5, .5, 1.06), (1, .5, .5, 1.0)), par=-16, hand=.25, fx=('steam',)),
    Shot('s08', 'K08', B(11), V((0, .5, .47, 1.0), (1, .5, .45, 1.1)), par=14, hand=.3, rain=1),

    # ---- pre-chorus: two held notes, the air opens, the rain slows
    Shot('s09', 'K10', B(13), V((0, .5, .53, 1.07), (1, .5, .5, 1.0)), par=0, parv=10, hand=.25, fx=('rings',),
         warm=(-.15, .2), dis=.5),
    Shot('s10', 'K09', B(15), V((0, .5, .5, 1.0), (1, .5, .49, 1.08)), par=12, hand=.25, rain=.85, sun=.45, rnear=.5,
         warm=(-.2, .4), gain=(.92, 1.04), dis=.4),

    # ---- chorus: the moment, from where she sits
    Shot('s11', 'K11', B(17), V((0, .5, .56, 1.06), (1, .5, .47, 1.0)), par=10, parv=-14, hand=.4, rain=1, sun=1, fx=('flood',)),
    Shot('s12', 'K12', B(18), V((0, .5, .5, 1.0), (1, .5, .49, 1.08)), par=14, hand=.35, rain=.8, sun=1, rnear=.3),
    Shot('s13', 'K13', B(19, 3), V((0, .5, .5, 1.05), (1, .51, .5, 1.1)), par=-12, hand=.45, rain=.6, sun=1, rnear=.25),
    Shot('s14', 'K14', B(21), V((0, .46, .5, 1.05), (1, .54, .5, 1.05)), par=26, hand=.35, rain=.8, sun=1),
    Shot('s15', 'K15', B(22), V((0, .5, .5, 1.08), (1, .5, .48, 1.02)), par=12, hand=.35, rain=1, sun=1),
    Shot('s16', 'K16', B(23), V((0, .5, .47, 1.12), (1, .5, .47, 1.0)), par=14, hand=.25, rain=1, sun=1, fx=('twinkle',)),

    # ---- interlude: the voice is gone, a low warm bed and the brushed pulse
    Shot('s17', 'K17', B(25, 3), V((0, .5, .5, 1.1), (1, .5, .5, 1.02)), par=0, hand=.2, spin=5, fx=('plinks', 'twinkle'), dis=1.6),
    Shot('s18', 'K18', B(27), V((0, .5, .52, 1.0), (1, .5, .47, 1.06)), par=20, parv=-8, hand=.3, rain=.8, dis=1.8),

    # ---- verse, second telling: the same days from where he stood
    Shot('s19', 'K19', B(29), V((0, .52, .5, 1.02), (1, .48, .5, 1.06)), par=-22, hand=.35),
    Shot('s20', 'K20', B(30), V((0, .5, .5, 1.0), (1, .5, .49, 1.06)), par=14, hand=.3),
    Shot('s21', 'K21', B(31), V((0, .5, .5, 1.08), (1, .5, .5, 1.0)), par=-18, hand=.3, fx=('steam',)),
    Shot('s22', 'K22', B(33), V((0, .53, .5, 1.04), (1, .47, .5, 1.04)), par=-24, hand=.45, rain=1),
    Shot('s23', 'K23', B(34), V((0, .5, .5, 1.0), (1, .5, .5, 1.06)), par=12, hand=.3, rain=.8),
    Shot('s24', 'K24', B(35), V((0, .5, .49, 1.0), (1, .5, .47, 1.1)), par=20, hand=.4, rain=1),

    # ---- pre-chorus again: he walks over
    Shot('s25', 'K25', B(37), V((0, .5, .5, 1.0), (1, .5, .48, 1.09)), par=16, hand=.45, rain=1, sun=.3,
         warm=(-.15, .3), gain=(.94, 1.03), dis=.5),
    Shot('s26', 'K26', B(39), V((0, .5, .47, 1.0), (1, .5, .5, 1.07)), par=0, parv=12, hand=.3, fx=('plinks',),
         warm=(-.1, .3), dis=.4),

    # ---- chorus again: the same moment, from where he stands
    Shot('s27', 'K27', B(41), V((0, .5, .5, 1.0), (1, .5, .48, 1.1)), par=10, hand=.3, rain=.7, sun=1, rnear=.3, fx=('flood',)),
    Shot('s28', 'K28', B(42, 3), V((0, .5, .5, 1.02), (1, .5, .5, 1.07)), par=8, hand=.3, rain=.3, sun=1, rnear=.15),
    Shot('s29', 'K29', B(43, 3), V((0, .5, .5, 1.0), (1, .5, .5, 1.07)), par=-10, hand=.35, rain=.5, sun=1, rnear=.25),
    Shot('s30', 'K30', B(45), V((0, .5, .5, 1.07), (1, .5, .5, 1.02)), par=14, hand=.35, rain=.7, sun=1, rnear=.4, fx=('steam',)),
    Shot('s31', 'K31', B(46), V((0, .5, .5, 1.0), (1, .5, .49, 1.06)), par=14, hand=.3, rain=1, sun=1),
    Shot('s32', 'K32', B(47), V((0, .5, .47, 1.12), (1, .5, .46, 1.0)), par=16, hand=.25, rain=1, sun=1, fx=('twinkle',)),

    # ---- outro: the bed without the voice, one last chord at bar 53 left to ring
    Shot('s33', 'K33', B(49, 3), V((0, .5, .5, 1.1), (1, .5, .49, 1.0)), par=12, hand=.2, rain=.22, sun=1, fx=('twinkle',), dis=1.8),
    Shot('s34', 'K34', B(51, 3), V((0, .5, .5, 1.0), (1, .5, .49, 1.06)), par=10, hand=.12, dis=2.0, fx=('twinkle',),
         fade_out=TOTAL - B(53) - 1.2, blur=(0, 14), extra={'blur_start': B(53) - .4, 'end': TOTAL - 1.2}),
]
for _i, _s in enumerate(SHOTS):
    _s.idx = _i
    _s.t1 = SHOTS[_i + 1].t0 if _i + 1 < len(SHOTS) else TOTAL

# per-shot effect geometry, in keyframe pixels (1088 x 1920); filled in after looking at the stills
FXGEO = {
    'K07': {'steam': (713, 1317, 220, 440, 38)},
    'K21': {'steam': (602, 1110, 240, 440, 42)},
    'K30': {'steam': (512, 803, 280, 470, 40)},
    'K10': {'rings': (0, 740, 1088, 1310, 10, (1.1, -.5))},      # the rings thin out and stop: the umbrella has arrived
    'K17': {'plinks': (60, 60, 1028, 1860, 7, (1, 1))},
    'K26': {'plinks': (40, 40, 1048, 1500, 8, (1, .7))},
}
