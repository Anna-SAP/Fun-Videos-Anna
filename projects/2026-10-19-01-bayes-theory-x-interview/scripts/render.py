# -*- coding: utf-8 -*-
"""Render one segment (or concat all) for the Bayes edit.
usage: python3 render.py <SEG|concat> <video_dir> <work_dir> [out_name]
"""
import os, sys, subprocess, shlex
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

seg, VID, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
A = os.path.join(WORK, "assets")
S = os.path.join(WORK, "segs")
os.makedirs(S, exist_ok=True)
FPS = C.FPS
PAPER_HEX = "0xE8E3D3"

VENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-level", "4.2", "-g", "60", "-r", str(FPS)]
AENC = ["-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]

def nframes(d): return int(round(d * FPS))

def run(cmd):
    print(" ".join(shlex.quote(c) for c in cmd)[:600], flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:]); sys.exit(1)

def audio_tail(label_in, gain_db, fin, fout, d, N):
    return (f"{label_in}aresample=48000,aformat=channel_layouts=stereo,volume={gain_db}dB,"
            f"afade=t=in:st=0:d={fin},afade=t=out:st={max(0, d - fout):.3f}:d={fout},"
            f"alimiter=limit=0.89:level=false,apad,atrim=end_sample={N * 1600}[aout]")

def theory(name):
    s, e = C.THEORY_SEG[name]["src"]; d = e - s; N = nframes(d); d = N / FPS
    inp = ["-ss", f"{s:.3f}", "-t", f"{d + 0.2:.3f}", "-i", os.path.join(VID, C.THEORY),
           "-loop", "1", "-framerate", str(FPS), "-t", f"{d + 0.2:.3f}", "-i", f"{A}/theory_tag.png"]
    fc = [f"[0:v]fps={FPS},scale={C.W}:{C.H}:flags=lanczos,setsar=1[v0]",
          "[1:v]format=rgba[tag]", "[v0][tag]overlay=0:0[v1]"]
    last = "[v1]"
    if "note_at" in C.THEORY_SEG[name]:
        inp += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d + 0.2:.3f}", "-i", f"{A}/t6_note.png"]
        fc += [f"[2:v]format=rgba,fade=t=in:st={C.THEORY_SEG[name]['note_at']}:d=0.4:alpha=1[note]", f"{last}[note]overlay=0:0[v2]"]
        last = "[v2]"
    fc.append(f"{last}trim=end_frame={N},setpts=PTS-STARTPTS,format=yuv420p[vout]")
    fc.append(audio_tail("[0:a]", 2.5, 0.03, 0.04, d, N))
    run(["ffmpeg", "-y", "-hide_banner", *inp, "-filter_complex", ";".join(fc),
         "-map", "[vout]", "-map", "[aout]", *VENC, *AENC, f"{S}/{name}.mkv"])

def caption_windows(ev, s, d):
    keys = ev["caps"]; out = []
    for i, k in enumerate(keys):
        a, b = C.CAP[k][0] - s, C.CAP[k][1] - s
        if i + 1 < len(keys):
            nxt = C.CAP[keys[i + 1]][0] - s
            if nxt - b < 1.2: b = nxt - 0.034
        else:
            b = d
        out.append((k, max(0.0, a), min(d, b)))
    return out

