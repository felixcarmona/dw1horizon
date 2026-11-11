"""Wizardmon (241) moves like native Angemon: its rig and body programs are Angemon's own; cape and hair follow.

The cases are parameterised by SPECIES and BUILDER, so test_sorcermon_native.py runs them all on Sorcermon too."""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import native_binding as binding
from tools.models.field_animations import wizardmon_native

FIELD = [0, 1, 2, 3, 4]
STAFF = 9  # Angemon's staff hand
TYPE = 941  # a spare type id, so Angemon's own skeleton (type 20) stays as it is


class WizardmonNative(unittest.TestCase):
    SPECIES = 241
    BUILDER = wizardmon_native

    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob(f'{cls.SPECIES}-*.MMD'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD0/ANGE.MMD'
        if not files or not native_path.exists():
            raise unittest.SkipTest(f'needs the imported {cls.SPECIES} model (edit.py get {cls.SPECIES}) and the player DW1 extraction')
        cls.files = files
        cls.recipe = json.loads(binding.MANIFEST.read_text())[str(cls.SPECIES)]
        cls.record = json.loads(next(Path('content/species').glob(f'{cls.SPECIES}-*.json')).read_text())
        cls.data, cls.proof = cls.BUILDER.build(files[0].read_bytes(), cls.record['model']['skeleton'])
        cls.rig = cls.proof['generated_skeleton']
        cls.model = mmd.MMD.parse(cls.data, len(cls.rig))
        mmd.exe().add_type(TYPE, cls.rig)
        cls.model.type = TYPE
        cls.native = mmd.MMD.load(str(native_path), 20)

    def test_rig_is_angemons(self):
        self.assertEqual([p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[20]])
        self.assertEqual(len(self.rig), 26)
        self.assertEqual((self.recipe['donor'], self.recipe['scale']), (20, 1.0))

    def test_field_slots_play_angemons_programs(self):
        spread = binding.spread_offsets(self.recipe, self.native)
        body = [b for b in range(26) if b not in self.BUILDER.FOLLOWERS and b not in self.BUILDER.ARMS_OUT]
        for slot in FIELD:
            with self.subTest(slot=slot):
                before, loop, _ = animsheet.slot_frames(self.native, 26, slot)
                after, new_loop, _ = animsheet.slot_frames(self.model, 26, slot)
                self.assertEqual((len(after), new_loop), (len(before), loop))
                # the root travels exactly as Angemon's: same speed, same cadence
                self.assertEqual([f[0] for f in after], [f[0] for f in before])
                for old, new in zip(before, after):
                    for bone in body:
                        expected = list(old[bone])
                        if bone in spread:
                            expected[6:9] = [v + o for v, o in zip(expected[6:9], spread[bone])]
                        self.assertEqual(list(new[bone]), expected)

    def test_cape_and_hair_follow_without_flapping(self):
        """Angemon's wing beat is gone from the follower bones: the cape swings no more than the chest leads it."""
        for slot in FIELD:
            frames, _, _ = animsheet.slot_frames(self.model, 26, slot)
            for bone in self.BUILDER.FOLLOWERS:
                for axis in range(3, 6):
                    values = [f[bone][axis] for f in frames]
                    self.assertLess(max(values) - min(values), 1100, (slot, bone, axis))

    def test_endless_loops_close_on_their_first_pose(self):
        """The cape and hair followers end each endless loop on the pose it began from, so repeated passes do not
        creep: the last tick equals the first on those bones (Angemon's own bones keep their own programs) and ten passes of
        the engine's player end where they began."""
        import numpy as np
        for slot, index in enumerate(self.model.anims.table):
            if index is None:
                continue
            frames, loop, _ = animsheet.slot_frames(self.model, 26, slot)
            if loop is None:
                continue
            with self.subTest(slot=slot):
                self.assertEqual([frames[-1][b] for b in sorted(self.BUILDER.FOLLOWERS)],
                                 [frames[loop][b] for b in sorted(self.BUILDER.FOLLOWERS)])
                player = mmd.AnimPlayer(self.model.anims.anims[index], 26, slot)
                poses = []
                for _ in range((len(frames) - 1 - loop) * 10 + loop + 1):
                    player.tick()
                    poses.append(np.array([list(v) for v in player.pose], float))
                follow = sorted(self.BUILDER.FOLLOWERS)
                self.assertLessEqual(np.abs(poses[-1][follow, 3:6] - poses[loop][follow, 3:6]).max(), 2)

    def test_staff_rides_the_staff_hand(self):
        self.assertEqual(self.recipe['map']['10'], STAFF)
        self.assertGreaterEqual(self.rig[STAFF][0], 0)

    def test_soles_meet_the_ground_at_rest(self):
        frames, _, _ = animsheet.slot_frames(self.model, 26, 0)
        for pose in frames:
            world = mmd.bone_matrices(self.model, [list(v) for v in pose])
            lowest = max(sum(world[b][1][i] * v[i] for i in range(3)) + world[b][1][3]
                         for b in (21, 24) for v in self.model.tmd.obj_verts(self.rig[b][0]))
            self.assertLessEqual(abs(lowest), 3)

    def test_training_clip_is_angemons_training_clip(self):
        self.assertEqual(self.record['partner']['training'], {'animation': 57, 'hit_tick': 14})
        before, _, _ = animsheet.slot_frames(self.native, 26, 46)
        after, _, _ = animsheet.slot_frames(self.model, 26, 57)
        self.assertEqual(len(after), len(before))
        self.assertEqual([[f[b][:6] for b in (0, 2, 3, 9)] for f in after], [[f[b][:6] for b in (0, 2, 3, 9)] for f in before])

    def test_effect_points_stay_on_the_rig(self):
        patch = self.recipe['species_patch']
        for origin in patch['effect_origins']:
            self.assertLess(origin[4], 26)
            self.assertGreaterEqual(self.rig[origin[4]][0], 0)
        self.assertLess(patch['condition_bubble'][3], 26)

    def test_followers_keep_every_sound_and_loop(self):
        """The follower pass re-encodes every program: sounds stay on their frames, endless loops stay as they are and
        a counted loop is played out in full (same length on screen)."""
        bound, _ = binding.build(Path(self.files[0]).read_bytes(), self.record['model']['skeleton'])
        before = mmd.MMD.parse(bound, len(self.rig))
        before.type = TYPE
        self.assertEqual(before.anims.table, self.model.anims.table)

        def events(animation, counted):
            return [i for i in animation.instrs if i['op'] not in ('key', 'tex')
                    and not (counted and i['op'] in ('loop_start', 'loop_end'))]
        for slot, index in enumerate(before.anims.table):
            if index is None:
                continue
            old, new = before.anims.anims[index], self.model.anims.anims[index]
            counted = any(i['op'] == 'loop_start' and i['count'] != 255 for i in old.instrs)
            self.assertEqual(events(new, counted), events(old, counted), slot)
            self.assertEqual(len(animsheet.slot_frames(self.model, 26, slot)[0]),
                             len(animsheet.slot_frames(before, 26, slot)[0]), slot)

    def surface(self, bone):
        """Points spread over every triangle of the piece on `bone`, in the bone's frame."""
        import numpy as np
        obj = self.model.tmd.objects[self.rig[bone][0]]
        verts = np.array([v[:3] for v in self.model.tmd.obj_verts(self.rig[bone][0])], float)
        tris = []
        for prim in obj.prims:
            v = prim.decode()['verts']
            if len(v) >= 3:
                tris.append(v[:3])
            if len(v) == 4:
                tris.append([v[1], v[3], v[2]])
        weights = np.array([(u/4, w/4, (4-u-w)/4) for u in range(5) for w in range(5-u)])
        return np.einsum('wk,tkc->twc', weights, verts[np.array(tris)]).reshape(-1, 3)

    def test_legs_apart_and_hair_outside_the_cape(self):
        """In every field clip and tick: the legs below the hips never meet, the hair tail stays clear of the cape."""
        import numpy as np
        points = {b: self.surface(b) for b in (10, 11, 12, 19, 20, 21, 22, 23, 24)}

        def gap(a, c):
            return min(np.sqrt(((a[i:i+400, None]-c[None])**2).sum(-1)).min() for i in range(0, len(a), 400))
        for slot in (0, 2, 3, 4):
            frames, _, _ = animsheet.slot_frames(self.model, 26, slot)
            for tick, pose in enumerate(frames):
                world = np.array(mmd.bone_matrices(self.model, [list(v) for v in pose]))
                at = {b: p @ world[b, :3, :3].T + world[b, :3, 3] for b, p in points.items()}
                right = np.concatenate([at[b] for b in (19, 20, 21)])
                left = np.concatenate([at[b] for b in (22, 23, 24)])
                right = right[np.linalg.norm(right - world[19, :3, 3], axis=1) > 45]
                left = left[np.linalg.norm(left - world[22, :3, 3], axis=1) > 45]
                self.assertGreater(gap(right, left), 5, (slot, tick))
                self.assertGreater(gap(at[12], np.concatenate([at[10], at[11]])), 10, (slot, tick))

    def test_resident_animation_buffer(self):
        storage = motionstorage.require(self.data, len(self.rig))
        self.assertTrue(storage['fits'])
        self.assertLessEqual(storage['resident_bytes'], storage['resident_limit'])
        self.assertEqual(storage['resident_limit'], 100352)

    def test_every_piece_is_bound_once(self):
        objects = sorted(o for o, _ in self.rig if o >= 0)
        self.assertEqual(objects, list(range(len(self.model.tmd.objects))))
        self.assertEqual(set(map(int, self.recipe['map'])), set(range(1, 20)))


if __name__ == '__main__':
    unittest.main()
