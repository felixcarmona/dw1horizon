"""Area profiles preserve every native preference and all other map data."""
import copy
from pathlib import Path
import unittest
import dwmap
from map_regions import apply, profiles

ROOT = Path(__file__).resolve().parent.parent


def response(m, region):
    return next((value for a, b in zip(m.regionA, m.regionB)
                 for match, value in [(a, 1), (b, 2)] if match == region), 0)


class MapRegions(unittest.TestCase):
    def test_native_maps_keep_other_regions_and_data(self):
        found = set()
        for path in (ROOT / 'extracted/MAP').rglob('*.MAP'):
            before = dwmap.MapFile(path.read_bytes())
            after = copy.deepcopy(before)
            apply(after, path.stem)
            apply(after, path.stem)  # repeat compilation remains idempotent
            for region in range(9):
                self.assertEqual(response(before, region), response(after, region), (path.stem, region))
            p = profiles()['9']
            expected = 1 if path.stem in p['pleased'] else 2 if path.stem in p['displeased'] else 0
            self.assertEqual(response(after, 9), expected, path.stem)
            if expected:
                found.add(path.stem)
            after.regionA = before.regionA
            after.regionB = before.regionB
            self.assertEqual(after.build(), before.build(), path.stem)
        expected = set(profiles()['9']['pleased'] + profiles()['9']['displeased']) - {'SHOR01', 'LAKE01'}
        self.assertEqual(found, expected)

    def test_full_or_conflicting_lists_fail(self):
        from types import SimpleNamespace
        name = profiles()['9']['pleased'][0]
        for a, b in [([0, 1, 2, 3], [-1]*4), ([-1]*4, [9, -1, -1, -1])]:
            with self.assertRaises(ValueError):
                apply(SimpleNamespace(regionA=a, regionB=b), name)


if __name__ == '__main__':
    unittest.main()
