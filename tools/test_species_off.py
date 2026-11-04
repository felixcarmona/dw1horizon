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
        self.assertEqual(len(swaps), sum('off' in s and s['level'] != s['off']['level'] for s in self.sp.values()))

    def test_stats_are_explicit_and_ordered(self):
        with patch.object(S, 'originals', side_effect=AssertionError('disc read')):
            rows = S.stats_swaps(self.sp)
        self.assertGreaterEqual(len(rows), 6)
        for row in rows:
            if row[0] in (59, 60, 65, 115, 116, 117):
                self.assertEqual(row[1:7], row[7:13])

    def test_whamon_off_is_original_champion(self):
        s = self.sp[24]
        self.assertEqual(s['level'], 'ultimate')
        self.assertEqual(s['off']['level'], 'champion')
        self.assertEqual(list(s['off']['stats'].values()), [2500, 1500, 100, 150, 100, 200])
        for t in (4, 46, 57):
            self.assertIn(24, self.sp[t]['off']['evolution']['to'])
            self.assertNotIn(24, self.sp[t]['evolution']['to'])

    def test_evolution_rows_have_fixed_layout(self):
        import struct
        paths = {t: s['evolution'] for t, s in self.sp.items() if 'evolution' in s}
        with patch.object(S, 'originals', side_effect=AssertionError('disc read')):
            rows = S.evolution_swaps(self.sp, paths)
        self.assertLessEqual(len(rows), S.EVOLUTION_SWAP_MAX)
        for row in rows:
            self.assertEqual(len(row), 102)
        whamon = next(row for row in rows if struct.unpack_from('<H', row)[0] == 24)
        self.assertEqual(struct.unpack_from('<6h', whamon, 34), (61, 13, 119, 112, -1, -1))
        self.assertEqual(struct.unpack_from('<h', whamon, 76)[0], 100)  # off HP requirement

    def test_missing_override_is_rejected(self):
        s = copy.deepcopy(self.sp[59])
        del s['off']
        with patch.object(S, 'originals', side_effect=AssertionError('disc read')):
            with self.assertRaisesRegex(SystemExit, 'off: required'):
                S.validate(s)

    def test_original_none_still_requires_explicit_off(self):
        s = copy.deepcopy(self.sp[62])
        del s['off']
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
