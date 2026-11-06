"""Native Angemon motion and World 2003 MagnaAngemon binding integration proof.

Set DW_NATIVE_ANGEL_MODEL to the candidate MMD or edit.py get output. The native
reference comes from the player's extraction; no game assets are test fixtures.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import unittest

import mmd
import motionstorage


class NativeAngemonRig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidate=os.environ.get('DW_NATIVE_ANGEL_MODEL')
        if not candidate:
            raise unittest.SkipTest('set DW_NATIVE_ANGEL_MODEL to the final provider model')
        cls.spec=json.loads(Path('content/imports/specs/MagnaAngemon.json').read_text())
        cls.own=json.loads(Path('content/species/206-magnaangemon.json').read_text())
        cls.data=Path(candidate).read_bytes()
        cls.model=mmd.MMD.parse(cls.data,26)
        cls.native=mmd.MMD.load(cls.spec['source']['mmd'],20)

    def test_every_program_uses_native_angles_timing_and_events(self):
        scale=self.spec['scale']
        for slot,index in enumerate(self.model.anims.table):
            if index is None:
                continue
            if 46<=slot<46+len(self.spec['technique_slots']):
                donor=self.spec['technique_slots'][slot-46]
            else:
                donor=self.spec['extra_slots'].get(str(slot),slot)
            expected=copy.deepcopy(self.native.anims.anims[self.native.anims.table[donor]])
            actual=self.model.anims.anims[index]
            self.assertEqual(actual.frame_count,expected.frame_count,slot)
            self.assertEqual(actual.has_scale,expected.has_scale,slot)
            # Every rotation and scale is native. Only a uniform size conversion
            # touches translations; there is no authored motion or new key time.
            for before,after in zip(expected.pose,actual.pose):
                self.assertEqual(after[:-3],before[:-3],slot)
                self.assertEqual(after[-3:],[round(v*scale) for v in before[-3:]],slot)
            expected.instrs=[i for i in expected.instrs if i['op']!='tex']
            for ins in expected.instrs:
                if ins['op']=='key':
                    for group in ins['bones']:
                        for channel,value in list(group['vals'].items()):
                            if channel in ('tx','ty','tz'):
                                group['vals'][channel]=round(value*scale)
            self.assertEqual(actual.instrs,expected.instrs,slot)

    def test_native_hierarchy_and_complete_rigid_wings(self):
        rig=self.own['model']['skeleton']
        self.assertEqual(len(rig),26)
        self.assertEqual([p for _,p in rig],[p for _,p in mmd.exe().skeleton[20]])
        for bone in (10,12):
            obj=rig[bone][0]
            # Each complete wing has both broad feather fans, sharing a
            # single native hinge. Its panels cannot acquire separate motion.
            self.assertEqual(self.model.tmd.objects[obj].nvert,28)
            self.assertEqual(len(self.model.tmd.objects[obj].prims),28)
        self.assertEqual(len(self.model.tmd.objects),17)

    def test_native_staff_texture_and_hand_binding(self):
        texture=Path(os.environ['DW_NATIVE_ANGEL_MODEL']).with_suffix('.TIM')
        if not texture.is_file():
            self.skipTest('candidate TIM required for staff atlas proof')
        own=mmd.Tim4(texture.read_bytes())
        native=mmd.load_tim('extracted/CHDAT/ALLTIM.TIM',20)
        self.assertEqual(own.pal[14],native.pal[9])
        for y in range(8):
            self.assertEqual(own.idx[y*256:y*256+40],native.idx[(72+y)*256+136:(72+y)*256+176])
        obj=self.own['model']['skeleton'][9][0]
        staff=[p.decode()for p in self.model.tmd.objects[obj].prims if (p.decode().get('cba',0)>>6)-488==14]
        self.assertEqual(len(staff),8)
        self.assertEqual(self.spec['map']['28'],9)

    def test_identity_storage_and_two_disc_sources(self):
        self.assertEqual(self.own['level'],'ultimate')
        self.assertEqual((self.own['voice'],self.own['partner']['voice']),(18,11))
        self.assertEqual((self.own['model']['height'],self.own['model']['radius']),(608,187))
        self.assertEqual(len(self.own['techniques']),14)
        self.assertEqual(self.spec['dw3'],'M211HANG')
        self.assertEqual(self.spec['map']['9'],18)
        storage=motionstorage.audit(self.data,26)
        self.assertTrue(storage['fits'],storage)
        records=json.loads(Path('content/modeldelta/models.json').read_text())['models']
        row=next(r for r in records if r['id']==206)
        self.assertEqual(hashlib.sha256(self.data).hexdigest(),row['mmd']['sha256'])
        self.assertEqual(row['mmd']['sources'][1]['path'],self.spec['source']['mmd'])
        registry=json.loads(Path('content/models/imports/models.json').read_text())
        self.assertEqual(registry['206']['native_animation_donor'],20)
