"""Cache correctness: independent inputs, mutable preimages and corrupt artifacts."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.build_cache import Cache, key


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'build'
        self.out.mkdir()
        self.cache = Cache(self.root / 'cache', self.out)
        self.input = self.root / 'source'
        self.input.write_text('one')
        self.output = self.out / 'result'
        self.calls = 0

    def call(self, identity=None):
        def build():
            self.calls += 1
            self.output.write_text(self.input.read_text().upper())
            return 'built'
        return self.cache.call(identity or {'step': 'test'}, build)

    def test_contents_not_timestamps_and_restore_not_hardlink(self):
        self.assertFalse(self.call()[1])
        self.output.write_text('damaged working output')
        self.assertTrue(self.call()[1])
        self.assertEqual(self.output.read_text(), 'ONE')
        stamp = self.input.stat()
        self.input.write_text('two')
        os.utime(self.input, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertFalse(self.call()[1])
        self.assertEqual(self.output.read_text(), 'TWO')
        self.assertEqual(self.calls, 2)

    def test_corrupt_or_missing_blob_rebuilds(self):
        self.call()
        ids = json.loads((self.cache.root / 'index' / key({'step': 'test'})).read_text())
        meta = json.loads(self.cache.blob(ids[0]).read_text())
        blob = self.cache.blob(meta['outputs'][0][1])
        blob.write_text('corrupt')
        self.assertFalse(self.call()[1])
        blob.unlink()
        self.assertFalse(self.call()[1])
        self.assertTrue(self.call()[1])

    def test_cache_blob_replaced_by_directory_does_not_break_build(self):
        self.call()
        ids = json.loads((self.cache.root / 'index' / key({'step': 'test'})).read_text())
        meta = json.loads(self.cache.blob(ids[0]).read_text())
        blob = self.cache.blob(meta['outputs'][0][1])
        blob.unlink()
        blob.mkdir()
        self.assertFalse(self.call()[1])
        self.assertEqual(self.output.read_text(), 'ONE')

    def test_bad_index_and_metadata_rebuild(self):
        self.call()
        index = self.cache.root / 'index' / key({'step': 'test'})
        index.write_text('{broken')
        self.assertFalse(self.call()[1])
        ids = json.loads(index.read_text())
        self.cache.blob(ids[0]).write_text('{}')
        self.assertFalse(self.call()[1])

    def test_added_glob_match_and_missing_optional_file(self):
        sources = self.root / 'sources'
        sources.mkdir()
        def build():
            text = ''.join(p.read_text() for p in sorted(sources.glob('*.txt')))
            optional = self.root / 'optional'
            if optional.exists():
                text += optional.read_text()
            self.output.write_text(text)
            return 'done'
        self.assertFalse(self.cache.call({}, build)[1])
        self.assertTrue(self.cache.call({}, build)[1])
        (sources / 'new.txt').write_text('new')
        self.assertFalse(self.cache.call({}, build)[1])
        (self.root / 'optional').write_text('optional')
        self.assertFalse(self.cache.call({}, build)[1])
        self.assertEqual(self.output.read_text(), 'newoptional')

    def test_in_place_input_uses_preimage(self):
        self.output.write_text('before')
        def build():
            self.output.write_text(self.output.read_text() + '!')
            return 'done'
        self.assertFalse(self.cache.call({}, build)[1])
        self.output.write_text('before')
        self.assertTrue(self.cache.call({}, build)[1])
        self.assertEqual(self.output.read_text(), 'before!')
        self.assertFalse(self.cache.call({}, build)[1])
        self.assertEqual(self.output.read_text(), 'before!!')

    def test_intermediate_not_an_input_and_deletion_restored(self):
        def build():
            intermediate = self.out / 'scratch'
            intermediate.write_text('temporary')
            self.output.write_text(intermediate.read_text())
            intermediate.unlink()
            return 'done'
        self.assertFalse(self.cache.call({}, build)[1])
        self.output.unlink()
        self.assertTrue(self.cache.call({}, build)[1])
        self.assertEqual(self.output.read_text(), 'temporary')

    def test_size_only_input_is_content_verified(self):
        def build():
            self.output.write_text(str(os.path.getsize(self.input)))
            return 'done'
        self.assertFalse(self.cache.call({}, build)[1])
        self.assertTrue(self.cache.call({}, build)[1])
        self.input.write_text('longer')
        self.assertFalse(self.cache.call({}, build)[1])
        self.assertEqual(self.output.read_text(), '6')

    def test_directory_rename_and_empty_output_directory(self):
        import shutil
        def build():
            source = self.out / 'scratch'
            source.mkdir()
            (source / 'file').write_text(self.input.read_text())
            source.rename(self.out / 'result-dir')
            (self.out / 'empty').mkdir()
            return 'done'
        self.assertFalse(self.cache.call({}, build)[1])
        shutil.rmtree(self.out / 'result-dir')
        (self.out / 'empty').rmdir()
        self.assertTrue(self.cache.call({}, build)[1])
        self.assertEqual((self.out / 'result-dir/file').read_text(), 'one')
        self.assertTrue((self.out / 'empty').is_dir())
        self.assertFalse((self.out / 'scratch').exists())

    def test_descriptor_update_preserves_input_tail(self):
        self.output.write_bytes(b'abc')
        def build():
            fd = os.open(self.output, os.O_WRONLY)
            try:
                os.write(fd, b'X')
            finally:
                os.close(fd)
            return 'done'
        self.assertFalse(self.cache.call({}, build)[1])
        self.output.write_bytes(b'abc')
        self.assertTrue(self.cache.call({}, build)[1])
        self.assertEqual(self.output.read_bytes(), b'Xbc')
        self.output.write_bytes(b'def')
        self.assertFalse(self.cache.call({}, build)[1])
        self.assertEqual(self.output.read_bytes(), b'Xef')

    def test_ensuring_existing_directory_still_records_its_input_names(self):
        inputs = self.out / 'inputs'
        inputs.mkdir()
        def build():
            inputs.mkdir(exist_ok=True)
            self.output.write_text(','.join(sorted(os.listdir(inputs))))
            return 'done'
        self.assertFalse(self.cache.call({}, build)[1])
        self.assertTrue(self.cache.call({}, build)[1])
        (inputs / 'added').write_text('input')
        self.assertFalse(self.cache.call({}, build)[1])
        self.assertEqual(self.output.read_text(), 'added')

    def test_failed_call_never_published(self):
        def fail():
            self.output.write_text('partial')
            raise RuntimeError('failed')
        with self.assertRaises(RuntimeError):
            self.cache.call({}, fail)
        self.assertIsNone(self.cache.restore({}))

    def test_recipe_or_tool_change_misses(self):
        self.call({'tool': 'v1', 'env': {'LANG': 'en'}})
        self.assertTrue(self.call({'tool': 'v1', 'env': {'LANG': 'en'}})[1])
        self.assertFalse(self.call({'tool': 'v2', 'env': {'LANG': 'en'}})[1])
        self.assertFalse(self.call({'tool': 'v2', 'env': {'LANG': 'es'}})[1])

    def test_writes_outside_build_are_not_cached(self):
        def build():
            (self.root / 'save.lock').write_text('new name')
            return 'done'
        self.assertFalse(self.cache.call({}, build)[1])
        self.assertFalse(self.cache.call({}, build)[1])


if __name__ == '__main__':
    unittest.main()
