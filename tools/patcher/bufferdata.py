"""Whole short buffer objects whose natural boundaries come from this build's map.

A record must be 12--15 bytes, in an inherited *_bss_* data object, and contain a
literal byte not already witnessed by the 16-byte scan. No arbitrary small
fragments, byte palettes or saved per-release ranges are searched here.
"""
import bisect
import collections
import json
import mmap
from pathlib import Path
import re


def player_buffers(objects, target, base, image, source, original, *, policy=None):
    """Copy complete inherited objects from the player's corresponding overlay.

    Coordinates describe original natural objects, not a dictionary of residue
    fragments. No incoming bytes are bundled. USA objects must still agree with
    their original layout; an edited/grown object requires a new review.
    The sole zero extension is the authored EVL shard scratch enlargement.
    """
    if policy is None:
        policy = json.loads(Path(__file__).with_name('buffers.json').read_text())
    if policy.get('version') != 1:
        raise ValueError('unsupported player buffer policy')
    selected = []
    for obj in objects:
        if '_bss_' not in obj['source'] or not obj['section'].startswith('.data.'):
            continue
        name = obj['section'][6:]
        spec = policy['objects'].get(name)
        if spec is None:
            continue  # New objects remain subject to the mandatory source gate.
        if obj['length'] != spec['length']:
            raise ValueError(f'{name}: player buffer layout changed; review required')
        selected.append((obj, name, spec))
    files = {spec['file'] for _, _, spec in selected}
    if len(files) > 1:
        raise ValueError('player buffer objects cross original overlays')
    data = bytearray(target)
    spans, additional, changes = [], [], []
    combined = original
    if not selected:
        return data, combined, additional, spans, changes
    file = next(iter(files))
    own = original if file == source else image.read(file)
    origin = 0 if file == source else len(original)
    if file != source:
        import hashlib
        additional.append(dict(file=file, size=len(own), sha1=hashlib.sha1(own).hexdigest()))
        combined += own
    zero_run = None
    for obj, name, spec in selected:
        a, n, count = obj['offset'], obj['length'], spec['copy_length']
        off = spec['offsets'][base]
        if (not 0 < count <= n or off < 0 or off + count > len(own)
                or a < 0 or a + n > len(target)):
            raise ValueError(f'{name}: player buffer outside its file')
        replacement = own[off:off + count] + bytes(n - count)
        if base == 'us' and replacement != target[a:a + n]:
            raise ValueError(f'{name}: USA buffer no longer matches the reviewed original object')
        spans.append([a, count, origin + off])
        if count < n:
            if name != 'EVL_D_80066274' or count != 5436 or any(target[a + count:a + n]):
                raise ValueError('unreviewed player buffer zero extension')
            if zero_run is None:
                runs = list(re.finditer(b'\0{16,}', combined))
                if not runs:
                    raise ValueError('no pinned zero source for authored buffer extension')
                longest = max(runs, key=lambda match: match.end() - match.start())
                zero_run = longest.start(), longest.end() - longest.start()
            pos = a + count
            while pos < a + n:
                take = min(zero_run[1], a + n - pos)
                spans.append([pos, take, zero_run[0]])
                pos += take
        if replacement != target[a:a + n]:
            import hashlib
            changes.append(dict(section=name, offset=a, length=n,
                before_sha1=hashlib.sha1(target[a:a + n]).hexdigest(),
                after_sha1=hashlib.sha1(replacement).hexdigest(),
                source=file, source_offset=off,
                reason='Retain the selected player disc buffer; discard inherited USA residue.'))
        data[a:a + n] = replacement
    return bytes(data), combined, additional, sorted(spans), changes


