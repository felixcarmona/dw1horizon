#!/usr/bin/env python3
"""Publication failures must be fresh, reviewable, and impossible to waive."""
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import literal_gate as gate


class GateInventoryTests(unittest.TestCase):
    def test_legacy_builder_cannot_bypass_publication_gate(self):
        with self.assertRaisesRegex(gate.audit.dw.PatchError, 'everything releases require format 3'):
            gate.audit.dw.cmd_make_release(types.SimpleNamespace(format=2))

    def test_split_literals_and_new_copy_operations(self):
        payload = dict(files={'EXE': [['f', 0, 0, 40], ['l', 0, 8], ['l', 8, 8],
                                      ['h', 0, 0, 2], ['l', 16, 3]]},
                       code=[], blob=bytes(range(19)), license=[])
        chunks = gate.payload_chunks(payload, 'changed')
        self.assertEqual([(c['offset'], len(c['data'])) for c in chunks], [(40, 16), (58, 3)])

    def test_regional_binary_delta_extras_cannot_hide_literals(self):
        data = bytes(range(32))
        payload = dict(files={'EXE': [['b', 0, 0, 40]]}, code=[], license=[], blob=data,
                       deltas=[{'size': 32, 'bases': {'us': {'control': [[16, 16, 0]], 'diff': [0, 16], 'extra': [16, 16]}}}])
        rows = [dict(file='EXE', offset=24, length=8, blob_offset=16, delta=0, base='us'),
                dict(file='EXE', offset=32, length=8, blob_offset=24, delta=0, base='us')]
        module = types.SimpleNamespace(extra_runs=lambda p: rows)
        with patch.dict(sys.modules, codecopy=module):
            chunks = gate.payload_chunks(payload, 'changed')
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['data'], data[16:])
        self.assertEqual(chunks[0]['owner'], 'changed/delta-0/us')
        payload['files']['TAIL'] = [['l', 0, 1]]
        gate.validate_blob(payload)
        payload['blob'] += b'hidden game bytes'
        with self.assertRaisesRegex(gate.GateFailure, 'unreferenced'):
            gate.validate_blob(payload)

    def test_mapping_search_is_recursive_and_joins_adjacent_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'bundle').mkdir()
            (root / 'bundle/new-import.json').write_text(json.dumps(
                {'patches': {'new-model': {'ops': [{'data': '00' * 8}, {'data': '11' * 8},
                                                  {'copy': [0, 2]}, {'data': '22'}]}}}))
            chunks = gate.mapping_chunks(root)
            self.assertEqual([len(c['data']) for c in chunks], [16, 1])
            self.assertEqual(chunks[0]['file'], '/patches/new-model/ops')
            self.assertEqual([(c['operation'], c['offset']) for c in chunks], [(0, 0), (3, 18)])
            (root/'bases').mkdir()
            (root/'bases/known.json').write_text(json.dumps({'files': {'UNUSED': {'how': 'needs-usa'}, 'OTHER': {'how': 'differs'}}}))
            self.assertEqual(len(gate.mapping_chunks(root)), 2)

    def test_new_mapping_encoding_requires_explicit_audit_support(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'bases').mkdir()
            (root/'bases/new.json').write_text(json.dumps({'ops': [{'delta': {'extra': 'original-bytes'}}]}))
            with self.assertRaisesRegex(gate.GateFailure, 'new mapping opcode'):
                gate.mapping_chunks(root)
            (root/'bases/new.json').write_text(json.dumps({'files': {'ART': {'how': 'binary-delta', 'extra': 'original'}}}))
            with self.assertRaisesRegex(gate.GateFailure, 'new mapping mode'):
                gate.mapping_chunks(root)
        with self.assertRaisesRegex(gate.GateFailure, 'new payload opcode'):
            gate.validate_blob(dict(files={'EXE': [['new', 0, 0, 4]]}, license=[], blob=b'', code=[]))

    def test_missing_code_query_fails_closed(self):
        with patch.dict(sys.modules, codecopy=types.ModuleType('codecopy')):
            with self.assertRaisesRegex(gate.GateFailure, 'audit_literals is required'):
                gate.check_release(Path('unused'), {}, {}, [], {})

    def test_three_arg_code_api_requires_exact_selected_plan(self):
        def old_probe(payload, build, bases):
            return []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'derived').mkdir()
            plan = {'authored': ['NEW_PROGRAM']}
            (root/'derived/manifest.json').write_text(json.dumps({'plan': plan}))
            self.assertEqual(gate.selected_plan_options(old_probe, {}, root, {}, plan), {})
            with self.assertRaisesRegex(gate.GateFailure, 'selected derive plan'):
                gate.selected_plan_options(old_probe, {}, root, {}, {'authored': ['OTHER']})

    def test_audit_only_package_cannot_receive_a_publication_pass(self):
        module = types.SimpleNamespace(audit_literals=lambda *args: [])
        with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules, codecopy=module):
            with self.assertRaisesRegex(gate.GateFailure, 'complete final manifest'):
                gate.check_release(Path(temp), {'provisional_audit_only': True}, {}, [], {})

    def test_new_imports_cannot_hide_short_unclassified_game_data(self):
        chunks = [dict(owner='bundle/new-import.json', file='/ops', offset=0, data=b'new bytes')]
        rows = gate.complete_mapping_provenance(chunks, [])
        self.assertEqual(rows[0]['category'], 'd')
        with tempfile.TemporaryDirectory() as temp, patch.object(gate, 'scan_chunks', return_value=[]):
            with self.assertRaisesRegex(gate.GateFailure, '9 unresolved mapping'):
                gate.check(chunks, {'sha1': {}}, [], Path(temp)/'gate.json', rows)
        owned = [dict(package_file=chunks[0]['owner'], category='a', length=9)]
        self.assertEqual(gate.complete_mapping_provenance(chunks, owned), [])
        owned[0]['length'] = 8
        with self.assertRaisesRegex(gate.GateFailure, 'coverage mismatch'):
            gate.complete_mapping_provenance(chunks, owned)

    def test_copyable_originals_block_even_without_disc_window_match(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(gate, 'scan_chunks', return_value=[]):
            out = Path(temp) / 'gate.json'
            with self.assertRaisesRegex(gate.GateFailure, '12 copyable original'):
                gate.check([], {'sha1': {}}, [dict(file='EXE', offset=4, length=12)], out)
            report = json.loads(out.read_text())
            self.assertFalse(report['passed'])
            self.assertEqual(report['copyable_original_bytes'], 12)

    def test_outside_source_diff_bytes_are_literals(self):
        payload = dict(blob=bytes(range(24)), deltas=[dict(file='EXE', size=24, bases={
            'us': dict(source='ORIGINAL', diff=[0, 24], extra=[24, 0],
                       control=[[0, 0, -4], [12, 0, 0], [12, 0, 0]])})])
        chunks = gate.outside_source_chunks(payload, 'changed', {'us': {'ORIGINAL': 12}})
        self.assertEqual([(c['offset'], c['data']) for c in chunks], [(0, bytes(range(4))), (16, bytes(range(16, 24)))])
        gate.validate_blob(dict(payload, files={}, code=[], license=[]))
        payload['deltas'][0]['bases']['us']['extra'][1] = 1
        with self.assertRaisesRegex(gate.GateFailure, 'controls'):
            gate.validate_blob(dict(payload, files={}, code=[], license=[]))

    def test_known_short_canonical_mapping_fragments_block_publication(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(gate, 'scan_chunks', return_value=[]):
            out = Path(temp) / 'gate.json'
            with self.assertRaisesRegex(gate.GateFailure, '2 canonical mapping'):
                gate.check([], {'sha1': {}}, [], out,
                           [dict(package_file='base.json', offset=4, length=2, category='c')])
            self.assertEqual(json.loads(out.read_text())['canonical_mapping_bytes'], 2)

    def test_final_package_hook_recomputes_code_eligibility(self):
        payload = dict(files={'EXE': [['l', 0, 12]]}, code=[], license=[], blob=b'new-original')
        calls = []
        def probe(p, build, bases, *, plan=None):
            calls.append((p, build, bases, plan))
            return [dict(file='EXE', offset=0, length=12)]
        module = types.SimpleNamespace(audit_literals=probe)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = dict(format=3, variants={'edited': {'outputs': {'us': {}}, 'holes': []}}, bases={'us': {'sha1': 'input'}})
            (root/'dwpatch.py').write_text('shipped reader')
            (root/'isowriter.py').write_text('shipped writer')
            with patch.dict(sys.modules, codecopy=module), \
                 patch.object(gate.audit.dw, 'read_patch_file', return_value=b'current'), \
                 patch.object(gate.audit.dw, 'read_payload3', return_value=payload), \
                 patch.object(gate, 'source_inventory', return_value={'sha1': {}}), \
                 patch.object(gate, 'scan_chunks', return_value=[]):
                with self.assertRaisesRegex(gate.GateFailure, '12 copyable original'):
                    gate.check_release(root, manifest, {'us': 'player.bin'}, [], {'edited': root/'new-build'},
                                       plans={'edited': {'authored': ['new-program']}})
            self.assertEqual(calls, [(payload, root/'new-build', {'us': 'player.bin'}, {'authored': ['new-program']})])
            self.assertFalse(json.loads((root/'literal-gate.json').read_text())['passed'])
            inputs = json.loads((root/'literal-gate.json').read_text())['inputs']
            self.assertEqual(inputs['patches']['edited'], hashlib.sha1(b'current').hexdigest())
            self.assertIn('manifest_sha1', inputs)
            self.assertEqual(inputs['audit_tools']['bufferdata.py'],
                hashlib.sha1(Path(gate.__file__).with_name('bufferdata.py').read_bytes()).hexdigest())

    def test_scanner_failure_cannot_leave_an_old_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'gate.json'
            out.write_text('{"passed":true}')
            with patch.object(gate, 'scan_chunks', side_effect=RuntimeError('scanner failed')):
                with self.assertRaisesRegex(RuntimeError, 'scanner failed'):
                    gate.check([], {'sha1': {}}, [], out)
            self.assertFalse(out.exists())

    def test_changed_story_is_rescanned_and_old_pass_is_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'gate.json'
            with patch.object(gate, 'scan_chunks', return_value=[]):
                gate.check([], {'sha1': {}}, [], out)
            match = dict(owner='story', file='LANG', offset=0, length=20)
            with patch.object(gate, 'scan_chunks', return_value=[match]):
                with self.assertRaises(gate.GateFailure):
                    gate.check([], {'sha1': {}}, [], out)
            self.assertFalse(json.loads(out.read_text())['passed'])


@unittest.skipUnless(shutil.which('c++'), 'developer gate requires C++17')
class RealScannerTests(unittest.TestCase):
    def test_changed_payload_and_inline_mapping_find_real_disc_bytes(self):
        rng = random.Random(51)
        logical = rng.randbytes(2048)
        raw = bytearray(2352); raw[24:24 + 2048] = logical
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); disc = root / 'player disc.bin'; disc.write_bytes(raw)
            sources = dict(images=[str(disc)], sha1={str(disc): hashlib.sha1(raw).hexdigest()},
                           rows=[[0, '@userdata', 0, 0, 3], [0, '@raw', 0, 0, 2]])
            # The function has moved and its address changed. Exact bytes still
            # present are detected independently of target or source addresses.
            body = logical[100:132]
            chunks = [dict(owner='changed', file='EXE', offset=800, data=body),
                      dict(owner='changed story', file='LANG', offset=0, data=rng.randbytes(32)),
                      dict(owner='bases/new.json', file='/ops', offset=0, data=logical[500:520])]
            out = root / 'gate.json'
            image = types.SimpleNamespace(f=disc.open('rb'))
            with patch.object(gate.audit.iw, 'Image', return_value=image):
                with self.assertRaises(gate.GateFailure):
                    gate.check(chunks, sources, [], out)
            report = json.loads(out.read_text())
            self.assertEqual(report['disc_matching_bytes'], 52)
            self.assertEqual({r['owner'] for r in report['disc_matches']}, {'changed', 'bases/new.json'})
            self.assertNotIn(body.hex(), out.read_text())
            self.assertFalse(any(p.name.startswith('literal-gate-') for p in root.iterdir()))


if __name__ == '__main__':
    unittest.main()
