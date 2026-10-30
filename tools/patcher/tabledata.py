"""Player-side table payloads bound to current natural linker objects.

Recipes contain source coordinates or semantic inputs, never inherited bytes.
Pointer masks come exclusively from current ELF relocations. A masked record
must supply at least sixteen equal non-pointer bytes in its original layout.
"""
import hashlib
from pathlib import Path
import struct
from functools import lru_cache
import fontcopy



def fields(obj, words):
    start, size = obj['offset'], obj['length']
    pointers = [r[0] for r in words if start <= r[0] and r[0] + 4 <= start + size]
    result, cursor = [], start
    for pointer in pointers:
        if cursor < pointer:
            result.append([cursor - start, pointer - cursor])
        cursor = pointer + 4
    if cursor < start + size:
        result.append([cursor - start, start + size - cursor])
    return pointers, result


from fontcopy import table_layout as layout, table_tail as tail



@lru_cache(maxsize=4)
def authored_texts(root):
    result = {}
    for language in ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca'):
        bank = fontcopy.authored_bank(root, language)
        for key, text in bank['text'].items():
            data = fontcopy.encode_bank(text, bank)
            if len(data) >= 7:
                result.setdefault(data, (language, key))
    return result


def authored_recipe(obj, data, tool_root=None, words=()):
    root = str(Path(tool_root) if tool_root else Path(__file__).resolve().parents[2])
    name = obj['section'].split('.')[-1]
    choices = []
    if name == 'SOUND_INDEX_FILES' and obj['source'] == 'src/main/sound.c':
        pointers, payload = fields(obj, words)
        if (len(data) == 48 and [p-obj['offset'] for p in pointers] ==
                [i*12+j for i in range(4) for j in (0, 4)] and
                payload == [[i*12+8, 4] for i in range(4)] and
                b''.join(data[a:a+n] for a,n in payload) == fontcopy.semantic_table('sound_index_limits', [])):
            return dict(offset=obj['offset'], size=obj['length'], section=obj['section'], kind='semantic',
                        fields=payload, generator='sound_index_limits', params=[])
    if obj['source'] == 'asm/main/data/psyq/libcd.data.s' and name in fontcopy.CD_REGISTERS:
        choices = [('cd_register', [name])]
    elif name == 'voice_on' and obj['source'] == 'asm/main/data/psyq/libsnd.data.s':
        choices = [('muted_voices', [])]
    elif name == 'KAR_D_8005AF58' and obj['source'] == 'src/kar/kar.c':
        pointers, payload = fields(obj, words)
        count = len(pointers)
        if ([p - obj['offset'] for p in pointers] == list(range(0, count * 4, 4))
                and payload == [[count * 4, 4]] and data[count * 4:] == struct.pack('<I', count)):
            return dict(offset=obj['offset'], size=obj['length'], section=obj['section'], kind='semantic',
                        fields=payload, generator='pointer_count', params=[count])
    if name in ('STD_INTRO_DIGIMON_NAMES', 'VS__INTRO_DIGIMON_NAMES'):
        choices = [('empty_sprite_names', [112 if name.startswith('STD') else 116])]
    elif obj['section'] == '.rodata.drawMainMenuStrings.str1.4' and len(data) == 26:
        choices = [('menu_picker', [])]
    elif name == 'ITEM_MENU_LABELS':
        choices = [('inventory_labels', [lang]) for lang in ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca')]
    elif name == 'VS_VERSUS_TEXT_PIECES' and len(data) == 294:
        for english in (True, False):
            piece = fontcopy.semantic_table('versus_mode', [english])
            if data[140:154] == piece:
                return dict(offset=obj['offset'], size=obj['length'], section=obj['section'],
                            kind='semantic', fields=[[140, 14]], generator='versus_mode', params=[english])
    elif name == 'NAMING_ROLLOVER_CHARS':
        choices = [('keyboard_rollover', [])]
    elif name == 'NAMING_CTRL_BOXES':
        choices = [('keyboard_boxes', [english]) for english in (True, False)]
    elif obj['source'] in ('asm/main/data/psyq/libgs.rodata.s', 'asm/main/data/psyq/libmcrd.rodata.s',
                           'asm/main/data/psyq/libspu.rodata.s'):
        import json
        sdk = Path(obj['source']).name.split('.')[0]
        messages = json.loads(Path(__file__).with_name('sdk-messages.json').read_text())[sdk]
        spans = []
        # Longer diagnostics can contain a shorter format string. Reserve the
        # complete longer slot before locating the shorter standalone slot.
        for index, row in sorted(enumerate(messages), key=lambda pair: -pair[1]['size']):
            chunk = (row['text'].encode() + b'\0').ljust(row['size'], b'\0')
            hits, at = [], data.find(chunk)
            while at >= 0:
                if not any(a < at+len(chunk) and at < a+n for a,n,_ in spans):
                    hits.append(at)
                at = data.find(chunk, at+1)
            if len(hits) == 1:
                at = hits[0]
                end = min(len(data), (at+len(chunk)+3)//4*4)
                if any(data[at+len(chunk):end]):
                    end = at+len(chunk)
                spans.append([at, end-at, index])
        if spans:
            spans.sort()
            # Sized diagnostic labels may include empty strings/alignment.
            # Regenerate the complete layout only if it is exactly reproduced.
            params = [sdk, len(data), spans]
            if fontcopy.semantic_table('sdk_layout', params, root) == data:
                return dict(offset=obj['offset'], size=obj['length'], section=obj['section'], kind='semantic',
                            fields=[[0, len(data)]], generator='sdk_layout', params=params)
    elif obj['source'] == 'asm/main/data/psyq/libsnd.data.s':
        pitch = fontcopy.semantic_table('pitch', [])
        at = data.find(pitch)
        if at >= 0 and data.find(pitch, at + 1) < 0:
            return dict(offset=obj['offset'], size=obj['length'], section=obj['section'],
                        kind='semantic', fields=[[at, len(pitch)]], generator='pitch', params=[])
    elif name.endswith('_BATTLE_START_TEXT_POSITIONS'):
        choices = [('banner', [language]) for language in ('es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca')]
    elif name == 'CHAR_MAPPING_SPECIAL':
        choices = [('sjis', [])]
    elif name == 'SAVEGAME_ID_LABEL':
        choices = [('save_ids', [])]
    elif len(data) >= 16 and data.rstrip(b'\0') in authored_texts(root):
        language, key = authored_texts(root)[data.rstrip(b'\0')]
        choices = [('text', [language, key, len(data)])]
    for generator, params in choices:
        if fontcopy.semantic_table(generator, params, root) == data:
            return dict(offset=obj['offset'], size=obj['length'], section=obj['section'],
                        kind='semantic', fields=[[0, len(data)]], generator=generator, params=params)
    return None



def item_recipe(obj, data, sources):
    if obj['section'] != '.data.ITEM_PARA' or obj['length'] != 128 * 32:
        return None
    root = str(Path(__file__).resolve().parents[2])
    language = None
    for lang in ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca'):
        bank = fontcopy.authored_bank(root, lang)
        if all(f'main.ITEM_NAMES.{i}' in bank['text'] and
               fontcopy.encode_bank(bank['text'][f'main.ITEM_NAMES.{i}'], bank).ljust(20, b'\0') == data[i*32:i*32+20]
               for i in range(128)):
            language = lang
            break
    if language is None:
        return None
    content = fontcopy.item_content(root)
    numeric = [data[i*32+20:i*32+32] for i in range(128)]
    found = {}
    for key, files in sources.items():
        for path, raw in files.items():
            stride = 32 if key in ('us', 'jp1') else 12
            offset = raw.find(numeric[0])
            while offset >= 0:
                if offset + 127*stride+12 > len(raw):
                    break
                equal_rows = sum(raw[offset+i*stride:offset+i*stride+12] == numeric[i] for i in range(128))
                if equal_rows >= 120:  # candidate discovery only; every output field is verified below
                    overrides = []
                    good = True
                    for index in range(128):
                        at = 0
                        for field, fmt in fontcopy.ITEM_NUMERIC_FIELDS:
                            size = struct.calcsize('<' + fmt)
                            old = raw[offset+index*stride+at:offset+index*stride+at+size]
                            new = numeric[index][at:at+size]
                            if old != new:
                                value, = struct.unpack('<' + fmt, new)
                                if content.get(index, {}).get(field) != value:
                                    good = False
                                    break
                                overrides.append([index, field])
                            at += size
                        if not good:
                            break
                    if good:
                        found[key] = [path, offset, stride, hashlib.sha1(raw).hexdigest(), overrides]
                        break
                offset = raw.find(numeric[0], offset+1)
            if key in found:
                break
    if len(found) != len(sources):
        return None
    return dict(offset=obj['offset'], size=obj['length'], section=obj['section'], kind='items',
                language=language, fields=[[0, len(data)]], sources=found)



def aura_recipe(obj, data, sources):
    if not obj['section'].endswith('_AURA_PROJECTILE_TYPES') or len(data) != 129 * 12:
        return None
    import json
    authored = json.loads((Path(__file__).resolve().parents[2] / 'content/tables/effects.json').read_text())['auraTypes']
    names = ('type', 'unk2', 'unk4', 'unk6', 'unk8', 'u')
    found = {}
    for key, files in sources.items():
        for path, raw in files.items():
            at = raw.find(data[:12])
            while at >= 0 and at + len(data) <= len(raw):
                if sum(raw[at+i:at+i+12] == data[i:i+12] for i in range(0, len(data), 12)) >= 120:
                    overrides, good = [], True
                    for i in range(129):
                        for j, name in enumerate(names):
                            before, = struct.unpack_from('<h', raw, at + i*12 + j*2)
                            after, = struct.unpack_from('<h', data, i*12 + j*2)
                            if before != after:
                                if authored[i][name] != after:
                                    good = False
                                    break
                                overrides.append([i, name])
                        if not good:
                            break
                    if good:
                        found[key] = [path, at, hashlib.sha1(raw).hexdigest(), overrides]
                        break
                at = raw.find(data[:12], at + 1)
            if key in found:
                break
    if len(found) != len(sources):
        return None
    return dict(offset=obj['offset'], size=obj['length'], section=obj['section'], kind='aura',
                fields=[[0, len(data)]], sources=found)



def zero_words(obj, words, data):
    pointers, payload = fields(obj, words)
    return [i for i in range(0, len(data) - 3, 4)
            if data[i:i+4] == bytes(4)
            and any(a <= i and i+4 <= a+n for a, n in payload)]


def masked_record(obj, words, target, raw, zeros):
    _, payload = fields(obj, words)
    start, size = obj['offset'], obj['length']
    fields_to_match = []
    for inner, length in payload:
        cursor = inner
        for zero in zeros:
            if inner <= zero and zero+4 <= inner+length:
                if cursor < zero:
                    fields_to_match.append((cursor, zero))
                cursor = zero+4
        if cursor < inner+length:
            fields_to_match.append((cursor, inner+length))
    if sum(b-a for a,b in fields_to_match) < 16:
        return None
    a,b = max(fields_to_match, key=lambda r: r[1]-r[0])
    data = target[start:start+size]
    at = raw.find(data[a:b])
    while at >= 0:
        source = at-a
        if (source >= 0 and source+size <= len(raw)
                and all(raw[source+x:source+y] == data[x:y] for x,y in fields_to_match)):
            return source
        at = raw.find(data[a:b], at+1)
    return None


def natural_objects(objects):
    # Only recipes use the finer retained labels. Full map objects and their
    # gaps remain independently covered by the publication audit.
    return [member for obj in objects for member in obj.get('members', [obj])]


def prepare(objects, words, target, sources):
    """Discover complete records in each player's corresponding regional file.

    sources maps each base to {path: bytes}. Search order is deterministic and
    source hashes pin the complete original files. NULL fields are generated
    only in complete pointer arrays whose other words all have ELF evidence.
    """
    import linkerdata
    recipes = []
    for obj in sorted(natural_objects(objects), key=lambda o: o['offset']):
        if obj['section'].startswith(('.text', '.linker')) or '_bss_' in obj['source']:
            continue
        start, size = obj['offset'], obj['length']
        pointers, payload = fields(obj, words)
        data = target[start:start + size]
        authored = ui_recipe(obj, data, sources) or header_recipe(obj, data, sources, words) or (((item_recipe(obj, data, sources) or aura_recipe(obj, data, sources)) if not pointers else None) or authored_recipe(obj, data, words=words))
        if authored and any(a + start < pointer + 4 and pointer < a + start + n
                            for a, n in authored['fields'] for pointer in pointers):
            authored = None
        if authored:
            recipes.append(authored)
            continue
        if not pointers or not payload:
            continue
        if (size % 4 == 0 and all((p - start) % 4 == 0 for p in pointers)
                and all(not any(data[a:a + n]) for a, n in payload)):
            recipes.append(dict(offset=start, size=size, section=obj['section'], kind='nulls', fields=payload))
            continue
        if sum(n for _, n in payload) < 16:
            continue
        found = {}
        generated_zeros = zero_words(obj, words, data)
        for key, files in sources.items():
            for path, raw in files.items():
                offset = masked_record(obj, words, target, raw, generated_zeros)
                if offset is not None:
                    found[key] = [path, offset, hashlib.sha1(raw).hexdigest()]
                    break
        if len(found) == len(sources):
            recipe = dict(offset=start, size=size, section=obj['section'], kind='record', fields=payload, sources=found)
            if generated_zeros:
                recipe['zeros'] = generated_zeros
            recipes.append(recipe)
    layout(recipes)
    return recipes


def verify(recipes, objects, words, target, images, regional_targets=None):
    """Independently bind recipes to this build's map, ELF and real inputs."""
    layout(recipes)
    objects = natural_objects(objects)
    for recipe in recipes:
        obj = next((o for o in objects if o['offset'] == recipe['offset'] and o['length'] == recipe['size']
                    and o['section'] == recipe['section']), None)
        if obj is None or obj['section'].startswith(('.text', '.linker')) or '_bss_' in obj['source']:
            raise ValueError('table recipe lacks a current natural data object')
        pointers, payload = fields(obj, words)
        if recipe['kind'] == 'ui':
            sources = {key: {recipe['sources'][key][0]: image.read(recipe['sources'][key][0])}
                       for key, image in images.items()}
            if pointers or ui_recipe(obj, target[obj['offset']:obj['offset'] + obj['length']], sources) != recipe:
                raise ValueError('UI table lacks reviewed player code/record witnesses')
            for key, image in images.items():
                actual = (regional_targets or {}).get(key, target)
                if tail([recipe], key, image.read) != actual[obj['offset']:obj['offset'] + obj['length']]:
                    raise ValueError('regional UI fields differ from player coordinates/authored crops')
            continue
        if recipe['kind'] == 'regional_header':
            sources = {key: {recipe['sources'][key][0]: image.read(recipe['sources'][key][0])}
                       for key, image in images.items()}
            if header_recipe(obj, target[obj['offset']:obj['offset'] + obj['length']], sources, words) != recipe:
                raise ValueError('overlay header lacks current map and player witnesses')
            for key, image in images.items():
                actual = (regional_targets or {}).get(key, target)
                expected = b''.join(actual[obj['offset'] + a:obj['offset'] + a + n] for a, n in recipe['fields'])
                if tail([recipe], key, image.read) != expected:
                    raise ValueError('regional header differs from the player record')
            continue
        if recipe['kind'] == 'aura':
            sources = {key: {recipe['sources'][key][0]: image.read(recipe['sources'][key][0])}
                       for key, image in images.items()}
            if pointers or aura_recipe(obj, target[obj['offset']:obj['offset'] + obj['length']], sources) != recipe:
                raise ValueError('aura fields lack complete player-record/authored witnesses')
            for key, image in images.items():
                if tail([recipe], key, image.read) != target[obj['offset']:obj['offset'] + obj['length']]:
                    raise ValueError('generated aura table differs from current output')
            continue
        if recipe['kind'] == 'items':
            sources = {key: {recipe['sources'][key][0]: image.read(recipe['sources'][key][0])}
                       for key, image in images.items()}
            expected = item_recipe(obj, target[obj['offset']:obj['offset'] + obj['length']], sources)
            if pointers or expected != recipe:
                raise ValueError('item fields lack complete player-record/authored witnesses')
            for key, image in images.items():
                if tail([recipe], key, image.read) != target[obj['offset']:obj['offset'] + obj['length']]:
                    raise ValueError('generated item table differs from current output')
            continue
        if recipe['kind'] == 'semantic':
            expected = authored_recipe(obj, target[obj['offset']:obj['offset'] + obj['length']], words=words)
            if expected != recipe or any(a + obj['offset'] < pointer + 4 and pointer < a + obj['offset'] + n
                                         for a, n in recipe['fields'] for pointer in pointers):
                raise ValueError('semantic table differs from current authored sources')
            continue
        if not pointers or payload != recipe['fields']:
            raise ValueError('table recipe masks non-relocated payload')
        data = target[obj['offset']:obj['offset'] + obj['length']]
        if recipe['kind'] == 'nulls':
            if (obj['length'] % 4 or any((p - obj['offset']) % 4 for p in pointers)
                    or any(any(data[a:a + n]) for a, n in payload)):
                raise ValueError('generated NULL fields are not a complete pointer array')
        elif recipe['kind'] == 'record':
            zeros = recipe.get('zeros', [])
            if zeros != zero_words(obj, words, data):
                raise ValueError('generated zero words differ from the current table')
            if sum(n for _, n in payload) - 4 * len(zeros) < 16 or set(recipe['sources']) != set(images):
                raise ValueError('table record lacks whole-layout witnesses')
            for key, image in images.items():
                raw = tail([recipe], key, image.read)
                expected = b''.join(data[a:a + n] for a, n in payload)
                if raw != expected:
                    raise ValueError('table payload differs from the witnessed player record')
        else:
            raise ValueError('unknown table payload generator')


def header_recipe(obj, data, sources, words):
    if not obj['source'].endswith('/data/header.rodata.s') or len(data) != 64 or data[:4] != b'MWo1':
        return None
    pointers, payload = fields(obj, words)
    if [p - obj['offset'] for p in pointers] != [8]:
        return None
    name = data[32:64].split(b'\0', 1)[0]
    if not name.endswith(b'_REL.BIN'):
        return None
    found = {}
    for key, files in sources.items():
        for path, raw in files.items():
            hits, at = [], raw.find(b'MWo1')
            while at >= 0:
                if (at + 64 <= len(raw) and raw[at+32:at+32+len(name)+1] == name + b'\0'):
                    hits.append(at)
                at = raw.find(b'MWo1', at + 1)
            if len(hits) == 1:
                found[key] = [path, hits[0], hashlib.sha1(raw).hexdigest()]
                break
    if len(found) != len(sources):
        return None
    return dict(offset=obj['offset'], size=64, section=obj['section'], kind='regional_header',
                fields=payload, sources=found)


def ui_recipe(obj, data, sources):
    import json
    name = obj['section'].split('.')[-1]
    profiles = json.loads(Path(__file__).with_name('ui-sources.json').read_text())['objects']
    if name not in profiles:
        return None
    profile = profiles[name]
    if obj['length'] != profile['length'] or obj['source'] not in ('src/main/game_menu.c', 'src/main/script_common.c'):
        raise ValueError('regional UI data no longer has its reviewed native type')
    found = {}
    for key, files in sources.items():
        original = profile['sources'][key]
        path = original['file']
        if path not in files:
            return None
        found[key] = [path, original['offset'], original['copy_length'],
                      hashlib.sha1(files[path]).hexdigest(), original['refs']]
    recipe = dict(offset=obj['offset'], size=obj['length'], section=obj['section'], kind='ui',
                  ui=name, fields=[[0, len(data)]], sources=found)
    # The USA layout is retained; other bases supply their own panel positions.
    if 'us' in sources and fontcopy.ui_table(recipe, 'us', sources['us'].__getitem__) != data:
        raise ValueError('native USA UI crops differ from the authored drawing contract')
    return recipe
