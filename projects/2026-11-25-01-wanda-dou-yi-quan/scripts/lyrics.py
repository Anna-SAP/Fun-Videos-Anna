#!/usr/bin/env python3
"""Parse the user's lyric sheet. The text itself lives only in work/src/lyrics.txt (not in the repo);
code refers to lines by index and characters by position.

  [Section]            a tag on its own line that names a section (Intro, Verse 1, Chorus, ...)
  [anything else]      a performance direction; "[Spoken ...]" marks the following lines as spoken
  other lines          one lyric line each

A second file, work/src/lyrics_sung.txt, is the lyric field embedded in the MP3: the same lines respelled the
way the generator was asked to pronounce them. It is used only to romanise characters for forced alignment.
"""
import difflib
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTIONS = ('Intro', 'Verse 1', 'Pre-Chorus', 'Chorus', 'Verse 2', 'Bridge', 'Final Chorus', 'Outro', 'End')
PUNCT = '，。、！？；：—…,.!?;: '


def is_cjk(c):
    return 0x3400 <= ord(c) <= 0x9FFF


def _read(path):
    out, sec, spoken, count = [], None, False, {}
    for raw in open(path, encoding='utf-8'):
        s = raw.strip()
        if not s:
            continue
        m = re.fullmatch(r'\[(.+)\]', s)
        if m:
            tag = m.group(1)
            if tag in SECTIONS:
                count[tag] = count.get(tag, 0) + 1
                sec = tag if count[tag] == 1 else f'{tag} {count[tag]}'
                spoken = False
            elif tag.lower().startswith('spoken'):
                spoken = True
            continue
        out.append({'sec': sec, 'spoken': spoken, 'text': s})
    return out


def load():
    """-> list of lines: {i, sec, spoken, text, chars:[{c, tail, word_gap, py}], ring}
    chars are the sung/spoken characters; tail is the punctuation that follows one; word_gap is True when a
    space follows (the sheet's phrase break). ring is the 1-based count of sung lines (None for spoken)."""
    from pypinyin import lazy_pinyin
    L = _read(os.path.join(ROOT, 'work', 'src', 'lyrics.txt'))
    S = _read(os.path.join(ROOT, 'work', 'src', 'lyrics_sung.txt'))
    assert len(L) == len(S) == 30, (len(L), len(S))
    ring = 0
    for i, (ln, sn) in enumerate(zip(L, S)):
        ln['i'] = i
        chars = []
        for c in ln['text']:
            if is_cjk(c):
                chars.append({'c': c, 'tail': '', 'gap': False, 'py': None})
            elif chars:
                if c == ' ':
                    chars[-1]['gap'] = True
                else:
                    chars[-1]['tail'] += c
        a = [x['c'] for x in chars]
        b = [c for c in sn['text'] if is_cjk(c)]
        py = ['luo' if c == '落' else p for c, p in zip(b, lazy_pinyin(''.join(b)))]
        assert len(py) == len(b)
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag == 'equal' or (tag == 'replace' and i2 - i1 == j2 - j1):
                for k in range(i2 - i1):
                    chars[i1 + k]['py'] = py[j1 + k]
        ln['chars'] = chars
        if ln['spoken']:
            ln['ring'] = None
        else:
            ring += 1
            ln['ring'] = ring
    assert ring == 26
    assert [l['ring'] for l in L if l['sec'] == 'Bridge' and not l['spoken']] == [21, 22]
    return L


if __name__ == '__main__':
    for l in load():
        print(l['i'], l['sec'], 'spoken' if l['spoken'] else f"ring {l['ring']}", len(l['chars']), 'chars; no-py:',
              [k for k, c in enumerate(l['chars']) if c['py'] is None], ' '.join(c['py'] or '-' for c in l['chars']))
