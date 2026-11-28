import json
import unittest

from tools.models import species_size


class SpeciesSize(unittest.TestCase):
    def test_bone_factor_scales_the_whole_subtree(self):
        skeleton = [(-1, -1), (0, 0), (1, 1), (2, 2), (3, 1)]
        self.assertEqual(species_size.cumulative(skeleton, {2: 1.2, 3: 1 / 1.2}), [1.0, 1.0, 1.2, 1.0, 1.0])
        self.assertEqual(species_size.cumulative(skeleton, {1: 0.5}), [1.0, 0.5, 0.5, 0.5, 0.5])

    def test_record_follows_the_model(self):
        s = {'model': {'height': 500, 'radius': 200}, 'condition_bubble': [10, -100, 0, 2],
             'effect_origins': [[4, 70, 0, 20, 2, 10, 50, -100], [4, 70, 0, 20, 'any', 1, 2, 3]],
             'effect_origin_fallback': [1, 0, -40, 0]}
        proof = dict(factor=0.5, height_before=500, height_after=300, point_scale=[0.5, 0.5, 0.6])
        out = species_size.patch_record(s, proof)
        self.assertEqual(out['model'], {'height': 300, 'radius': 100})
        self.assertEqual(out['condition_bubble'], [6, -60, 0, 2])
        self.assertEqual(out['effect_origins'], [[4, 70, 0, 20, 2, 6, 30, -60], [4, 70, 0, 20, 'any', 1, 2, 3]])
        self.assertEqual(out['effect_origin_fallback'], [1, 0, -20, 0])
        self.assertEqual(s['model']['height'], 500)

    def test_a_release_can_take_its_own_factor(self):
        row = {'target': 1.4, 'factor': 1.1, 'variants': {'dw3-us': {'factor': 1.3}}}
        self.assertEqual(species_size.variant_row(row, 'dw3-us')['factor'], 1.3)
        self.assertEqual(species_size.variant_row(row, None)['factor'], 1.1)
        self.assertEqual(species_size.variant_row({'factor': 1.1}, 'dw3-us'), {'factor': 1.1})

    def test_manifest_rows_are_complete(self):
        rows = species_size.rows()
        for sid, row in rows.items():
            self.assertGreaterEqual(int(sid), 180)
            self.assertTrue(0.3 < row['factor'] < 2.0, sid)
            self.assertIn('target', row)
            for bone, k in row.get('bones', {}).items():
                self.assertTrue(int(bone) > 0 and 0.5 < k < 2.0, sid)
            for bone, k in row.get('width', {}).items():
                self.assertTrue(int(bone) > 0 and all(0.5 < c < 2.0 for c in (k if isinstance(k, list) else [k])), sid)


if __name__ == '__main__':
    unittest.main()
