"""Check Pumpkinmon's idle (the import's hop with the legs attenuated) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 280`), or from the file named by
PUMPKINMON_MODEL. Before the change it is `pumpkinmon_idle.SOURCE`: the generator is run on it and its bytes are
checked; afterwards it is the result itself and the checks that need the old clips are skipped.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

try:
    import numpy as np
except ImportError:
    np = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from motiondiscidentity import changed_programs
from tools.models.field_animations import pumpkinmon_idle as gait

EXPECTED = '8944f680d63d3be0680139c144d99491dc59bf07a814c81e425b2969d7823a34'


class PumpkinmonIdle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if np is None:
            raise unittest.SkipTest('needs numpy')
        path = Path(os.environ.get('PUMPKINMON_MODEL', 'build/imported-model-edit/edit/280-Pumpkinmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 280')
        cls.rig = json.loads(Path('content/species/280-pumpkinmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[280] = cls.rig
        mmd.exe().bone_count[280] = len(cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, gait.NB)
            cls.old.type = 280
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, gait.NB)
        cls.new.type = 280
        cls.body = gait.Body(cls.new, cls.rig)

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, gait.NB, slot)[0]

    def need_old(self):
        if self.old is None:
            self.skipTest('needs the model before this change')

    def sole(self, frames):
        return np.array([self.body.lowest(p, set(gait.LEGS)) for p in frames])

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_idle_changes_and_other_slots_are_identical(self):
        self.need_old()
        self.assertEqual(changed_programs(self.old, self.new), [0])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        for slot, index in enumerate(self.old.anims.table):
            if slot != 0 and index is not None:
                self.assertEqual(self.frames(slot), self.frames(slot, self.old), slot)
        self.assertEqual(changed_programs(self.old, self.new), [0])        # slots 2, 3, 4 and 33: the same program, byte for byte
        self.assertEqual(self.frames(33), self.frames(0, self.old))          # the battle idle keeps the old program
        self.assertNotEqual(self.new.anims.table[0], self.new.anims.table[33])

    def test_everything_but_the_legs_is_the_original(self):
        self.need_old()
        old, new = self.frames(0, self.old), self.frames(0)
        self.assertEqual(len(new), len(old))
        for a, b in zip(old, new):
            for bone in range(gait.NB):
                if bone not in gait.LEGS:
                    self.assertEqual(a[bone], b[bone], bone)
        self.assertEqual(animsheet.slot_frames(self.new, gait.NB, 0)[2], animsheet.slot_frames(self.old, gait.NB, 0)[2])
        self.assertEqual(animsheet.slot_frames(self.new, gait.NB, 0)[1], animsheet.slot_frames(self.old, gait.NB, 0)[1])

    def test_legs_swing_and_rise_about_a_third(self):
        self.need_old()
        old, new = self.frames(0, self.old), self.frames(0)
        self.assertEqual(new[0], old[0])
        self.assertEqual(new[-1], new[0])                       # the loop still closes
        for bone in (12, 14):
            for k in (3, 5):
                a = max(abs(p[bone][k] - old[0][bone][k]) for p in old)
                b = max(abs(p[bone][k] - new[0][bone][k]) for p in new)
                self.assertLess(b, .4*a, (bone, k))
        lift_old, lift_new = self.sole(old), self.sole(new)
        self.assertGreater(float(lift_old.max()), 30)
        self.assertLess(float(lift_new.max()), 16)
        self.assertGreater(float(lift_new.min()), -1)           # nothing goes under the floor
        # no step is wilder than before
        for bone in gait.LEGS:
            for k in range(3, 9):
                so = max(abs(old[i + 1][bone][k] - old[i][bone][k]) for i in range(len(old) - 1))
                sn = max(abs(new[i + 1][bone][k] - new[i][bone][k]) for i in range(len(new) - 1))
                self.assertLessEqual(sn, max(so, 4), (bone, k))

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, gait.NB)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
