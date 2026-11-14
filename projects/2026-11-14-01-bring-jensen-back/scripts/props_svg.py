#!/usr/bin/env python3
"""The film's props as hand-written SVG, rendered to transparent PNGs by render_svg.mjs (headless Chromium).

  props_svg.py && node scripts/render_svg.mjs work/assets/props

Sticker-pictogram style: flat fills, a thick ink outline, one or two highlight strokes. Nothing here depicts a
real person, logo or masthead. The recurring props come from the lyrics: the leather jacket left hanging
backstage, the empty chair, the diner mug that goes cold, candles and flowers, the chip, the paper boat.
"""
import os

OUT = 'work/assets/props'
os.makedirs(OUT, exist_ok=True)
INK = '#0b0b0c'
K = f'stroke="{INK}" stroke-linejoin="round" stroke-linecap="round"'

SVG = {}

SVG['jacket'] = (600, 780, f'''
<defs><linearGradient id="lg" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#2a2a2c"/><stop offset=".55" stop-color="#121213"/><stop offset="1" stop-color="#1c1c1e"/></linearGradient></defs>
<path d="M300 78 C300 52 300 40 312 30 C326 18 346 26 346 44 C346 60 330 62 326 54" fill="none" stroke="#c9c9c9" stroke-width="9" stroke-linecap="round"/>
<path d="M300 78 L118 168 L482 168 Z" fill="none" stroke="#c9c9c9" stroke-width="10" stroke-linejoin="round"/>
<path d="M150 160 C190 140 240 132 300 132 C360 132 410 140 450 160 L474 190 C486 300 500 470 512 640 L452 652 C444 520 436 420 428 330 L432 718 L168 718 L172 330 C164 420 156 520 148 652 L88 640 C100 470 114 300 126 190 Z" fill="url(#lg)" {K} stroke-width="11"/>
<path d="M232 136 L300 250 L270 330 L210 250 L196 160 Z" fill="#1d1d1f" {K} stroke-width="9"/>
<path d="M368 136 L300 250 L318 300 L392 238 L404 160 Z" fill="#1d1d1f" {K} stroke-width="9"/>
<path d="M300 250 L326 712" fill="none" stroke="#b9b9b9" stroke-width="6" stroke-dasharray="6 7"/>
<path d="M206 430 L262 404" stroke="#a9a9a9" stroke-width="6" fill="none"/>
<path d="M350 404 L404 430" stroke="#a9a9a9" stroke-width="6" fill="none"/>
<path d="M176 640 L424 640" stroke="#2d2d30" stroke-width="10"/>
<circle cx="214" cy="176" r="7" fill="#d0d0d0"/><circle cx="386" cy="176" r="7" fill="#d0d0d0"/>
<path d="M150 210 C142 330 132 470 122 600" stroke="#5a5a60" stroke-width="7" fill="none" opacity=".7"/>
<path d="M196 300 C192 420 190 560 190 690" stroke="#4a4a50" stroke-width="6" fill="none" opacity=".6"/>
<path d="M420 210 C430 300 440 420 452 560" stroke="#3c3c42" stroke-width="5" fill="none" opacity=".6"/>
''')

SVG['hanger'] = (600, 200, '''
<path d="M300 78 C300 52 300 40 312 30 C326 18 346 26 346 44 C346 60 330 62 326 54" fill="none" stroke="#c9c9c9" stroke-width="9" stroke-linecap="round"/>
<path d="M300 78 L118 168 L482 168 Z" fill="none" stroke="#c9c9c9" stroke-width="10" stroke-linejoin="round"/>
''')

SVG['chair'] = (520, 720, f'''
<rect x="128" y="30" width="264" height="300" rx="48" fill="#1b1b1d" {K} stroke-width="11"/>
<rect x="152" y="58" width="216" height="244" rx="34" fill="none" stroke="#3a3a3e" stroke-width="7"/>
<path d="M98 360 C98 340 120 332 140 332 L380 332 C400 332 422 340 422 360 L414 410 C410 424 398 430 384 430 L136 430 C122 430 110 424 106 410 Z" fill="#232326" {K} stroke-width="11"/>
<path d="M92 300 L92 372 M428 300 L428 372" stroke="{INK}" stroke-width="16"/>
<path d="M72 296 L118 296 M402 296 L448 296" stroke="#2c2c30" stroke-width="18" stroke-linecap="round"/>
<rect x="244" y="430" width="32" height="132" fill="#9a9aa0" {K} stroke-width="8"/>
<path d="M260 566 L84 616 M260 566 L170 650 M260 566 L350 650 M260 566 L436 616 M260 566 L260 632" stroke="#2a2a2e" stroke-width="20" stroke-linecap="round"/>
<g fill="#111" {K} stroke-width="6"><circle cx="84" cy="640" r="20"/><circle cx="170" cy="672" r="20"/><circle cx="350" cy="672" r="20"/><circle cx="436" cy="640" r="20"/><circle cx="260" cy="656" r="20"/></g>
''')