def objects(build, starts, runs):
    build = Path(build)
    plan_path = build / 'derived/plan.json'
    if not plan_path.exists():
        return []
    paths = {q: ('en', q) for q in starts if q.endswith('_REL.BIN') or q == 'SLUS_010.32'}
    for entry in json.loads(plan_path.read_text())['LANG_OVL']:
        lang, source, target = entry.split(':')
        paths['SCN/' + target] = (lang, source)
    maps = {}
    for lang in {lang for lang, _ in paths.values()}:
        folder = build / ('exe-' + lang)
        if not folder.exists():
            folder = build / 'exe'
        path = folder / 'SLUS_010.32.elf.map'
        if not path.exists():
            continue
        sections = collections.defaultdict(list)
        output = None
        base = 0
        text = re.sub(r'( \.[\w.]+)\n\s+(0x)', r'\1 \2', path.read_text())
        for line in text.splitlines():
            m = re.match(r'^\.(\w+)\s+0x([\da-f]+)\s+0x([\da-f]+)', line)
            if m:
                name, base = m[1], int(m[2], 16)
                output = 'SLUS_010.32' if name in ('main', 'header') else name + '_REL.BIN' if name.isupper() else None
            m = re.match(r' (\.data\.[\w.]+)\s+0x([\da-f]+)\s+0x([\da-f]+)\s+(\S+\.o)\s*$', line)
            if not m or not output or '_bss_' not in m[4]:
                continue
            length = int(m[3], 16)
            offset = int(m[2], 16) - (0x80090000 if output == 'SLUS_010.32' else base)
            if 12 <= length < 16 and offset >= 0:
                sections[output].append((offset, length, m[1]))
        maps[lang] = sections
    literals = collections.defaultdict(list)
    for run in runs:
        literals[run['file']].append((run['offset'], run['offset'] + run['length']))
    out = []
    for file, start in starts.items():
        if file not in paths:
            continue
        lang, source = paths[file]
        for offset, length, section in maps.get(lang, {}).get(source, []):
            if any(a < offset + length and b > offset for a, b in literals[file]):
                out.append(dict(file=file, offset=offset, start=start + offset, length=length, section=section))
    return out


def supplemental(blob, starts, runs, matches, bases, source_discs, build):
    """Find missing whole records on the actual inputs; return new context spans."""
    intervals = sorted((a, b) for spans in matches.values() for a, b, *_ in spans)
    merged = []
    for a, b in intervals:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(b, merged[-1][1])
        else:
            merged.append([a, b])
    ends = [b for _, b in merged]
    queries = []
    for obj in objects(build, starts, runs):
        a, n = obj['start'], obj['length']
        i = bisect.bisect_right(ends, a)
        if i < len(merged) and merged[i][0] <= a and merged[i][1] >= a + n:
            continue
        if a < 0 or a + n > len(blob):
            raise ValueError('buffer object outside the target context')
        queries.append(dict(obj, hits=[]))
    found = {}
    for secondary, discs in ((False, bases), (True, source_discs)):
        for key, path in discs.items():
            spans = []
            if queries:
                with open(path, 'rb') as file:
                    raw = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
                    # Language aliases often name the same initialized record.
                    # Search identical bytes once, retaining every object's own
                    # coordinates and witnesses in the result.
                    grouped = {}
                    for obj in queries:
                        a, n = obj['start'], obj['length']
                        grouped.setdefault(blob[a:a + n], []).append(obj)
                    missing = {}
                    try:
                        for data, members in grouped.items():
                            offset = raw.find(data)
                            if offset >= 0:
                                for obj in members:
                                    a, n = obj['start'], obj['length']
                                    spans.append([a, a + n, '@raw', offset])
                                    obj['hits'].append([key, '@raw', offset])
                            else:
                                missing[data] = members
                        # All non-boundary data-plane matches also occur in raw.
                        # Search only the sector joins still missing in raw.
                        for sector in range(1, len(raw) // 2352):
                            if not missing:
                                break
                            end = (sector - 1) * 2352 + 24 + 2048
                            start = sector * 2352 + 24
                            bridge = raw[end - 14:end] + raw[start:start + 14]
                            for data, members in list(missing.items()):
                                p = bridge.find(data)
                                if p >= 0:
                                    offset = sector * 2048 - 14 + p
                                    for obj in members:
                                        a, n = obj['start'], obj['length']
                                        spans.append([a, a + n, '@userdata', offset])
                                        obj['hits'].append([key, '@userdata', offset])
                                    del missing[data]
                    finally:
                        raw.close()
            found[secondary, key] = spans
    result = {}
    for key in bases:
        spans = list(found[False, key])
        for game in source_discs:
            spans.extend([a, b, f'@disc:{game}:' + view, offset]
                         for a, b, view, offset in found[True, game])
        result[key] = sorted(spans, key=lambda span: (span[0], span[1]))
    return result, queries
