"""Explicit NEW DIGIMON off data must work without disc readers."""
import copy
import unittest
from unittest.mock import patch
import species as S


class OffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sp = S.load_content()

    def test_swaps_do_not_read_disc(self):
        with patch.object(S, 'originals', side_effect=AssertionError('disc read')):
            swaps = S.level_swaps(self.sp)
        self.assertIn((59, 6, 5), swaps)
        self.assertEqual(len(swaps), sum('off' in s for s in self.sp.values()))

    def test_missing_override_is_rejected(self):
        s = copy.deepcopy(self.sp[59])
        del s['off']
        with patch.object(S, 'originals', side_effect=AssertionError('disc read')):
            with self.assertRaisesRegex(SystemExit, 'off: required'):
                S.validate(s)

    def test_no_implicit_override(self):
        self.assertEqual(S.level_swaps({1: {'level': 'mega'}}), [])

    def test_incomplete_stats_are_rejected(self):
        s = copy.deepcopy(self.sp[59])
        s['off']['stats'] = {'hp': 1000}
        with self.assertRaisesRegex(SystemExit, 'off.stats'):
            S.validate(s)


if __name__ == '__main__':
    unittest.main()
