"""Per-file delta correctness, regional selection and hostile-control checks."""
import copy
import hashlib
import random
import json
import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import codecopy
import dwpatch as dw


def entry(old, new, native=True):
    control, diff, extra = codecopy.make_delta(old, new, native=native)
    d = dict(source='BOOT', source_sha1=hashlib.sha1(old).hexdigest(), control=control,
             diff=[0, len(diff)], extra=[len(diff), len(extra)])
    return dict(file='BOOT', size=len(new), sha1=hashlib.sha1(new).hexdigest(), bases={'us': d}), diff + extra


class BinaryDeltaTests(unittest.TestCase):
    def test_assembler_checks_regional_alias_pins_after_copy_propagation(self):
        usa, own = b'USA!', b'own!'
        h = lambda data: hashlib.sha1(data).hexdigest()
        e = dict(file='first', size=4, sha1=h(usa), sha1_by_base={'eu': h(own)}, bases={})
        for key, data in [('us', usa), ('eu', own)]:
            e['bases'][key] = dict(source='BOOT', source_sha1=h(data), control=[[4, 0, 0]],
                                  diff=[0, 4], extra=[4, 0])
        p = dict(files={'first': [['b', 0, 0, 4]], 'alias': [['o', 'first', 0, 4]]},
                 sources=[], deltas=[e], code=[], blob=bytes(4), layout='', license=[],
                 sha1={'first': h(usa), 'alias': h(usa)}, sha1_by_base={'eu': {'first': h(own)}})
        codecopy.propagate_regional_copies(p, {'first': usa, 'alias': usa}, {'eu': {'first': own}})
        writer = types.SimpleNamespace(Layout=lambda x: x, write=lambda lay, got, out, **kw: (dict(got), None))
        base = types.SimpleNamespace(key='eu', code=lambda _: own)
        with patch.object(dw, '_iw', return_value=writer):
            _, files = dw.build_disc3(p, base, {}, 'unused', progress=False)
            self.assertEqual(files, {'first': own, 'alias': own})
            p['sha1_by_base']['eu']['alias'] = h(usa)
            with self.assertRaisesRegex(dw.PatchError, 'alias'):
                dw.build_disc3(p, base, {}, 'unused', progress=False)

    def test_regional_hashes_follow_copied_output_slices_and_alias_chains(self):
        payload = dict(files={'first': [['b', 0, 0, 4]], 'second': [['o', 'first', 0, 4]],
                              'third': [['l', 0, 1], ['o', 'second', 1, 2]]}, code=[])
        outputs = {'first': b'USA!', 'second': b'USA!', 'third': b'xSA'}
        changed = {'eu': {'first': b'own!'}}
        self.assertEqual(codecopy.propagate_regional_copies(payload, outputs, changed),
                         {'eu': ['second', 'third']})
        self.assertEqual(changed['eu']['third'], b'xwn')
        self.assertEqual(payload['sha1_by_base']['eu']['second'], hashlib.sha1(b'own!').hexdigest())
        self.assertEqual(payload['sha1_by_base']['eu']['third'], hashlib.sha1(b'xwn').hexdigest())

    def test_appended_player_file_is_independently_pinned_and_addressable(self):
        own = {'MAIN': b'main', 'OVERLAY': b'own buffer'}
        d = dict(source='MAIN', source_sha1=hashlib.sha1(own['MAIN']).hexdigest(),
            additional_sources=[dict(file='OVERLAY', size=10, sha1=hashlib.sha1(own['OVERLAY']).hexdigest())],
            control=[[0, 0, 4], [10, 0, 0]], diff=[0, 10], extra=[10, 0])
        e = dict(size=10, sha1=hashlib.sha1(own['OVERLAY']).hexdigest(), bases={'us': d})
        self.assertEqual(dw.apply_binary_delta(e, 'us', own.__getitem__, bytes(10)), own['OVERLAY'])
        own['OVERLAY'] = b'bad buffer'
        with self.assertRaisesRegex(dw.PatchError, 'additional.*source differs'):
            dw.apply_binary_delta(e, 'us', own.__getitem__, bytes(10))

    def test_old_padding_does_not_start_reading_an_appended_player_file(self):
        # The original control copies two bytes then two implicit zeros. After
        # appending an overlay and replacing its buffer, padding must stay zero.
        old, own = b'AB', b'XY'
        control, diff, extra = codecopy.generate_linker_words(
            [[4, 2, 0]], bytes(4), b'??', 4, [], [[4, 2, 2]], original_source_size=2)
        d = dict(source='MAIN', source_sha1=hashlib.sha1(old).hexdigest(),
                 additional_sources=[dict(file='OVERLAY', size=2, sha1=hashlib.sha1(own).hexdigest())],
                 control=control, diff=[0, len(diff)], extra=[len(diff), len(extra)])
        target = b'AB\0\0XY'
        e = dict(size=6, sha1=hashlib.sha1(target).hexdigest(), bases={'us': d})
        self.assertEqual(dw.apply_binary_delta(e, 'us', {'MAIN': old, 'OVERLAY': own}.__getitem__,
                                             diff + extra), target)

    def test_regional_output_uses_its_own_pin_and_rejects_a_wrong_pin(self):
        usa, europe = b'USA buffer', b'own buffer'
        e = dict(file='BOOT', size=len(usa), sha1=hashlib.sha1(usa).hexdigest(),
                 sha1_by_base={'eu': hashlib.sha1(europe).hexdigest()}, bases={})
        for key, data in [('us', usa), ('eu', europe)]:
            e['bases'][key] = dict(source='BOOT', source_sha1=hashlib.sha1(data).hexdigest(),
                                  control=[[len(data), 0, 0]], diff=[0, len(data)], extra=[len(data), 0])
            self.assertEqual(dw.apply_binary_delta(e, key, lambda _: data, bytes(len(data))), data)
        e['sha1_by_base']['eu'] = e['sha1']
        with self.assertRaisesRegex(dw.PatchError, 'output differs'):
            dw.apply_binary_delta(e, 'eu', lambda _: europe, bytes(len(europe)))

    def test_native_and_python_round_trip_edits_moves_empty_and_repetition(self):
        r = random.Random(821)
        old = r.randbytes(8192)
        pairs = [(b'', b''), (b'', b'new story'), (old, b''), (old, old),
                 (old, b'story text' + old[2048:] + old[:2048] + b'end'),
                 (old, bytes((b + (i % 7 == 0)) & 255 for i, b in enumerate(old))),
                 (b'\0' * 4096, b'\0' * 1000 + b'own' + b'\0' * 6000)]
        for native in (True, False):
            for old, new in pairs:
                with self.subTest(native=native, sizes=(len(old), len(new))):
                    e, blob = entry(old, new, native)
                    self.assertEqual(dw.apply_binary_delta(e, 'us', lambda _: old, blob), new)
                    p = dict(deltas=[e], blob=blob)
                    rows = codecopy.extra_runs(p)
                    self.assertEqual(sum(x['length'] for x in rows), e['bases']['us']['extra'][1])
                    self.assertTrue(all(new[x['offset']:x['offset'] + x['length']] ==
                                        blob[x['blob_offset']:x['blob_offset'] + x['length']] for x in rows))

    def test_manifest_sources_compaction_and_future_edits(self):
        class Image:
            def __init__(self, data):
                self.data = data
                self.files = {q: (0, len(b), False) for q, b in data.items()}
            def read(self, q):
                return self.data[q]
        images = {'us': Image({'SLUS_010.32': b'original main' * 50, 'BTL_REL.BIN': b'overlay' * 50}),
                  'eu': Image({'SLES_029.14': b'regional main' * 50, 'BTL_REL.BIN': b'regional overlay' * 50})}
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / 'derived/plan.json'
            plan.parent.mkdir()
            plan.write_text(json.dumps(dict(authored=['SLUS_010.32'], LANG_OVL=['ca:BTL_REL.BIN:LC970.BIN', 'ca:MENU_REL.BIN:LC986.BIN'])))
            for changed in (False, True):
                outputs = {'SLUS_010.32': b'moved function' * 20 + bytes([changed]),
                           'SCN/LC970.BIN': b'edited overlay' * 40,
                           'SCN/LC986.BIN': b'new menu overlay' * 20,
                           'SCN/LANGCA.BIN': b'changed story' if changed else b'original authored story'}
                blob = bytearray(b'dead bytes must not ship')
                files = {}
                for file, data in outputs.items():
                    files[file] = [['l', len(blob), len(data)]]
                    blob.extend(data)
                p = dict(files=files, blob=bytes(blob), sources=[], code=[], license=[])
                report = codecopy.copy_files(p, tmp, outputs, images)
                self.assertEqual(len(report['files']), 3)
                self.assertEqual(p['files']['SCN/LANGCA.BIN'][0][0], 'l')
                self.assertNotIn(b'dead bytes must not ship', p['blob'])
                self.assertEqual(codecopy.extra_runs(p), [])
                for e in p['deltas']:
                    for base, image in images.items():
                        self.assertEqual(dw.apply_binary_delta(e, base, image.read, p['blob']), outputs[e['file']])

    def test_manifest_language_bank_is_a_program_delta_too(self):
        image = types.SimpleNamespace(files={'SLUS_010.32': (0, 1000, False)})
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / 'derived/plan.json'
            plan.parent.mkdir()
            plan.write_text(json.dumps(dict(authored=['SLUS_010.32', 'SCN/LANGEN.BIN'])))
            p = dict(files={'SLUS_010.32': [], 'SCN/LANGEN.BIN': [], 'unrelated': []})
            names = codecopy.source_names(p, tmp, {'us': image})
            self.assertEqual(names['SCN/LANGEN.BIN'], {'us': 'SLUS_010.32'})
            self.assertNotIn('unrelated', names)

    def test_selected_derive_manifest_drives_sources_without_sidecar(self):
        image = types.SimpleNamespace(files={'SLUS_010.32': (0, 1000, False)})
        p = dict(files={'SLUS_010.32': [], 'SCN/NEW-STORY.BIN': []})
        plan = dict(authored=list(p['files']))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'derived'
            folder.mkdir()
            (folder / 'manifest.json').write_text(json.dumps(dict(plan=plan)))
            self.assertEqual(codecopy.source_names(p, tmp, {'us': image})['SCN/NEW-STORY.BIN'],
                             {'us': 'SLUS_010.32'})
            (folder / 'manifest.json').unlink()
            self.assertEqual(codecopy.source_names(p, tmp, {'us': image}, plan=plan)['SCN/NEW-STORY.BIN'],
                             {'us': 'SLUS_010.32'})

    def test_standard_outside_source_and_negative_seek_semantics(self):
        old, new = b'abc', b'bc\0\0a'
        e = dict(size=5, sha1=hashlib.sha1(new).hexdigest(), bases={'us':
                 dict(source='BOOT', source_sha1=hashlib.sha1(old).hexdigest(),
                      control=[[0, 0, 1], [4, 0, -5], [1, 0, 0]], diff=[0, 5], extra=[5, 0])})
        self.assertEqual(dw.apply_binary_delta(e, 'us', lambda _: old, bytes(5)), new)

    def test_invalid_source_controls_and_unused_bytes_fail(self):
        e, blob = entry(b'original', b'new story and original')
        with self.assertRaises(dw.PatchError):
            dw.apply_binary_delta(e, 'eu', lambda _: b'original', blob)
        with self.assertRaises(dw.PatchError):
            dw.apply_binary_delta(e, 'us', lambda _: b'bad source', blob)
        for changes in (dict(control=[[-1, 0, 0]]), dict(control=[[999999, 0, 0]]),
                        dict(diff=[len(blob) + 1, 0]), dict(extra=[-1, 0]),
                        dict(control=[])):
            bad = copy.deepcopy(e); bad['bases']['us'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(dw.PatchError):
                dw.apply_binary_delta(bad, 'us', lambda _: b'original', blob)

    def test_disc_assembler_selects_each_players_own_source(self):
        new = b'new text and code' * 100
        e, blob = entry(b'USA executable' * 100, new)
        e2, blob2 = entry(b'Europe executable' * 100, new)
        d = e2['bases']['us']; d['diff'][0] += len(blob); d['extra'][0] += len(blob)
        e['bases']['eu'] = d
        p = dict(sources=[], blob=blob + blob2, deltas=[e], code=[], layout='', license=[],
                 files={'BOOT': [['b', 0, 0, len(new)]]}, sha1={'BOOT': hashlib.sha1(new).hexdigest()})
        writer = types.SimpleNamespace(Layout=lambda x: x, write=lambda lay, got, out, **kw: (None, dict(got)))
        for key, old in [('us', b'USA executable' * 100), ('eu', b'Europe executable' * 100)]:
            base = types.SimpleNamespace(key=key, code=lambda _: old)
            with patch.object(dw, '_iw', return_value=writer):
                got, _ = dw.build_disc3(p, base, {}, 'unused', progress=False)
            self.assertEqual(got['BOOT'], new)


if __name__ == '__main__':
    unittest.main()
