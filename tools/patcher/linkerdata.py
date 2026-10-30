"""Discover address words from this build's retained ELF32 MIPS relocations.

Only R_MIPS_32 words pointing inside an allocated linked section qualify.
The emitted recipe is section address plus section-relative offset; no table
payload is inferred from a pointer-shaped integer or from byte similarity.
"""
from pathlib import Path
import struct


def payload_copies(objects, words, target, original):
    """Locate complete pointer-bearing objects, masking only relocated words.

    At least 16 non-pointer bytes from the same natural linker object must
    agree at one corresponding source layout. This is a whole-record witness,
    never a dictionary of isolated small integers or arbitrary byte fragments.
    If a coarse assembly object has no match, try its current ELF's sized
    records independently. Their short fields still need 16 matching bytes
    together, in the same record layout; relocated words remain excluded.
    Return exact source spans for the non-pointer fields only.
    """
    copies = []
    for obj in objects:
        start, length = obj['offset'], obj['length']
        if obj['section'].startswith('.text') or '_bss_' in obj['source']:
            continue
        pointers = [row[0] for row in words if start <= row[0] and row[0] + 4 <= start + length]
        if not pointers:
            continue
        fields, cursor = [], start
        for offset in pointers:
            if cursor < offset:
                fields.append((cursor, offset))
            cursor = offset + 4
        if cursor < start + length:
            fields.append((cursor, start + length))
        if sum(hi - lo for lo, hi in fields) < 16:
            continue
        # Use the longest non-pointer field only to enumerate candidates. Every
        # remaining field is checked, at its original record-relative position.
        lo, hi = max(fields, key=lambda field: (field[1] - field[0], target[field[0]:field[1]]))
        anchor = target[lo:hi]
        at = original.find(anchor)
        while at >= 0:
            source = at - (lo - start)
            if (0 <= source and source + length <= len(original)
                    and all(original[source + a - start:source + b - start] == target[a:b]
                            for a, b in fields)):
                copies.extend([a, b - a, source + a - start] for a, b in fields)
                break
            at = original.find(anchor, at + 1)
        if at < 0 and obj.get('members'):
            copies.extend(payload_copies(obj['members'], words, target, original))
    # ELF aliases can describe overlapping records. Keep exact copies once,
    # clipping overlaps so the delta rewriter sees disjoint destination spans.
    result, end = [], 0
    for start, size, source in sorted(copies):
        lo = max(start, end)
        if lo < start + size:
            result.append([lo, start + size - lo, source + lo - start])
            end = start + size
    return result


def relocations(path):
    data = Path(path).read_bytes()
    if (len(data) < 52 or data[:7] != b'\x7fELF\x01\x01\x01'
            or struct.unpack_from('<HH', data, 16) != (2, 8)):
        raise ValueError('linker data requires a linked ELF32 little-endian MIPS executable')
    offset = struct.unpack_from('<I', data, 32)[0]
    stride, count, names_index = struct.unpack_from('<3H', data, 46)
    if stride < 40 or offset + stride * count > len(data) or names_index >= count:
        raise ValueError('invalid ELF section table')
    sections = [struct.unpack_from('<10I', data, offset + i * stride) for i in range(count)]

    def contents(section):
        start, size = section[4:6]
        if start + size > len(data):
            raise ValueError('ELF section outside file')
        return data[start:start + size]

    names = contents(sections[names_index])

    def name(section):
        at = section[0]
        return names[at:names.index(b'\0', at)].decode('ascii')

    result = {}
    for rel in sections:
        if rel[1] != 9:
            continue
        if rel[7] >= count or rel[6] >= count or rel[9] != 8 or rel[5] % 8:
            raise ValueError('invalid ELF relocation section')
        target = sections[rel[7]]
        symbols = sections[rel[6]]
        if symbols[1] != 2 or symbols[9] != 16 or symbols[5] % 16:
            raise ValueError('invalid ELF symbol table')
        symbol_data = contents(symbols)
        target_data = contents(target)
        for at, info in struct.iter_unpack('<II', contents(rel)):
            if info & 255 != 2:  # R_MIPS_32
                continue
            index = info >> 8
            if index * 16 + 16 > len(symbol_data):
                raise ValueError('ELF relocation symbol outside table')
            _, value, _, _, _, section_index = struct.unpack_from('<IIIBBH', symbol_data, index * 16)
            if section_index == 0 or section_index >= count:
                continue  # undefined/absolute values are not section addresses
            source = sections[section_index]
            if not source[2] & 2 or not target[2] & 2:
                continue
            position = at - target[3]
            if position < 0 or position + 4 > len(target_data):
                raise ValueError('ELF relocation outside linked section')
            word, = struct.unpack_from('<I', target_data, position)
            addend = word - source[3]
            if not 0 <= addend < source[5]:
                continue  # includes linker size constants and one-past-end symbols
            position += target[3] - 0x80090000 if name(target) == '.main' else 0
            row = [position, name(source), source[3], addend]
            rows = result.setdefault(name(target), {})
            if position in rows and rows[position] != row:
                raise ValueError('conflicting ELF word relocations')
            rows[position] = row
    return {section: sorted(rows.values()) for section, rows in result.items()}


