"""Zanbamon (430) wears native Monochromon's skeleton with nine bones of its own for the rider (torso, cape, head, crests, arms): the donor's programs, the gaits re-planted and the rider moved by zanbamon_gait."""
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
DONOR_BONES = 24
RIDER_BONES = 9
BONES = DONOR_BONES + RIDER_BONES
BUFFER = 100352
TICKS = {0: 34, 2: 14, 3: 18, 4: 12}                     # idle, walk, condition walk, run
SPEEDS = {2: 19.0, 3: 12.5, 4: 40.0}                     # the gait stage's units per tick
TARGET_SHA256 = '89e7b04046c6a79b95f42189a3395ebe4f4db84b278ef0b5ff4cc7d5920633b4'


class ZanbamonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('430-*.MMD'))
        tims = list(source.glob('430-*.TIM'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD1/MONO.MMD'
        if not files or not tims or not native_path.exists():
            raise unittest.SkipTest('needs the imported 430 model (edit.py get 430) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['430']
        spec = importlib.util.spec_from_file_location('imported_species_430', 'content/models/imports/species.py')
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        cls.tmp = tempfile.mkdtemp(prefix='zanbamon-')
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        shutil.copy(files[0], base / '430.MMD')
        shutil.copy(tims[0], base / '430.TIM')
        imported.BASE_MODELS = str(base)
        path, cls.proof = imported.overlay(str(Path(cls.tmp) / 'species'), '430')
        cls.data = Path(path).read_bytes()
        cls.rig = cls.proof['generated_skeleton']
        cls.record = json.loads(next(Path('content/species').glob('430-*.json')).read_text())
        mmd.exe().add_type(9430, cls.rig)
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

    def test_rig_is_monochromons_plus_the_riders_and_every_piece_is_bound_once(self):
        donor_rig = mmd.exe().skeleton[DONOR]
        self.assertEqual([p for _, p in self.rig[:DONOR_BONES]], [p for _, p in donor_rig])
        self.assertEqual(len(self.rig), BONES)
        self.assertEqual((self.recipe['donor'], self.recipe['model']), (DONOR, 'CHDAT/MMD1/MONO.MMD'))
        self.assertEqual(sorted(o for o, _ in self.rig if o >= 0), list(range(len(self.model.tmd.objects))))
        source = self.record['model']['skeleton']
        self.assertEqual(sorted(map(int, self.recipe['map'])), list(range(1, len(source))))
        # the rider's bones hang on Monochromon's hind hub (13) through the torso, the arms and the head on the torso
        names = [r['name'] for r in self.recipe['riders']]
        self.assertEqual(names, ['torso', 'cape', 'head', 'crestL', 'crestR', 'armRup', 'armRlo', 'armLup', 'armLlo'])
        parents = [self.rig[DONOR_BONES + k][1] for k in range(RIDER_BONES)]
        self.assertEqual(parents, [13] + [DONOR_BONES]*2 + [DONOR_BONES + 2]*2 + [DONOR_BONES]
                         + [DONOR_BONES + 5] + [DONOR_BONES] + [DONOR_BONES + 7])
        # the beast's neck and head ride Monochromon's, its tail the donor's tail
        m = self.recipe['map']
        self.assertEqual((m['3'], m['4']), (3, 4))
        self.assertEqual({m[k] for k in ('24', '25', '26')}, {14, 15, 16})

    def test_the_donor_is_pinned_and_a_changed_donor_stops(self):
        donor = (Path(mmd.EXTRACTED) / self.recipe['model']).read_bytes()
        self.assertEqual(hashlib.sha256(donor).hexdigest(), self.recipe['donor_sha256'])
        with self.assertRaises(ValueError):
            binding.bind(Path(self.tmp, 'base', '430.MMD').read_bytes(), self.record['model']['skeleton'],
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
        self.assertEqual(sorted(rows), [0, 2, 3, 4])
        for slot, row in rows.items():
            self.assertLessEqual(row['lowest_point'], 3, slot)
            self.assertLessEqual(max(row['stance_slip'].values()), .35, slot)
            self.assertLess(row['unreached'], 1, slot)

    def test_the_rider_moves_on_its_own_bones_and_stays_on_the_mount(self):
        swing = {2: 4, 3: 8, 4: 8}                           # the least torso pitch swing in degrees: it moves with every stride
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            for k in range(RIDER_BONES):
                bone = DONOR_BONES + k
                # the pivot never slides on the mount: only the rotation channels change from tick to tick
                self.assertEqual({tuple(f[bone][6:9]) for f in frames}, {tuple(frames[0][bone][6:9])}, (slot, bone))
        for slot, least in swing.items():
            pitch = [f[DONOR_BONES][3]*360/4096 for f in self.frames(slot)]
            self.assertGreater(max(pitch) - min(pitch), least/2, slot)
        # in the idle the head turns to look about
        yaw = [f[DONOR_BONES + 2][4]*360/4096 for f in self.frames(0)]
        self.assertGreater(max(yaw) - min(yaw), 20)
        # tired it slumps forward, in the run it leans: the torso's mean pitch is bowed in both
        for slot in (3, 4):
            self.assertGreater(np.mean([f[DONOR_BONES][3] for f in self.frames(slot)])*360/4096, 6, slot)

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

    def test_battle_originals(self):
        # the source game's own battle clips, retargeted onto the donor rig; all but the idles (which loop at their own
        # speed) as long as the donor's clip they replace, since technique effects are timed to it
        made = self.proof['battle_originals']
        self.assertEqual(sorted(int(s) for s in made), self.recipe['battle_originals']['slots'])
        for slot, row in made.items():
            if int(slot) not in (33, 34):
                self.assertEqual(row['frames'], row['donor_frames'])

    def test_the_buffer_holds(self):
        info = motionstorage.require(self.data, BONES)
        self.assertTrue(info['fits'])
        self.assertLess(info['resident_bytes'], BUFFER)
        self.assertEqual(info['resident_bytes'], 99368)
        for read in info['cold_reads']:
            self.assertTrue(read['fits'], read)


if __name__ == '__main__':
    unittest.main()
