"""Kyubimon final fan topology, sway, storage and full-clip regressions."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
import mmd
import motionstorage
from tools.models import kyubimon_mesh as K, mesh_stability as S
from tools.models.mesh_round4 import load


class Sway(unittest.TestCase):
    def test_periodic_continuous_windup(self):
        values = [K.fan_sway(x,103) for x in range(-4096,4097)]
        self.assertLessEqual(max(abs(b-a) for a,b in zip(values,values[1:])),1)
        for x in range(-2048,2049):
            self.assertEqual(K.fan_sway(x,103),K.fan_sway(x+4096,103))
            self.assertLessEqual(abs(K.fan_sway(x,103)-103),200)


@unittest.skipUnless((ROOT/'build/before/409.MMD').exists(), 'private model fixture unavailable')
class FinalModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=load(ROOT/'build/before',409)
        cls.after=load(ROOT/'build/after',409)
        cls.work=copy.deepcopy(cls.before.m)
        cls.fan=K.weld_fan(cls.work)
        K.finish(cls.work,cls.before.bones)
        cls.split=K.split_bends(cls.work,cls.fan)
        S.compact_pools(cls.work)

    def test_reproduces_provider_and_fits_own_budget(self):
        self.assertEqual(self.work.build(),self.after.m.build())
        storage=motionstorage.audit(self.work.build(),len(self.before.bones))
        self.assertTrue(storage['fits'])
        self.assertLessEqual(storage['resident_bytes'],94882)
        self.assertFalse(S.bent_quads(self.work,10))
        groups=self.fan['groups']
        self.assertEqual(sorted(p for g in groups for p in g),list(range(len(self.work.tmd.objects[9].prims))))

    def test_every_pose_preserves_root_scale_translation_events_aliases(self):
        b,a=self.before,self.after
        self.assertEqual(b.bones,a.bones)
        self.assertEqual(b.m.anims.table,a.m.anims.table)
        count=0
        for slot in b.slots():
            left,info=mmd.simulate(b.m.anims.anims[b.m.anims.table[slot]],len(b.bones),slot=slot)
            right,got=mmd.simulate(a.m.anims.anims[a.m.anims.table[slot]],len(a.bones),slot=slot)
            self.assertEqual(info,got)
            left,right=np.array(left),np.array(right)
            self.assertEqual(left.shape,right.shape)
            self.assertTrue(np.array_equal(left[:,0],right[:,0]))
            self.assertTrue(np.array_equal(left[:,:,:3],right[:,:,:3]))
            self.assertTrue(np.array_equal(left[:,:,6:],right[:,:,6:]))
            mask=np.ones(left.shape[1:],bool);mask[15,3:6]=False
            if slot==42:mask[2,4]=False
            self.assertTrue(np.array_equal(left[:,mask],right[:,mask]))
            count+=len(left)
        self.assertEqual(count,1461)

    def test_tail_and_root_certificates_cover_every_tick(self):
        from tools.models.kyubimon_mesh_audit import certificates
        report=certificates(self.after,self.fan)
        self.assertEqual(len(report['cross_tail']),36)
        self.assertEqual(len(report['joins']),7)
        self.assertEqual(len(report['root_frames']),1461)
        self.assertTrue(report['all_certificates_verified'])

    def test_each_attachment_is_separated_by_its_exact_ring_plane(self):
        m=self.after;source=self.fan['source_packets']
        for tail,(proximal,_,_) in enumerate(K.mesh_fan.JOINS):
            x=self.fan['join_planes'][tail]
            tris=lambda source_ids:np.array([m.local[15][list(t[3])] for t in m.tris if t[0]==15 and source[t[2]] in source_ids])
            base=tris(proximal);end=tris(range(84+20*tail,104+20*tail))
            self.assertLessEqual(base[:,:,0].max(),x)
            self.assertGreaterEqual(end[:,:,0].min(),x)
            # Only shared attachment edges lie on the separating plane.
            for triangles in (base,end):
                self.assertFalse(np.any(np.all(triangles[:,:,0]==x,axis=1)))


if __name__=='__main__':
    unittest.main()
