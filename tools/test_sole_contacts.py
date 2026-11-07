"""Contact constraints on a scaled rig, independent of private model artifacts."""
import copy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import mmd
from tools.models.field_animations.sole_contacts import bake, inverse3, linear_solve


class SoleContacts(unittest.TestCase):
    def test_affine_inverse_keeps_scaled_coordinates(self):
        matrix = [[1.2, .1, 0], [0, .9, -.2], [.3, 0, 1.1]]
        inverse = inverse3(matrix)
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(sum(matrix[i][k]*inverse[k][j] for k in range(3)), float(i == j))

    def test_idle_breathing_keeps_both_sole_axes_flat_and_planted(self):
        skeleton = [[-1,-1], [0,0], [1,1], [2,2], [3,3]]
        pose = [[4096]*3+[0]*6 for _ in skeleton]
        pose[1][:3] = [4915]*3
        pose[1][7] = -200
        pose[3][6:9] = [0,60,-40]
        pose[4][6:9] = [0,60,40]
        frames = [copy.deepcopy(pose) for _ in range(9)]
        for t,p in enumerate(frames):
            p[1][3] = [0,4,8,4,0,-4,-8,-4,0][t]
            p[1][7] += [0,1,2,3,4,3,2,1,0][t]
        vertices = [[-30,51,-100,0],[30,51,-100,0],[-30,51,50,0],[30,51,50,0],[0,0,0,0]]
        model = SimpleNamespace(type=998, tmd=SimpleNamespace(obj_verts=lambda _: vertices))
        cfg = dict(carrier=1,feet=[4],legs=[[2,3,4,4,0,0]],rest_slot=2,
                   sole_contacts=dict(sole=51,heel=50,toe=-100,profiles={}))
        with patch.object(mmd,'exe',return_value=SimpleNamespace(skeleton={998:skeleton})), \
             patch('tools.models.field_animations.sole_contacts.animsheet.slot_frames',return_value=([pose],0,[])):
            result = bake(model,frames,skeleton,cfg,0)
            soles = []
            for p in result:
                matrix = mmd.bone_matrices(model,p)[4]
                points = [[sum(matrix[i][j]*v[j] for j in range(3))+matrix[i][3] for i in range(3)] for v in vertices[:4]]
                self.assertLess(max(v[1] for v in points)-min(v[1] for v in points),1.5)
                self.assertLess(max(abs(v[1]) for v in points),2)
                soles.append(points)
            for first,last in zip(soles,soles[1:]):
                self.assertLess(max(abs(v[i]-w[i]) for v,w in zip(first,last) for i in (0,2)),2)
            self.assertEqual(result[0][1:],result[-1][1:])

    def test_nonuniform_carrier_is_rejected(self):
        pose = [[4096]*3+[0]*6, [4096,5000,4096]+[0]*6]
        cfg = dict(carrier=1,feet=[],legs=[],sole_contacts=dict(profiles={}))
        with self.assertRaisesRegex(ValueError,'uniformly scaled'):
            bake(None,[pose,pose],[[-1,-1],[0,0]],cfg,0)

    def test_contact_fit_pivots_its_normal_equations(self):
        matrix = [[0,2,1],[1,1,0],[2,0,3]]
        target = [3,-2,4]
        rhs = [sum(a*b for a,b in zip(row,target)) for row in matrix]
        for actual,expected in zip(linear_solve(matrix,rhs),target):
            self.assertAlmostEqual(actual,expected)


if __name__ == '__main__':
    unittest.main()
