#!/usr/bin/env python3
"""Keyframes for 三十秒 (the summoner's-valley song) with gpt-image-2, medium, 1088x1920.

  keyframes.py [ID ...]     run the listed ids, or every keyframe that does not exist yet
  keyframes.py --force ID   regenerate (the old file is kept as ID.vN.png)

Every picture is an original fantasy world: no character, costume, emblem or place of an existing game or film is
named or described, and STYLE says so again. Nothing that moves (sparks, embers, sand in the air, snow, petals,
rain, confetti, light rays, flares) is painted: render.py draws them on the variable clock so they can stop in
the song's silences. Prompts never contain lyric text.

Two people recur: NEW (the newcomer, "you" in the song) and OLD (the teller). Their reference sheets REF_NEW and
REF_OLD are made first; every frame that shows them goes through the edits endpoint with the sheets attached.
Cost is logged to work/keyframes/usage.jsonl and generation stops at CAP. Rates assumed: text in $5/M, image in
$8/M, image out $30/M (gpt-image-2 list prices; not reconciled with the bill).
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
CAP = 7.00

STYLE = ('Cinematic digital matte painting, epic original high-fantasy concept art with photographic lighting and deep '
         'atmospheric perspective, rich detail, dusk-blue shadows, warm gold firelight and cool teal magical light, '
         'grounded and weighty rather than cute, vertical 9:16 composition with a calm uncluttered area in the upper-middle '
         'third. An original world: no character, costume, emblem, creature or place from any existing game, film or '
         'franchise. No text, no letters, no numbers, no runes, no glyphs, no symbols, no logos, no watermark, no user '
         'interface. Do not paint sparks, embers in the air, falling particles, snow in the air, blowing sand, petals, '
         'rain, confetti, light rays or lens flares; keep the air clear so they can be added in rendering.')

NEW = ('a young woman of about nineteen with a short dark chin-length bob haircut, wearing a light sand-colored hooded '
       'travel cloak with the hood down over a teal tunic, a brown leather belt and brown leather boots')
OLD = ('a tall man in his thirties in a long weathered charcoal-grey hooded cloak with the hood up, dark leather armor '
       'beneath, a small brass hourglass hanging at his belt')
NIGHT = ' Night under a clear starry sky, cool blue moonlight, faint teal glow from below.'
DUSK = ' Blue hour just after sunset: deep blue sky with a last band of warm gold along the horizon.'
DAWN = ' First light of dawn: warm golden sunrise light grazing in from a low angle, long shadows, cool blue in the shade.'
FIRE = ' Stormy night lit by distant fires: warm orange light from below, cold blue above.'
DAY = ' Bright high sun, crisp clean air, deep blue sky.'

REFS = {'new': ['REF_NEW'], 'old': ['REF_OLD'], 'both': ['REF_NEW', 'REF_OLD'], 'cup': ['K64']}
REFTXT = {
    'new': 'The reference image shows the young woman who appears in this picture: keep her hair, face, age and clothing exactly. ',
    'old': 'The reference image shows the man who appears in this picture: keep his cloak, armor and build exactly. ',
    'both': 'The first reference image shows the young woman and the second shows the man who appear in this picture: '
            'keep their hair, faces, ages and clothing exactly. ',
    'cup': 'The reference image shows the trophy: use exactly this handleless silver chalice with its teal inlay; it has no '
           'handles, no wings and nothing rising above its rim. ',
}
NOSTYLE = {'REF_NEW', 'REF_OLD'}
FIX = {
    # added after the first pass (first versions kept as Kxx.v1.png)
    'K76': ' Her face is not visible: she is a dark silhouette seen from below and slightly behind, against the bright sun.',
    'K77': ' The sphere of light is enormous and close, filling the whole upper half of the frame, the far fortress dissolving into it.',
    # after the independent review (work/qc/review): an extra arm, a sixth finger, a franchise-specific hair cue
    'K05': ' The man shows exactly two arms: the right arm points, the left arm stays hidden under his cloak.',
    'K37': ' Exactly two small child-sized hands cupped side by side, each with exactly five fingers.',
    'K56': ' The small younger girl has short messy hair, no braids; both girls are plain dark silhouettes.',
}

FRAMES = [
    ('REF_NEW', None, f'Character reference sheet: {NEW}. Full body from head to boots, standing, three-quarter view, on a plain '
     'light-grey background, soft even studio light, calm expression; her face clearly visible: oval face, dark brown eyes, '
     'straight dark eyebrows, short dark chin-length bob with a side part. Realistic painted concept art. No text.'),
    ('REF_OLD', None, f'Character reference sheet: {OLD}. Full body, standing, three-quarter view, on a plain light-grey background, '
     'soft even studio light; the hood is up so the upper face is in shadow, a short dark beard visible. Realistic painted '
     'concept art. No text.'),
    # ---- intro
    ('K01', None, 'Close view at night of a weathered stone ledge at the edge of a high cliff platform; on the ledge in the lower '
     'third of the frame stands a single brass hourglass with clear glass bulbs, all its sand resting in the bottom bulb; far '
     'below and behind it, a dark valley with a faint teal glow; a vast starry sky fills the upper half. No figures.' + NIGHT),
    ('K02', None, 'A breathtaking aerial establishing view of a wide forested valley between two mountain ranges, seen from high '
     'above at a 45-degree angle: three distinct dirt paths run from the near bottom of the frame to a distant fortress at the '
     'top, one along the left ridge, one straight up the middle, one along the right ridge, and one winding river cuts '
     'diagonally across the valley between them; at the bottom center a stone fortress plaza with a huge softly glowing teal '
     'crystal; at the far top a dark fortress with a small crimson crystal. Tiny scale, vast.' + DUSK),
    ('K03', 'old', 'Close-up of a man\'s hand in a dark leather glove turning a brass hourglass upside down on a rough stone ledge, '
     'the hourglass tilted mid-turn, the sand just beginning to run; exactly one hand; the edge of a charcoal-grey cloak sleeve; '
     'the hourglass in the center of the frame; behind it, far out of focus, the blue night valley.' + NIGHT),
    ('K04', 'both', f'Two people seen from behind sitting on a stone step beside a small campfire with a small black iron pot hanging '
     f'over it on a tripod, at the edge of a high cliff platform: on the left {OLD}; on the right {NEW}. Below them the vast '
     'forested valley; the people and the fire in the lower third, a large sky above.' + DUSK),
    ('K05', 'both', f'Over-the-shoulder view from behind {OLD}: his shoulder and outstretched arm in the left foreground, pointing '
     'toward a far horizon of countless lands (distant ice mountains, deserts, seas, the spires of cities); beside him on the '
     f'right, seen from behind, {NEW}, looking where he points. Both figures in the lower half; the horizon at mid height.' + DUSK),
    # ---- verse 1
    ('K06', None, 'A vast continent seen from very high altitude at night: mountain ranges, plains and coastlines, and cut deep into '
     'the mountains and plains, enormous ancient carved channels forming giant abstract geometric patterns kilometers wide, '
     'glowing faintly gold from within; the patterns are pure geometry with no readable symbols.' + NIGHT),
    ('K07', None, 'A stormy ocean at night: a single glowing gold stone the size of a house hovers in the upper third of the frame, '
     'and beneath it a colossal wave rears up into a towering wall of dark water reaching toward it; one tiny sailing ship '
     'below for scale.' + FIRE),
    ('K08', None, 'A single glowing gold standing stone on a lonely mountain summit at night; above it the stars blaze far brighter '
     'than normal, and one huge new star is igniting directly above the stone; the summit in the lower third, the sky huge.' + NIGHT),
    ('K09', None, 'Two enormous armies clash on a vast plain, seen from a high hill: thousands of dark silhouettes with spears and '
     'plain banners, the front lines meeting in the middle distance; the sky above torn by streaks of gold fire; no faces.' + FIRE),
    ('K10', None, 'The sky itself torn open: a jagged luminous crack runs across the upper half of a dark sky with white-gold light '
     'bleeding from it; below, a broken barren landscape; five large smooth stones, each a different color, float unused in the '
     'air near the crack; no figures.' + NIGHT),
    ('K11', None, 'A whole continent seen from near-orbit height at dusk, its regions plainly different: snowy north, golden desert '
     'south, green jungle, sea harbors, dark iron lands, bright mountains; coastlines and seas; seen from above with a slight '
     'tilt; no borders drawn.' + DUSK),
    ('K12', None, 'A vast frozen tundra of ice and blue glaciers under a pale green aurora, an ice fortress far away, a lone '
     'fur-cloaked rider small in the lower third.' + NIGHT),
    ('K13', None, 'An endless golden desert of dunes under a low blazing sun, colossal golden sandstone pillars half buried in the '
     'sand, a lone camel caravan small in the lower third.' + DAY),
    ('K14', None, 'A deep tropical rainforest canyon with giant trees, hanging vines and tall waterfalls, huge leaves in the '
     'foreground, ancient moss-covered stone steps leading up into the green.' + DAY),
    ('K15', None, 'A seafaring harbor town built up steep cliffs above turquoise water, tall-masted ships with patched sails moored '
     'at wooden piers, lanterns lit along the quays.' + DUSK),
    ('K16', None, 'On a far horizon, a row of colossal statues of different gods stand side by side, each hundreds of meters tall '
     'and each of a different kind: a horned beast god, a sun goddess, a robed sage, a frost giant, a sea serpent coiled upright; '
     'dark silhouettes against the sky, a plain in front.' + DUSK),
    ('K17', None, 'A long procession of hero silhouettes walking toward the camera along a ruined stone road out of a hazy distance, '
     'people from many different eras: knights in plate armor, a swordsman in a straw hat, a robed mage with a staff, an engineer '
     'with goggles and a brass mechanical arm, a tribal hunter with a spear, a cloaked archer; backlit so they are dark '
     'silhouettes with rim light; no faces visible.' + DUSK),
    ('K18', 'new', f'A great silent crowd of hero silhouettes from many eras stands waiting on the tiers of a vast stone amphitheater, '
     f'all facing the camera, their faces in shadow; in the lower foreground, seen from behind, {NEW} stands alone facing them, '
     'small.' + DUSK),
    # ---- pre-chorus 1
    ('K19', 'new', f'Medium close shot from behind {NEW}: her head and shoulders fill the lower third of the frame; beyond her, out of '
     'focus, a wall of tall shadowed hero figures looking down at her, their faces unreadable in shadow.' + DUSK),
    ('K20', 'new', 'Close-up of a young woman\'s open right hand, palm up, held out in front of her chest; a tiny point of teal light '
     'floats just above the palm and lights her fingers; her sand-colored cloak sleeve and teal tunic cuff; a dark background '
     'with a faint teal glow; exactly one hand with five fingers.' + NIGHT),
    ('K21', 'new', f'{NEW}, seen from behind, stands small at the bottom center of a vast circular stone plaza before an enormous '
     'faceted teal crystal three stories tall on a stone pedestal, the crystal in the upper-middle of the frame glowing softly '
     'from within; stars above.' + NIGHT),
    # ---- chorus 1
    ('K22', None, 'A directly top-down aerial view of a forested valley at night: three clear dirt paths run from the bottom of the '
     'frame to the top, one hugging the left edge, one straight through the middle, one hugging the right edge, and one river '
     'crosses diagonally from upper left to lower right, crossing the middle path at the center of the frame; at the bottom a '
     'small plaza with a teal glow, at the top a small plaza with a crimson glow; tiny scale, painted realistically.' + NIGHT),
    ('K23', None, 'Five heroes stand in a row facing the camera on a stone plaza, backlit by an enormous glowing teal crystal directly '
     'behind them that fills the upper half, so they are dark silhouettes with bright teal rim light and their faces are '
     'completely in shadow; five different silhouettes: a broad warrior with a large shield, a lean hunter with a spear, a mage '
     'with a tall staff, an archer with a bow, a guardian holding a lantern.' + NIGHT),
    ('K24', None, 'Looking across a dark valley from a hilltop: on the far side, on a black stone fortress, an enormous faceted '
     'crimson crystal glows red; the fortress in the upper-middle third; dark rocks in the foreground.' + NIGHT),
    ('K25', 'new', f'Low-angle view from behind {NEW} as she heaves a long heavy greatsword up onto her right shoulder, both hands '
     'on the hilt, standing on a stone step; above her the deep blue sky with stars; her figure fills the lower half; her face '
     'not visible.' + NIGHT),
    ('K26', None, 'Massive ancient stone fortress gates two stories tall swinging open outward from the center, warm gold light '
     'pouring through the widening gap onto a stone road; seen from outside at ground level, centered; five small dark '
     'silhouettes standing in the light of the opening.' + NIGHT),
    # ---- drop 1
    ('K27', None, 'A very high aerial view at night of the forested valley\'s three paths, with streams of tiny glowing figures '
     'pouring down all three paths from the bottom fortress toward the top, their light forming three bright lines.' + NIGHT),
    ('K28', None, 'Low angle at ground level: five heroes in silhouette running straight toward the camera down a dirt path, cloaks '
     'flying, backlit by a teal glow behind them; faces in shadow.' + NIGHT),
    ('K29', None, 'Low angle across a shallow river at night: a hero in silhouette splashing through the water mid-stride toward the '
     'camera, the splash frozen in the air, teal light behind; face in shadow.' + NIGHT),
    ('K30', None, 'A heavily armored warrior with a huge tower shield and a massive axe stands alone on a high cliff-top path at the '
     'left edge of a valley, seen from a low angle, face hidden behind a visor; the figure fills the middle of the frame.' + NIGHT),
    ('K31', None, 'A lean hunter in a dark leather hood crouches on a mossy branch in a dark jungle, holding a long spear, the glowing '
     'eyes of hidden beasts in the darkness around; the face hidden in hood shadow.' + NIGHT),
    ('K32', None, 'A mage in deep blue robes stands in the middle of a stone road, one hand raised with a sphere of violet-white '
     'arcane light gathering above the palm and lighting the road; seen from slightly behind and to the side; face not visible.' + NIGHT),
    ('K33', None, 'An archer stands on a high rock against a deep blue sky, a tall longbow held upright at her side with a single '
     'gold-glowing arrow, cloak blowing, looking out over the valley; side view in silhouette; face in shadow.' + NIGHT),
    ('K34', None, 'A guardian in white and gold robes holds up a lantern of warm gold light and a round shield, protecting a wounded '
     'companion kneeling behind; seen from the front, the face hidden in the shadow of a hood.' + NIGHT),
    ('K35', None, 'Along a dark mountain ridge at night, a row of five stone beacon towers each topped by a blazing fire, receding '
     'from near to far; seen from the side; the fires bright against the blue night.' + NIGHT),
    # ---- verse 2
    ('K36', None, 'A towering city wall of pure white stone, impossibly tall, filling most of the frame, long plain blue and gold '
     'banners without emblems hanging from it, a heavy gate at its base with tiny knights before it; severe and clean.' + DAY),
    ('K37', None, 'Close-up of a young girl\'s two small hands cupped together, hiding a brilliant white-gold light that leaks '
     'between her fingers; the edge of a dark blue cloak; behind, out of focus, the foot of a white stone wall in shadow; '
     'exactly two hands.' + DUSK),
    ('K38', None, 'A brutal black-iron fortress city of jagged spires under a blood-red sky; in the foreground a great sand arena '
     'where a lone warrior raises a huge axe, tiny silhouettes of crowds on the stands, plain crimson and black banners.' + FIRE),
    ('K39', None, 'A windswept mountain ridge with gnarled blossoming trees bent by strong wind; a lone wandering swordsman in a '
     'straw hat and a tattered robe walks away along the ridge path, a sheathed sword at his hip; seen from behind; misty peaks.' + DUSK),
    ('K40', None, 'A king in dark ornate armor and a crown stands at the prow of a warship, seen from behind, leading a fleet across '
     'a dark sea toward a radiant island glowing white on the horizon.' + NIGHT),
    ('K41', None, 'An island swallowed by a churning black-green mist, its white towers ruined and dark, an endless dead night with '
     'faint ghostly green light inside the mist; a broken crown lying on black sand in the foreground.' + NIGHT),
    ('K42', None, 'A colossal ancient desert temple of gold sandstone rising out of the dunes, crowned by a gigantic golden sun disc, '
     'its ruins emerging from the sand after thousands of years; a tiny figure at the top of the great steps, seen from far.' + DAY),
    ('K43', None, 'A single mountain peak so tall it pierces the clouds into the starry night; at the summit a lone climber seen from '
     'behind, tiny, reaches up as a brilliant star descends toward them.' + NIGHT),
    ('K44', None, 'On a snowy cliff ledge at night, a tiny round-eared furry creature no bigger than a cat, wearing an oversized hooded '
     'cloak, holds up a twig from which an enormous swirl of many-colored magic erupts, casting a gigantic shadow of the tiny '
     'creature on the cliff face behind it; an original creature design.' + NIGHT),
    ('K45', None, 'On the far side of the world the ground splits into a vast rift; inside it a deep violet void full of strange stars; '
     'the edges of the land crumble into it under a dark stormy sky; no creatures.' + NIGHT),
    # ---- pre-chorus 2
    ('K46', None, 'A towering wall in an ancient hall covered with hundreds of round carved stone medallions, each showing a different '
     'simple abstract emblem (a shield, a flame, a wing, an eye, a wave, a star), ten of them glowing gold; seen from below.' + NIGHT),
    ('K47', None, 'The Milky Way blazing over a dark forested valley at night, fine glowing lines connecting groups of stars into many '
     'overlapping constellations; seen from a cliff platform with a stone ledge in the foreground.' + NIGHT),
    # ---- chorus 2 (the same words, now in the battle at night)
    ('K49', None, 'Low angle at night: five heroes, silhouettes seen from behind, wade across a shallow river in the middle of a '
     'valley, torchlight reflecting on the water, the far bank dark with trees.' + FIRE),
    ('K50', None, 'One hero seen from behind in the foreground at the bottom of the frame looks back across the dark valley at a '
     'distant hill where a great teal crystal glows like a lighthouse in the upper-middle of the frame.' + FIRE),
    ('K51', None, 'Close view of an enormous crimson crystal on a black stone pedestal, deep cracks running through it with red-white '
     'light leaking out, about to break; seen from slightly below.' + FIRE),
    ('K52', 'new', f'Low-angle view of {NEW} from the side and slightly behind, a greatsword resting on her shoulder, her cloak blown '
     'by wind, her face turned away and in shadow, warm firelight on her from below, a stormy sky above.' + FIRE),
    ('K53', None, 'A night charge seen from behind the attackers: dozens of heroes in silhouette run down a slope toward a burning '
     'enemy fortress, plain banners streaming.' + FIRE),
    # ---- bridge
    ('K54', None, 'A gleaming upper city of brass and white marble towers with gigantic interlocking clockwork gears built into the '
     'buildings, glass bridges and airships, all in warm golden sunlight; seen from below looking up.' + DAY),
    ('K55', None, 'Beneath a wealthy city, a dark undercity of crowded shacks, pipes and walkways sunk in thick green toxic haze, lit by '
     'glowing neon tubes in pink, violet and acid green shaped only as abstract lines and circles; looking down into the depths.'),
    ('K56', None, 'In a narrow undercity alley glowing with green haze and pink neon, an older teenage girl with bandaged fists stands '
     'in a boxer\'s guard in front of a small younger girl, shielding her; both seen from behind as silhouettes against the glow.'),
    ('K57', None, 'Close-up of a small homemade contraption of copper wire, tin cans and a glowing blue crystal cell standing on '
     'a scrap workbench in a dim workshop, a small child\'s hand reaching toward it from the left; exactly one small hand.'),
    ('K58', None, 'A small girl stands alone at the edge of an undercity rooftop at night, seen from behind, her wild hair a dark '
     'silhouette in the wind, the neon undercity glowing pink and violet below and a golden city far above; lonely.'),
    ('K59', None, 'A vertical picture split at the middle: the golden sunlit upper city of brass towers in the top half, the dark '
     'neon-lit undercity in green haze in the bottom half, mirrored; at the seam two small figures stand back to back.'),
    # ---- verse 3
    ('K60', None, 'On an old wooden table at night: a worn hand-drawn paper map of a valley with three paths and a river, and around it '
     'a chessboard with carved pieces, a fanned deck of plain painted cards, a smartphone with a softly glowing blank screen, a '
     'small brass telescope; a window behind shows a starry sky; warm lamp light.'),
    ('K61', 'cup', 'An enormous indoor arena at night filled with tens of thousands of fans as tiny silhouettes holding up small lights, '
     'autumn maple-red light on the stands, and at the center on a tall pedestal in a pool of spotlight a tall silver chalice-shaped '
     'trophy of an original design.'),
    ('K62', None, 'A huge oval stadium of interwoven steel lattice like a giant bird\'s nest at night, packed with spectators, and a '
     'colossal translucent dragon made of blue-white light flying in over the stands, its wings spanning the stadium.'),
    ('K63', 'cup', 'A night city skyline of tall towers across a river; in the foreground, on a stage inside a glass-walled arena, five '
     'young players seen from behind lift a tall silver chalice-shaped trophy high above their heads together; silhouettes only.'),
    ('K64', None, 'Close-up of exactly ten hands, belonging to five people, gripping one tall silver chalice-shaped trophy together from '
     'all sides and raising it; dark background with warm stage lights.'),
    ('K65', None, 'The forested valley with three paths and a river seen from the cliff platform at sunrise: the sun rising over the far '
     'mountains, golden light flooding down the three paths, soft mist lying in the low parts of the valley.' + DAWN),
    ('K66', 'new', f'{NEW} seen from behind standing at the very edge of a cliff platform at sunrise, a brass hourglass held at her '
     'side, the golden sunrise before her over the forested valley; she is small in the lower third.' + DAWN),
    # ---- build-up
    ('K67', None, 'Extreme close-up of the surface of an enormous teal crystal: deep cracks run through it but it holds, brilliant '
     'teal light pulsing inside the fractures; dark background.' + NIGHT),
    ('K68', None, 'Extreme close-up of a brass hourglass on a stone ledge at night: the last few grains of sand slipping through the '
     'narrow neck, the top bulb almost empty; teal glow from the valley behind; the hourglass large in the center.' + NIGHT),
    # ---- final chorus
    ('K69', None, 'An aerial view of the forested valley at sunrise: five bright trails of gold light streak from the near fortress '
     'down the three paths and along the river; long shadows of trees; the far crimson fortress in the distance.' + DAWN),
    ('K70', 'new', f'{NEW} stands at the front and center of a line of five heroes facing the camera, the enormous teal crystal '
     'blazing behind them; strongly backlit, all faces in deep shadow, only silhouettes and teal rim light.' + DAWN),
    ('K71', None, 'An enormous crimson crystal at the top of a black fortress shattering into thousands of glowing red shards in a '
     'burst of white light, the shards frozen in mid-air at the moment of breaking.' + DAWN),
    ('K72', 'both', f'{NEW} stands at the very front on a high ridge at sunrise holding a tall banner of plain teal cloth with no emblem '
     f'streaming in the wind; behind her a vast army fills the slope; one step behind her shoulder stands {OLD}, smaller; seen from '
     'a low angle, her face turned toward the horizon and hidden by her hair.' + DAWN),
    ('K73', 'new', f'{NEW}, seen from behind at the front of an army on a ridge at sunrise, raises her greatsword high above her head, '
     'the rising sun bursting behind the blade.' + DAWN),
    # ---- drop 2
    ('K74', None, 'Ground-level view on a dirt path: a wave of heroes charges past the camera toward a distant enemy fortress at '
     'sunrise, cloaks and plain banners flying, warm gold backlight.' + DAWN),
    ('K75', None, 'Two champions clash in the middle of a river, weapons meeting in an explosion of gold and crimson light, water '
     'erupting around them; wide shot.' + DAWN),
    ('K76', 'new', f'{NEW} leaps high above a battlefield with her greatsword raised, seen from below against the sunrise sky, her '
     'cloak spread like wings.' + DAWN),
    # ---- outro
    ('K77', None, 'The enemy fortress at the far end of the valley: its great crimson crystal explodes into a gigantic sphere of '
     'white-gold light blasting outward and lighting the whole sky; seen from the middle of the valley.' + DAWN),
    ('K78', 'new', f'Medium close-up of {NEW} looking back over her shoulder toward the camera with a wide relieved smile, dust on her '
     'cheek, her face fully visible and lit warm gold from one side; a bright battlefield behind her out of focus.' + DAWN),
    ('K79', None, 'An old memory painted in faded warm sepia: years ago, a young boy sits beside a small campfire at the edge of a cliff '
     'platform above a valley, and beside him an old hooded mentor, seen from behind, points out over the valley; soft and '
     'slightly hazy like an old photograph.' + DUSK),
    ('K80', None, 'An empty stone seat beside a burnt-out campfire on a cliff platform at night: a ring of stones and charred wood with '
     'a few red embers still glowing in the ashes, a worn grey cloak folded on the seat, the valley far below.' + NIGHT),
    ('K81', 'new', f'Seen from behind: {NEW}, now wearing a long charcoal-grey hooded cloak with the hood down, sits on a stone step '
     'beside a small campfire and turns a brass hourglass upside down for a small boy in a plain brown tunic sitting beside her; '
     'both look out at the forested valley.' + DUSK),
]

lock = threading.Lock()


def cost(u):
    d = u.get('input_tokens_details', {})
    return (d.get('text_tokens', 0) * 5 + d.get('image_tokens', 0) * 8 + u.get('output_tokens', 0) * 30) / 1e6


def spent():
    p = f'{KF}/usage.jsonl'
    return sum(json.loads(l)['cost'] for l in open(p)) if os.path.exists(p) else 0.0


def post(url, fields, files):
    key = os.environ.get('OPENAI_API_KEY', 'sk-proxy')
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


def text_of(kid):
    for k, ref, prompt in FRAMES:
        if k == kid:
            return (REFTXT[ref] if ref else '') + prompt + FIX.get(kid, '') + ('' if kid in NOSTYLE else ' ' + STYLE)
    raise KeyError(kid)


def run(item):
    kid, ref, prompt = item
    out = f'{KF}/{kid}.png'
    with lock:
        if spent() > CAP:
            return f'{kid} skipped: cap reached'
    fields = {'model': MODEL, 'prompt': text_of(kid), 'size': SIZE, 'quality': QUALITY}
    d = None
    for attempt in range(4):
        if ref:
            req = post('https://api.openai.com/v1/images/edits', fields, [('image[]', f'{KF}/{r}.png') for r in REFS[ref]])
        else:
            req = post('https://api.openai.com/v1/images/generations', fields, None)
        try:
            with urllib.request.urlopen(req, timeout=480) as r:
                d = json.load(r)
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:400]
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                continue
            return f'{kid} HTTP {e.code} {msg}'
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
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
    os.makedirs(KF, exist_ok=True)
    args = sys.argv[1:]
    force = '--force' in args
    ids = [a for a in args if not a.startswith('--')]
    todo = [f for f in FRAMES if (f[0] in ids if ids else True) and (force or not os.path.exists(f'{KF}/{f[0]}.png'))]
    first = [f for f in todo if f[0] in NOSTYLE]
    rest = [f for f in todo if f[0] not in NOSTYLE]
    for batch in (first, rest):
        with ThreadPoolExecutor(8) as ex:
            for r in ex.map(run, batch):
                print(r, flush=True)
    print(f'spent so far ${spent():.2f}')
