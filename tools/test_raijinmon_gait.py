"""Check Raijinmon's field gaits (species 333): the native Ogremon trunk with planted legs, made through the overlay.

Needs the imported model (`tools/models/edit.py get 333`, default build/imported-model-edit/edit) and the player DW1
extraction; without them the tests skip.
"""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animstudio
import mmd
import motionstorage
from tools.models.field_animations import raijinmon_gait

SPEED = {0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)}
TICKS = {0: 60, 2: 30, 3: 36, 4: 20}


@unittest.skipUnless((Path(os.environ.get('RAIJINMON_MODELS', 'build/imported-model-edit/edit')) / '333-Raijinmon.MMD').exists()
                     and (Path(mmd.EXTRACTED) / 'CHDAT/MMD1/OGRE.MMD').exists(),
                     'needs the imported 333 model (tools/models/edit.py get 333) and the player DW1 extraction')
class RaijinmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        models = Path(os.environ.get('RAIJINMON_MODELS', 'build/imported-model-edit/edit'))
        spec = importlib.util.spec_from_file_location('imported_species_333', 'content/models/imports/species.py')
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        cls.tmp = tempfile.mkdtemp()
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        shutil.copy(models / '333-Raijinmon.MMD', base / '333.MMD')
        shutil.copy(models / '333-Raijinmon.TIM', base / '333.TIM')
        imported.BASE_MODELS = str(base)
        path, cls.proof = imported.overlay(str(Path(cls.tmp) / 'species'), '333')
        cls.out = Path(cls.tmp) / 'out'
        cls.out.mkdir()
        shutil.copy(path, cls.out / '333.MMD')
        shutil.copy(models / '333-Raijinmon.TIM', cls.out / '333.TIM')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def checks(self):
        return {c['slot']: c for c in self.proof['gait']}

    def test_the_clips_are_integer_tick_loops_at_native_speeds(self):
        for slot, c in self.checks().items():
            self.assertEqual(c['ticks'], TICKS[slot])
            lo, hi = SPEED[slot]
            self.assertTrue(lo <= c['units_per_tick'] <= hi, (slot, c['units_per_tick']))
        speeds = [self.checks()[s]['units_per_tick'] for s in (3, 2, 4)]
        self.assertEqual(speeds, sorted(speeds))

    def test_the_soles_stand_still_and_stay_near_the_floor(self):
        for slot, c in self.checks().items():
            self.assertLess(max(c['stance_slip'].values()), 0.2, slot)
            self.assertGreaterEqual(c['lowest_point'], -3, slot)
            self.assertLessEqual(c['lowest_point'], 9 if slot == 0 else 4, slot)
            self.assertLess(c['unreached'], 1, slot)

    def test_the_measured_slip_and_the_steps_between_ticks(self):
        rig = self.proof['generated_skeleton']
        mmd.exe().skeleton[333] = rig
        mmd.exe().bone_count[333] = len(rig)
        for slot in (2, 3, 4):
            m = animstudio.Model(f'{self.out}/333.MMD:333:{self.out}/333.TIM', slot)
            per = []
            for foot in m.lowest[:2]:
                m.lowest = [foot, foot]
                per.append(animstudio.metrics(m)[1][0][3:5])
            self.assertLess(sum(a for a, _ in per) / 2, 25, slot)
            self.assertLess(max(b for _, b in per), 45, slot)

    def test_the_footsteps_are_kept(self):
        for slot, c in self.checks().items():
            if slot:
                self.assertTrue(c['sound_ticks'], slot)

    def test_the_resident_buffer_fits(self):
        st = self.proof['storage']
        self.assertTrue(st['fits'])
        self.assertLess(st['resident_bytes'], motionstorage.RESIDENT_LIMIT if hasattr(motionstorage, 'RESIDENT_LIMIT') else 100352)

    def test_the_recipe_asks_for_the_stage(self):
        recipes = json.loads(Path('content/models/imports/native-bindings.json').read_text())
        self.assertEqual(recipes['333']['gait'], 'raijinmon_gait')
        self.assertTrue(all('gait' not in r for k, r in recipes.items() if k not in ('333', '324', '402', '405', '409')))
        self.assertTrue(hasattr(raijinmon_gait, 'build'))


if __name__ == '__main__':
    unittest.main()
