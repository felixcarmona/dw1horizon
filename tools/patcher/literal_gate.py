#!/usr/bin/env python3
"""Fail a developer package build on disc-matching or copyable original literals.

Search is the audit's exact, alignment-independent 16-byte-window policy. A
single byte is not a useful provenance test: every byte value occurs on discs.
This is a regression gate, not a copyright/authorship classifier. No exceptions,
release-specific offsets, or saved scan results are accepted as inputs.
"""
from collections import Counter
import hashlib
import inspect
import json
import math
from pathlib import Path
import subprocess
import tempfile

import literal_audit as audit


class GateFailure(ValueError):
    pass


def payload_chunks(payload, variant):
    """Join adjacent literals so splitting an operation cannot hide a match."""
    chunks = []
    last = None
    for row in audit.literal_runs(payload):
        data = bytes(payload['blob'][row['blob_offset']:row['blob_offset'] + row['length']])
        if last and last['file'] == row['file'] and last['offset'] + len(last['data']) == row['offset']:
            last['data'] += data
        else:
            last = dict(owner=variant, file=row['file'], offset=row['offset'], data=data)
            chunks.append(last)
    # Conventional binary deltas store diff bytes plus literal extras. Every
    # base's extras must be searched, including blocks reused by multiple bases.
    if payload.get('deltas'):
        import codecopy
        last = None
        for row in codecopy.extra_runs(payload):
            data = bytes(payload['blob'][row['blob_offset']:row['blob_offset'] + row['length']])
            owner = f'{variant}/delta-{row["delta"]}/{row["base"]}'
            if last and last['owner'] == owner and last['file'] == row['file'] and last['offset'] + len(last['data']) == row['offset']:
                last['data'] += data
            else:
                last = dict(owner=owner, file=row['file'], offset=row['offset'], data=data)
                chunks.append(last)
    return chunks


def outside_source_chunks(payload, variant, source_sizes):
    """bspatch adds zero outside a source: those diff bytes are literals too."""
    chunks = []
    for index, entry in enumerate(payload.get('deltas', [])):
        for base, delta in entry['bases'].items():
            size = (source_sizes[base][delta['source']]
                    + sum(source['size'] for source in delta.get('additional_sources', []))
                    + sum(n for _, n in audit.dw.generated_layout(entry)))
            oldpos = newpos = 0
            diffpos = delta['diff'][0]
            for n, extra, seek in delta['control']:
                spans = []
                if oldpos < 0:
                    spans.append((0, min(n, -oldpos)))
                if oldpos + n > size:
                    spans.append((max(0, size - oldpos), n))
                for lo, hi in spans:
                    if hi > lo:
                        chunks.append(dict(owner=f'{variant}/zero-source-{index}/{base}', file=entry['file'],
                            offset=newpos + lo, data=bytes(payload['blob'][diffpos + lo:diffpos + hi])))
                diffpos += n
                oldpos += n + seek
                newpos += n + extra
    return chunks


def validate_blob(payload):
    """Dead blob data is a publication error, even if it is never reconstructed."""
    for ops in list(payload['files'].values()) + [payload['license']]:
        if any(op[0] not in {'s', 'c', 'r', 'l', 'h', 'o', 'b', 'f', 'j'} for op in ops):
            raise GateFailure('new payload opcode requires explicit literal audit support')
    for recipe in payload.get('chinese', []):
        refs = [recipe[key] for key in ('module', 'font', 'names', 'patch')]
        refs += [row['file'] for row in recipe['resources']]
        refs += [recipe[key] for key in ('compact', 'english_names') if key in recipe]
        if recipe.get('format') != 1 or any(ref not in payload['files'] for ref in refs):
            raise GateFailure('Chinese container references an unchecked component')
    spans = [(r['blob_offset'], r['length']) for r in audit.literal_runs(payload)]
    for entry in payload.get('deltas', []):
        audit.dw.linker_word_bytes(entry)
        for delta in entry['bases'].values():
            spans.extend(delta[block] for block in ('diff', 'extra'))
            controls = delta['control']
            if (any(n < 0 or extra < 0 for n, extra, seek in controls)
                    or sum(n for n, extra, seek in controls) != delta['diff'][1]
                    or sum(extra for n, extra, seek in controls) != delta['extra'][1]
                    or sum(n + extra for n, extra, seek in controls) != entry['size']):
                raise GateFailure('binary delta controls do not cover their blocks/output')
    end = 0
    for offset, length in sorted(spans, key=lambda pair: (pair[0], pair[1])):
        if offset < 0 or length < 0 or offset + length > len(payload['blob']):
            raise GateFailure('literal/delta block outside payload blob')
        if length == 0:
            continue
        if offset > end:
            raise GateFailure('unreferenced bytes in payload blob; compact before publication')
        end = max(end, offset + length)
    if end != len(payload['blob']):
        raise GateFailure('unreferenced bytes in payload blob; compact before publication')


