"""MetalTyrannomon (260) moves exactly like native Tyrannomon: its rig and every field and care program are Tyrannomon's own."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import native_binding as binding

DONOR = 8
SPREAD = (5, 6, 11, 12)


class MetalTyrannomonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('260-*.MMD'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD0/TYRA.MMD'
        if not files or not native_path.exists():
            raise unittest.SkipTest('needs the imported 260 model (edit.py get 260) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['260']
        cls.record = json.loads(next(Path('content/species').glob('260-*.json')).read_text())
        cls.data, cls.proof = binding.bind(files[0].read_bytes(), cls.record['model']['skeleton'], cls.recipe)
        cls.rig = cls.proof['generated_skeleton']
        mmd.exe().add_type(9260, cls.rig)
        cls.model = mmd.MMD.parse(cls.data, len(cls.rig))
        cls.model.type = DONOR
        cls.native = mmd.MMD.load(str(native_path), DONOR)

    @staticmethod
    def program(model, slot):
        clip = copy.deepcopy(model.anims.anims[model.anims.table[slot]])
        clip.instrs = [i for i in clip.instrs if i['op'] != 'tex']
        clip.tail = b''
        for bone in SPREAD:
            # the arms' joints are moved apart to the heavy body: only those start translations differ
            clip.pose[bone - 1][-3:] = [0, 0, 0]
        return clip.build()

    def test_rig_is_tyrannomons(self):
        self.assertEqual([p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[DONOR]])
        self.assertEqual(len(self.rig), 27)
        self.assertEqual((self.recipe['donor'], self.recipe['scale'], self.recipe['mesh_scale']), (DONOR, 1.0, 1.0))
        self.assertEqual(self.recipe['model'], 'CHDAT/MMD0/TYRA.MMD')

    def test_every_program_below_the_techniques_is_tyrannomons_unchanged(self):
        for slot, index in enumerate(self.native.anims.table[:46]):
            if index is None or slot == 4:  # the run's arms are re-posed below
                continue
            if slot in self.recipe['battle_originals']['slots']:  # the source game's own clip, see test_battle_originals
                continue
            with self.subTest(slot=slot):
                self.assertEqual(self.program(self.model, slot), self.program(self.native, slot))

    def test_field_clips_play_tyrannomons_frames(self):
        for slot in (0, 1, 2, 3, 4):
            with self.subTest(slot=slot):
                before, loop, _ = animsheet.slot_frames(self.native, 27, slot)
                after, new_loop, _ = animsheet.slot_frames(self.model, 27, slot)
                self.assertEqual((len(after), new_loop), (len(before), loop))
                for frame_a, frame_b in zip(after, before):
                    for bone, (x, y) in enumerate(zip(frame_a, frame_b)):
                        if slot == 4 and bone in SPREAD:  # the run's arms are re-posed (test_run_arms_...)
                            continue
                        # equal everywhere but the translation of the joints moved apart on the arms
                        self.assertEqual(x if bone not in SPREAD else x[:-3], y if bone not in SPREAD else y[:-3])
        self.assertEqual([len(animsheet.slot_frames(self.model, 27, s)[0]) for s in (0, 2, 3, 4)], [21, 23, 27, 21])

    def test_techniques_play_tyrannomons_clips_of_their_kind(self):
        moves = self.record['techniques']
        slots = self.recipe['technique_slots']
        self.assertEqual(len(slots), len(moves))
        tyrannomon = json.loads(next(Path('content/species').glob('8-tyrannomon.json')).read_text())['techniques']
        for position, move in enumerate(moves):
            if move in tyrannomon:
                # a move Tyrannomon has plays Tyrannomon's own clip for it (its list position is its slot minus 46)
                self.assertEqual(slots[position], 46 + tyrannomon.index(move), move)
            with self.subTest(move=move):
                self.assertIn(slots[position], range(46, 46 + len(tyrannomon)))
                self.assertEqual(self.program(self.model, 46 + position), self.program(self.native, slots[position]))

    def test_training_clip_is_tyrannomons_training_clip(self):
        training = self.recipe['species_patch']['partner']['training']
        self.assertEqual(training, {'animation': 46 + len(self.record['techniques']), 'hit_tick': 10})
        self.assertEqual(self.program(self.model, training['animation']), self.program(self.native, 46))

    def test_condition_bubble_and_effect_points_ride_tyrannomons_bones(self):
        patch = self.recipe['species_patch']
        self.assertEqual(patch['condition_bubble'][3], 3)
        for row in patch['effect_origins']:
            self.assertGreaterEqual(self.rig[row[4]][0], 0, row)
        self.assertEqual(len(patch['effect_origins']), len(self.record['effect_origins']))

    def test_battle_originals(self):
        # the source game's own battle clips, retargeted onto the donor rig; the idle loops at its own speed, the one-shot
        # clip is as long as the donor's clip it replaces, since technique effects are timed to it
        made = self.proof['battle_originals']
        self.assertEqual(sorted(int(s) for s in made), self.recipe['battle_originals']['slots'])
        for slot, row in made.items():
            if int(slot) not in (33, 34):
                self.assertEqual(row['frames'], row['donor_frames'])

    def test_resident_animation_buffer(self):
        storage = motionstorage.require(self.data, len(self.rig))
        self.assertTrue(storage['fits'])
        self.assertLessEqual(storage['resident_bytes'], storage['resident_limit'])
        self.assertEqual(storage['resident_limit'], 100352)
        self.assertEqual(storage['resident_bytes'], 81616)

    def test_every_piece_is_bound_once_and_the_feet_stand_on_the_floor(self):
        objects = sorted(o for o, _ in self.rig if o >= 0)
        self.assertEqual(objects, list(range(len(self.model.tmd.objects))))
        # 23 source pieces: the head carries the head and the pipe at its side; each arm's forearm bone carries the
        # forearm and its three claws as one rigid piece; the pelvis, both hands and the claw bones stay empty
        self.assertEqual(sorted(map(int, self.recipe['map'])), list(range(1, 24)))
        self.assertEqual([b for b, (o, _) in enumerate(self.rig) if o < 0], [0, 1, 7, 8, 9, 10, 13, 14, 15, 16, 17])
        self.assertEqual(sorted(set(self.recipe['map'].values())),
                         [b for b, (o, _) in enumerate(self.rig) if o >= 0])
        pose = animsheet.slot_frames(self.model, 27, 0)[0][0]
        pose[0] = [4096]*3 + [0]*6
        world = mmd.bone_matrices(self.model, pose)
        lowest = max(world[b][1][0]*v[0] + world[b][1][1]*v[1] + world[b][1][2]*v[2] + world[b][1][3]
                     for b, (o, _) in enumerate(self.rig) if o >= 0 and b in (21, 22, 23, 24, 25, 26) for v in self.model.tmd.obj_verts(o))
        self.assertLess(abs(lowest), 30)

    def test_claws_move_with_the_forearm_and_never_turn_at_a_wrist(self):
        mapping = {int(k): v for k, v in self.recipe['map'].items()}
        # source claws (15-17, 20-22) hang from the forearm piece (14, 19): the same bone, so the wrist cannot bend
        for forearm, claws in ((14, (15, 16, 17)), (19, (20, 21, 22))):
            for claw in claws:
                self.assertEqual(mapping[claw], mapping[forearm])
                self.assertEqual(self.recipe['pieces'][str(claw)]['anchor'], self.recipe['pieces'][str(forearm)]['anchor'])
                self.assertEqual(self.recipe['pieces'][str(claw)]['swing'], self.recipe['pieces'][str(forearm)]['swing'])
        self.assertEqual(set(self.recipe['spread']), {str(b) for b in SPREAD})
        # the two arms are mirror images of each other at rest
        pose = animsheet.slot_frames(self.model, 27, 0)[0][0]
        pose[0] = [4096]*3 + [0]*6
        world = mmd.bone_matrices(self.model, pose)
        for left, right in ((11, 5), (12, 6)):
            a = [world[left][r][3] for r in range(3)]
            b = [world[right][r][3] for r in range(3)]
            self.assertAlmostEqual(a[0], -b[0], delta=3)
            self.assertAlmostEqual(a[1], b[1], delta=3)
            self.assertAlmostEqual(a[2], b[2], delta=3)

    def _arm_world(self, slot):
        """Per tick of the loop: the forearm pieces' vertices (claws included) in the world, with the body's own
        position removed, for the right and the left arm."""
        out = []
        for pose in animsheet.slot_frames(self.model, 27, slot)[0][:-1]:
            pose = [list(p) for p in pose]
            world = np.array(mmd.bone_matrices(self.model, pose))
            row = {}
            for side, b in (('R', 6), ('L', 12)):
                points = np.array(self.model.tmd.obj_verts(self.rig[b][0]))[:, :3] @ world[b, :3, :3].T + world[b, :3, 3]
                row[side] = points - world[1, :3, 3]
                row[side + 'y'] = points[:, 1].max()
            row['foot'] = world[23, 2, 3] - world[1, 2, 3]
            out.append(row)
        return out

    def test_run_arms_pump_out_from_the_body_and_the_claws_clear_the_floor(self):
        before = self._arm_world(0)
        run = self._arm_world(4)
        for side in 'RL':
            centre = np.array([r[side].mean(0) for r in run])
            # a real pump: the forearm goes back and forth by well over the donor's 51 units
            self.assertGreaterEqual(np.ptp(centre[:, 2]), 130, side)
            # and the arm is held out at least as far as it hangs at rest (the donor's run closed it to 129)
            self.assertGreaterEqual(abs(centre[:, 0]).mean(), abs(np.mean([r[side].mean(0)[0] for r in before])) - 10)
            # no claw tip below the floor at any tick
            self.assertLess(max(r[side + 'y'] for r in run), -20, side)
        # the right arm goes forward with the left foot: opposite to its own side's foot
        right = np.array([r['R'].mean(0)[2] for r in run])
        foot = np.array([r['foot'] for r in run])
        self.assertLess(np.corrcoef(right, foot)[0, 1], -.6)

    def test_run_arms_loop_closes_and_only_the_arms_changed(self):
        frames, loop, _ = animsheet.slot_frames(self.model, 27, 4)
        for bone in range(27):
            # the same rotation, whatever branch of the angles it is written in
            np.testing.assert_allclose(mmd.rot_matrix(*frames[0][bone][3:6]), mmd.rot_matrix(*frames[-1][bone][3:6]),
                                       atol=.01, err_msg=str(bone))
        donor = animsheet.slot_frames(self.native, 27, 4)[0]
        for a, b in zip(frames, donor):
            for bone in set(range(27)) - set(SPREAD):
                self.assertEqual(a[bone], b[bone], bone)

    @staticmethod
    def _inside(points, triangles, probes):
        """Parity ray casting along three skew directions, majority vote: which probes lie inside the piece."""
        points = np.array(points, float)
        probes = np.array(probes, float)
        a, b, c = (points[[t[i] for t in triangles]] for i in range(3))
        e1, e2 = b - a, c - a
        votes = np.zeros(len(probes), int)
        for d in (np.array([1, 0.013, 0.007]), np.array([0.011, 1, 0.017]), np.array([0.009, 0.019, 1])):
            h = np.cross(d, e2)
            det = (e1*h).sum(1)
            ok = abs(det) > 1e-9
            f = np.where(ok, 1/np.where(ok, det, 1), 0)
            s = probes[:, None, :] - a[None]
            u = f[None]*(s*h[None]).sum(2)
            q = np.cross(s, e1[None])
            w = f[None]*(q*d).sum(2)
            t = f[None]*(q*e2[None]).sum(2)
            votes += (((u >= 0) & (u <= 1) & (w >= 0) & (u+w <= 1) & (t > 0) & ok[None]).sum(1) % 2)
        return votes >= 2

    def test_arms_stay_out_of_the_torso_and_head(self):
        # vertices of the upper arm and forearm (48 in all, the claws are 24 more) inside the torso or head
        # while the field clips play: a few at most, from 11-13 with the claws on the wrist
        for slot in (0, 2, 3, 4):
            frames = animsheet.slot_frames(self.model, 27, slot)[0]
            for tick in range(0, len(frames), 2 if slot == 4 else 4):
                pose = [list(p) for p in frames[tick]]
                world = np.array(mmd.bone_matrices(self.model, pose))
                placed = {b: np.array(self.model.tmd.obj_verts(o))[:, :3] @ world[b, :3, :3].T + world[b, :3, 3]
                          for b, (o, _) in enumerate(self.rig) if o >= 0}
                for body in (2, 3):
                    triangles = []
                    for prim in self.model.tmd.objects[self.rig[body][0]].prims:
                        v = prim.decode()['verts']
                        triangles += [v[:3]] if len(v) == 3 else [[v[0], v[1], v[2]], [v[1], v[3], v[2]]]
                    for arm in ((11, 12), (5, 6)):
                        probes = np.concatenate([placed[b] for b in arm])
                        count = int(self._inside(placed[body], triangles, probes).sum())
                        self.assertLessEqual(count, 8, (slot, tick, body, arm))


if __name__ == '__main__':
    unittest.main()
