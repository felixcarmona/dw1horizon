"""Synthetic geometry and texture regressions; no player data required."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import copy

sys.path[:0] = [str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
import numpy as np
from tools.models.audit_reduction import geometry,compare_parts,triangle_distances,views,robust_affine


def surface(points,uv=None,row=0,color=0x7fff):
    pal = np.array([[color]*16,[0x001f]*16],np.uint16)
    rgb = np.stack([(pal&31)<<3,(pal>>5&31)<<3,(pal>>10&31)<<3],-1).astype(np.uint8)
    return SimpleNamespace(points=np.array(points,float).reshape(-1,3,3),
                           tris=[(0,0,i,(),uv,row,False,(200,200,200)) for i in range(len(points))],
                           tex=(np.zeros((16,16),np.uint8),pal,rgb))


class ReductionAuditTests(unittest.TestCase):
    tetra = [[(0,0,0),(0,10,0),(10,0,0)],[(0,0,0),(10,0,0),(0,0,10)],
             [(0,0,0),(0,0,10),(0,10,0)],[(10,0,0),(0,10,0),(0,0,10)]]

    def test_closed_volume_and_new_hole(self):
        a,b = surface(self.tetra),surface(self.tetra[:-1])
        result, = compare_parts(a,b,.001)
        self.assertAlmostEqual(result['source']['volume'],1000/6)
        self.assertIsNone(result['target']['volume'])
        self.assertIsNone(result['volume_loss'])
        self.assertEqual(result['new_boundary_edges'],3)
        self.assertGreater(result['uncovered_area'],0)

    def test_native_open_surface_is_not_a_new_hole(self):
        a = surface(self.tetra[:1])
        result, = compare_parts(a,a,.001)
        self.assertEqual(result['new_boundary_edges'],0)
        self.assertEqual(result['uncovered_area'],0)
        self.assertIsNone(result['source']['volume'])

    def test_missing_whole_part_and_degenerate(self):
        a,b = surface(self.tetra),surface([])
        result, = compare_parts(a,b,.001)
        self.assertAlmostEqual(result['uncovered_fraction'],1)
        self.assertEqual(geometry([[(0,0,0)]*3])['degenerate'],1)

    def test_palette_uv_and_transparency(self):
        uv = [(1,1),(8,1),(1,8)]
        a = surface(self.tetra[:1],uv)
        for b,field in [(surface(self.tetra[:1],uv,row=1),'color_mismatch_area'),
                        (surface(self.tetra[:1],uv,color=0),'opaque_to_clear_area'),
                        (surface(self.tetra[:1],uv,color=0x8000),'opaque_to_black_area'),
                        (surface(self.tetra[:1],[(20,20)]*3),'invalid_texture_area'),
                        (surface(self.tetra[:1]),'missing_uv_area')]:
            with self.subTest(field=field):
                result, = compare_parts(a,b,.001)
                self.assertGreater(result[field],0)
        result, = compare_parts(a,a,.001)
        self.assertEqual(result['color_mismatch_area'],0)

    def test_distance_degenerate_and_projection(self):
        triangles = np.array([[(0,0,0),(10,0,0),(0,10,0)],[(0,0,0)]*3],float)
        np.testing.assert_allclose(triangle_distances(np.array([2,2,3]),triangles),[9,17])
        np.testing.assert_allclose(triangle_distances(np.array([20,0,0]),triangles),[100,400])

    def test_silhouette_uses_shared_camera(self):
        a,b = surface(self.tetra),surface(np.array(self.tetra)*.5)
        metrics,_ = views(a,b,size=40)
        self.assertTrue(any(v['silhouette'] > .2 for v in metrics))
        same,_ = views(a,a,size=40)
        self.assertTrue(all(v['silhouette'] == 0 for v in same))

    def test_new_imports_do_not_delete_small_faces_but_frozen_replay_is_stable(self):
        import import_batch,dw3mmd,dw2mmd,rigfix,mmdport,meshfix
        bone = dict(parent=-1,offset=(0,0,0),rest=mmdport.IDENTITY_Q,
                    verts=[(0,0,0),(10,0,0),(0,10,0)],norms=[(0,0,4096)],
                    prims=[dict(verts=[0,1,2],norms=[0]*3,uvs=[(0,0),(1,0),(0,1)],row=0,semi=False) for _ in range(714)])
        model = mmdport.Model('X',[bone],bytearray(256*128),[[0]*16],{})
        with patch.object(dw3mmd,'load',side_effect=lambda *a,**k:copy.deepcopy(model)), \
                patch.object(dw3mmd,'merge_quads',return_value=0), \
                patch.object(dw3mmd,'merge_normals',return_value=0), \
                patch.object(dw2mmd,'_dw2'),patch.object(dw2mmd,'hub_roots',return_value=None), \
                patch.object(rigfix,'on_load'),patch.object(meshfix,'apply',return_value={}) as reduce, \
                patch.object(meshfix,'spec_params',return_value={'prims':713}):
            current,_ = import_batch.load_source(dict(name='X',game='dw3',model='X'),log=lambda *a:None)
            self.assertFalse(hasattr(current,'dropped_faces'))
            reduce.assert_called_once()
            reduce.reset_mock()
            legacy,_ = import_batch.load_source(dict(name='X',game='dw3',model='X'),log=lambda *a:None,
                                                legacy_face_drop=True)
            self.assertEqual(legacy.dropped_faces,1)
            self.assertEqual(meshfix.prim_count(legacy),713)
            reduce.assert_not_called()

    def test_disconnected_detail_cannot_be_erased_by_an_edge_collapse(self):
        import meshfix,mmdport
        verts = [(0,0,0),(10,0,0),(0,10,0),(0,0,10),
                 (100,0,0),(101,0,0),(100,1,0)]
        indices = [(0,2,1),(0,1,3),(0,3,2),(1,2,3),(4,5,6)]
        bone = dict(parent=-1,offset=(0,0,0),rest=mmdport.IDENTITY_Q,verts=verts,norms=[],
                    prims=[dict(verts=list(t),norms=None,uvs=None,row=0) for t in indices])
        model = mmdport.Model('detail',[bone],bytearray(32768),[[0]*16],{})
        legacy = meshfix.Mesh(model,0,{},preserve_components=False)
        guarded = meshfix.Mesh(model,0,{})
        # The old per-BONE four-face floor permits this: five total faces,
        # but the fifth face is a whole independent detail component.
        self.assertIsNotNone(legacy.collapse_cost(4,5,.3,.3))
        self.assertIsNone(guarded.collapse_cost(4,5,.3,.3))
        legacy.collapse(4,5)
        self.assertFalse(legacy.faces[-1].alive)
        self.assertTrue(guarded.faces[-1].alive)

    def test_tetrahedron_cannot_collapse_into_coincident_opposite_faces(self):
        import meshfix,mmdport
        bone = dict(parent=-1,offset=(0,0,0),rest=mmdport.IDENTITY_Q,
                    verts=[(0,0,0),(10,0,0),(0,10,0),(0,0,10)],norms=[],
                    prims=[dict(verts=list(t),norms=None,uvs=None,row=0)
                           for t in [(0,2,1),(0,1,3),(0,3,2),(1,2,3)]])
        model = mmdport.Model('tetra',[bone],bytearray(32768),[[0]*16],{})
        guarded = meshfix.Mesh(model,0,{})
        guarded.component_floor = [0]  # Test the full link, independently of the face floor.
        self.assertIsNone(guarded.collapse_cost(0,1,.3,.3))

    def test_proportion_fit_tolerates_collapse_outliers_and_rejects_ambiguity(self):
        rng = np.random.default_rng(2)
        x = rng.normal(size=(40,3))*100
        expected = x*np.array([.8,1.5,1.1])+[30,-100,50]
        y = expected.copy()
        y[:8] += 1000
        fit = robust_affine(x,y,x)
        self.assertIsNotNone(fit)
        transform,_,support = fit
        np.testing.assert_allclose(np.column_stack([x,np.ones(len(x))])@transform,expected,atol=1e-8)
        self.assertGreaterEqual(support,.8)
        y = expected.copy()
        y[:20] += 1000
        self.assertIsNone(robust_affine(x,y,x))


if __name__ == '__main__':
    unittest.main()
