"""The imported species' unique finishers stay inside the DW1 finisher bands."""
import copy
import unittest

from tools import finisher_balance as F


class FinisherBalance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = F.load_json(F.DATA)
        cls.result = F.check(copy.deepcopy(cls.data))

    def entry(self, data, name):
        return next(e for e in data['finishers'] if e['species_name'] == name)

    def problems_after(self, name, change):
        data = copy.deepcopy(self.data)
        change(self.entry(data, name))
        return [p for p in F.check(data)['problems'] if name in p]

    def test_committed_data_has_no_problem(self):
        self.assertEqual(self.result['problems'], [])

    def test_every_import_has_one_unique_finisher(self):
        species = F.species_table()
        imports = {sid for sid, s in species.items() if sid >= 180 and s.get('level') in F.LEVELS
                   and any(isinstance(t, str) for t in s.get('techniques') or [])}
        covered = [e['species'] for e in self.data['finishers']]
        self.assertEqual(len(covered), len(set(covered)))
        self.assertLessEqual(imports, set(covered))
        names = [e['name'] for e in self.data['finishers']]
        self.assertEqual(len(names), len(set(names)))

    def test_imports_sit_inside_the_native_range(self):
        for level in F.LEVELS:
            ref = self.result['reference'][level]
            for row in self.result['rows']:
                if row['level'] == level and row['score']:
                    self.assertLessEqual(row['score'], ref['max'] * (1 + F.TOLERANCE), row)

    def test_a_strong_outlier_fails(self):
        def boost(e):
            e['move']['power'] = 400
        self.assertTrue(any('band' in p for p in self.problems_after('Veemon', boost)))

    def test_a_weak_outlier_fails(self):
        def drop(e):
            e['move']['power'] = 20
        self.assertTrue(self.problems_after('MetalGarurumon', drop))

    def test_area_takes_the_band_floor(self):
        def raise_area(e):
            e['move']['power'] += 10
        self.assertTrue(any('floor' in p for p in self.problems_after('SkullMeramon', raise_area)))

    def test_status_is_capped(self):
        def strong(e):
            e['move']['statusChance'] = 50
        self.assertTrue(any('status chance' in p for p in self.problems_after('Raremon', strong)))

        def status_on_top(e):
            e['move']['power'] = 195
        self.assertTrue(any('band middle' in p for p in self.problems_after('Raremon', status_on_top)))

    def test_buff_is_capped_and_has_a_fallback(self):
        def big(e):
            e['buff']['defense'] = 90
        self.assertTrue(self.problems_after('Baihumon', big))

        def no_fallback(e):
            del e['fallback']
        self.assertTrue(any('fallback' in p for p in self.problems_after('Baihumon', no_fallback)))

    def test_element_must_be_a_specialty(self):
        def wrong(e):
            e['move']['element'] = 'filth'
        self.assertTrue(any('specialties' in p for p in self.problems_after('Veemon', wrong)))

    def test_kind_fixes_range_and_distance(self):
        def far_breath(e):
            e['move']['distance'] = 640000
        self.assertTrue(any('distance' in p for p in self.problems_after('Raremon', far_breath)))

    def test_move_shape_exists_in_dw1(self):
        def odd_iframes(e):
            e['move']['iframes'] = 9
        self.assertTrue(any('no DW1 technique' in p for p in self.problems_after('Veemon', odd_iframes)))

        def targeted_melee(e):
            e['move']['flags'] = ['T']
        self.assertTrue(any('needs a target' in p for p in self.problems_after('Woodmon', targeted_melee)))

    def test_native_names_are_not_reused(self):
        def native(e):
            e['name'] = 'Mega Flame'
        self.assertTrue(any('DW1 technique' in p for p in self.problems_after('SkullMeramon', native)))

        def shown(e):
            e['name'] = 'Giga Destroyer'   # technique 79's displayed name
        self.assertTrue(any('DW1 technique' in p for p in self.problems_after('SkullMeramon', shown)))


if __name__ == '__main__':
    unittest.main()
