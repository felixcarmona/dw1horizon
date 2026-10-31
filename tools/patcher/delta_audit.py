"""Inspect reconstructed data, rather than equating subtraction with provenance.

The low-similarity threshold is diagnostic, not an ownership test. Inherited data
without an exact witness on the selected player's inputs fails closed. Licensed
fonts and authored symbols are reported separately. Coordinates come from the
current linker maps and delta controls, never a release-specific table.
"""
from collections import Counter
import bisect
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess


def sections(build, plan):
    build = Path(build)
    paths = {'SLUS_010.32': ('en', 'SLUS_010.32')}
    for value in plan.get('LANG_OVL', []):
        lang, source, target = value.split(':')
        paths['SCN/' + target] = (lang, source)
    maps = {}
    for folder in sorted(build.glob('exe*')):
        path = folder / 'SLUS_010.32.elf.map'
        if not path.is_file():
            continue
        lang = folder.name[4:] if folder.name.startswith('exe-') else 'en'
        rows = []
        output, base = None, 0
        text = re.sub(r'( \.[\w.]+)\n\s+(0x)', r'\1 \2', path.read_text())
        for line in text.splitlines():
            match = re.match(r'^\.(\w+)\s+0x([\da-f]+)\s+0x[\da-f]+', line)
            if match:
                name, base = match[1], int(match[2], 16)
                output = 'SLUS_010.32' if name in ('main', 'header') else name + '_REL.BIN' if name.isupper() else None
            word = re.match(r'\s+0x([\da-f]+)\s+0x4\s+LONG\s+0x([\da-f]+)\b', line)
            if word and output:
                offset = int(word[1], 16) - (0x80090000 if output == 'SLUS_010.32' else base)
                if offset >= 0:
                    rows.append(dict(output=output, offset=offset, length=4, section='.linker.LONG',
                                     source='linker', value=int(word[2], 16)))
            match = re.match(r' (\.(?:text|rodata|data|sdata)[\w.]*)\s+0x([\da-f]+)\s+0x([\da-f]+)\s+(\S+\.o)\s*$', line)
            if not match or not output:
                continue
            section, address, size, obj = match.groups()
            offset = int(address, 16) - (0x80090000 if output == 'SLUS_010.32' else base)
            if offset >= 0 and int(size, 16):
                rows.append(dict(output=output, offset=offset, length=int(size, 16), section=section,
                                 source=obj.split('/gcc/')[-1][:-2]))
                if lang == 'en' and output.endswith('_REL.BIN'):
                    paths.setdefault(output, ('en', output))
        # Assembly data maps contain whole library sections. Sized ELF labels
        # supply smaller natural recipe objects without dropping coarse audit
        # coverage or treating unnamed gaps as generated data.
        elf = folder / 'SLUS_010.32.elf'
        if elf.is_file():
            import linkerdata
            labels = linkerdata.objects(elf)
            for row in rows:
                if not row['source'].startswith('asm/') or '/data/' not in row['source']:
                    continue
                output = '.main' if row['output'] == 'SLUS_010.32' else '.' + row['output'].removesuffix('_REL.BIN')
                members = [dict(offset=a, length=n, section=row['section'] + '.' + name, source=row['source'])
                           for a, n, name in labels.get(output, [])
                           if row['offset'] <= a and a + n <= row['offset'] + row['length']]
                if members:
                    row['members'] = members
        maps[lang] = rows
    if 'en' not in maps:
        raise ValueError('delta provenance requires the current English linker map')
    return {file: [dict(row) for row in maps.get(lang, maps['en']) if row['output'] == source]
            for file, (lang, source) in paths.items()}


def similarity_index(delta):
    spans = []
    pos = dp = 0
    for n, extra, seek in delta['control']:
        if n:
            spans.append((pos, pos + n, delta['diff'][0] + dp))
        if extra:
            spans.append((pos + n, pos + n + extra, None))
        pos += n + extra
        dp += n
    return spans, [hi for _, hi, _ in spans]


def region_similarity(delta, blob, offset, length, index=None):
    """Count equal old/new bytes within real diff spans, and expose extras too."""
    equal = covered = extras = 0
    end = offset + length
    spans, ends = index if index is not None else similarity_index(delta)
    i = bisect.bisect_right(ends, offset)
    while i < len(spans) and spans[i][0] < end:
        start, stop, dp = spans[i]
        lo, hi = max(offset, start), min(end, stop)
        if dp is None:
            extras += hi - lo
        else:
            equal += blob[dp + lo - start:dp + hi - start].count(0)
            covered += hi - lo
        i += 1
    return dict(diff_bytes=covered, equal_bytes=equal, extra_bytes=extras,
                low_similarity=covered >= 16 and equal * 4 < covered)


