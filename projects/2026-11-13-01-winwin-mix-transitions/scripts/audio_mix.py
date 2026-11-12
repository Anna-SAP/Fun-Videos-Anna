"""Audio re-mix for the transitions. Usage: python3 audio_mix.py <src.wav> <out.wav>

Each song keeps its own sync with its picture; only the joins are rebuilt:
  open  : 60 ms fade-in + low-pass opening 300 Hz -> 18 kHz over 0.55 s (mirrors the bars opening)
  T1    : reverb throw of the last hit before the stop (5.48-5.70 s) + a soft right-to-left whoosh
  T2    : echo-out of song 1's last eighth (ping-pong, 0.29 s = 1/8 at 103.4 BPM) while song 2
          comes in high-passed and gets its bass back on its first downbeat (10.565 s)
  T3    : 0.833 s equal-power crossfade song 2 -> song 3 (relative keys F#m / A), song 2 closes
          through a low-pass sweep and leaves a reverb wash (the "fog")
  end   : 1.45 s fade with a closing low-pass (mirrors the bars closing)
  levels: A -1.0 dB, B -2.0 dB, C +1.2 dB  (-9.4/-8.3/-12.7 LUFS -> about -10.4/-10.3/-11.5)
"""
import sys
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from timeline import FPS, B_START, C_START, OVERLAP, N_OUT, C_LAST_OUT

src, dst = sys.argv[1], sys.argv[2]
x, sr = sf.read(src, dtype='float64')
assert x.ndim == 2 and x.shape[1] == 2


def sec(t):
    return int(round(t * sr))


def db(g):
    return 10 ** (g / 20)


def fade(n, kind='in', shape='sine'):
    u = np.linspace(0, 1, n, endpoint=True)
    if shape == 'sine':
        g = np.sin(u * np.pi / 2)
    else:
        g = 0.5 - 0.5 * np.cos(u * np.pi)
    return g if kind == 'in' else g[::-1]


def tv_filter(sig, fc_of_t, btype, order=2, block=128):
    """Time-varying Butterworth filter, coefficients updated per block, state carried over."""
    out = np.zeros_like(sig)
    zi = None
    for b0 in range(0, len(sig), block):
        b1 = min(b0 + block, len(sig))
        fc = float(np.clip(fc_of_t((b0 + b1) / 2 / sr), 20, sr * 0.45))
        sos = butter(order, fc, btype=btype, fs=sr, output='sos')
        if zi is None:
            zi = np.zeros((sos.shape[0], 2, sig.shape[1]))
        out[b0:b1], zi = sosfilt(sos, sig[b0:b1], axis=0, zi=zi)
    return out


def static_filter(sig, fc, btype, order=2):
    sos = butter(order, fc, btype=btype, fs=sr, output='sos')
    return sosfilt(sos, sig, axis=0)


def exp_sweep(f0, f1, t0, t1):
    def f(t):
        u = np.clip((t - t0) / (t1 - t0), 0, 1)
        return f0 * (f1 / f0) ** u
    return f


def make_ir(rt60, length, lp, hp, seed):
    n = sec(length)
    t = np.arange(n) / sr
    rng = np.random.default_rng(seed)
    ir = rng.standard_normal((n, 2)) * np.exp(-6.9 * t / rt60)[:, None]
    ir *= np.minimum(1, t / 0.012)[:, None]
    ir = static_filter(ir, lp, 'low')
    ir = static_filter(ir, hp, 'high')
    ir /= np.sqrt((ir ** 2).sum(0, keepdims=True))
    return ir


def convolve(sig, ir):
    return np.stack([fftconvolve(sig[:, c], ir[:, c]) for c in range(2)], axis=1)


def add_at(buf, sig, t0):
    i0 = sec(t0)
    if i0 < 0:
        sig = sig[-i0:]
        i0 = 0
    n = min(len(sig), len(buf) - i0)
    if n > 0:
        buf[i0:i0 + n] += sig[:n]


def blend_region(dry, wet, a, b, xf=0.03):
    """Use `wet` inside [a,b] (seconds, relative to dry), crossfading xf seconds at both edges."""
    m = np.zeros(len(dry))
    ia, ib, nx = sec(a), sec(b), sec(xf)
    m[max(ia, 0):ib] = 1
    if ia - nx >= 0:
        m[ia - nx:ia] = fade(nx, 'in', 'cos')
    if ib + nx <= len(m):
        m[ib:ib + nx] = fade(nx, 'out', 'cos')
    return dry * (1 - m[:, None]) + wet * m[:, None]


tA = B_START / FPS            # 10.2333  end of song 1
tB = C_START / FPS            # 30.0333  end of song 2
shift = OVERLAP / FPS         # 0.8333   song 3 placed this much earlier
n_out = sec(N_OUT / FPS)

A = x[:sec(tA)].copy() * db(-1.0)
B = x[sec(tA):sec(tB)].copy() * db(-2.0)
C = x[sec(tB):].copy() * db(+1.2)

out = np.zeros((n_out, 2))

# ---------------- opening: fade-in + low-pass opening -----------------------------------------
lp = tv_filter(A[:sec(1.0)], exp_sweep(300, 18000, 0.0, 0.55), 'low')
A[:sec(1.0)] = blend_region(A[:sec(1.0)], lp, 0.0, 0.62, xf=0.08)
A[:sec(0.06)] *= fade(sec(0.06), 'in', 'cos')[:, None]

