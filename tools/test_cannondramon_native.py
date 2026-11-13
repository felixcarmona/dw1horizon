"""Cannondramon (405) wears native Monochromon's skeleton: its rig and field programs are Monochromon's, the three gaits re-planted by cannondramon_gait."""
import hashlib
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
from tools.models.field_animations import native_binding as binding

DONOR = 47
BONES = 24
BUFFER = 100352
TICKS = {0: 47, 2: 14, 3: 20, 4: 12}                     # idle, walk, condition walk, run
SPEEDS = {2: 15.0, 3: 10.5, 4: 36.0}                     # the gait stage's units per tick
TARGET_SHA256 = '9ae2236f464d0f0852f969dd401b15b6c60badee2a20f7914b77aec3d2c1b9cb'


class CannondramonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('405-*.MMD'))
        tims = list(source.glob('405-*.TIM'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD1/MONO.MMD'
        if not files or not tims or not native_path.exists():
            raise unittest.SkipTest('needs the imported 405 model (edit.py get 405) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['405']
        spec = importlib.util.spec_from_file_location('imported_species_405', 'content/models/imports/species.py')
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        cls.tmp = tempfile.mkdtemp(prefix='cannondramon-')
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        shutil.copy(files[0], base / '405.MMD')
        shutil.copy(tims[0], base / '405.TIM')
        imported.BASE_MODELS = str(base)
        path, cls.proof = imported.overlay(str(Path(cls.tmp) / 'species'), '405')
        cls.data = Path(path).read_bytes()
        cls.rig = cls.proof['generated_skeleton']
        cls.record = json.loads(next(Path('content/species').glob('405-*.json')).read_text())
        mmd.exe().add_type(9405, cls.rig)
        cls.model = mmd.MMD.parse(cls.data, len(cls.rig))
        cls.model.type = DONOR
        cls.native = mmd.MMD.load(str(native_path), DONOR)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.model, BONES, slot)[0]

    @staticmethod
    def speed(frames):
        return abs(frames[-1][0][8] - frames[0][0][8])/(len(frames) - 1)

    def test_the_built_model_is_the_reviewed_one(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), TARGET_SHA256)
        self.assertEqual(self.proof['output_sha256'], TARGET_SHA256)

    def test_rig_is_ogremons_and_every_piece_is_bound_once(self):
        self.assertEqual([p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[DONOR]])
        self.assertEqual(len(self.rig), BONES)
        self.assertEqual((self.recipe['donor'], self.recipe['model']), (DONOR, 'CHDAT/MMD1/MONO.MMD'))
        self.assertEqual(sorted(o for o, _ in self.rig if o >= 0), list(range(len(self.model.tmd.objects))))
        source = self.record['model']['skeleton']
        self.assertEqual(sorted(map(int, self.recipe['map'])), list(range(1, len(source))))
        # the three neck pieces ride Monochromon's neck, the five cannon and weapon pieces its chest, and the tail pieces its tail
        m = self.recipe['map']
        self.assertEqual({m[k] for k in ('15', '16', '17')}, {3})
        self.assertEqual({m[k] for k in ('14', '20', '21', '22', '23')}, {2})
        self.assertEqual((m['3'], m['4'], m['5']), (14, 15, 16))

    def test_the_donor_is_pinned_and_a_changed_donor_stops(self):
        donor = (Path(mmd.EXTRACTED) / self.recipe['model']).read_bytes()
        self.assertEqual(hashlib.sha256(donor).hexdigest(), self.recipe['donor_sha256'])
        with self.assertRaises(ValueError):
            binding.bind(Path(self.tmp, 'base', '405.MMD').read_bytes(), self.record['model']['skeleton'],
                         dict(self.recipe, donor_sha256='0'*64))

    def test_field_ticks_and_slots(self):
        self.assertEqual({s: len(self.frames(s)) - 1 for s in TICKS}, TICKS)
        for slot in list(range(46, 46 + len(self.record['techniques']))) + [self.record['partner']['training']['animation']]:
            self.assertIsNotNone(self.model.anims.table[slot], slot)
        self.assertEqual(self.recipe['technique_slots'], [46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 48, 49, 50])
        self.assertGreaterEqual(len(self.recipe['technique_slots']), len(self.record['techniques']))
        # the care slot 61 plays the donor's clip 51
        self.assertEqual(self.recipe['extra_slots'], {'61': 51})
        for slot in (61,):
            self.assertIsNotNone(self.model.anims.table[slot], slot)

    def test_gait_speeds_are_the_recipes_and_ordered(self):
        speeds = {s: self.speed(self.frames(s)) for s in SPEEDS}
        for slot, want in SPEEDS.items():
            self.assertAlmostEqual(speeds[slot], want, delta=.8, msg=slot)
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])

    def test_feet_stay_planted_and_never_sink(self):
        rows = {row['slot']: row for row in self.proof['gait']}
        self.assertEqual(sorted(rows), [2, 3, 4])
        for slot, row in rows.items():
            self.assertLessEqual(row['lowest_point'], 3, slot)
            self.assertLessEqual(max(row['stance_slip'].values()), .35, slot)
            self.assertLess(row['unreached'], 1, slot)

    def test_loops_close(self):
        for slot in TICKS:
            frames = self.frames(slot)
            for bone in range(BONES):
                np.testing.assert_allclose(mmd.rot_matrix(*frames[0][bone][3:6]), mmd.rot_matrix(*frames[-1][bone][3:6]),
                                           atol=.01, err_msg=f'{slot} {bone}')

    def test_no_tick_jumps(self):
        for slot in SPEEDS:                                  # the donor's own idle is not ours to judge
            frames = self.frames(slot)
            steps = [max(abs(a - b) for pa, pb in zip(f, g) for a, b in zip(pa[3:6], pb[3:6])) for f, g in zip(frames, frames[1:])]
            self.assertLess(max(steps), 2.5*max(np.median(steps), 1), slot)

    def test_effect_points_and_bubble_sit_on_real_bones(self):
        patch = self.recipe['species_patch']
        self.assertTrue(0 <= patch['condition_bubble'][3] < BONES)
        for row in patch['effect_origins']:
            self.assertTrue(0 <= row[4] < BONES, row)
            self.assertTrue(0 <= row[0] < BONES, row)

    def test_the_buffer_holds(self):
        info = motionstorage.require(self.data, BONES)
        self.assertTrue(info['fits'])
        self.assertLess(info['resident_bytes'], BUFFER)
        self.assertEqual(info['resident_bytes'], 87984)
        for read in info['cold_reads']:
            self.assertTrue(read['fits'], read)


if __name__ == '__main__':
    unittest.main()
