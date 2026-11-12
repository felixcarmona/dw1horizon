"""Check Creepymon's idle, walk, tired walk and run (species 312) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 312`; CREEPYMON_MODEL names another
path). The test runs `creepymon_gait.build` on it and checks the clips: integer-tick loops that close, one step per
tick, native speeds ordered tired < walk < run, an idle that stays in place, the same mesh as the chibi model, and the
resident buffer.
"""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import creepymon_gait as gait

BONES = 20
TICKS = {2: 20, 3: 24, 4: 14}
SPEED = {2: 16, 3: 12, 4: 38}
IDLE_TICKS = 72


class CreepymonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('CREEPYMON_MODEL', 'build/imported-model-edit/edit/312-Creepymon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 312')
        cls.rig = json.loads(Path('content/species/312-creepymon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[312] = cls.rig
        mmd.exe().bone_count[312] = BONES
        cls.data, cls.report = gait.build(path.read_bytes(), cls.rig)
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 312

    def frames(self, slot):
        return animsheet.slot_frames(self.new, BONES, slot)[0]

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_the_idle_stands_still_and_closes(self):
        frames = self.frames(0)
        self.assertEqual(len(frames) - 1, IDLE_TICKS)
        self.assertEqual({f[0][8] for f in frames}, {0})
        for b in range(1, BONES):
            for i in range(3, 6):
                self.assertIn((frames[0][b][i] - frames[-1][b][i]) % 4096, (0, 1, 4095), (b, i))

    def test_cycle_lengths_speeds_and_their_order(self):
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks, slot)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(len(steps), 1, slot)
            speeds[slot] = -steps.pop()
            self.assertEqual(speeds[slot], SPEED[slot])
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])
        self.assertTrue(15 <= speeds[2] <= 31 and 10 <= speeds[3] <= 20 and 35 <= speeds[4] <= 52)

    def test_loops_are_seamless(self):
        for slot in (0, *TICKS):
            frames = self.frames(slot)
            first, last = frames[0], frames[-1]
            for b in range(1, BONES):
                for i in range(3, 6):
                    self.assertIn((first[b][i] - last[b][i]) % 4096, (0, 1, 4095), (slot, b, i))
                for i in (6, 7, 8):
                    self.assertLessEqual(abs(first[b][i] - last[b][i]), 1, (slot, b, i))

    def test_the_mesh_is_the_chibi_models(self):
        self.assertEqual(self.report['changed_slots'][:1], [0])


if __name__ == '__main__':
    unittest.main()
