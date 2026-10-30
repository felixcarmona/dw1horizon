"""Whole-record payload witnesses and generated NULL array fields."""
import copy
import hashlib
import io
from pathlib import Path
import struct
import sys
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import codecopy
import dwpatch as dw
import tabledata


class TableDataTests(unittest.TestCase):
    def fixture(self):
        target = b''.join(struct.pack('<II', i, 0x80090000 + i * 4) for i in range(6))
        original = b'prefix00' + b''.join(struct.pack('<II', i, 0x800a0000 + i * 12) for i in range(6))
        obj = dict(offset=0, length=len(target), section='.data.opcodes', source='src/main/effects.c')
        words = [[i * 8 + 4, '.main', 0x80090000, i * 4] for i in range(6)]
        sources = {'us': {'ORIGINAL': original}, 'eu': {'REGIONAL': original + b'end'}}
        recipes = tabledata.prepare([obj], words, target, sources)
        return target, obj, words, sources, recipes

    def test_whole_masked_record_from_different_player_files(self):
        target, obj, words, sources, recipes = self.fixture()
        self.assertEqual(len(recipes), 1)
        images = {key: types.SimpleNamespace(read=lambda p, files=files: files[p]) for key, files in sources.items()}
        tabledata.verify(recipes, [obj], words, target, images)
        for key, image in images.items():
            self.assertEqual(tabledata.tail(recipes, key, image.read), b''.join(struct.pack('<I', i) for i in range(6)))

    def test_missing_or_disordered_payload_cannot_use_number_dictionary(self):
        target, obj, words, sources, recipes = self.fixture()
        sources['eu']['REGIONAL'] = b''.join(struct.pack('<II', i, 0) for i in reversed(range(6)))
        self.assertEqual(tabledata.prepare([obj], words, target, sources), [])
        # A single four-byte non-pointer field is insufficient evidence.
        self.assertEqual(tabledata.prepare([dict(obj, length=8)], words[:1], struct.pack('<II', 1, 0x80090000), sources), [])

    def test_source_pin_and_object_layout_are_mandatory(self):
        target, obj, words, sources, recipes = self.fixture()
        images = {key: types.SimpleNamespace(read=lambda p, files=files: files[p]) for key, files in sources.items()}
        for bad_obj, bad_words in ((dict(obj, length=40), words), (obj, words[:-1]),
                                   (dict(obj, source='asm/main/data/main_bss_0.data.s'), words)):
            with self.subTest(obj=bad_obj, words=bad_words), self.assertRaises(ValueError):
                tabledata.verify(recipes, [bad_obj], bad_words, target, images)
        sources['eu']['REGIONAL'] += b'changed'
        with self.assertRaisesRegex(ValueError, 'pinned'):
            tabledata.tail(recipes, 'eu', images['eu'].read)

    def test_null_generation_requires_complete_relocated_pointer_array(self):
        obj = dict(offset=0, length=12, section='.data.pointers', source='src/main/example.c')
        words = [[0, '.main', 0x80090000, 4], [8, '.main', 0x80090000, 8]]
        target = struct.pack('<III', 0x80090004, 0, 0x80090008)
        recipes = tabledata.prepare([obj], words, target, {'us': {}})
        self.assertEqual(recipes[0]['kind'], 'nulls')
        tabledata.verify(recipes, [obj], words, target, {'us': None})
        self.assertEqual(tabledata.tail(recipes, 'us', None), bytes(4))
        for changed in (target[:4] + b'ABCD' + target[8:],):
            with self.assertRaises(ValueError):
                tabledata.verify(recipes, [obj], words, changed, {'us': None})

    def test_player_reconstruction_strictly_copies_each_payload_destination(self):
        target, obj, words, sources, recipes = self.fixture()
        old = bytes(len(target))
        tail = tabledata.tail(recipes, 'us', sources['us'].__getitem__)
        cursor = 4 * len(words)
        copies = []
        for offset, size in tabledata.layout(recipes):
            copies.append([offset, size, len(old) + cursor]); cursor += size
        controls, diff, extra = codecopy.generate_linker_words([[len(target), 0, 0]], target, b'', len(old),
            words, copies, tail_size=cursor)
        entry = dict(size=len(target), sha1=hashlib.sha1(target).hexdigest(), linker_words=words,
            table_recipes=recipes, bases={'us': dict(source='BOOT', source_sha1=hashlib.sha1(old).hexdigest(),
                control=controls, diff=[0, len(diff)], extra=[len(diff), len(extra)])})
        reader = lambda path: old if path == 'BOOT' else sources['us'][path]
        self.assertEqual(set(diff), {0})
        self.assertEqual(dw.apply_binary_delta(entry, 'us', reader, diff + extra), target)
        bad = bytearray(diff); bad[0] = 1
        with self.assertRaises(dw.PatchError):
            dw.apply_binary_delta(entry, 'us', reader, bad + extra)
        entry['table_recipes'][0]['fields'][0][0] += 1
        with self.assertRaises((ValueError, dw.PatchError)):
            dw.apply_binary_delta(entry, 'us', reader, diff + extra)


