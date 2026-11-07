"""Hand contact and preservation checks against the pinned crouched gait."""
import copy
import hashlib
import os
from pathlib import Path
import unittest

import animsheet
import mmd
from motiontailspace import interpolate_pose
from tools.models.diaboromon_hands import SOURCE
from tools.models.reviewed_motion import load,points,world


class HandContacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder=Path(os.environ.get('HAND_REVIEW','build/diaboromon-palms'))
        if not all((folder/phase/'237.MMD').exists() for phase in ('before','after')):
            raise unittest.SkipTest('requires reconstructed crouched and contact-corrected models')
        raw=(folder/'before/237.MMD').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=SOURCE:
            raise ValueError('incorrect crouched comparison model')
        cls.before=load(folder/'before/237.MMD',237)
        cls.after=load(folder/'after/237.MMD',237)

    def test_only_distal_arm_rotations_change(self):
        self.assertEqual(self.before.tmd.build(),self.after.tmd.build())
        for slot,index in enumerate(self.before.anims.table):
            if index is None:continue
            a,loop,events=animsheet.slot_frames(self.before,24,slot)
            b,newloop,newevents=animsheet.slot_frames(self.after,24,slot)
            self.assertEqual((len(a),loop,events),(len(b),newloop,newevents),slot)
            for old,new in zip(a,b):
                for bone in range(24):
                    for channel in range(9):
                        if slot<5 and bone in (8,9,12,13) and channel in (3,4,5):continue
                        self.assertEqual(old[bone][channel],new[bone][channel],(slot,bone,channel))
            if slot>=5:
                self.assertEqual(self.before.anims.anims[index].build(),
                                 self.after.anims.anims[self.after.anims.table[slot]].build(),slot)

    def test_finger_pads_land_and_wrists_stay_above(self):
        sk=mmd.exe().skeleton[237]
        for slot in range(5):
            a=animsheet.slot_frames(self.before,24,slot)[0]
            b=animsheet.slot_frames(self.after,24,slot)[0]
            contacts=0
            for old,new in zip(a,b):
                oldw,neww=world(self.before,old),world(self.after,new)
                for elbow,hand in ((8,9),(12,13)):
                    if oldw[hand][1][3]<-80:continue
                    contacts+=1
                    vertices=self.after.tmd.obj_verts(sk[hand][0])
                    heights=[sum(neww[hand][1][j]*v[j] for j in range(3))+neww[hand][1][3] for v in vertices]
                    self.assertTrue(-8<=max(heights)<=2,(slot,hand,max(heights)))
                    lowest=max(range(len(heights)),key=heights.__getitem__)
                    self.assertGreater(vertices[lowest][1],50,('contact is a pad, not the wrist',slot,hand))
                    self.assertLess(neww[hand][1][3],-65)
                    self.assertLess(abs(neww[hand][1][1]),.27,('hand lies along the floor',slot,hand))
                    cap=[self.after.tmd.obj_verts(sk[elbow][0])[i] for i in (4,5,6,7)]
                    self.assertLess(max(sum(neww[elbow][1][j]*v[j] for j in range(3))+neww[elbow][1][3] for v in cap),-15)
            self.assertGreater(contacts,0,slot)

    def test_no_hand_or_wrist_penetration_between_keys(self):
        for slot in range(5):
            frames=animsheet.slot_frames(self.after,24,slot)[0]
            for a,b in zip(frames,frames[1:]+frames[:1]):
                for alpha in (0,1365,2730,4096):
                    p=interpolate_pose(a,b,alpha)
                    self.assertLessEqual(max(v[1] for v in points(self.after,p,(8,9,12,13))),2,(slot,alpha))

    def test_four_cycles_keep_body_and_contact_motion(self):
        for slot in range(5):
            period=len(animsheet.slot_frames(self.after,24,slot)[0])-1
            players=[mmd.AnimPlayer(m.anims.anims[m.anims.table[slot]],24,slot)
                     for m in (self.before,self.after)]
            poses=[]
            for _ in range(period*4+1):
                for p in players:self.assertTrue(p.tick())
                a,b=players
                self.assertEqual(a.root,b.root)
                self.assertEqual(a.events,b.events)
                for bone in range(24):
                    if bone not in (8,9,12,13):self.assertEqual(a.pose[bone],b.pose[bone])
                poses.append(copy.deepcopy(b.pose))
            for tick in range(period*3):
                for bone in (8,9,12,13):
                    self.assertEqual(poses[tick][bone],poses[tick+period][bone],(slot,tick,bone))


if __name__=='__main__':unittest.main()
