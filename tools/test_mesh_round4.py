"""Equivalence and the scope of translation-floor certificates."""
import sys
from pathlib import Path
import unittest
import numpy as np
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from tools.models.mesh_round4 import sparse_crossing, translation_constraints, translation_cover, verify_cover
from tools.models.field_animations.meshclash import crossing


class Crossings(unittest.TestCase):
    def test_near_endpoint_uses_the_existing_detectors_reduction_order(self):
        # A real posed boundary: einsum dot products round differently from
        # the detector's multiply/sum and can add a spurious deep crossing.
        a = np.array([[[-.4547174162680149, -67.6360047747649, -66.00300796842821],
                       [31.69454901312043, -85.22299614723046, -70.37592490304057],
                       [-.3467426622682572, -76.65517285116624, -19.102656704689025]]])
        b = np.array([[[-.703150048685705, -37.07822524000851, -44.810297250429386],
                       [-.34171957922895785, -81.11289230636365, -70.08513581313849],
                       [-25.266187700685926, -90.67671010814071, -78.70512873174853]]])
        self.assertEqual(sparse_crossing(a,b), crossing(a,b,symmetric=True))

    def test_sparse_matches_existing_symmetric_detector(self):
        rng = np.random.default_rng(19)
        for integral in (False, True):
            for _ in range(20):
                a,b = rng.normal(size=(15,3,3))*30,rng.normal(size=(20,3,3))*30
                if integral:
                    a,b = a.round().astype(int),b.round().astype(int)
                # Include zero-area triangles and exact shared corners.
                a[0] = 0
                b[0,0] = a[1,0]
                expected = crossing(a,b,symmetric=True)
                actual = sparse_crossing(a,b)
                self.assertEqual(actual[0],expected[0])
                self.assertAlmostEqual(actual[1],expected[1])
                self.assertEqual(sparse_crossing(b,a)[0],actual[0])
                self.assertAlmostEqual(sparse_crossing(b,a)[1],actual[1])

    def test_separated_and_empty_arrays(self):
        a = np.array([[[0.,0,0],[1,0,0],[0,1,0]]])
        self.assertEqual(sparse_crossing(a,a+10),(0,0.))
        self.assertEqual(sparse_crossing(a,a[:0]),(0,0.))


class Floor(unittest.TestCase):
    def pair(self):
        return np.array([[[0.,0,-30],[0,0,30],[0,30,0]]]), np.array([[[-30.,-30,0],[30,-30,0],[0,30,0]]])

    def test_affine_constraints_match_translated_geometry_in_both_directions(self):
        a,b = self.pair()
        z,c = translation_constraints(a,b)
        for delta in (np.array([2.,-3,4]),np.array([-3.,1,-2])):
            shifted,_ = translation_constraints(a+delta,b)
            np.testing.assert_allclose(z+np.einsum('nki,i->nk',c,delta),shifted,atol=1e-7)

    def test_cover_certifies_a_box_but_rejects_separating_translations(self):
        a,b = self.pair()
        z,c = translation_constraints(a,b)
        tree = translation_cover(z,c,np.zeros(3),2)
        self.assertIsNotNone(tree)
        self.assertTrue(verify_cover(a,b,tree,2))
        self.assertFalse(verify_cover(a,b,tree,3))
        self.assertFalse(verify_cover(a+100,b,tree,2))
        self.assertIsNone(translation_cover(z,c,np.array([100.,0,0]),2))
        # A larger box includes both crossing and separated configurations.
        self.assertIsNone(translation_cover(z,c,np.zeros(3),100))

    def test_coplanar_contact_has_no_strict_certificate(self):
        a,_ = self.pair()
        z,c = translation_constraints(a,a)
        self.assertIsNone(translation_cover(z,c,np.zeros(3),1,depth=6))

if __name__ == '__main__':
    unittest.main()
