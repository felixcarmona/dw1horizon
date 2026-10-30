"""Developer-side per-file binary deltas; the player needs only dwpatch.py.

Control triples have BSDIFF40 semantics. Diff bytes are unsigned subtraction
modulo 256 against the player's corresponding file; only extras are literals.
No functions, addresses or release-specific byte ranges are recorded here.
"""
import bz2
import hashlib
import struct
from pathlib import Path
import json


def _signed(raw):
    n = int.from_bytes(raw, 'little')
    return -(n & ((1 << 63) - 1)) if n >> 63 else n


def _suffix_array(data):
    """Prefix doubling, used only if the optional developer bsdiff4 is absent."""
    order = list(range(len(data)))
    ranks = list(data)
    width = 1
    while width < len(data):
        key = lambda i: (ranks[i], ranks[i + width] if i + width < len(data) else -1)
        order.sort(key=key)
        updated = [0] * len(data)
        for a, b in zip(order, order[1:]):
            updated[b] = updated[a] + (key(a) != key(b))
        ranks = updated
        if ranks[order[-1]] == len(data) - 1:
            break
        width *= 2
    return order


def _python_delta(old, new):
    """Suffix-array exact-match bsdiff fallback, no native dependency.

    It favours exact matches rather than bsdiff4's approximate matching. Extra
    blocks are deliberately left visible to the same publication gate.
    """
    sa = _suffix_array(old)
    controls, diff, extra = [], bytearray(), bytearray()
    at = oldpos = pending = 0
    while at < len(new):
        lo, hi = 0, len(sa)
        # Compare at most the remaining target length (avoid copying old suffixes).
        while lo < hi:
            mid = (lo + hi) // 2
            source = sa[mid]
            size = min(len(old) - source, len(new) - at)
            common = 0
            while common + 32 <= size and old[source + common:source + common + 32] == new[at + common:at + common + 32]:
                common += 32
            while common < size and old[source + common] == new[at + common]:
                common += 1
            less = (len(old) - source < len(new) - at) if common == size else old[source + common] < new[at + common]
            if less:
                lo = mid + 1
            else:
                hi = mid
        best, where = 0, 0
        for i in (lo - 1, lo):
            if 0 <= i < len(sa):
                n, off = 0, sa[i]
                while off + n < len(old) and at + n < len(new) and old[off + n] == new[at + n]:
                    n += 1
                if n > best:
                    best, where = n, off
        if best < 8:
            at += 1
            continue
        controls.append([0, at - pending, where - oldpos])
        extra.extend(new[pending:at])
        controls.append([best, 0, 0])
        diff.extend(bytes(best))
        oldpos = where + best
        at += best
        pending = at
    if pending < len(new):
        controls.append([0, len(new) - pending, 0])
        extra.extend(new[pending:])
    return controls, bytes(diff), bytes(extra)


def _make_delta(old, new, *, native=True):
    """Uncompressed bsdiff control/diff/extra blocks, for the existing xz envelope."""
    if native:
        try:
            import bsdiff4
        except ImportError:
            pass
        else:
            raw = bsdiff4.diff(old, new)
            if raw[:8] != b'BSDIFF40':
                raise ValueError('unsupported bsdiff producer')
            nc, nd, size = (_signed(raw[i:i + 8]) for i in (8, 16, 24))
            if min(nc, nd) < 0 or size != len(new):
                raise ValueError('invalid bsdiff header')
            ctrl = bz2.decompress(raw[32:32 + nc])
            if len(ctrl) % 24:
                raise ValueError('invalid bsdiff controls')
            controls = [[_signed(ctrl[i + j:i + j + 8]) for j in (0, 8, 16)]
                        for i in range(0, len(ctrl), 24)]
            return controls, bz2.decompress(raw[32 + nc:32 + nc + nd]), bz2.decompress(raw[32 + nc + nd:])
    return _python_delta(old, new)


