"""Regenerate compact Latin arrays from player glyphs and our font sources.

No original glyph pixels live in this module. Source glyph ranges must be found
and verified against the current build's original input at package-build time.
Missing regional characters use our authored font, never shipped USA pixels.
"""
import struct


def generate(glyph_bytes, codes, fontgen):
    """{linker symbol: little-endian bytes}; caller supplies all 79 disc glyphs.

    fontgen is passed explicitly so a package can load its own bundled sources
    without depending on a developer checkout or optional image libraries.
    """
    if len(glyph_bytes) != 79 * 24 or len(codes) != 79:
        raise ValueError('expected 79 original 12x11 glyphs and their character codes')
    original = []
    for i in range(79):
        rows = struct.unpack_from('<12H', glyph_bytes, i * 24)
        original.append((rows[11], [''.join('.' if word & (0x8000 >> x) else '#' for x in range(12))
                                     for word in rows[:11]]))
    extra = fontgen.load_extra(include_japanese=False)
    base_b, extra_b = fontgen.font_tables('b', (list(codes), original))
    glyphs = [('?', width, rows) for width, rows in original]
    glyphs += extra
    glyphs += [('?', adv | original[i][0] << 8, rows) for i, (adv, rows) in enumerate(base_b)]
    glyphs += [(ch, adv | extra[i][1] << 8, rows) for i, (ch, adv, rows) in enumerate(extra_b[:len(extra)])]
    words, counts, offsets, bits = fontgen.japanese_huffman(glyphs, block=1, height=11)
    arrays = dict(LATIN_ROW_WORDS=words, LATIN_ROW_COUNTS=counts, LATIN_GLYPH_OFFSETS=offsets,
                  LATIN_GLYPH_WIDTHS=[w for _, w, _ in glyphs])
    out = {name: struct.pack(f'<{len(values)}H', *values) for name, values in arrays.items()}
    out['LATIN_GLYPH_BITS'] = bytes(bits)
    return out


def glyph_plan(original, executables):
    """Find each whole original glyph in each input executable, without fixed offsets.

    Return copy descriptors and exact missing glyph indices/byte counts per base.
    Equivalent rows may occur elsewhere in a table; equality is checked in full.
    """
    if len(original) != 79 * 24:
        raise ValueError('invalid original glyph table')
    plans = {}
    for key, exe in executables.items():
        sources, missing = [], []
        for i in range(79):
            glyph = original[i * 24:(i + 1) * 24]
            offset = exe.find(glyph)
            sources.append(None if offset < 0 else [offset, 24])
            if offset < 0:
                missing.append(i)
        plans[key] = dict(sources=sources, missing=missing, missing_bytes=len(missing) * 24)
    return plans


