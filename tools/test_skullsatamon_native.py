"""SkullSatamon (314) wears native Ogremon's skeleton: its rig and field programs are Ogremon's own, scaled to its body."""
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

DONOR = 34
BONES = 18
SOLES = (12, 13, 14, 15, 16, 17)     # every leg bone: the lowest point of a leg, whichever part touches
BUFFER = 100352


class SkullSatamonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('314-*.MMD'))
        tims = list(source.glob('314-*.TIM'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD1/OGRE.MMD'
        if not files or not tims or not native_path.exists():
            raise unittest.SkipTest('needs the imported 314 model (edit.py get 314) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['314']
        spec = importlib.util.spec_from_file_location('imported_species_314', 'content/models/imports/species.py')
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        cls.tmp = tempfile.mkdtemp(prefix='skullsatamon-')
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        shutil.copy(files[0], base / '314.MMD')
        shutil.copy(tims[0], base / '314.TIM')
        imported.BASE_MODELS = str(base)
        path, cls.proof = imported.overlay(str(Path(cls.tmp) / 'species'), '314')
        cls.data = Path(path).read_bytes()
        cls.rig = cls.proof['generated_skeleton']
        cls.record = json.loads(next(Path('content/species').glob('314-*.json')).read_text())
        mmd.exe().add_type(9314, cls.rig)
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

    def test_rig_is_centarumons_and_every_piece_is_bound_once(self):
        self.assertEqual([p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[DONOR]])
        self.assertEqual(len(self.rig), BONES)
        self.assertEqual((self.recipe['donor'], self.recipe['model']), (DONOR, 'CHDAT/MMD1/OGRE.MMD'))
        self.assertEqual(sorted(o for o, _ in self.rig if o >= 0), list(range(len(self.model.tmd.objects))))
        source = self.record['model']['skeleton']
        self.assertEqual(sorted(map(int, self.recipe['map'])), list(range(1, len(source))))
        # Ogremon has no wings: both wings ride its mane bone (4), which lags behind the head, and the hip piece rides the root
        m = self.recipe['map']
        self.assertEqual([m['11'], m['12'], m['13']], [4, 4, 1])
        self.assertEqual([m[k] for k in ('14', '15', '16', '17')], [12, 13, 14, 14])
        self.assertEqual([m[k] for k in ('18', '19', '20', '21')], [15, 16, 17, 17])

    def test_idle_and_walk_are_the_donors_scaled_programs(self):
        scale = self.recipe['scale']
        for slot in (0, 2):
            native = self.frames(slot, self.native)
            own = self.frames(slot)
            self.assertEqual(len(own), len(native), slot)
            if slot == 0:
                self.assertAlmostEqual(self.speed(own), self.speed(native)*scale, delta=.3)
            else:   # the chibi stage shortens the stride of the walk to its shorter legs
                self.assertLessEqual(self.speed(own), self.speed(native)*scale + .3)

    def test_slots_and_ticks(self):
        self.assertEqual([len(self.frames(s)) for s in (0, 2, 3, 4)], [17, 23, 25, 21])
        for slot in list(range(46, 46 + len(self.record['techniques']))) + [self.record['partner']['training']['animation']]:
            self.assertIsNotNone(self.model.anims.table[slot], slot)
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
            for bone in range(BONES):
                np.testing.assert_allclose(mmd.rot_matrix(*frames[0][bone][3:6]), mmd.rot_matrix(*frames[-1][bone][3:6]),
                                           atol=.01, err_msg=str(bone))

    def test_no_tick_jumps(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            steps = [max(abs(a - b) for pa, pb in zip(f, g) for a, b in zip(pa[3:6], pb[3:6])) for f, g in zip(frames, frames[1:])]
            if slot == 4:
                steps = steps[:-1]      # the donor's own run closes its loop through a gimbal pose of the chest (the same raw step in its file)
            self.assertLess(max(steps), 2.5*max(np.median(steps), 1), slot)

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
                p[0] = [4096]*3 + p[0][3:6] + [0, p[0][7], 0]       # the root keeps its own height: the floor is where the carrier puts it
                w = np.array(mmd.bone_matrices(self.model, p))
                ys = []
                for b in SOLES:
                    v = np.array(self.model.tmd.obj_verts(self.rig[b][0]))[:, :3]
                    ys.append((v @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max())
                low.append(max(ys))
            # the donor's own sole runs the same bounds on its own mesh
            self.assertLessEqual(max(low), 60, slot)
            self.assertGreaterEqual(min(low), -60, slot)    # the bones alone, without the carrier's own height: the swing and the stooped walk read higher


if __name__ == '__main__':
    unittest.main()
