#!/usr/bin/env python3
"""Static candidates: sustained wideband noise. Hi-hats and snares decay within ~100 ms, so the floor of the
1-10.5 kHz energy under a 120 ms minimum filter stays low between hits; radio static holds it up. Peaks of that
floor above its local 8 s median, with high spectral flatness, are candidates. Writes work/audio/static_cand.json
and a tiled zoom image work/qc/static_zoom.png (each tile 4 s around a candidate, 0-11 kHz).
"""
import json
import numpy as np
from PIL import Image, ImageDraw
from scipy.io import wavfile
from scipy.signal import stft, find_peaks
from scipy.ndimage import minimum_filter1d, median_filter, uniform_filter1d

sr, x = wavfile.read('work/audio/inst22k.wav')
x = x.astype(np.float32) / 32768
_, xm = wavfile.read('work/audio/mono22k.wav')
xm = xm.astype(np.float32) / 32768
HOP = 220
fps = sr / HOP
def spec(y):
    f, t, Z = stft(y, sr, nperseg=1024, noverlap=1024 - HOP, boundary=None, padded=False)
    return f, np.abs(Z) ** 2 + 1e-12
f, P = spec(x)
_, Pm = spec(xm)
b = (f >= 1000) & (f < 10500)
wide = 10 * np.log10(P[b].sum(0))
flat = uniform_filter1d(np.exp(np.log(P[b]).mean(0)) / P[b].mean(0), 12)
floor = minimum_filter1d(wide, 12)
floor = uniform_filter1d(floor, 5)
base = median_filter(floor, size=int(8 * fps))
rel = floor - base
pk, pr = find_peaks(rel, height=4.0, distance=int(0.6 * fps), prominence=4.0)
cands = []
for p in pk:
    # extent where rel stays above half the peak
    h = rel[p] / 2
    a = p
    while a > 0 and rel[a - 1] > h: a -= 1
    e = p
    while e < len(rel) - 1 and rel[e + 1] > h: e += 1
    cands.append({'t': round(p / fps, 2), 't0': round(a / fps, 2), 't1': round(e / fps, 2),
                  'rise_db': round(float(rel[p]), 1), 'flat': round(float(flat[p]), 2)})
json.dump(cands, open('work/audio/static_cand.json', 'w'), indent=1)
for c in cands:
    print(c)
# zoom tiles from the MIX spectrogram
S = 10 * np.log10(Pm[f < 11000])
S = np.clip((S - (S.max() - 75)) / 75, 0, 1)[::-1]
tiles = []
for c in cands:
    a = int(max(0, c['t'] - 2) * fps); e = a + int(4 * fps)
    im = Image.fromarray((255 * S[:, a:e]).astype(np.uint8)).resize((400, 200)).convert('RGB')
    dr = ImageDraw.Draw(im)
    for tt, col in ((c['t0'], (0, 255, 0)), (c['t1'], (255, 0, 0))):
        xx = (tt * fps - a) / (e - a) * 400
        dr.line([xx, 0, xx, 200], fill=col)
    dr.rectangle([0, 0, 170, 14], fill=(0, 0, 0))
    dr.text((2, 1), f"{c['t']}s +{c['rise_db']}dB fl{c['flat']}", fill=(255, 255, 0))
    tiles.append(im)
cols = 5
rows = int(np.ceil(len(tiles) / cols))
sheet = Image.new('RGB', (cols * 404, rows * 204), (40, 40, 40))
for i, im in enumerate(tiles):
    sheet.paste(im, ((i % cols) * 404, (i // cols) * 204))
sheet.save('work/qc/static_zoom.png')
print(len(cands), 'candidates')
