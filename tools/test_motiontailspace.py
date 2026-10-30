#!/usr/bin/env python3
"""Asset-free checks for nominal engine interpolation diagnostics."""
import copy
import unittest
import numpy as np
from motiontailspace import interpolate_pose
from motionquality import collide


class InterpolationDiagnostics(unittest.TestCase):
    def test_shortest_angle_arc_and_fixed_point_translation(self):
        first=[[4096,4096,4096,4090,0,0,-9,0,0]]
        second=[[4096,4096,4096,6,0,0,9,0,0]]
        saved=copy.deepcopy((first,second))
        a=interpolate_pose(first,second,1365)[0]
        b=interpolate_pose(first,second,2730)[0]
        self.assertEqual((a[3],b[3]),(4094,4098))
        self.assertEqual((a[6],b[6]),(-3,3))
        self.assertEqual(interpolate_pose(first,second,4096)[0][3]%4096,6)
        self.assertEqual((first,second),saved)

    def test_intermediate_crossing_can_exist_between_clear_endpoints(self):
        moving=np.array([[[-2,-2,0],[2,-2,0],[0,2,0]]],dtype=float)
        obstacle=np.array([[[0,-1,-1],[0,1,-1],[0,0,1]]],dtype=float)
        first=[[4096,4096,4096,0,0,0,-3,0,0]]
        second=[[4096,4096,4096,0,0,0,3,0,0]]
        self.assertFalse(collide(moving+np.array(first[0][6:9]),obstacle))
        self.assertFalse(collide(moving+np.array(second[0][6:9]),obstacle))
        middle=interpolate_pose(first,second,1365)[0][6:9]
        self.assertTrue(collide(moving+np.array(middle),obstacle))


if __name__=='__main__':unittest.main()
