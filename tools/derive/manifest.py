"""out/derived/manifest.json: what derive made, for build-disc and the patcher (tools/derive/README.md).

  {"format": 1,
   "files": {disc path: {"sha1", "size", "step", "file" (under out/), "origin": "derived"}},
   "steps": {name: {"description", "seconds", "outputs": [file...], "inputs": [path...] (with --record)}},
   "plan": {} (NEW_FILES, LANG_FILES, LANG_OVL, PARTNER_MMD_MAX, authored files),
   "facts": the exe facts the build read}
A step's output with no disc path (an intermediate another step reads) is listed under its step only.
"""
import hashlib
import json
import os

FORMAT = 1


def sha1(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def path(out):
    return os.path.join(out, 'derived', 'manifest.json')


def load(out):
    try:
        with open(path(out)) as f:
            m = json.load(f)
    except FileNotFoundError:
        return {'format': FORMAT, 'files': {}, 'steps': {}, 'plan': {}, 'facts': None}
    if m.get('format') != FORMAT:
        raise SystemExit(f'{path(out)}: manifest format {m.get("format")}, this derive writes {FORMAT}')
    return m


def record(m, out, mod, outputs, seconds, inputs=None):
    """Puts one step's outputs in the manifest m (replacing what that step had)."""
    m['files'] = {k: v for k, v in m['files'].items() if v['step'] != mod.NAME}
    for rel, disc in outputs:
        f = os.path.join(out, rel)
        if disc:
            m['files'][disc] = {'sha1': sha1(f), 'size': os.path.getsize(f), 'step': mod.NAME, 'file': rel,
                                'origin': 'derived'}
    s = {'description': mod.DESCRIPTION, 'seconds': round(seconds, 2), 'outputs': [rel for rel, _ in outputs]}
    if inputs is not None:
        s['inputs'] = inputs
    m['steps'][mod.NAME] = s


def save(m, out):
    os.makedirs(os.path.dirname(path(out)), exist_ok=True)
    m['files'] = dict(sorted(m['files'].items()))
    with open(path(out), 'w') as f:
        json.dump(m, f, indent=1)
        f.write('\n')
