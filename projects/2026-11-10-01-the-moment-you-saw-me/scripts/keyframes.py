#!/usr/bin/env python3
"""Generate the keyframes for "The Moment You Saw Me" with gpt-image-2.

  keyframes.py [ID ...]     run the listed ids, or every keyframe that does not exist yet
  keyframes.py --force ID   regenerate (the old file is kept as ID.vN.png)

No rain streaks are asked for in the air: the falling rain is drawn by render.py so it can move, slow down
and stop with the music. Cost is logged to work/keyframes/usage.jsonl and generation stops at the cap.
Rates assumed: text in $5/M, image in $8/M, image out $30/M (the higher of the two published sets).
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
CAP = 3.00

STYLE = ('Photorealistic still frame from a quiet contemporary Chinese romance film, shot on 35mm motion picture film '
         '(Kodak Vision3 500T), 50mm lens wide open, shallow depth of field, natural available light, fine organic grain, '
         'soft halation on highlights, restrained muted colour. Candid and unposed, emotionally understated, never glossy, '
         'not a stock photo, not an advertisement. Full-bleed vertical 9:16 frame edge to edge. No text, no readable signs, '
         'no logos, no watermark, no captions, no borders.')
NOSTREAK = ('Do not draw rain streaks or falling lines in the air: the rain shows only as wet surfaces, beads of water on '
            'things, ripples in puddles and a soft mist. ')
COOL = ('Light and colour: a heavily overcast rainy late afternoon, cool blue-grey and teal, low contrast, desaturated, '
        'no direct sunlight anywhere. ')
SUN = ('Light and colour: a sunshower. It is still raining, but low golden late-afternoon sun has broken through under the '
       'edge of the cloud and backlights everything: wet surfaces glow amber, water beads sparkle, warm gold highlights sit '
       'against cool blue-grey shadows. A few tiny out-of-focus golden bokeh sparkles of backlit droplets are welcome, but '
       'no long rain streaks. ')
SHE = ('The woman is Chinese, 26, with a soft oval face, almost no makeup, and shoulder-length black hair in a low loose '
       'ponytail with strands falling around her face. She wears an oversized cream knit cardigan over a white collared '
       'blouse, charcoal wide-leg trousers and black leather loafers, and has a black canvas tote bag. ')
HE = ('The man is Chinese, 27, tall and slim, with short black hair, in a dark navy coach jacket over a light grey hoodie, '
      'black trousers and grey sneakers. He holds a transparent clear vinyl umbrella with a white handle. ')
STEPS = ('Location: a flight of wide, worn grey stone steps beside an office building, under old plane trees, on a quiet '
         'side street in Shanghai. ')
REFS = {'she': 'REF_SHE', 'k01': 'K01', 'k07': 'K07', 'k08': 'K08', 'k16': 'K16', 'k27': 'K27', 'k32': 'K32'}
REFTXT = {
    'she': 'Image 1 is a portrait of the woman: keep exactly the same face, hair and cardigan. ',
    'k01': 'Image 1 shows this same window and room earlier, in the dark: keep the same window, the same framing and the same room. ',
    'k07': 'Image 1 shows this same desk, lamp and paper cup from another angle: keep the same desk, the same lamp and the same plain paper cup with a brown sleeve. ',
    'k08': 'Image 1 shows the same stone steps, trees and woman in a wider view: keep the same place and the same clothes. ',
    'k27': 'Image 1 shows the woman as she is in this scene, soaked by the rain: keep exactly the same face, the same wet hair stuck to her face, the same soaked cream cardigan and the same low golden light. ',
    'k32': 'Image 1 shows the same two people, the same street and the same golden light a few minutes earlier: keep the street, the clothes and the transparent umbrella. ',
    'k16': 'Image 1 shows the same steps, the same two people and the same sunshower light from across the street: keep the place, the clothes and the light. ',
}

# id, reference key or None, prompt
FRAMES = [
    ('REF_SHE', None, "Neutral character portrait, head and shoulders, three-quarter view, soft even window light, plain grey wall behind. " + SHE + "Her expression is calm and a little tired, lips closed, looking just past the camera. Sharp focus on the face."),

    # ---------------- first telling: what she hid (cool, close, enclosed)
    ('K01', None, "Night-blue dusk, inside a small dark rented apartment looking at a single window. The glass is covered in raindrops and slow rivulets, sharply in focus; beyond it the city is only soft blurred blue and a few dim amber lights. A plain curtain is drawn most of the way across, leaving the right two-thirds of the window uncovered. The room itself is almost black. Nobody in the frame. " + COOL),
    ('K02', None, "Inside a small dark rented apartment at dusk. A young woman sits on the floor with her back against the side of the bed, knees drawn up, arms around them, seen from behind and slightly to the side as a near-silhouette against a rain-covered window. Only a thin cold rim of window light on her hair, shoulder and the cream knit of her cardigan. Her face cannot be seen. The room is dark and quiet. " + COOL),
    ('K03', 'she', "Inside an office elevator with cold fluorescent light. Close-up of the mirrored elevator wall, with the soft out-of-focus back of the woman's shoulder and cardigan at the left edge of the frame. In the mirror we see her reflection from the bridge of the nose down to the collar: her mouth and chin sit in the middle of the frame, well below the top edge, as she puts on a small polite practised smile, lips closed, corners lifted just enough. Her eyes are cut off by the top edge of the frame. White blouse collar and cream cardigan. The smile is correct and empty. Brushed steel around the mirror. " + SHE),
    ('K04', None, "Inside the dark entry of a small rented apartment. Close-up of a woman's hand in a cream knit cardigan sleeve turning the thumb-turn lock of the front door from the inside. The door is almost shut: one last narrow vertical strip of warm corridor light falls across the door edge and her fingers. Everything else is in shadow. Nobody's face in the frame."),
    ('K05', None, "A small rented bedroom in near darkness, late at night, seen from the doorway. A young woman in a cream knit cardigan is curled up on the floor against the bed with her forehead on her knees, hair hiding her face. Around her the room is a quiet mess: crumpled sheets of paper on the floor, an open laptop throwing a faint cold glow, a cold mug, clothes over a chair. The curtain is closed except for one thin slit of blue light. " + COOL),
    ('K06', None, "A city bus stop in heavy rain, seen from behind the people waiting. Several strangers stand under dark umbrellas. At the left, a young woman in a soaked cream knit cardigan has no umbrella: she holds a black canvas tote bag over her head with both hands, shoulders hunched, seen from behind. Wet asphalt reflecting grey sky and red tail lights, a bus arriving as a soft blur. " + NOSTREAK + COOL),
    ('K07', None, "Late at night in an empty open-plan office, all lights off except one small desk lamp. A young woman in a cream knit cardigan has fallen asleep at her desk with her head on her folded arms, face turned away from the camera, low ponytail. In the near foreground at the edge of the desk stands a plain white paper cup with a brown cardboard sleeve, a thin thread of steam rising from it, in sharp focus. Behind her a dark window beaded with rain and blurred city lights. Papers and a closed laptop on the desk. No writing visible."),
    ('K08', None, STEPS + "Wide shot from across the street in steady rain. A young woman in a soaked cream knit cardigan sits alone halfway up the wet steps, small in the frame, hunched forward with her head down and her arms around her knees, a black tote bag beside her. Nobody else near her. Puddles on the steps, dark wet tree trunks, dripping leaves. " + NOSTREAK + COOL),
    ('K09', 'she', "Extreme close-up in profile of the woman sitting in the rain with her eyes closed and head slightly bowed. Soaked black hair clings to her temple and cheek, beads of water hang on her eyelashes and run down her skin, a little smudged mascara under the eye. The background is soft dark blurred plane trees. From behind and above, the very first thin warm golden rim of sunlight touches the wet edge of her hair, while her face is still in cool blue-grey shade. " + NOSTREAK),
    ('K10', None, "Looking straight down at a wet grey stone step, from the point of view of someone sitting with her head bowed. At the bottom of the frame, the toes of her black leather loafers, wet and shining. In front of them a shallow puddle on the stone. A pair of grey sneakers has just stepped up to the far edge of the puddle and stopped, toes pointing toward her; black trouser cuffs. Reflected in the puddle: the pale curve of a transparent umbrella held above and a patch of sky turning from grey to pale gold. Wet fallen plane-tree leaves. " + NOSTREAK),

    # chorus 1: the moment, from where she sits
    ('K11', None, STEPS + "Low angle point of view of someone sitting on the steps looking up. A tall young man in a dark navy coach jacket over a grey hoodie stands directly in front, leaning slightly forward, holding a transparent clear vinyl umbrella out over the camera so that its beaded canopy fills the top of the frame. Low golden sun has just broken through the cloud right behind his head: his face is lost in backlight and lens flare, only his outline, jacket and the hand on the white umbrella handle read clearly. " + SUN),
    ('K12', 'she', STEPS + "Close-up in profile: the woman, soaked, sitting on the steps, has just lifted her head and is looking up at someone standing out of frame. No smile, lips slightly parted, eyes wide and unguarded, mascara a little smudged, wet hair stuck to her cheek. Warm low sunlight falls across her wet cheek and eyelashes for the first time. The curved edge of a transparent umbrella, beaded with water, enters the top of the frame above her. " + SUN),
    ('K13', 'she', "Close-up: the woman, soaked, wipes her cheek clumsily with the back of her hand, the wet cuff of her cream knit cardigan pulled half over her palm. A faint grey smear of mascara on her knuckle. We see her hand, her wet cheek and jaw, and one eye looking down; she is not posing and not pretty about it. Warm backlight on the fuzz of the wet wool and on the drops falling from her hair. " + SUN),
    ('K14', None, STEPS + "Ground-level shot along one wet stone step, camera resting on the stone. In sharp focus in the foreground: two pairs of feet side by side. On the left, the feet and ankles of a seated woman in black leather loafers and charcoal trouser hems, heels on the step, toes turned slightly inward. Right beside them, the feet of a standing man in grey sneakers and black trousers, planted and still, pointing toward her. Every shoe has a foot and a leg in it; there are no empty shoes anywhere. In the soft out-of-focus background, the legs of several passers-by with dark umbrellas are walking away down the street. Sunlit puddle, wet plane-tree leaves. " + SUN),
    ('K15', 'k08', STEPS + "Seen from behind and a little above: the woman in the soaked cream cardigan and a tall young man in a dark navy coach jacket now sit side by side on the wet step, a hand's width of space between their shoulders. He holds a transparent clear umbrella tilted entirely over her side, so that his own far shoulder and sleeve are out in the rain and darkened with water. Neither looks at the other; both face the street. " + SUN),
    ('K16', 'k08', STEPS + "The same wide view from across the street as Image 1, but now the low sun has come out while it still rains. Two small figures sit side by side halfway up the steps under one transparent umbrella: the woman in the cream cardigan and a tall man in a dark navy jacket. The whole street glows: wet stone shining gold, plane-tree leaves glittering, long warm light through the mist, deep cool shadows. " + SUN),

    # interlude
    ('K17', None, "Looking straight up from underneath a transparent clear vinyl umbrella. The canopy fills the frame: eight thin white ribs radiating from the centre, the clear plastic covered in hundreds of round water beads, each one catching golden sunlight like a tiny lens. Through the plastic, soft and out of focus: plane-tree branches and a sky that is half warm gold cloud edge, half pale blue. " + SUN),
    ('K18', None, "Rainy blue dusk on a city street, looking up at an office building from the pavement. Almost every window is dark; one window on the fourth floor is lit warm, and in it the small silhouette of a woman sitting at a desk. In the near foreground, out of focus and seen from behind, the shoulder of a man in a dark navy jacket and the beaded edge of a transparent umbrella: he has stopped to look up at that window. Wet street, soft blurred lights. " + NOSTREAK + COOL),

    # ---------------- second telling: what he saw (same days, from where he stood)
    ('K19', 'she', "Inside an office elevator with cold fluorescent light, medium shot from the back corner. The woman stands near the brushed-steel doors, facing them, alone in the middle of the frame; she thinks nobody is looking, and the polite smile is gone: her face, seen softly in three-quarter view and dimly reflected in the steel door, is tired and far away, eyes lowered, tote bag held in both hands. In the near foreground at the right edge, large and out of focus, the dark navy shoulder and the back of the head of a man standing behind her. " + SHE),
    ('K20', None, "An office corridor, dim. A fire-escape door with a tall panel of frosted wired glass. Behind the frosted glass, blurred and pale: the shape of a woman in a cream cardigan sitting hunched on the concrete stairs, head in her hands. In the foreground, in focus, a man's hand in a dark navy jacket sleeve rests on the door's push bar without pushing; in his other hand, low in the frame, a plain white paper cup with a brown sleeve. Cold greenish light from the stairwell, quiet."),
    ('K21', 'k07', "Late at night in the same empty open-plan office, one desk lamp on. Close shot: a man's hand in a dark navy jacket sleeve is gently setting down a steaming plain white paper cup with a brown cardboard sleeve at the edge of the desk. Just behind, soft and out of focus, the woman in the cream cardigan asleep with her head on her folded arms, face turned away. He is careful not to wake her. Rain-beaded dark window and blurred city lights behind."),
    ('K22', None, "The same city bus stop in heavy rain, seen from behind and from a little further back. At the left, the young woman in the soaked cream knit cardigan holds her black tote bag over her head. One step to her right stands a tall young man in a dark navy coach jacket, seen from behind, holding a transparent clear umbrella; his arm is stretched a little toward her so the umbrella's edge reaches halfway into the gap between them, not quite covering her. He looks straight ahead. Strangers under dark umbrellas, wet asphalt, a bus arriving as a soft blur. " + NOSTREAK + COOL),
    ('K23', None, "Rainy night, shot from the street through the wet window of a small convenience store. Inside, at the narrow counter along the window, two people sit two stools apart, both facing out toward the rain: at the left the young woman in the cream knit cardigan eating a cup of instant noodles, eyes down; at the right a tall young man in a dark navy coach jacket with a paper cup, a folded transparent umbrella leaning against his stool. They are not looking at each other. Warm store light inside, cool blue street reflections and water beads on the glass. Packaging and shelves have no writing. " + NOSTREAK),
    ('K24', 'k08', STEPS + "Point of view of a man who has stopped on the pavement in the rain. In the near foreground, out of focus: his hand on the white handle of a transparent umbrella and the beaded curve of its edge across the top of the frame. In the distance, in focus, the woman in the soaked cream cardigan sits alone on the wet steps with her head down, small. A few passers-by with dark umbrellas hurry past between them without looking. " + NOSTREAK + COOL),
    ('K25', None, STEPS + "From behind: a tall young man in a dark navy coach jacket walks toward the steps holding a transparent umbrella, mid-stride, seen from the back at waist height. Ahead of him, soft and small, a figure in a cream cardigan sits hunched on the steps. Above the rooftops the cloud is splitting open and the first low gold sunlight spills through, rim-lighting his shoulders and the wet umbrella while the street is still blue-grey. " + NOSTREAK),
    ('K26', None, "High angle looking down through a transparent clear vinyl umbrella. The clear plastic, covered in water beads and with thin white ribs, fills the frame in sharp focus. Through it, slightly soft: the bowed head, low ponytail and hunched shoulders of a woman in a soaked cream cardigan sitting on wet grey stone steps, her face hidden. A man's hand in a navy sleeve holds the white handle at the bottom edge of the frame. The beads on the plastic are beginning to catch warm gold light. " + NOSTREAK),

    # chorus 2: the same moment, from where he stands
    ('K27', 'she', STEPS + "Close-up from slightly above, the point of view of someone standing over her with an umbrella. The woman, soaked, sitting on the steps, looks straight up into the camera. Her whole face is seen clearly for the first time: no smile, no composure, eyes red-rimmed and shining, a tear line mixed with rain on her cheek, mascara slightly smudged, wet black hair stuck to her forehead and cheek. She is not hiding. Warm low sunlight on her wet face. The beaded curved rim of a transparent umbrella, out of focus, frames the top and one side of the picture. " + SUN),
    ('K28', 'she', "Extreme close-up of the woman's eyes and the bridge of her nose, looking up into the camera. Wet lashes clumped with rain, red-rimmed eyelids, a single tear gathering at the lower lid, warm gold sunlight reflected as a small bright point in each dark iris. A wet strand of black hair crosses her brow. Skin texture real and unretouched. " + SUN),
    ('K29', 'she', "Close-up of the lower half of the woman's face, from the nose down, in three-quarter view: wet hair stuck to her cheek, a raindrop on her lip, and the very beginning of a real smile, small, crooked and a little embarrassed, nothing like a polite one. Her chin is slightly crumpled as if she might also cry. The wet collar of a white blouse and cream cardigan. Warm backlight glowing in the wet strands of hair. " + SUN),
    ('K30', None, "Close-up of hands under a transparent umbrella in a sunshower. A man's hand in a dark navy jacket sleeve holds out a plain white paper cup with a brown cardboard sleeve, steam rising from it and glowing in the backlight. A woman's two hands, the wet cuffs of a cream knit cardigan pulled over her palms, are just closing around the cup to take it; their fingers do not quite touch. Wet grey stone steps soft behind. " + SUN),
    ('K31', 'k27', STEPS + "Medium shot from the front and slightly below: the woman and a tall young man in a dark navy coach jacket sit side by side on the wet steps under one transparent umbrella, which he holds between them, a small gap between their shoulders. She is still soaked: wet hair stuck to her cheek, the cardigan dark with water, black leather loafers. She holds a white paper cup with a brown sleeve in both hands near her chin and looks out at the rain, eyes still red, with the smallest tired real smile. He looks out at the street the same way, his face turned mostly away from the camera and soft in focus, one shoulder of his jacket wet. Neither looks at the other. It is still raining around them. Unglamorous, quiet, not posed. " + SUN),
    ('K32', 'k16', STEPS + "From behind the two of them, at their shoulder height, looking out from the steps at the street: the backs of the woman in the cream cardigan and the man in the dark navy jacket sitting close under one transparent umbrella, soft and dark in the foreground, and beyond them the whole wet street blazing in low gold sunlight while it rains, plane-tree leaves glittering, mist glowing, the far end of the street dissolving into light. The brightest, warmest image of the film. " + SUN),

    # outro
    ('K33', 'k32', "The rain is almost over. Long shot from behind, low to the ground: the woman in the cream cardigan and the tall man in the dark navy jacket walk away down the middle of the wet plane-tree street side by side, small in the frame, a small gap between their shoulders. He carries the transparent umbrella, now tilted back and half lowered. Their two long reflections stretch toward the camera on the shining wet paving, which fills the lower half of the frame. Clearing sky, soft pale gold and blue light after rain, a few last drops, fallen plane-tree leaves on the ground."),
    ('K34', 'k01', "The same window, the same framing, the next morning. The curtain is now drawn fully open and the window stands slightly ajar. Clear soft morning sunlight comes through the glass; the last raindrops on the pane each hold a small point of gold light. The room is visible now and has been tidied a little. On the floor beneath the window a transparent clear vinyl umbrella stands open to dry, water beads on it catching the light, and two paper cups with brown sleeves sit side by side on the windowsill. Nobody in the frame. Warm, calm, clean light."),
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
    text = (REFTXT[ref] if ref else '') + prompt + ' ' + STYLE
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
