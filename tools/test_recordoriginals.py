"""Record-original player path: source/patch/target pins and ALLTIM slicing."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.models import delta as modeldelta
from tools import recordoriginals as R


class RecordOriginalsTest(unittest.TestCase):
    def test_checked_slice_and_all_pins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = b'player disc texture entry' * 20
            target = source[:70] + b'our changed palette' + source[90:]
            delta = modeldelta.encode(target, [source])
            (root / 'ALLTIM').write_bytes(b'prefix' + source + b'suffix')
            (root / 'patch').write_bytes(delta)
            record = dict(sources=[dict(path='ALLTIM', offset=6, size=len(source), sha256=R.digest(source))],
                          delta='patch', delta_sha256=R.digest(delta), size=len(target), sha256=R.digest(target))
            self.assertEqual(R.decode(record, root), target)
            for field in ('delta_sha256', 'sha256', 'size'):
                bad = copy.deepcopy(record)
                bad[field] = 0 if field == 'size' else '0' * 64
                with self.assertRaises(ValueError): R.decode(bad, root)
            (root / 'ALLTIM').write_bytes(b'prefix' + b'x' * len(source))
            with self.assertRaises(ValueError): R.decode(record, root)

    def test_only_selected_originals_need_sources(self):
        from types import SimpleNamespace
        from tools.derive.steps import record_originals as step
        self.assertEqual(step.ids(SimpleNamespace(env={'IMPORTS': '0'})), set())
        self.assertEqual(step.ids(SimpleNamespace(env={'SPECIES_PROVIDER': 'imports'})), set())
        self.assertEqual(step.ids(SimpleNamespace(env={'SPECIES': '67'})), {67})
        self.assertEqual(len(step.ids(SimpleNamespace(env={'SPECIES': 'all'}))), 33)

    def test_manifest_is_plain_and_matches_provider_pins(self):
        pins = json.loads((R.ROOT / 'tools/derive/recipes/species-pins.json').read_text())['record_originals']
        for row in R.records():
            for kind, index in (('mmd', 0), ('tim', 1)):
                if kind not in row:
                    self.assertIsNone(pins[str(row['id'])][index])
                    continue
                record = row[kind]
                patch = (R.ROOT / record['delta']).read_bytes()
                self.assertEqual(patch[:5], b'MD3\0\0')
                self.assertEqual(R.digest(patch), record['delta_sha256'])
                # With a player's extraction available, verify the actual output too.
                if not any(s.get('producer') == 'import' for s in record['sources']) and all(
                        (R.ROOT / s['path']).is_file() for s in record['sources']):
                    self.assertEqual(hashlib.sha1(R.decode(record)).hexdigest(), pins[str(row['id'])][index])


if __name__ == '__main__':
    unittest.main()
