"""PrinceMamemon (270) wears native Mamemon's skeleton: its rig and every field and care program are Mamemon's own."""
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
import test_metaltyrannomon_native as tyranno
from tools.models.field_animations import native_binding as binding

DONOR = 13
BONES = 19
SOLES = (14, 18)
ARMS = {'R': (7, 8, 9), 'L': (3, 4, 5)}
LEGS = {'R': (12, 13, 14), 'L': (16, 17, 18)}
BODY = 10


class PrinceMamemonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('270-*.MMD'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD0/MAME.MMD'
        if not files or not native_path.exists():
            raise unittest.SkipTest('needs the imported 270 model (edit.py get 270) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['270']
        cls.record = json.loads(next(Path('content/species').glob('270-*.json')).read_text())
        cls.source = files[0].read_bytes()
        cls.data, cls.proof = binding.bind(cls.source, cls.record['model']['skeleton'], cls.recipe)
        cls.rig = cls.proof['generated_skeleton']
        mmd.exe().add_type(9270, cls.rig)
        cls.model = mmd.MMD.parse(cls.data, len(cls.rig))
        cls.model.type = DONOR
        cls.native = mmd.MMD.load(str(native_path), DONOR)
        mmd.exe().add_type(270, cls.record['model']['skeleton'])
        old = mmd.MMD.parse(cls.source, len(cls.record['model']['skeleton']))
        cls.sphere_vertices = len(old.tmd.obj_verts(cls.record['model']['skeleton'][2][0]))

    def scaled(self, model, slot):
        """The donor's program with its translations scaled the way the recipe scales them."""
        clip = copy.deepcopy(model.anims.anims[model.anims.table[slot]])
        clip.instrs = [i for i in clip.instrs if i['op'] != 'tex']
        clip.tail = b''
        return clip

    def test_rig_is_mamemons(self):
        self.assertEqual([p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[DONOR]])
        self.assertEqual(len(self.rig), BONES)
        self.assertEqual((self.recipe['donor'], self.recipe['model']), (DONOR, 'CHDAT/MMD0/MAME.MMD'))

    def test_every_program_below_the_techniques_is_mamemons_with_scaled_translations(self):
        scale = self.recipe['scale']
        restored = set(self.recipe.get('battle_originals', {}).get('slots', []))
        for slot, index in enumerate(self.native.anims.table[:46]):
            if index is None or slot in restored:      # the source's own clip (test_battle_originals)
                continue
            with self.subTest(slot=slot):
                expected = self.scaled(self.native, slot)
                for pose in expected.pose:
                    pose[-3:] = [round(v*scale) for v in pose[-3:]]
                for instruction in expected.instrs:
                    if instruction['op'] == 'key':
                        for group in instruction['bones']:
                            for channel in group['vals']:
                                if channel in ('tx', 'ty', 'tz'):
                                    group['vals'][channel] = round(group['vals'][channel]*scale)
                self.assertEqual(self.scaled(self.model, slot).build(), expected.build())

    def test_every_old_slot_is_still_covered_and_field_clips_keep_mamemons_timing(self):
        old = {0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24, 25, 27,
               33, 34, 35, 36, 37, 40, 41, 42, 43, 44} | set(range(46, 63))
        for slot in old:
            if slot in (6, 20, 26):
                continue
            with self.subTest(slot=slot):
                self.assertIsNotNone(self.model.anims.table[slot])
        self.assertEqual({0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 19, 21, 22, 24, 25, 27, 33, 34, 35, 36, 37, 40, 41, 42, 43, 44}
                         - {s for s, i in enumerate(self.model.anims.table) if i is not None}, set())
        for slot in (0, 2, 3, 4):
            with self.subTest(slot=slot):
                before, loop, _ = animsheet.slot_frames(self.native, BONES, slot)
                after, new_loop, _ = animsheet.slot_frames(self.model, BONES, slot)
                self.assertEqual((len(after), new_loop), (len(before), loop))
        self.assertEqual([len(animsheet.slot_frames(self.model, BONES, s)[0]) for s in (0, 2, 3, 4)], [17, 15, 19, 15])

    def test_techniques_play_mamemons_clips_of_their_kind(self):
        moves = self.record['techniques']
        slots = self.recipe['technique_slots']
        self.assertEqual(len(slots), len(moves))
        mamemon = json.loads(next(Path('content/species').glob('13-mamemon.json')).read_text())['techniques']
        for position, move in enumerate(moves):
            if move in mamemon:
                self.assertEqual(slots[position], 46 + mamemon.index(move), move)
            with self.subTest(move=move):
                self.assertIn(slots[position], range(46, 46 + len(mamemon)))
                self.assertIsNotNone(self.model.anims.table[46 + position])

    def test_training_clip_is_mamemons_and_hits_on_its_tick(self):
        training = self.recipe['species_patch']['partner']['training']
        self.assertEqual(training, {'animation': 61, 'hit_tick': 8})
        self.assertEqual(self.recipe['extra_slots']['61'], 46)
        expected = self.scaled(self.native, 46)
        for pose in expected.pose:
            pose[-3:] = [round(v*self.recipe['scale']) for v in pose[-3:]]
        for instruction in expected.instrs:
            if instruction['op'] == 'key':
                for group in instruction['bones']:
                    for channel in group['vals']:
                        if channel in ('tx', 'ty', 'tz'):
                            group['vals'][channel] = round(group['vals'][channel]*self.recipe['scale'])
        self.assertEqual(self.scaled(self.model, 61).build(), expected.build())
        self.assertEqual(self.recipe['species_patch']['partner']['status_screen_position'],
                         self.record['partner']['status_screen_position'])

    def test_bubble_and_effect_points_ride_mamemons_bones(self):
        patch = self.recipe['species_patch']
        self.assertEqual(patch['condition_bubble'][3], BODY)
        self.assertEqual(len(patch['effect_origins']), len(self.record['effect_origins']))
        for row in patch['effect_origins']:
            self.assertGreaterEqual(self.rig[row[4]][0], 0, row)

    def test_resident_animation_buffer(self):
        storage = motionstorage.require(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertEqual(storage['resident_limit'], 100352)
        self.assertLessEqual(storage['resident_bytes'], 80000)

    def test_every_piece_is_bound_once(self):
        objects = sorted(o for o, _ in self.rig if o >= 0)
        self.assertEqual(objects, list(range(len(self.model.tmd.objects))))
        self.assertEqual(sorted(map(int, self.recipe['map'])), list(range(1, 24)))
        self.assertEqual(sorted(set(self.recipe['map'].values())), [b for b, (o, _) in enumerate(self.rig) if o >= 0])
        self.assertEqual([b for b, (o, _) in enumerate(self.rig) if o < 0], [0, 1, 2, 6, 11, 15])

    def world(self, slot, tick):
        pose = [list(p) for p in animsheet.slot_frames(self.model, BONES, slot)[0][tick]]
        pose[0] = [4096]*3 + pose[0][3:6] + [0, 0, 0]
        return np.array(mmd.bone_matrices(self.model, pose))

    def points(self, world, bone):
        v = np.array(self.model.tmd.obj_verts(self.rig[bone][0]))[:, :3]
        return v @ world[bone, :3, :3].T + world[bone, :3, 3]

    def test_feet_stand_on_the_floor_and_dig_in_only_a_little_in_the_gaits(self):
        low = {}
        for slot in (0, 2, 3, 4):
            ticks = len(animsheet.slot_frames(self.model, BONES, slot)[0]) - 1
            rows = []
            for t in range(ticks):
                w = self.world(slot, t)
                rows.append(max(self.points(w, b)[:, 1].max() for b in SOLES))
            low[slot] = (min(rows), max(rows))
        self.assertLessEqual(abs(low[0][0]), 3)
        self.assertLessEqual(abs(low[0][1]), 3)
        for slot in (2, 3, 4):
            # y is down: the lowest sole at the worst tick sinks no more than 45 below the floor
            self.assertLessEqual(max(0, low[slot][1]), 45, slot)

    def test_limbs_do_not_poke_through_the_body_and_the_cape(self):
        body = []
        for prim in self.model.tmd.objects[self.rig[BODY][0]].prims:
            v = prim.decode()['verts']
            body += [v[:3]] if len(v) == 3 else [[v[0], v[1], v[2]], [v[1], v[3], v[2]]]
        sphere = [t for t in body if max(t) < self.sphere_vertices]
        cape = [t for t in body if min(t) >= self.sphere_vertices]
        for slot in (0, 2, 3, 4):
            ticks = len(animsheet.slot_frames(self.model, BONES, slot)[0]) - 1
            worst = {'arm': 0, 'leg': 0, 'arm-cape': 0}
            for t in range(ticks):
                w = self.world(slot, t)
                body_points = self.points(w, BODY)
                arms = np.concatenate([self.points(w, b) for b in ARMS['R'] + ARMS['L']])
                legs = np.concatenate([self.points(w, b) for b in LEGS['R'] + LEGS['L']])
                worst['arm'] = max(worst['arm'], int(tyranno.MetalTyrannomonNative._inside(body_points, sphere, arms).sum()))
                worst['leg'] = max(worst['leg'], int(tyranno.MetalTyrannomonNative._inside(body_points, sphere, legs).sum()))
                worst['arm-cape'] = max(worst['arm-cape'], int(tyranno.MetalTyrannomonNative._inside(body_points, cape, arms).sum()))
            # thigh stubs begin inside the sphere on purpose, so a handful of leg vertices is the floor
            self.assertEqual(worst['arm'], 0, slot)
            self.assertEqual(worst['arm-cape'], 0, slot)
            self.assertLessEqual(worst['leg'], 16, slot)

    def test_battle_originals(self):
        # the source's own battle idle on Mamemon's rig (native_battle.py); the spinning quad inside the sphere (piece
        # 23) rides the sphere's bone without leading it; an idle keeps its own 40-tick cycle (battle_restore.plan)
        self.assertEqual(self.recipe['battle_originals'], {'slots': [33], 'ride': [23]})
        made = self.proof['battle_originals']
        self.assertEqual(sorted(int(s) for s in made), [33])
        self.assertEqual((made[33]['frames'], made[33]['cycles']), (40, 1))
        self.assertEqual(motionstorage.require(self.data, BONES)['resident_bytes'], 76032)

    def test_loops_close(self):
        for slot in (0, 2, 3, 4):
            frames, loop, _ = animsheet.slot_frames(self.model, BONES, slot)
            self.assertEqual(loop, animsheet.slot_frames(self.native, BONES, slot)[1])
            for bone in range(BONES):
                np.testing.assert_allclose(mmd.rot_matrix(*frames[0][bone][3:6]), mmd.rot_matrix(*frames[-1][bone][3:6]),
                                           atol=.01, err_msg=str(bone))

    def test_gait_speeds_keep_their_order(self):
        speed = {}
        for slot in (2, 3, 4):
            frames = animsheet.slot_frames(self.model, BONES, slot)[0]
            speed[slot] = abs(frames[-1][0][8] - frames[0][0][8])/(len(frames) - 1)
        native = {}
        for slot in (2, 3, 4):
            frames = animsheet.slot_frames(self.native, BONES, slot)[0]
            native[slot] = abs(frames[-1][0][8] - frames[0][0][8])/(len(frames) - 1)
        for slot in (2, 3, 4):
            self.assertAlmostEqual(speed[slot], native[slot]*self.recipe['scale'], delta=1)
        self.assertLess(speed[3], speed[2])
        self.assertLess(speed[2], speed[4])


if __name__ == '__main__':
    unittest.main()
