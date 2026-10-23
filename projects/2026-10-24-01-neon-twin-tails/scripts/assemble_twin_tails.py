#!/usr/bin/env python3
"""NEON twin tails — rebuild the 23 s AI-cartoon clip with the dolls' hair restyled into twin tails.

  assemble_twin_tails.py VIDEO_A MV GEN_DIR OUT.mp4 [--size 1920x1080] [--auto-shift]
                         [--shift clip1=1 ...] [--check-only]

  VIDEO_A  the Higgsfield AI-cartoon clip (filename contains "Comment [neon]"), 1276x718 30 fps
  MV       A2O LITE 'NEON' Official Video.mkv (only its audio is used)
  GEN_DIR  the restyled hair shots (Kling 4.0 Video Edit): clip1*.mp4, clip2*.mp4, clip3*.mp4, plus
           shot1*.mp4, a re-edit of clip1's first shot that replaces it when present. The last file in
           name order wins, so _run2 beats _run1. A missing clip falls back to video A, so the script
           also renders a dry run before anything has been generated.

Only the hair shots go through the AI edit; the hand close-ups and the A2O / "Stage 1" graphics are
cut straight from video A. As long as the edit keeps video A's frame timing, the result stays on the
MV's music (measured with tools/av/find_offset.py: MV time = video A time - 0.0407 s, no drift).

Each generated clip is conformed to its slot: retimed to 30 fps by timestamp (Kling returns 24 fps),
scaled/cropped to --size, then trimmed or padded (last frame held) to the exact frame count. Before
that its timing is measured against the source shot on the lower part of the frame, which the hair
edit leaves alone (legs, trousers): the lag is reported per clip, --auto-shift removes it when the
1 s windows agree, and --shift sets it by hand.

The edit wipes two overlays of video A, so they are cut from video A's own pixels and laid back on
top: the creator's signature (top left, every edited frame) and the "A2O LITE" logo of the first
shot (glitch-in on frames 0-11, static to the cut at frame 82). Ink = how much darker a pixel is
than the same spot with thin dark strokes closed away (grey closing), so the overlay reproduces the
original strokes and their anti-aliasing.

requires: ffmpeg on PATH, numpy, scipy, pillow
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image
from scipy.ndimage import grey_closing

FPS = 30
N_FRAMES = 690                       # 23.000 s
MV_DELAY = 0.0407                    # video A time = MV time + 0.0407 s
SRC_W, SRC_H = 1276, 718             # video A

# (kind, [(generated-clip prefix, its frame that lands on f0), ...] in priority order, f0, f1)
# in video A frames, end exclusive
SEGMENTS = [
    ('gen', [('shot1', 0), ('clip1', 0)], 0, 82),   # solo doll, push-in to the two-doll close-up
    ('gen', [('clip1', 82)], 82, 138),              # pale-bg two shot, face + hand close-up
    ('keep', [], 138, 219),                         # hand close-ups (no hair)
    ('gen', [('clip2', 0)], 219, 475),              # 3-frame two-doll flash, two-doll dance
    ('keep', [], 475, 527),                         # A2O / "Stage 1" graphics (no dolls)
    ('gen', [('clip3', 0)], 527, 690),              # close two-doll dance -> group formation
]
assert SEGMENTS[-1][3] == N_FRAMES
# Kling bills and generates whole seconds, so every upload had its last frame held up to one:
# shot1 82 -> 90, clip1 138 -> 150, clip2 256 -> 270, clip3 164 -> 180 (one frame past the cut)
UPLOAD_FRAMES = {'shot1': 90, 'clip1': 150, 'clip2': 270, 'clip3': 180}

SIGNATURE_BOX = (slice(5, 80), slice(15, 170))  # rows, cols in video A (strokes at x 28-154, y 15-65)
SIGNATURE_FRAME = 95                            # pale background behind it
LOGO_ROWS = slice(420, 536)                     # 'A2O LITE' strokes at y 446-520, glitch lines around
LOGO_FRAMES = (0, 82)                           # on screen until the first cut
LOGO_STATIC = 12                                # glitch-in before this frame, static from it on
LOGO_FRAME = 30                                 # solo doll on a plain wall behind the logo
INK = 10                                        # luminance of the strokes

LOWER = 0.6                          # timing is measured on the frame below this height
AUDIO_GAIN_DB = -3.5                 # the MV master runs at about -10.6 LUFS here; aim for -14
LIMIT = 10 ** (-1.4 / 20)            # limiter ceiling (linear), leaves room for AAC overshoot
FADE_OUT = 0.4


def ffmpeg_log(args):
    """ffmpeg's stderr as text; it is UTF-8 whatever the console code page (paths here are Chinese)."""
    return subprocess.run(['ffmpeg'] + args, capture_output=True, encoding='utf-8', errors='replace').stderr