def validate_battle_rebuilds(mapping, owner):
    """Prove this recipe stores transforms of input poses, not encoded poses.

    battle_restore.rebuild restores A's declared source clip (or B's current
    authored clip), optionally fits A/B rig channels, then clip_repair.apply_ops
    transforms those frames and re-encodes them. No operation below supplies a
    pose, event program or binary payload. Numeric operands have fixed arity;
    references select bones/ticks in those input frames. Source reconstruction
    and final output equality remain the isolated derive/delta audits' job.
    Keep this closed schema in step with those two consumers, never accept an
    arbitrary `op` string or exempt a whole file from inline-data inspection.
    """
    def number(v):
        return type(v) is int or type(v) is float and math.isfinite(v)

    def integer(v):
        return type(v) is int and v >= 0

    def positive(v):
        return integer(v) and v > 0

    def vector(v, n, predicate=number):
        return isinstance(v, list) and len(v) == n and all(predicate(x) for x in v)

    axis = lambda v: (isinstance(v, str) and v in ('x', 'y', 'z') or
                      vector(v, 3) and any(v))
    envelope = lambda v: v is None or vector(v, 4, integer) and v == sorted(v)
    channel = lambda v: isinstance(v, str) and v in ('x', 'y', 'z')
    boolean = lambda v: type(v) is bool
    # Required operands, optional operands: each is consumed by the named
    # arithmetic/channel-selection branch of clip_repair.apply_ops.
    bone = {'bone': integer}
    timed = {'ticks': envelope}
    rotation = dict(bone, axis=axis, deg=number)
    oscillation = dict(cycles=number, phase=number)
    schemas = {
        'turn': (rotation, dict(timed, space=lambda v: v in ('world', 'parent'))),
        'wave': (rotation, dict(timed, **oscillation)),
        'sway': (dict(rotation, cycles=number), {'phase': number}),
        'swing': (dict(bone, channel=channel, deg=number), oscillation),
        'damp': (dict(bone, keep=number), dict(timed, to=lambda v: v in ('mean', 'first'))),
        'smooth': (bone, dict(timed, passes=positive, weight=number)),
        'mirror': (dict(bone, **{'from': integer}), {'shift': lambda v: type(v) is int}),
        'follow': (dict(bone, **{'from': integer}),
                   {'shift': lambda v: type(v) is int, 'gain': number, 'mirror': boolean}),
        'lift': (dict(bone, up=number), timed),
        'offset': (dict(bone, delta=lambda v: vector(v, 3)), timed),
        'offset_motion': (dict(bone, axis=channel, keep=number), {}),
        'retime': ({'ticks': positive}, {}),
        'repeat': ({'times': positive}, {}),
        'cut': ({'from': integer, 'to': positive}, {}),
        'seam': ({'ticks': positive}, {'bones': lambda v: isinstance(v, list) and all(integer(b) for b in v)}),
    }

    def fail(location):
        raise GateFailure(f'{owner}{location}: invalid or unsupported battle rebuild recipe; '
                          'requires source-derived transform audit support')

    if not isinstance(mapping, dict):
        fail('')
    for species, slots in mapping.items():
        location = '/' + species
        if not species.isdecimal() or not isinstance(slots, dict):
            fail(location)
        for slot, row in slots.items():
            where = location + '/' + slot
            if (not slot.isdecimal() or not isinstance(row, dict)
                    or not {'ticks', 'ops'} <= row.keys()
                    or row.keys() - {'ticks', 'ops', 'rig', 'body', 'current', 'compact'}
                    or not (row['ticks'] is None or positive(row['ticks']))
                    or not isinstance(row['ops'], list)):
                fail(where)
            if ('rig' in row and not (integer(row['rig']) or vector(row['rig'], 2, integer))
                    or 'body' in row and row['body'] not in ('offset', 'scale')
                    or 'current' in row and not boolean(row['current'])
                    or 'compact' in row and not (isinstance(row['compact'], list) and all(integer(v) for v in row['compact']))):
                fail(where)
            for i, op in enumerate(row['ops']):
                at = where + '/ops/' + str(i)
                if not isinstance(op, dict) or not isinstance(op.get('op'), str) or op['op'] not in schemas:
                    fail(at)
                required, optional = schemas[op['op']]
                if (not required.keys() <= op.keys() or op.keys() - required.keys() - optional.keys() - {'op'}
                        or any(not check(op[k]) for k, check in dict(required, **optional).items() if k in op)):
                    fail(at)


