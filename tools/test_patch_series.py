#!/usr/bin/env python3
"""tools/patch_series.py: the series order, and what a union merge of series and index.md can leave wrong."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import patch_series as S

HEAD = '| patch | was | what it does | main executable cost (`main_BSS_END`) |\n|---|---|---|---|\n'


class SeriesTest(unittest.TestCase):
    def tree(self, series, files, rows):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name) / S.DIR
        d.mkdir(parents=True)
        for f in files:
            (d / f).write_text('')
        (d / 'series').write_text(series)
        (d / 'index.md').write_text('# table\n\n' + HEAD + ''.join(f'| `{r}` |  | x | |\n' for r in rows))
        return tmp.name

    def test_order_is_the_series_not_the_names(self):
        root = self.tree('b.patch\na.patch\n', ['a.patch', 'b.patch'], ['b.patch', 'a.patch'])
        self.assertEqual(S.problems(root), [])
        self.assertEqual([p.name for p in S.paths(root)], ['b.patch', 'a.patch'])

    def test_core_stops_at_the_first_merge_patch(self):
        names = ['a.patch', 'Merge-branch-x.patch', 'c.patch']
        root = self.tree(''.join(n + '\n' for n in names), names, names)
        self.assertEqual([p.name for p in S.paths(root, core=True)], ['a.patch'])

    def test_union_merge_leftovers(self):
        root = self.tree('a.patch\nb.patch\na.patch\nc.patch', ['a.patch', 'b.patch', 'd.patch'],
                         ['a.patch', 'b.patch', 'b.patch'])
        errs = '\n'.join(S.problems(root))
        for want in ('no newline', 'a.patch is listed twice', 'c.patch does not exist', 'd.patch: not in',
                     '2 rows for b.patch', 'no row for c.patch'):
            self.assertIn(want, errs)

    def test_rows_out_of_order(self):
        root = self.tree('a.patch\nb.patch\n', ['a.patch', 'b.patch'], ['b.patch', 'a.patch'])
        self.assertEqual(len(S.problems(root)), 1)
        self.assertIn('not in the order', S.problems(root)[0])

    def test_checkout_agrees(self):
        self.assertEqual(S.problems(), [])


if __name__ == '__main__':
    unittest.main()
