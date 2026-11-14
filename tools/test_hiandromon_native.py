"""HiAndromon (302) wears native Andromon's skeleton: its rig and field programs are Andromon's own, scaled to its body."""
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

DONOR = 40
BONES = 21
SOLES = (16, 20)
BUFFER = 100352


class HiAndromonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('302-*.MMD'))
        tims = list(source.glob('302-*.TIM'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD1/ANDR.MMD'
        if not files or not tims or not native_path.exists():
            raise unittest.SkipTest('needs the imported 302 model (edit.py get 302) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['302']
        spec = importlib.util.spec_from_file_location('imported_species_302', 'content/models/imports/species.py')
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        cls.tmp = tempfile.mkdtemp(prefix='hiandromon-')
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        shutil.copy(files[0], base / '302.MMD')
        shutil.copy(tims[0], base / '302.TIM')
        imported.BASE_MODELS = str(base)
        path, cls.proof = imported.overlay(str(Path(cls.tmp) / 'species'), '302')
        cls.data = Path(path).read_bytes()
        cls.rig = cls.proof['generated_skeleton']
        cls.record = json.loads(next(Path('content/species').glob('302-*.json')).read_text())
        mmd.exe().add_type(9302, cls.rig)
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

    def test_rig_is_andromons_and_every_piece_is_bound_once(self):
        self.assertEqual([p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[DONOR]])
        self.assertEqual(len(self.rig), BONES)
        self.assertEqual((self.recipe['donor'], self.recipe['model']), (DONOR, 'CHDAT/MMD1/ANDR.MMD'))
        self.assertEqual(sorted(o for o, _ in self.rig if o >= 0), list(range(len(self.model.tmd.objects))))
        source = self.record['model']['skeleton']
        self.assertEqual(sorted(map(int, self.recipe['map'])), list(range(1, len(source))))
        # each side's shoulder armour rides its own side's shoulder pivot (4 right, 8 left); the wrist and the hand share
        # Andromon's one hand bone, and so do the foot's heel and toes
        m = self.recipe['map']
        self.assertEqual((m['7'], m['13']), (4, 8))
        self.assertEqual((m['5'], m['6'], m['11'], m['12']), (7, 7, 11, 11))
        self.assertEqual((m['20'], m['21'], m['24'], m['25']), (16, 16, 20, 20))
        self.assertEqual({m[k] for k in ('16', '1', '17')}, {3, 2, 12})

    def test_walk_tired_walk_and_idle_are_the_donors_scaled_programs(self):
        scale = self.recipe['scale']
        for slot in (0, 2, 3):
            native = self.frames(slot, self.native)
            own = self.frames(slot)
            self.assertEqual(len(own), len(native), slot)
            self.assertAlmostEqual(self.speed(own), self.speed(native)*scale, delta=.3)

    def test_the_run_is_retimed_to_the_native_range(self):
        own = self.frames(4)
        self.assertEqual(len(own) - 1, self.recipe['pace']['4']['ticks'])
        self.assertAlmostEqual(self.speed(own), self.recipe['pace']['4']['speed'], delta=.5)
        self.assertIn(36, self.recipe['battle_originals']['slots'])     # the battle run is the source's own
        # at this scale the donor's own run would be faster than the range: its stride is kept over more ticks
        native = self.frames(4, self.native)
        self.assertGreater(self.speed(native)*self.recipe['scale'], 52)

    def test_slots_and_ticks(self):
        self.assertEqual([len(self.frames(s)) for s in (0, 2, 3, 4)], [21, 21, 23, 19])
        for slot in list(range(46, 46 + len(self.record['techniques']))) + [self.record['partner']['training']['animation']]:
            self.assertIsNotNone(self.model.anims.table[slot], slot)
        self.assertEqual(len(self.recipe['technique_slots']), len(self.record['techniques']))
        # every technique plays the donor's clip of its own name where it has one
        donor = ['Megaton Punch', 'Counter', 'Buster Dive', 'Tremar', 'Static Elect', 'Megalo Spark', 'Power Crane', 'Delete Program',
                 'Pulse Laser', 'Reverse Prog', 'Metal Sprinter', 'All Range Beam', 'DG Dimension', 'Full Potential', 'Spiral Sword']
        for move, slot in zip(self.record['techniques'], self.recipe['technique_slots']):
            if move in donor:
                self.assertEqual(slot, 46 + donor.index(move), move)

    def test_gait_speeds_are_native_and_ordered(self):
        walk, tired, run = (self.speed(self.frames(s)) for s in (2, 3, 4))
        self.assertTrue(15 <= walk <= 31, walk)
        self.assertTrue(10 <= tired <= 20, tired)
        self.assertTrue(35 <= run <= 52, run)
        self.assertLess(tired, walk)
        self.assertLess(walk, run)

    def test_loops_close(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            for bone in range(BONES):
                np.testing.assert_allclose(mmd.rot_matrix(*frames[0][bone][3:6]), mmd.rot_matrix(*frames[-1][bone][3:6]),
                                           atol=.01, err_msg=str(bone))

    def test_no_tick_jumps(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            # the angle between a bone's rotations on two ticks (an Euler triple may flip to its twin between them)
            def turn(f, g):
                return max(np.degrees(np.arccos(np.clip((np.trace(np.array(mmd.rot_matrix(*pa[3:6])).T @ np.array(mmd.rot_matrix(*pb[3:6]))) - 1)/2, -1, 1)))
                           for pa, pb in zip(f, g))
            steps = [turn(f, g) for f, g in zip(frames, frames[1:])]
            # the donor's own idle swings the right knee 3.4 times its median step in its first two ticks (a settling
            # shift of weight); its gaits stay inside 2.5
            self.assertLess(max(steps), (3.5 if slot == 0 else 2.5)*max(np.median(steps), 1), slot)

    def test_effect_points_and_bubble_sit_on_real_bones(self):
        patch = self.recipe['species_patch']
        self.assertTrue(0 <= patch['condition_bubble'][3] < BONES)
        for row in patch['effect_origins']:
            self.assertTrue(0 <= row[4] < BONES, row)

    def test_battle_originals(self):
        # the source game's own battle clips, retargeted onto the donor rig (native_battle.py); one-shot clips keep the
        # length of the donor's clip they replace, since technique effects are timed to it
        made = self.proof['battle_originals']
        self.assertEqual(sorted(int(s) for s in made), self.recipe['battle_originals']['slots'])
        for slot, row in made.items():
            if int(slot) not in (33, 34):
                self.assertEqual(row['frames'], row['donor_frames'])

    def test_the_buffer_holds(self):
        info = motionstorage.require(self.data, BONES)
        self.assertTrue(info['fits'])
        self.assertLess(info['resident_bytes'], BUFFER)

    def test_feet_stand_on_the_floor_in_the_gaits(self):
        for slot in (2, 3):
            low = []
            for pose in self.frames(slot)[:-1]:
                p = [list(x) for x in pose]
                p[0] = [4096]*3 + p[0][3:6] + [0, 0, 0]
                w = np.array(mmd.bone_matrices(self.model, p))
                ys = []
                for b in SOLES:
                    v = np.array(self.model.tmd.obj_verts(self.rig[b][0]))[:, :3]
                    ys.append((v @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max())
                low.append(max(ys))
            # the donor's own sole runs the same bounds on its own mesh
            self.assertLessEqual(max(low), 60, slot)
            self.assertGreaterEqual(min(low), -5, slot)


if __name__ == '__main__':
    unittest.main()
