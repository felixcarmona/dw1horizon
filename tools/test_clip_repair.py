"""tools/models/clip_repair.py: the repair operations of a rebuilt clip leave what they do not name as it was."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'tools')]

from tools.models import clip_repair  # noqa: E402

PARENTS = [-1, 0, 1, 2]


def clip(n=12):
    return [[[4096, 4096, 4096, 0, 0, 0, 0, -t, 0],
             [4096, 4096, 4096, 40 * t, 0, 0, 0, -300, 0],
             [4096, 4096, 4096, 0, 20 * t, -10 * t, 0, -200, 0],
             [4096, 4096, 4096, 100, 0, 30 * t, 50, -100, 0]] for t in range(n)]


class ClipRepairTest(unittest.TestCase):
    def test_no_ops_is_exact(self):
        self.assertEqual(clip_repair.apply_ops(clip(), PARENTS, []), clip())

    def test_wave_moves_only_its_bone_and_closes_the_loop(self):
        out = clip_repair.apply_ops(clip(13), PARENTS, [{'op': 'wave', 'bone': 3, 'axis': 'y', 'deg': 20, 'cycles': 2}])
        for a, b in zip(out, clip(13)):
            for bone in (0, 1, 2):
                self.assertEqual(a[bone], b[bone])
            self.assertEqual(a[3][:3] + a[3][6:], b[3][:3] + b[3][6:])
        self.assertEqual(out[0][3], clip(13)[0][3])
        self.assertEqual(out[-1][3], clip(13)[-1][3])
        self.assertNotEqual(out[1][3][3:6], clip(13)[1][3][3:6])

    def test_fit_rig_scales_offsets_and_keeps_rotations(self):
        frames = clip(4)
        source = frames[0]
        rig = [list(b) for b in source]
        rig[2][0:3] = [10240, 10240, 10240]
        rig[2][7] = -100          # offset -200 -> -100
        out = clip_repair.fit_rig(frames, source, rig)
        for pose, old in zip(out, frames):
            self.assertEqual(pose[0], old[0])
            self.assertEqual(pose[2][0:3], [10240, 10240, 10240])
            self.assertEqual(pose[2][3:6], old[2][3:6])
            self.assertAlmostEqual(pose[2][7], -100)

    def test_turn_changes_only_its_bone(self):
        out = clip_repair.apply_ops(clip(), PARENTS, [{'op': 'turn', 'bone': 2, 'axis': 'x', 'deg': 15}])
        for a, b in zip(out, clip()):
            for bone in (0, 1, 3):
                self.assertEqual(a[bone], b[bone])
            self.assertEqual(a[2][:3] + a[2][6:], b[2][:3] + b[2][6:])
        self.assertNotEqual([p[2] for p in out], [p[2] for p in clip()])

    def test_turn_envelope_outside_is_exact(self):
        ops = [{'op': 'turn', 'bone': 1, 'axis': [0, 0, 1], 'deg': 20, 'ticks': [4, 5, 6, 8]}]
        out = clip_repair.apply_ops(clip(), PARENTS, ops)
        self.assertEqual(out[:4], clip()[:4])
        self.assertEqual(out[9:], clip()[9:])

    def test_damp_keep_one_and_zero(self):
        self.assertEqual(clip_repair.apply_ops(clip(), PARENTS, [{'op': 'damp', 'bone': 1, 'keep': 1.0}]), clip())
        out = clip_repair.apply_ops(clip(), PARENTS, [{'op': 'damp', 'bone': 1, 'keep': 0.0, 'to': 'first'}])
        self.assertTrue(all(p[1][3:6] == [0, 0, 0] for p in out))

    def test_damp_to_the_first_pose_closes_a_loop_seam(self):
        n = 12
        out = clip_repair.apply_ops(clip(n), PARENTS, [{'op': 'damp', 'bone': 2, 'keep': 0.0, 'to': 'first',
                                                       'ticks': [6, n - 1, n - 1, n - 1]}])
        self.assertEqual(out[-1][2][3:6], out[0][2][3:6])
        self.assertTrue(all(a == b for a, b in zip(out[:6], clip(n))))
    def test_smooth_spreads_a_snap_and_keeps_the_rest(self):
        frames = clip()
        for t in range(6, 12):
            frames[t][1][3] += 600                   # a one-tick snap on bone 1 between ticks 5 and 6
        out = clip_repair.apply_ops(frames, PARENTS, [{'op': 'smooth', 'bone': 1, 'passes': 2}])
        step = lambda f: max(abs(f[t + 1][1][3] - f[t][1][3]) for t in range(len(f) - 1))
        self.assertLess(step(out), step(frames))
        for a, b in zip(out, frames):
            for bone in (0, 2, 3):
                self.assertEqual(a[bone], b[bone])
        self.assertEqual(clip_repair.apply_ops(frames, PARENTS, [{'op': 'smooth', 'bone': 1, 'weight': 0.0}]), frames)
        ops = [{'op': 'smooth', 'bone': 1, 'passes': 2, 'ticks': [4, 5, 6, 8]}]
        out = clip_repair.apply_ops(frames, PARENTS, ops)
        self.assertEqual(out[:4], frames[:4])
        self.assertEqual(out[9:], frames[9:])

    def test_mirror_copies_the_twin_mirrored_and_shifted(self):
        frames = clip()
        out = clip_repair.apply_ops(frames, PARENTS, [{'op': 'mirror', 'bone': 3, 'from': 2, 'shift': 2}])
        for t in range(len(frames)):
            u = min(t + 2, len(frames) - 1)
            rx, ry, rz = frames[u][2][3:6]
            self.assertEqual(out[t][3][3:6], [rx, -ry, -rz])
            for bone in (0, 1, 2):
                self.assertEqual(out[t][bone], frames[t][bone])
            self.assertEqual(out[t][3][:3] + out[t][3][6:], frames[t][3][:3] + frames[t][3][6:])
        loop = [[list(b) for b in p] for p in frames]
        loop[-1] = [list(b) for b in loop[0]]
        out = clip_repair.apply_ops(loop, PARENTS, [{'op': 'mirror', 'bone': 3, 'from': 2, 'shift': 3}])
        self.assertEqual(out[-1][3][3:6], out[0][3][3:6])
        self.assertEqual(out[len(loop) - 4][3][3:6], [loop[0][2][3], -loop[0][2][4], -loop[0][2][5]])

    def test_wave_sways_one_bone_and_closes_a_loop(self):
        frames = clip(13)
        frames[-1] = [list(b) for b in frames[0]]
        out = clip_repair.apply_ops(frames, PARENTS, [{'op': 'wave', 'bone': 2, 'axis': 'y', 'deg': 8, 'cycles': 2}])
        self.assertEqual(out[0], frames[0])
        self.assertEqual(out[-1], frames[-1])
        for bone in (0, 1, 3):
            self.assertEqual([p[bone] for p in out], [p[bone] for p in frames])
        self.assertNotEqual([p[2] for p in out[1:-1]], [p[2] for p in frames[1:-1]])
        self.assertEqual(clip_repair.apply_ops(frames, PARENTS, [{'op': 'wave', 'bone': 2, 'axis': 'y', 'deg': 0}]), frames)

    def test_lift_moves_a_body_bone_only(self):
        out = clip_repair.apply_ops(clip(), PARENTS, [{'op': 'lift', 'bone': 1, 'up': 25}])
        self.assertTrue(all(a[1][7] == b[1][7] - 25 and a[0] == b[0] for a, b in zip(out, clip())))
        with self.assertRaises(ValueError):
            clip_repair.apply_ops(clip(), PARENTS, [{'op': 'lift', 'bone': 0, 'up': 5}])


if __name__ == '__main__':
    unittest.main()