# ---------------- T1: reverb throw + whoosh under the whip-push --------------------------------
chunk = A[sec(5.48):sec(5.70)].copy()
nf = sec(0.012)
chunk[:nf] *= fade(nf, 'in')[:, None]
chunk[-nf:] *= fade(nf, 'out')[:, None]
wet = convolve(chunk, make_ir(1.1, 1.6, 6000, 220, seed=1)) * db(-11)
add_at(A, wet[:len(A) - sec(5.48)], 5.48)

# whoosh: noise band sweeping up into the cut and back down, panned right -> left
w0, w1, wpk = 5.47, 5.86, 5.655
nw = sec(w1 - w0)
tw = np.arange(nw) / sr + w0
rng = np.random.default_rng(7)
noise = rng.standard_normal((nw, 2))
fc_up = lambda t: 450 * (3200 / 450) ** np.clip((t - w0) / (wpk - w0), 0, 1) if t < wpk else \
    3200 * (1400 / 3200) ** np.clip((t - wpk) / (w1 - wpk), 0, 1)
bp = tv_filter(noise, lambda t: fc_up(t + w0) * 1.5, 'low', order=2)
bp = tv_filter(bp, lambda t: fc_up(t + w0) / 1.5, 'high', order=2)
env = np.where(tw < wpk, ((tw - w0) / (wpk - w0)) ** 2.2, np.exp(-(tw - wpk) / 0.06))
pan = np.clip((tw - w0) / (w1 - w0), 0, 1)               # 0 = right, 1 = left
gl, gr = np.sin(pan * np.pi / 2), np.cos(pan * np.pi / 2)
bp = bp / (np.sqrt((bp ** 2).mean()) + 1e-12)
whoosh = np.stack([bp[:, 0] * env * gl, bp[:, 1] * env * gr], axis=1) * db(-27)
add_at(A, whoosh, w0)

# ---------------- T2: echo-out of song 1 -------------------------------------------------------
d8 = 60 / 103.4 / 2                       # eighth note of song 1
src_e = A[sec(tA - d8):sec(tA)].copy()    # last eighth before the splice
nf = sec(0.006)
src_e[:nf] *= fade(nf, 'in')[:, None]
src_e[-nf:] *= fade(nf, 'out')[:, None]
A[-sec(0.008):] *= fade(sec(0.008), 'out')[:, None]   # dry signal ends cleanly on the splice

echo = np.zeros((sec(2.2), 2))
for n in range(1, 6):
    g = 0.62 * 0.55 ** (n - 1)
    e = static_filter(src_e, 260 * 1.45 ** (n - 1), 'high')
    e = static_filter(e, 7500 / 1.35 ** (n - 1), 'low')
    p = 0.78 if n % 2 else 0.22                         # ping-pong: odd repeats left, even right
    e = np.stack([e[:, 0] * np.sqrt(p) * 1.25, e[:, 1] * np.sqrt(1 - p) * 1.25], axis=1)
    add_at(echo, e * g, (n - 1) * d8)                  # repeat 1 lands exactly on the splice
echo[:sec(0.004)] *= fade(sec(0.004), 'in')[:, None]

# song 2 enters high-passed, gets its bass back on its first downbeat
tdb = 317 / FPS - tA                                    # 0.331 s after the splice
hp = tv_filter(B[:sec(1.0)], exp_sweep(480, 22, 0.0, tdb), 'high')
B[:sec(1.0)] = blend_region(B[:sec(1.0)], hp, 0.0, tdb + 0.01, xf=0.03)
ramp = np.ones(len(B))
ramp[:sec(tdb)] = np.linspace(db(-1.5), 1.0, sec(tdb))
B *= ramp[:, None]

# ---------------- T3: song 2 -> song 3 ---------------------------------------------------------
ov = sec(shift)
tail0 = len(B) - ov                                     # start of the overlap inside B
wash_src = B[len(B) - sec(1.13):].copy()                # last 1.13 s of song 2 feeds the fog
wash_src[:sec(0.05)] *= fade(sec(0.05), 'in')[:, None]
wash_src[-sec(0.01):] *= fade(sec(0.01), 'out')[:, None]
wash = convolve(static_filter(wash_src, 5000, 'low'), make_ir(2.1, 3.2, 4200, 180, seed=3)) * db(-13)

lpB = tv_filter(B[tail0 - sec(0.1):], exp_sweep(18000, 1500, 0.1, 0.1 + shift), 'low')
B[tail0 - sec(0.1):] = blend_region(B[tail0 - sec(0.1):], lpB, 0.1, 0.1 + shift + 0.01, xf=0.05)
B[tail0:] *= fade(ov, 'out', 'sine')[:, None]
C[:ov] *= fade(ov, 'in', 'sine')[:, None]

# ---------------- assemble ---------------------------------------------------------------------
add_at(out, A, 0.0)
add_at(out, echo, tA)
add_at(out, B, tA)
add_at(out, wash, tB - 1.13)
add_at(out, C, tB - shift)

# ---------------- ending: fade + closing low-pass ----------------------------------------------
t_end = (C_LAST_OUT + 1) / FPS                          # 68.867 s, last picture frame
f0 = t_end - 1.45
seg = out[sec(f0) - sec(0.1):].copy()
lpE = tv_filter(seg, exp_sweep(18000, 380, 0.1, 0.1 + 1.45), 'low')
out[sec(f0) - sec(0.1):] = blend_region(seg, lpE, 0.1, 10.0, xf=0.08)
g = np.ones(len(out))
nfade = sec(1.45)
g[sec(f0):sec(f0) + nfade] = fade(nfade, 'out', 'sine') ** 1.6
g[sec(f0) + nfade:] = 0
out *= g[:, None]

sf.write(dst, out.astype(np.float32), sr, subtype='FLOAT')
print('wrote', dst, out.shape, 'peak dBFS', 20 * np.log10(np.abs(out).max()))
