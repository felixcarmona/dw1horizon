"""Uniform world-space size and unchanged acting across Zudomon's clips."""
import copy
import os
from pathlib import Path
import unittest
import mmd
import animsheet
import motionstorage
from motiondiscidentity import program

class ZudomonSize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        before=Path(os.environ.get('ZUDOMON_BEFORE','build/model-size-review/219-before.MMD'))
        after=Path(os.environ.get('ZUDOMON_AFTER','build/model-size-review/219-after.MMD'))
        if not before.exists()or not after.exists():raise unittest.SkipTest('needs the before and reconstructed resized models')
        cls.before=mmd.MMD.load(str(before),219)
        cls.after=mmd.MMD.load(str(after),219)
        cls.data=after.read_bytes()

    def test_all_clips_keep_rotation_visibility_timing_and_events(self):
        a,b=self.before,self.after
        self.assertEqual(a.anims.table,b.anims.table)
        self.assertEqual(a.tmd.norms,b.tmd.norms)
        for slot,index in enumerate(a.anims.table):
            if index is None:continue
            before,loop,events=animsheet.slot_frames(a,22,slot)
            after,newloop,newevents=animsheet.slot_frames(b,22,slot)
            self.assertEqual((len(before),loop,events),(len(after),newloop,newevents),slot)
            for p,q in zip(before,after):
                for x,y in zip(p,q):self.assertEqual(x[:6],y[:6],slot)
        self.assertTrue(motionstorage.require(self.data,22)['fits'])

    def test_world_size_is_uniform_in_every_clip_including_hammer(self):
        a,b=self.before,self.after
        bones=mmd.exe().skeleton[219]
        checked=0
        for slot,index in enumerate(a.anims.table):
            if index is None:continue
            before=animsheet.slot_frames(a,22,slot)[0]
            after=animsheet.slot_frames(b,22,slot)[0]
            for tick in sorted({0,len(before)//2,len(before)-1}):
                p,q=copy.deepcopy(before[tick]),copy.deepcopy(after[tick])
                p[0]=q[0]=[4096]*3+[0]*6
                x,y=mmd.bone_matrices(a,p),mmd.bone_matrices(b,q)
                for bone,(obj,_) in enumerate(bones):
                    if obj<0:continue
                    va=a.tmd.obj_verts(obj);vb=b.tmd.obj_verts(obj)
                    for i in range(0,len(va),max(1,len(va)//8)):
                        for axis in range(3):
                            old=sum(x[bone][axis][k]*va[i][k]for k in range(3))+x[bone][axis][3]
                            new=sum(y[bone][axis][k]*vb[i][k]for k in range(3))+y[bone][axis][3]
                            self.assertLess(abs(new-.85*old),8,(slot,tick,bone,axis))
                            checked+=1
        self.assertGreater(checked,10000)