def _similar_source(old, data):
    """Find a nearby binary block by exact anchors, then score byte similarity.

    This is generic approximate bsdiff matching, independent of instructions,
    addresses and provenance. No match means the bytes remain literal extras.
    """
    from collections import Counter
    if len(data) < 16 or len(data) > len(old):
        return None
    votes = Counter()
    for pos in range(0, len(data) - 15, 64):
        anchor = data[pos:pos + 16]
        at = old.find(anchor)
        for _ in range(16):
            if at < 0:
                break
            start = at - pos
            if 0 <= start <= len(old) - len(data):
                votes[start] += 1
            at = old.find(anchor, at + 1)
    if not votes:
        return None
    candidates = [start for start, _ in votes.most_common(16)]
    at = max(candidates, key=lambda start: sum(a == b for a, b in zip(data, old[start:start + len(data)])))
    score = sum(a == b for a, b in zip(data, old[at:at + len(data)]))
    return at if score * 4 >= len(data) else None


def make_delta(old, new, *, native=True):
    """Prefer subtraction over an extra whenever a corresponding source exists.

    bsdiff's similarity heuristic often emits recompiled code as extras, even
    inside the old file's extent. Convert those spans to ordinary bsdiff diff
    controls against the same logical file offsets. This is whole-file binary
    differencing, with no address inference or one-byte dictionary. Beyond the
    source extent, anchor-based approximate matching may find another block in
    the same file. Unmatched bytes remain extras for the publication audit.
    """
    controls, diff, extra = _make_delta(old, new, native=native)
    out, differences, extras = [], bytearray(), bytearray()
    oldpos = newpos = di = ei = 0
    for n, count, seek in controls:
        if n:
            out.append([n, 0, 0])
            differences.extend(diff[di:di + n])
        di += n; oldpos += n; newpos += n
        at = 0
        source_cursor = oldpos
        while at < count:
            take = min(count - at, max(0, len(old) - newpos - at))
            source = newpos + at
            if not take:
                take = min(count - at, 4096)
                source = _similar_source(old, extra[ei + at:ei + at + take])
            if source is None:
                out.append([0, take, 0])
                extras.extend(extra[ei + at:ei + at + take])
            else:
                out.append([0, 0, source - source_cursor])
                differences.extend((a - b) & 255 for a, b in
                                   zip(extra[ei + at:ei + at + take], old[source:source + take]))
                out.append([take, 0, 0])
                source_cursor = source + take
            at += take
        if oldpos + seek != source_cursor:
            out.append([0, 0, oldpos + seek - source_cursor])
        oldpos += seek
        ei += count; newpos += count
    return out, bytes(differences), bytes(extras)


def generate_linker_words(control, diff, extra, source_size, words, copies=(), *, tail_size=None, original_source_size=None):
    """Replace only relocated address bytes with zero copies of evaluated words.

    The virtual source appends expressions after the pinned real source file.
    Original delta bytes at these positions are discarded, including extras.
    Remaining fields retain their original controls and provenance requirements.
    """
    out, differences, extras = [], bytearray(), bytearray()
    oldpos = newpos = dp = ep = cursor = wi = 0
    tail_size = 4 * len(words) if tail_size is None else tail_size
    source_limit = source_size if original_source_size is None else original_source_size
    if not 0 <= source_limit <= source_size:
        raise ValueError('invalid original source extent')
    spans = sorted([[row[0], 4, source_size + 4 * i] for i, row in enumerate(words)] + list(copies))
    if any(a + n > b for (a, n, _), (b, _, _) in zip(spans, spans[1:])):
        raise ValueError('overlapping generated/source-copy fields')

    def emit(kind, data, source):
        nonlocal cursor
        if kind == 'extra':
            out.append([0, len(data), 0])
            extras.extend(data)
        else:
            if cursor != source:
                out.append([0, 0, source - cursor])
            if out and out[-1][1:] == [0, 0] and out[-1][0]:
                out[-1][0] += len(data)
            else:
                out.append([len(data), 0, 0])
            differences.extend(data)
            cursor = source + len(data)

    for n, count, seek in control:
        for kind, length, block, start, source in (
                ('diff', n, diff, dp, oldpos), ('extra', count, extra, ep, 0)):
            at = 0
            while at < length:
                while wi < len(spans) and spans[wi][0] + spans[wi][1] <= newpos + at:
                    wi += 1
                offset = spans[wi][0] if wi < len(spans) else newpos + length
                if wi < len(spans) and offset <= newpos + at < offset + spans[wi][1]:
                    take = min(length - at, offset + spans[wi][1] - newpos - at)
                    emit('diff', bytes(take), spans[wi][2] + newpos + at - offset)
                else:
                    take = min(length - at, offset - newpos - at)
                    original = source + at
                    if kind == 'diff':
                        if original < source_limit:
                            take = min(take, source_limit - original)
                        else:
                            # Original bspatch padding is still zero; it must
                            # not start reading the appended expression tail.
                            original += source_size - source_limit + tail_size
                    emit(kind, block[start + at:start + at + take], original)
                at += take
            newpos += length
        dp += n; ep += count; oldpos += n + seek
    return out, bytes(differences), bytes(extras)


