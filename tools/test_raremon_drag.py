"""Check Raremon's drag-crawl walk, tired walk and run (tools/models/field_animations/raremon_drag.py).

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 264`). Before the change it is
`raremon_drag.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the checks
that need the old clips are skipped.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import okuwamon_limbs as limbs
from tools.models.field_animations import raremon_drag as drag

EXPECTED = 'f32b41ba348fed91179c2bec1e0966b6959a24aba059779605c8c48a82d5b7c5'
NB = 18
GAITS = (2, 3, 4)
BODY = (1, 2, 3, 4, 5)


class RaremonDrag(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/264-Raremon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 264')
        cls.sk = json.loads(next(Path('content/species').glob('264-*.json')).read_text())['model']['skeleton']
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        cls.proof = None
        if digest == drag.SOURCE:
            cls.old = drag.parse(data, cls.sk)
            data, cls.proof, _, _ = drag.build(data, cls.sk)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = drag.parse(data, cls.sk)
        cls.rest = animsheet.slot_frames(cls.new, NB, 0)[0][0]
        cls.rig = drag.Rig(cls.new, cls.sk, cls.rest)
        cls.body = limbs.Body(cls.new, cls.sk)
        cls.clips, cls.report = {}, {}
        for slot in GAITS:
            frames = [[[int(round(v)) for v in bone] for bone in pose] for pose in animsheet.slot_frames(cls.new, NB, slot)[0]]
            cls.clips[slot] = frames
            cls.report[slot] = drag.analyse(cls.rig, frames, slot)

    def need_old(self):
        if self.old is None:
            self.skipTest('needs the model before this change')

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, NB)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_only_the_three_clips_change_and_the_meshes_do_not(self):
        self.need_old()
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        self.assertEqual(self.proof['changed_slots'], [2, 3, 4])           # the idle, its alias 33 and the rest pose stay

    def test_the_three_clips_differ_in_poses_and_in_length(self):
        poses = {s: [[tuple(b[3:]) for b in f[1:]] for f in self.clips[s]] for s in GAITS}
        self.assertEqual({s: len(self.clips[s]) - 1 for s in GAITS}, {2: 16, 3: 24, 4: 12})
        for a in GAITS:
            for b in GAITS:
                if a < b:
                    self.assertNotEqual(poses[a][:12], poses[b][:12], (a, b))
        # not one clip replayed at another speed: the tired walk's hump sits lower and its head hangs
        def mean(slot, bone, col):
            return np.mean([f[bone][col] for f in self.clips[slot][:-1]])
        self.assertGreater(mean(3, 1, 3), mean(2, 1, 3) + 40)              # the tired body leans down further
        self.assertGreater(mean(3, 4, 3), mean(2, 4, 3) + 30)              # head pitched down
        self.assertGreater(mean(4, 1, 3), mean(2, 1, 3))                   # the run pitches the body forward more

    def test_loops_close_and_the_root_keeps_one_speed(self):
        for slot in GAITS:
            frames = self.clips[slot]
            v = drag.CLIPS[slot]['v']
            self.assertEqual(frames[-1][1:], frames[0][1:], slot)
            self.assertEqual([-f[0][8] for f in frames], [round(v * i) for i in range(len(frames))])

    def test_speeds_are_native_and_ordered_tired_walk_run(self):
        v = {s: drag.CLIPS[s]['v'] for s in GAITS}
        self.assertTrue(10 <= v[3] < v[2] < v[4])
        self.assertTrue(15 <= v[2] <= 31 and 35 <= v[4] <= 52, v)

    def test_planted_hands_do_not_slide_and_stand_on_the_floor(self):
        for slot in GAITS:
            for h in self.report[slot]['hands']:
                self.assertGreaterEqual(h['stance'], 3, slot)
                self.assertLessEqual(h['slip_mean'], 12, (slot, h['arm']))
                self.assertLessEqual(h['slip_max'], 25, (slot, h['arm']))
                self.assertLessEqual(h['sink'], 1.0, slot)                    # no vertex under the floor by 1 unit
                self.assertLessEqual(h['planted_height_range'][1], 2.5, slot)  # nor floating while planted
                self.assertGreaterEqual(h['planted_height_range'][0], -1.0, slot)

    def test_stride_is_what_the_pull_covers(self):
        for slot in GAITS:
            spec = drag.CLIPS[slot]
            for h in self.report[slot]['hands']:
                # a hand travels over the hump by what the body gains during its stance: the burst's travel, never more than the arm allows
                self.assertLessEqual(h['wrist_travel'], 155, slot)
                self.assertGreaterEqual(h['wrist_travel'], .75 * spec['v'] * (spec['stance'] - 1), slot)

    def test_the_arms_make_the_motion_not_the_fingers(self):
        for slot in GAITS:
            for h in self.report[slot]['hands']:
                self.assertGreaterEqual(h['arm_swing'], 25, slot)
                self.assertGreaterEqual(h['arm_swing'], 2.8 * h['finger_swing'], slot)
                self.assertLessEqual(h['finger_swing'], 20, slot)

    def test_the_body_surges_and_the_hands_alternate(self):
        for slot in GAITS:
            self.assertGreaterEqual(self.report[slot]['surge'], 30, slot)
            n = len(self.clips[slot]) - 1
            a, b = self.report[slot]['hands']
            frames = self.clips[slot][:n]
            height = [[-float(drag.hand_points(self.rig, f, arm)[0][:, 1].max()) for f in frames] for arm in drag.ARMS]
            down = [[t for t in range(n) if height[k][t] <= 2.5 and height[k][t - 1] > 6] for k in (0, 1)]
            self.assertEqual(len(down[0]), 1, slot)
            self.assertEqual((down[1][0] - down[0][0]) % n, n // 2, slot)

    def test_no_limb_goes_into_the_body_or_the_other_hand(self):
        idle = self.clips_idle()
        base = max(self.count(f, (7,), (2,)) for f in idle)                # the forearm's own sleeve in the idle
        for slot in GAITS:
            worst = dict(hand_body=0, hand_other=0, fore_body=0)
            for f in self.clips[slot][:-1]:
                mats, w = self.body.world(f)
                worst['hand_body'] = max(worst['hand_body'], self.body.count(mats, w, (8, 9, 10, 11), BODY), self.body.count(mats, w, (14, 15, 16, 17), BODY))
                worst['hand_other'] = max(worst['hand_other'], self.body.count(mats, w, (8, 9, 10, 11), (12, 13, 14, 15, 16, 17)),
                                          self.body.count(mats, w, (14, 15, 16, 17), (6, 7, 8, 9, 10, 11)))
                worst['fore_body'] = max(worst['fore_body'], self.body.count(mats, w, (7,), (2,)), self.body.count(mats, w, (13,), (2,)))
            self.assertLessEqual(worst['hand_body'], 9, slot)  # a few vertices graze the hump while a hand swings in
            self.assertEqual(worst['hand_other'], 0, slot)
            self.assertLessEqual(worst['fore_body'], base, slot)

    def clips_idle(self):
        return animsheet.slot_frames(self.new, NB, 0)[0]

    def count(self, frame, a, b):
        mats, w = self.body.world(frame)
        return self.body.count(mats, w, a, b)

    def test_no_joint_jumps(self):
        for slot in GAITS:
            for b, steps in self.report[slot]['steps'].items():
                median = float(np.median(steps))
                self.assertLessEqual(max(steps), max(4.0 * median, 8.0), (slot, b))

    def test_arm_targets_stay_inside_the_arms_reach(self):
        for slot in GAITS:
            clip = drag.Clip(self.rig, slot)                              # two_bone raises on a target out of reach, nothing is clamped
            reach = [d for _, _, d in clip.reach_log]
            lo, hi = abs(clip.l1 - clip.l2) + drag.REACH_MARGIN[0], drag.REACH_MARGIN[1] * (clip.l1 + clip.l2)
            self.assertTrue(all(lo <= d <= hi for d in reach), slot)
            self.assertGreater(max(reach) - min(reach), 60, slot)         # the arm really folds and stretches

    def test_head_jaw_and_tail_follow_late(self):
        for slot in GAITS:
            frames = self.clips[slot][:-1]
            for bone, least in ((4, 40), (5, 30), (3, 20), (2, 12)):
                span = max(np.ptp([f[bone][3 + c] for f in frames]) for c in range(3))
                self.assertGreaterEqual(span, least, (slot, bone))          # 4096 units a turn

    def test_events_keep_the_eyes_and_sound_at_each_landing(self):
        for slot in GAITS:
            events = animsheet.slot_frames(self.new, NB, slot)[2]
            self.assertEqual(sum(1 for e in events if e[1] == 'tex'), 2, slot)
            self.assertEqual([e[0] for e in events if e[1] == 'sound'], drag.landings(slot), slot)


if __name__ == '__main__':
    unittest.main()
