"""Check Shadramon's calm idle and the looser walk and run on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 250`). Before the change it is
`shadramon_loose.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and
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
from tools.models.field_animations import shadramon_loose as loose

EXPECTED = 'e01d04f9b618b712301ac6945328131e4e66d447505a97e3cf5dc29bb06acfa0'


class ShadramonLoose(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/250-Shadramon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 250')
        cls.rig = json.loads(Path('content/species/250-shadramon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[250] = cls.rig
        mmd.exe().bone_count[250] = len(cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == loose.SOURCE:
            cls.old = mmd.MMD.parse(data, 18)
            cls.old.type = 250
            data, cls.report = loose.build(data, cls.rig)
            cls.data = data
        elif digest == EXPECTED:
            cls.data = data
            cls.report = None
        else:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.new = mmd.MMD.parse(cls.data, 18)
        cls.new.type = 250
        cls.body = loose.Body(cls.new, cls.rig)

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, 18, slot)[0]

    def need_old(self):
        if self.old is None:
            self.skipTest('needs the model before this change')

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_idle_walk_and_run_change(self):
        self.need_old()
        self.assertEqual(changed_programs(self.old, self.new), [0, 2, 4])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        # the tired walk, the battle idle (slot 33, which shared the old idle) and the care clips are the old ones
        for slot in (1, 3, 5, 18, 33):
            self.assertEqual(self.frames(slot), self.frames(slot, self.old), slot)

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, 18)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_idle_keeps_its_length_and_loops(self):
        idle = self.frames(0)
        self.assertEqual(len(idle), 73)
        self.assertEqual(idle[-1], idle[0])

    def test_idle_stays_on_the_floor(self):
        low = [self.body.lowest(p) for p in self.frames(0)]
        self.assertGreaterEqual(min(low), -1)
        self.assertLessEqual(max(low), 4)
        self.assertLessEqual(max(low) - min(low), 3.5)
        pelvis = [-self.body.world(p)[1, 1, 3] for p in self.frames(0)]
        self.assertLessEqual(max(pelvis) - min(pelvis), 6)

    def test_idle_claws_do_not_slide(self):
        frames = self.frames(0)
        ankles = [[self.body.world(p)[b, :3, 3] for b in (10, 13)] for p in frames]
        for i in range(2):
            for a in ankles:
                self.assertLess(float(abs(a[i] - ankles[0][i]).max()), 1.5)         # angles are stored in 1/4096 turns

    def test_idle_moves_gently_but_it_moves(self):
        frames = self.frames(0)
        ring = frames[:-1] + frames[:1]
        for a, b in zip(ring, ring[1:]):
            for bone in range(1, 18):
                for k in range(3, 6):
                    self.assertLessEqual(abs(a[bone][k] - b[bone][k]), 60, bone)
        for bone in (1, 2, 3, 4, 6, 14, 15, 16, 17):
            spans = [max(p[bone][k] for p in frames) - min(p[bone][k] for p in frames) for k in (3, 4, 5)]
            self.assertGreater(max(spans), 8, bone)

    def test_walk_and_run_keep_speed_planting_and_the_old_feet(self):
        self.need_old()
        for slot, speed in ((2, 16), (4, 38)):
            before = mmd.AnimPlayer(self.old.anims.anims[self.old.anims.table[slot]], 18, slot)
            after = mmd.AnimPlayer(self.new.anims.anims[self.new.anims.table[slot]], 18, slot)
            old, new = self.frames(slot, self.old), self.frames(slot)
            self.assertEqual(len(old), len(new))
            for tick, (a, b) in enumerate(zip(old, new)):
                wa, wb = self.body.world(a), self.body.world(b)
                for foot in (10, 13):
                    self.assertLess(float(abs(wa[foot, :3, 3] - wb[foot, :3, 3]).max()), 1.0, (slot, tick, foot))
                    self.assertLess(float(abs(wa[foot, :3, :3] - wb[foot, :3, :3]).max()), .01, (slot, tick, foot))
                self.assertTrue(before.tick() and after.tick())
                self.assertEqual(after.base, [0, 0, -speed] if tick else [0, 0, 0])

    def test_walk_and_run_loop_and_have_no_equal_sides(self):
        for slot in (2, 4):
            frames = self.frames(slot)
            self.assertEqual(frames[-1][1:], frames[0][1:])
            span = lambda bone, k: max(p[bone][k] for p in frames) - min(p[bone][k] for p in frames)
            self.assertNotEqual(span(4, 3), span(6, 3))
            self.assertGreater(abs(span(4, 3) - span(6, 3)), 20)
            lobes = {span(b, 4) for b in (14, 15, 16, 17)}
            self.assertEqual(len(lobes), 4)
            # the pelvis sways and turns
            self.assertGreater(max(p[1][6] for p in frames) - min(p[1][6] for p in frames), 5)
            self.assertGreater(max(p[1][4] for p in frames) - min(p[1][4] for p in frames), 20)

    def test_gaits_stay_on_the_floor(self):
        for slot in (2, 4):
            low = [self.body.lowest(p) for p in self.frames(slot)]
            self.assertGreaterEqual(min(low), -1)
            self.assertLessEqual(max(low), 8)


if __name__ == '__main__':
    unittest.main()