def evidence(name):
    ev = C.EVIDENCE[name]
    s, e = ev["src"]; d = e - s; N = nframes(d); d = N / FPS
    T = f"{d + 0.2:.3f}"
    inp = ["-loop", "1", "-framerate", str(FPS), "-t", T, "-i", f"{A}/{name}_base.png",
           "-ss", f"{s:.3f}", "-t", T, "-i", os.path.join(VID, C.CLIP),
           "-loop", "1", "-framerate", str(FPS), "-t", T, "-i", f"{A}/ev_top.png",
           "-loop", "1", "-framerate", str(FPS), "-t", T, "-i", f"{A}/{name}_anno.png"]
    cw, ch, cx, cy = C.CLIP_CROP
    px, py, pw, ph = C.PANEL
    chain = f"[1:v]fps={FPS},crop={cw}:{ch}:{cx}:{cy}"
    for a, b in C.UI_WINDOWS:
        ra, rb = a - s, b - s
        if rb > 0 and ra < d:
            en = f"between(t\\,{max(0, ra):.3f}\\,{rb:.3f})"
            bx, by, bw, bh = C.UI_BAND; ix, iy, iw, ih = C.UI_ICONS
            chain += (f",drawbox=x={bx}:y={by}:w={bw}:h={bh}:color=0x120b09@1:t=fill:enable='{en}'"
                      f",delogo=x={ix}:y={iy}:w={iw}:h={ih}:enable='{en}'")
    chain += f",scale={pw}:{ph}:flags=lanczos,setsar=1[cv]"
    fc = [chain, "[0:v]setsar=1,format=yuv420p[b]", f"[b][cv]overlay={px}:{py}[v1]",
          "[2:v]format=rgba[top]", "[v1][top]overlay=0:0[v2]",
          f"[3:v]format=rgba,fade=t=in:st={ev['anno_at']}:d=0.45:alpha=1[an]", "[v2][an]overlay=0:1262[v3]"]
    last = "[v3]"; idx = 4
    for k, a, b in caption_windows(ev, s, d):
        inp += ["-loop", "1", "-framerate", str(FPS), "-t", T, "-i", f"{A}/cap_{k}.png"]
        fc += [f"[{idx}:v]format=rgba[c{idx}]", f"{last}[c{idx}]overlay=40:952:enable='between(t\\,{a:.3f}\\,{b:.3f})'[v{idx}]"]
        last = f"[v{idx}]"; idx += 1
    fc.append(f"{last}fade=t=in:st=0:d=0.18:color={PAPER_HEX},trim=end_frame={N},setpts=PTS-STARTPTS,format=yuv420p[vout]")
    fin, fout = ev["afade"]
    fc.append(audio_tail("[1:a]", 3.0, fin, fout, d, N))
    run(["ffmpeg", "-y", "-hide_banner", *inp, "-filter_complex", ";".join(fc),
         "-map", "[vout]", "-map", "[aout]", *VENC, *AENC, f"{S}/{name}.mkv"])

def endcard():
    d = C.END_DUR; N = nframes(d); d = N / FPS
    inp = ["-loop", "1", "-framerate", str(FPS), "-t", f"{d + 0.2:.3f}", "-i", f"{A}/end_card.png",
           "-f", "lavfi", "-t", f"{d + 0.2:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    fc = [f"[0:v]setsar=1,fade=t=in:st=0:d=0.35:color={PAPER_HEX},fade=t=out:st={d - 0.5:.3f}:d=0.5:color={PAPER_HEX},"
          f"trim=end_frame={N},setpts=PTS-STARTPTS,format=yuv420p[vout]",
          f"[1:a]atrim=end_sample={N * 1600}[aout]"]
    run(["ffmpeg", "-y", "-hide_banner", *inp, "-filter_complex", ";".join(fc),
         "-map", "[vout]", "-map", "[aout]", *VENC, *AENC, f"{S}/END.mkv"])

def concat(out_name):
    lst = os.path.join(S, "list.txt")
    with open(lst, "w") as f:
        for k in C.ORDER:
            f.write(f"file '{S}/{k}.mkv'\n")
    out = os.path.join(VID, out_name)
    run(["ffmpeg", "-y", "-hide_banner", "-f", "concat", "-safe", "0", "-i", lst,
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    print("wrote", out)

if __name__ == "__main__":
    if seg == "concat": concat(sys.argv[4] if len(sys.argv) > 4 else "out.mp4")
    elif seg == "END": endcard()
    elif seg in C.THEORY_SEG: theory(seg)
    elif seg in C.EVIDENCE: evidence(seg)
    print("done", seg)
