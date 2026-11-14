"""ChaosLord (289) wears native Machinedramon's skeleton: its rig and field programs are Machinedramon's own."""
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

DONOR = 115
BONES = 32
SOLES = (28, 31)
BUFFER = 100352


class ChaosLordNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('289-*.MMD'))
        tims = list(source.glob('289-*.TIM'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD3/MUGE.MMD'
        if not files or not tims or not native_path.exists():
            raise unittest.SkipTest('needs the imported 289 model (edit.py get 289) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['289']
        spec = importlib.util.spec_from_file_location('imported_species_289', 'content/models/imports/species.py')
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        cls.tmp = tempfile.mkdtemp(prefix='chaoslord-')
        base = Path(cls.tmp) / 'base'
        base.mkdir()
        shutil.copy(files[0], base / '289.MMD')
        shutil.copy(tims[0], base / '289.TIM')
        imported.BASE_MODELS = str(base)
        path, cls.proof = imported.overlay(str(Path(cls.tmp) / 'species'), '289')
        cls.data = Path(path).read_bytes()
        cls.source = files[0].read_bytes()
        cls.rig = cls.proof['generated_skeleton']
        cls.record = json.loads(next(Path('content/species').glob('289-*.json')).read_text())
        mmd.exe().add_type(9289, cls.rig)
        cls.model = mmd.MMD.parse(cls.data, len(cls.rig))
        cls.model.type = DONOR
        cls.native = mmd.MMD.load(str(native_path), DONOR)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def ticks(self, slot):
        return len(animsheet.slot_frames(self.model, BONES, slot)[0])

    def speed(self, slot):
        frames = animsheet.slot_frames(self.model, BONES, slot)[0]
        return abs(frames[-1][0][8] - frames[0][0][8])/(len(frames) - 1)

    def test_rig_is_machinedramons_and_every_piece_is_bound_once(self):
        self.assertEqual([p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[DONOR]])
        self.assertEqual(len(self.rig), BONES)
        self.assertEqual((self.recipe['donor'], self.recipe['model']), (DONOR, 'CHDAT/MMD3/MUGE.MMD'))
        self.assertEqual(sorted(o for o, _ in self.rig if o >= 0), list(range(len(self.model.tmd.objects))))
        source = self.record['model']['skeleton']
        self.assertEqual(sorted(map(int, self.recipe['map'])), list(range(1, len(source))))
        # the two thrusters share the chest; the claw hand, second neck bone and cannon tips carry no mesh
        self.assertEqual(self.recipe['map']['13'], self.recipe['map']['14'])
        self.assertTrue(all(o < 0 for b, (o, _) in enumerate(self.rig) if b in (0, 1)))

    def test_field_slots_below_the_techniques_are_the_donors_programs(self):
        donor = mmd.MMD.parse(binding.donor_model(self.recipe), BONES)
        donor.type = DONOR
        for slot in (2,):                # the idle and the run are the species' own, test_run_is_the_original_run_in_world_space
            clip = donor.anims.anims[donor.anims.table[slot]]
            clip.instrs = [i for i in clip.instrs if i['op'] != 'tex']
            clip.tail = b''
            self.assertEqual(self.recipe['scale'], 1.0)
            self.assertEqual(self.model.anims.anims[self.model.anims.table[slot]].build(), clip.build(), slot)

    def test_slots_and_ticks(self):
        self.assertEqual([self.ticks(s) for s in (0, 2, 3, 4)], [38, 21, 31, 19])
        for slot in list(range(46, 46 + len(self.record['techniques']))) + [61, 62]:
            self.assertIsNotNone(self.model.anims.table[slot], slot)
        self.assertEqual(self.recipe['technique_slots'], [50, 52, 48, 47, 47, 47, 49, 51, 46, 46, 46, 46, 48, 46, 47])
        self.assertEqual(len(self.recipe['technique_slots']), len(self.record['techniques']))

    def test_gait_speeds_are_native_and_ordered(self):
        walk, tired, run = (self.speed(s) for s in (2, 3, 4))
        self.assertTrue(15 <= walk <= 31, walk)
        self.assertTrue(10 <= tired <= 20, tired)
        self.assertTrue(35 <= run <= 52, run)
        self.assertLess(tired, walk)
        self.assertLess(walk, run)
        frames = animsheet.slot_frames(self.native, BONES, 2)[0]
        native = abs(frames[-1][0][8] - frames[0][0][8])/(len(frames) - 1)
        self.assertAlmostEqual(walk, native, delta=1)

    def donor_idle(self):
        donor = mmd.MMD.parse(binding.donor_model(self.recipe), BONES)
        donor.type = DONOR
        return animsheet.slot_frames(donor, BONES, 0)[0]

    def original_run(self, slot):
        """The unbound ChaosLord and its own run: (model, skeleton, frames, the pose both rigs were fitted in)."""
        skeleton = self.record['model']['skeleton']
        mmd.exe().add_type(9290, skeleton)
        original = mmd.MMD.parse(self.source, len(skeleton))
        original.type = 9290
        frames = animsheet.slot_frames(original, len(skeleton), slot)[0]
        rest = animsheet.slot_frames(original, len(skeleton), self.recipe['bind_slot'])[0][0]
        return original, skeleton, frames, rest

    @staticmethod
    def still(pose):
        return [[4096]*3 + pose[0][3:6] + [0, 0, 0]] + [list(v) for v in pose[1:]]

    def test_run_and_idle_are_the_original_ones_in_world_space(self):
        # the battle idle 33 and the battle run 36 are the source's own (battle_originals), so the run no longer shares its clip
        for slot, alias in ((4, 36), (0, None)):
            with self.subTest(slot=slot):
                self.world_space(slot, alias, shared=alias not in self.recipe['battle_originals']['slots'])

    def world_space(self, slot, alias, shared=True):
        original, skeleton, old, rest_source = self.original_run(slot)
        new = animsheet.slot_frames(self.model, BONES, slot)[0]
        if alias is not None and shared:
            self.assertEqual(self.model.anims.table[alias], self.model.anims.table[slot])
        self.assertEqual(len(old), len(new))
        row = self.recipe['pace'][str(slot)]
        aliases = [] if alias is None else [alias]
        self.assertEqual((row['ticks'], row['alias'], row['original_run']), (len(old) - 1, aliases, True))
        rest_donor = self.donor_idle()[0]
        rest_source = self.still(rest_source)
        rest_donor = self.still(rest_donor)
        source_inverse = [np.linalg.inv(m) for m in np.array(mmd.bone_matrices(original, rest_source))]
        donor_rest = np.array(mmd.bone_matrices(self.model, rest_donor))
        first = {}
        for sb, db in sorted((int(k), v) for k, v in self.recipe['map'].items()):
            first.setdefault(db, sb)
        reached = {b for base, mid, end in self.recipe['limbs'] for b in (base, mid)}
        worst = {}
        for t in range(len(old)):
            motion = np.array(mmd.bone_matrices(original, self.still(old[t]))) @ source_inverse
            world = np.array(mmd.bone_matrices(self.model, self.still(new[t])))
            for db, sb in first.items():
                want = (motion[sb] @ donor_rest[db])[:3, :3]
                gap = np.degrees(np.arccos(np.clip((np.trace(world[db][:3, :3].T @ want) - 1) / 2, -1, 1)))
                worst[db] = max(worst.get(db, 0), gap)
        # every bone that is not a limb's base or middle has the original's world rotation, whatever its parents did
        for db, gap in worst.items():
            self.assertLess(gap, 3 if db not in reached else 60, (db, gap))
        self.assertAlmostEqual(self.speed(slot), 47.5 if slot == 4 else 0, delta=.5)

    def test_run_and_idle_mesh_stay_on_the_original_mesh(self):
        for slot, mean, top, worst in ((4, 30, 42, 140), (0, 26, 26, 100)):
            with self.subTest(slot=slot):
                self.mesh_gap(slot, mean, top, worst)

    def mesh_gap(self, slot, mean_limit, top_limit, worst_limit):
        original, skeleton, old, _ = self.original_run(slot)
        new = animsheet.slot_frames(self.model, BONES, slot)[0]
        pairs, taken = [], {}
        for sb, db in sorted((int(k), v) for k, v in self.recipe['map'].items()):      # the order the pieces were bound in
            count = len(original.tmd.obj_verts(skeleton[sb][0]))
            start = taken.get(db, 0)
            taken[db] = start + count
            pairs.append((sb, db, start, count))
        mean, worst = [], 0
        for before, after in zip(old, new):
            then = np.array(mmd.bone_matrices(original, self.still(before)))
            now = np.array(mmd.bone_matrices(self.model, self.still(after)))
            gaps = []
            for sb, db, start, count in pairs:
                a = np.array(original.tmd.obj_verts(skeleton[sb][0]))[:, :3] @ then[sb, :3, :3].T + then[sb, :3, 3]
                b = np.array(self.model.tmd.obj_verts(self.rig[db][0]))[start:start + count, :3] @ now[db, :3, :3].T + now[db, :3, 3]
                gaps.append(np.linalg.norm(a - b, axis=1))
            gaps = np.concatenate(gaps)
            mean.append(gaps.mean())
            worst = max(worst, gaps.max())
        # the fitted pieces already differ from the original's by a mean 25 at rest (the donor stands lower and
        # crouched): the run adds little to that
        self.assertLess(np.mean(mean), mean_limit)
        self.assertLess(max(mean), top_limit)
        self.assertLess(worst, worst_limit)

    def test_donor_bones_without_a_source_hold_the_fitted_pose(self):
        original, skeleton, _, _ = self.original_run(4)
        new = animsheet.slot_frames(self.model, BONES, 4)[0]
        donor_rest = self.donor_idle()[0]
        mapped = {v for v in self.recipe['map'].values()} | {0}
        for db in set(range(BONES)) - mapped:
            self.assertEqual({tuple(f[db][3:7] + f[db][8:9]) for f in new}, {tuple(donor_rest[db][3:7] + donor_rest[db][8:9])}, db)

    def test_loops_close(self):
        for slot in (0, 2, 3, 4):
            frames = animsheet.slot_frames(self.model, BONES, slot)[0]
            for bone in range(BONES):
                np.testing.assert_allclose(mmd.rot_matrix(*frames[0][bone][3:6]), mmd.rot_matrix(*frames[-1][bone][3:6]),
                                           atol=.01, err_msg=str(bone))

    def test_effect_points_and_bubble_sit_on_real_bones(self):
        patch = self.recipe['species_patch']
        self.assertTrue(0 <= patch['condition_bubble'][3] < BONES)
        for row in patch['effect_origins']:
            self.assertTrue(0 <= row[0] < BONES and 0 <= row[4] < BONES, row)

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
            frames = animsheet.slot_frames(self.model, BONES, slot)[0]
            low = []
            for pose in frames[:-1]:
                p = [list(x) for x in pose]
                p[0] = [4096]*3 + p[0][3:6] + [0, 0, 0]
                w = np.array(mmd.bone_matrices(self.model, p))
                ys = []
                for b in SOLES:
                    v = np.array(self.model.tmd.obj_verts(self.rig[b][0]))[:, :3]
                    ys.append((v @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max())
                low.append(max(ys))
            self.assertLessEqual(max(low), 60, slot)
            self.assertGreaterEqual(min(low), -5, slot)


if __name__ == '__main__':
    unittest.main()
