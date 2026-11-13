"""Check NeoCrimson's clips (species 402): its parts bound to WarGreymon's rig by the recipe, WarGreymon's gait on top.

Needs the two imported base models (`tools/models/edit.py get 402` and `get 373`: NEOCRIMSON_MODEL and WARGREYMON_MODEL
name the files, default build/imported-model-edit/edit/). The test makes the overlay (a few seconds) and checks the
speeds, that the soles stand on the floor, the stance slip and the resident buffer.
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

EDIT = Path('build/imported-model-edit/edit')
SPEED = {2: (15, 31), 3: (10, 20), 4: (35, 52)}


class NeoCrimsonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        neo = Path(os.environ.get('NEOCRIMSON_MODEL', EDIT / '402-NeoCrimson.MMD'))
        war = Path(os.environ.get('WARGREYMON_MODEL', EDIT / '373-WarGreymon.MMD'))
        if not (neo.exists() and neo.with_suffix('.TIM').exists() and war.exists()):
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 402 and get 373')
        import importlib.util
        spec = importlib.util.spec_from_file_location('imported_species_402', 'content/models/imports/species.py')
        species = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(species)
        cls.tmp = tempfile.mkdtemp()
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        shutil.copy(neo, base / '402-NeoCrimson.MMD')
        shutil.copy(war, base / '373-WarGreymon.MMD')
        species.BASE_MODELS = str(base)
        records, names = species.records(), os.listdir('content/species')
        name, own = species._species('402', records['402'], names)
        own['model']['file'] = str(neo)
        path, cls.proof = species.overlay(cls.tmp + '/species', '402', records, names, own)
        cls.model = Path(path)
        cls.tim = neo.with_suffix('.TIM')
        cls.data = cls.model.read_bytes()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def clip(self, slot):
        return animstudio.Model(f'{self.model}:402:{self.tim}', slot)

    def test_speeds_and_order(self):
        speeds = {}
        for slot, (low, high) in SPEED.items():
            speed = abs(animstudio.metrics(self.clip(slot))[0])
            self.assertTrue(low <= speed <= high, (slot, speed))
            speeds[slot] = speed
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])

    def test_soles_stay_planted(self):
        for slot in SPEED:
            for row in animstudio.metrics(self.clip(slot))[1]:
                self.assertLessEqual(row[3], 25 if slot != 4 else 30, (slot, 'mean stance slip', row[3]))
                self.assertLessEqual(row[4], 45, (slot, 'worst stance slip', row[4]))

    def test_resident_buffer(self):
        import motionstorage
        rig = self.proof['generated_skeleton']
        self.assertLess(motionstorage.audit(self.data, len(rig))['resident_bytes'], 100352)

    def test_it_is_the_walk_ticks_of_two_cycles(self):
        self.assertEqual(len(self.clip(0).frames) - 1, 96)
        self.assertEqual(len(self.clip(2).frames) - 1, 44)


if __name__ == '__main__':
    unittest.main()