def mapping_chunks(release):
    """Find inline hex data in operation lists, including bundled import recipes."""
    chunks = []

    def visit(value, owner, location):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'ops' and isinstance(child, list):
                    if Path(owner).as_posix() == 'bundle/content/models/imports/battle-rebuilds.json':
                        # The entire closed recipe was validated before traversal.
                        visit(child, owner, location + '/' + key)
                        continue
                    known = {'copy', 'data', 'fill', 'disc_copy'}
                    for op in child:
                        if not isinstance(op, dict) or len(set(op) & known) != 1 or set(op) - known - {'what'}:
                            raise GateFailure(f'{owner}{location}: new mapping opcode requires literal audit support')
                visit(child, owner, location + '/' + key)
        elif isinstance(value, list):
            last = None
            pos = 0
            for i, child in enumerate(value):
                if isinstance(child, dict) and 'data' in child:
                    encoded = child['data']
                    # Numeric attribute scores are metadata, not byte operations.
                    # Mapping operation lists still require hexadecimal data.
                    if isinstance(encoded, (int, float)) and not location.endswith('/ops'):
                        last = None
                        visit(child, owner, location + '/' + str(i))
                        continue
                    if not isinstance(encoded, str):
                        raise GateFailure(f'{owner}{location}/{i}: non-hex inline data')
                    try:
                        data = bytes.fromhex(encoded)
                    except ValueError as exc:
                        raise GateFailure(f'{owner}{location}/{i}: invalid inline data') from exc
                    if last is None:
                        last = dict(owner=owner, file=location, offset=pos, operation=i, data=data)
                        chunks.append(last)
                    else:
                        last['data'] += data
                    pos += len(data)
                    # Other nested fields still need inspection.
                    visit({k: v for k, v in child.items() if k != 'data'}, owner, location + '/' + str(i))
                else:
                    last = None
                    if isinstance(child, dict):
                        if 'copy' in child:
                            pos += child['copy'][1]
                        elif 'fill' in child:
                            pos += child['fill'][1]
                        elif 'disc_copy' in child:
                            pos += child['disc_copy'][2]
                    visit(child, owner, location + '/' + str(i))

    for folder in ('bases', 'bundle'):
        for path in sorted((release / folder).rglob('*.json')):
            mapping = json.loads(path.read_text())
            if path.relative_to(release).as_posix() == 'bundle/content/models/imports/battle-rebuilds.json':
                validate_battle_rebuilds(mapping, str(path.relative_to(release)))
            if folder == 'bases':
                known_modes = {None, 'same', 'renamed', 'own', 'patch', 'localize', 'missing', 'needs-usa', 'differs'}
                for entry in mapping.get('files', {}).values():
                    if entry.get('how') not in known_modes:
                        raise GateFailure(f'{path}: new mapping mode requires literal audit support')
            if isinstance(mapping, dict) and 'recipes' in mapping and 'patches' in mapping:
                # (source releases are read as they are: a list that rebuilds one release's files from another's
                # would carry that release's game data)
                raise GateFailure(f'{path}: a source release list with patches: not publishable')
            visit(mapping, str(path.relative_to(release)), '')
    return chunks