SVG['mug'] = (560, 460, f'''
<ellipse cx="270" cy="400" rx="250" ry="46" fill="#f3efe6" {K} stroke-width="10"/>
<ellipse cx="270" cy="392" rx="150" ry="22" fill="#e2dccf"/>
<path d="M118 112 L136 360 C140 384 170 396 270 396 C370 396 400 384 404 360 L422 112 Z" fill="#f6f2ea" {K} stroke-width="11"/>
<path d="M418 170 C500 166 512 300 404 316" fill="none" stroke="{INK}" stroke-width="34"/>
<path d="M418 170 C500 166 512 300 404 316" fill="none" stroke="#f6f2ea" stroke-width="16"/>
<ellipse cx="270" cy="112" rx="152" ry="30" fill="#f6f2ea" {K} stroke-width="11"/>
<ellipse cx="270" cy="116" rx="132" ry="21" fill="#3b2216"/>
<path d="M150 150 L164 340" stroke="#ffffff" stroke-width="12" stroke-linecap="round" opacity=".9"/>
<path d="M126 230 L414 230" stroke="#c8462f" stroke-width="16"/>
''')

SVG['boat'] = (640, 380, f'''
<path d="M40 210 L600 210 L500 350 L140 350 Z" fill="#f4efe4" {K} stroke-width="11"/>
<path d="M140 210 L320 30 L500 210 Z" fill="#ffffff" {K} stroke-width="11"/>
<path d="M320 30 L320 210" stroke="{INK}" stroke-width="7"/>
<path d="M160 260 L480 260" stroke="#d9d2c2" stroke-width="8"/>
''')

SVG['chip'] = (600, 600, f'''
<g stroke="#c9c9c9" stroke-width="14" stroke-linecap="round">
{''.join(f'<path d="M{x} 40 L{x} 110 M{x} 490 L{x} 560 M40 {x} L110 {x} M490 {x} L560 {x}"/>' for x in range(150, 470, 50))}
</g>
<rect x="100" y="100" width="400" height="400" rx="26" fill="#17181a" {K} stroke-width="12"/>
<rect x="180" y="180" width="240" height="240" rx="10" fill="#2a2c2e" stroke="#8cff3a" stroke-width="8"/>
<path d="M210 270 L390 270 M210 330 L390 330" stroke="#8cff3a" stroke-width="6" opacity=".55"/>
''')

SVG['card'] = (420, 600, f'''
<rect x="20" y="20" width="380" height="560" rx="34" fill="#f6f1e6" {K} stroke-width="12"/>
<rect x="56" y="56" width="308" height="488" rx="18" fill="none" stroke="#c8462f" stroke-width="8"/>
<path d="M210 170 C150 240 108 270 108 320 C108 360 150 384 190 362 C182 392 170 410 150 424 L270 424 C250 410 238 392 230 362 C270 384 312 360 312 320 C312 270 270 240 210 170 Z" fill="{INK}"/>
''')

SVG['candle'] = (180, 520, f'''
<path d="M90 30 C60 80 62 120 90 140 C118 120 120 80 90 30 Z" fill="#ffcf5a" {K} stroke-width="6"/>
<path d="M90 70 C80 96 82 118 90 128 C98 118 100 96 90 70 Z" fill="#fff6c8"/>
<path d="M90 140 L90 168" stroke="{INK}" stroke-width="6"/>
<rect x="40" y="164" width="100" height="340" rx="10" fill="#f4ecd8" {K} stroke-width="9"/>
<path d="M60 170 C60 200 72 214 72 240" stroke="#ffffff" stroke-width="8" fill="none" stroke-linecap="round"/>
''')

SVG['flowers'] = (520, 640, f'''
<g stroke="#2f6b1e" stroke-width="10" stroke-linecap="round"><path d="M260 380 L200 180 M260 380 L260 150 M260 380 L320 190 M260 380 L150 240 M260 380 L370 250"/></g>
{''.join(f'<g transform="translate({x} {y})"><g fill="#fbf7ee" {K} stroke-width="6">' + ''.join(f'<ellipse cx="0" cy="-30" rx="18" ry="30" transform="rotate({a})"/>' for a in range(0, 360, 60)) + f'</g><circle r="16" fill="#ffcf3a" {K} stroke-width="6"/></g>' for x, y in [(200, 170), (260, 130), (320, 180), (150, 235), (370, 245), (240, 230), (300, 250)])}
<path d="M130 330 L390 330 L300 620 L220 620 Z" fill="#e9e1cf" {K} stroke-width="10"/>
<path d="M170 340 L250 610" stroke="#cfc4ad" stroke-width="8"/>
''')

SVG['envelope'] = (600, 400, f'''
<rect x="20" y="20" width="560" height="360" rx="16" fill="#f6f1e6" {K} stroke-width="12"/>
<path d="M20 36 L300 230 L580 36" fill="none" stroke="{INK}" stroke-width="12" stroke-linejoin="round"/>
<path d="M20 370 L230 190 M580 370 L370 190" stroke="{INK}" stroke-width="8"/>
''')

