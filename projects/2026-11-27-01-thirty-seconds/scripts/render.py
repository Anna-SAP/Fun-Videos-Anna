#!/usr/bin/env python3
"""Render 三十秒. One frame = plate (push + depth parallax + kick punch) -> grade -> haze -> particles -> shot
effects -> runes (lyric layer) -> slams -> fades -> bloom -> finish.

  render.py --preview 12.5,59.2,...      JPEGs into work/preview/
  render.py --all 4                      every missing chunk of 120 frames, 4 processes -> work/segments/cNNN.mkv
  render.py --chunks 3,4                 these chunks only (delete the old files first)

Everything that flows reads timeline.phi(t) (stops in the song's silences); everything that hits reads the
measured kicks, slams and chant times; the amount of fire in the air reads the measured loudness curve.
"""
import math
import os
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import look  # noqa: E402
import runes  # noqa: E402
import timeline as T  # noqa: E402
from look import W, H, XX, YY  # noqa: E402

ROOT = look.ROOT
CHUNK = 120

# keyframe-pixel geometry read off the keyframes (gridview.py): x, y in the 1088x1920 keyframe
FX = {
    'K21_crystal': (536, 650, 300),
    'K20_palm': (605, 932),
    'K26_gap': (562, 1150),
    'K35_fires': [(147, 654), (360, 942), (490, 1089), (585, 1187), (660, 1243)],
    'K43_star': (576, 589),
    'K57_cell': (621, 1079),
    'K67_core': (644, 1243),
    'K77_core': (533, 850),
    'K71_core': (631, 936),
    # hourglass neck: x, y, length of the falling stream (keyframe px)
    'sand_neck': {'K03': (536, 1193, 150), 'K68': (546, 1022, 300), 'K01': (310, 1285, 110), 'K81': (638, 1128, 40)},
}


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def kf_to_out(M, x, y):
    return (M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2])


def radial(cx, cy, r):
    return np.exp(-((XX - cx) ** 2 + (YY - cy) ** 2) / (2 * r * r)).astype(np.float32)


def slam_level(t):
    v = 0.0
    for ts in T.SLAMS:
        if 0 <= t - ts < 0.6:
            v = max(v, math.exp(-(t - ts) / 0.14))
    return v


def shake_of(t):
    for ts in T.SLAMS + [T.L('Bridge|4', 8)]:
        a = t - ts
        if 0 <= a < 0.35:
            amp = 14 * (1 - a / 0.35)
            rng = np.random.default_rng(int(t * T.FPS))
            return (float(rng.normal(0, amp)), float(rng.normal(0, amp)))
    return (0.0, 0.0)


def frame(t):
    sh = T.shot_at(t)
    ph = T.phi(t)
    p0, p1 = T.phi(sh.t0), T.phi(max(sh.t1 - 1e-3, sh.t0 + 1e-3))
    u = (ph - p0) / max(p1 - p0, 1e-6)
    en = T.energy(t)
    k = T.kick(t)

    # --- plate: push, kick punch, parallax drift, shake
    z = sh.z[0] + (sh.z[1] - sh.z[0]) * ease(u) if sh.z[0] != sh.z[1] else sh.z[0]
    if sh.punch:
        z *= 1.0 + 0.022 * k
    if 'count' in sh.fx:                          # the countdown pushes in one step per number
        L2 = 'Build-Up|2'
        n = sum(1 for i in range(5) if t >= T.L(L2, i))
        z = 1.0 + 0.07 * n
    dvec = np.array(sh.pdir, np.float32)
    dvec /= np.linalg.norm(dvec) + 1e-6
    par = sh.par * (u - 0.5)
    img, D, M = look.render_plate(sh.kf, z, sh.c, (float(dvec[0] * par), float(dvec[1] * par)), shake=shake_of(t))
    img = look.grade(img, sh.grade, en)
    if sh.punch:
        img = img * (1.0 + 0.05 * k)

    # --- haze
    if 'mist_green' in sh.parts or 'steam' in sh.parts:
        Dq = look.down(D)
        F = look.up(look.haze(ph, Dq))
        col = np.array([0.35, 0.85, 0.45] if 'mist_green' in sh.parts else [0.9, 0.9, 0.95], np.float32)
        amt = 0.30 if 'mist_green' in sh.parts else 0.10
        if 'steam' in sh.parts:
            F = F * np.clip((YY - 900) / 400, 0, 1) * np.clip((1500 - YY) / 300, 0, 1)
        img = img * (1 - amt * F[..., None]) + col * (amt * F[..., None])

    # --- particles (fire in the air scales with the measured loudness)
    for p in sh.parts:
        if p in ('mist_green', 'steam', 'sand_neck'):
            continue
        amount = 1.0
        if p in ('embers', 'embers_red'):
            amount = 0.35 + 0.9 * en
        elif p == 'shards':
            continue
        img = img + look.field(p, hash(sh.id) % 5).draw(ph, D, amount, T.rate(t))
    if 'shards' in sh.parts:
        img = img + shards(sh, t, M)
    if 'sand_neck' in sh.parts and sh.kf in FX['sand_neck']:
        img = img + sand_stream(sh, t, M)

    # --- shot effects
    img = shot_fx(img, sh, t, M, k, u)

    # --- slams: a hit of light on the downbeats where the band comes in (the world flares, the runes do not)
    sl = slam_level(t)
    if sl > 0.003:                               # a burst of light that keeps the blacks: highlights flare most
        img = img * (1 + 1.1 * sl) + (img ** 2) * (1.2 * sl) + 0.04 * sl

    # --- lyric layer
    img = runes.apply(img, t, D, sh)


    # --- fades
    a = 1.0
    if sh.fade_in:
        a *= ease((t - sh.t0 - 0.35) / sh.fade_in)
    if 'end_black' in sh.extra:
        a *= 1 - ease((t - (sh.extra['end_black'] - sh.fade_out)) / sh.fade_out)
    img = img * a

    img = look.bloom(img, thr=0.70, amt=0.30 + 0.15 * en)
    return look.finish(img, int(round(t * T.FPS)))