def words(build, mapped, targets, plan):
    """Bind linked relocations to current map data extents and target bytes."""
    build = Path(build)
    paths = {'SLUS_010.32': ('en', '.main')}
    for value in plan.get('LANG_OVL', []):
        lang, source, dest = value.split(':')
        paths['SCN/' + dest] = (lang, '.' + source.removesuffix('_REL.BIN'))
    for file in mapped:
        if file.endswith('_REL.BIN'):
            paths.setdefault(file, ('en', '.' + file.removesuffix('_REL.BIN')))
    cache, result = {}, {}
    for file, (lang, section) in paths.items():
        if file not in targets:
            continue
        folder = build / ('exe-' + lang)
        if not folder.exists():
            folder = build / 'exe'
        path = folder / 'SLUS_010.32.elf'
        if not path.is_file():
            continue  # absent relocation evidence cannot authorize generation
        if path not in cache:
            cache[path] = relocations(path)
        rows = []
        for row in cache[path].get(section, []):
            offset, _, address, addend = row
            # Main positions include the PS-X header; overlays are relative.
            owner = next((item for item in mapped.get(file, [])
                          if item['offset'] <= offset and offset + 4 <= item['offset'] + item['length']), None)
            if owner is None or owner['section'].startswith('.text') or '_bss_' in owner['source']:
                continue
            if targets[file][offset:offset + 4] != struct.pack('<I', address + addend):
                raise ValueError(f'{file}: linked word differs from target at {offset}')
            rows.append(row)
        if rows:
            result[file] = rows
    return result


def objects(path):
    """Sized data labels retained by the current ELF, grouped by output section.

    These refine assembly's coarse map objects for recipes. The auditor still
    checks the complete coarse objects, including all bytes between labels.
    """
    data = Path(path).read_bytes()
    if data[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('data labels require ELF32 little endian')
    at = struct.unpack_from('<I', data, 32)[0]
    stride, count, names_index = struct.unpack_from('<3H', data, 46)
    sections = [struct.unpack_from('<10I', data, at + i * stride) for i in range(count)]
    def contents(s):
        return data[s[4]:s[4] + s[5]]
    names = contents(sections[names_index])
    def string(raw, off):
        return raw[off:raw.index(b'\0', off)].decode('ascii')
    found = {}
    for table in sections:
        if table[1] != 2:
            continue
        strings = contents(sections[table[6]])
        for name, address, size, info, other, section in struct.iter_unpack('<IIIBBH', contents(table)):
            if not size or not 0 < section < count or not sections[section][2] & 2:
                continue
            output = sections[section]
            if not output[3] <= address < address + size <= output[3] + output[5]:
                continue
            label = string(strings, name)
            if not label or label.endswith('.NON_MATCHING'):
                continue
            section_name = string(names, output[0])
            offset = address - (0x80090000 if section_name == '.main' else output[3])
            found.setdefault(section_name, []).append((offset, size, label))
    return {key: sorted(set(rows)) for key, rows in found.items()}
