"""Characterize story copy policy before relocating it into DWS."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.dws import variants as V


class StoryVariants(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.disc = self.root / 'extracted'
        (self.disc / 'MAP/ZONE').mkdir(parents=True)
        self.out = self.root / 'copies'
        self.enterContext(patch.object(V, 'EXTRACTED', str(self.disc)))

    def file(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def test_last_override_sorted_copies_and_new_file_exclusion(self):
        self.file('extracted/MAP/ZONE/ALPHA.MAP', b'original map')
        self.file('extracted/MAP/ZONE/BRAVO.TFS', b'original textures')
        old = self.file('old', b'old override')
        final = self.file('final', b'final override')
        ext = V.pairs(['MAP/ZONE/BRAVO.TFS=' + old, 'MAP/ZONE/ALPHA.MAP=' + old,
                       'MAP/ZONE/ALPHA.MAP=' + final, 'MAP/NEW/CHARLIE.MAP=' + final])
        rows = V.plan(str(self.out), ext, {})
        self.assertEqual([(r[0], r[1]) for r in rows],
                         [('MAP/ZONE/ALPHA.MAP', '_LPHA.MAP'), ('MAP/ZONE/BRAVO.TFS', '_RAVO.TFS')])
        self.assertEqual(rows[0][2], final)
        self.assertEqual((self.out / '_LPHA.MAP').read_bytes(), b'original map')
        self.assertEqual(V.plan_lines(str(self.out), rows)[0],
                         '--add\tMAP/ZONE/_LPHA.MAP=' + str(self.out / '_LPHA.MAP'))
        replacement = self.file('balanced', b'balanced base')
        self.assertEqual(V.finish(str(self.out), rows, {'MAP/ZONE/ALPHA.MAP': replacement}), 1)
        self.assertEqual((self.out / '_LPHA.MAP').read_bytes(), b'balanced base')
        self.assertEqual(V.finish(str(self.out), rows, {'MAP/ZONE/ALPHA.MAP': replacement}), 0)

    def test_equal_bytes_and_non_maps_have_no_copies(self):
        original = self.file('extracted/MAP/ZONE/ALPHA.MAP', b'same')
        other = self.file('other', b'same')
        self.assertEqual(V.plan(str(self.out), {'MAP/ZONE/ALPHA.MAP': other, 'DG.SCN': original}, {}), [])

    def test_collision_checks_all_disc_folders(self):
        self.file('extracted/MAP/ZONE/ALPHA.MAP', b'original')
        self.file('extracted/OTHER/_LPHA.MAP', b'occupied')
        different = self.file('different', b'changed')
        with self.assertRaisesRegex(SystemExit, 'taken'):
            V.plan(str(self.out), {'MAP/ZONE/ALPHA.MAP': different}, {})

    def test_two_copies_cannot_share_a_basename(self):
        for name in ['ALPHA.MAP', 'BLPHA.MAP']:
            self.file('extracted/MAP/ZONE/' + name, b'original')
        changed = self.file('changed', b'changed')
        with self.assertRaisesRegex(SystemExit, 'taken'):
            V.plan(str(self.out), {f'MAP/ZONE/{n}': changed for n in ['ALPHA.MAP', 'BLPHA.MAP']}, {})


if __name__ == '__main__':
    unittest.main()
