#!/usr/bin/env python3
"""Asset-free tests of the deliberately limited triangle-crossing diagnostic."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
import motionquality as Q

class TriangleCrossings(unittest.TestCase):
    def test_cached_bounds_match_original_crossing_predicate(self):
        def original(A,B):
            if np.any(A.max((0,1))<B.min((0,1))) or np.any(B.max((0,1))<A.min((0,1))):return False
            for first,second in [(A,B),(B,A)]:
                for tri in first:
                    mask=np.all(second.max(1)>=tri.min(0),axis=1)&np.all(second.min(1)<=tri.max(0),axis=1)
                    if np.any(mask) and Q.edges_cross(tri,second[mask]):return True
            return False
        rng=np.random.default_rng(4391)
        for trial in range(120):
            a=rng.normal(size=(trial%9+1,3,3));b=rng.normal(size=(trial%7+1,3,3))+rng.normal(size=3)*2
            if trial%4==0:b[:,:,2]=0;a[:,:,2]=0
            if trial%5==0:b=np.concatenate([a[:1],b])
            self.assertEqual(Q.collide(a,b),original(a,b))

    def test_surfaces_cross(self):
        a=np.array([[[0.,0,0],[3,0,0],[0,3,0]]])
        b=np.array([[[.5,.5,-1],[.5,.5,1],[2,.5,0]]])
        self.assertTrue(Q.collide(a,b))

    def test_separated_parts_do_not_cross(self):
        a=np.array([[[0.,0,0],[3,0,0],[0,3,0]]])
        self.assertFalse(Q.collide(a,a+10))

    def test_coplanar_contact_is_outside_this_diagnostic(self):
        a=np.array([[[0.,0,0],[3,0,0],[0,3,0]]])
        self.assertFalse(Q.collide(a,a+.1*np.array([1,1,0])))

class MaterialRegions(unittest.TestCase):
    def test_rigid_material_region_remains_separate_from_touching_soft_mane(self):
        def prim(ids,palette):return NS(decode=lambda:dict(verts=ids,uv=[(0,0)]*3,cba=(488+palette)<<6))
        vertices=[(0,0,0),(3,0,0),(0,3,0),(10,0,0),(13,0,0),(10,3,0)]
        crossing=[(10.5,.5,-1),(10.5,.5,1),(12,.5,0)]
        mod=NS(tmd=NS(objects=[NS(prims=[prim([0,1,2],8),prim([3,4,5],4)]),NS(prims=[prim([0,1,2],0)])],obj_verts=lambda o:vertices if o==0 else crossing))
        sk=[(-1,-1),(0,0),(1,0)]
        local=Q.local_triangles(mod,sk,{'fangs':dict(bone=1,palettes=[8])})
        self.assertEqual(local['fangs'].shape,(1,3,3))
        matrices=[np.eye(4).tolist() for _ in sk]
        with patch.object(Q.M.mmd,'bone_matrices',return_value=matrices):
            self.assertEqual(Q.crossings(mod,local,[None],[['fangs',2]]),{})
            self.assertEqual(Q.crossings(mod,local,[None],[[1,2]]),{'1-2':[0]})
        with self.assertRaisesRegex(ValueError,'no triangles'):
            Q.local_triangles(mod,sk,{'missing':dict(bone=1,palettes=[7])})

if __name__=='__main__':unittest.main()
