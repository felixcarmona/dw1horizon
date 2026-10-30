"""Exercise object reuse with a real host compiler and independent clean objects."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(shutil.which('cc'), 'needs a host C compiler')
class CompilerCacheTests(unittest.TestCase):
    def test_headers_same_mtime_corruption_and_clean_equality(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, header = root / 'test.c', root / 'test.h'
            source.write_text('#include "test.h"\nint value(void) { return VALUE; }\n')
            header.write_text('#define VALUE 1\n')
            obj, dep = root / 'test.o', root / 'test.d'
            cache = root / 'cache'
            env = dict(os.environ, DW_COMPILER_IMAGE='host-test', DW_COMPILER_CACHE=str(cache), DW_COMPILER_NAMESPACE='test-headers')
            wrapper = Path(__file__).with_name('compiler_cache.py')
            args = ['-c', '-g', '-MMD', '-MP', '-MF', str(dep), '-MT', str(obj), '-o', str(obj), str(source)]
            def call():
                subprocess.run([sys.executable, str(wrapper), 'cc', *args], env=env, check=True)
                return obj.read_bytes(), dep.read_bytes()
            first = call()
            obj.unlink(); dep.unlink()
            self.assertEqual(call(), first)
            stamp = header.stat()
            header.write_text('#define VALUE 2\n')
            os.utime(header, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            second = call()
            self.assertNotEqual(first[0], second[0])
            subprocess.run(['cc', *args], check=True)
            self.assertEqual((obj.read_bytes(), dep.read_bytes()), second)
            for blob in cache.rglob('object'):
                blob.write_bytes(b'corrupt object')
            self.assertEqual(call(), second)
            for blob in cache.rglob('deps'):
                blob.unlink()
            self.assertEqual(call(), second)

    def test_new_header_cannot_shadow_recorded_include(self):
        from tools.native_build import source_hashes
        from tools.build_cache import key
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src').mkdir()
            early, late = root / 'include/early', root / 'include/late'
            early.mkdir(parents=True); late.mkdir()
            (late / 'value.h').write_text('#define VALUE 1\n')
            source = root / 'src/test.c'
            source.write_text('#include <value.h>\nint value(void) { return VALUE; }\n')
            obj, dep = root / 'test.o', root / 'test.d'
            cache = root.parent / (root.name + '-objects')
            self.addCleanup(shutil.rmtree, cache, True)
            wrapper = Path(__file__).with_name('compiler_cache.py')
            args = ['-c', '-I'+str(early), '-I'+str(late), '-MMD', '-MP', '-MF', str(dep),
                    '-MT', str(obj), '-o', str(obj), str(source)]
            def call():
                namespace = key([p for p, _ in source_hashes(root)])
                env = dict(os.environ, DW_COMPILER_IMAGE='host-test', DW_COMPILER_CACHE=str(cache),
                           DW_COMPILER_NAMESPACE=namespace)
                subprocess.run([sys.executable, str(wrapper), 'cc', *args], env=env, check=True)
                return obj.read_bytes()
            first = call()
            # Keep outputs outside the source namespace, as in the real tree.
            obj.unlink(); dep.unlink()
            self.assertEqual(call(), first)
            (early / 'value.h').write_text('#define VALUE 2\n')
            obj.unlink(); dep.unlink()
            second = call()
            self.assertNotEqual(second, first)
            subprocess.run(['cc', *args], check=True)
            self.assertEqual(obj.read_bytes(), second)


if __name__ == '__main__':
    unittest.main()
