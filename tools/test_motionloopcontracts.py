"""Asset-free tests of tools/motionloopcontracts.py (a looping rotor must wind the same way at every phase, not only at the cycle boundary).

    python3 tools/test_motionloopcontracts.py
"""
import copy,unittest
from motionloopcontracts import verify_winding

class RotorPlayer:
    def __init__(self,delta,error_phase=None):self.tick_count=-1;self.delta=delta;self.error_phase=error_phase
    def tick(self):
        self.tick_count+=1;cycle,phase=divmod(self.tick_count,2)
        self.pose=[[4096]*3+[0]*6 for _ in range(2)]
        self.pose[1][5]=([0,-100][phase]+cycle*self.delta)%4096
        if self.error_phase==(cycle,phase):self.pose[1][5]+=1
        return True

class ContinuousRotationTest(unittest.TestCase):
    def frames(self):
        result=[[[4096]*3+[0]*6 for _ in range(2)] for _ in range(3)]
        result[1][1][5]=-100;result[2][1][5]=-1984
        return result
    def test_preserves_negative_native_winding_across_modulo_wraps(self):
        frames=self.frames();before=copy.deepcopy(frames)
        self.assertEqual(verify_winding(RotorPlayer(-1984),frames,[(1,5)],64),[dict(bone=1,channel=5,delta=-1984)])
        self.assertEqual(frames,before)
    def test_rejects_wrong_loop_advance(self):
        with self.assertRaises(ValueError):verify_winding(RotorPlayer(-2048),self.frames(),[(1,5)])
    def test_checks_intermediate_phase_not_only_cycle_boundary(self):
        with self.assertRaises(ValueError):verify_winding(RotorPlayer(-1984,(5,1)),self.frames(),[(1,5)])
    def test_rejects_missing_continuous_declaration(self):
        with self.assertRaises(ValueError):verify_winding(RotorPlayer(-1984),self.frames(),[])

if __name__ == '__main__':
    unittest.main()
