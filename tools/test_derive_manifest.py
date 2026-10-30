"""The manifest must keep disc-file hashes and intermediate outputs across metadata changes."""
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from tools.derive import manifest


class Manifest(unittest.TestCase):
    def test_step_replacement_keeps_other_producers_and_records_intermediates(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / 'model').write_bytes(b'model bytes')
            (out / 'intermediate').write_bytes(b'intermediate bytes')
            m = manifest.load(td)
            m['files'] = {'OLD.MMD': {'step': 'imports'}, 'OTHER.MMD': {'step': 'models'}}
            step = SimpleNamespace(NAME='imports', DESCRIPTION='Imported models')
            manifest.record(m, td, step, [('model', 'NEW.MMD'), ('intermediate', None)], 1.23456,
                            inputs=['source.MMD'])
            manifest.save(m, td)
            got = manifest.load(td)
            self.assertEqual(set(got['files']), {'NEW.MMD', 'OTHER.MMD'})
            self.assertEqual(got['files']['NEW.MMD'], dict(sha1=hashlib.sha1(b'model bytes').hexdigest(),
                             size=11, step='imports', file='model', origin='derived'))
            self.assertEqual(got['steps']['imports']['outputs'], ['model', 'intermediate'])
            self.assertEqual(got['steps']['imports']['inputs'], ['source.MMD'])
            self.assertEqual(got['steps']['imports']['seconds'], 1.23)


if __name__ == '__main__':
    unittest.main()
