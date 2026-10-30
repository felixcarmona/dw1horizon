#!/usr/bin/env python3
"""Asset-free native idle grounding checks."""
import copy
import unittest
from unittest.mock import patch
import motionidle as I
import motionlab as M


class IdleSupport(unittest.TestCase):
    def test_intentional_native_spin_is_not_closed_as_a_grounded_idle(self):
        with patch('motionloopcontracts.load',return_value={33:{(2,5)}}):
            with self.assertRaisesRegex(ValueError,'intentional continuous rotation'):
                I.generate(None,[],[],{'species':290},{'source':'0x21'})

    def setUp(self):
        self.skeleton=[(-1,-1),(-1,0),(-1,1),(-1,2),(-1,1)]
        rest=[[4096,4096,4096,0,0,0,0,0,0] for _ in self.skeleton]
        rest[1][7]=-45;rest[2][7]=20;rest[3][7]=20
        self.frames=[copy.deepcopy(rest) for _ in range(3)]
        self.frames[1][1][7]=-40;self.frames[1][4][4]=30
        self.vertices={2:[(0,20,0)],3:[(0,1,0)]}

    def test_compound_support_stays_on_floor_and_keeps_native_gesture(self):
        original=copy.deepcopy(self.frames)
        result=I.ground(self.frames,self.skeleton,1,self.vertices,0)
        for pose in result:
            positions=M.R.world_pos(self.skeleton,pose)
            self.assertAlmostEqual(max(positions[2][1]+20,positions[3][1]+1),0)
        self.assertEqual(result[1][4],self.frames[1][4])
        self.assertEqual(original,self.frames)
        self.assertEqual(result[0],result[-1])

    def test_moving_root_is_not_silently_converted_to_idle(self):
        self.frames[1][0][8]=1
        with self.assertRaisesRegex(ValueError,'stationary'):
            I.ground(self.frames,self.skeleton,1,self.vertices,0)

    def test_upper_alignment_preserves_native_gesture_and_lower_limbs(self):
        rotation=M.mmd.rot_matrix(0,300,0)
        result=I.align_upper(self.frames,self.skeleton,4,rotation)
        for original,pose in zip(self.frames,result):
            self.assertEqual(pose[:4],original[:4])
        actual=M.R.world_rots(self.skeleton,result[0])[4]
        self.assertLess(max(abs(actual[i][j]-rotation[i][j]) for i in range(3) for j in range(3)),.002)
        self.assertEqual(result[1][4][4]-result[0][4][4],30)

    def test_grounding_includes_inherited_nonunit_scale(self):
        self.frames[1][2][1]=8192
        result=I.ground(self.frames,self.skeleton,1,self.vertices,0)
        for pose in result:
            world=I.world_matrices(self.skeleton,pose)
            low=max(sum(world[b][1][j]*v[j] for j in range(3))+world[b][1][3]
                    for b,points in self.vertices.items() for v in points)
            self.assertAlmostEqual(low,0)
        self.assertEqual(result[1][2][1],8192)

    def test_rotating_root_requires_a_different_solver(self):
        self.frames[1][0][4]=20
        with self.assertRaisesRegex(ValueError,'rotation'):
            I.ground(self.frames,self.skeleton,1,self.vertices,0)


if __name__=='__main__':unittest.main()
