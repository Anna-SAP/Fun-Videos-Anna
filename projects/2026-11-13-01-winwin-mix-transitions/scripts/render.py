"""Frame-accurate re-render of winwin_V2_mixure_clip.mp4 with designed transitions.

Usage: python3 render.py <src.mp4> <mix.wav> <out.mp4> [--frames a:b] [--preview]

Design language: one black cinematic frame whose letterbox "breathes" with the music
(opens like an eye at the start, bursts open on song 1's drop, tightens into song 2's
ultra-wide frame, settles to 2.35:1 for song 3, closes like an eye at the end), and three
transitions carried by motion, echo and atmosphere:
  T1  5.6 s  whip-push (horizontal motion blur, light bloom) from the day shot into the garage,
             frame stays 2.35:1 through the whip, then opens to full 16:9 + impact zoom on the drop
  T2 10.2 s  echo-out: the dancers leave ghost trails (RGB-split, red) that dissolve into the
             black void of song 2's first shot while its white ramp lights up on the downbeat
  T3 30.0 s  fog-into-smoke: luminance-keyed dissolve (C's shadows emerge first), dusk grade
             on the pink fog, haze lift on the smoke, one continuous camera push across both
"""
import subprocess
import sys
import numpy as np
import cv2

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from timeline import (FPS, W, H, N_SRC, A2_START, B_START, C_START, OVERLAP, DISS_OUT0,
                      C_LAST_OUT, N_OUT, BAR_A1, BAR_B, BAR_C, LOGO_BOX)

args = sys.argv[1:]
SRC, MIX, OUT = args[0], args[1], args[2]
RANGE = None
PREVIEW = '--preview' in args
if '--frames' in args:
    a, b = args[args.index('--frames') + 1].split(':')
    RANGE = (int(a), int(b))

FRAME_BYTES = W * H * 3


# ---------------------------------------------------------------- easing
def clamp01(x):
    return float(min(1.0, max(0.0, x)))


