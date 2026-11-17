"""Display model of the lyric sheet: every line as timing units that carry their own punctuation.

The sheet is the user's text (work/lyrics.txt, not committed). lyrics.parse() gives sections, lines and timing
units (one CJK character or one Latin word). For the screen each unit also carries the punctuation around it,
so the characters on screen are the sheet's characters and nothing else:

  pre   opening marks drawn before the unit      “ ( " …
  tok   the unit itself
  post  closing marks drawn after the unit       ！ ？ ” ) — 。 ：，、

A line is also cut into phrases at the sheet's own spaces (consecutive Latin words stay one phrase); the
layouts break rows at phrase boundaries. A unit inside ASCII parentheses is a response (backing vocal).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lyrics import CJK, parse  # noqa: E402

OPEN = '“‘(《「『…'
_cjk = re.compile(f'[{CJK}]')


def is_cjk(s):
    return bool(_cjk.match(s[0]))


def display_units(line):
    """[{tok, pre, post, cjk, resp, brk, phrase}] for one parsed line."""
    text = line['text']
    us = line['units']
    n = len(us)
    out = [{'tok': u[0], 'pre': '', 'post': '', 'cjk': is_cjk(u[0]), 'resp': False, 'brk': False} for u in us]
    quote_open = False
    depth = 0
    for k in range(n + 1):
        gap = text[(us[k - 1][2] if k else 0):(us[k][1] if k < n else len(text))]
        left = right = ''
        if re.search(r'\s', gap):
            m = re.match(r'^(\S*)\s+(.*?)\s*(\S*)$', gap, re.S)
            A, mid, B = m.group(1), ' '.join(m.group(2).split()), m.group(3)
            if not re.search(r'\s', gap[len(A):-len(B)] if B else gap[len(A):]):
                mid = ''
            left, right = A, B
            if mid:
                if k:
                    left = left + ' ' + mid
                else:
                    right = mid + ' ' + right
            if k == n and right:
                left, right = (left + ' ' + right).strip() if not A else left + ' ' + right, ''
                left = (' ' + left) if not left.startswith(' ') and not A else left
            quote_open ^= (gap.count('"') % 2 == 1)
            brk = True
        else:
            brk = False
            for ch in gap:
                opening = ch in OPEN or (ch == '"' and not quote_open)
                if ch == '"':
                    quote_open = not quote_open
                if right or (opening and k < n):
                    right += ch
                else:
                    left += ch
            if k == 0:
                left, right = '', left + right
            if k == n:
                left, right = left + right, ''
        if k:
            out[k - 1]['post'] = left
            depth -= left.count(')')
        if k < n:
            out[k]['pre'] = right
            out[k]['brk'] = brk and k > 0
            depth += right.count('(')
            out[k]['resp'] = depth > 0
    ph = 0
    for k, u in enumerate(out):
        if k:
            p = out[k - 1]
            if u['resp'] != p['resp']:
                ph += 1
            elif u['brk']:
                latin_run = (not u['cjk']) and (not p['cjk']) and not p['post'].strip(" ,.'’") and not u['pre']
                if not latin_run:
                    ph += 1
        u['phrase'] = ph
    return out


def load(path='work/lyrics.txt'):
    secs, lines = parse(path)
    for l in lines:
        l['du'] = display_units(l)
        shown = ''.join(u['pre'] + u['tok'] + u['post'] for u in l['du'])
        want = l['text']
        assert re.sub(r'\s', '', shown) == re.sub(r'\s', '', want), (l['i'], shown, want)
    return secs, lines


if __name__ == '__main__':
    secs, lines = load(sys.argv[1] if len(sys.argv) > 1 else 'work/lyrics.txt')
    for l in lines:
        ph = {}
        for u in l['du']:
            ph.setdefault(u['phrase'], []).append(('(' if u['resp'] else '') + u['pre'] + u['tok'] + u['post'])
        print(l['i'], l['sec_name'], ' | '.join(''.join(x if len(x) == 1 else x + ' ' for x in v).strip() for v in ph.values()))
