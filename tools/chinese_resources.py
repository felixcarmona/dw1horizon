"""Deterministic Chinese container: one resident file entry, selected index/font in extra RAM."""
import hashlib
import json
from pathlib import Path
import struct

BASE = 0x80400000
PREFIX_SIZE = 0x70000
MODULE_OFFSET = 0x800
FONT_OFFSET = 0x10000
NAMES_OFFSET = 0x30000
NAME_COUNT = 1024
NAME_SIZE = 20
EN_NAMES_OFFSET = 0x35000
UI_OFFSET = 0x60000
DIRECTORY_OFFSET = 0x40000
PATCH_OFFSET = 0x50000
MAGIC = b'DWCZ'
SECTOR = 2048
HEADER = struct.Struct('<4s7I')
ENTRY = struct.Struct('<4I')


def fnv(data):
    value = 0x811c9dc5
    for byte in data:
        value = ((value ^ byte) * 0x01000193) & 0xffffffff
    return value


def key(name):
    return fnv(name.encode('ascii')) & 0xffffff


def build(module, font, patch, resources, names=None, ui=None, english_names=None):
    """Resources: [{name, story: 0 extended / 1 original, signs, data}]."""
    from tools.chinese import validate_font
    validate_font(font)
    if not module or len(module) > FONT_OFFSET - MODULE_OFFSET:
        raise ValueError('Chinese runtime exceeds its reserved module area')
    if len(font) > NAMES_OFFSET - FONT_OFFSET or len(patch) > UI_OFFSET - PATCH_OFFSET:
        raise ValueError('Chinese font or language writes exceed extra-RAM reservations')
    if patch[:4] != b'DWLP':
        raise ValueError('Chinese container needs checked DWLP language writes')
    if ui is None:
        ui = compact_font()
    if validate_compact(ui) != struct.unpack_from('<I',font,20)[0] + struct.unpack_from('<I',font,24)[0]:
        raise ValueError('Chinese font cell sets differ')
    if len(ui) > PREFIX_SIZE - UI_OFFSET:
        raise ValueError('Chinese compact font exceeds reservation')
    prefix = bytearray(PREFIX_SIZE)
    prefix[UI_OFFSET:UI_OFFSET+len(ui)] = ui
    if english_names is not None:
        validate_names(english_names)
        prefix[EN_NAMES_OFFSET:EN_NAMES_OFFSET+len(english_names)] = english_names
    prefix[MODULE_OFFSET:MODULE_OFFSET+len(module)] = module
    prefix[FONT_OFFSET:FONT_OFFSET+len(font)] = font
    if names is not None:
        validate_names(names)
        prefix[NAMES_OFFSET:NAMES_OFFSET+len(names)] = names
    prefix[PATCH_OFFSET:PATCH_OFFSET+len(patch)] = patch
    payload, entries, locations, hashes, seen, source_bytes = bytearray(), [], {}, {}, set(), {}
    for resource in sorted(resources, key=lambda r:(r['name'],r.get('story',0))):
        name, story, data = resource['name'], resource.get('story',0), resource['data']
        if story not in (0,1) or not data:
            raise ValueError('invalid Chinese resource story/size')
        hashed = key(name)
        if not hashed or (hashed in hashes and hashes[hashed] != name):
            raise ValueError('Chinese resource filename hash collision')
        hashes[hashed] = name
        if (hashed, story) in seen:
            raise ValueError('duplicate Chinese resource route')
        seen.add((hashed, story))
        digest = ('source', resource['source']) if 'source' in resource else ('sha256', hashlib.sha256(data).digest())
        if digest in source_bytes and source_bytes[digest] != data:
            raise ValueError('Chinese source alias has different bytes')
        source_bytes[digest] = data
        if digest not in locations:
            locations[digest] = (PREFIX_SIZE + len(payload)) // SECTOR
            payload += data + bytes(-len(data) % SECTOR)
        entries.append((hashed, story | (2 if resource.get('signs') else 0), locations[digest], len(data)))
    if len(entries) * ENTRY.size > PATCH_OFFSET - DIRECTORY_OFFSET:
        raise ValueError('Chinese directory exceeds its extra-RAM reservation')
    for i, row in enumerate(entries):
        ENTRY.pack_into(prefix, DIRECTORY_OFFSET + i*ENTRY.size, *row)
    HEADER.pack_into(prefix,0,MAGIC,1,PREFIX_SIZE,len(module),len(font),len(entries),len(patch),fnv(prefix[32:]))
    result = bytes(prefix + payload)
    validate(result)
    return result


