"""Import identity regressions; no disc or generated game files required."""
import os
from pathlib import Path
import tempfile
import unittest

from tools.dws.backend import Backend
from tools.dws.gen import Program


class Imports(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.getcwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.names = self.root / 'names.dws'
        self.names.write_text('pub alias flag cheap_ordered = 178;\n', encoding='utf-8')
        self.program = Program(Backend(), None)

    def load_alias(self, alias):
        # A top-level prelude and an import from lowered code must share identity.
        self.program.load(str(self.names))
        importer = self.root / 'importer.dws'
        importer.write_text('import "' + str(alias).replace(os.sep, '/') + '";\r\n', encoding='utf-8')
        self.program.load(str(importer))
        self.assertEqual([e.render() for e in self.program.errors], [])
        self.assertEqual(len(self.program.syms), 1)

    def test_relative_import_and_crlf(self):
        self.load_alias('./names.dws')

    @unittest.skipUnless(os.name == 'nt', 'Windows path identity')
    def test_drive_letter_case(self):
        path = str(self.names.resolve())
        self.load_alias(path[0].swapcase() + path[1:])

    @unittest.skipUnless(os.name == 'nt', 'Windows path identity')
    def test_directory_and_filename_case(self):
        self.load_alias(str(self.names.resolve()).swapcase())

    def test_distinct_files_still_reject_duplicate_declarations(self):
        other = self.root / 'other.dws'
        other.write_bytes(self.names.read_bytes())
        self.program.load(str(self.names))
        self.program.load(str(other))
        self.assertEqual(len(self.program.errors), 1)
        self.assertIn('already declared', self.program.errors[0].render())

    @unittest.skipIf(os.name == 'nt', 'case-sensitive filesystem')
    def test_case_distinct_files_remain_distinct(self):
        other = self.root / 'NAMES.dws'
        other.write_text('pub alias flag another = 179;\n', encoding='utf-8')
        if os.path.samefile(self.names, other):
            self.skipTest('case-insensitive filesystem')
        self.program.load(str(self.names))
        self.program.load(str(other))
        self.assertEqual(self.program.errors, [])
        self.assertEqual(len(self.program.syms), 2)


if __name__ == '__main__':
    unittest.main()
