"""Decoded regressions for the player-reported size and aliased dive attacks.

Reconstruct BEFORE with edit.py get at the parent commit, then run the authoring
recipe. SILPHYMON_REVIEW overrides build/silphymon for those local disc assets.
"""
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import mmd
import motionstorage
import species
from motiontailspace import interpolate_pose
from tools.models.silphymon_attacks import DONORS, FACTOR, author
from tools.models.resize import resize

REVIEW = Path(os.environ.get('SILPHYMON_REVIEW', ROOT / 'build/silphymon'))


class SilphymonAttacks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = [REVIEW / 'before/226-Silphymon.MMD', REVIEW / 'after/226-Silphymon.MMD']
        if not all(p.is_file() for p in paths):
            raise unittest.SkipTest('needs reconstructed before/after player-disc models')
        cls.before, cls.after = [mmd.MMD.load(str(p), 226) for p in paths]
        cls.sk = mmd.exe().skeleton[226]
        cls.data = paths[1].read_bytes()

    def test_replay_and_storage(self):
        result, _, _ = author((REVIEW / 'before/226-Silphymon.MMD').read_bytes())
        self.assertEqual(result, self.data)
        self.assertTrue(motionstorage.require(self.data, 21)['fits'])

    def test_size_and_unaffected_acting(self):
        scaled = mmd.MMD.parse(resize((REVIEW / 'before/226-Silphymon.MMD').read_bytes(),21,FACTOR),21)
        self.assertEqual(scaled.tmd.build(),self.after.tmd.build())
        for slot in range(46):
            if slot in (2,3,4) or self.before.anims.table[slot] is None:
                continue
            fa, la, ea = animsheet.slot_frames(scaled,21,slot)
            fb, lb, eb = animsheet.slot_frames(self.after,21,slot)
            self.assertEqual((len(fa),la,ea),(len(fb),lb,eb),slot)
            for x,y in zip(fa,fb):
                for bone in range(21):
                    self.assertEqual(x[bone][:6],y[bone][:6],(slot,bone))
                    for j in range(6,9):
                        self.assertLessEqual(abs(x[bone][j]-y[bone][j]),2,(slot,bone,j))
        def height(model):
            pose=animsheet.slot_frames(model,21,0)[0][0]
            ys=[v[1] for tri in animsheet.world_tris(model,pose,self.sk) for v in tri[0]]
            return max(ys)-min(ys)
        self.assertAlmostEqual(height(self.after)/height(self.before),FACTOR,delta=.005)
        self.assertLess(height(self.after),480)

    def test_native_technique_clocks_and_events(self):
        spec=json.loads((ROOT/'content/species/226-silphymon.json').read_text())
        ids=species.techniques_from_json(spec['techniques'],'Silphymon')
        originals=species.originals()
        programs=[]
        for i,d in enumerate(DONORS):
            slot=46+i; ds=46+originals.rec[d]['para']['moves'].index(ids[i])
            native=mmd.MMD.load(originals.model_path(d),d)
            source,_,events=animsheet.slot_frames(native,mmd.exe().bone_count[d],ds)
            target,loop,actual=animsheet.slot_frames(self.after,21,slot)
            self.assertIsNone(loop)
            for bone in range(1,21):
                self.assertEqual(target[0][bone][3:6], target[-1][bone][3:6], (slot,bone))
            self.assertEqual(len(source),len(target),slot)
            self.assertEqual([e for e in events if e[1]=='sound'],actual,slot)
            programs.append(self.after.anims.table[slot])
        # No ordinary projectile may inherit the Buster Dive program again.
        self.assertEqual(len(set(programs)),14)

    def test_ground_support_including_display_blends(self):
        for slot in range(46,60):
            frames,_,_=animsheet.slot_frames(self.after,21,slot)
            for a,b in zip(frames,frames[1:]):
                for alpha in (0,1365,2730,4096):
                    pose=interpolate_pose(a,b,alpha)
                    pose[0][6:9]=[0,0,0]
                    mats=mmd.bone_matrices(self.after,pose)
                    feet=(18,19) if slot==54 else (14,15,18,19)
                    floor=max(sum(mats[bone][1][j]*v[j] for j in range(3))+mats[bone][1][3]
                              for bone in feet for v in self.after.tmd.obj_verts(self.sk[bone][0]))
                    self.assertLessEqual(abs(floor),4,(slot,alpha,floor))
            # The reported 357-unit carrier launch must not recur in shots.
            self.assertLess(max(p[1][7]for p in frames)-min(p[1][7]for p in frames),8)

    def test_carrier_loops_do_not_drift_after_resize(self):
        for slot in range(46):
            if self.after.anims.table[slot] is None:
                continue
            frames,loop,_=animsheet.slot_frames(self.after,21,slot)
            if loop is not None:
                self.assertEqual(frames[loop][1][6:9],frames[-1][1][6:9],slot)

    def test_dash_reach_and_field_pace(self):
        from tools.models.buster_dive import native_dash
        roots,_=mmd.simulate(native_dash(),len(native_dash().pose)+1)
        frames,_,_=animsheet.slot_frames(self.after,21,55)
        self.assertEqual([f[0][6:9]for f in frames],[f[0][6:9]for f in roots])
        self.assertGreaterEqual(frames[22][0][8]-min(f[0][8]for f in frames[22:34]),500)
        for slot in (2,3,4):
            before,_,_=animsheet.slot_frames(self.before,21,slot)
            after,loop,_=animsheet.slot_frames(self.after,21,slot)
            self.assertEqual(loop,0)
            speed=lambda fs: abs(fs[-1][0][8]-fs[0][0][8])/(len(fs)-1)
            self.assertAlmostEqual(speed(before),speed(after),delta=1)


if __name__ == '__main__':
    unittest.main()
