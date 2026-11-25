"""CTC forced alignment with the MMS aligner (torchaudio.pipelines.MMS_FA): letter posteriors every 20 ms.

  ctc.py emit         compute and cache emissions of the vocal stem and the mix (work/audio/em_*.npy)

align(ids_per_unit, t0, t1, src) forces a romanised unit sequence through the emissions between t0 and t1 and
returns per unit (start, end, mean posterior). CJK is romanised to toneless pinyin, Latin words to their letters.
"""
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOP = 0.02
SPELL = {'ceo': 'seeeeo', 'ptt': 'peeteetee', "we've": 'weev', 'elon': 'eelon', 'jensen': 'jensen', "jensen's": 'jensens'}
_state = {}


def _bundle():
    if 'b' not in _state:
        import torch
        import torchaudio
        torch.hub.set_dir(os.path.join(ROOT, 'work', 'models', 'torchhub'))
        torch.set_num_threads(os.cpu_count())
        b = torchaudio.pipelines.MMS_FA
        _state['b'] = b
        _state['dic'] = b.get_dict(star='*')
    return _state['b'], _state['dic']


def dic():
    if 'dic' not in _state:
        import torchaudio
        _state['dic'] = torchaudio.pipelines.MMS_FA.get_dict(star='*')
    return _state['dic']


def romanise(units):
    """units: list of strings (a CJK char or a Latin word) -> list of id lists."""
    from pypinyin import lazy_pinyin
    D = dic()
    out = []
    zh = [u for u in units if ord(u[0]) >= 0x2E80]
    py = lazy_pinyin(''.join(zh))
    assert len(py) == len(zh)
    k = 0
    for u in units:
        if ord(u[0]) >= 0x2E80:
            s = py[k].lower().replace('ü', 'u').replace('v', 'u')
            k += 1
        else:
            s = u.lower().replace('’', "'")
            s = SPELL.get(s, s)
        s = re.sub(r"[^a-z']", '', s)
        out.append([D[c] for c in s if c in D] or [D['*']])
    return out


def emit():
    import soundfile as sf
    import torch
    b, D = _bundle()
    model = b.get_model(with_star=True)
    model.eval()
    for name, path in (('voc', 'voc16k.wav'), ('mix', 'mono16k.wav')):
        pcm, sr = sf.read(os.path.join(ROOT, 'work', 'audio', path), dtype='float32')
        n = len(pcm)
        CH, OV = 20 * sr, 2 * sr
        frames = int(np.ceil(n / (sr * HOP)))
        em = np.full((frames, len(D)), -1e9, np.float32)
        pos = 0
        with torch.inference_mode():
            while pos < n:
                a, bb = max(0, pos - OV), min(n, pos + CH + OV)
                e, _ = model(torch.from_numpy(pcm[a:bb])[None])
                e = torch.log_softmax(e[0], -1).numpy()
                f0 = int(round(a / (sr * HOP)))
                ka = int(round((pos - a) / (sr * HOP)))
                kb = min(len(e), int(round((min(n, pos + CH) - a) / (sr * HOP))))
                em[f0 + ka:f0 + kb] = e[ka:kb]
                pos += CH
        np.save(os.path.join(ROOT, 'work', 'audio', f'em_{name}.npy'), em)
        print(name, em.shape, flush=True)


def em(src='voc'):
    if src not in _state:
        _state[src] = np.load(os.path.join(ROOT, 'work', 'audio', f'em_{src}.npy'))
    return _state[src]


def align(ids, t0, t1, src='voc'):
    """-> list of (start, end, score) per unit, or None when the window is too short."""
    import torch
    import torchaudio
    E = em(src)
    f0, f1 = max(0, int(t0 / HOP)), min(len(E), int(t1 / HOP))
    targets, owner = [], []
    for ui, x in enumerate(ids):
        targets += x
        owner += [ui] * len(x)
    e = torch.from_numpy(E[f0:f1])[None]
    if e.shape[1] < len(targets) + 2:
        return None
    try:
        path, score = torchaudio.functional.forced_align(e, torch.tensor([targets], dtype=torch.int32), blank=0)
    except Exception:  # noqa: BLE001
        return None
    path, score = path[0].numpy(), score[0].exp().numpy()
    # walk the path: each target token is a run of its label; consecutive identical targets are split by a blank
    spans, k, prev = [], -1, 0
    for f, lab in enumerate(path):
        if lab != 0 and (prev == 0 or lab != prev):
            k += 1
            spans.append([f, f, [score[f]]])
        elif lab != 0:
            spans[-1][1] = f
            spans[-1][2].append(score[f])
        prev = lab
    if len(spans) != len(targets):
        return None
    res = [None] * len(ids)
    for ui, (a, b, sc) in zip(owner, spans):
        if res[ui] is None:
            res[ui] = [f0 * HOP + a * HOP, f0 * HOP + (b + 1) * HOP, list(sc)]
        else:
            res[ui][1] = f0 * HOP + (b + 1) * HOP
            res[ui][2] += sc
    return [(r[0], r[1], float(np.mean(r[2]))) for r in res]


if __name__ == '__main__':
    if sys.argv[1] == 'emit':
        emit()


def romanise_py(py):
    """one toneless pinyin syllable -> id list"""
    D = dic()
    s = re.sub(r"[^a-z']", '', py.lower().replace('ü', 'u').replace('v', 'u'))
    return [D[c] for c in s if c in D] or [D['*']]
