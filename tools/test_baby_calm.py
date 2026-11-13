"""Motimon's (474) and Bukamon's (475) four calm field clips: native speeds in order, a planted body, the mesh never under
the floor, little arms that move, blinks that read."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animstudio  # noqa: E402
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
import numpy as np  # noqa: E402
from tools.models import babies  # noqa: E402
from tools.models.field_animations import baby_calm  # noqa: E402

SPECIES = (474, 475)
ARMS = {474: ((2, 4), (4, 6)), 475: ((1, 3), (3, 5))}      # (object, bone) of the x > 0 and x < 0 arm
SHUT = {474: (34, 0), 475: (34, 0)}                         # the closed-eye frame of the blink
BLINKS = {474: {0: 4, 2: 1, 3: 1, 4: 1}, 475: {0: 4, 2: 1, 3: 1, 4: 1}}   # blinks (closed frames shown) per clip


@unittest.skipUnless((ROOT / 'extracted/CHDAT/MMD0/KORO.MMD').exists(), 'needs the player extraction')
class BabyClips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.built = {}
        for species in SPECIES:
            model, tim = babies.build_species(species, ROOT / 'extracted')
            cls.built[species] = model
            (Path(cls.tmp.name) / f'{species}.MMD').write_bytes(model)
            (Path(cls.tmp.name) / f'{species}.TIM').write_bytes(tim)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def clip(self, species, slot):
        return animstudio.Model(f'{self.tmp.name}/{species}.MMD:{species}:{self.tmp.name}/{species}.TIM', slot)

    def test_speeds_are_native_and_ordered(self):
        for species in SPECIES:
            speed = {s: abs(animstudio.metrics(self.clip(species, s))[0]) for s in (2, 3, 4)}
            self.assertTrue(15 <= speed[2] <= 31 and 10 <= speed[3] <= 20 and 35 <= speed[4] <= 52, speed)
            self.assertLess(speed[3], speed[2])
            self.assertLess(speed[2], speed[4])

    def test_the_body_is_planted_while_it_is_down(self):
        for species in SPECIES:
            for slot in (2, 3, 4):
                _, res = animstudio.metrics(self.clip(species, slot))
                self.assertTrue(all(r[3] < 25 and r[4] < 45 for r in res), (slot, res))

    def test_the_mesh_never_sinks_under_the_floor(self):
        for species in SPECIES:
            for slot in (0, 2, 3, 4):
                m = self.clip(species, slot)
                floor = float(m.verts[:, 1].max())
                for t in range(len(m.frames)):
                    pose, root = m.pose(t)
                    pts = np.array([v for tri in animsheet.world_tris(m.m, pose, m.skel) for v in tri[0]])
                    self.assertGreaterEqual(floor - (pts[:, 1].max() + root[1]), -.01, (slot, t))

    def test_hops_are_low_and_squash_is_soft(self):
        for species in SPECIES:
            for slot in (2, 3, 4):
                frames = self.clip(species, slot).frames
                self.assertTrue(all(.84 <= f[1][1] / 4096 <= 1.04 for f in frames), (species, slot))
                rise = max(f[1][7] for f in frames) - min(f[1][7] for f in frames)
                self.assertLess(rise, 32, (species, slot, rise))         # Koromon rises 80, 52 and 160 (walk, tired, run)

    def test_every_other_program_is_koromons(self):
        for species in SPECIES:
            record = babies.records()[species]
            parsed = mmd.MMD.parse(self.built[species], record['bones'])
            donor = mmd.MMD.load(str(ROOT / 'extracted/CHDAT' / record['donor_model']), record['donor'])
            self.assertEqual(len(parsed.anims.table), len(donor.anims.table))
            for slot, (a, b) in enumerate(zip(parsed.anims.table, donor.anims.table)):
                self.assertEqual(a is None, b is None)
                if a is not None and slot not in (0, 2, 3, 4):
                    self.assertEqual(vars(parsed.anims.anims[a]), vars(donor.anims.anims[b]), slot)

    def test_storage_and_mesh_budget(self):
        for species in SPECIES:
            self.assertLess(motionstorage.require(self.built[species], 7)['resident_bytes'], 100352)
            self.assertLess(len(self.built[species]), 48 * 1024)

    def test_the_eyes_shut_in_a_blink_with_lids_either_side(self):
        for species in SPECIES:
            m = mmd.MMD.parse(self.built[species], 7)
            for slot, blinks in BLINKS[species].items():
                events = [e for e in animsheet.slot_frames(m, 7, slot)[2] if e[1] == 'tex' and e[2]['dst'] == (2, 0)]
                shut = [e for e in events if e[2]['src'] == SHUT[species]]
                self.assertGreaterEqual(len(shut), blinks, slot)
                self.assertTrue(all(e[2]['size'][0] == 10 for e in events))
                if slot == 0:                                              # irregular, with a double blink
                    ticks = sorted(e[0] for e in shut)
                    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
                    self.assertGreater(max(gaps), 3 * min(gaps), gaps)

    def test_the_little_arms_move_about_their_shoulders(self):
        for species in SPECIES:
            m = mmd.MMD.parse(self.built[species], 7)
            exe = mmd.exe()
            exe.skeleton[species] = exe.skeleton[babies.records()[species]['donor']]
            exe.bone_count[species] = 7
            m.type = species
            t = m.tmd

            def in_body_frame(f, obj, bone):
                mats = [np.vstack([np.array(M, float)[:3], [0, 0, 0, 1]]) for M in mmd.bone_matrices(m, f)]
                v = np.array([c[:3] + (1,) for c in t.obj_verts(obj)], float)
                return v @ (np.linalg.inv(mats[2]) @ mats[bone])[:3].T

            for slot, swing in ((0, 7), (2, 12), (3, 5), (4, 10)):
                frames = animsheet.slot_frames(m, 7, slot)[0]
                for obj, bone in ARMS[species]:
                    side = 1 if obj == 2 else -1
                    origin = np.array(baby_calm.CONFIGS[species]['shoulder'][side], float) if species == 474 else np.zeros(3)
                    shape = [in_body_frame(f, obj, bone) for f in frames]
                    tip = np.array([s_[np.argmax(np.linalg.norm(shape[0] - origin, axis=1))] for s_ in shape])
                    self.assertGreater(np.ptp(tip, axis=0).max(), swing, (species, slot, obj))
                    self.assertLess(np.ptp(tip, axis=0).max(), 60, (species, slot, obj))
                    if species == 474:                                     # no arm stays up: the tip hangs below its shoulder
                        self.assertGreater(tip[:, 1].min(), origin[1] + 8, (slot, obj, tip[:, 1].min()))

    def test_motimons_arms_left_the_body_object_and_its_rest_pose_is_unchanged(self):
        m = mmd.MMD.parse(self.built[474], 7)
        self.assertEqual([len(m.tmd.objects[i].prims) for i in (2, 4)], [66, 66])
        self.assertEqual(sum(1 for p in m.tmd.objects[0].prims if all(u >= 140 and 60 <= v <= 95 for u, v in p.decode()['uv'])), 0)


if __name__ == '__main__':
    unittest.main()
