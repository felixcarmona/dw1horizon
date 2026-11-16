"""Restore missing faces without changing a fitted pool or animation."""
import copy
from pathlib import Path
import sys
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parents[1])]
import mmd
import mmdport
from tools.models.restore_surface import restore

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