def sand_stream(sh, t, M):
    x, y, b = FX['sand_neck'][sh.kf]
    ox, oy = kf_to_out(M, x, y)
    s = M[0, 0]
    out = np.zeros((H, W), np.float32)
    ph = T.phi(t)
    rng = np.random.default_rng(5)
    n = 70
    off = rng.uniform(0, 1, n)
    L = b * s
    for i in range(n):
        f = (off[i] + ph * 1.6) % 1.0
        py = oy + f * L
        px = ox + rng.normal(0, 1.2) * s
        if 0 <= px < W and 0 <= py < H:
            out[int(py), int(px)] += 0.8
    out = cv2.GaussianBlur(out, (0, 0), 1.0) * 4
    return out[..., None] * np.array([1.0, 0.85, 0.6], np.float32)


def shards(sh, t, M):
    """Crystal shards flying out from the breaking crystal (frozen in shape, moving on the clock)."""
    key = {'K71': FX['K71_core'], 'K77': FX['K77_core']}.get(sh.kf, (544, 800))
    cx, cy = kf_to_out(M, *key)
    out = np.zeros((H, W), np.float32)
    age = T.phi(t) - T.phi(sh.t0)
    rng = np.random.default_rng(11)
    n = 260
    ang = rng.uniform(0, 2 * np.pi, n)
    sp = rng.uniform(150, 900, n)
    px = cx + np.cos(ang) * sp * age
    py = cy + np.sin(ang) * sp * age + 250 * age * age
    m = (px >= 0) & (px < W) & (py >= 0) & (py < H)
    np.add.at(out, (py[m].astype(int), px[m].astype(int)), 1.0)
    out = cv2.GaussianBlur(out, (0, 0), 2.0) * 10 * max(0.0, 1 - age / 3.0)
    col = np.array([1.0, 0.35, 0.25] if sh.kf == 'K71' else [1.0, 0.85, 0.55], np.float32)
    return out[..., None] * col