def source_inventory(paths):
    sources = dict(images=[], rows=[], sha1={})
    for path in sorted({str(Path(p).resolve()) for p in paths}):
        image = audit.iw.Image(path)
        try:
            idx = len(sources['images'])
            sources['images'].append(path)
            sources['sha1'][path] = audit.digest(path)
            sources['rows'].extend([idx, q, lba, n, xa]
                                   for q, (lba, n, xa) in sorted(image.files.items()))
            sources['rows'].extend([[idx, 'license_data.dat', 0, 12 * 2048, 1],
                                    [idx, '@raw', 0, 0, 2], [idx, '@userdata', 0, 0, 3]])
        finally:
            image.f.close()
    if not sources['images']:
        raise GateFailure('no player discs supplied to publication gate')
    return sources


def scan_chunks(chunks, sources, work):
    """Search current bytes, never an evidence file from a previous build."""
    if not any(len(chunk["data"]) >= 16 for chunk in chunks):
        return []
    blob = bytearray()
    runs = []
    for chunk in chunks:
        runs.append(dict(blob_offset=len(blob), length=len(chunk['data'])))
        blob.extend(chunk['data'])
    (work / 'blob').write_bytes(blob)
    (work / 'ranges').write_text(''.join(f'{r["blob_offset"]}\t{r["length"]}\n' for r in runs))
    (work / 'sources').write_text(''.join(
        f'{sources["images"][idx]}\t{i}\t{lba}\t{n}\t{int(mode)}\n'
        for i, (idx, _, lba, n, mode) in enumerate(sources['rows'])))
    scanner = work / 'scanner'
    subprocess.run(['c++', '-O3', '-std=c++17', str(Path(audit.__file__).with_name('literal_scan.cpp')),
                    '-o', str(scanner)], check=True)
    with (work / 'hits').open('w') as hits, (work / 'scan.log').open('w') as log:
        subprocess.run([str(scanner), str(work / 'blob'), str(work / 'ranges'), str(work / 'sources')],
                       stdout=hits, stderr=log, check=True)
    hits = {}
    with (work / 'hits').open() as file:
        for line in file:
            pos, row, offset = map(int, line.split())
            hits[pos] = (row, offset)
    spans = audit.extend_matches(blob, runs, hits, sources)
    findings = []
    i = 0
    for lo, hi, row, offset in spans:
        while i < len(runs) and lo >= runs[i]['blob_offset'] + runs[i]['length']:
            i += 1
        chunk = chunks[i]
        idx, source_file, *_ = sources['rows'][row]
        findings.append(dict({k: chunk[k] for k in ('operation',) if k in chunk}, owner=chunk['owner'], file=chunk['file'],
            offset=chunk['offset'] + lo - runs[i]['blob_offset'], length=hi - lo,
            source_disc_sha1=sources['sha1'][sources['images'][idx]], source_file=source_file,
            source_offset=offset, sha1=hashlib.sha1(blob[lo:hi]).hexdigest()))
    return findings


