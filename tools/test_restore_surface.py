"""Restore missing faces without changing a fitted pool or animation."""
import copy
from pathlib import Path
import sys
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import mmd
import mmdport
from tools.models.restore_surface import face, pool_mapping, restore
import numpy as np

try:
    import networkx
except ImportError:
    networkx = None


@unittest.skipIf(networkx is None,'offline maximum quad pairing requires networkx')
class RestoreSurface(unittest.TestCase):
    def fixture(self):
        bone = dict(parent=-1,offset=(0,0,0),rest=mmdport.IDENTITY_Q,
                    verts=[(0,0,0),(20,0,0),(0,20,0),(0,0,20)],norms=[(0,0,4096)],
                    prims=[dict(verts=list(t),norms=[0]*3,uvs=[(0,0),(4,0),(0,4)],row=0)
                           for t in [(0,1,2),(0,3,1),(0,2,3)]])
        source = mmdport.Model('source',[bone],bytearray(32768),[[0]*16],{})
        damaged = copy.deepcopy(source)
        damaged.bones[0]['prims'].pop()
        model = mmd.MMD()
        model.tmd = mmdport.build_tmd(damaged,log=lambda *a:None)
        model.anims = mmd.AnimSection()
        pose = [[4096]*3+[0]*6 for _ in range(2)]
        model.anims.anims = [mmd.encode_anim([pose,pose],2,0,[])]
        model.anims.table = [0]
        return source,model,mmdport.build_tim(source.idx,source.pals)

    def test_missing_face_returns_with_exact_vertices_and_acting(self):
        source,before,tim = self.fixture()
        data,proof = restore(source,before.build(),tim,2,[0])
        after = mmd.MMD.parse(data,2)
        self.assertEqual(proof['restored_triangles'],{0:1})
        self.assertTrue(proof['storage']['fits'])
        self.assertEqual(after.tmd.obj_verts(0),before.tmd.obj_verts(0))
        self.assertEqual(after.anims.build(),before.anims.build())
        self.assertEqual(sum(len(p.decode()['verts'])-2 for p in after.tmd.objects[0].prims),3)

    def test_changed_pool_is_refused(self):
        source,before,tim = self.fixture()
        before.tmd.verts[0] = (300,400,500,0)
        # Four independent points can fit an affine change. A pool-size
        # change cannot establish indexed lineage and must be refused.
        before.tmd.objects[0].nvert -= 1
        with self.assertRaisesRegex(ValueError,'vertex pool differs'):
            restore(source,before.build(),tim,2,[0])

    def test_compacted_pool_maps_survivors_and_appends_dropped(self):
        rng = np.random.default_rng(1)
        x = rng.integers(-500,500,(30,3)).astype(float)
        for drop in ([7],[2,3,19,20,21,28]):   # exhaustive search, then the ordered alignment
            keep = [i for i in range(30) if i not in drop]
            y = x[keep]*.97+(1,2,3)
            mapping,fit = pool_mapping(x,y,3)
            self.assertEqual([mapping[i] for i in keep],list(range(len(keep))))
            self.assertEqual(sorted(mapping[i] for i in drop),list(range(len(keep),30)))
            self.assertTrue(np.allclose(np.column_stack([x,np.ones(30)])@fit,x*.97+(1,2,3)))

    def test_unlit_and_untextured_faces_keep_their_kind(self):
        unlit = face(dict(verts=[0,1,2],norms=[],uv=[(0,0),(4,0),(0,4)],cba=489<<6,colors=[(9,8,7,0x25)]))
        self.assertEqual((unlit['norms'],unlit['row'],unlit['color']),(None,1,(9,8,7)))
        flat = face(dict(verts=[0,1,2],norms=[0,0,0],uv=[],cba=0,colors=[(1,2,3,0x30)]))
        self.assertEqual((flat['uvs'],flat['row'],flat['color']),(None,None,(1,2,3)))