def shot_fx(img, sh, t, M, k, u):
    fx = sh.fx
    if 'crystal_flare' in fx:                          # the name: the crystal brightens as it is carved
        x, y, r = FX['K21_crystal']
        cx, cy = kf_to_out(M, x, y)
        lv = 0.25 + 0.75 * ease((t - T.NAME_STOP[0]) / (T.B(34) - T.NAME_STOP[0]))
        img = img + radial(cx, cy, r * 1.3)[..., None] * np.array([0.2, 0.75, 0.7], np.float32) * 0.45 * lv
    if 'palm' in fx:
        cx, cy = kf_to_out(M, *FX['K20_palm'])
        g = 0.6 + 0.4 * math.sin(T.phi(t) * 4.0)
        img = img + radial(cx, cy, 40)[..., None] * np.array([0.4, 1.0, 0.9], np.float32) * 0.6 * g \
            + radial(cx, cy, 160)[..., None] * np.array([0.1, 0.5, 0.45], np.float32) * 0.25 * g
    if 'gate_light' in fx:
        cx, cy = kf_to_out(M, *FX['K26_gap'])
        img = img + radial(cx, cy, 260 + 300 * u)[..., None] * np.array([1.0, 0.75, 0.4], np.float32) * (0.15 + 0.35 * u)
    if 'beacons' in fx:                                # one fire lights on each pair of vocal chops
        for i, (x, y) in enumerate(FX['K35_fires']):
            ti = T.CHOPS[0] + i * (T.CHOPS[1] - T.CHOPS[0]) / 5.5
            if t >= ti:
                cx, cy = kf_to_out(M, x, y)
                a = t - ti
                sc = (1.0, 0.72, 0.52, 0.40, 0.32)[i]                  # farther beacons are smaller
                lv = 0.6 + 1.2 * math.exp(-a / 0.12)
                img = img + radial(cx, cy, 34 * sc)[..., None] * np.array([1.0, 0.7, 0.3], np.float32) * 0.55 * lv \
                    + radial(cx, cy, 130 * sc)[..., None] * np.array([1.0, 0.45, 0.12], np.float32) * 0.14 * lv
    if 'star_fall' in fx:
        cx, cy = kf_to_out(M, *FX['K43_star'])
        lv = 0.3 + 0.9 * ease(u)
        img = img + radial(cx, cy, 30)[..., None] * 0.8 * lv + radial(cx, cy, 200)[..., None] * np.array([0.6, 0.7, 1.0], np.float32) * 0.25 * lv
    if 'blast' in fx:                                  # the bridge: the home blown apart on its word
        tb = T.L('Bridge|4', 8)
        if t >= tb:
            a = t - tb
            cx, cy = kf_to_out(M, *FX['K57_cell'])
            R = 80 + 1400 * min(1.0, a / 0.4) ** 0.7
            lv = math.exp(-a / 0.30)
            img = img + radial(cx, cy, R * 0.45)[..., None] * np.array([1.0, 0.7, 0.45], np.float32) * 1.1 * lv
    if 'crystal_pulse' in fx:
        cx, cy = kf_to_out(M, *FX['K67_core'])
        i = np.searchsorted(T.BEATS, t) - 1
        a = t - T.BEATS[max(0, i)]
        img = img + radial(cx, cy, 380)[..., None] * np.array([0.2, 0.9, 0.8], np.float32) * 0.30 * math.exp(-a / 0.2)
    if 'explode' in fx:                                # the enemy crystal goes at the loudest moment of the song
        cx, cy = kf_to_out(M, *FX['K77_core'])
        a = t - sh.t0
        R = 90 + 520 * min(1.0, a / (T.LOUDEST - sh.t0)) ** 0.7
        lv = min(1.0, a / 0.10) * (1.0 if t < T.LOUDEST else math.exp(-(t - T.LOUDEST) / 0.4))
        flash = 0.55 * math.exp(-a / 0.12)
        img = img + radial(cx, cy, R)[..., None] * np.array([1.0, 0.88, 0.62], np.float32) * 0.9 * lv + flash
    return img


# ---- driver -------------------------------------------------------------------------------------------------
def render_chunk(kc):
    f0, f1 = kc * CHUNK, min(T.NFRAMES, (kc + 1) * CHUNK)
    out = os.path.join(ROOT, 'work', 'segments', f'c{kc:03d}.mkv')
    tmp = out[:-4] + '.tmp.mkv'
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(T.FPS), '-i', '-',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-threads', '1', tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(frame(f / T.FPS).tobytes())
    p.stdin.close()
    p.wait()
    os.replace(tmp, out)
    return kc


def main():
    a = sys.argv[1:]
    if a[0] == '--preview':
        os.makedirs(os.path.join(ROOT, 'work', 'preview'), exist_ok=True)
        for s in a[1].split(','):
            t = float(s)
            im = frame(t)
            p = os.path.join(ROOT, 'work', 'preview', f'p_{t:07.2f}.jpg')
            cv2.imwrite(p, im[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 90])
            print(p, flush=True)
        return
    os.makedirs(os.path.join(ROOT, 'work', 'segments'), exist_ok=True)
    n = -(-T.NFRAMES // CHUNK)
    if a[0] == '--chunks':
        todo = [int(x) for x in a[1].split(',')]
        procs = int(a[2]) if len(a) > 2 else 4
    else:
        procs = int(a[1]) if len(a) > 1 else 4
        todo = [kc for kc in range(n) if not os.path.exists(os.path.join(ROOT, 'work', 'segments', f'c{kc:03d}.mkv'))]
    from multiprocessing import Pool
    with Pool(procs) as pool:
        for kc in pool.imap_unordered(render_chunk, todo):
            print('chunk', kc, 'done', flush=True)


if __name__ == '__main__':
    main()