class AuthoredPayloadTests(unittest.TestCase):
    def test_banner_and_standard_encoding_have_no_supplied_byte_payload(self):
        import fontcopy
        for language in ('es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca'):
            data = fontcopy.semantic_table('banner', [language])
            obj = dict(offset=7, length=len(data), section='.data.BTL_BATTLE_START_TEXT_POSITIONS', source='src/btl/battle_effect.c')
            recipe = tabledata.authored_recipe(obj, data)
            self.assertIsNotNone(recipe)
            self.assertEqual(fontcopy.table_tail([recipe], 'eu', None), data)
            changed = bytes([data[0] ^ 1]) + data[1:]
            self.assertIsNone(tabledata.authored_recipe(obj, changed))
        codes = fontcopy.semantic_table('sjis', [])
        self.assertEqual(len(codes), 33 * 4)
        for jis, ascii_code in struct.iter_unpack('<HH', codes):
            self.assertTrue(0x20 <= ascii_code < 0x7f)
            self.assertEqual(len(jis.to_bytes(2, 'big').decode('cp932')), 1)
        with self.assertRaises(ValueError):
            fontcopy.semantic_table('sjis', ['byte palette'])

    def test_complete_authored_bank_text_is_generated_and_stale_content_fails(self):
        import fontcopy
        root = str(Path(__file__).resolve().parents[1])
        bank = fontcopy.authored_bank(root, 'en')
        key = 'main.ITEM_NAMES.1'
        data = fontcopy.semantic_table('text', ['en', key, 20])
        obj = dict(offset=3, length=20, section='.data.label', source='src/main/test.c')
        recipe = tabledata.authored_recipe(obj, data)
        self.assertIsNotNone(recipe)
        self.assertEqual(fontcopy.table_tail([recipe], 'us', None), data)
        with self.assertRaises(ValueError):
            tabledata.verify([recipe], [obj], [], b'abc' + b'X' * 20, {'us': None})

    def test_items_witness_numeric_fields_and_generate_only_authored_overrides(self):
        import fontcopy
        root = str(Path(__file__).resolve().parents[1])
        bank = fontcopy.authored_bank(root, 'en')
        content = fontcopy.item_content(root)
        target = bytearray()
        for index in range(128):
            name = fontcopy.encode_bank(bank['text'][f'main.ITEM_NAMES.{index}'], bank)
            target.extend(name.ljust(20, b'\0'))
            for field, fmt in fontcopy.ITEM_NUMERIC_FIELDS:
                target.extend(struct.pack('<' + fmt, content[index][field]))
        original = bytearray(target)
        struct.pack_into('<H', original, 3 * 32 + 24, 20)
        sources = {'us': {'ORIGINAL': bytes(original)}}
        obj = dict(offset=0, length=4096, section='.data.ITEM_PARA', source='src/main/item.c')
        recipe = tabledata.item_recipe(obj, target, sources)
        self.assertEqual(recipe['sources']['us'][-1], [[3, 'meritValue']])
        image = types.SimpleNamespace(read=sources['us'].__getitem__)
        tabledata.verify([recipe], [obj], [], target, {'us': image})
        self.assertEqual(fontcopy.item_table(recipe, 'us', image.read), target)
        # Unsupported target numeric data cannot acquire an authored override.
        struct.pack_into('<H', target, 3 * 32 + 24, 65530)
        self.assertIsNone(tabledata.item_recipe(obj, target, sources))


class RegionalLayoutTests(unittest.TestCase):
    def test_header_payload_comes_from_each_player_without_replacing_linked_address(self):
        def header(size):
            return struct.pack('<8I', 0x316f574d, 1, 0x80010000, size, 48, 0, 0, 0) + b'BTL_REL.BIN\0'.ljust(32, b'\0')
        obj = dict(offset=16, length=64, section='.rodata.header', source='asm/btl/data/header.rodata.s')
        words = [[24, '.BTL', 0x80060000, 0]]
        sources = {'us': {'BTL_REL.BIN': header(100)}, 'eu': {'BTL_REL.BIN': header(120)}}
        target = b'X' * 16 + header(100)
        recipe = tabledata.header_recipe(obj, target[16:], sources, words)
        self.assertIsNotNone(recipe)
        self.assertNotIn([8, 4], recipe['fields'])
        images = {key: types.SimpleNamespace(read=files.__getitem__) for key, files in sources.items()}
        regional = {'us': target, 'eu': b'X' * 16 + header(120)}
        tabledata.verify([recipe], [obj], words, target, images, regional)
        with self.assertRaises(ValueError):
            tabledata.verify([recipe], [obj], words, target, images, {'us': target, 'eu': target})

    def test_ui_coordinates_require_the_original_code_reference(self):
        import fontcopy
        raw = bytearray(256)
        struct.pack_into('<II', raw, 0, 0x3c028009, 0x24420040)
        for i in range(9):
            struct.pack_into('<hhhBB', raw, 64+i*8, i-100, i*10, 20, 0, 0)
        recipe = dict(ui='STATS_VIEW_TEXT', size=72,
            sources={'eu': ['BOOT', 64, 72, hashlib.sha1(raw).hexdigest(), [0, 4]]})
        got = fontcopy.ui_table(recipe, 'eu', lambda _: raw)
        for i in range(9):
            self.assertEqual(got[i*8:i*8+4], raw[64+i*8:64+i*8+4])
        self.assertEqual(struct.unpack_from('<hBB', got, 4), (48, 72, 48))
        self.assertEqual(struct.unpack_from('<hBB', got, 60), (0, 0, 48))
        struct.pack_into('<I', raw, 4, 0x24420044)
        recipe['sources']['eu'][3] = hashlib.sha1(raw).hexdigest()
        with self.assertRaisesRegex(ValueError, 'address reference'):
            fontcopy.ui_table(recipe, 'eu', lambda _: raw)

    def test_zeros_do_not_supply_nonzero_adjacent_payload(self):
        fixture = TableDataTests()
        target, obj, words, sources, unused = fixture.fixture()
        for key, files in sources.items():
            path = next(iter(files)); raw = bytearray(files[path])
            struct.pack_into('<I', raw, 8, 0x12345678)
            files[path] = bytes(raw)
        recipes = tabledata.prepare([obj], words, target, sources)
        self.assertEqual(recipes[0]['zeros'], [0])
        images = {key: types.SimpleNamespace(read=files.__getitem__) for key, files in sources.items()}
        tabledata.verify(recipes, [obj], words, target, images)
        recipes[0]['zeros'].append(8)
        with self.assertRaisesRegex(ValueError, 'zero words'):
            tabledata.verify(recipes, [obj], words, target, images)




