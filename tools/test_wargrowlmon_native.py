"""WarGrowlmon (326) wears Growlmon's skeleton: its rig and field programs are Growlmon's own, scaled to its body."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models import chibi_proportions
from tools.models.field_animations import native_binding as binding

DONOR = 320
BONES = 25
BUFFER = 100352


class WarGrowlmonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = {sid: (list(source.glob(f'{sid}-*.MMD')), list(source.glob(f'{sid}-*.TIM'))) for sid in (320, 326)}
        if not all(all(pair) for pair in files.values()):
            raise unittest.SkipTest('needs the imported 320 and 326 models (edit.py get 320, edit.py get 326)')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['326']
        spec = importlib.util.spec_from_file_location('imported_species_326', 'content/models/imports/species.py')
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        cls.tmp = tempfile.mkdtemp(prefix='wargrowlmon-')
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        for sid, (models, tims) in files.items():
            shutil.copy(models[0], base / f'{sid}.MMD')
            shutil.copy(tims[0], base / f'{sid}.TIM')
        imported.BASE_MODELS = str(base)
        path, cls.proof = imported.overlay(str(Path(cls.tmp) / 'species'), '326')
        cls.data = Path(path).read_bytes()
        cls.rig = cls.proof['generated_skeleton']
        cls.record = json.loads(next(Path('content/species').glob('326-*.json')).read_text())
        mmd.exe().add_type(9326, cls.rig)
        cls.model = mmd.MMD.parse(cls.data, len(cls.rig))
        cls.model.type = DONOR
        cls.native = mmd.MMD.parse((base / '320.MMD').read_bytes(), BONES)
        cls.native.type = DONOR

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.model, BONES, slot)[0]

    @staticmethod
    def speed(frames):
        return abs(frames[-1][0][8] - frames[0][0][8])/(len(frames) - 1)

    def test_rig_is_growlmons_and_every_piece_is_bound_once(self):
        self.assertEqual([p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[DONOR]])
        self.assertEqual(len(self.rig), BONES)
        self.assertEqual((self.recipe['donor'], self.recipe['donor_species']), (DONOR, DONOR))
        self.assertEqual(sorted(o for o, _ in self.rig if o >= 0), list(range(len(self.model.tmd.objects))))
        source = self.record['model']['skeleton']
        self.assertEqual(sorted(map(int, self.recipe['map'])), list(range(1, len(source))))
        # the four back-whip pieces ride the upper body with the pods; the head and jaw pieces ride Growlmon's head
        m = self.recipe['map']
        self.assertEqual([m[k] for k in ('14', '15', '16', '17')], [1, 1, 1, 1])
        self.assertEqual(m['19'], 7)

    def test_the_donor_is_pinned_and_a_changed_donor_stops(self):
        self.assertEqual(binding.digest(binding.donor_model(self.recipe)), self.recipe['donor_sha256'])
        with self.assertRaises(ValueError):
            binding.bind(Path(self.tmp, 'base', '326.MMD').read_bytes(), self.record['model']['skeleton'],
                         dict(self.recipe, donor_sha256='0'*64))

    def test_every_field_program_is_growlmons_scaled(self):
        scale = self.recipe['scale']
        for slot in (0, 2, 3, 4):
            native = self.frames(slot, self.native)
            own = self.frames(slot)
            self.assertEqual(len(own), len(native), slot)
            self.assertAlmostEqual(self.speed(own), self.speed(native)*scale, delta=.3, msg=slot)

    def test_slots_and_ticks(self):
        for slot in list(range(46, 46 + len(self.record['techniques']))) + [self.record['partner']['training']['animation']]:
            self.assertIsNotNone(self.model.anims.table[slot], slot)
        # the 14 techniques play Growlmon's clips 46 to 56, then 48, 47 and 46 (the recipe lists one slot more than the techniques)
        self.assertEqual(self.recipe['technique_slots'][:11], list(range(46, 57)))
        self.assertGreaterEqual(len(self.recipe['technique_slots']), len(self.record['techniques']))
        self.assertEqual([len(self.frames(s)) for s in (0, 2, 3, 4)], [len(self.frames(s, self.native)) for s in (0, 2, 3, 4)])

    def test_gait_speeds_are_ordered(self):
        walk, tired, run = (self.speed(self.frames(s)) for s in (2, 3, 4))
        self.assertLess(tired, walk)
        self.assertLess(walk, run)

    def test_loops_close(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            for bone in range(BONES):
                np.testing.assert_allclose(mmd.rot_matrix(*frames[0][bone][3:6]), mmd.rot_matrix(*frames[-1][bone][3:6]),
                                           atol=.01, err_msg=f'{slot} {bone}')

    def test_no_tick_jumps_beyond_the_donors(self):
        def steps(model, slot):
            frames = self.frames(slot, model)
            return [max(abs(a - b) for pa, pb in zip(f, g) for a, b in zip(pa[3:6], pb[3:6])) for f, g in zip(frames, frames[1:])]
        for slot in (0, 2, 3, 4):
            self.assertEqual(steps(self.model, slot), steps(self.native, slot), slot)      # the rotations are the donor's, tick by tick

    def test_effect_points_and_bubble_sit_on_real_bones(self):
        patch = self.recipe['species_patch']
        self.assertTrue(0 <= patch['condition_bubble'][3] < BONES)
        for row in patch['effect_origins']:
            self.assertTrue(0 <= row[4] < BONES, row)

    def test_the_buffer_holds(self):
        info = motionstorage.require(self.data, BONES)
        self.assertTrue(info['fits'])
        self.assertLess(info['resident_bytes'], BUFFER)

    def test_the_chibi_proportions_stay_pinned(self):
        pins = json.loads(chibi_proportions.PINS.read_text())['326']
        rows = json.loads(chibi_proportions.chibi.MANIFEST.read_text())
        groups = chibi_proportions.chibi.donor_groups(self.recipe['map'], {int(b): g for b, g in rows['326']['groups'].items()})
        measured = chibi_proportions.chibi.proportions(self.data, self.rig, groups, 9326)
        self.assertFalse(chibi_proportions.strays('326', measured, pins), measured)


if __name__ == '__main__':
    unittest.main()