def extra_runs(payload):
    """Fresh audit rows for every extra extent, including each regional variant."""
    rows = []
    for k, entry in enumerate(payload.get('deltas', [])):
        for base, d in entry['bases'].items():
            pos, at = 0, d['extra'][0]
            for n, extra, seek in d['control']:
                if extra:
                    rows.append(dict(file=entry['file'], offset=pos + n, length=extra,
                                     blob_offset=at, base=base, delta=k,
                                     sha1=hashlib.sha1(payload['blob'][at:at + extra]).hexdigest()))
                pos += n + extra
                at += extra
    return rows


def audit_literals(payload, build_dir, base_paths, *, plan=None):
    """Compatibility query: literal-bearing files still eligible for a file delta.

    Recomputes from current payload and actual source directories, never a report.
    Original bytes in delta extras are checked separately by literal_audit.
    """
    import dwpatch
    images = {key: dwpatch._iw().Image(str(path)) for key, path in base_paths.items()}
    try:
        names = source_names(payload, build_dir, images, plan=plan)
        for file, ops in payload['files'].items():
            pos = 0
            for op in ops:
                if op[0] == 'l' and file in names:
                    yield dict(file=file, offset=pos, length=op[2])
                if op[0] != 's':
                    pos += op[2] if op[0] == 'l' else payload['code'][op[1]][2] if op[0] == 'r' else op[3]
    finally:
        for image in images.values():
            image.f.close()


def _build_plan(build_dir, plan=None):
    if plan is not None:
        return plan
    folder = Path(build_dir) / 'derived'
    if (folder / 'plan.json').exists():
        return json.loads((folder / 'plan.json').read_text())
    if (folder / 'manifest.json').exists():
        return json.loads((folder / 'manifest.json').read_text()).get('plan', {})
    return {}


def source_names(payload, build_dir, images, *, plan=None):
    """Resolve corresponding files using this build's derive manifest and discs."""
    candidates = {q: q for q in payload['files']}
    metadata = _build_plan(build_dir, plan)
    generated = set(metadata.get('authored', []))
    for item in metadata.get('LANG_OVL', []):
        _, original, target = item.split(':')
        candidates['SCN/' + target] = original
        generated.add('SCN/' + target)
    boots = {key: next(q for q, info in img.files.items()
                      if q.startswith(('SLUS_', 'SLES_', 'SLPS_')) and not info[2])
             for key, img in images.items()}
    result = {}
    for dest, source in candidates.items():
        names = {key: boots[key] if dest == 'SLUS_010.32' else source for key in images}
        if all(name in images[key].files for key, name in names.items()):
            result[dest] = names
        elif dest in generated and all(source not in img.files for img in images.values()):
            # A manifest-authored program file has no original counterpart.
            # Use the player's main executable as its whole-file delta base.
            result[dest] = dict(boots)
    return result


