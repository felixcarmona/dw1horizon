#!/usr/bin/env python3
"""Asset-free checks for reference pose resampling."""
import math
import unittest
import motionreference as Q

class ReferenceSampling(unittest.TestCase):
    def test_closed_angular_envelope_measures_speed_and_direction_changes(self):
        sk=[(-1,-1),(-1,0)]
        fs=[[[4096,4096,4096,0,0,0,0,0,0],[4096,4096,4096,round(a*4096/360),0,0,0,0,0]] for a in [0,10,20,10,0]]
        envelope=Q.angular_envelope(sk,fs,[1])
        self.assertAlmostEqual(envelope['max_step_degrees'],10,delta=.2)
        self.assertAlmostEqual(envelope['max_velocity_change_degrees'],20,delta=.3)

    def test_angular_envelope_detects_an_abrupt_reversal(self):
        sk=[(-1,-1),(-1,0)]
        fs=[[[4096,4096,4096,0,0,0,0,0,0],[4096,4096,4096,round(a*4096/360),0,0,0,0,0]] for a in [0,0,45,0,0]]
        envelope=Q.angular_envelope(sk,fs,[1])
        self.assertAlmostEqual(envelope['max_velocity_change_degrees'],90,delta=.3)

    def test_source_scale_is_interpolated_for_native_motion(self):
        a=[[4096,4096,4096,0,0,0,0,0,0]]
        b=[[2048,8192,0,0,0,0,0,0,0]]
        self.assertEqual(Q.resample([a,b],.5)[0][:3],[3072,6144,2048])
    def test_swing_offset_wraps_without_adding_an_extra_stride(self):
        self.assertAlmostEqual(Q.swing_world_offset(0,3,5,8,-350),
                               Q.swing_world_offset(8,3,5,8,-350))
        self.assertEqual(Q.swing_world_offset(4,3,5,8,-350),0)

    def test_swing_velocity_is_zero_at_touchdown_and_liftoff(self):
        epsilon=1e-4
        self.assertLess(abs(Q.swing_world_offset(5+epsilon,3,5,8,-350)/epsilon),1e-4)
        self.assertLess(abs(Q.swing_world_offset(3-epsilon,3,5,8,-350)/epsilon),1e-4)

    def test_rotation_crosses_wrap_by_short_arc(self):
        a=[[4096,4096,4096,0,round(179*4096/360),0,0,0,0]]
        b=[[4096,4096,4096,0,round(-179*4096/360),0,10,20,-30]]
        p=Q.resample([a,b],.5)
        rotation=Q.R.rot_of(p[0])
        self.assertLess(rotation[0][0],-.999)
        self.assertEqual(p[0][6:9],[5,10,-15])
        self.assertEqual(a[0][6:9],[0,0,0])

    def test_loop_endpoint_retains_accumulated_root(self):
        a=[[4096,4096,4096,0,0,0,0,0,0],[4096,4096,4096,0,100,0,0,-90,0]]
        b=[[4096,4096,4096,0,0,0,0,0,-120],[4096,4096,4096,0,100,0,0,-90,0]]
        p=Q.resample([a,b],1)
        self.assertEqual(p[0][6:9],[0,0,-120])
        self.assertEqual(p[1],a[1])

if __name__=='__main__':unittest.main()
