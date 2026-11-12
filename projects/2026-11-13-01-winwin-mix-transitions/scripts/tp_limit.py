"""True-peak lookahead limiter. Usage: python3 tp_limit.py in.wav out.wav [ceiling_dBTP]"""
import sys, numpy as np, soundfile as sf
from scipy.signal import resample_poly
from scipy.ndimage import minimum_filter1d, uniform_filter1d
x, sr = sf.read(sys.argv[1], dtype='float64')
ceil = 10 ** (float(sys.argv[3] if len(sys.argv) > 3 else -1.5) / 20)
up = resample_poly(x, 4, 1, axis=0)
tp = np.abs(up).max(axis=1)[:len(x) * 4].reshape(len(x), 4).max(axis=1)
g = np.minimum(1.0, ceil / np.maximum(tp, 1e-12))
L = int(0.0025 * sr)                                   # 2.5 ms lookahead / attack
g = minimum_filter1d(g, size=2 * L + 1)
rel = np.exp(-1 / (0.09 * sr))                         # 90 ms release
out = np.empty_like(g); cur = 1.0
for i, v in enumerate(g):
    cur = v if v < cur else min(v, 1 - (1 - cur) * rel)
    out[i] = cur
g = uniform_filter1d(out, size=L)
y = x * g[:, None]
sf.write(sys.argv[2], y.astype(np.float32), sr, subtype='FLOAT')
upy = resample_poly(y, 4, 1, axis=0)
print('gain reduction max %.2f dB, time limited %.2f%%, out true peak %.2f dBTP' % (
    -20 * np.log10(g.min()), 100 * (g < 0.999).mean(), 20 * np.log10(np.abs(upy).max())))
