#!/usr/bin/env python3
"""Download the fonts the film uses from Google Fonts (all OFL), keeping only the subsets it needs.

  fetch_fonts.py LYRICS.txt OUTDIR

Google Fonts serves CJK families split into ~100 unicode-range WOFF2 slices. For each family this reads the
CSS, downloads only the slices that hold characters in the lyrics file (plus the on-screen extras below),
converts them from WOFF2 and merges them into one TTF with fontTools.
"""
import io
import os
import re
import sys
import urllib.request

from fontTools.merge import Merger
from fontTools.ttLib import TTFont

lyr_path, outdir = sys.argv[1:3]
os.makedirs(outdir, exist_ok=True)
EXTRA = ('0123456789$,.:;!?\'"-—…·%+#@&()/[]<>|*=_~^ ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
         '“”‘’《》〈〉「」『』（）、。，：；！？—…·％▲▼↑↓→←'
         '年月日周秒分时第号天一二三四五六七八九十百千万亿零两〇')
chars = set(open(lyr_path, encoding='utf-8').read()) | set(EXTRA)
chars = {c for c in chars if not c.isspace()}
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
FAMILIES = {
    'NotoSerifSC-Black.ttf': 'Noto+Serif+SC:wght@900',
    'NotoSerifSC-Bold.ttf': 'Noto+Serif+SC:wght@700',
    'NotoSerifSC-Medium.ttf': 'Noto+Serif+SC:wght@500',
    'NotoSerifSC-Regular.ttf': 'Noto+Serif+SC:wght@400',
    'NotoSansSC-Medium.ttf': 'Noto+Sans+SC:wght@500',
    'NotoSansSC-Regular.ttf': 'Noto+Sans+SC:wght@400',
    'LXGWWenKaiTC-Regular.ttf': 'LXGW+WenKai+TC:wght@400',
    'LXGWWenKaiTC-Bold.ttf': 'LXGW+WenKai+TC:wght@700',
    'MaShanZheng.ttf': 'Ma+Shan+Zheng',
    'ZCOOLXiaoWei.ttf': 'ZCOOL+XiaoWei',
    'PlayfairDisplay-Italic.ttf': 'Playfair+Display:ital,wght@1,500',
    'PlayfairDisplay-Regular.ttf': 'Playfair+Display:wght@500',
    'CormorantGaramond-MediumItalic.ttf': 'Cormorant+Garamond:ital,wght@1,500',
}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=120).read()


def in_range(cp, rng):
    for part in rng.split(','):
        part = part.strip().upper().replace('U+', '')
        if '-' in part:
            a, b = part.split('-')
            if int(a, 16) <= cp <= int(b, 16):
                return True
        elif part and int(part, 16) == cp:
            return True
    return False


for name, fam in FAMILIES.items():
    out = os.path.join(outdir, name)
    if os.path.exists(out):
        print('have', name)
        continue
    css = get(f'https://fonts.googleapis.com/css2?family={fam}&display=swap').decode()
    need = []
    for block in re.findall(r'@font-face\s*{(.*?)}', css, re.S):
        url = re.search(r'url\(([^)]+\.woff2)\)', block).group(1)
        rng = re.search(r'unicode-range:\s*([^;}]+)', block).group(1)
        if any(in_range(ord(c), rng) for c in chars):
            need.append(url)
    paths = []
    for i, url in enumerate(need):
        f = TTFont(io.BytesIO(get(url)))
        f.flavor = None
        p = f'{out}.part{i}.ttf'
        f.save(p)
        paths.append(p)
    merged = Merger().merge(paths) if len(paths) > 1 else TTFont(paths[0])
    merged.save(out)
    for p in paths:
        os.remove(p)
    cmap = TTFont(out).getBestCmap()
    missing = sorted(c for c in chars if ord(c) not in cmap)
    if not any(k in name for k in ('Noto','ZCOOL','LXGW','MaShan')):
        missing = [c for c in missing if ord(c) < 0x2E80]
    print(name, len(need), 'slices; missing:', ''.join(missing)[:80])
