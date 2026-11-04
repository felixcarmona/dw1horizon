"""Prepare and audit the Simplified Chinese translation and its offline font.

This authoring tool does not register a playable language. A complete bank and
the extra-RAM runtime must pass their gates before Chinese enters the registry.
All player-side font generation uses the standard library and committed pixels.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import struct
import unicodedata
import zlib

ROOT = Path(__file__).resolve().parents[1]
LANGUAGE = 'zh-hans'
FIRST_LEAD, LAST_LEAD, TRAILS = 0xA0, 0xDF, 188
CAPACITY = (LAST_LEAD - FIRST_LEAD + 1) * TRAILS
CELL = 12
ASCII = ''.join(map(chr, range(32, 127)))
PUNCTUATION = '，。！？；：“”‘’（）《》〈〉「」『』【】〔〕、…—％'
HEADER = struct.Struct('<4s7I')
RECORD = struct.Struct('<13H')  # advance, twelve inverted MSB-first row words
ESCAPE = re.compile(r'\{[^{}]+\}|#[A-Z]\d*|%[-+0-9.]*[a-zA-Z]')
CJK = re.compile(r'[\u3400-\u9fff]')
FONT_PATH = Path('tools/font/chinese.json')
NO_START = frozenset('，。、；：？！）》〉」』】〕］｝”’％‰…—,.!?:;)]}')
NO_END = frozenset('（《〈「『【〔［｛“‘([{')
TOKENS = re.compile(r'\{[^{}]+\}|#[A-Z]\d*|%[-+0-9.]*[a-zA-Z]|[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*|……|——|.')
SOURCE_SHA256 = 'bdb520006cddacccc1d3f780d5fab79007a4d6d1f3559d04665e652af4cdf50f'


def read_json(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f'{path}: duplicate key {key}')
            out[key] = value
        return out
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for part in value:
            yield from strings(part)
    else:
        raise ValueError('bank values must be strings or lists of strings/pages')


def banks(root=ROOT):
    """English authority paired with its target, including every mod bank."""
    for source in sorted((root / 'text/ours/dialogue').glob('*.json')):
        yield source, root / 'text' / LANGUAGE / 'dialogue' / source.name
    yield root / 'text/ours/names.json', root / 'text' / LANGUAGE / 'names.json'
    yield root / 'text/en.json', root / 'text' / (LANGUAGE + '.json')
    for source in sorted((root / 'story/mods').glob('*/text/en.json')):
        yield source, source.with_name(LANGUAGE + '.json')


def displayed(root=ROOT):
    for _, target in banks(root):
        if target.exists():
            for key, value in read_json(target).items():
                if not key.startswith('_'):
                    yield from strings(value)


def repertoire(root=ROOT):
    text = ''.join(ESCAPE.sub('', s) for s in displayed(root))
    glossary = read_json(root / 'text' / LANGUAGE / 'glossary.json')
    for group in ('species', 'items', 'techniques'):
        text += ''.join(row['zh'] for row in glossary.get(group, {}).values())
    text += ''.join(glossary.get('provisional', {}).values())
    # Button glyphs are handled by the game's established button codes.
    return sorted(set(unicodedata.normalize('NFC', text + PUNCTUATION)) - set(ASCII + '\n\r\t○□△×'))


def index_to_code(index):
    if not 0 <= index < CAPACITY:
        raise ValueError(f'Chinese glyph index outside 0..{CAPACITY - 1}: {index}')
    lead, trail = divmod(index, TRAILS)
    trail += 0x40
    return ((FIRST_LEAD + lead) << 8) | (trail + (trail >= 0x7F))


def code_to_index(code):
    lead, trail = divmod(code, 256)
    if not FIRST_LEAD <= lead <= LAST_LEAD or not (0x40 <= trail <= 0xFC and trail != 0x7F):
        raise ValueError(f'invalid Chinese glyph code: {code:04X}')
    return (lead - FIRST_LEAD) * TRAILS + trail - 0x40 - (trail > 0x7F)


def encoding(chars):
    if len(set(chars)) != len(chars) or any(len(c) != 1 or c in ASCII for c in chars):
        raise ValueError('extended repertoire must contain distinct non-ASCII characters')
    return {c: index_to_code(i) for i, c in enumerate(chars)}


def encode(text, chars):
    """Literal text only; the script compiler must handle substitutions separately."""
    mapping = encoding(chars)
    out = bytearray()
    for char in text:
        if char in ASCII:
            out.append(ord(char))
        elif char in mapping:
            out.extend(mapping[char].to_bytes(2, 'big'))
        else:
            raise ValueError(f'no Chinese glyph for U+{ord(char):04X} {char!r}')
    return bytes(out)


def row_metrics(row, glyphs, packed=True):
    """Conservative dynamic names match the existing compiler's 80px/16B bound."""
    pixels, size = 0, 0
    for token in TOKENS.findall(row):
        if ESCAPE.fullmatch(token):
            if token.startswith('{color '):
                size += 2
            elif token.startswith('{'):
                pixels += 80
                size += 16
            else:
                raise ValueError('executable format controls are not dialogue: ' + token)
        else:
            for char in token:
                if char in '○□△×':
                    pixels += 12
                    size += 2
                elif char in glyphs:
                    pixels += glyphs[char][0]
                    size += 1 if packed and char in ASCII else 2
                else:
                    raise ValueError(f'no font metrics for {char!r}')
    return pixels, size


