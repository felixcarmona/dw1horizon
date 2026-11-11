"""Check Gesomon's grounded idle and its tired walk on the real import."""
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from motiondiscidentity import changed_programs
from tools.models.field_animations import gesomon, gesomon_rest as rest


class GesomonRest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path('build/imported-model-edit/edit/240-Gesomon.MMD')
        if not source.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 240')
        cls.rig = json.loads(Path('content/species/240-gesomon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(240, cls.rig)
        cls.walking, _ = gesomon.build(source.read_bytes(), cls.rig)
        cls.data, cls.report = rest.build(source.read_bytes(), cls.rig)
        cls.old = mmd.MMD.parse(cls.walking, 29)
        cls.new = mmd.MMD.parse(cls.data, 29)
        cls.old.type = cls.new.type = 240
        cls.body = rest.Body(cls.new, cls.rig)

    def frames(self, slot):
        return animsheet.slot_frames(self.new, 29, slot)[0]

    def lowest(self, slot):
        return [self.body.low(self.body.world(p), range(1, 29)) for p in self.frames(slot)[:-1]]

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_idle_the_arms_and_the_tired_walk_change(self):
        self.assertEqual(changed_programs(self.old, self.new), [0, 1, 2, 3, 4, 18])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        self.assertEqual(self.new.anims.table[0], self.new.anims.table[18])

    def test_storage_fits_the_resident_buffer(self):
        storage = self.report['storage']
        self.assertTrue(storage['fits'])
        self.assertLessEqual(storage['resident_bytes'], 100352)

    def test_idle_stands_on_the_floor(self):
        low = self.lowest(0)
        self.assertLessEqual(max(low), 3.5)
        self.assertGreaterEqual(min(low), -2.5)
        self.assertLessEqual(max(low) - min(low), 5)
        self.assertEqual(len(low), 83)        # the import's breathing and sway keep their length

    def test_tired_walk_stays_on_the_floor_and_loops(self):
        low = self.lowest(3)
        self.assertGreaterEqual(min(low), -2.5)
        self.assertLessEqual(max(low), 3.5)
        frames = self.frames(3)
        self.assertEqual(len(frames), rest.LOOP + 1)
        self.assertEqual(frames[-1][1:], frames[0][1:])
        zs = [p[0][8] for p in frames]
        steps = [a - b for a, b in zip(zs, zs[1:])]
        self.assertTrue(all(10 <= s <= 13 for s in steps), steps)

    def arm_bones(self, side):
        return (4, 5, 6) if side > 0 else (8, 9, 10)

    def test_tired_arms_lie_on_the_floor_behind_the_body(self):
        for p in self.frames(3)[:-1]:
            w = self.body.world(p)
            for side in (1, -1):
                for b in self.arm_bones(side):
                    self.assertGreaterEqual(self.body.low(w, [b]), -5, b)      # not through the floor
                    self.assertLessEqual(self.body.low(w, [b]), 12, b)   # lying along it, not hovering
                tip = w[self.arm_bones(side)[2], :3, 3]
                self.assertGreater(float(tip[2] - w[0, 2, 3]), 100)            # behind the root (forward is -z)

    def test_arms_move_gently_and_loop(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            ring = frames[:-1] + frames[:1]
            for a, b in zip(ring, ring[1:]):
                for bone in range(3, 11):
                    for k in range(3, 6):
                        self.assertLessEqual(abs(a[bone][k] - b[bone][k]), 300, (slot, bone))
            self.assertLess(max(abs(v) for p in frames for bone in range(3, 11) for v in p[bone][3:6]), 5000)

    def test_hanging_and_walking_arms_stay_out_of_the_floor(self):
        for slot in (0, 2, 4):
            for p in self.frames(slot):
                w = self.body.world(p)
                for b in (4, 5, 8, 9):
                    self.assertGreaterEqual(self.body.low(w, [b]), -3, (slot, b))

    def test_palms_face_inwards_and_down_or_the_floor(self):
        for slot in (0, 2, 3, 4):
            for p in self.frames(slot)[:-1]:
                w = self.body.world(p)
                for side, b in ((1, 6), (-1, 10)):
                    col = [float(w[b, i, 2]) for i in range(3)]
                    k = math.sqrt(sum(x*x for x in col))
                    px, py = side*col[0]/k, col[1]/k            # y is down
                    if slot == 3:
                        self.assertGreater(py, .9, (slot, b))   # palm on the floor
                    else:
                        self.assertLess(px, -.5, (slot, b))     # towards the body
                        self.assertGreater(py, .2, (slot, b))

    def test_tired_walk_droops_and_sits_low(self):
        idle, tired = self.frames(0)[:-1], self.frames(3)[:-1]
        pitch = lambda p: p[1][3]*360/4096
        self.assertGreaterEqual(min(pitch(p) for p in tired) - max(pitch(p) for p in idle), 12)
        self.assertLessEqual(max(-p[1][7] for p in tired), min(-p[1][7] for p in idle) - 8)

    def test_gaits_differ(self):
        def mesh(slot):
            out = []
            for p in self.frames(slot)[:-1]:
                w = self.body.world(p)
                out.append([v @ w[b, :3, :3].T + w[b, :3, 3] for b, v in sorted(self.body.verts.items())])
            return out

        def distance(a, b):
            total = count = 0
            for i, pose in enumerate(a):
                other = b[i*len(b)//len(a)]
                for x, y in zip(pose, other):
                    d = x - y
                    total += float((d*d).sum())
                    count += len(x)
            return math.sqrt(total/count)
        meshes = {slot: mesh(slot) for slot in (0, 2, 3, 4)}
        for a, b in ((0, 2), (0, 3), (0, 4), (2, 3), (3, 4)):
            self.assertGreater(distance(meshes[a], meshes[b]), 50 if (a, b) in ((0, 2), (0, 4)) else 100, (a, b))
        periods = {len(meshes[s]) for s in meshes}
        self.assertEqual(len(periods), 3)


EXPECTED = '4409f3a1642988749c7699c93a7928da9ceb65e358fa544ab9234682605118b8'

if __name__ == '__main__':
    unittest.main()