def validate(data):
    if len(data) < PREFIX_SIZE:
        raise ValueError('truncated Chinese container prefix')
    magic,version,size,module_size,font_size,count,patch_size,checksum = HEADER.unpack_from(data)
    if (magic,version,size) != (MAGIC,1,PREFIX_SIZE):
        raise ValueError('unsupported Chinese container format')
    if not 0 < module_size <= FONT_OFFSET - MODULE_OFFSET or font_size > NAMES_OFFSET-FONT_OFFSET or patch_size > UI_OFFSET-PATCH_OFFSET:
        raise ValueError('Chinese container component exceeds reservation')
    if count * ENTRY.size > PATCH_OFFSET-DIRECTORY_OFFSET or fnv(data[32:PREFIX_SIZE]) != checksum:
        raise ValueError('Chinese container directory/checksum failure')
    from tools.chinese import validate_font
    validate_font(data[FONT_OFFSET:FONT_OFFSET+font_size])
    validate_names(data[NAMES_OFFSET:NAMES_OFFSET+NAME_COUNT*NAME_SIZE])
    validate_names(data[EN_NAMES_OFFSET:EN_NAMES_OFFSET+NAME_COUNT*NAME_SIZE])
    compact_size = struct.unpack_from('<I', data, UI_OFFSET+8)[0] * 18 + 32
    if validate_compact(data[UI_OFFSET:UI_OFFSET+compact_size]) != struct.unpack_from('<I',data,FONT_OFFSET+20)[0] + struct.unpack_from('<I',data,FONT_OFFSET+24)[0]:
        raise ValueError('Chinese font cell sets differ')
    patch = data[PATCH_OFFSET:PATCH_OFFSET+patch_size]
    if patch[:4] != b'DWLP' or len(patch) < 8:
        raise ValueError('invalid Chinese language writes')
    at = 8
    for _ in range(struct.unpack_from('<I',patch,4)[0]):
        if at+8 > len(patch):raise ValueError('truncated Chinese language write')
        address,length = struct.unpack_from('<II',patch,at);at += 8
        if address < 0x80090000 or address + length > 0x80200000 or at + length > len(patch):
            raise ValueError('Chinese language write outside resident data')
        at += (length+3)&~3
    if at != len(patch):raise ValueError('Chinese language write size mismatch')
    seen=set()
    for i in range(count):
        hashed,flags,sector,length = ENTRY.unpack_from(data,DIRECTORY_OFFSET+i*ENTRY.size)
        if not 0 < hashed <= 0xffffff or flags & ~3 or not length or sector*SECTOR < PREFIX_SIZE or sector*SECTOR+length > len(data):
            raise ValueError('Chinese resource outside container bounds')
        if (hashed,flags&1) in seen:raise ValueError('duplicate Chinese resource route')
        seen.add((hashed,flags&1))
    return count


def from_plan(plan_path, module_path, font_path, patch_path, output):
    plan=json.loads(Path(plan_path).read_text(encoding='utf-8'))
    root = Path(plan_path).resolve().parent.parent
    resources=[{**row,'data':(root / row['source']).read_bytes()} for row in plan['CHINESE_RESOURCES']]
    result=build(Path(module_path).read_bytes(),Path(font_path).read_bytes(),Path(patch_path).read_bytes(),resources,
                 species_names(root / 'species'), english_names=latin_species_names(root / 'species'))
    Path(output).write_bytes(result)
    return hashlib.sha256(result).hexdigest()


def compact_font():
    from tools import chinese as zh
    chars = zh.ASCII + ''.join(zh.repertoire())
    glyphs = zh.read_json(zh.ROOT / 'tools/font/chinese-ui.json')['glyphs']
    return struct.pack('<4s7I', b'DWZ8', 1, len(chars), 18, 0, 0, 0, 0) + b''.join(
        struct.pack('<9H', *glyphs[c]) for c in chars)


def validate_compact(data):
    if len(data) < 32:
        raise ValueError('truncated Chinese compact font')
    magic, version, count, stride, *reserved = struct.unpack_from('<4s7I', data)
    if magic != b'DWZ8' or version != 1 or stride != 18 or not 95 <= count <= 12127 or any(reserved) or len(data) != 32+count*18:
        raise ValueError('invalid Chinese compact font')
    for at in range(32, len(data), 18):
        if not 1 <= struct.unpack_from('<H', data, at)[0] <= 8:
            raise ValueError('invalid Chinese compact glyph width')
    return count


def latin_species_names(folder):
    result = bytearray(NAME_COUNT * NAME_SIZE)
    for path in sorted(Path(folder).glob('*.json')):
        row = json.loads(path.read_text())
        encoded = row['name'].encode('ascii')
        if len(encoded) >= NAME_SIZE:
            raise ValueError('English registration name exceeds record')
        at = row['id'] * NAME_SIZE
        result[at:at+len(encoded)] = encoded
    validate_names(result)
    return bytes(result)


