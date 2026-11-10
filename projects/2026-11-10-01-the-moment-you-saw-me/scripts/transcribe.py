#!/usr/bin/env python3
"""Transcribe the song through the OpenAI audio API.

  transcribe.py AUDIO OUT.json MODEL [PROMPT]

whisper-1 returns word and segment timestamps (verbose_json); gpt-4o-transcribe returns plain text only
and is used as a second reading of the lyrics.
"""
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid

audio, out, model = sys.argv[1:4]
prompt = sys.argv[4] if len(sys.argv) > 4 else ''
key = os.environ['OPENAI_API_KEY']

fields = [('model', model), ('language', 'en')]
if prompt:
    fields.append(('prompt', prompt))
if model == 'whisper-1':
    fields += [('response_format', 'verbose_json'), ('timestamp_granularities[]', 'word'),
               ('timestamp_granularities[]', 'segment'), ('temperature', '0')]
else:
    fields.append(('response_format', 'json'))

b = uuid.uuid4().hex
parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields]
ctype = mimetypes.guess_type(audio)[0] or 'audio/mp4'
parts.append(f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="song{os.path.splitext(audio)[1]}"\r\n'
             f'Content-Type: {ctype}\r\n\r\n'.encode() + open(audio, 'rb').read() + b'\r\n')
parts.append(f'--{b}--\r\n'.encode())
req = urllib.request.Request('https://api.openai.com/v1/audio/transcriptions', b''.join(parts), {
    'Authorization': f'Bearer {key}', 'Content-Type': f'multipart/form-data; boundary={b}'})
try:
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.load(r)
except urllib.error.HTTPError as e:
    print('HTTP', e.code, e.read().decode()[:800])
    sys.exit(1)
json.dump(d, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(model, 'ok', len(d.get('text', '')), 'chars', json.dumps(d.get('usage')))