def unchanged_witnesses(delta, blob, target, original, source_regions=None):
    """Exact witnesses supplied by zero diff bytes, including sub-seed runs.

    A zero difference only copies a player byte when its source is in bounds.
    Verify the actual input bytes as well: controls or source metadata alone
    cannot establish provenance. Each returned interval is in target coordinates.
    """
    pos = oldpos = diffpos = 0
    spans = []
    for n, extra, seek in delta['control']:
        lo, hi = max(0, -oldpos), min(n, len(original) - oldpos)
        start = None
        for i in range(lo, hi):
            equal = (blob[delta['diff'][0] + diffpos + i] == 0
                     and target[pos + i] == original[oldpos + i])
            if equal and start is None:
                start = i
            if start is not None and (not equal or i + 1 == hi):
                end = i if not equal else i + 1
                spans.append([pos + start, pos + end, delta['source'], oldpos + start])
                start = None
        pos += n + extra
        oldpos += n + seek
        diffpos += n
    if source_regions is None:
        return spans
    result = []
    for lo, hi, _, offset in spans:
        for start, end, source, source_offset in source_regions:
            a, b = max(offset, start), min(offset + hi - lo, end)
            if b > a:
                result.append([lo + a - offset, lo + b - offset, source, source_offset + a - start])
    return result


def stored_information(delta, blob, target, ranges):
    """Measure stored delta bytes at output ranges; never an approval heuristic.

    Nonzero subtraction carries information even when it is not a literal.
    Equality with output is especially useful for finding subtraction from zero.
    Counts describe positions across bases, not unique compressed patch bytes.
    """
    counts = Counter(diff_bytes=0, nonzero_diff_bytes=0,
                     nonzero_diff_equal_output=0, extra_bytes=0)
    pos = dp = 0
    # Zero-copy witnesses can leave thousands of tiny holes in a large buffer.
    # Visit only holes intersecting this control, rather than multiplying the
    # number of holes by the number of controls.
    ranges = sorted(ranges)
    ends = [a + size for a, size in ranges]
    for n, extra, seek in delta['control']:
        i = bisect.bisect_right(ends, pos)
        while i < len(ranges) and ranges[i][0] < pos + n + extra:
            a, size = ranges[i]
            lo, hi = max(a, pos), min(a + size, pos + n)
            if hi > lo:
                data = blob[delta['diff'][0] + dp + lo - pos:delta['diff'][0] + dp + hi - pos]
                counts['diff_bytes'] += hi - lo
                counts['nonzero_diff_bytes'] += len(data) - data.count(0)
                counts['nonzero_diff_equal_output'] += sum(x != 0 and x == y for x, y in zip(data, target[lo:hi]))
            counts['extra_bytes'] += max(0, min(a + size, pos + n + extra) - max(a, pos + n))
            i += 1
        pos += n + extra
        dp += n
    return dict(counts)


def intersect(spans, ends, a, b):
    """Clip sorted nonoverlapping witnesses, retaining their source coordinates."""
    i = bisect.bisect_right(ends, a)
    while i < len(spans) and spans[i][0] < b:
        lo, hi, source, off = spans[i]
        left, right = max(a, lo), min(b, hi)
        if right > left:
            yield [left, right, source, off + left - lo]
        i += 1


