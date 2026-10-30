#!/usr/bin/env python3
"""The authored secret-shop DWS and Python views must implement the same stock."""
import os
from pathlib import Path
import tempfile
import unittest

from dws import basebuild as BB, build as B
from dws.py import lower as PL
from dws import bytecode as bytecode


@unittest.skipUnless(Path(B.ROOT, 'extracted/SCN/DG.SCN').exists(), 'needs extracted/ (your own disc)')
class SecretShop(unittest.TestCase):
    def test_both_views_have_the_same_sections_and_stock(self):
        with tempfile.TemporaryDirectory(prefix='secret-shop-') as folder:
            previous = PL.LOWERED
            PL.LOWERED = os.path.join(folder, 'lowered')
            try:
                entries = []
                for suffix in ('dws', 'py'):
                    source = Path(BB.script_file(BB.BASE, 177)).with_suffix('.' + suffix)
                    program = B.compile_sources([str(source)])
                    out = os.path.join(folder, suffix, 'DG.SCN')
                    B.assemble(program, out)
                    blob = Path(out).read_bytes()
                    offsets = bytecode.container_entries(blob)
                    entries.append(blob[offsets[177]:offsets[178]])
                equal, bad = BB.compare_entries(*entries, 'secret shop')
                self.assertGreater(equal, 0)
                self.assertEqual(bad, [])
            finally:
                PL.LOWERED = previous


if __name__ == '__main__':
    unittest.main()
