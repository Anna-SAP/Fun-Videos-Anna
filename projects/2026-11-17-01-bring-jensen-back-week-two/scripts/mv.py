"""One frame of the film as a pure function of time.

frame(t) -> uint8 HxWx3

Pipeline: camera -> lyric openings (typo.draw into holes/back/inten) -> section effects add their own
openings (pinholes, the ten lamps, the market crack, LED dots ...) -> door/tower warp -> light.compose ->
foreground (crowd, dust) -> overlays (title, credits) -> grade, grain, vignette.
"""
import math

import cv2
import numpy as np

import doors
import light
import post
import scenes
import timeline as TL
import typo
from common import DUR, FPS, H, W, clamp01, ease_in, ease_out, font, hash01, smooth, to8, window
from PIL import Image, ImageDraw

DCX, DY0, DX0, DX1, DY1 = TL.DCX, TL.DY0, TL.DX0, TL.DX1, TL.DY1


def _song_subtitle():
    """The Chinese half of the MP3's title tag (read at run time, not copied into the code)."""
    import subprocess
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format_tags=title', '-of', 'default=nw=1:nk=1',
                        'work/song.mp3'], capture_output=True, text=True)
    t = r.stdout.strip()
    return t.split('melody', 1)[-1].strip() if 'melody' in t else ''


SUBTITLE = _song_subtitle()


# ----------------------------------------------------------------------------------- small helpers
def world_pts(cam, pts):
    M = typo.cam_xform(cam)
    p = np.asarray(pts, np.float32)
    return p @ M[:, :2].T + M[:, 2]


_pins = None


def pinholes():
    """Verse 1's petition: tiny holes punched into the front door, a burst on every kick of the verse.
    They stay in the door for the rest of the film (the hooks come back to the same door)."""
    global _pins
    if _pins is None:
        rng = np.random.default_rng(180000)
        t0, t1 = TL.SEC_T0[1], TL.SEC_T1[1]
        ks = TL.KICKS[(TL.KICKS >= t0) & (TL.KICKS < t1)]
        pts, born = [], []
        for k in ks:
            n = 34
            pts.append(np.stack([rng.uniform(DX0 + 30, DX1 - 30, n), rng.uniform(DY0 + 40, DY1 - 60, n)], 1))
            born.append(np.full(n, k))
        _pins = (np.concatenate(pts).astype(np.float32), np.concatenate(born), rng.random(len(ks) * 34).astype(np.float32))
    return _pins


def draw_pins(buf, t, cam, level=1.0, upto=None, flash=True):
    pts, born, rnd = pinholes()
    m = born <= (t if upto is None else min(t, upto))
    if not m.any():
        return
    sp = world_pts(cam, pts[m])
    b = born[m]
    r = rnd[m]
    z = cam[0]
    holes, inten = buf['holes'], buf['inten']
    for (x, y), bt, rr in zip(sp, b, r):
        if x < -5 or y < -5 or x > W + 5 or y > H + 5:
            continue
        a = t - bt
        k = level * (0.55 + 0.45 * rr) * (1 + (2.0 * math.exp(-a / 0.15) if flash else 0))
        rad = max(1, int(round((1.6 + 2.2 * rr) * z)))
        cv2.circle(holes, (int(x), int(y)), rad, 1.0, -1, cv2.LINE_AA)
        cv2.circle(inten, (int(x), int(y)), rad, float(k), -1)


def lamps(buf, t, cam, lit, total=10, y=None, level=1.2, blink=None, start_dark=0):
    """A row of ten round lamps over the door: 'ten days, two gone'."""
    y = DY0 - 150 if y is None else y
    xs = np.linspace(DX0 + 70, DX1 - 70, total)
    sp = world_pts(cam, [(x, y) for x in xs])
    rad = int(30 * cam[0])
    base_ring = np.zeros_like(buf['holes'])
    for i, (x, yy) in enumerate(sp):
        on = start_dark <= i < start_dark + lit
        if blink is not None and i == blink:
            on = (int(t * 4) % 2 == 0)
        cv2.circle(base_ring, (int(x), int(yy)), rad + max(2, int(4 * cam[0])), 1.0, max(1, int(3 * cam[0])), cv2.LINE_AA)
        if on:
            cv2.circle(buf['holes'], (int(x), int(yy)), rad, 1.0, -1, cv2.LINE_AA)
            cv2.circle(buf['inten'], (int(x), int(yy)), rad, level, -1)
    return base_ring


