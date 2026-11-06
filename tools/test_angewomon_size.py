"""Uniform world-space size and unchanged acting across Angewomon's clips."""
import copy
import os
from pathlib import Path
import unittest
import mmd
import animsheet
import motionstorage
from motiondiscidentity import program

class AngewomonSize(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        before=Path(os.environ.get('ANGEWOMON_BEFORE','build/angewomon-redo/A-before.MMD'))
        after=Path(os.environ.get('ANGEWOMON_AFTER','build/angewomon-redo/A.MMD'))
        if not before.exists()or not after.exists():raise unittest.SkipTest('needs the before and reconstructed resized models')
        cls.before=mmd.MMD.load(str(before),190)
        cls.after=mmd.MMD.load(str(after),190)
        cls.data=after.read_bytes()

    def test_all_clips_keep_rotation_visibility_timing_and_events(self):
        a,b=self.before,self.after
        self.assertEqual(a.anims.table,b.anims.table)
        self.assertEqual(a.tmd.norms,b.tmd.norms)
        for old,new in zip(a.tmd.verts,b.tmd.verts):
            self.assertEqual(tuple(new[:3]),tuple(round(v*.74) for v in old[:3]))
        for old,new in zip(a.anims.anims,b.anims.anims):
            expected=copy.deepcopy(old.instrs)
            for instruction in expected:
                if instruction["op"]=="key":
                    for group in instruction["bones"]:
                        for channel in ("tx","ty","tz"):
                            if channel in group["vals"]:
                                group["vals"][channel]=round(group["vals"][channel]*.74)
            self.assertEqual(new.instrs,expected)
        for slot,index in enumerate(a.anims.table):
            if index is None:continue
            before,loop,events=animsheet.slot_frames(a,31,slot)
            after,newloop,newevents=animsheet.slot_frames(b,31,slot)
            self.assertEqual((len(before),loop,events),(len(after),newloop,newevents),slot)
            for p,q in zip(before,after):
                for x,y in zip(p,q):self.assertEqual(x[:6],y[:6],slot)
        self.assertTrue(motionstorage.require(self.data,31)['fits'])

    def test_world_size_is_uniform_in_every_clip_including_wings(self):
        a,b=self.before,self.after
        bones=mmd.exe().skeleton[190]
        checked=0
        worst=0
        for slot,index in enumerate(a.anims.table):
            if index is None:continue
            before=animsheet.slot_frames(a,31,slot)[0]
            after=animsheet.slot_frames(b,31,slot)[0]
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
                            worst=max(worst,abs(new-.74*old))
                            checked+=1
        self.assertGreater(checked,10000)
        # Integer key velocities accumulate rounding over a clip; the rig and angles stay exact.
        self.assertLess(worst,24)
