#!/usr/bin/env python3
"""Keyframes for 别回答 (coldwave version) with gpt-image-2, medium, 1088x1920.

  keyframes.py [ID ...]     run the listed ids, or every keyframe that does not exist yet
  keyframes.py --force ID   regenerate (the old file is kept as ID.vN.png)

Prompts are the user's design verbatim; STYLE is appended to every prompt except K21 and K26. Nothing that moves
(light beams, fog, snow, dust, flares) is painted: render.py draws them so they can follow the music.
K03 goes through the edits endpoint with K02 as the reference. Cost is logged to work/keyframes/usage.jsonl and
generation stops at CAP. Rates assumed: text in $5/M, image in $8/M, image out $30/M.
"""
import base64
import json
import mimetypes
import os
import sys
import threading
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

KF = 'work/keyframes'
MODEL, SIZE, QUALITY = 'gpt-image-2', '1088x1920', 'medium'
CAP = 1.70

STYLE = ('Black-and-white 16mm film still, cold neutral tone, full tonal detail in the shadows, soft even ambient light as '
         'under a heavy overcast night sky, brutalist concrete and steel, stark minimal composition with strong vertical lines, '
         'austere and unposed, not a fashion photo, not an advertisement, vertical 9:16. Monochrome only. No text, no letters, '
         'no numbers, no signs, no logos, no watermark; all dials and panels are unmarked. Do not paint light beams, light rays, '
         'drifting fog, falling snow, dust or lens flares; keep the air clear so that light and fog can be added in rendering.')

REFS = {'k02': 'K02'}
REFTXT = {'k02': 'The reference image shows this same radar station; keep the dish, its concrete tower and the lattice masts exactly as they are there. '}
NOSTYLE = {'K21', 'K26'}
# Added after the first pass, appended to the user's prompt (the first versions are kept as Kxx.v1.png):
# STYLE's "brutalist concrete" put buildings into scenes that have none, K18 drew a literal mirror, K22 drew a room.
FIX = {
    'K06': ' Only open land and sky: no buildings, towers, walls, stairs or structures of any kind anywhere in the frame. All three sun discs are clearly visible.',
    'K07': ' Only the land, the sky and the lights: no buildings, towers or structures anywhere in the frame; the lights are thousands of separate tiny points, not a single streak.',
    'K12': ' It floats free with nothing holding it: no string, no wire, no buildings or structures; only empty black space around it.',
    'K13': ' Only trees and the man: no buildings, towers, monoliths or structures anywhere in the forest.',
    'K18': ' Her position mirrors, as a composition, a figure who stood left of center in another shot: there is exactly one person in this frame, no mirror and no reflection, and the wall of round lamps fills the background behind her.',
    'K22': ' Seen from directly above and close: the glass plate fills most of the frame; no telescope, no room, no buildings in view.',
}

FRAMES = [
    ('K01', None, "A bare board-marked concrete wall at night filling the lower two thirds of the frame, a strip of snow at its foot, and above the wall a low heavy overcast sky filling the upper third; nothing else."),
    ('K02', None, "A brutalist concrete radar station on a snow-covered summit: one giant parabolic dish on a concrete tower in the upper half, lattice antenna masts beside it, and a small woman in a long padded coat seen from behind at the foot of the tower, standing left of center."),
    ('K03', 'k02', "The same dish seen from behind and below, aimed at a pale flat sun disc veiled by fog, the disc exactly on the dish's axis; the masts as black verticals at the edge."),
    ('K04', None, "A cramped listening room: a woman seen from behind wearing large headphones, sitting at a wall of shortwave receivers with round dials and toggle switches, a reel-to-reel recorder at the side; her back and shoulders fill the lower half of the frame."),
    ('K05', None, "Close-up of one bare finger resting on the knob of a brass telegraph key bolted to a scarred wooden desk, not yet pressing; exactly one hand; the key in the center of the frame."),
    ('K06', None, "Three pale flat sun discs of different sizes at chaotic heights in a white fogged sky above a black volcanic plain; the left half of the plain cracked and hot, the right half sheeted in ice; no figures; horizon at 60 percent height."),
    ('K07', None, "A long diagonal column of thousands of small white lights rising from a black horizon into a dark sky, like an exodus seen from very far away; three faint discs low at the edge."),
    ('K08', None, "An empty university lecture hall with tiered wooden benches and three huge blackboards wiped blank, only chalk smears left; one tiny brilliant point of light hanging in the air in front of the middle board."),
    ('K09', None, "A vast empty concrete plaza seen from high above at a steep angle, one small figure standing alone near the bottom of the frame, expansion joints running in a grid across the slabs; no other objects."),
    ('K10', None, "Macro view of a single pale moth resting on the thick glass lens of a large searchlight, the filament dim behind the glass; the moth in the lower third."),
    ('K11', None, "Thousands of identical dark slab-like warships in rigid ranks receding to a vanishing point in black space, each with one small white running light, the ranks as regular as the windows of a housing block; seen from slightly below."),
    ('K12', None, "A flawless mirror-surfaced teardrop-shaped object hanging in black space, reflecting ranks of small white lights in perfect distortion; small, slightly above the center."),
    ('K13', None, "A pine forest at night in dense fog, black trunks receding into grey, a man in a long dark coat seen from behind standing small at the bottom center; no light source anywhere."),
    ('K14', None, "A man in a long coat seen from behind standing before a field of tall lattice radio masts in fog, one hand pressed to his chest, the masts towering into the upper two thirds."),
    ('K15', None, "A brutalist housing estate at night: three long concrete apartment slabs with hundreds of lit windows, laundry on the balconies, a few tiny figures at the windows; clear air between the blocks."),
    ('K16', None, "Two concrete watchtowers facing each other across a flat snow-covered no-man's-land with a low fence between them, each tower carrying one large searchlight aimed at the other; strictly symmetrical."),
    ('K17', None, "Close-up of exactly two hands over a small steel switch box with a single guarded toggle: an old veined hand letting go on the left, a young woman's hand receiving it on the right; plain concrete background."),
    ('K18', None, "A young woman in a long coat seen from behind, standing right of center before a wall of round alarm lamps, the switch box held low in her open hand with her thumb lifted away from the toggle; the mirror image of a woman standing left of center."),
    ('K19', None, "A single lattice radio mast on a dark hill at the lower left; in the sky at the upper right three small pale discs close together."),
    ('K20', None, "One small blank sheet of white photographic paper falling through darkness, slightly curled, lit softly from above; nothing else in the frame."),
    ('K21', None, "A cyanotype photogram on a sheet of paper seen face-on and filling the frame: flat white soft-edged silhouettes on deep Prussian blue \u2014 one large disc with concentric rings, smaller discs of several sizes, wavy bands like a sea, a radar dish, pine branches, a moth and small human profiles \u2014 everything with zero depth, overlapping like objects laid on the paper; rough brushed emulsion edges at the paper border. No text, no letters, no watermark."),
    ('K22', None, "An astronomical glass plate negative lying on a lightbox: hundreds of tiny black star dots on a pale ground, one star ringed with a grease-pencil circle; a young man's thin hand resting at the edge; exactly one hand; no writing."),
    ('K23', None, "A tiny capsule towed on fine threads by an enormous thin sail, both backlit as silhouettes with bright rims, alone in black space; the sail in the upper half."),
    ('K24', None, "A long-exposure night photograph: star trails as concentric circles around one fixed star above a flat shoreline, a single figure seen from behind standing small at the water's edge."),
    ('K25', None, "A tiny whitewashed cottage with one lit window alone in a wide snowfield at night, a single bare tree beside it; the cottage in the lower third, heavy overcast sky above."),
    ('K26', None, "A round glass fishbowl on a bare concrete windowsill at night lit by one small lamp, one small goldfish inside, a sealed glass bottle and a folded letter beside it; a black-and-white 16mm film still in which the only colored element is the orange goldfish. No text, no letters, no watermark."),
]

