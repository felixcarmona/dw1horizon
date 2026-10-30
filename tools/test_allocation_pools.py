"""Pin the allocator's saved identities and capacities before consolidating constants."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.dws import alloc


class AllocationPools(unittest.TestCase):
    def test_original_saved_and_temporary_numbers(self):
        a = alloc.Allocator()
        self.assertEqual(a.pool('flag', 'save').numbers, list(range(717, 800)))
        self.assertEqual(a.pool('var', 'save').numbers, list(range(7, 16)) + [20])
        self.assertEqual(a.pool('var', 'temp').numbers, list(range(45, 94)))
        self.assertEqual(a.engine_number('flag', 'save', 717), 717)

    def test_extended_save_capacities_and_operand_mapping(self):
        a = alloc.Allocator(profile='tier2')
        self.assertEqual([len(a.pool(*k).numbers) for k in
                          [('flag', 'save'), ('var', 'save'), ('var', 'temp'), ('var', 'scratch')]],
                         [16384, 1024, 256, 49])
        self.assertEqual(a.engine_number('flag', 'save', 16383), 17183)
        self.assertEqual(a.engine_number('var', 'temp', 255), 0x80ff)
        self.assertEqual(a.engine_number('var', 'save', 1023), 1023)

    def test_historical_profile_loads_and_writes_the_existing_lock_format(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'story.lock'
            p.write_text(json.dumps(dict(profile='tier2', flags={'quest': 42}, vars={}, temps={}, sizes={})))
            a = alloc.Allocator(p, profile='tier2xl')
            self.assertEqual(a.lock['flags'], {'quest': 42})
            a.write_lock(p)
            self.assertEqual(json.loads(p.read_text())['profile'], 'tier2')

    def test_descriptive_profiles_preserve_legacy_locks_and_shared_pools(self):
        from tools.dws import backend
        self.assertIs(backend.FREE_TRIGGERS, alloc.FREE_TRIGGERS)
        self.assertIs(backend.FREE_SAVED_PSTATS, alloc.FREE_SAVED_PSTATS)
        self.assertIs(backend.FREE_TEMP_PSTATS, alloc.FREE_TEMP_PSTATS)
        for current, legacy in [('original', 'tier0'), ('extended-save', 'tier2')]:
            with self.subTest(profile=current):
                a = alloc.Allocator(profile=current)
                b = alloc.Allocator(profile=legacy)
                self.assertIs(a.pools, b.pools)
                self.assertEqual(a.lock, b.lock)
                self.assertEqual(a.lock['profile'], legacy)
                self.assertEqual(a.profile, current)

    def test_frontend_selects_shared_canonical_pools(self):
        from tools.dws.targets import profile_pool
        for name in alloc.LOCK_PROFILES:
            self.assertEqual(profile_pool(name), name)
            self.assertIs(alloc.Allocator(profile=profile_pool(name)).pools, alloc.PROFILES[name])
        for legacy in alloc.PROFILE_ALIASES:
            with self.assertRaises(ValueError):
                profile_pool(legacy)

    def test_incompatible_serialized_profiles_still_fail(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'story.lock'
            for requested in ('tier0', 'tier2', 'tier2xl'):
                stored_profile = 'tier0' if requested == 'tier0' else 'tier2'
                for stored in ('tier0', 'tier2', 'tier2xl', 'unknown'):
                    with self.subTest(requested=requested, stored=stored):
                        p.write_text(json.dumps({'profile': stored}))
                        if stored == stored_profile:
                            alloc.Allocator(p, profile=requested)
                        else:
                            with self.assertRaises(alloc.DwsError):
                                alloc.Allocator(p, profile=requested)


if __name__ == '__main__':
    unittest.main()
