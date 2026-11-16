"""Bilateral QA catches overlap independently of an already-bad idle."""
import unittest
import numpy as np
from tools.models import battle_qa as q, field_sides_qa as sides


class FieldSidesQA(unittest.TestCase):
    def test_candidate_requires_depth_and_contact_on_the_same_sample(self):
        row = dict(depth=[0, 20], triangles=[4, 0], max_centroid=0)
        self.assertFalse(sides.candidate(row, 100))
        row['triangles'][1] = 1
        self.assertTrue(sides.candidate(row, 100))

    def rig(self, cross=False):
        # Two mirrored rigid triangular wings, sharing the moving body bone.
        P = np.zeros((3, 4, 9)); P[..., :3] = 4096
        P[:, 2, 6], P[:, 3, 6] = 10, -10
        local = {2: [[0, 0, 0], [5, 0, 5], [0, 5, 5]],
                 3: [[0, 0, 0], [-5, 0, 5], [0, 5, 5]]}
        rig = q.Rig([-1, 0, 1, 1], local, [(2, [0, 1, 2]), (3, [0, 1, 2])], {0: (P.copy(), 0)})
        if cross:
            P[1, 2, 6], P[1, 3, 6] = -10, 10
        return rig, P

    def test_finds_reflected_pair_and_clear_wings(self):
        rig, P = self.rig()
        self.assertEqual(sides.pairs(rig), [(2, 3, 1)])
        self.assertEqual(sides.measure(q.Clip(rig, P))[0]['max_depth'], 0)

    def test_detects_a_side_swap_on_just_one_frame(self):
        rig, P = self.rig(cross=True)
        row = sides.measure(q.Clip(rig, P))[0]
        self.assertEqual(row['depth'], [0, 10, 0])
        self.assertGreater(row['centroid'][1], 0)

    def test_an_already_crossed_idle_is_not_a_clearance_allowance(self):
        rig, P = self.rig()
        rig.local[2][:, 0] -= 30
        rig.local[3][:, 0] += 30
        self.assertGreater(sides.measure(q.Clip(rig, P))[0]['max_depth'], 15)

    def test_plane_follows_body_and_root_turns(self):
        rig, P = self.rig()
        P[:, 1, 6] = [0, 70, -80]
        P[:, 1, 4] = [0, 1024, 2048]
        P[:, 0, 4] = [0, 512, 1024]
        self.assertAlmostEqual(sides.measure(q.Clip(rig, P))[0]['max_depth'], 0)

    def test_checks_outer_feather_against_opposite_root_too(self):
        rig, P = self.rig()
        P = np.concatenate([P, P[:, 2:4].copy()], axis=1)
        local = dict(rig.local)
        local[4], local[5] = local[2], local[3]
        rig = q.Rig([-1, 0, 1, 1, 2, 3], local, [], {0: (P, 0)})
        self.assertEqual(sides.pairs(rig), [(2, 3, 1), (2, 5, 1), (4, 3, 1), (4, 5, 1)])

    def test_thirds_detect_crossing_between_clear_endpoint_poses(self):
        rig, P = self.rig()
        # Rotate a long feather 180 degrees; its tip passes the mid-plane
        # during the engine's Euler interpolation despite clear endpoints.
        rig.local[2] = np.array([[0, 0, 0], [0, 0, 30], [0, 2, 30]], float)
        P[1:, 2, 4] = 2048
        rig._clips[2] = P, 0
        self.assertEqual(sides.measure(q.Clip(rig, P), [(2, 3, 1)])[0]['max_depth'], 0)
        self.assertGreater(sides.measure(sides.samples(rig, 2), [(2, 3, 1)])[0]['max_depth'], 10)


if __name__ == '__main__':
    unittest.main()
