"""Disc-backed checks for the Leomon follow-up; assets stay under build/."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import animsheet
import mmd
import motionstorage
from motiontailspace import interpolate_pose
from tools.models.silphymon_leomon import FIELD, CARE, author


class SilphymonLeomon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=ROOT/'build/silphymon/after/226-Silphymon.MMD'
        cls.path=ROOT/'build/silphymon/leomon/226-Silphymon.MMD'
        if not cls.source.is_file() or not cls.path.is_file():
            raise unittest.SkipTest('needs reconstructed before/after review models')
        cls.old=mmd.MMD.load(str(cls.source),226)
        cls.new=mmd.MMD.load(str(cls.path),226)
        cls.sk=mmd.exe().skeleton[226]

    def test_replay_mesh_and_fixed_storage(self):
        data,report=author(self.source.read_bytes())
        self.assertEqual(data,self.path.read_bytes())
        self.assertEqual(self.old.tmd.build(),self.new.tmd.build())
        self.assertTrue(motionstorage.require(data,21)['fits'])

    def test_effect_clocks_events_and_dash_trajectory(self):
        for slot in range(46,60):
            a,la,ea=animsheet.slot_frames(self.old,21,slot)
            b,lb,eb=animsheet.slot_frames(self.new,21,slot)
            self.assertEqual((len(a),la,ea),(len(b),lb,eb),slot)
            self.assertEqual([p[0] for p in a],[p[0] for p in b],slot)

    def test_native_cadence_and_closed_loops(self):
        native=mmd.MMD.load(str(ROOT/'extracted/CHDAT/MMD1/LEOM.MMD'),48)
        for slot in FIELD:
            a,la,_=animsheet.slot_frames(native,23,slot)
            b,lb,_=animsheet.slot_frames(self.new,21,slot)
            self.assertEqual((len(a),la),(len(b),lb),slot)
            self.assertEqual(a[-1][0][8]-a[0][0][8],b[-1][0][8]-b[0][0][8],slot)
            for bone in range(1,21):
                self.assertEqual(b[lb][bone][6:9],b[-1][bone][6:9],(slot,bone))

    def test_support_at_keys_and_display_samples(self):
        for slot in FIELD+list(range(46,60)):
            frames,_,_=animsheet.slot_frames(self.new,21,slot)
            for a,b in zip(frames,frames[1:]):
                for alpha in (0,1365,2730,4096):
                    p=interpolate_pose(a,b,alpha);p[0]=[4096]*3+[0]*6
                    mats=mmd.bone_matrices(self.new,p)
                    floor=max(sum(mats[k][1][j]*v[j] for j in range(3))+mats[k][1][3]
                              for k in range(1,21) for v in self.new.tmd.obj_verts(self.sk[k][0]))
                    self.assertLessEqual(floor,1.5,(slot,alpha,floor))

    def test_reviewed_size_and_voice(self):
        p=animsheet.slot_frames(self.new,21,0)[0][0]
        yy=[v[1] for tri in animsheet.world_tris(self.new,p,self.sk) for v in tri[0]]
        self.assertLess(max(yy)-min(yy),480)
        spec=json.loads((ROOT/'content/species/226-silphymon.json').read_text())
        self.assertEqual((spec['voice'],spec['partner']['voice']),(42,3))


if __name__=='__main__':
    unittest.main()