SVG['lock'] = (420, 520, f'''
<path d="M110 230 L110 150 C110 40 310 40 310 150 L310 230" fill="none" stroke="#bdbdbd" stroke-width="44"/>
<path d="M110 230 L110 150 C110 40 310 40 310 150 L310 230" fill="none" stroke="{INK}" stroke-width="10" opacity=".35"/>
<rect x="40" y="220" width="340" height="280" rx="30" fill="#e8bf3a" {K} stroke-width="12"/>
<circle cx="210" cy="330" r="34" fill="{INK}"/><rect x="196" y="340" width="28" height="90" rx="10" fill="{INK}"/>
''')

SVG['heart'] = (420, 640, f'''
<path d="M210 20 L210 260" stroke="{INK}" stroke-width="6"/>
<path d="M210 600 C90 500 30 430 30 350 C30 280 80 240 130 240 C170 240 196 262 210 290 C224 262 250 240 290 240 C340 240 390 280 390 350 C390 430 330 500 210 600 Z" fill="#ff3b30" {K} stroke-width="12"/>
<path d="M100 330 C100 300 120 285 140 282" stroke="#ffb3ad" stroke-width="12" fill="none" stroke-linecap="round"/>
''')

SVG['scale'] = (640, 600, f'''
<path d="M320 60 L320 520 M200 540 L440 540" stroke="{INK}" stroke-width="18" stroke-linecap="round"/>
<path d="M90 140 L550 140" stroke="{INK}" stroke-width="16" stroke-linecap="round"/>
<circle cx="320" cy="60" r="22" fill="#e8bf3a" {K} stroke-width="8"/>
<path d="M90 140 L40 330 M90 140 L140 330 M550 140 L500 330 M550 140 L600 330" stroke="{INK}" stroke-width="6"/>
<path d="M20 330 C20 400 160 400 160 330 Z" fill="#e8bf3a" {K} stroke-width="10"/>
<path d="M480 330 C480 400 620 400 620 330 Z" fill="#e8bf3a" {K} stroke-width="10"/>
''')

SVG['gauge'] = (640, 420, f'''
<path d="M60 360 A260 260 0 0 1 580 360" fill="none" stroke="#2a2a2e" stroke-width="60"/>
<path d="M60 360 A260 260 0 0 1 452 135" fill="none" stroke="#8cff3a" stroke-width="44"/>
<path d="M452 135 A260 260 0 0 1 580 360" fill="none" stroke="#ff2b26" stroke-width="44"/>
<path d="M60 360 A260 260 0 0 1 580 360" fill="none" stroke="{INK}" stroke-width="8"/>
<circle cx="320" cy="360" r="34" fill="{INK}"/>
''')

SVG['phone'] = (420, 800, f'''
<rect x="20" y="20" width="380" height="760" rx="56" fill="#111214" {K} stroke-width="12"/>
<rect x="44" y="70" width="332" height="660" rx="22" fill="#f6f4ef"/>
<rect x="160" y="40" width="100" height="16" rx="8" fill="#2a2a2e"/>
''')

SVG['door'] = (440, 760, f'''
<rect x="20" y="20" width="400" height="720" rx="8" fill="#5a3b26" {K} stroke-width="12"/>
<rect x="70" y="70" width="300" height="270" rx="6" fill="none" stroke="#3b2618" stroke-width="10"/>
<rect x="70" y="390" width="300" height="300" rx="6" fill="none" stroke="#3b2618" stroke-width="10"/>
<circle cx="350" cy="380" r="22" fill="#e8bf3a" {K} stroke-width="7"/>
''')

SVG['folder'] = (640, 480, f'''
<path d="M30 70 L240 70 L280 30 L610 30 L610 450 L30 450 Z" fill="#d9b779" {K} stroke-width="12" stroke-linejoin="round"/>
<path d="M30 110 L610 110" stroke="#b8955a" stroke-width="8"/>
<rect x="90" y="170" width="460" height="230" fill="#f4efe4" {K} stroke-width="8" transform="rotate(-3 320 285)"/>
''')

SVG['halo'] = (520, 200, '''
<ellipse cx="260" cy="100" rx="230" ry="60" fill="none" stroke="#ffd84a" stroke-width="26"/>
''')

SVG['fist'] = (300, 520, f'''
<path d="M120 520 L120 300 L190 300 L190 520 Z" fill="{INK}"/>
<path d="M70 150 C70 100 100 80 130 86 C140 60 170 56 186 72 C204 56 236 62 240 92 C262 92 280 112 276 140 L270 250 C266 290 240 312 200 312 L120 312 C90 312 74 290 72 260 Z" fill="{INK}"/>
''')

for name, (w, h, body) in SVG.items():
    with open(f'{OUT}/{name}.svg', 'w') as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{body}</svg>')
print(len(SVG), 'svg written')
