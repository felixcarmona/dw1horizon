"""Integration checks against the pinned imported model and native Ogremon."""
import copy
import json
import os
from pathlib import Path
import unittest
import mmd
import animsheet
from motiondiscidentity import program
from tools.models.field_animations import pace, vilemon

class VilemonWalk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=Path(os.environ.get('VILEMON_MODEL','build/imported-model-edit/edit/295-Vilemon.MMD'))
        if not p.exists():raise unittest.SkipTest('needs the imported Vilemon model and DW1 extraction')
        cls.rig=json.loads(Path('content/species/295-vilemon.json').read_text())['model']['skeleton']
        data,cls.proof=pace.build(p.read_bytes(),cls.rig)
        cls.new=mmd.MMD.parse(data,21);cls.new.type=295
        profile=json.loads(pace.MANIFEST.read_text())['295']
        raw=mmd.MMD.parse(p.read_bytes(),21);raw.type=295
        old=copy.deepcopy(raw)
        animation,_=pace._author(raw,cls.rig,2,profile['slots']['2'],pace._feet(raw,cls.rig))
        old.anims.table[2]=len(old.anims.anims);old.anims.anims.append(animation)
        cls.old=old

    def test_run_and_every_other_slot_mesh_and_wrist_grip_exact(self):
        self.assertEqual(self.new.tmd.build(),self.old.tmd.build())
        for slot,index in enumerate(self.old.anims.table):
            if index is not None and slot!=2:
                self.assertEqual(program(self.new.anims.anims[self.new.anims.table[slot]]),program(self.old.anims.anims[index]),slot)
        before,loop,events=animsheet.slot_frames(self.old,21,2)
        after,newloop,newevents=animsheet.slot_frames(self.new,21,2)
        self.assertEqual((len(after),newloop,newevents),(len(before),loop,events))
        for a,b in zip(before,after):
            for bone in range(21):
                self.assertEqual(a[bone][:3],b[bone][:3])
                self.assertEqual(a[bone][6:],b[bone][6:])
                if bone not in (13,14,16,17):self.assertEqual(a[bone],b[bone],bone)

    def test_both_wrists_swing_and_loop_has_no_accumulating_drift(self):
        frames=animsheet.slot_frames(self.new,21,2)[0]
        zs={b:[] for b in (15,18)}
        for frame in frames:
            p=copy.deepcopy(frame);p[0]=[4096]*3+[0]*6
            w=mmd.bone_matrices(self.new,p)
            for b in zs:zs[b].append(w[b][2][3])
        for b,v in zs.items():self.assertGreater(max(v)-min(v),50,b)
        player=mmd.AnimPlayer(self.new.anims.anims[self.new.anims.table[2]],21,2)
        first=[]
        for tick in range(60*9):
            self.assertTrue(player.tick())
            if tick<60:first.append(copy.deepcopy(player.pose))
            else:self.assertEqual(player.pose,first[tick%60],tick)
        self.assertTrue(self.proof['storage']['fits'])

    def test_unreviewed_input_rejected(self):
        with self.assertRaises(ValueError):vilemon.build(b'changed',self.rig)
