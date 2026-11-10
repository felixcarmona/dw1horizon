"""MetalSeadramon's field clips are authored on its own upright skeleton (needs the pre-overlay import)."""
import os
from pathlib import Path
import unittest

import animsheet
import mmd
from tools.models.field_animations import metal_seadramon, gliding


class MetalSeadramonSwim(unittest.TestCase):
    def test_clips_differ_and_keep_speed(self):
        folder = os.environ.get('DW_SPECIES_REPAIR_FIXTURES')
        if not folder or not (Path(folder)/'211-MetalSeadramon.MMD').is_file():
            self.skipTest('set DW_SPECIES_REPAIR_FIXTURES to the folder with 211-MetalSeadramon.MMD')
        source = (Path(folder)/'211-MetalSeadramon.MMD').read_bytes()
        skeleton = mmd.exe().skeleton[211]
        result, proof = metal_seadramon.build(source, skeleton)
        before = gliding.build(source, skeleton)[0]
        old = metal_seadramon._parse(before, skeleton)
        new = metal_seadramon._parse(result, skeleton)
        poses = {s: animsheet.slot_frames(new, 18, s)[0] for s in (0, 2, 3, 4)}
        for a, b in ((0, 2), (2, 4), (0, 4)):
            self.assertNotEqual(poses[a][:2], poses[b][:2])
        self.assertEqual([len(poses[s]) - 1 for s in (0, 2, 3, 4)], [60, 40, 40, 40])
        # the upright S rest pose stays: no bone strays more than 50 degrees from it, loops close exactly
        import retarget
        rest = retarget.rest_pose(new, 18, 0)
        for s in (0, 2, 3, 4):
            self.assertEqual(poses[s][0][1:], poses[s][-1][1:])
            for pose in poses[s]:
                for b in range(2, 18):
                    for ch in (3, 4, 5):
                        d = abs(pose[b][ch] - rest[b][ch]) % 4096
                        self.assertLess(min(d, 4096 - d), 50 * 4096 / 360, (s, b, ch))
        for s in (2, 3, 4):
            frames = animsheet.slot_frames(old, 18, s)[0]
            speed = (frames[-1][0][8] - frames[0][0][8]) / (len(frames) - 1)
            got = (poses[s][-1][0][8] - poses[s][0][0][8]) / (len(poses[s]) - 1)
            self.assertLess(abs(speed - got), 0.1)
        # every other program, the mesh and the care/battle slots are untouched
        for s in range(len(old.anims.table)):
            if s not in (0, 1, 2, 3, 4) and old.anims.table[s] is not None:
                self.assertEqual(animsheet.slot_frames(old, 18, s)[0], animsheet.slot_frames(new, 18, s)[0])
        self.assertEqual(proof['changed_slots'], [0, 1, 2, 3, 4])


if __name__ == '__main__':
    unittest.main()
