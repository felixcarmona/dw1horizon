"""Native Angemon motion and Card Battle MagnaAngemon binding integration proof.

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
        candidate = os.environ.get('DW_NATIVE_ANGEL_MODEL')
        if not candidate:
            raise unittest.SkipTest('set DW_NATIVE_ANGEL_MODEL to the bound model (rig_angemon output or edit.py get)')
        cls.spec = json.loads(Path('content/imports/specs/MagnaAngemon.json').read_text())
        cls.own = json.loads(Path('content/species/206-magnaangemon.json').read_text())
        cls.data = Path(candidate).read_bytes()
        cls.model = mmd.MMD.parse(cls.data, 26)
        cls.native = mmd.MMD.load(cls.spec['source']['mmd'], 20)
        # the bones the wings and the back cloth ride turn about the Card Battle joints
        cls.pivots = {cls.spec['map'][str(b)] for b in cls.spec['pivots']}

    def donor(self, slot):
        if 46 <= slot < 46 + len(self.spec['technique_slots']):
            return self.spec['technique_slots'][slot - 46]
        return self.spec['extra_slots'].get(str(slot), slot)

    def test_every_program_uses_native_angles_timing_and_events(self):
        scale = self.spec['scale']
        joints = {}
        for slot, index in enumerate(self.model.anims.table):
            if index is None:
                continue
            expected = copy.deepcopy(self.native.anims.anims[self.native.anims.table[self.donor(slot)]])
            actual = self.model.anims.anims[index]
            self.assertEqual(actual.frame_count, expected.frame_count, slot)
            self.assertEqual(actual.has_scale, expected.has_scale, slot)
            # Every rotation and scale is native. Translations are a uniform size conversion, but for the pivot bones'
            # joints, the same in every program; there is no authored motion or new key time.
            for bone, (before, after) in enumerate(zip(expected.pose, actual.pose), 1):
                self.assertEqual(after[:-3], before[:-3], slot)
                if bone in self.pivots:
                    self.assertEqual(joints.setdefault(bone, after[-3:]), after[-3:], (slot, bone))
                else:
                    self.assertEqual(after[-3:], [round(v * scale) for v in before[-3:]], slot)
            expected.instrs = [i for i in expected.instrs if i['op'] != 'tex']
            for ins in expected.instrs:
                if ins['op'] == 'key':
                    for group in ins['bones']:
                        if group['bone'] in self.pivots:     # their joints are never keyed
                            self.assertFalse({'tx', 'ty', 'tz'} & set(group['vals']), slot)
                        for channel, value in list(group['vals'].items()):
                            if channel in ('tx', 'ty', 'tz'):
                                group['vals'][channel] = round(value * scale)
            self.assertEqual(actual.instrs, expected.instrs, slot)
        self.assertEqual(set(joints), self.pivots)

    def test_native_hierarchy_and_card_battle_pieces(self):
        rig = self.own['model']['skeleton']
        self.assertEqual(len(rig), 26)
        self.assertEqual([p for _, p in rig], [p for _, p in mmd.exe().skeleton[20]])
        source = self.spec['mesh']['skeleton']
        carried = {}
        for sb, tb in self.spec['map'].items():
            carried.setdefault(tb, []).append(int(sb))
        grafted = {g['bone'] for g in self.spec['grafts']['pieces']}
        source_model = None
        sizes = Path(self.spec['mesh']['file'])
        if sizes.is_file():
            source_model = mmd.MMD.parse(sizes.read_bytes(), len(source))
        drawn = 0
        for bone, (obj, _) in enumerate(rig):
            if obj < 0:
                self.assertNotIn(bone, carried)
                continue
            drawn += 1
            self.assertIn(bone, carried)
            if source_model is not None:
                n = sum(source_model.tmd.objects[source[sb][0]].nvert for sb in carried[bone])
                have = self.model.tmd.objects[obj].nvert
                # every Card Battle vertex, plus the World 2003 shield and bracelet on the arms
                (self.assertGreater if bone in grafted else self.assertEqual)(have, n, bone)
        self.assertEqual(len(self.model.tmd.objects), drawn)
        # the back cloth rides Angemon's own cloth bone, so it swings with the clips
        self.assertEqual(self.spec['map']['11'], 25)

    def test_identity_storage_and_three_disc_sources(self):
        self.assertEqual(self.own['level'], 'ultimate')
        self.assertEqual((self.own['voice'], self.own['partner']['voice']), (18, 11))
        self.assertEqual((self.own['model']['height'], self.own['model']['radius']), (608, 187))
        storage = motionstorage.audit(self.data, 26)
        self.assertTrue(storage['fits'], storage)
        records = json.loads(Path('content/modeldelta/models.json').read_text())['models']
        row = next(r for r in records if r['id'] == 206)
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), row['mmd']['sha256'])
        self.assertEqual([s['path'] for s in row['mmd']['sources']],
                         [self.spec['mesh']['file'], self.spec['source']['mmd'], self.spec['grafts']['mesh']['file']])
        self.assertEqual([s['path'] for s in row['tim']['sources']],
                         [self.spec['mesh']['texture'], self.spec['grafts']['mesh']['file'][:-4] + '.TIM'])
        registry = json.loads(Path('content/models/imports/models.json').read_text())
        self.assertEqual(registry['206']['native_animation_donor'], 20)


if __name__ == '__main__':
    unittest.main()