def count_frames(path):
    """Video frame count by remuxing to null (ffprobe is not always installed next to ffmpeg)."""
    err = ffmpeg_log(['-v', 'error', '-stats', '-i', path, '-map', '0:v:0', '-c', 'copy', '-f', 'null', '-'])
    hits = re.findall(r'frame=\s*(\d+)', err)
    return int(hits[-1]) if hits else 0


def probe_duration(path):
    """Video duration in seconds at the clip's own frame rate."""
    err = ffmpeg_log(['-hide_banner', '-i', path])
    fps = next((float(w) for line in err.splitlines() if 'Video:' in line
                for w, nxt in zip(line.split(), line.split()[1:]) if nxt.startswith('fps')), FPS)
    return count_frames(path) / fps


def gray(path, vf):
    """Raw 8-bit grayscale frames of `path` after the filter chain `vf`."""
    return subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', vf + ',format=gray', '-f', 'rawvideo', '-'],
                          check=True, capture_output=True).stdout


def lower_frames(path, start=None, end=None):
    """The part of each frame below LOWER, 128x72 grayscale at 30 fps, mean removed per frame;
    optionally only frames [start, end) of the source."""
    vf = 'fps=30,'
    if start is not None:
        vf += f'trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS,'
    f = np.frombuffer(gray(path, vf + 'scale=128:72'), np.uint8).reshape(-1, 72, 128).astype(np.float32)
    f = f[:, int(72 * LOWER):]
    return f - f.mean(axis=(1, 2), keepdims=True)


def frame_lag(ref, gen, max_lag=10, win=30):
    """(lag, agreement): the shift that best matches gen to ref, positive = gen is late, as the
    median over 1 s windows, and the share of windows within one frame of it.

    Pixels, not motion energy: a dance repeats every half beat (~14 frames at 130 BPM), and the
    motion-energy correlation aliased onto those repeats (clip2 run 2 read anywhere from -15 to +20
    frames; the legs read +2..+3 in every window)."""
    lags = []
    for s in range(max_lag, len(ref) - win - max_lag + 1, win // 2):
        errs = [np.abs(ref[s:s + win] - gen[s + lag:s + lag + win]).mean()
                if len(gen[s + lag:s + lag + win]) == win else np.inf
                for lag in range(-max_lag, max_lag + 1)]
        lags.append(int(np.argmin(errs)) - max_lag)
    if not lags:
        return 0, 0.0
    lag = int(np.median(lags))
    return lag, float(np.mean([abs(x - lag) <= 1 for x in lags]))


def ink(lum, clean=None):
    """0..1 stroke coverage: how far each pixel sits below the clean background, on the way to INK."""
    if clean is None:
        clean = grey_closing(lum, size=(9, 9))
    a = np.clip((clean - lum) / np.maximum(clean - INK, 1), 0, 1)
    a[a < 0.12] = 0
    return a, clean


def build_overlay(video_a, gen_frames, W, H, path):
    """Stroke alpha (gray video, one frame per output frame) for the generated frames only — the
    frames cut from video A still carry their own: the signature everywhere, the logo in the
    first shot."""
    f0, f1 = LOGO_FRAMES
    lum = np.frombuffer(gray(video_a, f'trim=end_frame={SIGNATURE_FRAME + 1}'), np.uint8).reshape(-1, SRC_H, SRC_W)
    L = lambda n, region: lum[n][region].astype(np.float32)
    sig = np.zeros((SRC_H, SRC_W), np.float32)
    sig[SIGNATURE_BOX] = ink(L(SIGNATURE_FRAME, SIGNATURE_BOX))[0]
    logo = np.zeros_like(sig)
    logo[LOGO_ROWS] = ink(L(LOGO_FRAME, LOGO_ROWS))[0]
    logo_static = np.maximum(sig, logo)
    clean_glitch = ink(L(LOGO_STATIC, LOGO_ROWS))[1]   # the wall behind the glitch-in frames

    def scaled(a):
        return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)).tobytes()

    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', f'{W}x{H}',
                            '-r', str(FPS), '-i', '-', '-c:v', 'ffv1', path], stdin=subprocess.PIPE)
    cache = {'none': scaled(np.zeros_like(sig)), 'sig': scaled(sig), 'logo': scaled(logo_static)}
    for n in range(N_FRAMES):
        if not gen_frames[n]:
            enc.stdin.write(cache['none'])
        elif not f0 <= n < f1:
            enc.stdin.write(cache['sig'])
        elif n >= LOGO_STATIC:
            enc.stdin.write(cache['logo'])
        else:
            glitch = np.zeros_like(sig)
            glitch[LOGO_ROWS] = ink(L(n, LOGO_ROWS), clean_glitch)[0]
            enc.stdin.write(scaled(np.maximum(sig, glitch)))
    enc.stdin.close()
    if enc.wait():
        raise RuntimeError('overlay encode failed')


