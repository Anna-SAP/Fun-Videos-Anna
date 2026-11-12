#!/usr/bin/env python3
"""Before/after contact sheets for each join, a 2-second sheet of the re-edit and the posters.

Usage: python3 compare_sheets.py <source.mp4> <re-edit.mp4> <thumbs_dir> <site_posters_dir> [--vs]
       (--vs only writes the 1280x720 before/after still for the site)
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC, OUT, THUMBS, POSTERS = sys.argv[1:5]
FONT = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
TW, TH = 320, 180
OVERLAP = 25          # output frame = source frame - 25 after the B->C dissolve

# (title, source frames, output frames)
JOINS = [
    ('① 5.6 秒 · 第一段 → 舞蹈段：横向甩镜推入，遮幅在落拍时打开',
     [166, 167, 168, 169, 170, 171, 172, 173, 185, 189],
     [166, 167, 168, 169, 170, 171, 172, 173, 185, 189]),
    ('② 10.2 秒 · 第一首 → 第二首：回声残影沉进黑场，白边改黑并收成超宽画幅',
     [302, 304, 306, 307, 308, 309, 311, 313, 315, 317],
     [302, 304, 306, 307, 308, 309, 311, 313, 315, 317]),
    ('③ 30.0 秒 · 第二首 → 第三首：雾化成烟，按亮度溶解 25 帧，画幅回到 2.35:1',
     [880, 886, 892, 896, 898, 899, 900, 901, 903, 906],
     [876, 879, 882, 885, 888, 891, 894, 897, 900, 906]),
    ('开头与结尾：遮幅像眼睛一样睁开、闭上，声音随之打开、收拢',
     [0, 3, 6, 9, 15, 2060, 2070, 2078, 2084, 2090],
     [0, 3, 6, 9, 15, 2035, 2045, 2053, 2059, 2065]),
]


def grab(path, frames):
    want = sorted(set(frames))
    cap = cv2.VideoCapture(path)
    got, i = {}, 0
    while want and i <= want[-1]:
        ok, f = cap.read()
        if not ok:
            break
        if i in want:
            got[i] = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)).resize((TW, TH), Image.LANCZOS)
        i += 1
    return got


def label(im, text, size=15):
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(FONT, size)
    w = d.textlength(text, font=font)
    d.rectangle((0, 0, w + 10, size + 8), fill=(0, 0, 0))
    d.text((5, 3), text, font=font, fill=(255, 214, 90))
    return im


def join_sheet(title, sf, of, src_frames, out_frames, path):
    cols = len(sf)
    head, rowlab, pad = 44, 70, 4
    W = rowlab + cols * (TW + pad)
    H = head + 2 * (TH + pad) + 6
    sheet = Image.new('RGB', (W, H), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    d.text((10, 10), title, font=ImageFont.truetype(FONT, 22), fill=(240, 240, 240))
    small = ImageFont.truetype(FONT, 18)
    for r, (name, frames, grabbed) in enumerate([('原片', sf, src_frames), ('重剪', of, out_frames)]):
        y = head + r * (TH + pad)
        d.text((14, y + TH // 2 - 12), name, font=small, fill=(255, 214, 90) if r else (170, 170, 170))
        for c, fr in enumerate(frames):
            im = grabbed[fr].copy()
            label(im, f'{fr / 30:.2f}s')
            sheet.paste(im, (rowlab + c * (TW + pad), y))
    sheet.save(path, quality=88)
    print(path, sheet.size)


def main():
    os.makedirs(THUMBS, exist_ok=True)
    all_src = sorted({f for _, s, _ in JOINS for f in s})
    all_out = sorted({f for _, _, o in JOINS for f in o} | set(range(0, 2078, 60)) | {309, 889, 190})
    src = grab(SRC, all_src)
    out = grab(OUT, all_out)
    names = ['t1', 't2', 't3', 'open-close']
    for (title, sf, of), n in zip(JOINS, names):
        join_sheet(title, sf, of, src, out, f'{THUMBS}/winwin-mix_{n}.jpg')

    # 2-second sheet of the re-edit
    frames = list(range(0, 2078, 60))
    cols = 7
    rows = -(-len(frames) // cols)
    sheet = Image.new('RGB', (cols * (TW + 4), rows * (TH + 4)), (18, 18, 20))
    for k, fr in enumerate(frames):
        sheet.paste(label(out[fr].copy(), f'{fr / 30:.0f}s'), ((k % cols) * (TW + 4), (k // cols) * (TH + 4)))
    sheet.save(f'{THUMBS}/winwin-mix_sheet.jpg', quality=86)

    # posters: the echo-out ghost frame (full-res re-grab)
    cap = cv2.VideoCapture(OUT)
    for _ in range(310):                      # sequential read: frame-exact
        ok, f = cap.read()
    big = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    big.resize((1280, 720), Image.LANCZOS).save(f'{POSTERS}/winwin-mix.jpg', quality=86)
    big.resize((640, 360), Image.LANCZOS).save(f'{THUMBS}/winwin-mix_poster.jpg', quality=88)
    print('posters done')


if __name__ == '__main__' and '--vs' not in sys.argv:
    main()


def vs_poster(src_path, out_path, dst):
    """1280x720 still for the site: three joins, each as a 原片 row over a 重剪 row."""
    rows = [  # (label, frames) pairs; the re-edit timeline is 25 frames shorter after the third join
        ('① 原片', src_path, [167, 168, 169, 170, 171, 173]), ('① 重剪', out_path, [167, 168, 169, 170, 171, 173]),
        ('② 原片', src_path, [304, 306, 307, 309, 312, 317]), ('② 重剪', out_path, [304, 306, 307, 309, 312, 317]),
        ('③ 原片', src_path, [890, 896, 900, 901, 904, 910]), ('③ 重剪', out_path, [876, 882, 886, 890, 894, 900]),
    ]
    tw, th, lab = 202, 114, 64
    canvas = Image.new('RGB', (1280, 720), (16, 16, 18))
    d = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT, 17)
    cache = {}
    for path in (src_path, out_path):
        cache[path] = grab_full(path, sorted({f for _, p, fr in rows if p == path for f in fr}), tw, th)
    for r, (name, path, frames) in enumerate(rows):
        y = 6 + r * (th + 6) + (6 if r >= 2 else 0) + (6 if r >= 4 else 0)
        d.text((8, y + th // 2 - 10), name, font=font, fill=(255, 214, 90) if '重剪' in name else (160, 160, 160))
        for c, fr in enumerate(frames):
            canvas.paste(cache[path][fr], (lab + c * (tw + 1), y))
    canvas.save(dst, quality=88)
    print(dst)


def grab_full(path, frames, tw, th):
    cap = cv2.VideoCapture(path)
    got, i = {}, 0
    while i <= frames[-1]:
        ok, f = cap.read()
        if not ok:
            break
        if i in frames:
            got[i] = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)).resize((tw, th), Image.LANCZOS)
        i += 1
    return got


if __name__ == '__main__' and len(sys.argv) > 5 and sys.argv[5] == '--vs':
    vs_poster(SRC, OUT, f'{POSTERS}/winwin-mix-vs.jpg')
