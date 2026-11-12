#!/usr/bin/env python3
"""Build one small TTF of LXGW WenKai (OFL) holding exactly the Chinese characters the film uses.

  fetch_cjk_font.py LYRICS.json OUT.ttf [light|regular]

The npm package lxgw-wenkai-webfont ships the font split into ~100 unicode-range subsets. This reads the
package CSS, downloads only the subsets that contain the characters in the lyrics' Chinese lines (plus a
few extra strings used on screen), converts them from WOFF2 and merges them with fontTools.
"""
import io
import json
import re
import sys
import urllib.request

from fontTools.merge import Merger
from fontTools.ttLib import TTFont

lyr = json.load(open(sys.argv[1], encoding='utf-8'))
out = sys.argv[2]
weight = sys.argv[3] if len(sys.argv) > 3 else 'regular'
EXTRA = '慢慢抱紧我，。、：·「」—词曲演唱歌词校对翻译制作'
chars = set(''.join(l.get('zh', '') for l in lyr['lines']) + EXTRA)
BASE = 'https://cdn.jsdelivr.net/npm/lxgw-wenkai-webfont@1.7.0/'
css = urllib.request.urlopen(BASE + f'lxgwwenkai-{weight}.css', timeout=60).read().decode()


def in_range(cp, rng):
    for part in rng.split(','):
        part = part.strip().replace('U+', '').replace('u+', '')
        if '-' in part:
            a, b = part.split('-')
            if int(a, 16) <= cp <= int(b, 16):
                return True
        elif '?' in part:
            if int(part.replace('?', '0'), 16) <= cp <= int(part.replace('?', 'F'), 16):
                return True
        elif part and int(part, 16) == cp:
            return True
    return False


need = []
for block in re.findall(r'@font-face\s*{(.*?)}', css, re.S):
    url = re.search(r'url\([\'"]?([^\'")]+\.woff2)', block).group(1)
    rng = re.search(r'unicode-range:\s*([^;}]+)', block).group(1)
    if any(in_range(ord(c), rng) for c in chars):
        need.append(url)
print(len(need), 'subsets for', len(chars), 'characters')
paths = []
for i, url in enumerate(need):
    full = url if url.startswith('http') else BASE + url.lstrip('./')
    f = TTFont(io.BytesIO(urllib.request.urlopen(full, timeout=120).read()))
    f.flavor = None
    p = f'{out}.part{i}.ttf'
    f.save(p)
    paths.append(p)
merged = Merger().merge(paths) if len(paths) > 1 else TTFont(paths[0])
merged.save(out)
cmap = TTFont(out).getBestCmap()
missing = [c for c in chars if ord(c) not in cmap and not c.isspace()]
print('missing', missing)