def find_generated(gen_dir, sources):
    """(path, prefix, its frame that lands on the slot's first frame) for the first source present."""
    for prefix, offset in sources:
        hits = sorted(glob.glob(os.path.join(gen_dir, prefix + '*.mp4')))
        if hits:
            return hits[-1], prefix, offset
    return None, None, 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video_a')
    ap.add_argument('mv')
    ap.add_argument('gen_dir')
    ap.add_argument('out')
    ap.add_argument('--size', default='1920x1080')
    ap.add_argument('--auto-shift', action='store_true', help='remove the measured lag when windows agree (>= 70%%)')
    ap.add_argument('--shift', action='append', default=[], metavar='CLIP=FRAMES',
                    help='remove this many frames of lag from a clip by hand (negative = clip is early)')
    ap.add_argument('--check-only', action='store_true', help='report each clip, render nothing')
    args = ap.parse_args()
    W, H = map(int, args.size.split('x'))
    manual = {k: int(v) for k, v in (s.split('=') for s in args.shift)}

    inputs, chains = [args.video_a], []
    gen_frames = np.zeros(N_FRAMES, np.float32)
    print(f'{"slot":7} {"frames":>11} {"source":40} {"dur":>7} {"want":>7} {"lag":>4} {"agree":>5} {"shift":>5}')
    for i, (kind, sources, f0, f1) in enumerate(SEGMENTS):
        n = f1 - f0
        src, prefix, off = find_generated(args.gen_dir, sources)
        if src is None:
            label = 'video A' + (' (no generated clip yet)' if kind == 'gen' else '')
            print(f'{i:<7} {f0:4d}-{f1 - 1:<6d} {label:40}')
            chains.append(f'[0:v]trim=start_frame={f0}:end_frame={f1},setpts=PTS-STARTPTS,'
                          f'scale={W}:{H}:flags=lanczos,setsar=1[s{i}]')
            continue
        gen_frames[f0:f1] = 1
        dur, want = probe_duration(src), UPLOAD_FRAMES[prefix] / FPS
        lag, agree = frame_lag(lower_frames(args.video_a, f0, f1), lower_frames(src, off, off + n + 10))
        shift = manual.get(prefix, lag if (args.auto_shift and agree >= 0.7) else 0)
        print(f'{i:<7} {f0:4d}-{f1 - 1:<6d} {os.path.basename(src)[:40]:40} {dur:7.3f} {want:7.3f} '
              f'{lag:+4d} {agree:5.0%} {shift:+5d}')
        if abs(dur - want) > 2 / FPS:
            print(f'        ! length differs from the upload by {dur - want:+.3f} s: trimmed / last frame held')
        if agree < 0.7:
            print('        ! windows disagree on the lag: check this clip by eye')
        start = off + shift
        head = (f'trim=start_frame={start},setpts=PTS-STARTPTS,' if start > 0 else
                f'tpad=start={-start}:start_mode=clone,' if start < 0 else '')
        inputs.append(src)
        k = len(inputs) - 1
        chains.append(f'[{k}:v]setpts=PTS-STARTPTS,fps={FPS},{head}'
                      f'scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1,'
                      f'tpad=stop={n}:stop_mode=clone,trim=end_frame={n},setpts=PTS-STARTPTS[s{i}]')
    if args.check_only:
        return

    with tempfile.TemporaryDirectory() as tmp:
        overlay = os.path.join(tmp, 'overlay.mkv')
        build_overlay(args.video_a, gen_frames, W, H, overlay)
        o = len(inputs)
        inputs.append(overlay)
        m = len(inputs)
        inputs.append(args.mv)
        t_end = N_FRAMES / FPS
        chains.append(''.join(f'[s{i}]' for i in range(len(SEGMENTS))) +
                      f'concat=n={len(SEGMENTS)}:v=1:a=0,format=rgb24[base]')
        chains.append(f'color=c=0x{INK:02x}{INK:02x}{INK:02x}:s={W}x{H}:r={FPS}:d={t_end},format=rgb24[ink]')
        chains.append(f'[ink][{o}:v]alphamerge[strokes]')
        chains.append(f'[base][strokes]overlay=0:0:shortest=1,format=yuv420p[v]')
        chains.append(f'[{m}:a]aresample=48000,atrim=end={t_end},asetpts=PTS-STARTPTS,'
                      f'adelay={round(MV_DELAY * 48000)}S:all=1,atrim=end={t_end},'
                      f'volume={AUDIO_GAIN_DB}dB,alimiter=limit={LIMIT:.4f}:level=disabled,'
                      f'afade=t=out:st={t_end - FADE_OUT}:d={FADE_OUT}[a]')
        cmd = ['ffmpeg', '-v', 'error', '-y']
        for p in inputs:
            cmd += ['-i', p]
        cmd += ['-filter_complex', ';'.join(chains), '-map', '[v]', '-map', '[a]',
                '-r', str(FPS), '-frames:v', str(N_FRAMES), '-t', f'{t_end}',
                '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-movflags', '+faststart', args.out]
        subprocess.run(cmd, check=True)
    print(f'written {args.out}  ({count_frames(args.out)} frames = {probe_duration(args.out):.3f} s)')


if __name__ == '__main__':
    sys.exit(main())