def propagate_regional_copies(payload, outputs, changed):
    """Pin aliases/slices of changed earlier outputs, including multiple hops."""
    aliases = {}
    for base, replacements in changed.items():
        for file, ops in payload['files'].items():
            if file in replacements or not any(op[0] == 'o' and op[1] in replacements for op in ops):
                continue
            data = bytearray(outputs[file])
            pos = 0
            for op in ops:
                if op[0] == 's':
                    raise ValueError('whole-file source mixed with copied output')
                length = op[2] if op[0] == 'l' else payload['code'][op[1]][2] if op[0] == 'r' else op[3]
                if op[0] == 'o' and op[1] in replacements:
                    piece = replacements[op[1]][op[2]:op[2] + length]
                    if len(piece) != length:
                        raise ValueError('regional output copy exceeds its earlier file')
                    data[pos:pos + length] = piece
                pos += length
            if pos != len(data):
                raise ValueError('regional copied output has incomplete coverage')
            replacements[file] = bytes(data)
            payload.setdefault('sha1_by_base', {}).setdefault(base, {})[file] = hashlib.sha1(data).hexdigest()
            aliases.setdefault(base, []).append(file)
    return aliases


def copy_files(payload, build_dir, outputs, images, say=lambda _: None, *, plan=None):
    """Replace literal-bearing files by per-base bsdiff against corresponding files."""
    plan = _build_plan(build_dir, plan)
    names = source_names(payload, build_dir, images, plan=plan)
    import delta_audit
    import linkerdata
    import fontcopy
    import tabledata
    import bufferdata
    mapped = delta_audit.sections(build_dir, plan) if any(Path(build_dir).glob('exe*/SLUS_010.32.elf.map')) else {}
    linked = linkerdata.words(build_dir, mapped, outputs, plan)
    # The build names its main executable as an authored program source. Growing
    # overlays can use that whole file as an alternate bsdiff base. Selection is
    # automatic and prioritises fewer literal extras, never a release table.
    main_sources = names.get('SLUS_010.32', {}) if 'SLUS_010.32' in plan.get('authored', []) else {}
    blob = bytearray(payload['blob'])
    entries = payload.setdefault('deltas', [])
    report = dict(files=[], literal_before=sum(op[2] for ops in payload['files'].values()
                                              for op in ops if op[0] == 'l'), bases={}, buffer_changes={}, generated_changes={})
    cache = {}
    regional_outputs = {}
    def store(data):
        if data not in cache:
            cache[data] = [len(blob), len(data)]
            blob.extend(data)
        return cache[data]
    for file, ops in list(payload['files'].items()):
        if file not in names or not any(op[0] == 'l' for op in ops):
            continue
        target = outputs[file]
        entry = dict(file=file, size=len(target), sha1=hashlib.sha1(target).hexdigest(), bases={})
        if linked.get(file):
            entry['linker_words'] = linked[file]
        font_layout = fontcopy.native_layout(mapped.get(file, []), target, None) if file == 'SLUS_010.32' else []
        if font_layout:
            entry['font_layout'] = font_layout
        table_sources = {key: {path: images[key].read(path)} for key, path in names[file].items()}
        recipes = tabledata.prepare(mapped.get(file, []), entry.get('linker_words', []), target, table_sources)
        if recipes:
            entry['table_recipes'] = recipes
        for base, source in names[file].items():
            old = images[base].read(source)
            control, diff, extra = make_delta(old, target)
            alternate = main_sources.get(base)
            if extra and alternate and alternate != source:
                candidate = images[base].read(alternate)
                if len(candidate) >= len(target):
                    other_control, other_diff, other_extra = make_delta(candidate, target)
                    if len(other_extra) < len(extra):
                        source, old = alternate, candidate
                        control, diff, extra = other_control, other_diff, other_extra
            regional, combined, additional, buffers, changes = bufferdata.player_buffers(
                mapped.get(file, []), target, base, images[base], source, old)
            copies = linkerdata.payload_copies(mapped.get(file, []), entry.get('linker_words', []), target, old)
            table_fields = tabledata.layout(recipes)
            copies = [span for span in copies if not any(a < span[0] + span[1] and span[0] < a + n
                                                       for a, n in table_fields)]
            copies.extend(buffers)
            tail_size = 4 * len(entry.get('linker_words', []))
            generated_changes = []
            if font_layout:
                font_tail = fontcopy.generated_tail(font_layout, old, base)
                regional_target = bytearray(regional)
                cursor = 0
                for offset, name, size in font_layout:
                    copies.append([offset, size, len(combined) + tail_size + cursor])
                    data = font_tail[cursor:cursor + size]
                    if data != target[offset:offset + size]:
                        generated_changes.append(dict(offset=offset, length=size, reason='player regional Latin font'))
                    regional_target[offset:offset + size] = data
                    cursor += size
                if base == 'us' and any(regional_target[a:a+n] != target[a:a+n] for a, _, n in font_layout):
                    raise ValueError('native Latin font differs from current player-side generator')
                regional = bytes(regional_target)
                digest = hashlib.sha1(regional).hexdigest()
                entry.setdefault('sha1_by_base', {})[base] = digest
                payload.setdefault('sha1_by_base', {}).setdefault(base, {})[file] = digest
                tail_size += len(font_tail)
            if recipes:
                table_tail = tabledata.tail(recipes, base, images[base].read)
                cursor = 0
                regional_target = bytearray(regional)
                for offset, size in tabledata.layout(recipes):
                    copies.append([offset, size, len(combined) + tail_size + cursor])
                    data = table_tail[cursor:cursor + size]
                    if data != target[offset:offset + size]:
                        generated_changes.append(dict(offset=offset, length=size, reason='player table payload and authored layout'))
                    regional_target[offset:offset + size] = data
                    cursor += size
                regional = bytes(regional_target)
                digest = hashlib.sha1(regional).hexdigest()
                entry.setdefault('sha1_by_base', {})[base] = digest
                payload.setdefault('sha1_by_base', {}).setdefault(base, {})[file] = digest
                tail_size += len(table_tail)
            if entry.get('linker_words') or copies:
                control, diff, extra = generate_linker_words(control, diff, extra, len(combined),
                    entry.get('linker_words', []), copies, tail_size=tail_size, original_source_size=len(old))
            entry['bases'][base] = dict(source=source, source_sha1=hashlib.sha1(old).hexdigest(),
                                       control=control, diff=store(diff), extra=store(extra))
            if additional:
                entry['bases'][base]['additional_sources'] = additional
            if changes:
                digest = hashlib.sha1(regional).hexdigest()
                entry.setdefault('sha1_by_base', {})[base] = digest
                payload.setdefault('sha1_by_base', {}).setdefault(base, {})[file] = digest
                report['buffer_changes'].setdefault(base, {})[file] = changes
            if generated_changes:
                report['generated_changes'].setdefault(base, {})[file] = generated_changes
            if regional != target:
                regional_outputs.setdefault(base, {})[file] = regional
            counts = report['bases'].setdefault(base, dict(diff=0, extra=0, files=0))
            counts['diff'] += len(diff); counts['extra'] += len(extra); counts['files'] += 1
        payload['files'][file] = [['b', len(entries), 0, len(target)]]
        entries.append(entry)
        report['files'].append(file)
        say(f'  binary delta: {file} ({len(target)} bytes, {len(images)} bases)')
    report['copied_buffer_files'] = propagate_regional_copies(payload, outputs, regional_outputs)
    # Compact all live literal + delta block extents. No dead original bytes survive.
    compact, spans = bytearray(), {}
    def move(pair):
        key = tuple(pair)
        if key not in spans:
            at, length = pair
            spans[key] = [len(compact), length]
            compact.extend(blob[at:at + length])
        return list(spans[key])
    for ops in list(payload['files'].values()) + [payload['license']]:
        for op in ops:
            if op[0] == 'l':
                op[1:3] = move(op[1:3])
    for entry in entries:
        for delta in entry['bases'].values():
            for block in ('diff', 'extra'):
                delta[block] = move(delta[block])
    payload['blob'] = bytes(compact)
    report['literal_after'] = sum(op[2] for ops in payload['files'].values() for op in ops if op[0] == 'l')
    return report
