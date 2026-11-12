"""Check Maildramon's field gaits (species 324): the native Unimon trunk with planted legs, made through the overlay.

Needs the imported model (`tools/models/edit.py get 324`, default build/imported-model-edit/edit) and the player DW1
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
from tools.models.field_animations import maildramon_gait

SPEED = {2: (15, 31), 3: (10, 20), 4: (35, 52)}
TICKS = {2: 16, 3: 20, 4: 12}


@unittest.skipUnless((Path(os.environ.get('MAILDRAMON_MODELS', 'build/imported-model-edit/edit')) / '324-Maildramon.MMD').exists()
                     and (Path(mmd.EXTRACTED) / 'CHDAT/MMD1/UNIM.MMD').exists(),
                     'needs the imported 324 model (tools/models/edit.py get 324) and the player DW1 extraction')
class MaildramonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        models = Path(os.environ.get('MAILDRAMON_MODELS', 'build/imported-model-edit/edit'))
        spec = importlib.util.spec_from_file_location('imported_species_324', 'content/models/imports/species.py')
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        cls.tmp = tempfile.mkdtemp()
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        shutil.copy(models / '324-Maildramon.MMD', base / '324.MMD')
        shutil.copy(models / '324-Maildramon.TIM', base / '324.TIM')
        imported.BASE_MODELS = str(base)
        path, cls.proof = imported.overlay(str(Path(cls.tmp) / 'species'), '324')
        cls.out = Path(cls.tmp) / 'out'
        cls.out.mkdir()
        shutil.copy(path, cls.out / '324.MMD')
        shutil.copy(models / '324-Maildramon.TIM', cls.out / '324.TIM')

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
            self.assertLessEqual(c['lowest_point'], 4, slot)
            self.assertLess(c['unreached'], 1, slot)

    def test_the_measured_slip_and_the_steps_between_ticks(self):
        rig = self.proof['generated_skeleton']
        mmd.exe().skeleton[324] = rig
        mmd.exe().bone_count[324] = len(rig)
        for slot in (2, 3, 4):
            m = animstudio.Model(f'{self.out}/324.MMD:324:{self.out}/324.TIM', slot)
            per = []
            for foot in m.lowest[:4]:
                m.lowest = [foot, foot]
                per.append(animstudio.metrics(m)[1][0][3:5])
            self.assertLess(sum(a for a, _ in per) / 4, 25, slot)
            self.assertLess(max(b for _, b in per), 45, slot)

    def test_the_footsteps_are_kept(self):
        for slot, c in self.checks().items():
            self.assertTrue(c['sound_ticks'], slot)

    def test_the_resident_buffer_fits(self):
        st = self.proof['storage']
        self.assertTrue(st['fits'])
        self.assertLess(st['resident_bytes'], motionstorage.RESIDENT_LIMIT if hasattr(motionstorage, 'RESIDENT_LIMIT') else 100352)

    def test_the_recipe_asks_for_the_stage(self):
        recipes = json.loads(Path('content/models/imports/native-bindings.json').read_text())
        self.assertEqual(recipes['324']['gait'], 'maildramon_gait')
        self.assertTrue(all('gait' not in r for k, r in recipes.items() if k != '324'))
        self.assertTrue(hasattr(maildramon_gait, 'build'))


if __name__ == '__main__':
    unittest.main()
