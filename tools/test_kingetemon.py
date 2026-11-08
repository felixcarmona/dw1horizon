"""Decoded regression checks for the reviewed KingEtemon model artifacts."""
import hashlib
import copy
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
from tools.models.resize import resize


class KingEtemon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = Path(os.environ.get('KINGETEMON_MODELS', ROOT / 'build/model-review'))
        if not all((folder / f'{name}.MMD').is_file() for name in ('before','after')):
            raise unittest.SkipTest('needs the reviewed before/after model artifacts')
        cls.cfg = json.loads((ROOT / 'content/models/authoring/kingetemon.json').read_text())
        cls.before = (folder / 'before.MMD').read_bytes()
        cls.after = (folder / 'after.MMD').read_bytes()
        cls.sk = cls.cfg['skeleton']
        mmd.exe().add_type(303, cls.sk)
        cls.old = mmd.MMD.parse(resize(cls.before,23,.85),23); cls.old.type = 303
        cls.new = mmd.MMD.parse(cls.after,23); cls.new.type = 303

    def test_source_mesh_and_original_console_storage(self):
        self.assertEqual(hashlib.sha256(self.before).hexdigest(),self.cfg['source_sha256'])
        self.assertEqual(self.old.tmd.build(),self.new.tmd.build())
        self.assertTrue(motionstorage.require(self.after,23)['fits'])

    def test_support_repair_preserves_acting_timing_and_events(self):
        for slot in self.cfg['ground_slots']:
            before,loop,events = animsheet.slot_frames(self.old,23,slot)
            after,new_loop,new_events = animsheet.slot_frames(self.new,23,slot)
            self.assertEqual((len(before),loop,events),(len(after),new_loop,new_events))
            for a,b in zip(before,after):
                for bone in range(23):
                    for channel in range(9):
                        cape = slot in self.cfg.get('cape_floor_slots',[]) and bone in (20,21,22) and channel in (3,4,5)
                        if (bone,channel) != (1,7) and not cape:
                            self.assertEqual(a[bone][channel],b[bone][channel],(slot,bone,channel))
                p = [list(v) for v in b]; p[0] = [4096]*3+[0]*6
                world = mmd.bone_matrices(self.new,p)
                bottom = max(sum(world[foot][1][j]*v[j] for j in range(3))+world[foot][1][3]
                             for foot in self.cfg['feet'] for v in self.new.tmd.obj_verts(self.sk[foot][0]))
                self.assertLessEqual(abs(bottom),4,(slot,bottom))
                if slot in self.cfg.get('cape_floor_slots',[]):
                    hem = max(sum(world[bone][1][j]*v[j] for j in range(3))+world[bone][1][3]
                              for bone in (19,20,21,22) for v in self.new.tmd.obj_verts(self.sk[bone][0]))
                    self.assertLessEqual(hem,1,(slot,hem))

    def test_other_programs_remain_exact_after_uniform_resize(self):
        changed = set(self.cfg['slots']+self.cfg['ground_slots'])
        for slot,index in enumerate(self.old.anims.table):
            if index is not None and slot not in changed:
                before = copy.deepcopy(self.old.anims.anims[index])
                after = copy.deepcopy(self.new.anims.anims[self.new.anims.table[slot]])
                before.tail = after.tail = b''
                self.assertEqual(before.build(),after.build(),slot)

    def test_native_gesture_timing_and_events(self):
        donor = mmd.MMD.load(str(ROOT / self.cfg['model']),42)
        for slot in self.cfg['slots']:
            source = self.cfg['donor_slots'].get(str(slot),slot)
            expected,loop,events = animsheet.slot_frames(donor,27,source)
            actual,new_loop,new_events = animsheet.slot_frames(self.new,23,slot)
            self.assertEqual((len(expected),loop),(len(actual),new_loop),slot)
            self.assertEqual([e for e in events if e[1]=='sound'],new_events,slot)
        # The three tosses share the same complete native performance.
        self.assertEqual(self.new.anims.table[56],self.new.anims.table[57])
        self.assertEqual(self.new.anims.table[56],self.new.anims.table[58])

    def test_native_gestures_have_continuous_euler_tracks(self):
        # The 60 FPS renderer interpolates Euler channels between logic ticks.
        # Equivalent wrist poses must not switch charts by half a turn.
        for slot in self.cfg['slots']:
            frames,_,_ = animsheet.slot_frames(self.new,23,slot)
            for tick,(a,b) in enumerate(zip(frames,frames[1:])):
                for bone in range(1,23):
                    delta = [(y-x+2048)%4096-2048 for x,y in zip(a[bone][3:6],b[bone][3:6])]
                    self.assertLessEqual(max(map(abs,delta)),1024,(slot,tick,bone))


if __name__ == '__main__':
    unittest.main()
