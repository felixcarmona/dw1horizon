"""The authored effect chunks, drawn once here and committed (content/battle/own-effects.bin.z).

The drawing code needs numpy; the player's patcher runs on a bare Python, so it reads these bytes instead.
After changing tools/technique_effects or the "authored" entries of content/battle/own-effects.json, run
`python3 -m tools.technique_effects.prebuilt` (tools/test_technique_effects.py checks the file is current).

The file is the zlib-compressed chunks of the "authored" entries in ascending key order, 0x5000 bytes each,
built for effect id 0x100 + key.
"""
import importlib
import json
import os
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPEC = 'content/battle/own-effects.json'
BLOB = 'content/battle/own-effects.bin.z'
CHUNK_SIZE = 0x5000


def authored_keys(spec):
    return sorted(int(k) for k, e in spec.items() if k != 'note' and 'authored' in e)


def draw(spec):
    """{key: chunk} drawn by tools/technique_effects (needs numpy)."""
    out = {}
    for key in authored_keys(spec):
        e = spec[str(key)]
        row = importlib.import_module('tools.technique_effects.' + e['authored'])
        chunk, _kept = row.EFFECTS[e['technique']]().build(0x100 + key)
        if len(chunk) != CHUNK_SIZE:
            raise ValueError(f'own effect {key}: {len(chunk):#x} bytes, expected {CHUNK_SIZE:#x}')
        out[key] = bytes(chunk)
    return out


def encode(chunks):
    return zlib.compress(b''.join(chunks[k] for k in sorted(chunks)), 9)


def load(root, spec):
    """{key: chunk} from the committed file, checked against the spec's authored entries."""
    with open(os.path.join(root, BLOB), 'rb') as f:
        data = zlib.decompress(f.read())
    keys = authored_keys(spec)
    if len(data) != len(keys) * CHUNK_SIZE:
        raise ValueError(f'{BLOB}: {len(data) // CHUNK_SIZE} chunks for {len(keys)} authored effects; '
                         'run python3 -m tools.technique_effects.prebuilt')
    return {k: data[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE] for i, k in enumerate(keys)}


def main():
    with open(os.path.join(ROOT, SPEC)) as f:
        spec = json.load(f)
    chunks = draw(spec)
    with open(os.path.join(ROOT, BLOB), 'wb') as f:
        f.write(encode(chunks))
    print(f'{BLOB}: {len(chunks)} authored effects')


if __name__ == '__main__':
    main()
