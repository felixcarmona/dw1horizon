"""Replay the authored Valkyrimon delta and check original-console storage."""
import copy
import json
import math
from pathlib import Path
import unittest

import animsheet
import mmd
import motionstorage
from motiondiscidentity import program
from motiontailspace import interpolate_pose
from tools.models.field_animations import valkyrimon as V
from tools.models.resize import resize


class Valkyrimon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        before = Path('build/review/before/255-Valkyrimon.MMD')
        donor = Path('extracted/CHDAT/MMD0/ANGE.MMD')
        if not before.exists() or not donor.exists():
            raise unittest.SkipTest('reconstruct the pinned import with edit.py get 255 into build/review/before')
        cls.source = before.read_bytes()
        cls.donor_data = donor.read_bytes()
        cls.sk = json.loads(Path('content/species/255-valkyrimon.json').read_text())['model']['skeleton']
        cls.data, cls.proof = V.build(cls.source, donor.read_bytes(), cls.sk)
        cls.old = mmd.MMD.parse(resize(cls.source,30,.8),30)
        cls.new = mmd.MMD.parse(cls.data,30)
        cls.new.type = cls.old.type = 255

    def test_mesh_and_all_non_locomotion_acting_are_exact_after_uniform_resize(self):
        self.assertEqual(self.old.tmd.build(),self.new.tmd.build())
        for slot,index in enumerate(self.old.anims.table):
            if index is not None and slot not in (2,3,4):
                self.assertEqual(program(self.old.anims.anims[index]),
                                 program(self.new.anims.anims[self.new.anims.table[slot]]),slot)
        after = Path('build/review/after/255-Valkyrimon.MMD')
        if after.exists():
            self.assertEqual(self.data,after.read_bytes())

    def test_whole_boots_clear_floor_at_ticks_and_renderer_thirds(self):
        for slot in (2,3,4):
            frames,loop,events = animsheet.slot_frames(self.new,30,slot)
            self.assertEqual(loop,0)
            for a,b in zip(frames,frames[1:]):
                for alpha in (0,1365,2730,4096):
                    pose = interpolate_pose(a,b,alpha)
                    pose[0] = [4096]*3+[0]*6
                    mats = mmd.bone_matrices(self.new,pose)
                    worst = max(sum(mats[bone][1][i]*v[i] for i in range(3))+mats[bone][1][3]
                                for bone in (20,23) for v in self.new.tmd.obj_verts(self.sk[bone][0]))
                    self.assertLess(worst,2,(slot,alpha,worst))

    def test_follow_speed_loop_closure_and_two_alternating_feet(self):
        for slot,duration,floor in ((2,24,15),(3,28,10),(4,16,35)):
            frames,loop,events = animsheet.slot_frames(self.new,30,slot)
            self.assertEqual(len(frames)-1,duration)
            self.assertGreaterEqual(-(frames[-1][0][8]-frames[0][0][8])/duration,floor)
            self.assertEqual(frames[0][1:],frames[-1][1:])
            heights = {b:[] for b in (20,23)}
            for frame in frames:
                pose = copy.deepcopy(frame);pose[0] = [4096]*3+[0]*6
                mats = mmd.bone_matrices(self.new,pose)
                for b in heights:heights[b].append(mats[b][1][3])
            for h in heights.values():self.assertGreater(max(h)-min(h),20)
            self.assertGreater(abs(heights[20].index(min(heights[20]))-heights[23].index(min(heights[23]))),3)
            player = mmd.AnimPlayer(self.new.anims.anims[self.new.anims.table[slot]],30,slot)
            cycle = []
            for tick in range(duration*6):
                self.assertTrue(player.tick())
                if tick<duration:cycle.append(copy.deepcopy(player.pose))
                else:self.assertEqual(player.pose,cycle[tick%duration])
        self.assertTrue(motionstorage.require(self.data,30)['fits'])
        self.assertTrue(all(r['maximum_ik_error']<1 for r in self.proof['checks']))

    def test_supporting_knees_do_not_keep_the_insect_crouch(self):
        frames = animsheet.slot_frames(self.new,30,2)[0]
        flexion = []
        for frame in frames:
            pose = copy.deepcopy(frame)
            pose[0] = [4096]*3+[0]*6
            world = mmd.bone_matrices(self.new,pose)
            for hip,knee,foot in ((18,19,20),(21,22,23)):
                sole = max(sum(world[foot][1][i]*v[i] for i in range(3))+world[foot][1][3]
                           for v in self.new.tmd.obj_verts(self.sk[foot][0]))
                if sole < -8:
                    continue
                a = [world[hip][i][3]-world[knee][i][3] for i in range(3)]
                b = [world[foot][i][3]-world[knee][i][3] for i in range(3)]
                cosine = sum(x*y for x,y in zip(a,b))/math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
                flexion.append(180-math.degrees(math.acos(max(-1,min(1,cosine)))))
        self.assertGreater(len(flexion),10)
        self.assertLess(sum(flexion)/len(flexion),70)
        self.assertLess(max(flexion),120)

    def test_native_sound_times_follow_retimed_steps(self):
        donor = mmd.MMD.parse(self.donor_data,26)
        for slot,duration in ((2,24),(3,28),(4,16)):
            native,_,events = animsheet.slot_frames(donor,26,slot)
            actual = animsheet.slot_frames(self.new,30,slot)[2]
            expected = [(round(t*duration/(len(native)-1)),k,c) for t,k,c in events if k=='sound']
            semantic = lambda events: [(t,k,{key:v for key,v in c.items() if key!='frame'}) for t,k,c in events]
            self.assertEqual(semantic(actual),semantic(expected),slot)

    def test_source_and_native_donor_are_pinned(self):
        with self.assertRaises(ValueError):V.build(b'wrong',b'wrong',self.sk)
        with self.assertRaises(ValueError):V.build(self.source,b'wrong',self.sk)


if __name__ == '__main__':
    unittest.main()
