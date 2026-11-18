"""Parse the user's lyric sheet (kept only in work/lyrics.txt, never in the repo) into sections, lines and units.

Conventions of that sheet (stated by the user):
  [Section: arrangement note]     section header; not sung
  [Spoken] / [DJ scratch: "..."]  cues; not sung text, not shown
  (...)                           ASCII parentheses = backing vocals / ad-libs; sung, shown as a second voice

A line's timing units are single CJK characters (incl. 〇) and whole Latin words or numbers. Punctuation is
carried by the unit before it for display only. Every unit records whether it sits inside parentheses (backing).

Scripts refer to lines by index and to units by position; the words themselves stay in the sheet.
"""
import re

CJK = r'〇㐀-鿿豈-﫿'
UNIT_RE = re.compile(rf"[{CJK}]|[A-Za-z0-9][A-Za-z0-9'’-]*[A-Za-z0-9]|[A-Za-z0-9]")


def units(text):
    """[[tok, start_char, end_char, backing]] over the whole line (parentheses included in the text)."""
    depth = [0] * (len(text) + 1)
    d = 0
    for k, ch in enumerate(text):
        if ch == '(':
            d += 1
        depth[k] = d
        if ch == ')':
            d -= 1
    out = []
    for m in UNIT_RE.finditer(text):
        out.append([m.group(0), m.start(), m.end(), depth[m.start()] > 0])
    return out


def phrases(text):
    """Split the main (non-backing) text at the sheet's own spaces and dashes -> list of (a, b) char spans.
    A dash ' — ' is a phrase break too. Backing groups in parentheses are returned separately."""
    spans, back = [], []
    k = 0
    n = len(text)
    while k < n:
        if text[k] == '(':
            j = text.index(')', k)
            back.append((k, j + 1))
            k = j + 1
            continue
        if text[k] in ' —':
            k += 1
            continue
        j = k
        while j < n and text[j] not in '(' and not (text[j] == ' ' and _cjk_boundary(text, j)) and text[j] != '—':
            j += 1
        seg = text[k:j].rstrip()
        if seg:
            spans.append((k, k + len(seg)))
        k = j
    return spans, back


def _cjk_boundary(text, j):
    """a space is a phrase break unless it sits between two Latin words (e.g. 'ghost job', '9 to 5')."""
    a = text[j - 1] if j > 0 else ' '
    b = text[j + 1] if j + 1 < len(text) else ' '
    lat = lambda c: c.isascii() and (c.isalnum() or c in "'’-!?,.")  # noqa: E731
    return not (lat(a) and lat(b))


def norm(s):
    return re.sub(rf"[^a-z0-9{CJK}]", '', s.lower().replace('’', "'"))


def parse(path):
    raw = open(path, encoding='utf-8').read().splitlines()
    sections, cur = [], None
    for ln in raw:
        s = ln.strip()
        if not s:
            continue
        m = re.match(r'^\[([^\]]+)\]$', s)
        if m:
            head = m.group(1)
            name = head.split(':')[0].strip()
            if name in ('Spoken',) or name.startswith('DJ scratch'):
                if cur is not None:
                    cur.setdefault('cues', []).append((len(cur['lines']), head))
                continue
            if name == 'End':
                continue
            cur = {'name': name, 'head': head, 'lines': [], 'cues': []}
            sections.append(cur)
            continue
        if cur is None:
            continue
        cur['lines'].append({'text': s})
    lines = []
    for si, sec in enumerate(sections):
        spoken_from = [k for k, h in sec['cues'] if h == 'Spoken']
        for li, l in enumerate(sec['lines']):
            l['sec'] = si
            l['sec_name'] = sec['name']
            l['spoken'] = bool(spoken_from) and li >= min(spoken_from)
            l['units'] = units(l['text'])
            l['phr'], l['back'] = phrases(l['text'])
            lines.append(l)
    for i, l in enumerate(lines):
        l['i'] = i
    return sections, lines


if __name__ == '__main__':
    import sys
    secs, lines = parse(sys.argv[1])
    for s in secs:
        print('#', s['name'], len(s['lines']), s['cues'])
    for l in lines:
        nm = sum(1 for u in l['units'] if not u[3])
        nb = sum(1 for u in l['units'] if u[3])
        ph = ' | '.join(l['text'][a:b] for a, b in l['phr'])
        bk = ' '.join(l['text'][a:b] for a, b in l['back'])
        print(f"{l['i']:3d} {l['sec']:2d} {l['sec_name'][:10]:10s} {'S' if l['spoken'] else ' '} {nm:2d}+{nb:<2d} {ph}   {bk}")
    assert len(lines) == sum(len(s['lines']) for s in secs)
