"""Gatomon (234) moves exactly like BlackGatomon (222): the same rig, the same field layers, the same parameters."""
import json
import os
from pathlib import Path
import unittest
import mmd
import animsheet
from motiondiscidentity import changed_programs
from tools.models.field_animations import black_gatomon_calm, pace

MODELS = Path(os.environ.get('GATOMON_MODELS', 'build/imported-model-edit/edit'))
FILES = {234: 'Gatomon', 222: 'BlackGatomon'}


class GatomonRows(unittest.TestCase):
    def test_the_pace_row_is_blackgatomons_with_its_own_source(self):
        rows = json.loads(pace.MANIFEST.read_text())
        a, b = rows['234'], rows['222']
        self.assertEqual(a['name'], 'Gatomon')
        for key in ('bones', 'skeleton_sha256', 'base_generator', 'slots', 'after_generator'):
            self.assertEqual(a[key], b[key], key)
        self.assertNotEqual(a['source_sha256'], b['source_sha256'])

    def test_the_two_species_share_a_rig(self):
        rigs = [json.loads(Path(p).read_text())['model']['skeleton'] for p in sorted(Path('content/species').glob('2[23][24]-*gatomon.json'))]
        self.assertEqual(len(rigs), 2)
        self.assertEqual(rigs[0], rigs[1])


class GatomonClips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all((MODELS / f'{sid}-{name}.MMD').exists() for sid, name in FILES.items()):
            raise unittest.SkipTest('needs the imported Gatomon and BlackGatomon models (tools/models/edit.py get)')
        cls.rig = json.loads(next(Path('content/species').glob('234-*.json')).read_text())['model']['skeleton']
        cls.old, cls.new, cls.report = {}, {}, {}
        for sid, name in FILES.items():
            raw = (MODELS / f'{sid}-{name}.MMD').read_bytes()
            data, cls.report[sid] = pace.build(raw, cls.rig)
            cls.old[sid] = mmd.MMD.parse(raw, 19)
            cls.new[sid] = mmd.MMD.parse(data, 19)
            for m in (cls.old[sid], cls.new[sid]):
                m.type = sid

    def frames(self, sid, slot):
        return animsheet.slot_frames(self.new[sid], 19, slot)[0]

    def test_field_slots_have_the_same_timing_and_root_speed(self):
        for slot, ticks, speed in ((2, 8, 15), (3, 12, 9.5), (4, 16, 38)):
            fa, fb = self.frames(234, slot), self.frames(222, slot)
            self.assertEqual((len(fa) - 1, len(fb) - 1), (ticks, ticks))
            for f in (fa, fb):
                self.assertAlmostEqual(abs(f[-1][0][8] - f[0][0][8]) / ticks, speed, delta=.3)

    def test_only_the_walk_condition_walk_and_run_change(self):
        for sid in FILES:
            self.assertEqual(changed_programs(self.old[sid], self.new[sid]), [2, 3, 4])
            self.assertEqual(self.old[sid].tmd.build(), self.new[sid].tmd.build())
        # idle, the care and every other program stay the species' own
        for slot in (0, 1, 5):
            self.assertEqual(self.frames(234, slot), animsheet.slot_frames(self.old[234], 19, slot)[0])

    def test_the_legs_are_written_as_the_same_planted_step(self):
        a = self.report[234]['following_recipe']['checks']
        b = self.report[222]['following_recipe']['checks']
        self.assertEqual([(c['slot'], c['ticks']) for c in a], [(c['slot'], c['ticks']) for c in b])
        for c in a:
            self.assertLess(c['ground_err'], 1)
            self.assertGreater(c['reach_min'], 0)
        self.assertEqual(self.report[234]['following_recipe']['species'], 234)

    def test_resident_animation_buffer_fits(self):
        for sid in FILES:
            storage = self.report[sid]['storage']
            self.assertTrue(storage['fits'])
            self.assertLessEqual(storage['resident_bytes'], storage['resident_limit'])
        self.assertEqual(black_gatomon_calm.SPECIES, 222)


if __name__ == '__main__':
    unittest.main()