def smoothstep(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def smootherstep(x):
    x = clamp01(x)
    return x * x * x * (x * (6 * x - 15) + 10)


def ease_out_cubic(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_out_quart(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 4


def ease_in_quad(x):
    x = clamp01(x)
    return x * x


def ease_out_quad(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 2


def ease_in_out_cubic(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------- source reader (sequential + cache)
class Reader:
    def __init__(self, path, start=0):
        cmd = ['ffmpeg', '-v', 'error', '-i', path, '-an',
               '-vf', 'scale=in_color_matrix=bt709:in_range=limited:flags=accurate_rnd+full_chroma_int+bicubic,format=rgb24',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=FRAME_BYTES * 2)
        self.next = 0
        self.cache = {}

    def get(self, i):
        i = min(max(i, 0), N_SRC - 1)
        while self.next <= i:
            buf = self.p.stdout.read(FRAME_BYTES)
            if len(buf) < FRAME_BYTES:
                raise EOFError(f'source ended at frame {self.next}')
            if self.next >= i - 64:
                self.cache[self.next] = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            self.next += 1
        for k in [k for k in self.cache if k < i - 64]:
            del self.cache[k]
        return self.cache[i]


def segment_of(s):
    if s < A2_START:
        return 'A1'
    if s < B_START:
        return 'A2'
    if s < C_START:
        return 'B'
    return 'C'


def native(reader, s):
    """Source frame as float32 RGB [0,1]; B's white bars repainted black."""
    f = reader.get(s).astype(np.float32) * (1 / 255)
    if segment_of(s) == 'B':
        f[:BAR_B] = 0
        f[H - BAR_B:] = 0
    return f


# ---------------------------------------------------------------- image ops
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def luma(img):
    return img @ LUMA


def saturate(img, s):
    y = luma(img)[..., None]
    return y + (img - y) * s


def zoom(img, z, cy=H / 2 - 0.5, cx=W / 2 - 0.5):
    if abs(z - 1) < 1e-4:
        return img
    M = np.array([[z, 0, cx * (1 - z)], [0, z, cy * (1 - z)]], np.float32)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def hblur(img, L):
    L = int(round(L))
    if L < 2:
        return img
    return cv2.blur(img, (L, 1), borderType=cv2.BORDER_REFLECT)


def gblur(img, sigma):
    if sigma < 0.3:
        return img
    return cv2.GaussianBlur(img, (0, 0), sigma)


def shift_x(img, dx):
    dx = int(round(dx))
    if dx == 0:
        return img
    return np.roll(img, dx, axis=1)


def screen(a, b):
    return 1 - (1 - a) * (1 - b)


def to_lin(img):
    return np.power(np.clip(img, 0, 1), 2.2)


def from_lin(img):
    return np.power(np.clip(img, 0, 1), 1 / 2.2)


def draw_bars(img, h):
    h = max(0.0, min(H / 2, h))
    hi = int(np.floor(h))
    fr = h - hi
    if hi > 0:
        img[:hi] = 0
        img[H - hi:] = 0
    if fr > 1e-3 and hi < H // 2:
        img[hi] *= (1 - fr)
        img[H - hi - 1] *= (1 - fr)
    return img


# ---------------------------------------------------------------- per-frame parameter curves
def bar_h(o):
    if o < 18:                                    # eye opens onto the first downbeat
        return lerp(H / 2, BAR_A1, ease_out_quart(o / 17))
    if o < 185:
        return BAR_A1
    if o < 192:                                   # frame bursts open on the drop (6.17 s)
        return lerp(BAR_A1, 0, ease_out_cubic((o - 185) / 6))
    if o < 300:
        return 0
    if o <= 317:                                  # tightens into song 2's ultra-wide frame
        return lerp(0, BAR_B, smootherstep((o - 300) / 17))
    if o < DISS_OUT0:
        return BAR_B
    if o <= DISS_OUT0 + OVERLAP - 1:              # settles to 2.35:1 through the fog
        return lerp(BAR_B, BAR_C, smootherstep((o - DISS_OUT0 + 1) / (OVERLAP + 1)))
    if o < C_LAST_OUT - 25:
        return BAR_C
    if o <= C_LAST_OUT:                           # eye closes
        return lerp(BAR_C, H / 2, ease_in_out_cubic((o - (C_LAST_OUT - 26)) / 26))
    return H / 2


def zoom_for(o):
    z = 1.0
    if o < 45:
        z *= lerp(1.05, 1.0, ease_out_cubic(o / 44))
    if 185 <= o < 197:                            # impact zoom on the drop
        z *= lerp(1.06, 1.0, ease_out_cubic((o - 185) / 11))
    return z


def exposure_for(o):
    e = 1.0
    if o < 12:
        e *= ease_out_quad((o + 1) / 12)
    if o > C_LAST_OUT - 20:
        e *= 1 - smoothstep((o - (C_LAST_OUT - 20)) / 20)
    return e


# ---------------------------------------------------------------- transitions
# T1 whip-push: output frames 167..172; outgoing holds src 167 (day shot), incoming src 170..172.
T1_FRAMES = list(range(167, 173))
T1_X = [1920 * ease_in_out_cubic((k + 1) / 7) for k in range(6)]
_X = [0.0] + T1_X + [1920.0]
T1_V = [(_X[k + 2] - _X[k]) / 2 for k in range(6)]          # px per frame, central difference
T1_BLOOM = {167: 1.0, 168: 1.05, 169: 1.13, 170: 1.13, 171: 1.05, 172: 1.0}


def t1_frame(reader, o):
    k = o - 167
    out_src = native(reader, 167)
    in_src = native(reader, max(A2_START, o) if k >= 3 else A2_START)
    X = int(round(T1_X[k]))
    canvas = np.empty_like(out_src)
    canvas[:, :W - X] = out_src[:, X:]
    canvas[:, W - X:] = in_src[:, :X]
    canvas = hblur(canvas, 0.55 * T1_V[k])
    return canvas * T1_BLOOM[o]


# T2 echo-out: trails build on src 294..306, then the ghost dissolves over B 307..318.
class EchoState:
    def __init__(self):
        self.E = None
        self.G = None


ECHO = EchoState()
GHOST_TINT = np.array([1.0, 0.42, 0.52], np.float32)


def t2_pre(img, o):
    """o in 294..306: accumulate trails; from 300 show them and cool the red down."""
    if ECHO.E is None:
        ECHO.E = img.copy()
    else:
        ECHO.E = 0.5 * img + 0.5 * ECHO.E
    if o < 300:
        return img
    m = 0.7 * smoothstep((o - 299) / 7)
    q = smoothstep((o - 299) / 7)
    disp = img * (1 - m) + np.maximum(img, ECHO.E) * m
    disp = saturate(disp, 1 - 0.3 * q) * (1 - 0.15 * q)
    return disp


def t2_post(img, o):
    """o in 307..318: ghost of the last dance frame decays over B's black void."""
    k = o - B_START
    if ECHO.G is None:
        g = ECHO.E * 0.95
        # RGB split echo
        g = np.stack([shift_x(g[..., 0], 10), g[..., 1], shift_x(g[..., 2], -10)], axis=-1)
        ECHO.G = g
    else:
        ECHO.G = gblur(zoom(ECHO.G, 1.018), 1.2 + 0.5 * k) * 0.80
    pulse = 0.18 * np.exp(-0.5 * ((o - 316) / 1.2) ** 2)          # small kick on song 2's downbeat
    alpha = 0.85 * np.exp(-k / 3.8) + pulse
    bexp = lerp(0.35, 1.0, ease_out_cubic((k + 1) / 10))
    return screen(np.clip(img * bexp, 0, 1), np.clip(ECHO.G * GHOST_TINT * alpha, 0, 1))


# T3 fog-into-smoke
def b_tail_grade(img, o):
    q = smoothstep((o - 846) / 54)
    if q <= 0:
        return img
    img = saturate(img, 1 - 0.3 * q) * (1 - 0.12 * q)
    return img * np.array([1 - 0.05 * q, 1 - 0.01 * q, 1 + 0.04 * q], np.float32)


def b_tail_zoom(o):
    return 1 + 0.03 * ease_in_quad((o - 851) / 49) if o >= 851 else 1.0


def c_first_shot_zoom(o):
    # C's first shot runs to src 1050 (out 1025); keep pushing in with the speed B had
    if DISS_OUT0 <= o <= 1025:
        return 1 + 0.07 * ease_out_quad((o - DISS_OUT0) / (1025 - DISS_OUT0))
    return 1.0


FOG = {'col': None}


def c_haze(img, o):
    f = 0.28 * (1 - smoothstep((o - DISS_OUT0) / 35))
    if f <= 1e-3 or FOG['col'] is None:
        return img
    return img * (1 - f) + FOG['col'] * f


def luma_key_dissolve(b, c, p):
    lc = luma(c)
    small = cv2.resize(lc, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 3)
    lc = cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)
    lc = np.clip((lc - 0.02) / 0.45, 0, 1)                      # C is dark: stretch its range
    a = 0.4 * lc
    w = np.clip((p - a) / 0.6, 0, 1)
    w = (w * w * (3 - 2 * w))[..., None]
    return from_lin(to_lin(b) * (1 - w) + to_lin(c) * w)


def logo_layer(reader, s):
    r0, r1, c0, c1 = LOGO_BOX
    return reader.get(s)[r0:r1, c0:c1].astype(np.float32) * (1 / 255)


# ---------------------------------------------------------------- frame builder
def build(reader, o):
    if o > C_LAST_OUT:
        return np.zeros((H, W, 3), np.float32)

    logo_alpha = 0.0
    logo_src = None

    if o < DISS_OUT0:
        s = o
        seg = segment_of(s)
        if o in T1_FRAMES:
            img = t1_frame(reader, o)
        else:
            img = native(reader, s)
            if 294 <= o <= 306:
                img = t2_pre(img, o)
            elif B_START <= o <= 318:
                img = t2_post(img, o)
            if seg == 'B':
                img = zoom(b_tail_grade(img, o), b_tail_zoom(o)) if o >= 846 else img
            z = zoom_for(o)
            if seg in ('A1', 'A2') and abs(z - 1) > 1e-4:
                img = zoom(img, z)
    elif o < DISS_OUT0 + OVERLAP:
        sb, sc = o, o + OVERLAP
        b = native(reader, sb)
        # the frame opens from B's 228 px bars to C's 129 px: extend the fog into B's bar area
        # (mirror + soften) so no dark band shows between the two picture edges
        pic = b[BAR_B:H - BAR_B]
        b = cv2.copyMakeBorder(pic, BAR_B, BAR_B, 0, 0, cv2.BORDER_REFLECT)
        soft = gblur(b, 18)
        b[:BAR_B + 12] = soft[:BAR_B + 12]
        b[H - BAR_B - 12:] = soft[H - BAR_B - 12:]
        b = zoom(b_tail_grade(b, o), b_tail_zoom(o))
        if FOG['col'] is None:
            FOG['col'] = (b.reshape(-1, 3)[BAR_B * W:(H - BAR_B) * W].mean(0) * 0.72).astype(np.float32)
        c = c_haze(zoom(native(reader, sc), c_first_shot_zoom(o)), o)
        p = (o - DISS_OUT0 + 1) / (OVERLAP + 1)
        img = luma_key_dissolve(b, c, p)
        logo_alpha, logo_src = smoothstep(p), sc
    else:
        s = o + OVERLAP
        img = native(reader, s)
        z = c_first_shot_zoom(o)
        if o >= C_LAST_OUT - 39:
            z *= 1 + 0.04 * ease_in_quad((o - (C_LAST_OUT - 39)) / 39)
        img = c_haze(zoom(img, z), o)
        logo_alpha, logo_src = 1.0, s

    img = img * exposure_for(o)
    img = draw_bars(np.ascontiguousarray(img, np.float32), bar_h(o))
    if logo_src is not None and logo_alpha > 0:
        r0, r1, c0, c1 = LOGO_BOX
        lg = logo_layer(reader, logo_src) * logo_alpha * exposure_for(o)
        img[r0:r1, c0:c1] = np.maximum(img[r0:r1, c0:c1], lg)
    return img


def main():
    reader = Reader(SRC)
    a, b = RANGE if RANGE else (0, N_OUT)
    # the echo state needs its warm-up frames even when previewing a range
    a_eff = min(a, 294) if a <= 318 and b > 294 else a
    if PREVIEW:
        enc = None
        import os
        os.makedirs(OUT, exist_ok=True)
    else:
        enc_cmd = ['ffmpeg', '-v', 'error', '-y',
                   '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                   '-i', MIX,
                   '-map', '0:v', '-map', '1:a',
                   '-vf', 'scale=out_color_matrix=bt709:out_range=limited:flags=accurate_rnd+full_chroma_int,format=yuv420p',
                   '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-profile:v', 'high', '-tune', 'film',
                   '-x264-params', 'keyint=60:min-keyint=1:aq-mode=3:aq-strength=0.9',
                   '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
                   '-af', 'aresample=44100',              # mix is already true-peak limited (tp_limit.py)
                   '-c:a', 'aac', '-b:a', '256k',
                   '-shortest', '-movflags', '+faststart', OUT]
        if RANGE:
            enc_cmd[enc_cmd.index('-i', 12):enc_cmd.index('-i', 12) + 2] = ['-ss', f'{a / FPS:.6f}', '-i', MIX]
        enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)
    for o in range(a_eff, b):
        img = build(reader, o)
        if o < a:
            continue
        u8 = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
        if PREVIEW:
            cv2.imwrite(f'{OUT}/f{o:04d}.jpg', cv2.cvtColor(u8, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
        else:
            enc.stdin.write(u8.tobytes())
        if o % 150 == 0:
            print('frame', o, flush=True)
    if enc:
        enc.stdin.close()
        enc.wait()
        print('encoder exit', enc.returncode)
    reader.p.kill()


if __name__ == '__main__':
    main()
