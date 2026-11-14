"""GrapLeomon (306) wears native Leomon's skeleton and field programs, scaled to its body, and its four striped drums
(forearms and shins) turn about their own axes on four bones of their own after the donor's."""
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

DONOR = 48
DONOR_BONES = 23
BONES = 27
SOLES = (17, 18, 21, 22)
DRUMS = (23, 24, 25, 26)
BUFFER = 100352


class GrapLeomonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('306-*.MMD'))
        tims = list(source.glob('306-*.TIM'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD1/LEOM.MMD'
        if not files or not tims or not native_path.exists():
            raise unittest.SkipTest('needs the imported 306 model (edit.py get 306) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['306']
        spec = importlib.util.spec_from_file_location('imported_species_306', 'content/models/imports/species.py')
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        cls.tmp = tempfile.mkdtemp(prefix='vilemon-')
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        shutil.copy(files[0], base / '306.MMD')
        shutil.copy(tims[0], base / '306.TIM')
        imported.BASE_MODELS = str(base)
        path, cls.proof = imported.overlay(str(Path(cls.tmp) / 'species'), '306')
        cls.data = Path(path).read_bytes()
        cls.rig = cls.proof['generated_skeleton']
        cls.record = json.loads(next(Path('content/species').glob('306-*.json')).read_text())
        mmd.exe().add_type(9306, cls.rig)
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

    def test_rig_is_leomons_plus_four_drum_bones_and_every_piece_is_bound_once(self):
        self.assertEqual([p for _, p in self.rig[:DONOR_BONES]], [p for _, p in mmd.exe().skeleton[DONOR]])
        self.assertEqual(len(self.rig), BONES)
        self.assertEqual((self.recipe['donor'], self.recipe['model']), (DONOR, 'CHDAT/MMD1/LEOM.MMD'))
        self.assertEqual(sorted(o for o, _ in self.rig if o >= 0), list(range(len(self.model.tmd.objects))))
        source = self.record['model']['skeleton']
        self.assertEqual(sorted(map(int, self.recipe['map'])), list(range(1, len(source))))
        # the drums are children of the donor's forearm and shin bones
        self.assertEqual([self.rig[b][1] for b in DRUMS], [6, 9, 16, 20])
        self.assertEqual(list(self.recipe['spin']['bones']), ['4', '8', '17', '25'])
        # head parts ride the head, the tail follows the donor's tail chain
        self.assertEqual({self.recipe['map'][k] for k in ('10', '11', '12', '13')}, {3})
        self.assertEqual([self.recipe['map'][k] for k in ('20', '21', '22')], [12, 13, 14])

    def test_field_slots_below_the_techniques_are_the_donors_scaled_programs(self):
        scale = self.recipe['scale']
        for slot in (0, 2, 3, 4):
            native = animsheet.slot_frames(self.native, DONOR_BONES, slot)[0]
            own = self.frames(slot)
            self.assertEqual(len(own), len(native), slot)
            self.assertAlmostEqual(self.speed(own), self.speed(native)*scale, delta=.3)
            for bone in range(DONOR_BONES):
                self.assertEqual([f[bone][3:6] for f in own], [f[bone][3:6] for f in native], (slot, bone))

    def test_slots_and_ticks(self):
        self.assertEqual([len(self.frames(s)) for s in (0, 2, 3, 4)], [17, 17, 17, 17])
        for slot in range(46, 46 + len(self.record['techniques'])):
            self.assertIsNotNone(self.model.anims.table[slot], slot)
        self.assertEqual(self.recipe['technique_slots'], [48, 50, 49, 47, 51, 46, 53, 52, 52, 54, 55, 55, 54, 56])
        self.assertEqual(len(self.recipe['technique_slots']), len(self.record['techniques']))

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
            for bone in range(DONOR_BONES):
                np.testing.assert_allclose(mmd.rot_matrix(*frames[0][bone][3:6]), mmd.rot_matrix(*frames[-1][bone][3:6]),
                                           atol=.01, err_msg=str(bone))

    def test_no_tick_jumps_beyond_the_donors_own(self):
        # Leomon's run swings each thigh through 93 degrees in the tick it lifts (3.9 times the median): its own motion, kept
        for slot in (0, 2, 3, 4):
            ratios = []
            for model, nb in ((self.model, DONOR_BONES), (self.native, DONOR_BONES)):
                frames = [f[:nb] for f in animsheet.slot_frames(model, BONES if model is self.model else DONOR_BONES, slot)[0]]
                steps = [max(abs(a - b) for pa, pb in zip(f, g) for a, b in zip(pa[3:6], pb[3:6])) for f, g in zip(frames, frames[1:])]
                ratios.append(max(steps)/max(np.median(steps), 1))
            self.assertAlmostEqual(ratios[0], ratios[1], places=6, msg=slot)

    def test_effect_points_and_bubble_sit_on_real_bones(self):
        patch = self.recipe['species_patch']
        self.assertTrue(0 <= patch['condition_bubble'][3] < DONOR_BONES)
        for row in patch['effect_origins']:
            self.assertTrue(0 <= row[4] < BONES, row)

    def test_the_drums_turn_in_every_field_clip(self):
        quarters = {0: 1, 2: 3, 3: 2, 4: 4}
        per_tick = {}
        for slot, q in quarters.items():
            frames = self.frames(slot)
            for number, bone in enumerate(DRUMS):
                sign = list(self.recipe['spin']['bones'].values())[number].get('sign', 1)
                rz = [f[bone][5] for f in frames]
                steps = [b - a for a, b in zip(rz, rz[1:])]
                # one steady step a tick, whole quarter turns (the drum's facets repeat every 90 degrees) over the loop
                self.assertLessEqual(max(steps) - min(steps), 1, (slot, bone))
                self.assertAlmostEqual(rz[-1] - rz[0], sign*q*1024, delta=1)
                self.assertLessEqual(abs(steps[0])*360/4096, 30)
                self.assertLessEqual(abs(steps[0])*360/4096*2, 90)
            per_tick[slot] = abs(steps[0])
        self.assertLess(per_tick[0], per_tick[3])
        self.assertLess(per_tick[3], per_tick[2])
        self.assertLess(per_tick[2], per_tick[4])
        # the other clips leave them at rest, still; a restored battle clip turns them as the source game does
        for slot in [s for s in (46, 50) if s not in self.recipe['battle_originals']['slots']]:
            frames = self.frames(slot)
            for bone in DRUMS:
                self.assertEqual(len({f[bone][5] for f in frames}), 1)

    def test_the_drums_are_straight_on_their_axes(self):
        # the spin axis is the bone's z axis; every ring of a drum lies round it
        for bone in DRUMS:
            v = np.array(self.model.tmd.obj_verts(self.rig[bone][0]))[:, :3].astype(float)
            radial = np.hypot(v[:, 0], v[:, 1])
            self.assertTrue(np.all(np.abs(v[:, 2]) < 60), bone)
            for ring in sorted(set(np.round(v[:, 2]))):
                r = radial[np.round(v[:, 2]) == ring]
                self.assertLess(r.max() - r.min(), 25, (bone, ring))

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