def text_overlay(img, s, x, y, size, fname='sansb', color=(1, 1, 1), alpha=1.0, anchor='la', spacing=0):
    if alpha <= 0.01:
        return img
    f = font(fname, size)
    l, t_, r, b = f.getbbox(s, anchor=anchor)
    w, h = r - l + 8, b - t_ + 8
    im = Image.new('L', (w, h), 0)
    ImageDraw.Draw(im).text((-l + 4, -t_ + 4), s, font=f, fill=255, anchor=anchor)
    m = np.asarray(im, np.float32) / 255.0 * alpha
    x0, y0 = int(x + l - 4), int(y + t_ - 4)
    x1, y1 = min(W, x0 + w), min(H, y0 + h)
    cx0, cy0 = max(0, x0), max(0, y0)
    if x1 <= cx0 or y1 <= cy0:
        return img
    sub = m[cy0 - y0:y1 - y0, cx0 - x0:x1 - x0][..., None]
    img[cy0:y1, cx0:x1] = img[cy0:y1, cx0:x1] * (1 - sub) + np.asarray(color, np.float32) * sub
    return img


def draw_shots(buf, t, cam, k, extra=None, led=None):
    """Draw every shot of section k alive at t. Returns the active shots."""
    act = []
    for sh in TL.shots_at(t):
        if sh.sec != k:
            continue
        act.append(sh)
        st = sh.st
        if extra:
            st = dict(st, **extra(sh))
        typo.draw(buf, sh.blk, t, cam, st)
        for (b, sd) in sh.subs:
            sst = dict(st, **sd.get('st', {}))
            typo.draw(led if (sd.get('led') and led is not None) else buf, b, t, cam, sst)
        echo = sh.d.get('echo_units')
        if echo:
            a0, a1, units = echo
            if a0 <= t <= a1 + 0.5:
                e = (t - a0) / max(0.01, a1 - a0)
                for j in range(3):
                    off = (-(j + 1) * 70 * clamp01(e), 0)
                    typo.draw(buf, sh.blk, t, cam, dict(st, units=units, off=off, level=0.55 / (j + 1), flash=0,
                                                        inn='fade', din=0.01, t_out=a1, dout=0.5))
    return act


def glyph_rect(sh, units, cam, pad=10):
    """Screen-space bounding box of the glyphs of `units` in shot sh."""
    M = typo.cam_xform(cam)
    pts = []
    for g in sh.blk.glyphs:
        if g.unit in units:
            for (x, y) in ((g.x, g.y), (g.x + g.w, g.y), (g.x, g.y + g.h), (g.x + g.w, g.y + g.h)):
                pts.append(typo.to_screen(M, sh.blk.ox + x, sh.blk.oy + y))
    if not pts:
        return None
    p = np.array(pts)
    return p[:, 0].min() - pad, p[:, 1].min() - pad, p[:, 0].max() + pad, p[:, 1].max() + pad


def unit_time(sh, u):
    tt = sh.blk.times[u]
    return tt[0] if tt else sh.t0


