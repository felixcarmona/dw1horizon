"""406-only repair: clip conservation, strict residuals, and fixture regressions."""
import copy
import json
from pathlib import Path
import sys
import unittest
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
from tools.models import malomyotismon_mesh as repair
from tools.models import malomyotismon_audit as audit
from tools.models.mesh_round4 import load
import mmd
from tools.models import meshcheck, psx_blend
from tools.test_meshcheck import model, box_object


class EvidenceSemantics(unittest.TestCase):
    def test_residual_is_not_a_floor_and_zero_depth_contacts_are_retained(self):
        pair = dict(depth=0, slot=0, tick=0)
        result = audit.compare(dict(pairs={'3/5': pair, '11/13': dict(depth=14)}),
                               dict(pairs={'3/5': pair}))
        self.assertEqual(result['3/5']['status'], 'residual_unproven')
        self.assertEqual(result['11/13']['status'], 'clear_all_frames')
        self.assertEqual(result['11/13']['before_units'], 14)

    def test_windup_keeps_counterbalance_easing_and_exact_boundary_poses(self):
        poses = [[[4096]*3+[0]*6 for _ in range(31)] for _ in range(21)]
        ordinary = repair.windup_brace(55, 10, poses)
        poses[10][12][3] = 500
        poses[10][13][3] = -250
        changed = repair.windup_brace(55, 10, poses)
        self.assertEqual(changed[12, 0]-ordinary[12, 0], 100)
        self.assertEqual(changed[13, 0]-ordinary[13, 0], -50)
        for tick in (0, 20):
            self.assertTrue(all(value == poses[tick][bone][3+axis]
                                for (bone, axis), value in repair.windup_brace(55, tick, poses).items()))
        self.assertEqual({bone for bone, axis in changed}, {4, 12, 13})

    def test_lids_return_to_entry_and_exit_without_a_boundary_snap(self):
        for count in (17, 31, 45):
            poses = [[[4096]*3+[0]*6 for _ in range(31)] for _ in range(count)]
            samples = [repair.lid_dodge(47, t, poses) for t in range(count)]
            for bone in (3, 11):
                angles = [values[bone, 0] for values in samples]
                self.assertEqual(angles[0], 0)
                self.assertEqual(angles[-1], 0)
                self.assertEqual(angles, angles[::-1])
                self.assertLessEqual(max(abs(b-a) for a, b in zip(angles, angles[1:])), 54)


class RenderCache(unittest.TestCase):
    def test_cache_reuses_identical_render_and_invalidates_after_a_pose_change(self):
        raw, bones = model(box_object())
        frames = [[[4096]*3+[0]*6 for _ in bones] for _ in range(2)]
        raw.anims.anims = [mmd.encode_anim(frames, len(bones), None, [])]
        raw.anims.table = [0]
        before = meshcheck.Model(raw, bones)
        after = copy.deepcopy(before)
        with tempfile.TemporaryDirectory() as folder:
            audit._before, audit._after = before, after
            audit._out, audit._cases, audit._same_surface = Path(folder), {(0, 0)}, True
            first = audit._render((0, [0]))
            self.assertEqual(first['views'], 16)
            self.assertTrue(audit._render((0, [0]))['cached'])
            after.m.anims.anims[0].pose[0][0] += 256
            self.assertNotIn('cached', audit._render((0, [0])))
            sheet = np.load(Path(folder)/'0.npz')['frames'][0]
            left, frame = psx_blend.render(before, 0, np.pi/6, size=128, pose=before.poses(0)[0])
            right, _ = psx_blend.render(after, 0, np.pi/6, size=128, pose=after.poses(0)[0], frame=frame)
            self.assertTrue(np.array_equal(sheet[:128, :128], left))
            self.assertTrue(np.array_equal(sheet[:128, 128:], right))


@unittest.skipUnless((ROOT/'build/before/406.MMD').exists() and
                     (ROOT/'build/after/406.MMD').exists(), 'private final model fixtures unavailable')
class FinalFixtures(unittest.TestCase):
    def test_repair_matches_provider_and_preserves_root_events_timing_aliases_and_mesh(self):
        before, after = [load(ROOT/'build'/stage, 406) for stage in ('before', 'after')]
        model = copy.deepcopy(before.m)
        report = repair.polish(model, before.bones)
        self.assertEqual(model.build(), after.m.build())
        self.assertEqual(before.m.tmd.build(), after.m.tmd.build())
        for tick in (0, -1):
            self.assertEqual(before.poses(55, 6000)[tick], after.poses(55, 6000)[tick])
        checked = audit.preservation(before, after)
        self.assertEqual(checked['ticks'], 1714)
        for row in checked['slots'].values():
            self.assertTrue(all(bone < 18 for bone, channel in row['rotation_channels']))
        self.assertLessEqual(report['clearance_resident_after'], report['clearance_resident_before'])
        self.assertLessEqual(checked['storage']['after']['resident_bytes'], 74558)

    @unittest.skipUnless((ROOT/'build/ledger-verified/406.json').exists(), 'full ledger unavailable')
    def test_final_cap_pairs_clear_and_all_other_pair_regressions_are_reported(self):
        before = json.loads((ROOT/'build/ledger-before/406.json').read_text())
        after = json.loads((ROOT/'build/ledger-verified/406.json').read_text())
        for pair in ('2/3', '10/11', '3/5', '11/13', '3/21', '11/28'):
            self.assertNotIn(pair, after['pairs'])
        for pair, row in after['pairs'].items():
            self.assertIn(pair, before['pairs'], f'new crossing pair {pair}')
            self.assertLessEqual(row['depth'], before['pairs'][pair]['depth']+.501, pair)


if __name__ == '__main__':
    unittest.main()
