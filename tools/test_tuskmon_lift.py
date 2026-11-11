"""Check Tuskmon's lifted body and stiffer horns on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 253`). Before the change it is
`tuskmon_lift.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and
the checks that need the old clips are skipped.
"""
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from motiondiscidentity import changed_programs
from tools.models.field_animations import tuskmon_lift as lift

EXPECTED = '3369b03344b9f3c195a0c12f6acfdc26fdae16f9615de4ce0e8eebc37543b805'
RAISED = {0: 15, 2: 10, 3: 10, 4: 6}        # least units the pelvis stands higher, on average, than before


class TuskmonLift(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/253-Tuskmon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 253')
        cls.rig = json.loads(Path('content/species/253-tuskmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[253] = cls.rig
        mmd.exe().bone_count[253] = len(cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == lift.SOURCE:
            cls.old = mmd.MMD.parse(data, 22)
            cls.old.type = 253
            data, _ = lift.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, 22)
        cls.new.type = 253
        cls.body = lift.Body(cls.new, cls.rig)

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, 22, slot)[0]

    def need_old(self):
        if self.old is None:
            self.skipTest('needs the model before this change')

    def pelvis(self, slot, model=None):
        model = model or self.new
        body = lift.Body(model, self.rig)
        return [-body.world(f)[11, 1, 3] for f in self.frames(slot, model)]

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_field_clips_change_and_keep_their_length(self):
        self.need_old()
        self.assertEqual(changed_programs(self.old, self.new), [0, 1, 2, 3, 4])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        for slot in range(5):
            self.assertEqual(len(self.frames(slot)), len(self.frames(slot, self.old)))
            before = mmd.AnimPlayer(self.old.anims.anims[self.old.anims.table[slot]], 22, slot)
            after = mmd.AnimPlayer(self.new.anims.anims[self.new.anims.table[slot]], 22, slot)
            for _ in range(60):
                self.assertTrue(before.tick() and after.tick())
                self.assertEqual(before.base, after.base)

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, 22)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_body_stands_higher(self):
        self.need_old()
        for slot, units in RAISED.items():
            now, then = self.pelvis(slot), self.pelvis(slot, self.old)
            self.assertGreaterEqual(sum(now)/len(now) - sum(then)/len(then), units, slot)
            self.assertGreaterEqual(min(now) - min(then), units - 4, slot)

    def test_claws_stay_where_they_were(self):
        self.need_old()
        for slot in (0, 2, 3, 4):
            for a, b in zip(self.frames(slot, self.old), self.frames(slot)):
                wa, wb = self.body.world(a), self.body.world(b)
                for foot in (14, 17):
                    self.assertLess(float(abs(wa[foot, :3, 3] - wb[foot, :3, 3]).max()), 1.5, (slot, foot))
                    self.assertLess(float(abs(wa[foot, :3, :3] - wb[foot, :3, :3]).max()), .01, (slot, foot))

    def test_floor_contact(self):
        for slot in (0, 2, 3, 4):
            low = [self.body.lowest(f) for f in self.frames(slot)]
            self.assertGreaterEqual(min(low), -2, slot)
            self.assertLessEqual(max(low), 9, slot)

    def test_horns_are_rigid_on_the_chest(self):
        for slot in range(5):
            frames = self.frames(slot)
            for k in range(3, 9):
                self.assertEqual({tuple(f[lift.HORN][3:9]) for f in frames}.__len__(), 1, (slot, k))
            self.assertEqual(max(lift.horn_angles(frames)), 0, slot)

    def test_loops_are_seamless(self):
        for slot in range(5):
            frames = self.frames(slot)
            self.assertEqual(frames[-1][1:], frames[0][1:], slot)


if __name__ == '__main__':
    unittest.main()