def wrap(text, glyphs, rows_per_page=3, packed=True):
    """Chinese kinsoku, with atomic references, words, ellipses and dashes.

    This is an authoring preview. The engine's C walkers do not yet implement
    these glyph codes; passing this layout check is not a runtime proof.
    """
    if rows_per_page not in (3, 4):
        raise ValueError('dialogue pages must have three or four rows')
    tokens = TOKENS.findall(text)
    rows = []
    def visible(parts):
        return ''.join('' if t.startswith('{color ') else '名' if ESCAPE.fullmatch(t) else t
                       for t in parts).strip()
    while tokens:
        candidates = []
        limit = 228 if len(rows) % rows_per_page == rows_per_page - 1 else 240
        for end in range(1, len(tokens) + 1):
            candidate = ''.join(tokens[:end]).strip()
            px, size = row_metrics(candidate, glyphs, packed)
            if px > limit or size > 62:
                break
            left, right = visible(tokens[:end]), visible(tokens[end:])
            if candidate and (not left or left[-1] not in NO_END) and (not right or right[0] not in NO_START):
                candidates.append(end)
        if not candidates:
            raise ValueError('cannot fit an atomic word/reference or obey Chinese punctuation rules')
        end = candidates[-1]
        rows.append(''.join(tokens[:end]).strip())
        tokens = tokens[end:]
        while tokens and tokens[0] == ' ':
            tokens.pop(0)
    return [rows[i:i + rows_per_page] for i in range(0, len(rows), rows_per_page)] or [['']]


