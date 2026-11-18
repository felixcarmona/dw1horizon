"""Deltamon (292) wears native Tyrannomon's skeleton and field programs, with its own pace for the tired walk and the run."""
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
from tools.models.field_animations import native_jaws

DONOR = 8
BONES = 27
BUFFER = 100352


def turned(pose, rest):
    """Degrees between two bone poses' rotations."""
    a, b = np.array(mmd.rot_matrix(*pose[3:6])), np.array(mmd.rot_matrix(*rest[3:6]))
    return float(np.degrees(np.arccos(np.clip((np.trace(b.T @ a) - 1) / 2, -1, 1))))


class DeltamonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('292-*.MMD'))
        tims = list(source.glob('292-*.TIM'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD0/TYRA.MMD'
        if not files or not tims or not native_path.exists():
            raise unittest.SkipTest('needs the imported 292 model (edit.py get 292) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['292']
        spec = importlib.util.spec_from_file_location('imported_species_292', 'content/models/imports/species.py')
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        cls.tmp = tempfile.mkdtemp(prefix='deltamon-')
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        shutil.copy(files[0], base / '292.MMD')
        shutil.copy(tims[0], base / '292.TIM')
        imported.BASE_MODELS = str(base)
        path, cls.proof = imported.overlay(str(Path(cls.tmp) / 'species'), '292')
        cls.data = Path(path).read_bytes()
        cls.rig = cls.proof['generated_skeleton']
        cls.record = json.loads(next(Path('content/species').glob('292-*.json')).read_text())
        mmd.exe().add_type(9292, cls.rig)
        cls.model = mmd.MMD.parse(cls.data, len(cls.rig))
        cls.model.type = DONOR
        cls.native = mmd.MMD.load(str(native_path), DONOR)
        # the same binding with every jaw shut, to tell the jaws' own motion from the arms'
        shut = json.loads(json.dumps(cls.recipe_all()))
        for curves in shut['292']['jaws']['curves'].values():
            for bone in curves:
                curves[bone] = {'peak': 0, 'cycles': 1, 'offset': 0}
        manifest = Path(cls.tmp) / 'shut.json'
        manifest.write_text(json.dumps(shut))
        real, binding.MANIFEST = binding.MANIFEST, manifest
        try:
            path, _ = imported.overlay(str(Path(cls.tmp) / 'shut'), '292')
        finally:
            binding.MANIFEST = real
        cls.shut = mmd.MMD.parse(Path(path).read_bytes(), len(cls.rig))
        cls.shut.type = DONOR

    @classmethod
    def recipe_all(cls):
        return json.loads(binding.MANIFEST.read_text())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.model, BONES, slot)[0]

    def speed(self, slot):
        frames = self.frames(slot)
        return abs(frames[-1][0][8] - frames[0][0][8])/(len(frames) - 1)

    def test_rig_is_tyrannomons_and_every_piece_is_bound_once(self):
        self.assertEqual([p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[DONOR]])
        self.assertEqual(len(self.rig), BONES)
        self.assertEqual((self.recipe['donor'], self.recipe['model']), (DONOR, 'CHDAT/MMD0/TYRA.MMD'))
        self.assertEqual(sorted(o for o, _ in self.rig if o >= 0), list(range(len(self.model.tmd.objects))))
        source = self.record['model']['skeleton']
        self.assertEqual(sorted(map(int, self.recipe['map'])), list(range(1, len(source))))
        # the two jaws that open on a hand ride on that hand's finger bones, the main jaw on the head's
        self.assertEqual([self.recipe['map'][k] for k in ('17', '21', '24')], [4, 8, 14])

    def test_slots_and_ticks(self):
        self.assertEqual([len(self.frames(s)) - 1 for s in (0, 2, 3, 4)], [20, 22, 30, 24])
        self.assertIn(33, self.recipe['battle_originals']['slots'])     # the battle idle is the source's own
        self.assertEqual(self.model.anims.table[36], self.model.anims.table[4])
        for slot in list(range(46, 46 + len(self.record['techniques']))) + [60]:
            self.assertIsNotNone(self.model.anims.table[slot], slot)
        self.assertEqual(len(self.recipe['technique_slots']), len(self.record['techniques']))

    def test_gait_speeds_are_native_and_ordered(self):
        walk, tired, run = (self.speed(s) for s in (2, 3, 4))
        self.assertTrue(15 <= walk <= 31, walk)
        self.assertTrue(10 <= tired <= 20, tired)
        self.assertTrue(35 <= run <= 52, run)
        self.assertLess(tired, walk)
        self.assertLess(walk, run)

    def vertex_steps(self, slot):
        """Largest per-tick displacement of any vertex in body space, per tick, loop seam included."""
        frames = self.frames(slot)
        clouds = []
        for pose in frames:
            p = [list(x) for x in pose]
            p[0] = [4096]*3 + [0]*6
            w = np.array(mmd.bone_matrices(self.model, p))
            clouds.append(np.concatenate([np.array(self.model.tmd.obj_verts(o))[:, :3] @ w[b, :3, :3].T + w[b, :3, 3]
                                          for b, (o, _) in enumerate(self.rig) if o >= 0]))
        return [np.linalg.norm(clouds[(t + 1) % (len(frames) - 1)] - clouds[t], axis=1).max() for t in range(len(frames) - 1)]

    def test_root_speed_is_constant_and_no_tick_pops(self):
        for slot in (2, 3, 4):
            frames = self.frames(slot)
            steps = [abs(b[0][8] - a[0][8]) for a, b in zip(frames, frames[1:])]
            if slot != 2:        # the walk keeps the donor's own uneven pace through a stride
                self.assertLess(max(steps), 1.05*min(steps) + 1, slot)
            jumps = self.vertex_steps(slot)
            # no pop beyond the donor's own: its walk swings a foot through the stride in two ticks (a ratio of 3.2)
            self.assertLess(max(jumps)/np.median(jumps), max(2.5, {2: 3.6}.get(slot, 0)), slot)

    def test_loops_close(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            for bone in range(BONES):
                np.testing.assert_allclose(mmd.rot_matrix(*frames[0][bone][3:6]), mmd.rot_matrix(*frames[-1][bone][3:6]),
                                           atol=.01, err_msg=str(bone))

    def low_points(self, slot, model, rig, scale, highest=False):
        low = []
        for pose in self.frames(slot, model)[:-1]:
            p = [list(x) for x in pose]
            p[0] = [4096]*3 + p[0][3:6] + [0, 0, 0]
            w = np.array(mmd.bone_matrices(model, p))
            ys = []
            for b, (o, _) in enumerate(rig):
                if o >= 0:
                    v = np.array(model.tmd.obj_verts(o))[:, :3]
                    ys.append((v @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max())
            low.append(max(ys))
        return min(low) if highest else max(low)

    def test_nothing_sinks_further_than_the_donor_does(self):
        native_rig = mmd.exe().skeleton[DONOR]
        scale = self.recipe['scale']
        for slot, margin in ((2, 15), (3, 15), (4, 25)):
            donor = self.low_points(slot, self.native, native_rig, 1)
            ours = self.low_points(slot, self.model, self.rig, scale)
            self.assertLessEqual(ours, donor*scale + margin, (slot, ours, donor))
            self.assertGreaterEqual(self.low_points(slot, self.model, self.rig, scale, highest=True),
                                    self.low_points(slot, self.native, native_rig, 1, highest=True)*scale - 5, slot)
        self.assertLessEqual(self.low_points(0, self.model, self.rig, scale), 40)   # the idle tail tips and the skull's jaw dropping open next to the floor

    def test_head_jaw_is_calm_and_hand_jaws_replay_the_source(self):
        curves = self.recipe['jaws']['curves']
        for slot, per_bone in curves.items():
            ticks = len(self.frames(int(slot))) - 1
            for bone, curve in per_bone.items():
                if 'replay' in curve:       # the hand heads play the source's own jaw turns, unscaled (13-14 degrees, one slow hump)
                    self.assertEqual(curve, {'replay': 1.0}, (slot, bone))
                    continue
                angles = [native_jaws.opening(curve, t / ticks) for t in range(ticks + 1)]
                self.assertLess(max(abs(b - a) for a, b in zip(angles, angles[1:])), 3.2, (slot, bone))
                self.assertLessEqual(curve['cycles'] / ticks, 1 / 12, (slot, bone))
                self.assertAlmostEqual(angles[0], angles[-1], 6)
                self.assertLessEqual(max(angles) - min(angles), 24, (slot, bone))
        self.assertLessEqual(curves['3']['17']['peak'], 4)
        for slot in ('0', '2', '4'):
            self.assertTrue(12 <= curves[slot]['17']['peak'] <= 20, slot)
        # and the posed head jaw really opens, smoothly, in every clip
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            angles = [turned(f[4], frames[0][4]) for f in frames]
            self.assertGreater(max(angles), 3 if slot == 3 else 10, slot)
            self.assertLess(max(abs(b - a) for a, b in zip(angles, angles[1:])), 4.0, slot)

    def jaw_motion(self, slot, bone):
        """[(world axis of the jaw's turn against the same clip with its jaws shut, degrees, lowest-point move)] per tick"""
        out = []
        self.model.type = self.shut.type = 9292       # the generated skeleton (scaled), not the donor's
        try:
            frames = list(zip(self.frames(slot), self.frames(slot, self.shut)))
            return self.jaw_turns(frames, bone)
        finally:
            self.model.type = self.shut.type = DONOR

    def jaw_turns(self, frames, bone):
        out = []
        for pose, shut in frames:
            wa, wb = [np.array(mmd.bone_matrices(m, [[4096]*3 + [0]*6] + [list(x) for x in p[1:]]))
                      for m, p in ((self.model, pose), (self.shut, shut))]
            turn = wa[bone, :3, :3] @ np.linalg.inv(wb[bone, :3, :3])
            degrees = float(np.degrees(np.arccos(np.clip((np.trace(turn) - 1) / 2, -1, 1))))
            axis = np.array([turn[2, 1] - turn[1, 2], turn[0, 2] - turn[2, 0], turn[1, 0] - turn[0, 1]])
            axis = axis / max(np.linalg.norm(axis), 1e-9)
            centre = []
            for m, w in ((self.model, wa), (self.shut, wb)):
                v = np.array(m.tmd.obj_verts(self.rig[bone][0]))[:, :3]
                world = v @ w[bone, :3, :3].T + w[bone, :3, 3]
                centre.append(np.array([0, world[:, 1].max(), 0]))       # the lowest point of the jaw
            out.append((axis, degrees, centre[0] - centre[1]))
        return out

    def test_jaws_open_about_a_horizontal_axis_and_drop(self):
        # the opening is a vertical one: the turn is about a horizontal axis (never a swing about the vertical), and the
        # head's and the skull's jaw centres go down (y is down) when open; the tired walk and the run roll the hand heads on their drooping or pumping arms
        limit = {0: 0.35, 2: 0.35, 3: 0.6, 4: 0.6}
        for slot in (0, 2, 3, 4):
            for bone in (4, 8, 14):
                motion = [m for m in self.jaw_motion(slot, bone) if m[1] > 4]
                self.assertTrue(motion, (slot, bone))
                self.assertLess(max(abs(m[0][1]) for m in motion), 0.2 if bone == 4 else limit[slot], (slot, bone))
                if True:
                    widest = max(motion, key=lambda m: m[1])
                    self.assertGreater(widest[2][1], 3, (slot, bone))

    def test_effect_points_and_bubble_sit_on_real_bones(self):
        patch = self.recipe['species_patch']
        self.assertTrue(0 <= patch['condition_bubble'][3] < BONES)
        for row in patch['effect_origins']:
            self.assertTrue(0 <= row[0] < len(self.record['model']['skeleton']) and 0 <= row[4] < BONES, row)

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


if __name__ == '__main__':
    unittest.main()