class NaturalMemberTests(unittest.TestCase):
    def test_sized_jump_table_null_is_generated_without_clearing_its_gap(self):
        target = struct.pack('<III', 0x80090000, 0, 0xdeadbeef)
        member = dict(offset=0, length=8, section='.rodata.jtbl', source='asm/main/data/psyq/libspu.rodata.s')
        outer = dict(offset=0, length=12, section='.rodata', source=member['source'], members=[member])
        words = [[0, '.main', 0x80090000, 0]]
        recipes = tabledata.prepare([outer], words, target, {'us': {'MAIN': bytes(12)}})
        self.assertEqual(tabledata.layout(recipes), [[4, 4]])
        tabledata.verify(recipes, [outer], words, target, {'us': types.SimpleNamespace(read=lambda _: bytes(12))})
        changed = copy.deepcopy(outer); changed['members'][0]['length'] = 12
        with self.assertRaisesRegex(ValueError, 'natural'):
            tabledata.verify(recipes, [changed], words, target, {'us': None})

    def test_nested_diagnostic_formats_keep_their_distinct_slots(self):
        import fontcopy
        import json
        rows = json.loads((Path(__file__).parent/'patcher/sdk-messages.json').read_text())['libgs']
        data = b''.join((r['text'].encode()+b'\0').ljust(r['size'], b'\0') for r in rows[1:3])
        obj = dict(offset=0, length=len(data), section='.rodata.diagnostics', source='asm/main/data/psyq/libgs.rodata.s')
        recipe = tabledata.authored_recipe(obj, data)
        self.assertEqual(recipe['fields'], [[0, len(data)]])
        self.assertEqual(fontcopy.semantic_table(recipe['generator'], recipe['params']), data)
        corrupted = data[:-1]+b'x'
        self.assertIsNone(tabledata.authored_recipe(obj, corrupted))

    def test_sound_index_builder_passes_current_pointer_evidence_to_generator(self):
        import fontcopy
        limits = fontcopy.semantic_table('sound_index_limits', [])
        target = b''.join(struct.pack('<II', 0x80090000+i*8, 0x80140000+i*8) + limits[i*4:i*4+4]
                          for i in range(4))
        obj = dict(offset=0, length=48, section='.rodata.SOUND_INDEX_FILES', source='src/main/sound.c')
        words = [[i*12+j, '.main', 0x80090000, i*8] for i in range(4) for j in (0, 4)]
        recipes = tabledata.prepare([obj], words, target, {'us': {'MAIN': bytes(48)}})
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]['generator'], 'sound_index_limits')
        self.assertEqual(tabledata.tail(recipes, 'us', lambda _: bytes(48)), limits)
        tabledata.verify(recipes, [obj], words, target, {'us': None})
        self.assertEqual(tabledata.prepare([obj], [], target, {'us': {'MAIN': bytes(48)}}), [])

    def test_mmio_constants_require_reviewed_name_and_exact_hardware_value(self):
        obj = dict(offset=0, length=4, section='.data.COMMON_DELAY', source='asm/main/data/psyq/libcd.data.s')
        data = struct.pack('<I', 0x1f801020)
        recipe = tabledata.authored_recipe(obj, data)
        self.assertEqual(recipe['generator'], 'cd_register')
        self.assertIsNone(tabledata.authored_recipe(obj, struct.pack('<I', 0x1f801024)))
        obj['source'] = 'src/arbitrary.c'
        self.assertIsNone(tabledata.authored_recipe(obj, data))


if __name__ == '__main__':
    unittest.main()