def prepare(payload, usa_exe, base_executables, map_path, fontgen):
    """Use linker extents and current input glyphs, and expose missing-source proof.

    All supported bases must supply every source glyph before any mixed table is
    removed. This prevents an apparently successful USA fix shipping hidden
    USA-only fallbacks in a seven-base package.
    """
    import re
    from pathlib import Path
    a = fontgen.GLYPH_DATA - fontgen.EXE_BASE
    original = usa_exe[a:a + 79 * 24]
    code_offset = fontgen.CHAR_TO_GLYPH_TABLE - fontgen.EXE_BASE
    code_bytes = usa_exe[code_offset:code_offset + 79 * 2]
    codes = struct.unpack('<79H', code_bytes)
    code_sources = {}
    for key, (path, data) in base_executables.items():
        offset = data.find(code_bytes)
        code_sources[key] = None if offset < 0 else [path, offset, len(code_bytes)]
    plans = glyph_plan(original, {key: data for key, (_, data) in base_executables.items()})
    tables = generate(original, codes, fontgen)
    text = Path(map_path).read_text()
    extents = []
    for m in re.finditer(r' \.rodata\.(LATIN_\w+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+\S+font\.c\.o', text):
        symbol, address, length = m[1], int(m[2], 16), int(m[3], 16)
        if symbol not in tables or len(tables[symbol]) != length:
            raise ValueError(f'compact Latin table changed shape: {symbol}')
        extents.append((address - fontgen.EXE_BASE, address - fontgen.EXE_BASE + length, symbol))
    if not extents:
        return dict(reason='This build has no compact Latin font tables.', copied_literals=0)
    if len(extents) != len(tables):
        raise ValueError('linker map does not describe every compact Latin table')
    result = dict(source_bytes=len(original), code_table_bytes=len(code_bytes), generated_bytes=sum(map(len, tables.values())),
                  plans=plans, copied_literals=0, missing_by_base={k: v['missing_bytes'] for k, v in plans.items()},
                  code_table_missing_by_base={key: 0 if source else len(code_bytes) for key, source in code_sources.items()})
    if any(p['missing'] for p in plans.values()) or any(source is None for source in code_sources.values()):
        result['reason'] = 'Required original glyphs or their code table are absent from a base executable; mixed tables retained.'
        return result
    # Reader metadata contains only copies from the player's own executable.
    payload['font'] = dict(code_sources=code_sources, sources={key: [[path, off, n] for off, n in plans[key]['sources']]
                           for key, (path, _) in base_executables.items()})
    ops = payload['files']['SLUS_010.32']
    out = []
    pos = 0
    for op in ops:
        n = payload['code'][op[1]][2] if op[0] == 'r' else op[2] if op[0] == 'l' else op[3]
        if op[0] != 'l':
            out.append(op)
            pos += n
            continue
        at = pos
        stop = pos + n
        for lo, hi, symbol in sorted(extents):
            lo2, hi2 = max(at, lo), min(stop, hi)
            if hi2 <= lo2:
                continue
            if at < lo2:
                out.append(['l', op[1] + at - pos, lo2 - at])
            expected = tables[symbol][lo2 - lo:hi2 - lo]
            if payload['blob'][op[1] + lo2 - pos:op[1] + hi2 - pos] != expected:
                raise ValueError(f'generated {symbol} differs from current target')
            path = '@font:' + symbol
            if path not in payload['sources']:
                payload['sources'].append(path)
            k = len(payload['code'])
            payload['code'].append([payload['sources'].index(path), lo2 - lo, hi2 - lo2])
            out.append(['r', k])
            for key in base_executables:
                if key != 'us':
                    payload['reloc'].setdefault(key, {})[str(k)] = [[path, lo2 - lo, hi2 - lo2]]
            result['copied_literals'] += hi2 - lo2
            at = hi2
        if at < stop:
            out.append(['l', op[1] + at - pos, stop - at])
        pos = stop
    payload['files']['SLUS_010.32'] = out
    # Reuse the standard compactor, which also preserves literal license data.
    import types
    import reloc
    files = dict(payload['files'])
    files['\0license'] = payload['license']
    enc = types.SimpleNamespace(blob=payload['blob'], usa_lit=set())
    reloc.compact(enc, files)
    payload['license'] = files.pop('\0license')
    payload['files'] = files
    payload['blob'] = bytes(enc.blob)
    return result


def rebuild(base, spec):
    """Player-side regeneration: standard-library fontgen plus authored b/extra.txt."""
    import importlib.util
    from pathlib import Path
    path = Path(base.tool_root) / 'tools/fontgen.py'
    module_spec = importlib.util.spec_from_file_location('_dwpatch_fontgen', path)
    fontgen = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(fontgen)
    original = b''.join(base.code(path)[off:off + n] for path, off, n in spec['sources'][base.key])
    path, offset, length = spec['code_sources'][base.key]
    codes = struct.unpack('<79H', base.code(path)[offset:offset + length])
    return generate(original, codes, fontgen)


# Fixed native capacities cover the seven regional tables. The bounds are part
# of the generated C layout, shared with the player-side encoder.
CAPACITIES = dict(LATIN_ROW_WORDS=512, LATIN_ROW_COUNTS=32,
                  LATIN_GLYPH_OFFSETS=600, LATIN_GLYPH_WIDTHS=600,
                  LATIN_GLYPH_BITS=2304)
MAX_BITS = 15


