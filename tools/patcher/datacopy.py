"""Build-time exact data copies from a base and the recipe's required source discs.

All ranges come from this build's literal operations/mapping data. The scanner
ships no game bytes and the emitted copies need only Python's standard library.
A 16-byte seed is required; extension can consume shorter surrounding fragments.
Unmatched bytes are retained for the publication gate to diagnose, never encoded
as byte dictionaries, XOR records or frozen per-release coordinates.
"""
import bisect
from pathlib import Path
import subprocess
import tempfile

import literal_audit as audit
import reloc


def merge_spans(primary, secondary):
    """Cover primary first, filling its gaps from secondary (both sorted/disjoint)."""
    spans = []
    stops = [s[1] for s in primary]
    for a, b, path, off in secondary:
        p = a
        i = bisect.bisect_right(stops, a)
        while i < len(primary) and primary[i][0] < b:
            lo, hi, *_ = primary[i]
            if p < lo:
                spans.append([p, min(lo, b), path, off + p - a])
            p = max(p, hi)
            i += 1
        if p < b:
            spans.append([p, b, path, off + p - a])
    return sorted(primary + spans)


def find_sources(blob, ranges, bases, source_discs=None, work=None):
    """{base: [(blob start,end,source view,offset)]}, fresh exact search per build.

    bases and source_discs are {id: image path}. Secondary discs are restricted
    by the caller to those already required by this recipe. Views are raw bytes
    and the complete sector-data plane (including DW3's hidden archives).
    """
    if not ranges:
        return {key: [] for key in bases}
    sources = dict(images=[], rows=[])
    identities = []
    for secondary, discs in ((False, bases), (True, source_discs or {})):
        for key, path in discs.items():
            i = len(sources['images'])
            sources['images'].append(str(path))
            sources['rows'].extend([[i, '@raw', 0, 0, 2], [i, '@userdata', 0, 0, 3]])
            identities.append((key, secondary))
    found = {}
    with tempfile.TemporaryDirectory(prefix='data-copy-', dir=work) as td:
        td = Path(td)
        (td / 'blob').write_bytes(blob)
        (td / 'ranges').write_text(''.join(f'{a}\t{n}\n' for a, n in ranges))
        subprocess.run(['c++', '-O3', '-std=c++17', str(Path(__file__).with_name('literal_scan.cpp')),
                        '-o', str(td / 'scan')], check=True)
        runs = [dict(blob_offset=a, length=n) for a, n in ranges]
        for i, (key, secondary) in enumerate(identities):
            rows = [2 * i, 2 * i + 1]
            (td / 'sources').write_text(''.join(
                f'{sources["images"][i]}\t{r}\t0\t0\t{sources["rows"][r][4]}\n' for r in rows))
            with (td / 'hits').open('w') as out:
                subprocess.run([str(td / 'scan'), str(td / 'blob'), str(td / 'ranges'), str(td / 'sources')],
                               stdout=out, stderr=subprocess.DEVNULL, check=True)
            hits = {}
            for line in (td / 'hits').read_text().splitlines():
                a, row, off = map(int, line.split())
                hits[a] = (rows[row], off)
            spans = audit.extend_matches(blob, runs, hits, sources)
            prefix = f'@disc:{key}:' if secondary else ''
            found[secondary, key] = [[a, b, prefix + sources['rows'][r][1], off] for a, b, r, off in spans]
    common = []
    for key in source_discs or {}:
        common = merge_spans(common, found[True, key])
    return {key: merge_spans(found[False, key], common) for key in bases}


def copy_payload(payload, bases, source_discs=None, work=None, targets=None, build=None):
    """Replace the all-base intersection with verified r copies; return audit counts.

    Whole target-file context supplies legitimate seeds across a short literal's
    boundaries. Only the intersection with literal operations is rewritten.
    """
    runs = audit.literal_runs(payload)
    before = len(payload['blob'])
    typed = []
    if targets is None:
        matches = find_sources(payload['blob'], [(r['blob_offset'], r['length']) for r in runs],
                               bases, source_discs, work)
    else:
        context = bytearray()
        starts, ranges = {}, []
        for q in dict.fromkeys(r['file'] for r in runs):
            starts[q] = len(context)
            data = targets[q]
            ranges.append((len(context), len(data)))
            context.extend(data)
        full = find_sources(bytes(context), ranges, bases, source_discs, work)
        if build is not None:
            import bufferdata
            supplements, typed = bufferdata.supplemental(bytes(context), starts, runs, full,
                                                         bases, source_discs or {}, build)
            for key, spans in supplements.items():
                # Prefer existing context witnesses, then one whole record at a time.
                for span in spans:
                    full[key] = merge_spans(full[key], [span])
        matches = {}
        for key, spans in full.items():
            ends = [s[1] for s in spans]
            projected = []
            for r in runs:
                a = starts[r['file']] + r['offset']
                b = a + r['length']
                i = bisect.bisect_right(ends, a)
                while i < len(spans) and spans[i][0] < b:
                    lo, hi, path, off = spans[i]
                    left, right = max(a, lo), min(b, hi)
                    projected.append([r['blob_offset'] + left - a,
                                      r['blob_offset'] + right - a, path, off + left - lo])
                    i += 1
            matches[key] = sorted(projected)
    available = {key: sum(b - a for a, b, *_ in spans) for key, spans in matches.items()}
    union = []
    for spans in matches.values():
        union = merge_spans(union, spans)
    any_disc = sum(b - a for a, b, *_ in union)
    union_ends = [s[1] for s in union]
    per_file = {}
    for row in runs:
        stats = per_file.setdefault(row['file'], dict(before=0, after=0, disc_matching_before=0))
        stats['before'] += row['length']
        a, b = row['blob_offset'], row['blob_offset'] + row['length']
        i = bisect.bisect_right(union_ends, a)
        while i < len(union) and union[i][0] < b:
            stats['disc_matching_before'] += min(b, union[i][1]) - max(a, union[i][0])
            i += 1
    saved = reloc.copy_literal_sources(payload, matches, minimum=1)
    for row in audit.literal_runs(payload):
        per_file[row['file']]['after'] += row['length']
    for stats in per_file.values():
        stats['copied'] = stats['before'] - stats['after']
        stats['disc_matching_after'] = stats['disc_matching_before'] - stats['copied']
    return dict(before=before, copied=saved, after=len(payload['blob']), available_by_base=available,
                available_after_by_base={key: n - saved for key, n in available.items()},
                disc_matching_before=any_disc, disc_matching_after=any_disc - saved, per_file=per_file,
                short_buffer_objects=typed)


