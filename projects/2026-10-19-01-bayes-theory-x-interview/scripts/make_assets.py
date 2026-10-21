# -*- coding: utf-8 -*-
"""Render all static overlay PNGs for the edit (paper style matched to 非常贝叶斯.mp4)."""
import os, re, sys, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets"
os.makedirs(OUT, exist_ok=True)
W, H = C.W, C.H

# ---------------------------------------------------------------- palette (sampled from the theory video)
PAPER = (232, 227, 211)
DOT = (205, 200, 183)
CARD = (245, 240, 228)
INK = (38, 32, 24)
INK2 = (104, 96, 82)
ORANGE = (214, 98, 43)
ORANGE_D = (176, 74, 28)
TEAL = (16, 158, 188)
TEAL_D = (6, 128, 158)
WHITE = (255, 255, 255)

CJK_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
CJK_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
LATO = "/usr/share/fonts/truetype/lato/"
SERIF_I = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf" if os.path.exists("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf") else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"

_fc = {}
def F(kind, size):
    key = (kind, size)
    if key not in _fc:
        if kind == "zb": _fc[key] = ImageFont.truetype(CJK_B, size, index=2)
        elif kind == "zr": _fc[key] = ImageFont.truetype(CJK_R, size, index=2)
        elif kind == "eb": _fc[key] = ImageFont.truetype(LATO + "Lato-Bold.ttf", size)
        elif kind == "eh": _fc[key] = ImageFont.truetype(LATO + "Lato-Heavy.ttf", size)
        elif kind == "er": _fc[key] = ImageFont.truetype(LATO + "Lato-Medium.ttf", size)
        elif kind == "ei": _fc[key] = ImageFont.truetype(LATO + "Lato-MediumItalic.ttf", size)
        elif kind == "si": _fc[key] = ImageFont.truetype(SERIF_I, size)
    return _fc[key]

# ---------------------------------------------------------------- rich text layout
NO_START = set("，。、；：！？）」』”’》〉…—,.;:!?)%")
NO_END = set("“‘（《「『(")
def tokens(text):
    # ASCII words stay whole; short quoted / bracketed CJK spans stay whole; other CJK chars split
    out = []
    for m in re.finditer(r"“[^”]{1,6}”|（[^）]{1,4}）|[A-Za-z0-9'’\-\(\)\.,!?:;%θ|∝·/&]+|\s+|.", text):
        out.append(m.group(0))
    return out

def layout(runs, max_w):
    """runs: list of (text, font, color). returns list of lines, each a list of (tok, font, color, width)."""
    toks = []
    for text, font, color in runs:
        for t in tokens(text):
            toks.append((t, font, color, font.getlength(t)))
    lines, cur, cw = [], [], 0.0
    for tk in toks:
        t, f, c, w = tk
        if t.isspace() and not cur:
            continue
        if cw + w > max_w and cur and not t.isspace():
            carry = []
            if t[0] in NO_START and len(cur) > 1:   # closing punct can't start a line: carry previous token
                carry.insert(0, cur.pop())
            while len(cur) > 1 and (cur[-1][0].isspace() or cur[-1][0][-1] in NO_END):
                tok = cur.pop()
                if not tok[0].isspace(): carry.insert(0, tok)
            lines.append(cur)
            cur = carry; cw = sum(x[3] for x in cur)
        cur.append(tk); cw += w
    while cur and cur[-1][0].isspace():
        cur.pop()
    if cur: lines.append(cur)
    return lines

def line_w(line): return sum(t[3] for t in line)

def draw_lines(d, lines, x, y, line_h, align="left", box_w=None, ascent=None):
    """y = top of first line box. baseline placed at y + ascent."""
    for i, line in enumerate(lines):
        lw = line_w(line)
        xx = x if align == "left" else x + (box_w - lw) / 2
        by = y + i * line_h + ascent
        for t, f, c, w in line:
            d.text((xx, by), t, font=f, fill=c, anchor="ls")
            xx += w

