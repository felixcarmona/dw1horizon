"""Check SkullMammothmon's walk, tired walk and run on the real import: the front legs stay out of the head.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 268`). Before the change it is
`skullmammothmon_clash.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself
and the checks that need the old clips are skipped.
"""
import copy
import hashlib
import math
from pathlib import Path
import statistics
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import skullmammothmon_clash as clash

EXPECTED = '1adf3349b738a7d9a44ee13fa8169f1c85b3dbcd7b6736e50befdb6042f4a2c5'
NB = clash.NB
CLIPS = (2, 3, 4, 35, 36)            # 35 plays slot 2's program, 36 slot 4's
UNTOUCHED = (0, 1, 5, 6, 7, 8, 9, 10)


class SkullMammothmonClash(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/268-SkullMammothmon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 268')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == clash.SOURCE:
            cls.old = clash._parse(data)
            data, cls.proof = clash.build(data)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = clash._parse(data)
        cls.scenes = {}

    @classmethod
    def frames(cls, slot, model=None):
        return animsheet.slot_frames(model or cls.new, NB, slot)[0]

    def scene(self, slot):
        if slot not in self.scenes:
            self.scenes[slot] = clash.Scene(self.new, slot)
        return self.scenes[slot]

    def need_old(self):
        if self.old is None:
            self.skipTest('needs the model before this change')

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_front_legs_never_cross_the_head(self):
        for slot in CLIPS:
            for t, base in enumerate(self.scene(slot).base):
                self.assertEqual((base['L']['head'], base['R']['head']), (0, 0), (slot, t))

    def test_the_original_clips_did_cross(self):
        self.need_old()
        for slot in (2, 3, 4):
            counts = [b['L']['head'] + b['R']['head'] for b in clash.Scene(self.old, slot).base]
            self.assertGreater(sum(c > 0 for c in counts), len(counts) // 2, slot)

    def test_no_new_clash_with_the_body_or_the_other_leg(self):
        self.need_old()
        for slot in CLIPS:
            old, new = clash.Scene(self.old, slot).base, self.scene(slot).base
            for t in range(len(new)):
                for side in 'LR':
                    self.assertLessEqual(new[t][side]['rest'], old[t][side]['rest'], (slot, t, side))
                # the neck turns about its joint with the chest, so the head's overlap with the chest grows a little
                self.assertLessEqual(new[t]['hb'], 3 * old[t]['hb'], (slot, t, 'head'))

    def test_feet_stay_where_the_floor_is(self):
        self.need_old()
        for slot in CLIPS:
            old, new = clash.Scene(self.old, slot).base, self.scene(slot).base
            for t in range(len(new)):
                for side in 'LR':
                    a, b = old[t][side]['low'], new[t][side]['low']
                    self.assertLessEqual(b, max(a, 1.5) + .01, (slot, t, side))              # nothing sinks into the floor
                    if a > -clash.FLOOR:
                        self.assertGreaterEqual(b, a - 4.0, (slot, t, side))               # a planted foot stays planted

    def test_only_the_corrected_bones_changed_and_the_loops_close(self):
        self.need_old()
        corrected = {b for b, _ in clash.CHANNELS}
        for slot in CLIPS:
            old, loop_old, _ = animsheet.slot_frames(self.old, NB, slot)
            new, loop_new, _ = animsheet.slot_frames(self.new, NB, slot)
            self.assertEqual((len(old), loop_old), (len(new), loop_new), slot)
            for a, b in zip(old, new):
                for bone in range(NB):
                    if bone not in corrected:
                        self.assertEqual(a[bone], b[bone], (slot, bone))
                for bone in corrected:
                    changed = {i for i in range(9) if a[bone][i] != b[bone][i]}
                    self.assertTrue(changed <= {c for bb, c in clash.CHANNELS if bb == bone}, (slot, bone, changed))
            for bone, chan in clash.CHANNELS:
                self.assertEqual(new[-1][bone][chan], new[0][bone][chan], (slot, bone, chan))

    def test_other_programs_and_the_mesh_are_unchanged(self):
        self.need_old()
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        self.assertEqual(sorted(self.proof['changed']), [2, 3, 4, 35, 36])
        for slot in UNTOUCHED:
            if self.old.anims.table[slot] is None:
                continue
            self.assertEqual(self.old.anims.anims[self.old.anims.table[slot]].build(),
                             self.new.anims.anims[self.new.anims.table[slot]].build(), slot)

    def test_the_correction_is_small_and_smooth(self):
        for table in (clash.TABLE[2], clash.TABLE[3], clash.TABLE[4]):
            n = len(table)
            for col, (most, jump) in enumerate(((17, 5), (45, 12)) + ((17, 8),) * 8):
                values = [row[col] for row in table]
                self.assertLessEqual(max(abs(v) for v in values), most, col)
                steps = [abs(values[(i + 1) % n] - values[i]) for i in range(n)]
                self.assertLessEqual(max(steps), jump, col)

    def test_no_joint_jumps_in_the_corrected_bones(self):
        """The neck, which the correction moves most, turns smoothly; the legs keep the source's own turns (a swing is a
        fast turn by nature), so a leg may not turn faster in a tick than it did in the source."""
        def turns(frames, bone):
            out = []
            for a, b in zip(frames, frames[1:]):
                m = clash.R.m3mul(clash.R.rot_of(b[bone]), [list(r) for r in zip(*clash.R.rot_of(a[bone]))])
                out.append(math.acos(max(-1., min(1., (m[0][0] + m[1][1] + m[2][2] - 1) / 2))))
            return out
        for slot in (2, 3, 4):
            new = turns(self.frames(slot), clash.HEAD)
            self.assertLessEqual(max(new), max(3.0 * statistics.median(new), math.radians(3)), slot)
            if self.old is not None:
                for bone in sorted({b for b, _ in clash.CHANNELS} - {clash.HEAD}):
                    before = max(turns(self.frames(slot, self.old), bone))
                    self.assertLessEqual(max(turns(self.frames(slot), bone)), before + math.radians(1.5), (slot, bone))

    def test_idle_and_the_rest_are_untouched_by_the_table(self):
        self.assertEqual(self.frames(0), self.frames(0, self.old or self.new))

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, NB)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
