#!/usr/bin/env python3
"""Generate one image through the OpenAI Images API.

  oai_image.py MODEL SIZE QUALITY OUT.png PROMPT_FILE [REF.png ...]

With reference images it calls the edits endpoint. Prints usage so the cost can be tracked.
"""
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid

model, size, quality, out, prompt_file = sys.argv[1:6]
refs = sys.argv[6:]
prompt = open(prompt_file, encoding='utf-8').read().strip()
key = os.environ['OPENAI_API_KEY']


def post_json(url, body):
    return urllib.request.Request(url, json.dumps(body).encode(), {
        'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})


def post_multipart(url, fields, files):
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, path in files:
        ctype = mimetypes.guess_type(path)[0] or 'image/png'
        head = f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{os.path.basename(path)}"\r\nContent-Type: {ctype}\r\n\r\n'
        parts.append(head.encode() + open(path, 'rb').read() + b'\r\n')
    parts.append(f'--{b}--\r\n'.encode())
    return urllib.request.Request(url, b''.join(parts), {
        'Authorization': f'Bearer {key}', 'Content-Type': f'multipart/form-data; boundary={b}'})


fields = {'model': model, 'prompt': prompt, 'size': size, 'quality': quality}
if refs:
    req = post_multipart('https://api.openai.com/v1/images/edits', fields, [('image[]', p) for p in refs])
else:
    req = post_json('https://api.openai.com/v1/images/generations', fields)
try:
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
except urllib.error.HTTPError as e:
    print('HTTP', e.code, e.read().decode()[:600])
    sys.exit(1)
open(out, 'wb').write(base64.b64decode(d['data'][0]['b64_json']))
print(os.path.basename(out), json.dumps(d.get('usage')))
