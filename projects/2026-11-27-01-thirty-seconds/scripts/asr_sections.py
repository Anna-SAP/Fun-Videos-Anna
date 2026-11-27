#!/usr/bin/env python3
"""Per-section whisper-1 transcriptions of the vocal stem, twice each: no prompt, and with the section's lyric
lines as the prompt. Gives more independent word-time estimates for timing.py.

  asr_sections.py            writes work/audio/asr/<section>_<plain|prompt>.json (times are clip-relative;
                             the clip offset is stored as "offset")
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lyrics  # noqa: E402

ROOT = lyrics.ROOT
WIN = {'Intro': (8.0, 23.4), 'Verse 1': (22.8, 50.6), 'Pre-Chorus 1': (49.8, 59.4), 'Chorus 1': (58.4, 74.2),
       'Drop 1': (73.2, 88.0), 'Verse 2': (86.8, 123.6), 'Pre-Chorus 2': (122.6, 131.0), 'Chorus 2': (129.8, 145.2),
       'Bridge': (144.4, 162.2), 'Verse 3': (160.8, 177.0), 'Build-Up': (176.2, 184.0), 'Final Chorus': (183.2, 202.6),
       'Drop 2': (199.8, 211.2), 'Outro': (210.4, 237.5)}
os.makedirs(os.path.join(ROOT, 'work', 'audio', 'asr'), exist_ok=True)


def job(sec, mode):
    t0, t1 = WIN[sec]
    tag = sec.replace(' ', '_')
    clip = os.path.join(ROOT, 'work', 'audio', 'asr', f'{tag}.m4a')
    if not os.path.exists(clip):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t0), '-t', str(t1 - t0), '-i',
                        os.path.join(ROOT, 'work', 'audio', 'vocals.wav'), '-ac', '1', '-b:a', '96k', clip], check=True)
    out = os.path.join(ROOT, 'work', 'audio', 'asr', f'{tag}_{mode}.json')
    if os.path.exists(out):
        return out
    prompt = ''
    if mode == 'prompt':
        prompt = '，'.join(x['text'].replace(' ', '，') for x in lyrics.LINES if x['sec'] == sec)
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'transcribe.py'), clip, out + '.tmp', 'whisper-1',
                        prompt, 'zh'], capture_output=True, text=True)
    if r.returncode != 0:
        print(sec, mode, r.stdout[-300:], r.stderr[-300:])
        return None
    d = json.load(open(out + '.tmp'))
    d['offset'] = t0
    json.dump(d, open(out, 'w'), ensure_ascii=False)
    os.remove(out + '.tmp')
    return out


# make the clips first (sequential, cheap), then the API calls in parallel
for s in WIN:
    job_clip = os.path.join(ROOT, 'work', 'audio', 'asr', f"{s.replace(' ', '_')}.m4a")
with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda a: job(*a), [(s, m) for s in WIN for m in ('plain', 'prompt')]))
print(sum(1 for r in res if r), 'of', len(res), 'done')