def copy_mappings(mappings, bases, source_discs=None, work=None):
    """Remove matching mapping data, keeping unmatched extents visible to the gate.

    A disc_copy is [source view, offset, length]; an unprefixed view is the
    player's base disc. No import normalization recipe is modified here.
    """
    blob = bytearray()
    entries, ranges = {}, []
    for key, mp in mappings.items():
        image = audit.iw.Image(str(bases[key]))
        try:
            for path, entry in mp['files'].items():
                if not any('data' in op for op in entry.get('ops', [])):
                    continue
                source = entry['source']
                src = image.license() if source == 'license_data.dat' else image.read(source)
                target = audit.dw.apply_ops(entry['ops'], src)
                pos = len(blob)
                ranges.append((pos, len(target)))
                blob.extend(target)
                for i, op in enumerate(entry['ops']):
                    n = len(bytes.fromhex(op['data'])) if 'data' in op else op['copy'][1] if 'copy' in op else op['fill'][1]
                    if 'data' in op:
                        entries[key, path, i] = (pos, n)
                    pos += n
        finally:
            image.f.close()
    if not entries:
        return dict(before=0, copied=0, after=0, by_base={})
    matches = find_sources(bytes(blob), ranges, bases, source_discs, work)
    stats = {}
    for key, mp in mappings.items():
        spans = matches[key]
        starts = [s[0] for s in spans]
        before = copied = 0
        for path, entry in mp['files'].items():
            ops = []
            for i, op in enumerate(entry.get('ops', [])):
                if 'data' not in op:
                    ops.append(op)
                    continue
                a, n = entries[key, path, i]
                before += n
                stop = a + n
                p = a
                def literal(lo, hi):
                    if hi > lo:
                        ops.append(dict(data=blob[lo:hi].hex()))
                for j in range(max(0, bisect.bisect_right(starts, a) - 1), len(spans)):
                    lo, hi, view, off = spans[j]
                    if lo >= stop:
                        break
                    lo2, hi2 = max(a, lo), min(stop, hi)
                    if hi2 <= lo2:
                        continue
                    literal(p, lo2)
                    ops.append(dict(disc_copy=[view, off + lo2 - lo, hi2 - lo2]))
                    copied += hi2 - lo2
                    p = hi2
                literal(p, stop)
            if 'ops' in entry:
                entry['ops'] = ops
        stats[key] = dict(before=before, copied=copied, after=before - copied)
    return dict(before=sum(s['before'] for s in stats.values()), copied=sum(s['copied'] for s in stats.values()),
                after=sum(s['after'] for s in stats.values()), by_base=stats)


def copy_boot_config(payload, bases, targets):
    """Generate only the BOOT file-name field from this build's own file plan.

    All other bytes come from the player's own SYSTEM.CNF. Enable only when
    that structured rename reproduces the entire target on every supported
    base. This is a format operation, not an encoding of unavailable data.
    """
    filename = (payload.get('table') or {}).get('file')
    if not filename or 'SYSTEM.CNF' not in payload['files']:
        return dict(generated_literals=0, reason='No executable file plan')
    target = targets['SYSTEM.CNF']
    for key, path in bases.items():
        image = audit.iw.Image(str(path))
        try:
            if audit.dw.boot_config(image.read('SYSTEM.CNF'), filename) != target:
                return dict(generated_literals=0, reason=f'{key} has different BOOT settings')
        finally:
            image.f.close()
    removed = sum(op[2] for op in payload['files']['SYSTEM.CNF'] if op[0] == 'l')
    view = '@boot:' + filename
    if view not in payload['sources']:
        payload['sources'].append(view)
    k = len(payload['code'])
    payload['code'].append([payload['sources'].index(view), 0, len(target)])
    payload['files']['SYSTEM.CNF'] = [['r', k]]
    for key in bases:
        if key != 'us':
            payload['reloc'].setdefault(key, {})[str(k)] = [[view, 0, len(target)]]
    import types
    files = dict(payload['files'])
    files['\0license'] = payload['license']
    enc = types.SimpleNamespace(blob=payload['blob'], usa_lit=set())
    reloc.compact(enc, files)
    payload['license'] = files.pop('\0license')
    payload['files'], payload['blob'] = files, bytes(enc.blob)
    return dict(generated_literals=removed, output_bytes=len(target), executable=filename)
