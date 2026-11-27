#!/usr/bin/env python3
"""Keyframes with a labelled 100 px grid, side by side, for reading coordinates.  gridview.py OUT.jpg ID [ID ...]"""
import sys
from PIL import Image, ImageDraw
out, ids = sys.argv[1], sys.argv[2:]
S = 0.5
tiles = []
for k in ids:
    im = Image.open(f'work/keyframes/{k}.png').convert('RGB')
    d = ImageDraw.Draw(im)
    for x in range(0, im.width, 100):
        d.line([x, 0, x, im.height], fill=(255, 60, 60) if x % 500 == 0 else (200, 200, 0), width=1)
        d.text((x + 3, 3), str(x), fill=(255, 255, 0))
    for y in range(0, im.height, 100):
        d.line([0, y, im.width, y], fill=(255, 60, 60) if y % 500 == 0 else (200, 200, 0), width=1)
        d.text((3, y + 3), str(y), fill=(255, 255, 0))
    d.text((40, 40), k, fill=(0, 255, 255))
    tiles.append(im.resize((int(im.width * S), int(im.height * S))))
sh = Image.new('RGB', (sum(t.width for t in tiles), tiles[0].height))
x = 0
for t in tiles:
    sh.paste(t, (x, 0)); x += t.width
sh.save(out, quality=90)
