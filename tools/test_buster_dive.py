"""The dash edit isolates a shared attack and preserves body acting and events."""
import sys
from pathlib import Path
import unittest
import hashlib
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mmd
from copy import deepcopy
from tools.models.buster_dive import apply, repair


class DashEdit(unittest.TestCase):
    def test_reviewed_compact_body_keeps_exact_native_root_and_other_slots(self):
        data, donor = self.models(61)
        before = mmd.MMD.parse(data, 2)
        source = before.anims.anims[0]
        recipe = dict(source_sha256=hashlib.sha256(source.build()).hexdigest(),
                      pose_keys=[[0, 0], [22, 22], [33, 22], [44, 60]])
        actual = mmd.MMD.parse(repair(data, 2, 47, donor, clip=recipe), 2)
        dense = mmd.MMD.parse(repair(data, 2, 47, donor), 2)
        poses, info = mmd.simulate(actual.anims.anims[actual.anims.table[47]], 2, slot=47)
        original, _ = mmd.simulate(source, 2, slot=47)
        reference, _ = mmd.simulate(dense.anims.anims[dense.anims.table[47]], 2, slot=47)
        self.assertEqual(len(poses), 45)
        self.assertEqual([p[0] for p in poses], [p[0] for p in reference[:45]])
        for output, source_index in recipe['pose_keys']:
            for channel in range(9):
                self.assertLessEqual(abs(poses[output][1][channel] - original[source_index][1][channel]), 1)
        self.assertIsNone(info['loop'])
        self.assertEqual(actual.tmd.build(), before.tmd.build())
        for slot in range(64):
            if slot != 47:
                self.assertEqual(actual.anims.anims[actual.anims.table[slot]].build(), source.build())
        self.assertEqual([(bank, note) for _, bank, note in info['sounds']], [(4, 17)])

    def test_compact_body_rejects_unreviewed_source(self):
        data, donor = self.models(61)
        recipe = dict(source_sha256='0' * 64, pose_keys=[[0, 0], [22, 22], [44, 22]])
        with self.assertRaisesRegex(ValueError, 'body source changed'):
            repair(data, 2, 47, donor, clip=recipe)

    def models(self, length):
        model = mmd.MMD()
        model.nbones = 2
        model.tmd = mmd.TMD()
        model.anims = mmd.AnimSection()
        poses = [[[4096, 4096, 4096, 0, 0, 0, 0, 0, -i],
                  [4096, 4096, 4096, i * 3, 0, 0, i, -20, 0]] for i in range(length)]
        attack = mmd.encode_anim(poses, 2, events=[(5, 'sound', dict(bank=4, note=17))], tol=0)
        model.anims.anims = [attack]
        model.anims.table = [0] * 64
        roots = [[[4096, 4096, 4096, 0, 0, 0, 0, 0, -max(0, min(i - 22, 8)) * 100]]
                 for i in range(45)]
        return model.build(), mmd.encode_anim(roots, 1, tol=0)

    def check_edit(self, length):
        data, donor = self.models(length)
        before = mmd.MMD.parse(data, 2)
        after = mmd.MMD.parse(repair(data, 2, 47, donor), 2)
        old = before.anims.anims[0]
        new = after.anims.anims[after.anims.table[47]]
        self.assertNotEqual(after.anims.table[46], after.anims.table[47])
        for slot in range(64):
            if slot != 47:
                other = after.anims.anims[after.anims.table[slot]]
                self.assertEqual((old.pose, old.instrs), (other.pose, other.instrs))
        original, _ = mmd.simulate(old, 2)
        edited, _ = mmd.simulate(new, 2)
        self.assertEqual(len(edited), max(length, 45))
        for tick, pose in enumerate(edited):
            self.assertEqual(pose[1], original[min(tick, length - 1)][1])
        self.assertEqual(edited[22][0][8] - edited[32][0][8], 800)
        self.assertEqual(edited[-1][0][8], -800)
        self.assertEqual(mmd.anim_events(old, 2, 47, ('sound', 'tex')),
                         mmd.anim_events(new, 2, 47, ('sound', 'tex')))

    def test_short_attack_holds_its_pose_until_the_sweep_ends(self):
        self.check_edit(19)

    def test_long_attack_keeps_its_recovery_after_the_dash(self):
        self.check_edit(61)

    def test_final_model_pass_is_idempotent(self):
        data, donor = self.models(19)
        spec = dict(id=461, techniques=['Megaton Punch', 'Buster Dive'],
                    model=dict(skeleton=[[-1, -1], [0, 0]]))
        with patch('tools.models.buster_dive.native_dash', return_value=donor):
            result, proof = apply(data, spec)
        self.assertEqual(proof['slot'], 47)
        self.assertTrue(proof['storage']['fits'])
        again, proof = apply(result, spec)
        self.assertEqual(result, again)
        self.assertIsNone(proof)

    def test_unreachable_tails_are_reclaimed_without_changing_live_programs(self):
        data, donor = self.models(19)
        model = mmd.MMD.parse(data, 2)
        model.anims.anims[0].tail = bytes(range(256)) * 16
        duplicate = deepcopy(model.anims.anims[0])
        duplicate.tail = bytes(range(255, -1, -1)) * 16
        model.anims.table[5] = len(model.anims.anims)
        model.anims.anims.append(duplicate)
        data = model.build()
        edited = repair(data, 2, 47, donor)
        after = mmd.MMD.parse(edited, 2)
        self.assertLess(len(edited), len(data) - 7000)
        self.assertEqual(after.anims.table[0], after.anims.table[5])
        for slot in range(64):
            if slot == 47:
                continue
            a = model.anims.anims[model.anims.table[slot]]
            b = after.anims.anims[after.anims.table[slot]]
            self.assertEqual(mmd.simulate(a, 2, slot=slot), mmd.simulate(b, 2, slot=slot))

    def test_over_budget_candidate_keeps_the_playable_source_and_reports_it(self):
        data, donor = self.models(19)
        spec = dict(id=219, techniques=['Megaton Punch', 'Buster Dive'],
                    model=dict(skeleton=[[-1, -1], [0, 0]]))
        with patch('tools.models.buster_dive.native_dash', return_value=donor), \
             patch('tools.models.buster_dive.motionstorage.audit', return_value=dict(fits=False, resident_bytes=103000)):
            result, proof = apply(data, spec)
        self.assertEqual(result, data)
        self.assertFalse(proof['applied'])
        self.assertEqual(proof['storage']['resident_bytes'], 103000)


if __name__ == '__main__':
    unittest.main()