def rich(text, base_font, base_color, hi_font=None, hi_color=None, phrases=(), brace=False):
    """Split text into runs; highlight given phrases or {braced} spans."""
    hi_font = hi_font or base_font; hi_color = hi_color or base_color
    if brace:
        runs = []
        for part in re.split(r"(\{[^}]*\})", text):
            if not part: continue
            if part.startswith("{"): runs.append((part[1:-1], hi_font, hi_color))
            else: runs.append((part, base_font, base_color))
        return runs
    if not phrases:
        return [(text, base_font, base_color)]
    pat = "(" + "|".join(re.escape(p) for p in sorted(phrases, key=len, reverse=True)) + ")"
    runs = []
    for part in re.split(pat, text):
        if not part: continue
        if part in phrases: runs.append((part, hi_font, hi_color))
        else: runs.append((part, base_font, base_color))
    return runs

# ---------------------------------------------------------------- primitives
def paper_bg(seed=7):
    rng = np.random.default_rng(seed)
    base = np.ones((H, W, 3), np.float32) * np.array(PAPER, np.float32)
    # low-frequency mottling + fine grain
    low = rng.normal(0, 1, (H // 24 + 1, W // 24 + 1)).astype(np.float32)
    low = np.array(Image.fromarray(((low * 30) + 128).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) - 128
    grain = rng.normal(0, 1.6, (H, W)).astype(np.float32)
    base += (low * 0.045 + grain)[..., None]
    img = Image.fromarray(base.clip(0, 255).astype(np.uint8))
    # dot grid (2x supersampled)
    S = 2
    dots = Image.new("L", (W * S, H * S), 0)
    dd = ImageDraw.Draw(dots)
    dx, dy = 69.5, 66.8
    r = 2.4 * S
    y = 37.0
    while y < H:
        x = 45.0
        while x < W:
            cx, cy = x * S, y * S
            dd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
            x += dx
        y += dy
    dots = dots.resize((W, H), Image.LANCZOS)
    img.paste(Image.new("RGB", (W, H), DOT), (0, 0), dots.point(lambda v: int(v * 0.85)))
    # sparse fibres
    fib = Image.new("RGBA", (W, H), (0, 0, 0, 0)); fd = ImageDraw.Draw(fib)
    for _ in range(260):
        x0, y0 = rng.uniform(0, W), rng.uniform(0, H)
        a = rng.uniform(0, math.pi); L = rng.uniform(6, 22)
        col = (205, 160, 120, int(rng.uniform(25, 60))) if rng.random() < 0.5 else (190, 186, 170, int(rng.uniform(30, 70)))
        fd.line((x0, y0, x0 + L * math.cos(a), y0 + L * math.sin(a)), fill=col, width=1)
    img = Image.alpha_composite(img.convert("RGBA"), fib)
    return img

def shadow_rect(canvas, box, radius, blur=14, offset=(0, 8), alpha=70):
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((box[0] + offset[0], box[1] + offset[1], box[2] + offset[0], box[3] + offset[1]), radius, fill=(60, 45, 25, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(sh)

def pill(d, x, y, text, font, fg, bg, padx=22, h=None):
    tw = font.getlength(text)
    asc, desc = font.getmetrics()
    h = h or (asc + desc + 14)
    d.rounded_rectangle((x, y, x + tw + 2 * padx, y + h), h // 2, fill=bg)
    d.text((x + padx, y + h / 2), text, font=font, fill=fg, anchor="lm")
    return x + tw + 2 * padx

def tape(canvas, cx, cy, ang, w=170, h=46):
    t = Image.new("RGBA", (w, h), (248, 240, 214, 225))
    td = ImageDraw.Draw(t)
    for i in range(0, w, 6):   # torn edges
        td.rectangle((i, 0, i + 2, random.randint(0, 3)), fill=(0, 0, 0, 0))
        td.rectangle((i, h - random.randint(0, 3), i + 2, h), fill=(0, 0, 0, 0))
    t = t.rotate(ang, expand=True, resample=Image.BICUBIC)
    canvas.alpha_composite(t, (int(cx - t.width / 2), int(cy - t.height / 2)))

# ---------------------------------------------------------------- evidence screens
PX, PY, PW, PH = C.PANEL
CAP_BOX = (40, 952, 1040, 1226)        # caption card
ANNO_Y = 1262

def evidence_base(idx, total, ev):
    img = paper_bg(seed=11 + idx)
    d = ImageDraw.Draw(img)
    # tag row
    x = pill(d, 60, 64, "访谈实录", F("zb", 32), WHITE, TEAL, h=56)
    d.text((x + 16, 64 + 28), f"{idx:02d} / {total:02d}", font=F("eh", 34), fill=TEAL_D, anchor="lm")
    d.text((W - 60, 64 + 28), "ORIGINAL FOOTAGE", font=F("eb", 26), fill=INK2, anchor="rm")
    # heading
    hl = layout(rich(ev["heading"], F("zb", 60), INK, F("zb", 60), ORANGE_D, brace=True), 960)
    asc = F("zb", 60).getmetrics()[0]
    top = 150 if len(hl) == 1 else 128
    draw_lines(d, hl, 60, top, 78, ascent=asc)
    # marker underline below heading
    d.rounded_rectangle((60, top + 78 * len(hl) + 8, 60 + 120, top + 78 * len(hl) + 16), 4, fill=ORANGE)
    # video panel frame (photo print with shadow)
    fr = (PX - 12, PY - 12, PX + PW + 12, PY + PH + 12)
    shadow_rect(img, fr, 6, blur=16, offset=(0, 10), alpha=85)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(fr, 6, fill=(252, 250, 245))
    d.rectangle((PX, PY, PX + PW - 1, PY + PH - 1), fill=(18, 12, 10))
    # caption card
    shadow_rect(img, CAP_BOX, 14, blur=10, offset=(0, 6), alpha=55)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(CAP_BOX, 14, fill=CARD)
    d.rounded_rectangle((CAP_BOX[0], CAP_BOX[1], CAP_BOX[0] + 10, CAP_BOX[3]), 5, fill=TEAL)
    # footnote
    d.text((W / 2, 1868), C.FOOTNOTE, font=F("zr", 26), fill=INK2, anchor="mm")
    return img.convert("RGB")

def evidence_top():
    """layer above the video: tape + 'original' badge"""
    random.seed(3)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tape(img, PX + 34, PY - 2, 35)
    tape(img, PX + PW - 34, PY - 2, -35)
    d = ImageDraw.Draw(img)
    bx, by = PX + 22, PY + 22
    f = F("zb", 26)
    tw = f.getlength("原始访谈画面")
    d.rounded_rectangle((bx, by, bx + tw + 64, by + 44), 22, fill=(0, 0, 0, 150))
    d.ellipse((bx + 16, by + 14, bx + 32, by + 30), fill=(232, 52, 44, 255))
    d.text((bx + 42, by + 22), "原始访谈画面", font=f, fill=WHITE, anchor="lm")
    return img

def caption_png(key):
    t0, t1, en, zh, hi = C.CAP[key]
    bw = CAP_BOX[2] - CAP_BOX[0]; bh = CAP_BOX[3] - CAP_BOX[1]
    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    def fit(make_runs, sizes, cap, two_size):
        # one line if it fits at any allowed size, else two balanced lines
        for s in sizes:
            lines = layout(make_runs(s), cap)
            if len(lines) == 1:
                return s, lines
        runs = make_runs(two_size)
        total = sum(f.getlength(t) for t, f, c in runs)
        target = total / 2 + two_size * 1.5
        lines = layout(runs, target)
        while len(lines) > 2 and target < cap:
            target += 16; lines = layout(runs, target)
        return two_size, lines
    if "\n" in zh:   # explicit line break: largest size at which every part fits on one line
        parts = zh.split("\n")
        for zs in (50, 47, 44, 40):
            zl = [layout([(p, F("zb", zs), INK)], 930) for p in parts]
            if all(len(x) == 1 for x in zl): break
        zl = [x[0] for x in zl]
    else:
        zs, zl = fit(lambda s: [(zh, F("zb", s), INK)], (50, 47, 44), 930, 48)
    es, el = fit(lambda s: rich(en, F("er", s), INK2, F("eb", s), ORANGE_D, phrases=hi), (32, 30, 28), 950, 30)
    fz, fe = F("zb", zs), F("er", es)
    zlh, elh, gap = int(zs * 1.36), int(es * 1.4), 18
    tot = len(zl) * zlh + gap + len(el) * elh
    y = (bh - tot) / 2
    draw_lines(d, zl, 20, y, zlh, align="center", box_w=bw - 20, ascent=fz.getmetrics()[0] - 4)
    y2 = y + len(zl) * zlh + gap
    draw_lines(d, el, 20, y2, elh, align="center", box_w=bw - 20, ascent=fe.getmetrics()[0] - 2)
    return img

def anno_png(ev):
    """annotation card, full width; returns RGBA image (top at ANNO_Y)"""
    X0, X1 = 40, 1040
    inner = X1 - X0 - 80
    # measure
    fk_e = F("eh", 40); fk_z = F("zb", 38); fn = F("zr", 37)
    rows = []
    for en, zh in ev["keys"]:
        ew = fk_e.getlength(en); arrow = fk_z.getlength("  →  "); zw = fk_z.getlength(zh)
        rows.append((en, zh, ew + arrow + zw > inner))
    note_lines = layout([(ev["note"], fn, INK)], inner)
    h = 36 + 60 + 22
    for r in rows: h += 64 * (2 if r[2] else 1) + 6
    h += 26 + len(note_lines) * 56 + 34
    img = Image.new("RGBA", (W, h + 40), (0, 0, 0, 0))
    box = (X0, 6, X1, 6 + h)
    shadow_rect(img, box, 16, blur=12, offset=(0, 8), alpha=60)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, 16, fill=CARD + (255,))
    d.rounded_rectangle((X0, 6, X0 + 10, 6 + h), 5, fill=ORANGE)
    y = 6 + 36
    xe = pill(d, X0 + 40, y, "解析", F("zb", 30), WHITE, ORANGE, h=50)
    d.text((xe + 16, y + 25), "原话关键词 → 中文含义", font=F("zr", 28), fill=INK2, anchor="lm")
    y += 60 + 22
    for en, zh, wrap in rows:
        a = fk_e.getmetrics()[0]
        d.text((X0 + 40, y + a), en, font=fk_e, fill=TEAL_D, anchor="ls")
        if wrap:
            d.text((X0 + 40, y + 64 + a), "→  " + zh, font=fk_z, fill=INK, anchor="ls")
            y += 128 + 6
        else:
            xx = X0 + 40 + fk_e.getlength(en)
            d.text((xx, y + a), "  →  " + zh, font=fk_z, fill=INK, anchor="ls")
            y += 64 + 6
    # dashed divider
    yy = y + 6
    for xx in range(X0 + 40, X1 - 40, 18):
        d.line((xx, yy, xx + 9, yy), fill=(200, 192, 172), width=2)
    y += 26
    draw_lines(d, note_lines, X0 + 40, y, 56, ascent=fn.getmetrics()[0] - 2)
    return img

# ---------------------------------------------------------------- theory overlays
def theory_tag():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pill(d, 36, 34, "理论解析", F("zb", 28), WHITE, (38, 32, 24, 205), h=50)
    return img

def t6_note():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    X0, X1, Y0 = 96, 984, 1300
    title, text = C.T6_NOTE
    fn = F("zr", 34)
    lines = layout(rich(text, fn, INK, F("zb", 34), ORANGE_D, phrases=["Prior（先验）", "Posterior（后验）"]), X1 - X0 - 70)
    h = 30 + 46 + 18 + len(lines) * 52 + 26
    box = (X0, Y0, X1, Y0 + h)
    shadow_rect(img, box, 10, blur=10, offset=(0, 6), alpha=55)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, 10, fill=(255, 248, 214, 245))
    d.rectangle((X0, Y0, X1, Y0 + 8), fill=(240, 200, 90, 255))
    pill(d, X0 + 34, Y0 + 30, title, F("zb", 26), WHITE, TEAL_D, h=46)
    draw_lines(d, lines, X0 + 34, Y0 + 30 + 46 + 18, 52, ascent=fn.getmetrics()[0] - 2)
    return img

def end_card():
    img = paper_bg(seed=99)
    d = ImageDraw.Draw(img)
    f1 = F("zb", 76); f2 = F("zb", 54)
    d.text((W / 2, 760), "先看证据，", font=f1, fill=INK, anchor="mm")
    d.text((W / 2, 870), "再更新判断。", font=f1, fill=INK, anchor="mm")
    d.rounded_rectangle((W / 2 - 90, 940, W / 2 + 90, 950), 5, fill=ORANGE)
    d.text((W / 2, 1040), "这才是“非常贝叶斯”。", font=f2, fill=ORANGE_D, anchor="mm")
    # formula
    fs = F("si", 46)
    parts = [("P(θ|x) ∝ ", INK), ("P(x|θ)", TEAL_D), (" · ", INK), ("P(θ)", ORANGE)]
    tw = sum(fs.getlength(p) for p, _ in parts); x = W / 2 - tw / 2
    for p, c in parts:
        d.text((x, 1190), p, font=fs, fill=c, anchor="lm"); x += fs.getlength(p)
    d.text((W / 2, 1262), "后验  ∝  似然（新证据） × 先验", font=F("zr", 30), fill=INK2, anchor="mm")
    d.text((W / 2, 1820), "理论解析：《非常贝叶斯》 ｜ 访谈实录：Zuckerberg's $100 Billion Bet", font=F("zr", 26), fill=INK2, anchor="mm")
    return img.convert("RGB")

if __name__ == "__main__":
    evs = [k for k in C.ORDER if k in C.EVIDENCE]
    top = evidence_top(); top.save(f"{OUT}/ev_top.png")
    for i, k in enumerate(evs, 1):
        ev = C.EVIDENCE[k]
        evidence_base(i, len(evs), ev).save(f"{OUT}/{k}_base.png")
        anno_png(ev).save(f"{OUT}/{k}_anno.png")
    for key in C.CAP:
        caption_png(key).save(f"{OUT}/cap_{key}.png")
    theory_tag().save(f"{OUT}/theory_tag.png")
    t6_note().save(f"{OUT}/t6_note.png")
    end_card().save(f"{OUT}/end_card.png")
    # preview composite for checking
    prev = Image.open(f"{OUT}/E3_base.png").convert("RGBA")
    prev.alpha_composite(top)
    prev.alpha_composite(caption_png("L10"), (CAP_BOX[0], CAP_BOX[1]))
    prev.alpha_composite(anno_png(C.EVIDENCE["E3"]), (0, ANNO_Y))
    prev.convert("RGB").save(f"{OUT}/_preview_E3.jpg", quality=88)
    prev = Image.open(f"{OUT}/E6_base.png").convert("RGBA")
    prev.alpha_composite(top)
    prev.alpha_composite(caption_png("L18"), (CAP_BOX[0], CAP_BOX[1]))
    prev.alpha_composite(anno_png(C.EVIDENCE["E6"]), (0, ANNO_Y))
    prev.convert("RGB").save(f"{OUT}/_preview_E6.jpg", quality=88)
    keys = list(C.CAP)
    cw, chh = 1000, CAP_BOX[3] - CAP_BOX[1]
    sheet = Image.new("RGB", (cw * 3 + 40, (chh + 10) * ((len(keys) + 2) // 3)), (180, 175, 160))
    for i, k in enumerate(keys):
        tile = Image.new("RGBA", (cw, chh), CARD + (255,))
        tile.alpha_composite(caption_png(k))
        sheet.paste(tile.convert("RGB"), ((i % 3) * (cw + 20), (i // 3) * (chh + 10)))
    sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS).save(f"{OUT}/_captions_sheet.jpg", quality=88)
    print("ok")