def shot_fx(buf, t, cam, act, black):
    """Per-shot effects: redaction bars, typing cursor, lamps; returns (ring or None, glitch)."""
    ring, gl = None, 0.0
    for sh in act:
        d = sh.d
        if d.get('redact'):
            us = d['redact']
            ta = max(sh.blk.times[u][1] for u in us) + 0.25
            r = glyph_rect(sh, us, cam, pad=14)
            t_end = sh.st['t_out'] + sh.st['dout']
            if r is not None and ta < t < t_end:
                e = ease_out((t - ta) / 0.22)
                x0, y0, x1, y1 = [int(v) for v in r]
                xe = int(x0 + (x1 - x0) * e)
                fade = 1.0 - smooth((t - sh.st['t_out']) / sh.st['dout']) if t > sh.st['t_out'] else 1.0
                y0c, y1c, x0c, xec = max(0, y0), min(H, y1), max(0, x0), min(W, xe)
                if y1c > y0c and xec > x0c:
                    buf['holes'][y0c:y1c, x0c:xec] = 0
                    black[y0c:y1c, x0c:xec] = fade
        if d.get('cursor'):
            shown = [g for g in sh.blk.glyphs if unit_time(sh, g.unit) - 0.04 <= t]
            if shown and t < sh.st['t_out']:
                g = max(shown, key=lambda q: q.k)
                M = typo.cam_xform(cam)
                x, y = typo.to_screen(M, sh.blk.ox + g.x + g.w + 14, sh.blk.oy + g.y)
                if int(t * 2.4) % 2 == 0:
                    hh = int(g.h * cam[0])
                    x0, y0 = int(x), int(y)
                    cv2.rectangle(buf['holes'], (x0, y0), (x0 + int(18 * cam[0]), y0 + hh), 1.0, -1)
                    cv2.rectangle(buf['inten'], (x0, y0), (x0 + int(18 * cam[0]), y0 + hh), 1.1, -1)
        if d.get('lamps') and sh.t0 - 0.3 <= t <= sh.st['t_out'] + sh.st['dout']:
            line = d['line']
            if line in (38, 112):        # L38/L112: ten lamps; the two on the left go dark on unit 8
                tg = unit_time(sh, 8)
                lit = 10 if t < tg else 8
                ring = lamps(buf, t, cam, lit, start_dark=0 if t < tg else 2)
            else:                         # L121: eight left, the next one blinking, from unit 7
                tg = unit_time(sh, 7)
                ring = lamps(buf, t, cam, 10 if t < tg else 8, start_dark=0 if t < tg else 2,
                             blink=2 if t >= tg else None)
        if d.get('rewind'):
            a0 = unit_time(sh, 2)
            a1 = unit_time(sh, 5)
            if a0 - 0.05 <= t <= a1:
                gl = max(gl, 0.35 + 0.25 * math.sin((t - a0) * 40) ** 2)
    return ring, gl


# ----------------------------------------------------------------------------------- the frame
_crack = None


def crack_pts():
    """The market's line, cut through the board-room door: a jagged fall from upper left to lower right."""
    global _crack
    if _crack is None:
        rng = np.random.default_rng(156)
        n = 46
        xs = np.linspace(DX0 + 40, DX1 - 40, n)
        trend = np.linspace(DY0 + 520, DY1 - 380, n)
        ys = trend + np.cumsum(rng.normal(0, 38, n)) * 0.6 + rng.normal(0, 40, n)
        ys[0] = DY0 + 520
        _crack = np.stack([xs, ys], 1).astype(np.float32)
    return _crack


def draw_crack(buf, t, cam, t0, t1, level=1.0):
    if t < t0:
        return
    p = crack_pts()
    e = clamp01((t - t0) / (t1 - t0))
    n = max(2, int(len(p) * e) + 1)
    sp = world_pts(cam, p[:n]).astype(np.int32)
    w = max(2, int(7 * cam[0]))
    cv2.polylines(buf['holes'], [sp], False, 1.0, w, cv2.LINE_AA)
    fl = level * (0.8 + 0.4 * hash01(int(t * 20), 77))
    cv2.polylines(buf['inten'], [sp], False, float(fl), w, cv2.LINE_AA)
    # the head of the line burns brighter
    cv2.circle(buf['inten'], tuple(sp[-1]), w * 2, 2.5, -1)
    cv2.circle(buf['holes'], tuple(sp[-1]), w, 1.0, -1)


