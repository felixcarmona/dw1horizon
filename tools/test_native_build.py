"""Verified object sharing must tolerate misleading/future object timestamps."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import native_build
from tools.dev import build as dev_build


@unittest.skipUnless(shutil.which('make') and shutil.which('cc'), 'needs make and host cc')
class NativeTests(unittest.TestCase):
    def test_future_object_cannot_hide_language_header_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            (tree / 'src').mkdir()
            (tree / 'src/main.c').write_text('#include "lang_build.h"\nint main(void) { return LANGUAGE; }\n')
            (tree / 'text-bank.json').write_text('{}')
            # Real make/cc exercise the same generated-header dependency pattern.
            (tree / 'Makefile').write_text('''CC=cc
GEN=build/us/psx/generated
OUT=build/us/psx/gcc
$(shell mkdir -p $(GEN); printf '#define LANGUAGE %s\\n' '$(LANG_BUILD)' > $(GEN)/lang_build.h.tmp; cmp -s $(GEN)/lang_build.h.tmp $(GEN)/lang_build.h && rm $(GEN)/lang_build.h.tmp || mv $(GEN)/lang_build.h.tmp $(GEN)/lang_build.h)
all: $(OUT)/program
$(OUT)/main.o: src/main.c $(GEN)/lang_build.h
\t@mkdir -p $(OUT)
\t$(CC) -I$(GEN) -c $< -o $@
$(OUT)/program: $(OUT)/main.o
\t$(CC) $< -o $@
''')
            real_run = subprocess.run
            def host_make(cmd, **kwargs):
                return real_run(['make', '-j2', *[x for x in cmd if x.startswith('LANG_BUILD=')]], cwd=tree, **kwargs)
            with patch.object(native_build.subprocess, 'run', host_make):
                native_build.compile(tree, tree / 'first.log', ['LANG_BUILD=1'], image='host')
                # Logs are not compiler inputs in this fixture (real driver keeps
                # them outside the tree).
                (tree / 'first.log').unlink()
                for p in (tree / 'build').rglob('*'):
                    if p.is_file():
                        future = 2_000_000_000_000_000_000
                        os.utime(p, ns=(future, future))
                log = tree.parent / (tree.name + '.log')
                try:
                    native_build.compile(tree, log, ['LANG_BUILD=2'], image='host')
                    result = real_run([tree / 'build/us/psx/gcc/program'])
                    self.assertEqual(result.returncode, 2)
                finally:
                    log.unlink(missing_ok=True)



class GeneratedFontRefreshTests(unittest.TestCase):
    def test_generated_headers_refresh_but_manual_edits_survive(self):
        from tools import fontgen
        for manual in (False, True):
            with self.subTest(manual=manual), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                tree = root / 'build/decomp-dev'
                (tree / 'src/main').mkdir(parents=True)
                (root / 'extracted').mkdir()
                (root / 'extracted/SLUS_010.32').write_bytes(b'disc fixture')
                extra = tree / 'src/main/font_extra.h'
                font_b = tree / 'src/main/font_b.h'
                extra.write_bytes(b'generated extra' + (b' manual edit' if manual else b''))
                font_b.write_bytes(b'generated b')
                def generate_extra(path):
                    Path(path).write_bytes(b'generated extra')
                def generate_b(font, path):
                    self.assertEqual(font, 'b')
                    Path(path).write_bytes(b'generated b')
                with patch.object(dev_build, 'ROOT', root), \
                     patch.object(dev_build, 'git', return_value='src/main/font_extra.h\nsrc/main/font_b.h') as git, \
                     patch.object(fontgen, 'header', generate_extra), \
                     patch.object(fontgen, 'font_header', generate_b):
                    dev_build.restore_generated_fonts(tree)
                expected = ['src/main/font_b.h'] + ([] if manual else ['src/main/font_extra.h'])
                git.assert_any_call('checkout', '--', *expected, cwd=tree)
                self.assertEqual(extra.read_bytes(), b'generated extra' + (b' manual edit' if manual else b''))


if __name__ == '__main__':
    unittest.main()
