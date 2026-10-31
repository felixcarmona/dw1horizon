"""Disc-free checks of rigid calibration and simultaneous support constraints."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numeric as np
import mmd
from tools.models.field_animations.metal_greymon_care import fit_piece, carrier_offsets, stationary_root


class MetalGreymonCare(unittest.TestCase):
    def test_registration_recovers_permuted_rigid_piece_with_different_pivot(self):
        vertices = np.array([[0,0,0],[8,1,2],[-2,12,1],[3,-4,15],[-4,3,-7],[7,9,11]])
        rotation = np.array(mmd.rot_matrix(100,-180,90))
        native = vertices @ rotation.T * 1.2 + [20,-30,40]
        q, center, origin, scale, error = fit_piece(vertices,native[[3,1,5,0,4,2]],rotation)
        self.assertLess(error,1e-8)
        self.assertAlmostEqual(scale,1.2)
        self.assertLess(float(np.max(np.abs(q-rotation))),1e-8)
        self.assertLess(float(np.max(np.abs((vertices-origin) @ q.T * scale+center-native))),1e-8)

    def test_stationary_native_action_removes_only_entity_translation_keys(self):
        from types import SimpleNamespace
        anim = SimpleNamespace(instrs=[
            {'op':'key','frame':3,'bones':[
                {'bone':0,'div':4,'vals':{'tx':40,'tz':-30,'ry':100}},
                {'bone':6,'div':4,'vals':{'rx':80}}]},
            {'op':'sound','frame':15,'bank':1,'note':2},
            {'op':'end'}])
        stationary_root(anim)
        self.assertEqual(anim.instrs[0]['bones'][0]['vals'],{'ry':100})
        self.assertEqual(anim.instrs[0]['bones'][1]['vals'],{'rx':80})
        self.assertEqual(anim.instrs[1],{'op':'sound','frame':15,'bank':1,'note':2})

    def test_support_gap_requires_lowering_carrier_instead_of_only_lifting(self):
        # The foot floats six units at a third. Two units of downward carrier
        # correction resolve it while the endpoints remain in the floor band.
        bounds = [(0,0,[(0,0,0),(1365,-6,-6),(2730,-6,-6),(4096,0,0)])]
        with self.assertRaises(ValueError):
            carrier_offsets(bounds,None)  # endpoints cannot move down by >=3
        bounds = [(0,0,[(0,-2,-2),(1365,-5,-5),(2730,-5,-5),(4096,-2,-2)])]
        path = carrier_offsets(bounds,None)
        self.assertTrue(any(d>0 for d in path))

    def test_loop_contact_closes_without_sacrificing_floor(self):
        bounds = [(0,0,[(0,3,3),(1365,3,3),(2730,3,3),(4096,3,3)])]*3
        path = carrier_offsets(bounds,0)
        self.assertEqual(path[0],path[-1])
        self.assertTrue(all(-6<=d<=-2 for d in path))

    def test_contact_can_close_after_a_non_looping_intro(self):
        bounds = [(0,0,[(0,0,0),(4096,0,0)]),
                  (0,0,[(0,3,3),(4096,3,3)]),
                  (0,0,[(0,3,3),(4096,3,3)])]
        path = carrier_offsets(bounds,1)
        self.assertEqual(path[1],path[-1])


if __name__=='__main__':
    unittest.main()