def pad_tables(tables):
    result = {}
    if set(tables) != set(CAPACITIES):
        raise ValueError('incomplete Latin font tables')
    for name, size in CAPACITIES.items():
        data = tables[name]
        if len(data) > size:
            raise ValueError(f'{name}: regional font exceeds native capacity ({len(data)} > {size})')
        result[name] = data + bytes(size - len(data))
    return result


def regional_glyphs(executable, key, fontgen):
    """Read a regional font by its code table; absent characters use authored b.

    Western/Japanese retail fonts use 992 codes and eleven packed row words,
    with an implicit twelve-pixel advance. The USA font uses 79 explicit-width
    records. Button code semantics differ: 817E is cross outside the USA.
    No USA glyph, checksum or bitmap is needed for another region.
    """
    import json
    from pathlib import Path
    codes = json.loads(Path(fontgen.ORIGINAL_METRICS).read_text())['codes']
    authored = fontgen.load_font_txt(fontgen.FONT_B)
    if key == 'us':
        code_data = struct.pack('<79H', *codes)
        offset = executable.find(code_data)
        if offset < 0 or executable.find(code_data, offset + 1) >= 0:
            raise ValueError('USA font code table is missing or ambiguous')
        # The glyph array follows the 158-byte code array and two alignment bytes.
        start = offset + 160
        stop = start + 79 * 24
        if stop > len(executable):
            raise ValueError('USA font glyph table is truncated')
        glyphs = executable[start:stop]
        if any(not 1 <= struct.unpack_from('<H', glyphs, i * 24 + 22)[0] <= 12 for i in range(79)):
            raise ValueError('invalid USA glyph widths')
        return glyphs, codes, dict(code_offset=offset, glyph_offset=start, missing=[])
    signature = struct.pack('<8H', 0x8141, 0x8142, 0x8145, 0x8146, 0x8148, 0x8149, 0x8158, 0x815b)
    offset = executable.find(signature)
    if offset < 0 or executable.find(signature, offset + 1) >= 0:
        raise ValueError('regional font code table is missing or ambiguous')
    start = offset + 992 * 2
    if start + 992 * 22 > len(executable):
        raise ValueError('regional font glyph table is truncated')
    regional = struct.unpack_from('<992H', executable, offset)
    # The final code is a mutable lookup sentinel, never a source glyph.
    lookup = {}
    for i, code in enumerate(regional[:-1]):
        lookup.setdefault(code, i)
    out, missing = bytearray(), []
    for i, code in enumerate(codes):
        source_code = {0x81a2: 0x817e, 0x817e: 0x81a2}.get(code, code)
        if source_code in lookup:
            pos = start + lookup[source_code] * 22
            out.extend(executable[pos:pos + 22])
            out.extend(struct.pack('<H', 12))
        else:
            char = fontgen.code_char(code)
            if char == ' ':
                width, rows = 4, ['.' * 12] * 11
            elif char in authored:
                width, rows = authored[char]
                width = 12  # original mode places regional glyphs in full cells
            else:
                raise ValueError(f'no authored fallback for {code:04X}')
            out.extend(struct.pack('<12H', *(fontgen.row_word(row) for row in rows), width))
            missing.append(i)
    return bytes(out), codes, dict(code_offset=offset, glyph_offset=start, missing=missing)


def regional_tables(executable, key, fontgen):
    glyphs, codes, evidence = regional_glyphs(executable, key, fontgen)
    tables = generate(glyphs, codes, fontgen)
    if len(tables['LATIN_ROW_COUNTS']) > (MAX_BITS + 1) * 2:
        raise ValueError('regional Huffman code exceeds native decoder limit')
    return pad_tables(tables), evidence


