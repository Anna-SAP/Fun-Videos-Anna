"""Parse the lyric sheet (the text the user gave, saved as work/lyrics.txt) into sections, lines and timing units.

Conventions of that text:
  [Section — note]            section header, optional note
  （…）                        full-width parentheses = production notes (not sung), e.g. （scratch）
  (Back!) / (没散！)           ASCII parentheses = sung responses (backing vocal), kept and timed

A line's timing units are single CJK characters and whole Latin words/numbers; punctuation is carried by the
unit before it for display only.
"""
import re

CJK = r'㐀-鿿豈-﫿'
UNIT_RE = re.compile(rf"[{CJK}]|[A-Za-z0-9$][A-Za-z0-9$'’.,-]*[A-Za-z0-9$]|[A-Za-z0-9$]")


def units(text):
    """[(unit_text, start_char, end_char)] -- end_char extends over trailing punctuation for display."""
    out = []
    for m in UNIT_RE.finditer(text):
        tok = m.group(0)
        # a trailing comma/period that belongs to the sentence, not the number
        while tok and tok[-1] in ',.' and not re.search(r'\d[.,]\d', tok):
            tok = tok[:-1]
        out.append([tok, m.start(), m.start() + len(tok)])
    return out


def norm(s):
    """lower-case letters/digits/CJK only -- for matching against transcripts."""
    return re.sub(rf"[^a-z0-9{CJK}]", '', s.lower().replace('’', "'"))


def parse(path):
    raw = open(path, encoding='utf-8').read().splitlines()
    sections, cur = [], None
    for ln in raw:
        s = ln.strip()
        if not s:
            continue
        m = re.match(r'^\[(.+?)\](.*)$', s)
        if m:
            head = m.group(1)
            name = re.split(r'\s+[—-]\s+', head)[0].strip()
            cur = {'name': name, 'head': head, 'note': m.group(2).strip(), 'lines': []}
            sections.append(cur)
            continue
        if cur is None:          # title card before [Intro]
            continue
        sung = re.sub(r'（[^）]*）', '', s).strip()
        if not sung:
            continue
        cur['lines'].append({'raw': s, 'text': sung})
    out = sections
    lines = []
    for si, sec in enumerate(out):
        for li, l in enumerate(sec['lines']):
            l['sec'] = si
            l['sec_name'] = sec['name']
            l['units'] = units(l['text'])
            lines.append(l)
    for i, l in enumerate(lines):
        l['i'] = i
    return out, lines


if __name__ == '__main__':
    import sys
    secs, lines = parse(sys.argv[1])
    for l in lines:
        print(f"{l['i']:3d} {l['sec']:2d} {l['sec_name'][:10]:10s} {len(l['units']):3d}u  {l['text']}")
    assert len(lines) > 80, 'expected the full lyric sheet'
