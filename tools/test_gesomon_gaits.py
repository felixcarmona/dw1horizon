"""Check support, looping, storage, and untouched acting on the real import."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from motiondiscidentity import changed_programs
from tools.models.field_animations import gesomon, gesomon_hops


class GesomonGaits(unittest.TestCase):
    generator = gesomon
    @classmethod
    def setUpClass(cls):
        source = Path('build/imported-model-edit/edit/240-Gesomon.MMD')
        if not source.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 240')
        cls.source = source.read_bytes()
        cls.rig = json.loads(Path('content/species/240-gesomon.json').read_text())['model']['skeleton']
        cls.data, cls.report = cls.generator.build(cls.source, cls.rig)
        cls.old = mmd.MMD.parse(cls.source, 29)
        cls.new = mmd.MMD.parse(cls.data, 29)
        cls.new.type = 240

    def test_only_walk_and_run_change(self):
        self.assertEqual(changed_programs(self.old, self.new), [2, 4])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        self.assertTrue(self.report['storage']['fits'])

    def test_nine_cycles_have_no_body_or_distance_drift(self):
        for row in self.report['checks']:
            slot, period = row['slot'], row['period']
            player = mmd.AnimPlayer(self.new.anims.anims[self.new.anims.table[slot]], 29, slot)
            body, travel = [], []
            for tick in range(period*9):
                self.assertTrue(player.tick())
                if tick < period:
                    body.append(copy.deepcopy(player.pose[1:]))
                else:
                    self.assertEqual(player.pose[1:], body[tick % period])
                travel.append(player.base[2])
            for start in range(period, period*8, period):
                self.assertAlmostEqual(sum(travel[start:start+period]), -period*row['speed'], delta=1)

    def test_decoded_stance_tips_touch_floor_and_lift_in_recovery(self):
        for row in self.report['checks']:
            frames, _, _ = animsheet.slot_frames(self.new, 29, row['slot'])
            stance_errors, recovery = [], []
            for frame, plan in zip(frames[:-1], row['plan'][:-1]):
                w = gesomon.world(self.new, frame)
                supporting = 0
                for tip in plan:
                    bone = tip['tip']
                    verts = self.new.tmd.obj_verts(self.rig[bone][0])
                    bottom = max(sum(w[bone, 1, j]*v[j] for j in range(3))+w[bone, 1, 3] for v in verts)
                    self.assertLessEqual(bottom, 1.5)
                    if tip['stance']:
                        supporting += 1
                        stance_errors.append(abs(bottom))
                    else:
                        recovery.append(-bottom)
                if self.report['variant'] == 'terrestrial' or plan[0]['stance']:
                    self.assertGreaterEqual(supporting, 2)
                else:
                    self.assertEqual(supporting, 0)
            self.assertLess(max(stance_errors), 3.5)
            self.assertGreater(max(recovery), 25)

    def test_floor_clearance_between_logic_ticks(self):
        for row in self.report['checks']:
            frames, _, _ = animsheet.slot_frames(self.new, 29, row['slot'])
            for left, right in zip(frames[:-1], frames[1:]):
                for alpha in (1365/4096, 2730/4096):
                    pose = copy.deepcopy(left)
                    for b in range(29):
                        for c in range(9):
                            delta = right[b][c]-left[b][c]
                            if c in (3, 4, 5):
                                delta = (delta+2048)%4096-2048
                            pose[b][c] += delta*alpha
                    w = gesomon.world(self.new, pose)
                    for chain in gesomon.CHAINS:
                        bone = chain[-1]
                        bottom = max(sum(w[bone, 1, j]*v[j] for j in range(3))+w[bone, 1, 3]
                                     for v in self.new.tmd.obj_verts(self.rig[bone][0]))
                        self.assertLessEqual(bottom, 1.5, (row['slot'], bone, bottom))

    def test_modified_sources_rejected(self):
        with self.assertRaises(ValueError):
            gesomon.build(b'invalid', self.rig)


class GesomonHops(GesomonGaits):
    generator = gesomon_hops

    def test_native_takeoff_landing_and_mantle_deformation(self):
        self.assertEqual(self.report['donor'], 44)
        for row in self.report['checks']:
            frames, _, events = animsheet.slot_frames(self.new, 29, row['slot'])
            self.assertEqual(row['period'], 17)
            self.assertTrue(all(not tip['stance'] for tip in row['plan'][3]))
            self.assertTrue(all(tip['stance'] for tip in row['plan'][7]))
            self.assertLess(frames[3][1][7], frames[0][1][7]-40)
            self.assertLess(frames[8][1][1], 4096)
            self.assertTrue(any(t == 7 and kind == 'sound' for t, kind, _ in events))


if __name__ == '__main__':
    unittest.main()