def load_generator(tool_root=None):
    import importlib.util
    from pathlib import Path
    root = Path(tool_root) if tool_root else Path(__file__).resolve().parents[2]
    path = root / 'tools/fontgen.py'
    spec = importlib.util.spec_from_file_location('_dwpatch_regional_fontgen', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native_layout(objects, target, fontgen):
    """Bind every generated array to this build's exact linker extent/USA bytes."""
    rows = []
    for obj in objects:
        name = obj['section'].removeprefix('.rodata.')
        if obj['source'] != 'src/main/font.c' or name not in CAPACITIES:
            continue
        if obj['length'] != CAPACITIES[name]:
            raise ValueError('native font capacities are stale; rebuild with tools/font/compact.py')
        rows.append([obj['offset'], name, obj['length']])
    if rows and {row[1] for row in rows} != set(CAPACITIES):
        raise ValueError('current linker map lacks a Latin font array')
    return sorted(rows)


def generated_tail(layout, original, key, tool_root=None):
    """Return arrays and their destination coordinates, with no stored pixels."""
    if len(layout) != len(CAPACITIES) or {row[1] for row in layout} != set(CAPACITIES):
        raise ValueError('incomplete regional font layout')
    end = 0
    for offset, name, size in layout:
        if type(offset) is not int or offset < end or size != CAPACITIES[name]:
            raise ValueError('invalid regional font layout')
        end = offset + size
    tables, _ = regional_tables(original, key, load_generator(tool_root))
    return b''.join(tables[name] for _, name, _ in layout)


def table_layout(recipes):
    result = []
    end = 0
    for recipe in recipes:
        start, size = recipe['offset'], recipe['size']
        if type(start) is not int or type(size) is not int or start < end or size <= 0:
            raise ValueError('invalid table object layout')
        inner_end = 0
        for inner, length in recipe['fields']:
            if type(inner) is not int or type(length) is not int or inner < inner_end or length <= 0 or inner + length > size:
                raise ValueError('invalid table payload fields')
            result.append([start + inner, length])
            inner_end = inner + length
        end = start + size
    return result


def table_tail(recipes, key, read_source, tool_root=None):
    table_layout(recipes)
    result = bytearray()
    for recipe in recipes:
        kind = recipe['kind']
        if kind == 'nulls':
            data = bytes(recipe['size'])
        elif kind in ('record', 'regional_header'):
            path, offset, digest = recipe['sources'][key]
            source = read_source(path)
            if __import__('hashlib').sha1(source).hexdigest() != digest or offset < 0 or offset + recipe['size'] > len(source):
                raise ValueError('table witness differs from pinned player file')
            data = bytearray(source[offset:offset + recipe['size']])
            for inner in recipe.get('zeros', []):
                if type(inner) is not int or inner % 4 or inner < 0 or inner + 4 > len(data):
                    raise ValueError('invalid generated zero word')
                data[inner:inner + 4] = bytes(4)
        elif kind == 'ui':
            data = ui_table(recipe, key, read_source)
        elif kind == 'aura':
            data = aura_table(recipe, key, read_source, tool_root)
        elif kind == 'items':
            data = item_table(recipe, key, read_source, tool_root)
        elif kind == 'semantic':
            data = semantic_table(recipe['generator'], recipe['params'], tool_root)
            if len(data) != sum(size for _, size in recipe['fields']):
                raise ValueError('semantic table size differs from the native fields')
            result.extend(data)
            continue
        else:
            raise ValueError('unknown table payload generator')
        for offset, size in recipe['fields']:
            result.extend(data[offset:offset + size])
    return bytes(result)


def semantic_table(kind, params, tool_root=None):
    """Generate authored text/layouts and standard encodings from semantic inputs."""
    import importlib.util
    import json
    from pathlib import Path
    import sys
    root = Path(tool_root) if tool_root else Path(__file__).resolve().parents[2]

    def module(relative):
        path = root / relative
        spec = importlib.util.spec_from_file_location('_dwpatch_' + path.stem, path)
        value = importlib.util.module_from_spec(spec)
        # The existing bundled tools import both tools.* and top-level dws.
        for parent in (root, root / 'tools'):
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
        spec.loader.exec_module(value)
        return value

    if kind == 'empty_sprite_names':
        rows, = params
        if rows not in (112, 116):
            raise ValueError('unexpected discarded sprite name table')
        return bytes(rows * 14)
    if kind == 'pitch':
        if params:
            raise ValueError('pitch formula takes no supplied bytes')
        return struct.pack('<200H', *(int(4096 * 2 ** (i / 192)) for i in range(193)), *([0] * 7))
    if kind == 'sound_index_limits':
        if params:
            raise ValueError('sound limits take no supplied bytes')
        return b''.join(struct.pack('<hh', cap, stride) for cap, stride in
                        ((254, 39), (256, 7), (256, 15), (32, 0)))
    if kind == 'muted_voices':
        if params:
            raise ValueError('muted voices take no supplied bytes')
        return bytes(16)
    if kind == 'cd_register':
        name, = params
        return struct.pack('<I', 0x1f800000 + CD_REGISTERS[name])
    if kind == 'sdk_layout':
        sdk, size, spans = params
        messages = json.loads((root / 'tools/patcher/sdk-messages.json').read_text())[sdk]
        out = bytearray(size)
        end = 0
        for at, n, index in spans:
            row = messages[index]
            if at < end or at+n > size or not row['size'] <= n <= row['size']+3:
                raise ValueError('SDK diagnostic layout exceeds its natural label')
            out[at:at+n] = (row['text'].encode() + b'\0').ljust(n, b'\0')
            end = at+n
        return bytes(out)
    if kind == 'sdk_messages':
        sdk, fields = params
        messages = json.loads((root / 'tools/patcher/sdk-messages.json').read_text())[sdk]
        out = bytearray()
        for index, size in fields:
            row = messages[index]
            if type(size) is not int or not row['size'] <= size <= row['size'] + 3:
                raise ValueError('SDK diagnostic padding differs from its slot')
            out.extend((row['text'].encode() + b'\0').ljust(size, b'\0'))
        return bytes(out)
    if kind == 'pointer_count':
        count, = params
        return struct.pack('<I', count)
    if kind == 'menu_picker':
        if params:
            raise ValueError('picker labels take no supplied bytes')
        return b'LANGUAGE - IDIOMA\0'.ljust(20, b'\0') + b'START\0'
    if kind == 'inventory_labels':
        language, = params
        bank = authored_bank(str(root), language)
        return b''.join(encode_bank(bank['text'][f'main.ITEM_MENU_LABELS.{i}'], bank).ljust(8, b'\0') for i in range(4))
    if kind == 'versus_mode':
        english, = params
        return struct.pack('<4h6B', 77 if english else 79, 14, 113 if english else 112, 9,
                           1, 48, 0, 77 if english else 79, 14, 5)
    if kind == 'keyboard_rollover':
        if params:
            raise ValueError('keyboard row map takes no supplied bytes')
        return struct.pack('<10H', *(0x8000 + i for i in (0, 0, 0, 1, 2, 3, 3, 4, 4)), 0)
    if kind == 'keyboard_boxes':
        english, = params
        return struct.pack('<18h', 14, 6, 48 if english else 52,
                           14, 34, 36, 14, 48, 36, 14, 62, 36 if english else 24,
                           14, 90, 48 if english else 52, 14, 118, 24)
    if kind == 'banner':
        language, = params
        if language in ('es', 'pt-br'):
            builder = module('tools/localize/textures/misc/build.py')
            seq = ([('L', 2), ('U', 2), ('T', 2), ('A', 1), ('e1', 0)] if language == 'pt-br' else
                   [('i1', 1), ('L', 2), ('U', 2), ('C', 2), ('H', 2), ('A', 1), ('e1', 0)])
            cells, width = builder.banner_layout(seq)
            x = -172 + (44 - width) // 2 * 8
            points = [[x + c * 8, -48 + r * 12] for c, r in cells]
            points += [points[-1]] * (155 - len(points))
        else:
            points = module('tools/localize/labels.py').battle_banner(language)['positions']
        return b''.join(struct.pack('<hh', *point) for point in points)
    if kind == 'sjis':
        if params:
            raise ValueError('encoding table takes no supplied bytes')
        chars = ' !"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'
        punctuation = {' ': '　', '"': '”', "'": '’', '-': '−', '~': '￣', '.': '。',
                       '<': '〈', '>': '〉', '`': '‘'}
        out = bytearray()
        for char in chars:
            wide = punctuation.get(char, chr(ord(char) + 0xfee0))
            code = int.from_bytes(wide.encode('cp932'), 'big')
            out.extend(struct.pack('<HH', code, ord(char)))
        return bytes(out)
    if kind == 'save_ids':
        if params:
            raise ValueError('save labels take no supplied bytes')
        # Retain the original menu's spacing for slots seven and eight.
        return b''.join((f'{i:2}' + (' ' if i in (7, 8) else '')).encode().ljust(6, b'\0') for i in range(16))
    if kind == 'text':
        language, key, size = params
        bank = authored_bank(str(root), language)
        text = bank['text'][key]
        encoded = encode_bank(text, bank)
        if type(size) is not int or len(encoded) >= size:
            raise ValueError('authored table text exceeds its field')
        return (encoded + b'\0').ljust(size, b'\0')
    raise ValueError('unknown semantic table generator')


def encode_bank(text, bank):
    return b''.join(bytes.fromhex(bank['font'][char]) if char in bank['font'] else char.encode('cp932')
                    for char in text)


from functools import lru_cache


@lru_cache(maxsize=24)
def authored_bank(root, language):
    import importlib.util
    from pathlib import Path
    import sys
    root = Path(root)
    for parent in (root, root / 'tools'):
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
    spec = importlib.util.spec_from_file_location('_dwpatch_authored_bank', root / 'tools/localize/executable/bank.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if language not in ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca'):
        raise ValueError('unknown authored text language')
    return module.exe_bank('ours' if language == 'en' else language, exe_font='b')[0]


ITEM_NUMERIC_FIELDS = [('value', 'i'), ('meritValue', 'H'), ('sortingValue', 'h'),
                       ('itemColor', 'B'), ('droppable', 'B'), ('unk', 'H')]


@lru_cache(maxsize=4)
def item_content(root):
    import json
    from pathlib import Path
    return {row['id']: row for path in sorted((Path(root) / 'content/items').glob('*.json'))
            for row in [json.loads(path.read_text())]}


def item_table(recipe, key, read_source, tool_root=None):
    from pathlib import Path
    import hashlib
    root = str(Path(tool_root) if tool_root else Path(__file__).resolve().parents[2])
    path, offset, stride, digest, overrides = recipe['sources'][key]
    raw = read_source(path)
    if (hashlib.sha1(raw).hexdigest() != digest or stride not in (12, 32)
            or offset < 0 or offset + 127 * stride + 12 > len(raw)):
        raise ValueError('item table differs from pinned player records')
    bank = authored_bank(root, recipe['language'])
    numeric = [bytearray(raw[offset + i * stride:offset + i * stride + 12]) for i in range(128)]
    positions, at = {}, 0
    for field, fmt in ITEM_NUMERIC_FIELDS:
        positions[field] = (at, fmt); at += struct.calcsize('<' + fmt)
    content = item_content(root)
    for index, field in overrides:
        at, fmt = positions[field]
        struct.pack_into('<' + fmt, numeric[index], at, content[index][field])
    out = bytearray()
    for index in range(128):
        name = encode_bank(bank['text'][f'main.ITEM_NAMES.{index}'], bank)
        if len(name) >= 20:
            raise ValueError('authored item name exceeds its record')
        out.extend(name.ljust(20, b'\0')); out.extend(numeric[index])
    return bytes(out)


def aura_table(recipe, key, read_source, tool_root=None):
    import hashlib
    import json
    from pathlib import Path
    root = Path(tool_root) if tool_root else Path(__file__).resolve().parents[2]
    path, offset, digest, overrides = recipe['sources'][key]
    source = read_source(path)
    if hashlib.sha1(source).hexdigest() != digest or offset < 0 or offset + 129 * 12 > len(source):
        raise ValueError('aura table differs from pinned player records')
    out = bytearray(source[offset:offset + 129 * 12])
    authored = json.loads((root / 'content/tables/effects.json').read_text())['auraTypes']
    fields = ('type', 'unk2', 'unk4', 'unk6', 'unk8', 'u')
    for row, field in overrides:
        struct.pack_into('<h', out, row * 12 + fields.index(field) * 2, authored[row][field])
    return bytes(out)


def ui_table(recipe, key, read_source):
    """Player panel positions, with crops for our authored text-drawing contract.

    The source's original instruction pair identifies the complete semantic
    table. Coordinates are never assembled from unrelated short byte values.
    """
    import hashlib
    path, offset, size, digest, references = recipe['sources'][key]
    raw = read_source(path)
    if hashlib.sha1(raw).hexdigest() != digest or offset < 0 or offset + size > len(raw):
        raise ValueError('UI table differs from its pinned player file')
    high, low = references
    if not (0 <= high <= len(raw)-4 and 0 <= low <= len(raw)-4):
        raise ValueError('UI table reference outside player code')
    hi, = struct.unpack_from('<I', raw, high); lo, = struct.unpack_from('<I', raw, low)
    register = (hi >> 16) & 31
    address = ((hi & 65535) << 16) + ((lo & 65535) - 65536 if lo & 32768 else lo & 65535)
    if (hi >> 26 != 15 or lo >> 26 != 9 or (lo >> 21) & 31 != register
            or (lo >> 16) & 31 != register or address != 0x80090000 + offset):
        raise ValueError('UI table lacks its original address reference')
    source = raw[offset:offset + size]
    name = recipe['ui']
    if name in ('MOVES_VIEW_SPRITES', 'AMOUNT_BOX_LAYOUT'):
        return source
    out = bytearray()
    if name == 'STATS_VIEW_TEXT':
        # DRAW_STRING_PIECES' seven stat-label slots: 12-pixel cells in rows
        # 3/4 of our shared text area. Two trailing slots are blank in USA code.
        cells = (4, 3, 3, 2, 2, 3, 3)
        columns = (6, 2, 10, 13, 15, 0, 3)
        for i, (width, column) in enumerate(zip(cells, columns)):
            out.extend(source[i*8:i*8+4])
            out.extend(struct.pack('<hBB', width*12, column*12, (4 if i < 5 else 3)*12))
        for i in range(7, 9):
            out.extend(source[i*8:i*8+4] if i*8+4 <= len(source) else bytes(4))
            out.extend(struct.pack('<hBB', 0, 0, 4*12))
    elif name == 'MOVES_VIEW_STRING_SPRITES':
        # Text-area slots shared by drawDigimonMovesText/drawMoveViewHelpStrings.
        # A disabled slot has width zero; the six help rows are 100 pixels wide.
        widths = (113+2, 223-113, 0, 12, 88-(-102), 0) + (100,)*6
        columns = (0, 113, 223, 0, 12, 84) + (0,)*6
        rows = (2, 2, 2, 3, 3, 4, 5, 6, 7, 8, 8, 9)
        for i, (width, column, row) in enumerate(zip(widths, columns, rows)):
            out.extend(source[i*8:i*8+4])
            out.extend(struct.pack('<hBB', width, column, row*12))
    else:
        raise ValueError('unknown regional UI table')
    if len(out) != recipe['size']:
        raise ValueError('regional UI table shape differs from native layout')
    return bytes(out)


# Named PlayStation MMIO registers, offsets from the I/O page. These are
# hardware addresses, independent of any game's inherited initializers.
CD_REGISTERS = dict(reg0=0x1800, reg1=0x1801, reg2=0x1802, reg3=0x1803,
                    c_003_HADR0=0x1800, c_003_HADR3=0x1803,
                    c_011_HADR0=0x1800, c_011_HADR3=0x1803, HADR2=0x1802,
                    com_delay=0x1020, COMMON_DELAY=0x1020, spu=0x1c00,
                    dv5_delay=0x1018, DEV5_DELAY=0x1018, bios_d_pcr=0x10f0,
                    Dma_PCR=0x10f0, Dma_ICR=0x10f4, Dma_CHCR1=0x1098, Dma_CHCR3=0x10b8,
                    d3_madr=0x10b0, d3_bcr=0x10b4)