def check(chunks, sources, original_findings, output, canonical_mappings=(), inputs=None, delta_audits=None):
    """Write reviewable evidence even on failure; do not accept exemptions."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='literal-gate-', dir=output.parent) as temp:
        matches = scan_chunks(chunks, sources, Path(temp))
    report = dict(schema=1, inputs=inputs or {}, policy='exact 16-byte seeds, bytewise extension; adjacent literals joined',
                  sources={Path(path).name: sha1 for path, sha1 in sources['sha1'].items()}, literal_bytes=sum(len(c['data']) for c in chunks),
                  short_literal_bytes=sum(len(c['data']) for c in chunks if len(c['data']) < 16),
                  disc_matching_bytes=sum(r['length'] for r in matches),
                  copyable_original_bytes=sum(r['length'] for r in original_findings),
                  canonical_mapping_bytes=sum(r['length'] for r in canonical_mappings if r.get('category', 'c') == 'c'),
                  unresolved_mapping_bytes=sum(r['length'] for r in canonical_mappings if r.get('category', 'c') != 'c'),
                  canonical_mappings=list(canonical_mappings),
                  disc_matches=matches, copyable_originals=original_findings)
    report['delta_audits'] = delta_audits or {}
    report['unverified_delta_data_bytes'] = sum(
        sum(row['unavailable_bytes_by_base'].values()) for row in report['delta_audits'].values())
    report['passed'] = not matches and not original_findings and not canonical_mappings and not report['unverified_delta_data_bytes']
    audit.write_json(output, report)
    if not report['passed']:
        raise GateFailure(f'publication blocked: {report["disc_matching_bytes"]} disc-matching literal bytes; '
                          f'{report["copyable_original_bytes"]} copyable original literal bytes; '
                          f'{report["canonical_mapping_bytes"]} canonical mapping literal bytes; '
                          f'{report["unresolved_mapping_bytes"]} unresolved mapping literal bytes; '
                          f'{report["unverified_delta_data_bytes"]} unverified reconstructed data bytes across bases; see {output}')
    return report


def output_keys_complete(outputs, manifest):
    """Every base has its output checksum, and with each source variant too ("<base>+<variant>"); nothing else."""
    want = set(manifest['bases']) | {f'{b}+{v}' for b in manifest['bases'] for v in manifest.get('source_variants') or {}}
    return set(outputs) == want


def canonical_mapping_matches(release, sources, usa_path):
    """Verify known mapping provenance even for fragments below the seed size."""
    if not any((release / 'bases').glob('*.json')):
        return []
    bases = {'us': sources['images'].index(str(Path(usa_path).resolve()))}
    with tempfile.TemporaryDirectory(prefix='literal-mappings-') as temp:
        folder = Path(temp)
        audit.mapping_literals(release, folder, sources, bases)
        rows = json.loads((folder / 'mapping-literals.json').read_text())
    return [row for row in rows if row['opcode'] == 'data']


def complete_mapping_provenance(chunks, rows):
    """New import recipes cannot hide short literals outside known backends."""
    stored = Counter()
    verified = Counter()
    for chunk in chunks:
        stored[chunk['owner']] += len(chunk['data'])
    for row in rows:
        verified[row['package_file']] += row['length']
        if row['category'] not in 'abcde':
            raise GateFailure('unknown mapping provenance class')
    for owner, length in verified.items():
        if stored[owner] != length:
            raise GateFailure(f'{owner}: mapping audit coverage mismatch: stored {stored[owner]}, audited {length}')
    out = [row for row in rows if row['category'] not in 'ae']
    for chunk in chunks:
        if chunk['owner'] not in verified:
            out.append(dict(package_file=chunk['owner'], target_file=chunk['file'],
                offset=chunk['offset'], length=len(chunk['data']), category='d',
                sha1=hashlib.sha1(chunk['data']).hexdigest(),
                evidence='Inline mapping bytes lack source-aware provenance; extend the audit backend'))
    return out


def selected_plan_options(probe, payload, build_dir, base_paths, plan):
    """Older three-argument queries are safe only for the exact recorded plan."""
    if plan is None:
        return {}
    try:
        inspect.signature(probe).bind(payload, build_dir, base_paths, plan=plan)
    except TypeError:
        folder = Path(build_dir) / 'derived'
        if (folder/'plan.json').is_file():
            recorded = json.loads((folder/'plan.json').read_text())
        elif (folder/'manifest.json').is_file():
            recorded = json.loads((folder/'manifest.json').read_text()).get('plan', {})
        else:
            recorded = None
        if recorded != plan:
            raise GateFailure('code audit cannot accept the selected derive plan; update codecopy.audit_literals for this manifest override')
        return {}
    return {'plan': plan}


def check_release(release, manifest, base_paths, source_discs, build_dirs, *, plans=None):
    """Mandatory make-release hook, after every variant and bundle is complete.

    codecopy.audit_literals must recompute eligible ranges from this build's
    derive manifest and each base file directory. Missing support fails closed.
    """
    release = Path(release)
    (release / 'literal-gate.json').unlink(missing_ok=True)
    try:
        import codecopy
    except ModuleNotFoundError as exc:
        raise GateFailure('codecopy.audit_literals is required: refusing an unchecked package') from exc
    probe = getattr(codecopy, 'audit_literals', None)
    if probe is None:
        raise GateFailure('codecopy.audit_literals is required: refusing an unchecked package')
    if (manifest.get('provisional_audit_only') or manifest.get('format') != 3
            or not manifest.get('bases') or not manifest.get('variants')
            or any(not output_keys_complete(v.get('outputs', {}), manifest) or 'holes' not in v
                   for v in manifest['variants'].values())
            or any(not (release/name).is_file() for name in ('dwpatch.py', 'isowriter.py'))):
        raise GateFailure('publication gate requires a complete final manifest and shipped runtime files')
    mapping_data = mapping_chunks(release)
    chunks = list(mapping_data)
    original_findings = []
    patch_hashes = {}
    delta_audits = {}
    for name, variant in manifest['variants'].items():
        raw = audit.dw.read_patch_file(str(release), variant)
        patch_hashes[name] = hashlib.sha1(raw).hexdigest()
        payload = audit.dw.read_payload3(raw)
        validate_blob(payload)
        chunks.extend(payload_chunks(payload, name))
        source_sizes = {}
        for key, path in (base_paths.items() if payload.get('deltas') else []):
            image = audit.iw.Image(str(path))
            try:
                source_sizes[key] = {delta['bases'][key]['source']: len(image.read(delta['bases'][key]['source']))
                                     for delta in payload.get('deltas', [])}
                for entry in payload.get('deltas', []):
                    delta = entry['bases'][key]
                    data, _ = audit.dw.binary_delta_source(delta, image.read)
                    audit.dw.validate_linker_copies(entry, delta, len(data), payload['blob'])
            finally:
                image.f.close()
        chunks.extend(outside_source_chunks(payload, name, source_sizes))
        plan = (plans or {}).get(name)
        options = selected_plan_options(probe, payload, Path(build_dirs[name]), base_paths, plan)
        for row in probe(payload, Path(build_dirs[name]), base_paths, **options):
            original_findings.append(dict(row, variant=name))
        if payload.get('deltas'):
            import delta_audit
            delta_audits[name] = delta_audit.inspect(payload, build_dirs[name], base_paths,
                dict(spec.split('=', 1) for spec in (source_discs or [])), plan)
    paths = list(base_paths.values()) + [spec.split('=', 1)[1] for spec in (source_discs or [])]
    sources = source_inventory(paths)
    mappings = complete_mapping_provenance(mapping_data, canonical_mapping_matches(release, sources, base_paths['us']))
    inputs = dict(manifest_sha1=hashlib.sha1(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                  patches=patch_hashes,
                  plans={name: hashlib.sha1(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                         for name, plan in (plans or {}).items() if plan is not None},
                  json_files={str(path.relative_to(release)): audit.digest(path)
                              for folder in ('bases', 'bundle') for path in sorted((release/folder).rglob('*.json'))},
                  generator_resources={str(path.relative_to(release)): audit.digest(path)
                                       for path in sorted((release/'bundle').rglob('*.csv'))},
                  runtime={name: audit.digest(release/name) for name in ('dwpatch.py', 'isowriter.py', 'fontcopy.py', 'discformats.py')
                           if (release/name).exists()},
                  audit_tools={name: audit.digest(Path(__file__).with_name(name)) for name in
                               ('literal_gate.py', 'literal_audit.py', 'literal_scan.cpp', 'codecopy.py',
                                'datacopy.py', 'delta_audit.py', 'bufferdata.py', 'buffers.json', 'linkerdata.py', 'fontcopy.py', 'tabledata.py', 'ui-sources.json', 'sdk-messages.json')})
    return check(chunks, sources, original_findings, release / 'literal-gate.json', mappings, inputs, delta_audits)
