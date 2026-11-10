"""Private-disc proof of Submarimon's repair: no stencil faces, and a steady tail screw in every looping clip."""
from pathlib import Path
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
import animsheet
import mmd
import motionstorage
from tools.models import repair_submarimon as R

MODEL = Path('build/imported-model-edit/edit/202-Submarimon.MMD')   # tools/models/edit.py get 202


class SubmarimonRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEL.is_file():
            raise unittest.SkipTest('requires `tools/models/edit.py get 202` output (private source games)')
        mmd.exe().add_type(202, [(-1, -1), (0, 0), (1, 1), (2, 2), (3, 1), (4, 1), (5, 1), (6, 1), (7, 3), (8, 3), (9, 3)])
        cls.data = MODEL.read_bytes()
        cls.model = mmd.MMD.parse(cls.data, 11)
        cls.model.type = 202

    def test_no_stencil_faces_on_the_body(self):
        self.assertEqual(R.twins(self.model), [])
        self.assertEqual(len(self.model.tmd.objects[0].prims), 178)

    def test_screw_turns_steadily_in_idle_walk_and_run(self):
        for slot in (0, 2, 3, 4):
            frames, loop, _ = animsheet.slot_frames(self.model, 11, slot)
            rz = [f[8][5] for f in frames]
            steps = {b - a for a, b in zip(rz, rz[1:])}
            self.assertLessEqual(max(steps) - min(steps), 1, slot)
            self.assertTrue(-300 < max(steps) < -100, (slot, steps))
            self.assertEqual((rz[-1] - rz[0]) % 4096, 0, slot)   # whole turns: the loop has no jump

    def test_console_storage_fits(self):
        self.assertTrue(motionstorage.require(self.data, 11)['fits'])


if __name__ == '__main__':
    unittest.main()
