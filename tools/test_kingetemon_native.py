"""KingEtemon (303) wears native Etemon's skeleton: its rig and field programs are Etemon's own, scaled to its body and paced to the native speeds."""
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
from tools.models.field_animations import native_hands

DONOR = 42
BONES = 27
SOLES = (22, 26)
ARMS = {9: (8, 1), 13: (12, -1)}     # hand bone: forearm bone, side (+x is the model's right)
BUFFER = 100352


class KingEtemonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('303-*.MMD'))
        tims = list(source.glob('303-*.TIM'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD1/ETEM.MMD'
        if not files or not tims or not native_path.exists():
            raise unittest.SkipTest('needs the imported 303 model (edit.py get 303) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['303']
        spec = importlib.util.spec_from_file_location('imported_species_303', 'content/models/imports/species.py')
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        cls.tmp = tempfile.mkdtemp(prefix='kingetemon-')
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        shutil.copy(files[0], base / '303.MMD')
        shutil.copy(tims[0], base / '303.TIM')
        imported.BASE_MODELS = str(base)
        path, cls.proof = imported.overlay(str(Path(cls.tmp) / 'species'), '303')
        cls.data = Path(path).read_bytes()
        cls.rig = cls.proof['generated_skeleton']
        cls.record = json.loads(next(Path('content/species').glob('303-*.json')).read_text())
        mmd.exe().add_type(9303, cls.rig)
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

    def test_rig_is_etemons_and_every_piece_is_bound_once(self):
        self.assertEqual([p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[DONOR]])
        self.assertEqual(len(self.rig), BONES)
        self.assertEqual((self.recipe['donor'], self.recipe['model']), (DONOR, 'CHDAT/MMD1/ETEM.MMD'))
        self.assertEqual(sorted(o for o, _ in self.rig if o >= 0), list(range(len(self.model.tmd.objects))))
        source = self.record['model']['skeleton']
        self.assertEqual(sorted(map(int, self.recipe['map'])), list(range(1, len(source))))
        # the cape has no Etemon bone: it rides the pelvis and the chest; the toes follow the foot, the crown the head
        self.assertEqual((self.recipe['map']['5'], self.recipe['map']['6']), (22, 22))
        self.assertEqual((self.recipe['map']['9'], self.recipe['map']['10']), (26, 26))
        self.assertEqual(self.recipe['map']['17'], 4)

    def test_idle_keeps_the_donors_clip_and_the_gaits_are_retimed(self):
        native, own = self.frames(0, self.native), self.frames(0)
        self.assertEqual(len(own), len(native))
        self.assertEqual(self.speed(own), 0)
        self.assertEqual([len(self.frames(s)) for s in (0, 2, 3, 4)], [17, 17, 21, 15])
        # the donor's own slots 27, 33, 35 and 36 are the programs the rows alias or repeat
        for slot, alias in ((2, 35), (3, 27), (4, 36)):
            self.assertEqual(self.model.anims.table[slot], self.model.anims.table[alias], slot)
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

    @staticmethod
    def turned(a, b):
        """Degrees between two bone poses' rotations (an Euler wrap is no jump)."""
        x, y = np.array(mmd.rot_matrix(*a[3:6])), np.array(mmd.rot_matrix(*b[3:6]))
        return float(np.degrees(np.arccos(np.clip((np.trace(y.T @ x) - 1) / 2, -1, 1))))

    def test_no_tick_jumps(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            steps = [max(self.turned(a, b) for a, b in zip(f, g)) for f, g in zip(frames, frames[1:])]
            self.assertLess(max(steps), 2.5*max(np.median(steps), 1), slot)

    def test_effect_points_and_bubble_sit_on_real_bones(self):
        patch = self.recipe['species_patch']
        self.assertTrue(0 <= patch['condition_bubble'][3] < BONES)
        for row in patch['effect_origins']:
            self.assertTrue(0 <= row[4] < BONES, row)

    def test_hands_trail_the_forearms_and_loops_close(self):
        spec = self.recipe['hands']
        # the run's follow-through is held down (per_slot 4): a loose fist, not a flapping one
        for slot, least in ((2, 15), (3, 15), (4, 10)):
            frames = self.frames(slot)
            for hand in map(int, spec['bones']):
                swing = max(self.turned(f[hand], frames[0][hand]) for f in frames)
                self.assertGreater(swing, least, (slot, hand))
                self.assertLess(self.turned(frames[0][hand], frames[-1][hand]), .5)

    def world(self, pose):
        q = [list(x) for x in pose]
        q[0] = [4096]*3 + [0]*6
        w = np.array(mmd.bone_matrices(self.model, q))
        for b in range(len(w)):
            w[b, :3, :3] /= np.linalg.norm(w[b, :3, :3], axis=0)
        return w

    def test_gloves_lie_along_the_hand_bones_palm_in(self):
        """Each glove's line runs down its hand bone's x with the slight droop, its flat side (palm) on the bone's
        `palm` axis: the hand-bone tests below then speak for the glove itself."""
        spec = self.recipe['hands']
        for hand in ARMS:
            v = np.array(self.model.tmd.obj_verts(self.rig[hand][0]), float)[:, :3]
            line = v.mean(0)/np.linalg.norm(v.mean(0))
            self.assertLess(np.degrees(np.arccos(line[0])), 15, hand)
            c = v - v.mean(0)
            thin = np.linalg.eigh(c.T @ c)[1][:, 0]
            self.assertGreater(abs(thin @ np.array(spec['palm'][str(hand)])), np.cos(np.radians(20)), hand)

    def hand_angles(self, pose):
        """Per hand: bend off the forearm line, and roll of the palm away from the body's middle, in degrees."""
        spec, w, out = self.recipe['hands'], self.world(pose), {}
        for hand, (forearm, side) in ARMS.items():
            fore, own = w[forearm, :3, :3], w[hand, :3, :3]
            line = fore[:, 0]
            bend = np.degrees(np.arccos(np.clip(own[:, 0] @ line, -1, 1)))
            medial = np.array([-side, 0, 0.]) - line*(-side*line[0])
            medial /= np.linalg.norm(medial)
            palm = own @ np.array(spec['palm'][str(hand)], float)
            palm = palm - line*(palm @ line)
            palm /= np.linalg.norm(palm)
            out[hand] = (bend, np.degrees(np.arctan2(np.cross(medial, palm) @ line, medial @ palm)))
        return out

    def test_hands_continue_the_forearms_palms_to_the_thighs(self):
        """No sideways hand (palm rolled off the thigh) and no hand folded far in, on any gait tick; no roll jump."""
        for slot in (2, 3, 4):
            angles = [self.hand_angles(p) for p in self.frames(slot)]
            for hand in ARMS:
                bends = [a[hand][0] for a in angles]
                rolls = [a[hand][1] for a in angles]
                self.assertLess(max(bends), 40, (slot, hand))
                self.assertLess(max(map(abs, rolls)), 30, (slot, hand))
                steps = [abs((b - a + 180) % 360 - 180) for a, b in zip(rolls, rolls[1:])]
                self.assertLess(max(steps), 18, (slot, hand))     # a twist flip would be 90 or more

    def test_hands_and_forearms_stay_out_of_the_legs_and_body(self):
        """No glove vertex inside a leg, foot, the cape or the body on any tick of the idles and gaits; a forearm grazes
        by two at most (the run's forearm meets the rising foot)."""
        mesh, bones = native_hands._Mesh(self.model, self.rig), self.recipe['hands']['clear']['bones']
        for slot in (0, 33, 2, 3, 4):
            for t, pose in enumerate(self.frames(slot)[:-1]):
                for hand, (forearm, _) in ARMS.items():
                    self.assertEqual(mesh.inside_count(pose, hand, bones), 0, (slot, t, hand))
                    self.assertLessEqual(mesh.inside_count(pose, forearm, bones), 2, (slot, t, forearm))

    def test_arms_do_not_splay_outward(self):
        """Sideways lean of each upper arm and forearm against the line of the shoulders, per tick."""
        for slot in (2, 3, 4):
            for pose in self.frames(slot)[:-1]:
                q = [list(x) for x in pose]
                q[0] = [4096]*3 + [0]*6
                w = np.array(mmd.bone_matrices(self.model, q))
                axis = w[7, :3, 3] - w[11, :3, 3]
                axis[1] = 0
                axis /= np.linalg.norm(axis)
                for side, (shoulder, elbow, hand) in ((1, (7, 8, 9)), (-1, (11, 12, 13))):
                    for a, b, limit in ((shoulder, elbow, 30), (elbow, hand, 20)):
                        v = w[b, :3, 3] - w[a, :3, 3]
                        lean = side*np.degrees(np.arcsin(v @ axis/np.linalg.norm(v)))
                        self.assertLess(lean, limit, (slot, a))

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
            # the native sole runs these bounds too: the swinging foot lifts, the stance foot grounds
            self.assertLessEqual(max(low), 60, slot)
            self.assertGreaterEqual(min(low), -25, slot)


if __name__ == '__main__':
    unittest.main()
