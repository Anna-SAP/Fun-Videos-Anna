#!/usr/bin/env python3
"""Contact sheet of stills.   sheet.py OUT.jpg COLS THUMB_W FILE [FILE ...]   (labels are the file stems)"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

out, cols, tw = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
files = sys.argv[4:]
th = tw * 16 // 9
rows = -(-len(files) // cols)
sheet = Image.new('RGB', (cols * tw, rows * th), (12, 12, 12))
font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', max(14, tw // 14))
for i, f in enumerate(files):
    im = Image.open(f).convert('RGB').resize((tw, th), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    label = os.path.splitext(os.path.basename(f))[0]
    d.rectangle((0, 0, font.getlength(label) + 12, font.size + 10), fill=(0, 0, 0))
    d.text((6, 4), label, font=font, fill=(255, 220, 90))
    sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
sheet.save(out, quality=88)
print(out, sheet.size)