def frame(t):
    k = TL.section_at(t)
    name, _, world, color = TL.SEC[k]
    color = np.array(color, np.float32)
    cam = TL.camera(t)
    buf = typo.new_buffers()
    led = typo.new_buffers() if world == 'tower' else None
    black = np.zeros((H, W), np.float32)
    kick = TL.pulse(TL.KICKS, t, 0.12)
    snare = TL.pulse(TL.SNARES, t, 0.1)
    s0, s1 = TL.SEC_T0[k], TL.SEC_T1[k]
    gap_level, fill, glow, rays, ray_len = 1.0, 0.95, 1.0, 0.55, 0.35
    glitch = 0.0
    overlay = []
    fg = None
    extra = None
    flash = 0.0

    if name == 'intro':
        lamp_on = TL.first('i2') - 0.02
        if t < lamp_on:
            fl = 0.55 + 0.45 * hash01(int(t * 12), 4) ** 0.5
            color = np.array([0.5, 0.72, 1.0], np.float32) * (0.85 + 0.15 * math.sin(t * 9))
            gap_level = 0.65 * fl
            fill = 0.42
            glitch = 0.04 + 0.2 * window(t, 7.7, 7.95, 0.05, 0.1)
            extra = lambda sh: {'pulse': lambda tt: 0.75 + 0.25 * hash01(int(tt * 15), 9)}  # noqa: E731
        else:
            e = ease_out((t - lamp_on) / 0.6)
            gap_level = 0.65 + 0.55 * e
            fill = 0.42 + 0.38 * e
            color = np.array([0.5, 0.72, 1.0]) * (1 - e) + np.array([0.55, 1.0, 0.62]) * e
            glitch = max(0.3 * math.exp(-(t - lamp_on) / 0.15), 0.45 * window(t, 8.05, 8.42, 0.03, 0.08))
            flash = 0.25 * math.exp(-(t - lamp_on) / 0.2)
        if t < 2.25:
            a = window(t, 0.35, 1.85, 0.4, 0.35)
            overlay.append(('Bring Jensen Back 2.0', W / 2, H * 0.84, 46, 'anton', a * 0.85))
            overlay.append((SUBTITLE, W / 2, H * 0.84 + 64, 34, 'sansb', a * 0.7))
        act = draw_shots(buf, t, cam, k, extra)
    elif name == 'verse1':
        draw_pins(buf, t, cam, level=0.9)
        act = draw_shots(buf, t, cam, k)
        gap_level = 1.0 + 0.4 * kick
    elif name == 'pre':
        hb = TL.pulse(TL.KICKS, t, 0.28)
        prog = clamp01((t - s0) / (s1 - s0))
        extra = lambda sh: {'pulse': lambda tt: 0.55 + 0.75 * TL.pulse(TL.KICKS, tt, 0.28)}  # noqa: E731
        act = draw_shots(buf, t, cam, k, extra)
        gap_level = 0.4 + 0.9 * hb
        rays = 0.45 + 0.7 * prog
        ray_len = 0.3 + 0.4 * prog
        fill = 0.7
        flash = 0.9 * ease_in(clamp01((t - (s1 - 0.5)) / 0.5), 2)
    elif name in ('hook1', 'hook2', 'drop'):
        draw_pins(buf, t, cam, level=0.7 + 0.5 * kick, flash=False)
        act = draw_shots(buf, t, cam, k)
        gap_level = 1.1 + 0.8 * kick
        rays = 0.6 + 0.25 * kick
        fg = ('crowd', 1.0, 0.6 + 0.4 * snare, kick)
        if t < s0 + 0.35:
            flash = 0.8 * (1 - (t - s0) / 0.35)
        if name == 'drop':
            strobe = 1.0 if (int(t * FPS) % 4) < 2 else 0.5
            gap_level *= strobe
            glow = 1.25
            fg = ('crowd', 1.0, 0.7 + 0.5 * snare, kick)
        if name == 'hook2':
            glow = 1.15
    elif name == 'verse2':
        act = draw_shots(buf, t, cam, k)
        gap_level = 0.9 + 0.3 * TL.pulse(TL.KICKS, t, 0.08)
        fill = 0.75
    elif name == 'build':
        prog = clamp01((t - s0) / (s1 - s0))
        act = draw_shots(buf, t, cam, k)
        gap_level = 0.7 + 1.3 * prog
        rays = 0.5 + 0.6 * prog
        fill = 0.6 + 0.3 * prog
        color = np.array([0.62, 0.92, 1.0]) * (1 - prog) + np.array([1.0, 0.9, 0.7]) * prog
        flash = 0.7 * ease_in(clamp01((t - (s1 - 0.4)) / 0.4), 2)
    elif name == 'taipei':
        act = draw_shots(buf, t, cam, k, led=led)
    elif name == 'verse3':
        act = draw_shots(buf, t, cam, k)
        if 'v3i' in TL.TIM:
            draw_crack(buf, t, cam, TL.first('v3i'), TL.last('v3l'), level=1.0)
        gap_level = 0.9 + 0.3 * kick
    elif name == 'bridge':
        act = draw_shots(buf, t, cam, k)
        rays = 0.45
        gap_level = 0.9
        fill = 0.75
    elif name == 'outro':
        act = draw_shots(buf, t, cam, k)
        rays = 0.45
        fill = 0.7
        if 'o7' in TL.TIM and t > TL.last('o7') + 0.4:
            glitch = 0.5 * window(t, TL.first('o8') - 0.9, TL.first('o8') - 0.6, 0.05, 0.1)
    else:
        act = draw_shots(buf, t, cam, k)
    ring, gl = shot_fx(buf, t, cam, act, black)
    glitch = max(glitch, gl)

    if world == 'tower':
        base, fac = scenes.tower_view(cam, fill=1.6)
        dots = scenes.dotgrid(max(5, int(round(9 * cam[0]))), 0.44)
        # the whole facade is a wall of warm lamps; it switches on with the first line and breathes
        won = smooth((t - s0 - 0.2) / 1.2)
        wall = fac * dots * won * (0.10 + 0.03 * math.sin(t * 2.0))
        holes = np.maximum(np.maximum(buf['holes'], led['holes'] * dots), wall)
        inten = np.maximum(np.maximum(buf['inten'], led['inten']), (wall > 0) * 1.0)
        inner = np.zeros_like(holes)
        img = light.compose(base, holes, inner, inten, color, glow=1.0, rays=0.3, bounce=0.0, haze=0.4)
    else:
        base, gap, spill = post.door_view(world, cam, fill=fill)
        if ring is not None:
            base = base * (1 - ring[..., None]) + ring[..., None] * 0.2
        holes = np.maximum(buf['holes'], gap * gap_level)
        inten = np.maximum(buf['inten'], gap * gap_level * 1.3)
        inner = buf['holes'] * (1 - buf['back'])
        img = light.compose(base, holes, inner, inten, color, glow=glow, rays=rays, ray_len=ray_len)
        img = img + spill[..., None] * color[None, None, :] * (0.45 * gap_level)
    if black.any():
        img = img * (1 - 0.94 * black[..., None])
    if fg and fg[0] == 'crowd':
        img = post.crowd(img, t, fg[1], fg[2], color, kick=fg[3], raise_=0.8 + 0.2 * fg[3])
    if flash > 0.005:
        img = img + flash * (0.6 + 0.4 * color[None, None, :])
    for (txt, x, y, size, fn, a) in overlay:
        f = font(fn, size)
        w = f.getlength(txt)
        img = text_overlay(img, txt, x - w / 2, y, size, fn, (0.85, 0.85, 0.85), a)
    if name == 'outro':
        end = clamp01((t - (DUR - 1.6)) / 1.4)
        img = img * (1 - end)
    if glitch > 0.01:
        img = post.glitch(img, t, glitch)
    img = post.finish(img, t)
    return to8(img)


if __name__ == '__main__':
    import sys
    import time
    for a in sys.argv[1:]:
        t = float(a)
        t1 = time.time()
        im = frame(t)
        cv2.imwrite(f'work/preview/f_{t:07.2f}.jpg', im[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 90])
        print(t, TL.sec_name(t), int((time.time() - t1) * 1000), 'ms')
