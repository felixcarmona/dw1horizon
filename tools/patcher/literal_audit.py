#!/usr/bin/env python3
"""Inventory/search DWP3 literals, then replace all-base exact matches with copies.

Developer tool: scan needs a C++17 compiler on a POSIX host. Refined packages use
only existing format-3 operations: applying remains plain Python 3.10, including
the browser engine. Evidence contains offsets and hashes, never literal data.
"""
import argparse
import bisect
import collections
import csv
import functools
import hashlib
import json
import lzma
import mmap
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

import dwpatch as dw
import reloc
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import isowriter as iw


def digest(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def package(folder):
    m = json.loads((folder / 'manifest.json').read_text())
    v = m['variants'][m['default']]
    raw = dw.read_patch_file(str(folder), v)
    return m, v, dw.read_payload3(raw)


def literal_runs(p):
    rows = []
    for q, ops in list(p['files'].items()) + [('license_data.dat', p['license'])]:
        pos = 0
        for i, op in enumerate(ops):
            if op[0] == 'l':
                rows.append(dict(file=q, offset=pos, length=op[2], operation=i,
                    blob_offset=op[1], sha1=hashlib.sha1(p['blob'][op[1]:op[1] + op[2]]).hexdigest()))
            if op[0] == 's':
                # Whole-file operations are never mixed with other operations.
                if len(ops) != 1:
                    raise ValueError('whole-file source mixed with operations')
            else:
                pos += op[2] if op[0] == 'l' else p['code'][op[1]][2] if op[0] == 'r' else op[3]
    return rows


def inventory(out, p):
    rows = literal_runs(p)
    write_json(out / 'runs.json', rows)
    with (out / 'runs.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['file', 'offset', 'length', 'operation', 'blob_offset', 'sha1'])
        w.writeheader(); w.writerows(rows)
    return rows


class UserData:
    """A view of every Form-1 user-data sector, including unindexed archives."""
    def __init__(self, file):
        self.raw = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)

    def __len__(self):
        return len(self.raw) // 2352 * 2048

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.raw[item // 2048 * 2352 + 24 + item % 2048]
        start, stop, step = item.indices(len(self))
        if step != 1:
            raise ValueError('user-data slices require step 1')
        parts = []
        while start < stop:
            sector, pos = divmod(start, 2048)
            length = min(stop - start, 2048 - pos)
            off = sector * 2352 + 24 + pos
            parts.append(self.raw[off:off + length])
            start += length
        return b''.join(parts)


class DiscFiles:
    def __init__(self, sources):
        self.sources = sources
        self.images = {}

    @functools.lru_cache(maxsize=3)
    def read(self, row):
        idx, q, *_ = self.sources['rows'][row]
        if idx not in self.images:
            self.images[idx] = iw.Image(self.sources['images'][idx])
        img = self.images[idx]
        return UserData(img.f) if q == '@userdata' else mmap.mmap(img.f.fileno(), 0, access=mmap.ACCESS_READ) if q == '@raw' else img.license() if q == 'license_data.dat' else img.read(q)

    def close(self):
        self.read.cache_clear()
        for img in self.images.values():
            img.f.close()


def extend_matches(blob, runs, hits, sources):
    """Extend exact 16-byte seeds both ways, without crossing literal/file ends."""
    out = []
    reader = DiscFiles(sources)
    try:
        for run in runs:
            a = run['blob_offset']; end = a + run['length']; p = previous = a
            while p < end:
                seed = p
                hit = hits.get(seed)
                if hit is None:
                    for seed in range(p - 1, max(a - 1, p - 16), -1):
                        if seed in hits:
                            hit = hits[seed]
                            break
                if hit is None:
                    p += 1; continue
                row, off = hit
                off += p - seed
                data = reader.read(row); q = seed + 16; z = off + q - p
                if blob[p:q] != data[off:z]:
                    raise ValueError('search seed does not match the source')
                while q + 4096 <= end and z + 4096 <= len(data) and blob[q:q+4096] == data[z:z+4096]:
                    q += 4096; z += 4096
                while q < end and z < len(data) and blob[q] == data[z]:
                    q += 1; z += 1
                while p > previous and off > 0 and blob[p-1] == data[off-1]:
                    p -= 1; off -= 1
                assert blob[p:q] == data[off:off+q-p]
                out.append([p, q, row, off]); p = previous = q
    finally:
        reader.close()
    return out


def mapping_literals(release, output, sources, bases):
    """Inventory hex data in regional mappings separately from the DWP blob."""
    rows = []
    totals = collections.Counter()
    usa_path = sources['images'][bases['us']]
    usa = iw.Image(usa_path)

    def inspect(owner, target, ops, canonical, source_path, source_file):
        pos = 0
        for index, op in enumerate(ops):
            if 'copy' in op:
                pos += op['copy'][1]
            elif 'disc_copy' in op:
                pos += op['disc_copy'][2]
            elif 'data' in op:
                data = bytes.fromhex(op['data'])
                same = data == canonical[pos:pos + len(data)]
                rows.append(dict(package_file=owner, target_file=target, offset=pos,
                    length=len(data), operation=index, opcode='data', category='c' if same else 'd',
                    sha1=hashlib.sha1(data).hexdigest(), source_disc=source_path if same else None,
                    source_file=source_file if same else None, source_offset=pos if same else None,
                    source_disc_sha1=sources.get('sha1', {}).get(source_path) if same else None,
                    source_file_sha1=hashlib.sha1(canonical).hexdigest() if same else None,
                    what=op.get('what'), evidence='Exact canonical disc file bytes' if same else 'Needs provenance review'))
                totals['data_bytes'] += len(data)
                totals['class_c'] += len(data) if same else 0
                totals['class_d'] += 0 if same else len(data)
                pos += len(data)
            elif 'fill' in op:
                rows.append(dict(package_file=owner, target_file=target, offset=pos,
                    length=op['fill'][1], operation=index, opcode='fill', category='a',
                    evidence='Generated repeated-byte operation; not stored data payload'))
                totals['fill_operations'] += 1
                totals['fill_output_bytes'] += op['fill'][1]
                pos += op['fill'][1]

    try:
        for path in sorted((release / 'bases').glob('*.json')):
            mapping = json.loads(path.read_text())
            for q, entry in mapping.get('files', {}).items():
                if entry.get('ops'):
                    data = usa.license() if q == 'license_data.dat' else usa.read(q)
                    inspect(str(path.relative_to(release)), q, entry['ops'], data, usa_path, q)
    finally:
        usa.f.close()
    patches = release / 'bundle/content/imports/releases/dw3-us.json'
    if patches.exists():
        import discs as catalog
        from derive.importers.discs import Image as SourceImage
        expected = next(d['sha1'] for d in catalog.SOURCE_DISCS if d['id'] == 'dw2003')
        path = next((n for n, sha in sources['sha1'].items() if sha == expected), None)
        if path is None:
            raise ValueError('DW3 Europe is required to verify the USA normalization mapping data')
        image = SourceImage(path)
        try:
            files = image.index()
            mapping = json.loads(patches.read_text())
            for code, entry in mapping.get('patches', {}).items():
                q = next(q for q in files if q.endswith('/' + code + '.BIN'))
                data = image.read(*files[q])
                if hashlib.sha1(data).hexdigest() != mapping['recipes'][code]:
                    raise ValueError('DW3 canonical model does not match its recorded source')
                inspect(str(patches.relative_to(release)), code + '.BIN', entry['ops'], data, path, q)
        finally:
            image.file.close()
    write_json(output / 'mapping-literals.json', rows)
    write_json(output / 'mapping-literal-totals.json', totals)
    return totals


def scan(a):
    m, v, p = package(a.release)
    a.output.mkdir(parents=True, exist_ok=False)
    runs = inventory(a.output, p)
    sources = dict(images=[], rows=[], sha1={})
    bases = {}
    errors = {}
    for path in sorted(a.isos.rglob('*')):
        if path.suffix.lower() not in ('.bin', '.iso') or any(x.startswith('fan-') for x in path.parts):
            continue
        try:
            img = iw.Image(str(path))
        except (ValueError, OSError, struct.error) as e:
            errors[str(path)] = str(e); continue
        h = digest(path)
        for key, b in m['bases'].items():
            if h == b['sha1']:
                bases[key] = len(sources['images'])
        idx = len(sources['images']); sources['images'].append(str(path)); sources['sha1'][str(path)] = h
        for q, (lba, n, xa) in sorted(img.files.items()):
            sources['rows'].append([idx, q, lba, n, xa])
        sources['rows'].extend([[idx, 'license_data.dat', 0, 12 * 2048, 1], [idx, '@raw', 0, 0, 2], [idx, '@userdata', 0, 0, 3]])
        img.f.close()
    if set(bases) != set(m['bases']):
        raise ValueError(f'missing verified base images: {set(m["bases"]) - set(bases)}')
    write_json(a.output / 'sources.json', sources)
    mapping_literals(a.release, a.output, sources, bases)
    write_json(a.output / 'scan-errors.json', errors)
    write_json(a.output / 'input.json', dict(patch_sha1=v['patch_sha1'], bases=bases,
                                           release=str(a.release.resolve())))
    with tempfile.TemporaryDirectory(prefix='literal-scan-', dir=a.output) as td:
        temp = Path(td)
        (temp / 'blob').write_bytes(p['blob'])
        (temp / 'ranges').write_text(''.join(f'{r["blob_offset"]}\t{r["length"]}\n' for r in runs))
        subprocess.run(['c++', '-O3', '-std=c++17', str(Path(__file__).with_name('literal_scan.cpp')),
                        '-o', str(temp / 'scan')], check=True)
        for key in ['all'] + list(bases):
            rows = [i for i, r in enumerate(sources['rows']) if key == 'all' or r[0] == bases[key]]
            (temp / 'sources').write_text(''.join(
                f'{sources["images"][sources["rows"][i][0]]}\t{i}\t{sources["rows"][i][2]}\t'
                f'{sources["rows"][i][3]}\t{int(sources["rows"][i][4])}\n' for i in rows))
            with (temp / 'matches').open('w') as output, (a.output / f'scan-{key}.log').open('w') as log:
                subprocess.run([str(temp / 'scan'), str(temp / 'blob'), str(temp / 'ranges'),
                                str(temp / 'sources')], stdout=output, stderr=log, check=True)
            hits = {}
            for line in (temp / 'matches').read_text().splitlines():
                off, row, pos = map(int, line.split())
                hits[off] = (rows[row], pos)
            spans = extend_matches(p['blob'], runs, hits, sources)
            write_json(a.output / f'segments-{key}.json', spans)
            print(key, len(spans), 'spans,', sum(b-a for a,b,*_ in spans), 'matching bytes', flush=True)


def refine(a):
    if a.output.exists():
        raise ValueError(f'output already exists: {a.output}')
    m, v, p = package(a.release)
    info = json.loads((a.evidence / 'input.json').read_text())
    if info['patch_sha1'] != v['patch_sha1']:
        raise ValueError('search evidence belongs to another patch')
    sources = json.loads((a.evidence / 'sources.json').read_text())
    for path, sha in sources['sha1'].items():
        if digest(path) != sha:
            raise ValueError(f'search source changed: {path}')
    matches = {}
    reader = DiscFiles(sources)
    try:
        for key in m['bases']:
            spans = json.loads((a.evidence / f'segments-{key}.json').read_text())
            matches[key] = []
            by_source = collections.defaultdict(list)
            for lo, hi, row, off in spans:
                idx, q, *_ = sources['rows'][row]
                if idx != info['bases'][key]:
                    raise ValueError('copy evidence is not a supported file on its base')
                by_source[row].append((lo, hi, off))
                matches[key].append([lo, hi, q, off])
            # Validate each source once, even when thousands of literal fragments use it.
            for row, records in by_source.items():
                data = reader.read(row)
                for lo, hi, off in records:
                    if lo < 0 or hi <= lo or off < 0 or p['blob'][lo:hi] != data[off:off+hi-lo]:
                        raise ValueError('copy evidence does not match its base/literal')
    finally:
        reader.close()
    donor = None
    if a.bundle_from:
        dm, dv, _ = package(a.bundle_from)
        expected = lambda variant: {h['file']: (h['size'], h['sha1'], h.get('sha1_by_base', {}))
                                    for h in variant['holes']}
        if (len(m['variants']) != 1 or expected(v) != expected(dv) or
                m['extract'] != dm['extract'] or m.get('source_discs') != dm.get('source_discs') or
                v['local'] != dv['local'] or dm.get('python_packages') != []):
            raise ValueError('bundle donor does not prove the same dependency-free derived files')
        donor = dict(manifest_sha1=digest(a.bundle_from / 'manifest.json'),
                     release=str(a.bundle_from.resolve()), identical_holes=len(v['holes']),
                     entry_files={name: digest(a.bundle_from / name) for name in ('dwpatch.py', 'isowriter.py', 'README.md')})
    before = len(p['blob'])
    saved = reloc.copy_literal_sources(p, matches, minimum=1)
    blob = p.pop('blob')
    j = json.dumps(p, separators=(',', ':')).encode()
    raw = lzma.compress(b'DWP3' + struct.pack('<I', len(j)) + j + blob, preset=9 | lzma.PRESET_EXTREME)
    shutil.copytree(a.release, a.output)
    if donor:
        shutil.rmtree(a.output / 'bundle')
        shutil.copytree(a.bundle_from / 'bundle', a.output / 'bundle')
        for name in ('dwpatch.py', 'isowriter.py', 'README.md'):
            shutil.copyfile(a.bundle_from / name, a.output / name)
        m['python_min'] = dm['python_min']; m['python_packages'] = []
        v['description'] = dv['description']
    shutil.copyfile(Path(__file__).with_name('dwpatch.py'), a.output / 'dwpatch.py')
    font_notices = Path(__file__).resolve().parents[1] / 'font/japanese-license'
    if font_notices.is_dir():
        shutil.copytree(font_notices, a.output / 'licenses/japanese-font', dirs_exist_ok=True)
    (a.output / v['patch']).write_bytes(raw)
    v['patch_sha1'] = hashlib.sha1(raw).hexdigest(); v['patch_size'] = len(raw)
    write_json(a.output / 'manifest.json', m)
    if (a.output / 'audit.txt').exists():
        (a.output / 'audit.txt').rename(a.output / 'audit-before-refinement.txt')
    p['blob'] = blob
    inventory(a.output, p)
    summary = dict(before=before, after=len(blob), copied=saved, patch_sha1=v['patch_sha1'],
                   patch_size=len(raw), original_patch_sha1=info['patch_sha1'], bundle_donor=donor,
                   reader_sha1=digest(a.output / 'dwpatch.py'))
    write_json(a.output / 'literal-refinement.json', summary)
    (a.output / 'audit.txt').write_text(
        'Literal refinement: exact matches on every supported base, using existing r operations.\n'
        'Original operation counts are in audit-before-refinement.txt (BEFORE this pass).\n'
        'runs.csv lists EVERY remaining literal; literal-refinement.json gives the totals.\n'
        'Japanese font source/notices: licenses/japanese-font/ (Fusion Pixel, SIL OFL 1.1).\n'
        'This is byte provenance evidence, not publication clearance.\n' + json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('scan'); s.add_argument('--isos', type=Path, required=True)
    r = sub.add_parser('refine'); r.add_argument('--evidence', type=Path, required=True)
    r.add_argument('--bundle-from', type=Path, help='verified dependency-free package with identical holes')
    for p in (s, r):
        p.add_argument('--release', type=Path, required=True)
        p.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    (scan if a.cmd == 'scan' else refine)(a)


if __name__ == '__main__':
    main()