def validate_names(names):
    if len(names) != NAME_COUNT * NAME_SIZE:
        raise ValueError('Chinese species names have the wrong capacity')
    for at in range(0, len(names), NAME_SIZE):
        row = names[at:at+NAME_SIZE]
        end = row.find(b'\0')
        if end < 0 or any(row[end:]):
            raise ValueError('Chinese species name lacks a padded terminator')
        i = 0
        while i < end:
            if row[i] < 128:
                if not 32 <= row[i] <= 126:
                    raise ValueError('Chinese species name has a control byte')
                i += 1
            else:
                from tools.chinese import code_to_index
                if i+1 >= end:
                    raise ValueError('Chinese species name splits a two-byte glyph')
                code_to_index(row[i] * 256 + row[i+1])
                i += 2


def species_names(folder):
    from tools import chinese as zh
    glossary = zh.read_json(zh.ROOT / 'text/zh-hans/glossary.json')
    terms = {k:v['zh'] for k,v in glossary['species'].items()}
    terms.update(glossary.get('provisional', {}))
    result = bytearray(NAME_COUNT * NAME_SIZE)
    seen = set()
    for path in sorted(Path(folder).glob('*.json')):
        row = zh.read_json(path)
        if row['id'] in seen or not 0 <= row['id'] < NAME_COUNT:
            raise ValueError('duplicate/out-of-range Chinese species name')
        seen.add(row['id'])
        name = terms.get(row['name']) if row['name'] else ''
        if name is None:
            # Non-species records (sentinels and human actors) also need authored names.
            name = glossary.get('terms', {}).get(row['name'])
            if isinstance(name, dict):name = name['zh']
        if name is None:
            raise ValueError('missing Chinese species term: ' + row['name'])
        encoded = zh.encode(name, zh.repertoire())
        if len(encoded) >= NAME_SIZE:
            raise ValueError('Chinese species name exceeds its fixed record: ' + name)
        at = row['id'] * NAME_SIZE
        result[at:at+len(encoded)] = encoded
    if not seen:
        raise ValueError('Chinese names require the selected species records')
    validate_names(result)
    return bytes(result)


def localize_native_names(executable, elf, names):
    """Change the Chinese image before the all-language union writes are generated."""
    from tools.langpatch import elf_symbols
    validate_names(names)
    address, size, _ = elf_symbols(elf)['DIGIMON_DATA']
    if size != 180 * 52:
        raise ValueError('unexpected native species record layout')
    image = bytearray(Path(executable).read_bytes())
    if image[:8] != b'PS-X EXE':raise ValueError('not a PS-X executable')
    load, length = struct.unpack_from('<II', image, 0x18)
    start = address - load + 0x800
    if start < 0x800 or start + size > 0x800 + length:
        raise ValueError('native species records outside executable')
    for i in range(1, 180):
        name = names[i*NAME_SIZE:(i+1)*NAME_SIZE]
        if name[0]:image[start+i*52:start+i*52+20] = name
    Path(executable).write_bytes(image)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'finish'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tree', type=Path)
    args = parser.parse_args(argv)
    root = args.out
    plan_path = root / 'derived/plan.json'
    plan = json.loads(plan_path.read_text())
    if not plan.get('CHINESE_RESOURCES'):
        return
    names = species_names(root / 'species')
    if args.command == 'prepare':
        if args.tree is None:parser.error('prepare requires --tree')
        localize_native_names(root / 'exe-zh-hans/SLUS_010.32',
                              args.tree / 'build/us/psx/gcc/SLUS_010.32.elf', names)
        return
    from tools import chinese as zh
    from tools.langpatch import section_functions, overlay_code_differs
    elf = root / 'exe-en/SLUS_010.32.elf'
    if not elf.exists() and args.tree:
        elf = args.tree / 'build/us/psx/gcc/SLUS_010.32.elf'
    for spec in plan['CHINESE_OVL']:
        original, target = spec.split(':')
        base = (root / 'exe-en' / original).read_bytes()
        translated = (root / 'exe-zh-hans' / original).read_bytes()
        functions = section_functions(elf, '.'+original.removesuffix('_REL.BIN'))
        if len(base) != len(translated) or (functions and overlay_code_differs(base, translated, functions[1], functions[0])):
            raise ValueError('Chinese overlay changes code/layout: ' + original)
        (root / 'lang' / target).write_bytes(translated)
    path = root / 'lang/LANGZH.BIN'
    font = zh.build_font(zh.read_json(zh.ROOT / zh.FONT_PATH), zh.repertoire())
    module = (root / 'exe-zh-hans/ZH_REL.BIN').read_bytes()
    entries = [{**r, 'data':(root / r['source']).read_bytes()} for r in plan['CHINESE_RESOURCES']]
    path.write_bytes(build(module, font, path.read_bytes(), entries, names, english_names=latin_species_names(root / 'species')))
    print(f'Chinese container: {len(entries)} routes, {len(font)} font bytes, {path.stat().st_size} bytes')


if __name__ == '__main__':
    main()
