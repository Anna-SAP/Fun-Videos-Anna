#!/usr/bin/env python3
"""Fetch the film's fonts from the Google Fonts CSS API (all OFL) as TTF files under work/fonts/.

  fetch_fonts.py LYRICS.txt [EXTRA_TEXT]

Latin families come whole (latin + latin-ext subsets merged). CJK families are requested with `text=` so the
server returns a subset holding exactly the characters the film shows (lyrics file + EXTRA_TEXT + ASCII);
long character lists are requested in chunks and merged with fontTools.
"""
import io
import os
import re
import sys
import urllib.parse
import urllib.request

from fontTools.merge import Merger
from fontTools.ttLib import TTFont

OUT = 'work/fonts'
os.makedirs(OUT, exist_ok=True)
text = open(sys.argv[1], encoding='utf-8').read()
extra = sys.argv[2] if len(sys.argv) > 2 else ''
cjk = sorted(set(c for c in text + extra if ord(c) > 0x2000 and not c.isspace()))
ascii_ = ''.join(chr(i) for i in range(0x20, 0x7f))
print(len(cjk), 'non-ASCII characters')

LATIN = {'Anton': 'Anton:wght@400', 'ArchivoBlack': 'Archivo+Black:wght@400', 'SpaceMono': 'Space+Mono:wght@700',
         'SpaceMonoR': 'Space+Mono:wght@400', 'PermanentMarker': 'Permanent+Marker:wght@400',
         'BebasNeue': 'Bebas+Neue:wght@400', 'UnifrakturCook': 'UnifrakturCook:wght@700'}
CJK = {'NotoSansSC-Black': 'Noto+Sans+SC:wght@900', 'NotoSansSC-Bold': 'Noto+Sans+SC:wght@700',
       'NotoSerifSC-Black': 'Noto+Serif+SC:wght@900', 'ZCOOLQingKe': 'ZCOOL+QingKe+HuangYou:wght@400',
       'ZhiMangXing': 'Zhi+Mang+Xing:wght@400'}


def css(q):
    return urllib.request.urlopen('https://fonts.googleapis.com/css2?family=' + q, timeout=60).read().decode()


def urls(c):
    return re.findall(r"url\((https://[^)]+)\) format\('truetype'\)", c)


def fetch(u):
    return TTFont(io.BytesIO(urllib.request.urlopen(u, timeout=120).read()))


def merge(fonts, path):
    if len(fonts) == 1:
        fonts[0].save(path)
        return
    parts = []
    for i, f in enumerate(fonts):
        for t in ('GSUB', 'GPOS', 'GDEF'):  # subset layout tables differ between chunks and break the merger
            if t in f:
                del f[t]
        p = f'{path}.part{i}.ttf'
        f.save(p)
        parts.append(p)
    Merger().merge(parts).save(path)
    for p in parts:
        os.remove(p)


for name, q in LATIN.items():
    path = f'{OUT}/{name}.ttf'
    if os.path.exists(path):
        continue
    us = urls(css(q))
    merge([fetch(u) for u in us], path)
    print(name, len(us), 'subsets')

for name, q in CJK.items():
    path = f'{OUT}/{name}.ttf'
    if os.path.exists(path):
        continue
    chars = cjk + list(ascii_)
    fonts = []
    for i in range(0, len(chars), 150):
        chunk = ''.join(chars[i:i + 150])
        us = urls(css(q + '&text=' + urllib.parse.quote(chunk)))
        fonts += [fetch(u) for u in us]
    merge(fonts, path)
    cmap = TTFont(path).getBestCmap()
    miss = [c for c in cjk if ord(c) not in cmap]
    print(name, 'missing', ''.join(miss))
