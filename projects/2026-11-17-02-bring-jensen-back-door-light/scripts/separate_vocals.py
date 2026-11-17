#!/usr/bin/env python3
"""Pull the lead vocal out of the mix with the UVR MDX-Net model Kim_Vocal_2 (ONNX, CPU).

  separate_vocals.py STEREO44K.wav MODEL.onnx OUT_VOCALS.wav [OUT_INST.wav]

MDX-Net works on a complex STFT (n_fft 7680, hop 1024, 3072 bins, 256 frames per chunk); the network maps
the mixture spectrum (real/imag of both channels as 4 planes) to the vocal spectrum. Chunks overlap by half
and are cross-faded. The separated vocal is only for listening-by-measurement (reading word onsets and
consonants); it never goes into the film.
"""
import sys

import numpy as np
import onnxruntime as ort
from scipy.io import wavfile
from scipy.signal import istft, stft

src, model, out_v = sys.argv[1:4]
out_i = sys.argv[4] if len(sys.argv) > 4 else None
sr, x = wavfile.read(src)
x = x.astype(np.float32) / 32768.0
assert sr == 44100 and x.ndim == 2
N_FFT, HOP, DIM_F, DIM_T = 7680, 1024, 3072, 256
WS = N_FFT / 2.0
sess = ort.InferenceSession(model, providers=['CPUExecutionProvider'])

seg = HOP * (DIM_T - 1)          # samples covered by one chunk
pad = N_FFT // 2
step = seg // 2
n = x.shape[0]
xp = np.pad(x, ((pad, pad + seg), (0, 0)))
win = np.hanning(seg).astype(np.float32)
win = np.maximum(win, 1e-3)
acc = np.zeros_like(xp)
wsum = np.zeros(xp.shape[0], np.float32)

for start in range(0, n + pad, step):
    chunk = xp[start:start + seg + N_FFT]
    if chunk.shape[0] < seg + N_FFT:
        chunk = np.pad(chunk, ((0, seg + N_FFT - chunk.shape[0]), (0, 0)))
    specs = []
    for c in range(2):
        _, _, Z = stft(chunk[:, c], nperseg=N_FFT, noverlap=N_FFT - HOP, window='hann', boundary=None, padded=False)
        specs.append(Z[:DIM_F, :DIM_T] * WS)   # scipy scales by 1/sum(window); the model expects torch.stft scale
    S = np.stack([specs[0].real, specs[0].imag, specs[1].real, specs[1].imag])[None].astype(np.float32)
    if S.shape[-1] < DIM_T:
        S = np.pad(S, ((0, 0), (0, 0), (0, 0), (0, DIM_T - S.shape[-1])))
    Y = sess.run(None, {'input': S})[0][0]
    outc = []
    for c in range(2):
        Zc = np.zeros((N_FFT // 2 + 1, DIM_T), np.complex64)
        Zc[:DIM_F] = (Y[2 * c] + 1j * Y[2 * c + 1]) / WS
        _, y = istft(Zc, nperseg=N_FFT, noverlap=N_FFT - HOP, window='hann', boundary=False)
        outc.append(y)
    y = np.stack(outc, 1)
    L = min(seg, y.shape[0] - pad)
    acc[start + pad:start + pad + L] += y[pad:pad + L] * win[:L, None]
    wsum[start + pad:start + pad + L] += win[:L]

voc = acc / np.maximum(wsum, 1e-6)[:, None]
voc = voc[pad:pad + n] * 1.009
wavfile.write(out_v, sr, np.clip(voc * 32767, -32768, 32767).astype(np.int16))
if out_i:
    wavfile.write(out_i, sr, np.clip((x - voc) * 32767, -32768, 32767).astype(np.int16))
print('vocal rms dB', round(20 * np.log10(np.sqrt((voc ** 2).mean()) + 1e-9), 1),
      'mix rms dB', round(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9), 1))