def parse_bdf(path, wanted):
    """Copy exact pixels onto a 12x12 cell; refuse clipping and absent glyphs."""
    text = Path(path).read_text(encoding='utf-8')
    ascent = int(re.search(r'^FONT_ASCENT (\d+)$', text, re.M)[1])
    out = {}
    for block in text.split('STARTCHAR ')[1:]:
        code = int(re.search(r'^ENCODING (-?\d+)$', block, re.M)[1])
        if code < 0 or chr(code) not in wanted:
            continue
        char = chr(code)
        advance = int(re.search(r'^DWIDTH (\d+) ', block, re.M)[1])
        w, h, x, y = map(int, re.search(r'^BBX (-?\d+) (-?\d+) (-?\d+) (-?\d+)$', block, re.M).groups())
        rows = block.split('BITMAP\n', 1)[1].split('ENDCHAR', 1)[0].split()
        if len(rows) != h or not 0 < advance <= CELL or char in out:
            raise ValueError(f'invalid BDF record for {char!r}')
        canvas = [0xFFFF] * CELL
        for row, data in enumerate(rows):
            bits = int(data, 16)
            if len(data) != ((w + 7) // 8) * 2:
                raise ValueError(f'invalid BDF row for {char!r}')
            for column in range(w):
                if bits & (1 << (((w + 7) // 8) * 8 - column - 1)):
                    xx, yy = x + column, ascent - y - h + row
                    if not 0 <= xx < CELL or not 0 <= yy < CELL:
                        raise ValueError(f'BDF pixels would be clipped: {char!r}')
                    canvas[yy] &= ~(0x8000 >> xx)
        out[char] = [advance, *canvas]
    missing = set(wanted) - out.keys()
    if missing:
        raise ValueError('font lacks ' + ''.join(sorted(missing)))
    return out


def build_font(subset, chars):
    """Versioned proposal for a font loaded wholly above 2 MB at selection.

    No Unicode map is needed on the console: ASCII indexes the first 95 records,
    followed by the dense two-byte indices. The source map stays in build tools.
    Runtime integration and the twelve-row renderer remain separate gates.
    """
    encoding(chars)
    records = subset['glyphs']
    payload = bytearray()
    for char in ASCII + ''.join(chars):
        if char not in records:
            raise ValueError(f'font subset lacks {char!r}; regenerate it')
        record = records[char]
        if (len(record) != 13 or any(not isinstance(v, int) or not 0 <= v <= 65535 for v in record) or
                not 0 < record[0] <= CELL or
                any((v & 15) != 15 for v in record[1:])):
            raise ValueError(f'invalid 12x12 font record for {char!r}')
        payload.extend(RECORD.pack(*record))
    # magic, version, width, height, record bytes, ASCII count, extra count, CRC32
    header = HEADER.pack(b'DWZH', 1, CELL, CELL, RECORD.size, len(ASCII), len(chars), zlib.crc32(payload))
    return header + payload


def validate_font(data):
    if len(data) < HEADER.size:
        raise ValueError('truncated Chinese font header')
    magic, version, width, height, stride, ascii_count, count, crc = HEADER.unpack_from(data)
    if (magic, version, width, height, stride, ascii_count) != (b'DWZH', 1, CELL, CELL, RECORD.size, len(ASCII)):
        raise ValueError('unsupported Chinese font format')
    if count > CAPACITY or len(data) != HEADER.size + (count + ascii_count) * stride:
        raise ValueError('Chinese font size/count mismatch')
    if zlib.crc32(data[HEADER.size:]) != crc:
        raise ValueError('Chinese font CRC32 mismatch')
    for at in range(HEADER.size, len(data), stride):
        record = RECORD.unpack_from(data, at)
        if not 0 < record[0] <= CELL or any((v & 15) != 15 for v in record[1:]):
            raise ValueError('invalid Chinese font bitmap record')
    return count


def audit(root=ROOT):
    report = {'translated': 0, 'expected': 0, 'missing': [], 'errors': []}
    glossary = read_json(root / 'text' / LANGUAGE / 'glossary.json')
    for source, target in banks(root):
        original = {k: v for k, v in read_json(source).items() if not k.startswith('_')}
        translated = read_json(target) if target.exists() else {}
        report['expected'] += len(original)
        for key in original.keys() - translated.keys():
            report['missing'].append(f'{target.relative_to(root)}:{key}')
        for key, value in translated.items():
            if key.startswith('_'):
                continue
            where = f'{target.relative_to(root)}:{key}'
            if key not in original:
                report['errors'].append(where + ': unknown key')
                continue
            report['translated'] += 1
            target_strings = list(strings(value))
            text = ''.join(target_strings)
            if unicodedata.normalize('NFC', text) != text:
                report['errors'].append(where + ': text is not NFC')
            if sum(not s.strip() for s in target_strings) > sum(not s.strip() for s in strings(original[key])):
                report['errors'].append(where + ': blank translated row')
            # Preserve the exact controls, multiplicity and order. Explicit source
            # pages can be translated without losing a substitution or a color reset.
            before = ESCAPE.findall(''.join(strings(original[key])))
            after = ESCAPE.findall(text)
            if before != after:
                report['errors'].append(where + ': control/substitution signature changed')
            if text.count('{') != len(re.findall(r'\{[^{}]+\}', text)) or text.count('}') != text.count('{'):
                report['errors'].append(where + ': malformed escape')
            for wrong, right in glossary.get('avoid', {}).items():
                if wrong in text:
                    report['errors'].append(where + f': use {right}, not {wrong}')
            # Latin species left in prose should never pass as Chinese coverage.
            literal = ESCAPE.sub('', text)
            for name in glossary['species']:
                if re.search(r'(?<![A-Za-z])' + re.escape(name) + r'(?![A-Za-z])', literal):
                    report['errors'].append(where + ': untranslated species ' + name)
            if not CJK.search(literal) and re.search(r'[A-Za-z]{3}', literal) and literal != 'START':
                report['errors'].append(where + ': untranslated Latin prose')
    report['missing'].sort()
    report['errors'].sort()
    report['glyphs'] = len(repertoire(root))
    return report


def audit_layout(root=ROOT):
    """Check explicit pages and preview automatic wrapping with the exact subset."""
    from tools.dws.text.profiles import header_row, named_keys
    glyphs = read_json(root / FONT_PATH)['glyphs']
    named = named_keys(root)
    errors = []
    for _, target in banks(root):
        if not target.exists() or target.name == 'names.json':
            continue
        for key, value in read_json(target).items():
            if key.startswith('_'):
                continue
            where = f'{target.relative_to(root)}:{key}'
            try:
                if isinstance(value, str):
                    if re.search(r'\.m\d+\.o\d+$', key):
                        pixels, size = row_metrics(value, glyphs)
                        if pixels > 240 or size > 62:
                            raise ValueError('menu option exceeds one row')
                    else:
                        wrap(value, glyphs, 3 if key in named else 4)
                    continue
                pages = [value] if all(isinstance(v, str) for v in value) else value
                for page in pages:
                    rows = 3 if key in named else 4
                    if page and header_row(page[0]):
                        rows = 4
                    if len(page) > rows:
                        raise ValueError(f'explicit page has {len(page)} rows, maximum {rows}')
                    for i, row in enumerate(page):
                        pixels, size = row_metrics(row, glyphs)
                        limit = 228 if i == rows - 1 else 240
                        if pixels > limit or size > 62:
                            raise ValueError(f'explicit row {i + 1}: {pixels}px/{size}B exceeds {limit}px/62B')
                        literal = re.sub(r'\{color [^}]+\}', '', row).strip()
                        first_body = 1 if page and header_row(page[0]) else 0
                        # An utterance may deliberately begin with hesitation.
                        # Kinsoku prohibits a break before it within that utterance.
                        bad_start = i > first_body and literal and literal[0] in NO_START
                        if (literal and not header_row(row) and set(literal) != {'…'} and
                                (bad_start or literal[-1] in NO_END)):
                            raise ValueError(f'explicit row {i + 1}: forbidden punctuation at row boundary')
            except ValueError as exc:
                errors.append(where + ': ' + str(exc))
    return errors


def review(destination, root=ROOT):
    """Local parallel text; never distribute extracted Japanese in the repository."""
    japanese = {}
    for name in ('jp', 'jp-rev1'):
        japanese[name] = {}
        for kind in ('dialogue', 'names'):
            path = root / 'text' / name / (kind + '.json')
            japanese[name][kind] = read_json(path) if path.exists() else {}
    columns = ['Key / scene', 'English', 'Japanese', 'Japanese Rev 1', 'Simplified Chinese', 'ES / PT / FR / DE / IT']
    rows = []
    def cell(value):
        return '<td>' + html.escape('\n'.join(strings(value))) + '</td>'
    for source, target in banks(root):
        if not target.exists():
            continue
        original, translated = read_json(source), read_json(target)
        kind = 'names' if source.name == 'names.json' else 'dialogue'
        context = []
        for lang in ('es', 'pt-br', 'fr', 'de', 'it'):
            relative = source.relative_to(root).as_posix()
            path = (root / relative.replace('text/ours/', f'text/{lang}/') if 'text/ours/' in relative
                    else source.with_name(lang + '.json'))
            context.append((lang, read_json(path) if path.exists() else {}))
        for key, value in translated.items():
            if key.startswith('_'):
                continue
            other = '\n\n'.join(lang + ': ' + '\n'.join(strings(bank[key])) for lang, bank in context if key in bank)
            values = [str(source.relative_to(root)) + '\n' + key, original.get(key, ''),
                      japanese['jp'][kind].get(key, ''), japanese['jp-rev1'][kind].get(key, ''), value, other]
            rows.append('<tr>' + ''.join(cell(v) for v in values) + '</tr>')
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<!doctype html><meta charset="utf-8"><title>Chinese translation review</title>'
                    '<style>table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:8px;'
                    'vertical-align:top;white-space:pre-wrap;min-width:180px}</style><table><tr>' +
                    ''.join('<th>' + v + '</th>' for v in columns) + '</tr>' + ''.join(rows) + '</table>', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('audit')
    check.add_argument('--report', type=Path)
    check.add_argument('--draft', action='store_true', help='report missing keys without failing; never a release gate')
    check.add_argument('--layout', action='store_true', help='check 12px authoring layout; not a runtime proof')
    rv = commands.add_parser('review')
    rv.add_argument('output', type=Path)
    imp = commands.add_parser('import-font')
    imp.add_argument('bdf', type=Path)
    font = commands.add_parser('font')
    font.add_argument('output', type=Path)
    a = parser.parse_args(argv)
    if a.command == 'audit':
        result = audit()
        if a.layout:
            result['errors'].extend(audit_layout())
        if a.report:
            write_json(a.report, result)
        print(f"Chinese: {result['translated']}/{result['expected']} keys, {result['glyphs']} extended glyphs, "
              f"{len(result['errors'])} errors, {len(result['missing'])} missing")
        for error in result['errors'][:30]:
            print(error)
        return bool(result['errors'] or (result['missing'] and not a.draft))
    if a.command == 'review':
        review(a.output)
    elif a.command == 'import-font':
        digest = hashlib.sha256(a.bdf.read_bytes()).hexdigest()
        if digest != SOURCE_SHA256:
            parser.error('BDF SHA-256 differs from the pinned licensed Simplified Chinese font')
        glyphs = parse_bdf(a.bdf, set(ASCII + ''.join(repertoire())))
        write_json(ROOT / FONT_PATH, {'_license': 'SIL-OFL-1.1; see chinese-license/',
                   '_name': 'Horizon Simplified Chinese subset', '_source_sha256': digest, 'glyphs': glyphs})
        print(f'{len(glyphs)} exact bitmap glyphs')
    elif a.command == 'font':
        chars = repertoire()
        data = build_font(read_json(ROOT / FONT_PATH), chars)
        validate_font(data)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_bytes(data)
        write_json(a.output.with_suffix('.json'), {'format': 'DWZH-1', 'sha256': hashlib.sha256(data).hexdigest(),
                   'bytes': len(data), 'sector_bytes': (len(data) + 2047) // 2048 * 2048,
                   'codes': {c: f'{code:04X}' for c, code in encoding(chars).items()}})
        print(f'{len(chars)} extended glyphs + {len(ASCII)} ASCII, {len(data)} bytes')
    return 0




_FONT_METRICS_CACHE = None


def font_glyphs():
    global _FONT_METRICS_CACHE
    path = ROOT / FONT_PATH
    stamp = (path.stat().st_mtime_ns, path.stat().st_size)
    if _FONT_METRICS_CACHE is None or _FONT_METRICS_CACHE[0] != stamp:
        _FONT_METRICS_CACHE = (stamp, read_json(path)['glyphs'])
    return _FONT_METRICS_CACHE[1]


def configure_compiler(backend=None):
    """Select the Chinese-only encoding for one compiler invocation."""
    if backend is None:
        from dws import backend
    bytecode = backend.bytecode
    glyphs = font_glyphs()
    codes = encoding(repertoire())
    # ASCII not in the packed dialogue alphabet needs its established SJIS code.
    special_codes = (0x8140,0x8149,0x8168,0x8194,0x8190,0x8193,0x8195,0x8166,
                     0x8169,0x816A,0x8196,0x817B,0x8143,0x817C,0x8142,0x815E,
                     0x8146,0x8147,0x8171,0x8181,0x8172,0x8148,0x8197,
                     0x816D,0x815F,0x816E,0x814F,0x8151,0x8165,0x816F,0x8162,0x8170,0x8150)
    special_chars = ''.join(chr(i) for i in (*range(32,48),*range(58,65),*range(91,97),*range(123,127)))
    bytecode.CHINESE_CODES = {**codes, **{c:n for c,n in zip(special_chars,special_codes) if c not in bytecode.CHAR2SJIS}}
    bytecode.CHINESE_REVERSE = {code:char for char,code in bytecode.CHINESE_CODES.items()}
    backend.FONT.update(chinese=True, name='b', extra=True, chars=frozenset(glyphs) | set('○□△×'))


if __name__ == '__main__':
    raise SystemExit(main())