lock = threading.Lock()


def cost(u):
    d = u.get('input_tokens_details', {})
    return (d.get('text_tokens', 0) * 5 + d.get('image_tokens', 0) * 8 + u.get('output_tokens', 0) * 30) / 1e6


def spent():
    p = f'{KF}/usage.jsonl'
    return sum(json.loads(l)['cost'] for l in open(p)) if os.path.exists(p) else 0.0


def post(url, fields, files):
    key = os.environ['OPENAI_API_KEY']
    if not files:
        return urllib.request.Request(url, json.dumps(fields).encode(), {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    b = uuid.uuid4().hex
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    for k, path in files:
        ctype = mimetypes.guess_type(path)[0] or 'image/png'
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{os.path.basename(path)}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
                     + open(path, 'rb').read() + b'\r\n')
    parts.append(f'--{b}--\r\n'.encode())
    return urllib.request.Request(url, b''.join(parts), {'Authorization': f'Bearer {key}', 'Content-Type': f'multipart/form-data; boundary={b}'})


def run(item):
    kid, ref, prompt = item
    out = f'{KF}/{kid}.png'
    with lock:
        if spent() > CAP:
            return f'{kid} skipped: cap reached'
    text = (REFTXT[ref] if ref else '') + prompt + FIX.get(kid, '') + ('' if kid in NOSTYLE else ' ' + STYLE)
    fields = {'model': MODEL, 'prompt': text, 'size': SIZE, 'quality': QUALITY}
    if ref:
        req = post('https://api.openai.com/v1/images/edits', fields, [('image[]', f'{KF}/{REFS[ref]}.png')])
    else:
        req = post('https://api.openai.com/v1/images/generations', fields, None)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=420) as r:
                d = json.load(r)
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:400]
            if e.code in (429, 500, 502, 503) and attempt < 2:
                continue
            return f'{kid} HTTP {e.code} {msg}'
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                return f'{kid} failed {e}'
    if os.path.exists(out):
        n = 1
        while os.path.exists(f'{KF}/{kid}.v{n}.png'):
            n += 1
        os.replace(out, f'{KF}/{kid}.v{n}.png')
    open(out, 'wb').write(base64.b64decode(d['data'][0]['b64_json']))
    c = cost(d.get('usage', {}))
    with lock:
        open(f'{KF}/usage.jsonl', 'a').write(json.dumps({'id': kid, 'cost': round(c, 4), 'usage': d.get('usage')}) + '\n')
    return f'{kid} ok ${c:.3f}'


if __name__ == '__main__':
    args = sys.argv[1:]
    force = '--force' in args
    ids = [a for a in args if not a.startswith('--')]
    todo = [f for f in FRAMES if (f[0] in ids if ids else True) and (force or not os.path.exists(f'{KF}/{f[0]}.png'))]
    # references must exist before the frames that use them
    first = [f for f in todo if f[0] in REFS.values()]
    rest = [f for f in todo if f[0] not in REFS.values()]
    for batch in (first, rest):
        with ThreadPoolExecutor(6) as ex:
            for r in ex.map(run, batch):
                print(r, flush=True)
    print(f'spent so far ${spent():.2f}')
