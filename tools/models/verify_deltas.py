#!/usr/bin/env python3
"""Verify or rebase the plain imported model deltas against explicit importer outputs."""
import argparse
import hashlib
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.models import delta as modeldelta

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'content/modeldelta/models.json'


def checked(path, sha, size=None):
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != sha or (size is not None and len(data) != size):
        raise ValueError(f'{path}: SHA-256 {actual}, expected {sha}')
    return data


def decode_file(record, sources, delta_root=ROOT):
    inputs = [checked(sources / s['path'], s['sha256'], s['size']) for s in record['sources']]
    delta = checked(delta_root / record['delta'], record['delta_sha256'])
    data = modeldelta.decode(delta, inputs)
    if hashlib.sha256(data).hexdigest() != record['sha256'] or len(data) != record['size']:
        raise ValueError(f'{record["delta"]}: unexpected target')
    return data


def verify(sources, out=None, manifest_path=MANIFEST):
    manifest = json.loads(manifest_path.read_text())
    records = manifest['models']
    delta_root = manifest_path.parent if manifest.get('delta_base') == '.' else ROOT
    if out is not None:
        out.mkdir(parents=True, exist_ok=False)
    for row in records:
        for kind in ('mmd', 'tim'):
            data = decode_file(row[kind], sources, delta_root)
            if out is not None:
                (out / f'{row["id"]}-{row["name"]}.{kind.upper()}').write_bytes(data)
    print(f'{len(records)} models and {len(records)} textures verified by SHA-256')


def rebase(sources, previous, out, manifest_path=MANIFEST):
    manifest = json.loads(manifest_path.read_text())
    delta_root = manifest_path.parent if manifest.get('delta_base') == '.' else ROOT
    out.mkdir(parents=True, exist_ok=False)
    for row in manifest['models']:
        for kind in ('mmd', 'tim'):
            record = row[kind]
            target = decode_file(record, previous, delta_root)
            inputs = [(sources / s['path']).read_bytes() for s in record['sources']]
            delta = modeldelta.encode(target, inputs)
            if modeldelta.decode(delta, inputs) != target:
                raise ValueError(f'{row["id"]}: rebase failed')
            name = Path(record['delta']).name
            (out / name).write_bytes(delta)
            record['delta'] = name
            record['delta_sha256'] = hashlib.sha256(delta).hexdigest()
            for source, data in zip(record['sources'], inputs):
                source.update(sha256=hashlib.sha256(data).hexdigest(), size=len(data))
    manifest['delta_base'] = '.'
    (out / 'models.json').write_text(json.dumps(manifest, indent=2) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    v = sub.add_parser('verify')
    v.add_argument('--sources', type=Path, required=True)
    v.add_argument('--out', type=Path)
    v.add_argument('--manifest', type=Path, default=MANIFEST)
    r = sub.add_parser('rebase')
    r.add_argument('--sources', type=Path, required=True)
    r.add_argument('--previous', type=Path, required=True)
    r.add_argument('--out', type=Path, required=True)
    r.add_argument('--manifest', type=Path, default=MANIFEST)
    a = p.parse_args()
    if a.command == 'verify':
        verify(a.sources, a.out, a.manifest)
    else:
        rebase(a.sources, a.previous, a.out, a.manifest)


if __name__ == '__main__':
    main()
