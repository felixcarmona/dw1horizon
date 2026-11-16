"""The residual floor must count retained opposite layers, not co-facing ones."""
import copy
import unittest

from tools.models import mesh_ga as GA, meshcheck as MC, mesh_glitch as G
from tools.test_meshcheck import model
import mmd


class OppositeFaceFloor(unittest.TestCase):
    def pair(self, opposite=True, separate_bones=False):
        verts = [(0, 0, 0, 0), (100, 0, 0, 0), (0, 100, 0, 0)]
        norms = [(0, 0, 4096, 0), (0, 0, -4096, 0)]
        prim = dict(mode=0x24, flag=0, verts=[0, 1, 2], norms=[0],
                    uv=[(0, 0), (100, 0), (0, 100)], cba=0, tsb=0)
        a = mmd.TMDObject()
        a.prims = [mmd.Prim.encode(prim)]
        second = copy.deepcopy(prim)
        second['verts'] = [3, 5, 4] if opposite else [3, 4, 5]
        second['norms'] = [1 if opposite else 0]
        second['uv'] = [(1, 1), (1, 101), (101, 1)]
        if separate_bones:
            second['verts'] = [v-3 for v in second['verts']]
            b = mmd.TMDObject()
            b.prims = [mmd.Prim.encode(second)]
            m, bones = model((a, verts, norms), (b, verts, norms))
        else:
            a.prims.append(mmd.Prim.encode(second))
            m, bones = model((a, verts*2, norms))
        return MC.Model(m, bones)

    def test_opposite_surfaces_match_legacy_area_and_keep_both_windings(self):
        m = self.pair()
        raw = m.m.build()
        floor = GA.opposite_floor(m)
        self.assertEqual(floor['count'], 1)
        self.assertEqual(floor['normalized_area'], .5)
        self.assertEqual(floor['normalized_area'], G.geometry(m)['coplanar_area'])
        self.assertEqual(G.coplanar_details(m)['cofacing_pairs'], 0)
        self.assertEqual(raw, m.m.build())

    def test_cofacing_layers_are_not_an_opposite_face_floor(self):
        m = self.pair(opposite=False)
        self.assertEqual(GA.opposite_floor(m)['count'], 0)
        self.assertEqual(G.coplanar_details(m)['cofacing_pairs'], 1)

    def test_interpart_overlap_is_excluded_from_local_surface_floor(self):
        m = self.pair(separate_bones=True)
        self.assertEqual(GA.opposite_floor(m)['count'], 0)
        self.assertEqual(G.geometry(m)['coplanar_area'], .5)


if __name__ == '__main__':
    unittest.main()
