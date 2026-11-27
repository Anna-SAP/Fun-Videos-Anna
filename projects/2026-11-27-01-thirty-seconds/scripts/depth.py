#!/usr/bin/env python3
"""Estimate a depth map for a still with Depth Anything V2 small (ONNX, CPU).

  depth.py MODEL.onnx PYLIBS IN.png OUT.png      16-bit PNG, 0 = far, 65535 = near
"""
import sys

model, pylibs, src, dst = sys.argv[1:5]
sys.path.insert(0, pylibs)
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import onnxruntime as ort  # noqa: E402

sess = ort.InferenceSession(model, providers=['CPUExecutionProvider'])
name = sess.get_inputs()[0].name
im = cv2.imdecode(np.fromfile(src, np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1].astype(np.float32) / 255
h, w = im.shape[:2]
# ViT patch size 14; 518 on the short side
scale = 518 / min(h, w)
nw, nh = round(w * scale / 14) * 14, round(h * scale / 14) * 14
x = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_CUBIC)
x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
x = x.transpose(2, 0, 1)[None].astype(np.float32)
d = sess.run(None, {name: x})[0].squeeze()
d = cv2.resize(d, (w, h), interpolation=cv2.INTER_CUBIC)
lo, hi = np.percentile(d, [1, 99])
d = np.clip((d - lo) / (hi - lo + 1e-6), 0, 1)
ok, buf = cv2.imencode('.png', (d * 65535).astype(np.uint16))
buf.tofile(dst)
print('depth', dst, d.shape, 'near mean', round(float(d.mean()), 3))