def inspect(payload, build, bases, secondary, plan=None):
    import datacopy
    import dwpatch as dw
    def source_data(delta, image):
        try:
            return dw.binary_delta_source(delta, image.read)
        except dw.PatchError as exc:
            raise ValueError(str(exc)) from exc
    if not payload.get('deltas'):
        return dict(classes={}, regions=[], unavailable_bytes_by_base={}, unavailable=[])
    build = Path(build)
    if plan is None:
        plan = json.loads((build / 'derived/manifest.json').read_text())['plan']
    mapped = sections(build, plan)
    # Source identifiers distinguish additions from inherited tables; this is
    # deliberately conservative, as in literal_provenance.py.
    repo = Path(__file__).resolve().parents[2]
    pin = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD:decomp'], text=True).strip()
    archive = subprocess.check_output(['git', '-C', str(repo / 'decomp'), 'grep', '-h', '-I', '-e', '.', pin, '--', 'src'], text=True)
    identifiers = set(re.findall(r'\b[A-Za-z_]\w*\b', archive))
    banks = set()
    for path in build.glob('text-bank-*.json'):
        banks.update(key.split('.', 1)[-1] for key in json.loads(path.read_text()).get('text', {}))
    regions, classes, query, ranges = [], Counter(), bytearray(), []
    controls = []
    targets = {}
    regional_targets = {key: {} for key in bases}
    # An exact witness for the USA result cannot certify different regional
    # bytes. Reconstruct and validate every selected base before source search.
    for key, path in bases.items():
        image = dw._iw().Image(str(path))
        try:
            for entry in payload['deltas']:
                delta = entry['bases'][key]
                original, _ = source_data(delta, image)
                regional_targets[key][entry['file']] = dw.apply_binary_delta(
                    entry, key, image.read, payload['blob'])
        finally:
            image.f.close()
    image = dw._iw().Image(str(bases['us']))
    try:
        for index, entry in enumerate(payload['deltas']):
            target = dw.apply_binary_delta(entry, 'us', image.read, payload['blob'])
            targets[entry['file']] = target
            similarities = {key: similarity_index(delta) for key, delta in entry['bases'].items()}
            for key, delta in entry['bases'].items():
                oldpos = newpos = diffpos = 0
                for n, extra, seek in delta['control']:
                    equal = payload['blob'][delta['diff'][0] + diffpos:delta['diff'][0] + diffpos + n].count(0)
                    if n >= 16 and equal * 4 < n:
                        controls.append(dict(file=entry['file'], base=key, source=delta['source'],
                            offset=newpos, source_offset=oldpos, length=n, equal_bytes=equal))
                    newpos += n + extra
                    oldpos += n + seek
                    diffpos += n
            rows = mapped.get(entry['file'], [])
            generated = build / 'lang' / Path(entry['file']).name
            if entry['file'].startswith('SCN/LANG') and generated.is_file() and generated.read_bytes() == target:
                classes['a'] += len(target)
                continue
            # Nonzero map gaps and newly introduced program formats must not be
            # silently exempted just because no symbol names them yet.
            cursor = 0
            complete = []
            for row in sorted(rows, key=lambda row: row['offset']):
                if row['offset'] > cursor:
                    complete.append(dict(offset=cursor, length=row['offset']-cursor,
                                         section='.unmapped', source='unmapped'))
                complete.append(row)
                cursor = max(cursor, row['offset'] + row['length'])
            if cursor < len(target):
                complete.append(dict(offset=cursor, length=len(target)-cursor,
                                     section='.unmapped', source='unmapped'))
            for row in complete:
                row = dict(row, file=entry['file'], delta=index)
                name = row['section'].split('.', 2)[-1].split('.')[0]
                if row['offset'] + row['length'] > len(target):
                    raise ValueError('linker section exceeds reconstructed delta output')
                if row['section'] == '.linker.LONG':
                    # Current GNU map LONGs are linker expressions, not inherited
                    # object data. Bind the expression's evaluated value to the
                    # reconstructed bytes; edited/stale maps cannot clear them.
                    category = 'a' if target[row['offset']:row['offset'] + 4] == struct.pack('<I', row['value']) else 'd'
                elif row['section'] == '.unmapped':
                    category = 'd' if any(target[row['offset']:row['offset'] + row['length']]) else 'a'
                elif row['section'].startswith('.text'):
                    category = 'b' if name in identifiers or row['source'].startswith('asm/') else 'a'
                elif name.startswith('JAPANESE_') and row['source'] == 'src/main/font.c':
                    category = 'e'
                elif name.startswith(('LATIN_GLYPH_', 'LATIN_ROW_')) and row['source'] == 'src/main/font.c':
                    category = 'd'
                elif name in banks or name in ('FILE_OFFSET_TABLE', 'MOD_VERSION_TEXT'):
                    category = 'a'
                elif '_bss_' in row['source'] or name in identifiers or row['source'].startswith('asm/'):
                    category = 'b'
                else:
                    category = 'a'
                row['category'] = category
                classes[category] += row['length']
                row['bases'] = {key: region_similarity(delta, payload['blob'], row['offset'], row['length'], similarities[key])
                                for key, delta in entry['bases'].items()}
                data = target[row['offset']:row['offset'] + row['length']]
                row['sha1'] = hashlib.sha1(data).hexdigest()
                # Inspect inherited data even if alignment masks a poor match.
                if category == 'd' or (category == 'b' and not row['section'].startswith('.text')):
                    row['query_offset'] = len(query)
                    row['query_offsets_by_base'] = {}
                    distinct = {}
                    for key in bases:
                        data = regional_targets[key][entry['file']][row['offset']:row['offset'] + row['length']]
                        if data not in distinct:
                            distinct[data] = len(query)
                            ranges.append((len(query), len(data)))
                            query.extend(data)
                        row['query_offsets_by_base'][key] = distinct[data]
                regions.append(row)
    finally:
        image.f.close()
    # Metadata alone is not provenance: freshly rediscover every expression
    # from this build's ELF relocations and check the actual zero-copy controls.
    import linkerdata
    linked = linkerdata.words(build, mapped, targets, plan) if any(
        entry.get('linker_words') for entry in payload['deltas']) else {}
    generated = {}
    for index, entry in enumerate(payload['deltas']):
        expected = {tuple(row) for row in linked.get(entry['file'], [])}
        declared = entry.get('linker_words', [])
        if any(tuple(row) not in expected for row in declared):
            raise ValueError('generated linker word lacks current ELF relocation evidence')
        generated[index] = [[row[0], row[0] + 4, '@linker:' + row[1], 4 * i]
                            for i, row in enumerate(declared)]
        if entry.get('font_layout'):
            import fontcopy
            layout = fontcopy.native_layout(mapped.get(entry['file'], []), targets[entry['file']], None)
            if entry['file'] != 'SLUS_010.32' or entry['font_layout'] != layout:
                raise ValueError('generated font layout lacks current linker evidence')
            for key, path in bases.items():
                image = dw._iw().Image(str(path))
                try:
                    original = image.read(entry['bases'][key]['source'])
                    tail = fontcopy.generated_tail(layout, original, key)
                    output = dw.apply_binary_delta(entry, key, image.read, payload['blob'])
                finally:
                    image.f.close()
                cursor = 0
                for offset, name, size in layout:
                    if output[offset:offset + size] != tail[cursor:cursor + size]:
                        raise ValueError('regional font output differs from its player-side generator')
                    cursor += size
            generated[index].extend([offset, offset + size, '@font:' + name, 0]
                                    for offset, name, size in layout)
            generated[index].sort()

    if any(entry.get('table_recipes') for entry in payload['deltas']):
        import tabledata
        images = {key: dw._iw().Image(str(path)) for key, path in bases.items()}
        try:
            for index, entry in enumerate(payload['deltas']):
                recipes = entry.get('table_recipes', [])
                tabledata.verify(recipes, mapped.get(entry['file'], []), linked.get(entry['file'], []),
                                 targets[entry['file']], images,
                                 {key: files[entry['file']] for key, files in regional_targets.items()})
                generated[index].extend([offset, offset + size, '@table', 0]
                                        for offset, size in tabledata.layout(recipes))
                generated[index].sort()
        finally:
            for image in images.values():
                image.f.close()

    generated_ends = {index: [hi for _, hi, *_ in spans] for index, spans in generated.items()}
    matches = datacopy.find_sources(bytes(query), ranges, bases, secondary)
    # The 16-byte scanner cannot seed a complete 12--15-byte inherited object.
    # Reuse the data lane's map-driven whole-record search for precisely those
    # records, rather than calling a short, witnessed USA object unavailable.
    import bufferdata
    context, starts = bytearray(), {}
    for file, data in targets.items():
        starts[file] = len(context)
        context.extend(data)
    short = [row for row in regions if 'query_offset' in row and '_bss_' in row['source'] and 12 <= row['length'] < 16]
    supplements, records = bufferdata.supplemental(bytes(context), starts, short,
        {key: [] for key in bases}, bases, secondary, build) if short else ({}, [])
    for row in short:
        a, b = starts[row['file']] + row['offset'], starts[row['file']] + row['offset'] + row['length']
        for key, spans in supplements.items():
            for lo, hi, view, off in spans:
                lo2, hi2 = max(a, lo), min(b, hi)
                if hi2 > lo2:
                    # These supplemental searches use the USA object. A changed
                    # regional object needs its own bytes, not a USA witness.
                    begin = row['offset'] + lo2 - a
                    end = begin + hi2 - lo2
                    if regional_targets[key][row['file']][begin:end] != targets[row['file']][begin:end]:
                        continue
                    q = row['query_offsets_by_base'][key]
                    span = [q + lo2-a, q + hi2-a, view, off + lo2-lo]
                    matches[key] = datacopy.merge_spans(matches[key], [span])
    # The broad scanner needs a seed. Zero diff runs already identify an exact
    # source location, so short runs need no search or arbitrary byte palette.
    # Read each base's actual source and bind it to the delta's existing pin.
    unchanged = {}
    for key, path in bases.items():
        image = dw._iw().Image(str(path))
        try:
            for index, entry in enumerate(payload['deltas']):
                delta = entry['bases'][key]
                original, source_regions = source_data(delta, image)
                dw.validate_linker_copies(entry, delta, len(original), payload['blob'])
                unchanged[index, key] = unchanged_witnesses(
                    delta, payload['blob'], regional_targets[key][entry['file']], original, source_regions)
        finally:
            image.f.close()
    unchanged_ends = {key: [hi for _, hi, *_ in spans] for key, spans in unchanged.items()}
    match_ends = {key: [hi for _, hi, *_ in spans] for key, spans in matches.items()}
    unavailable, totals = [], Counter()
    for row in regions:
        if 'query_offset' not in row:
            continue
        for key, spans in matches.items():
            a = row['query_offsets_by_base'][key]
            b = a + row['length']
            copies = []
            witnesses = list(intersect(unchanged[row['delta'], key], unchanged_ends[row['delta'], key],
                                      row['offset'], row['offset'] + row['length']))
            for lo, hi, source, off in witnesses:
                copies.append([a + lo - row['offset'], a + hi - row['offset'], source, off])
            linker_witnesses = list(intersect(generated[row['delta']],
                generated_ends[row['delta']], row['offset'], row['offset'] + row['length']))
            spans = datacopy.merge_spans(list(intersect(spans, match_ends[key], a, b)), copies)
            disc_bytes = sum(hi - lo for lo, hi, *_ in spans)
            copies = []
            for lo, hi, source, off in linker_witnesses:
                copies.append([a + lo - row['offset'], a + hi - row['offset'], source, off])
            spans = datacopy.merge_spans(spans, copies)
            available = sum(max(0, min(b, hi) - max(a, lo)) for lo, hi, *_ in spans)
            missing = b - a - available
            row['bases'][key].update(exact_source_bytes=disc_bytes, generated_linker_bytes=available - disc_bytes,
                                    unverified_source_bytes=missing,
                                    zero_diff_witnesses=witnesses, linker_witnesses=linker_witnesses)
            if missing and (row['category'] == 'd' or '_bss_' in row['source']
                            or linker_witnesses or row['bases'][key]['low_similarity']):
                gaps, cursor = [], a
                for lo, hi, *_ in spans:
                    lo, hi = max(a, lo), min(b, hi)
                    if hi <= lo:
                        continue
                    if lo > cursor:
                        gaps.append([row['offset'] + cursor - a, lo - cursor])
                    cursor = max(cursor, hi)
                if cursor < b:
                    gaps.append([row['offset'] + cursor - a, b - cursor])
                unavailable.append(dict(file=row['file'], base=key, offset=row['offset'],
                    length=row['length'], unverified_bytes=missing, section=row['section'], source=row['source'],
                    sha1=row['sha1'], category=row['category'], unverified_ranges=gaps, **row['bases'][key]))
                unavailable[-1]['stored_information'] = stored_information(
                    payload['deltas'][row['delta']]['bases'][key], payload['blob'], regional_targets[key][row['file']], gaps)
                totals[key] += missing
    return dict(policy='current linker data objects; exact 16-byte witnesses or source-pinned zero-diff copies on each selected four-disc input set; '
                       'low similarity means fewer than 25% equal bytes in a diff span of at least 16 bytes; '
                       'mixed fonts and inherited buffer objects always require verified sources',
                classes=dict(classes), regions=regions, low_similarity_controls=controls,
                short_buffer_objects=records,
                maps_sha1={path.relative_to(build).as_posix(): hashlib.sha1(path.read_bytes()).hexdigest()
                           for path in sorted(build.glob('exe*/SLUS_010.32.elf.map'))},
                text_banks_sha1={path.relative_to(build).as_posix(): hashlib.sha1(path.read_bytes()).hexdigest()
                                for path in sorted(build.glob('text-bank-*.json'))},
                elf_sha1={path.relative_to(build).as_posix(): hashlib.sha1(path.read_bytes()).hexdigest()
                          for path in sorted(build.glob('exe*/SLUS_010.32.elf'))},
                decomp_pin=pin,
                unavailable_bytes_by_base=dict(totals), unavailable=unavailable)
