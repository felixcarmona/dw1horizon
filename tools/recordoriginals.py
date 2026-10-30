"""DW1 record-original models from the player's extracted files and plain MD3 deltas.

Native DW1 decoding uses only the standard library. Four cross-game entries
use the standard-library importers, also usable in Pyodide. The manifest pins
sources (including slices of ALLTIM), patches and targets independently.
"""
import hashlib
import json
from pathlib import Path

from tools.models import delta as modeldelta

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'content/record-originals/models.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(data, record, label):
    if len(data) != record['size'] or digest(data) != record['sha256']:
        raise ValueError(f'record originals: {label}: source/target SHA-256 or size mismatch')
    return data


def records(root=ROOT):
    return json.loads((Path(root) / MANIFEST).read_text())['models']


def sources(record, root=ROOT, provider=None):
    out = []
    for source in record['sources']:
        if source.get('producer') == 'import':
            if provider is None:
                raise ValueError('record originals: cross-game source needs the player source discs')
            data = provider.source(source['path'])
        else:
            data = (Path(root) / source['path']).read_bytes()
        if 'offset' in source:
            data = data[source['offset']:source['offset'] + source['size']]
        out.append(checked(data, source, source['path']))
    return out


def decode(record, root=ROOT, provider=None):
    delta = (Path(root) / record['delta']).read_bytes()
    if digest(delta) != record['delta_sha256']:
        raise ValueError(f'record originals: {record["delta"]}: delta SHA-256 mismatch')
    return checked(modeldelta.decode(delta, sources(record, root, provider)), record, record['delta'])


def make(out, root=ROOT, ids=None, games=None, work=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    made, provider = {}, None
    for row in records(root):
        if ids is not None and row['id'] not in ids:
            continue
        files = []
        for kind in ('mmd', 'tim'):
            if kind not in row:
                files.append(None)
                continue
            path = out / f'{row["id"]}.{kind.upper()}'
            if any(s.get('producer') == 'import' for s in row[kind]['sources']):
                if provider is None:
                    from tools.recordimports import Sources
                    provider = Sources(games or out.parent / 'source-games',
                                       work or out.parent / 'record-import-work', root)
                from tools.derive.importers import source_context
                with source_context(provider.games):
                    data = decode(row[kind], root, provider)
            else:
                data = decode(row[kind], root)
            path.write_bytes(data)
            files.append(str(path))
        made[row['id']] = tuple(files)
    return made
