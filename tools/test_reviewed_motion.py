"""Decoded motion, source isolation and original-console storage checks.

Populate build/motion-review-models4/{before,after}/ID.MMD with the reviewed
provider inputs and outputs; MODEL_REVIEW selects an alternate evidence folder.
"""
import copy
import json
import os
from pathlib import Path
import unittest

import animsheet
import mmd
import motionstorage
from motiondiscidentity import program
from tools.models.reviewed_motion import load, points
from tools.models.scale_lock import measure

IDS = (62,237,246,267,268,431)
CARE = {246:(9,12),431:(9,12)}
NATIVE = {237:(0,1,2,3,4),267:(0,1,2,3,4,5,7,8,9,10,11,12,13,14,15,16,17,18,19,34,35,36),
          268:(0,1,2,3,4,5,7,8,9,10,11,12,13,14,15,16,17,18,19,34,35,36)}

class ReviewedMotion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=Path(os.environ.get('MODEL_REVIEW','build/motion-review-models4'))
        if not all((cls.folder / phase / f'{sid}.MMD').exists() for sid in IDS for phase in ('before','after')):
            raise unittest.SkipTest('requires reconstructed before/after provider models')

    def models(self,sid):
        return tuple(load(self.folder/phase/f'{sid}.MMD',sid) for phase in ('before','after'))

    def test_original_console_buffers(self):
        for sid in IDS:
            model=self.models(sid)[1]
            audit=motionstorage.require(model.build(),mmd.exe().bone_count[sid])
            self.assertTrue(audit['fits'],(sid,audit))
            if sid==62:
                self.assertLessEqual(len(model.build()),0x18800)
                proof=json.loads(Path('content/modeldelta/reviewed-motion.json').read_text())
                recorded=proof['models']['62']['storage']
                import species
                spec=json.loads(Path('content/species/62-weregarurumon.json').read_text())
                effective=species.apply_slot_aliases(model.build(),spec)
                self.assertLessEqual(len(effective),0x18800)
                self.assertEqual(recorded['resident_bytes'],len(effective))
                self.assertEqual(recorded['cold_bytes'],0)

    def test_untouched_programs_and_mesh(self):
        for sid in (237,267,268,431):
            before,after=self.models(sid)
            self.assertEqual(before.tmd.build(),after.tmd.build(),sid)
            touched=set(CARE.get(sid,NATIVE.get(sid,())))
            for slot,index in enumerate(before.anims.table):
                if index is None or slot in touched:continue
                self.assertEqual(program(before.anims.anims[index]),
                    program(after.anims.anims[after.anims.table[slot]]),(sid,slot))

    def test_care_clocks_and_sound_events(self):
        for sid,slots in CARE.items():
            before,after=self.models(sid);nb=mmd.exe().bone_count[sid]
            for slot in slots:
                a,loop,events=animsheet.slot_frames(before,nb,slot)
                b,newloop,newevents=animsheet.slot_frames(after,nb,slot)
                self.assertEqual((len(a),loop),(len(b),newloop),(sid,slot))
                self.assertEqual([e for e in events if e[1]=='sound'],newevents,(sid,slot))

    def test_infermon_has_constant_scale_in_every_slot(self):
        model=self.models(246)[1]
        report=measure(model,mmd.exe().skeleton[246],0)
        self.assertFalse(report['animated'])
        self.assertFalse(report['across_slots'])

    def test_infermon_care_contacts_stay_planted(self):
        model=self.models(246)[1];feet=(7,8,11,12,15,16,19,20,23,24,27,28)
        for slot in CARE[246]:
            frames=animsheet.slot_frames(model,30,slot)[0]
            positions=[]
            for pose in frames:
                for foot in feet:
                    self.assertLessEqual(max(v[1] for v in points(model,pose,[foot])),2,(slot,foot))
                mats=mmd.bone_matrices(model,pose)
                positions.append([[mats[b][i][3] for i in range(3)] for b in feet])
            for b in range(len(feet)):
                for axis in range(3):
                    values=[p[b][axis] for p in positions]
                    self.assertLess(max(values)-min(values),4,(slot,feet[b],axis))

    def test_kurisarimon_sleep_keeps_the_shell_above_ground(self):
        from motiontailspace import interpolate_pose
        model=self.models(431)[1]
        for slot in (9,12):
            frames=animsheet.slot_frames(model,34,slot)[0]
            for first,second in zip(frames,frames[1:]):
                for alpha in (0,1365,2730,4096):
                    pose=interpolate_pose(first,second,alpha)
                    self.assertLessEqual(max(v[1] for v in points(model,pose,(1,30,31,32,33))),1)

    def test_native_donor_clocks_and_voice_cues(self):
        for sid,dsid,path in ((237,26,'MMD0/SKUL.MMD'),(267,47,'MMD1/MONO.MMD'),(268,47,'MMD1/MONO.MMD')):
            model=self.models(sid)[1];donor=load(Path('extracted/CHDAT')/path,dsid)
            for slot in NATIVE[sid]:
                a,loop,events=animsheet.slot_frames(donor,mmd.exe().bone_count[dsid],slot)
                b,newloop,newevents=animsheet.slot_frames(model,mmd.exe().bone_count[sid],slot)
                self.assertEqual((len(a),loop),(len(b),newloop),(sid,slot))
                self.assertEqual([e for e in events if e[1]=='sound'],newevents,(sid,slot))

    def test_support_clearance_between_keys_and_at_loop_seams(self):
        from motiontailspace import interpolate_pose
        for sid,feet,slots in ((237,(19,23),range(5)),
                              (267,(9,12,23,26),(2,4)),
                              (268,(9,12,25,28),(2,4)),
                              (246,(7,8,11,12,15,16,19,20,23,24,27,28),(9,12))):
            model=self.models(sid)[1]
            for slot in slots:
                frames=animsheet.slot_frames(model,mmd.exe().bone_count[sid],slot)[0]
                for tick,(first,second) in enumerate(zip(frames,frames[1:])):
                    for alpha in (0,1365,2730,4096):
                        pose=interpolate_pose(first,second,alpha)
                        self.assertLessEqual(max(v[1] for v in points(model,pose,feet)),2,
                                             (sid,slot,tick,alpha))

    def test_diaboromon_walks_on_legs_with_free_arms(self):
        import math
        import retarget
        from motiontailspace import interpolate_pose
        model=self.models(237)[1]
        sk=mmd.exe().skeleton[237]
        for slot in range(5):
            frames=animsheet.slot_frames(model,24,slot)[0]
            for first,second in zip(frames,frames[1:]):
                for alpha in (0,1365,2730,4096):
                    pose=interpolate_pose(first,second,alpha)
                    self.assertLessEqual(max(v[1] for v in points(model,pose,range(6,14))),-30,
                                         ('arm clearance',slot,alpha))
                    if slot in (0,2,4):
                        positions=retarget.world_pos(sk,pose)
                        spine=[positions[2][i]-positions[14][i] for i in range(3)]
                        lean=math.degrees(math.atan2(-spine[2],-spine[1]))
                        self.assertTrue(8<lean<35,('spine lean',slot,lean))
            if slot in (2,4):
                for foot in (19,23):
                    floors=[max(v[1] for v in points(model,pose,(foot,))) for pose in frames]
                    self.assertGreater(max(floors),-5 if slot==2 else -10,('stance',slot,foot))
                    self.assertLess(min(floors),-50,('swing',slot,foot))

    def test_resize_keeps_all_weregarurumon_acting(self):
        before,after=self.models(62)
        for slot,index in enumerate(before.anims.table):
            if index is None:continue
            a,loop,events=animsheet.slot_frames(before,22,slot)
            b,newloop,newevents=animsheet.slot_frames(after,22,slot)
            self.assertEqual((len(a),loop,events),(len(b),newloop,newevents),slot)
            for p,q in zip(a,b):
                for old,new in zip(p,q):self.assertEqual(old[:6],new[:6],slot)

if __name__=='__main__': unittest.main()
