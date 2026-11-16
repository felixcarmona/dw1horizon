"""Budget-neutral quad repair and independent geometry/depth diagnostics."""
import copy
import sys
import unittest
from unittest import mock
import hashlib
from pathlib import Path

import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
import mmd
from tools.test_meshcheck import model, box_object
from tools.models import mesh_stability as S, meshcheck as MC, mesh_glitch as G


def animated(m, bones):
    pose = [[4096]*3 + [0]*6 for _ in bones]
    m.anims.anims = [mmd.encode_anim([pose, pose], len(bones), 0, [])]
    m.anims.table = [0]
    return m, bones


class Stability(unittest.TestCase):
    def bent(self, spare=0):
        ob, verts, norms = box_object()
        # Separate one bent quad, then add unreferenced pool entries. They
        # model the final rig's grounding landmarks, available only at the end.
        ob.prims = ob.prims[:1]
        verts = [(0,0,0,0),(100,0,0,0),(0,100,0,0),(100,100,30,0)]
        d = ob.prims[0].decode(); d['verts'] = list(range(4))
        ob.prims = [mmd.Prim.encode(d)]
        verts += [(i,0,0,0) for i in range(spare)]
        return animated(*model((ob, verts, norms[:1])))

    def test_split_preserves_both_gpu_triangles_and_attributes(self):
        m,bones = self.bent(20)
        before = MC.Model(m,bones)
        out,proof = S.apply(m.build(), bones)
        after = MC.Model(out,bones)
        self.assertTrue(proof['applied'])
        self.assertEqual(proof['split'],1)
        self.assertLessEqual(proof['resident_after'],proof['resident_before'])
        np.testing.assert_array_equal(before.tri_array(before.local),after.tri_array(after.local))
        self.assertFalse(S.bent_quads(after.m))

    def test_refuses_unfunded_repair(self):
        m,bones=self.bent()
        data=m.build();out,proof=S.apply(data,bones)
        self.assertEqual(out,data)
        self.assertFalse(proof['applied'])
        self.assertEqual(proof['remaining'],1)

    def test_planar_box_keeps_exact_bytes(self):
        m,bones=animated(*model(box_object()))
        data=m.build()
        self.assertEqual(S.apply(data,bones)[0],data)

    def test_packet_growth_is_bounded(self):
        m,bones=self.bent(20)
        data=m.build()
        self.assertEqual(S.apply(data,bones,packet_growth=0)[0],data)

    def test_adjacent_faces_do_not_count_as_depth_overlaps(self):
        T=np.array([[[0,0],[2,0],[0,2]],[[2,0],[2,2],[0,2]]],float)
        a,b=G.overlap_pairs(T,np.array([0,1]),np.array([0,0]),np.array([[0,1,2],[1,3,2]]))
        self.assertEqual(len(a),0)

    def test_sat_rejects_disjoint_triangles_with_overlapping_boxes(self):
        T=np.array([[[0,0],[2,0],[0,2]],[[2,2],[2,1.1],[1.1,2]]],float)
        a,b=G.overlap_pairs(T,np.array([0,1]),np.array([0,1]),np.array([[0,1,2],[0,1,2]]))
        self.assertEqual(len(a),0)

    def test_static_overlap_can_tie_but_cannot_flip(self):
        m,bones=self.bent()
        # Distinct objects on the same plane, with distinct primitive identity.
        part=box_object()[0:3]
        m,bones=model(part,copy.deepcopy(part))
        mc=MC.Model(m,bones)
        r=G.depth_probe(mc,[mc.rest(),mc.rest()])
        self.assertGreater(r['ties'],0)
        self.assertEqual(r['flips'],0)

    def test_order_flip_is_measured_only_between_overlapping_poses(self):
        part=box_object()
        m,bones=model(part,copy.deepcopy(part))
        mc=MC.Model(m,bones)
        a,b=copy.deepcopy(mc.rest()),copy.deepcopy(mc.rest())
        a[2][8]=-1; b[2][8]=1
        r=G.depth_probe(mc,[a,b])
        self.assertGreater(r['flips'],0)
        self.assertGreater(r['tied_flips'],0)

    def test_native_control_envelope_passes_controls_and_flags_excess(self):
        a={k:0.1 for k in G.METRICS}
        b={k:0.2 for k in G.METRICS}
        limits=G.calibrate({'1':a,'2':b})
        self.assertEqual(G.classify(a,limits)['verdict'],'pass')
        self.assertEqual(G.classify(b,limits)['verdict'],'pass')
        bad={**b,'bent_risk':0.4}
        self.assertEqual(G.classify(bad,limits)['flags'],['bent_risk'])

    def test_identical_shading_is_flattened_but_distinct_shading_is_kept(self):
        for mode, flag in ((0x3c,0),(0x3d,1),(0x38,4),(0x38,0)):
            nv,nu,nc,nn=mmd.prim_shape(mode,flag)
            d=dict(mode=mode,flag=flag,verts=list(range(nv)),norms=list(range(nn)),
                   uv=[(i*7,i*11) for i in range(nu)],
                   colors=[(42,84,126,mode)]*nc,cba=31232,tsb=5)
            ob=mmd.TMDObject(); ob.prims=[mmd.Prim.encode(d)]
            m,bones=model((ob,[(0,0,0,0)]*nv,[(0,0,-4096,0)]*nn))
            self.assertEqual(S.flatten_identical_shading(m),1)
            after=m.tmd.objects[0].prims[0].decode()
            self.assertFalse(after['mode']&16)
            self.assertEqual(after['verts'],d['verts'])
            self.assertEqual(after['uv'],d['uv'])
            self.assertTrue(all(c[:3]==(42,84,126) for c in after['colors']))
        # A single different normal must retain Gouraud interpolation.
        d=dict(mode=0x3c,flag=0,verts=list(range(4)),norms=list(range(4)),
               uv=[(0,0)]*4,cba=31232,tsb=5)
        ob=mmd.TMDObject(); ob.prims=[mmd.Prim.encode(d)]
        m,bones=model((ob,[(0,0,0,0)]*4,[(0,0,-4096,0)]*3+[(0,4096,0,0)]))
        self.assertEqual(S.flatten_identical_shading(m),0)

    def test_alternate_release_pin_is_preserved_without_species_exceptions(self):
        m,bones=self.bent(20)
        data=m.build()
        table={'imports@alternate':{'999':[hashlib.sha1(data).hexdigest(),'texture']}}
        with mock.patch.object(S.json,'loads',return_value=table):
            out,proof=S.apply_provider(data,bones)
        self.assertEqual(out,data)
        self.assertEqual(proof['source_variant'],'imports@alternate')
        self.assertTrue(proof['deferred'])

    def test_unused_grounding_landmarks_do_not_change_geometry_normalization(self):
        m,bones=self.bent(20)
        a=G.geometry(MC.Model(m,bones))
        m.tmd.verts[-1]=(0,30000,0,0)
        b=G.geometry(MC.Model(m,bones))
        self.assertEqual(a,b)


if __name__=='__main__':unittest.main()
