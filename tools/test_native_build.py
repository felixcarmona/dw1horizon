"""Verified object sharing must tolerate misleading/future object timestamps."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import native_build


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


if __name__ == '__main__':
    unittest.main()
