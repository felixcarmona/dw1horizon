"""Quetzalmon's idle, walk, condition walk and run are four different, seamless flights that keep the field speed.

Needs its model before the overlay (tools/models/edit.py get 249 writes it to build/imported-model-edit/edit)."""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import quetzalmon_flight as flight

SOURCE = Path(os.environ.get('QUETZALMON_MODEL', 'build/imported-model-edit/edit/249-Quetzalmon.MMD'))
NB = flight.NB
IDENTITY = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]


def turn(a, b):
    gap = abs(a - b) % 4096
    return min(gap, 4096 - gap) * 360 / 4096


class QuetzalmonFlight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the imported Quetzalmon model and the player DW1 extraction')
        record = json.loads(next(Path('content/species').glob('249-*.json')).read_text())
        cls.skeleton = record['model']['skeleton']
        cls.before = SOURCE.read_bytes()
        cls.after, cls.proof = flight.build(cls.before, cls.skeleton)

    def parse(self, data):
        mmd.exe().add_type(249, self.skeleton)
        model = mmd.MMD.parse(data, NB)
        model.type = 249
        return model

    def clips(self, data):
        model = self.parse(data)
        return {s: animsheet.slot_frames(model, NB, s) for s in range(0, 40)
                if model.anims.table[s] is not None}, model

    def heights(self, slot):
        """Per tick, the lowest and the highest point of the mesh (y points down: the floor is 0)."""
        frames, model = self.clips(self.after)[0][slot][0], self.parse(self.after)
        low, high = [], []
        for pose in frames:
            ys = [v[1] for tri in animsheet.world_tris(model, [IDENTITY] + pose[1:], self.skeleton) for v in tri[0]]
            low.append(max(ys))
            high.append(min(ys))
        return low, high

    def test_the_frozen_import_is_the_input_and_only_the_field_slots_change(self):
        before, old = self.clips(self.before)
        after, new = self.clips(self.after)
        self.assertEqual(new.tmd.build(), old.tmd.build())
        for slot in before:
            if slot not in flight.SLOTS:
                self.assertEqual(after[slot][0], before[slot][0], slot)
        for slot in (2, 3, 4):
            loops = 2 if slot == 2 else 1                           # the walk plays its earlier loop twice
            self.assertEqual(len(after[slot][0]) - 1, (len(before[slot][0]) - 1) * loops)
            self.assertEqual(after[slot][0][-1][0][8], before[slot][0][-1][0][8] * loops)
            period = len(before[slot][0]) - 1                       # the footstep sounds, once per earlier loop
            self.assertEqual([e[0] for e in after[slot][2]], [e[0] + k * period for k in range(loops) for e in before[slot][2]])
        self.assertEqual(after[1][0], after[0][0])
        for pose in before[2][0]:                                   # what was wrong: not one bone moved
            self.assertEqual(pose[1:], before[2][0][0][1:])
        with self.assertRaises(ValueError):
            flight.build(self.before + b'x', self.skeleton)

    def test_the_root_travels_the_same_distance_every_tick(self):
        after, _ = self.clips(self.after)
        speed = {2: 15.9, 3: 13.6, 4: 38.1}
        for slot, expected in speed.items():
            frames = after[slot][0]
            steps = [frames[i + 1][0][8] - frames[i][0][8] for i in range(len(frames) - 1)]
            self.assertLessEqual(max(steps) - min(steps), 1, slot)
            self.assertTrue(all(s < 0 for s in steps), slot)
            self.assertAlmostEqual(-sum(steps) / len(steps), expected, delta=.1)
        self.assertEqual({f[0][8] for f in after[0][0]}, {0})

    def test_wings_stay_low_and_open(self):
        for name, c in flight.CLIPS.items():
            self.assertGreaterEqual(c['top'], 40, name)            # the upstroke stops a little above the horizontal
            self.assertGreaterEqual(c['bot'], 80, name)            # and the wings stay spread out

    def test_loops_are_seamless_with_whole_beats(self):
        after, _ = self.clips(self.after)
        for slot in flight.SLOTS:
            frames, loop, _ = after[slot]
            self.assertEqual(loop, 0)
            for bone in range(1, NB):
                for channel in range(3, 9):
                    self.assertLessEqual(turn(frames[-1][bone][channel], frames[0][bone][channel]), 1, (slot, bone))
        # the wings: whole beats per loop (the right wing's angle crosses its mean 2 x beats times) and no jumps
        for slot, beats in ((0, 2), (2, 3), (3, 1), (4, 2)):
            wing = [f[flight.WING_R][5] for f in after[slot][0]]
            mean = sum(wing[:-1]) / (len(wing) - 1)
            crossings = sum(1 for a, b in zip(wing[:-1], wing[1:-1] + [wing[0]]) if (a - mean) * (b - mean) < 0)
            self.assertEqual(crossings, 2 * beats, (slot, crossings))
        for slot, fastest in ((0, 10), (2, 16), (3, 10), (4, 16)):   # degrees a tick, the wings' peak
            frames = after[slot][0]
            self.assertLessEqual(max(turn(a[9][5], b[9][5]) for a, b in zip(frames, frames[1:])), fastest, slot)
        for slot in (0, 2, 3, 4):
            frames = after[slot][0]
            for bone in range(1, NB):          # the step over the seam is no bigger than the biggest step inside
                steps = [max(turn(frames[i + 1][bone][c], frames[i][bone][c]) for c in (3, 4, 5)) for i in range(len(frames) - 1)]
                seam = max(turn(frames[1][bone][c], frames[0][bone][c]) for c in (3, 4, 5))
                self.assertLessEqual(seam, max(steps) + .5, (slot, bone))

    def test_every_part_moves_and_the_wings_follow_through(self):
        after, _ = self.clips(self.after)
        for slot in (0, 2, 3, 4):
            frames = after[slot][0]
            for bone in range(1, NB):
                spread = max(max(turn(f[bone][c], frames[0][bone][c]) for f in frames) for c in (3, 4, 5))
                self.assertGreater(spread, 1.5, (slot, bone))
            for bone, least in ((flight.WING_R, 25), (flight.WING_L, 20)):
                angle = [f[bone][5] for f in frames]
                self.assertGreater(max(angle) - min(angle), least / 360 * 4096, (slot, bone))
            # the left wing lags and falls short of the right one: the two are not mirror images
            right = [turn(f[flight.WING_R][5], frames[0][flight.WING_R][5]) for f in frames]
            left = [turn(f[flight.WING_L][5], frames[0][flight.WING_L][5]) for f in frames]
            self.assertNotEqual(right, left, slot)

    def test_the_four_clips_read_as_four_states(self):
        after, _ = self.clips(self.after)
        mean = {}
        for slot in (0, 2, 3, 4):
            frames = after[slot][0][:-1]
            mean[slot] = [[sum(f[b][c] for f in frames) / len(frames) for c in (3, 4, 5)] for b in range(1, NB)]
        for a in (0, 2, 3, 4):
            for b in (0, 2, 3, 4):
                if a < b:
                    gaps = [sum(turn(x, y) for x, y in zip(m, n)) for m, n in zip(mean[a], mean[b])]
                    self.assertGreater(max(gaps), 8, (a, b))
                    self.assertGreater(sum(gaps), 50, (a, b))
        periods = {s: len(after[s][0]) - 1 for s in (0, 2, 3, 4)}
        self.assertEqual(sorted(periods.values()), [20, 28, 48, 54])
        # beat rate: the run beats quicker than the walk (a lean flight of three slow beats in 48 ticks), the walk quicker than the tired walk and the idle
        rate = {s: len(flight.CLIPS[flight.CLIP_OF_SLOT[s]]['beats']) / periods[s] for s in periods}
        self.assertGreater(rate[4], rate[2])
        self.assertLess(rate[4], .105)                         # never the frantic six ticks a beat
        self.assertGreater(rate[2], rate[3])
        self.assertGreater(rate[2], rate[0])
        # the run leans furthest forward, the idle not at all
        lean = {s: mean[s][0][0] for s in mean}
        self.assertGreater(len({round(v / 40) for v in lean.values()}), 2, lean)

    def test_it_stays_a_flyer_above_the_floor(self):
        for slot in (0, 2, 3, 4):
            low, high = self.heights(slot)
            clear = flight.CLIPS[flight.CLIP_OF_SLOT[slot]]['clear']
            self.assertLessEqual(max(low), -clear + 2, slot)        # never in the floor
            self.assertGreaterEqual(max(low), -clear - 2, slot)
            self.assertGreaterEqual(min(low), -85, slot)             # nor far above it: the lowest point stays within 85
            self.assertLessEqual(max(low) - min(low), 40, slot)      # and bobs little (the import's rest sat 15 up)
            self.assertGreaterEqual(min(high), -900, slot)           # the wings reach up to 640 to 700 (rest: 567)

    def test_the_wings_never_enter_the_body(self):
        model = self.parse(self.after)
        after, _ = self.clips(self.after)
        for slot in (0, 2, 3, 4):
            closest = 1e9
            for pose in after[slot][0]:
                pose = [IDENTITY] + pose[1:]
                mats = mmd.bone_matrices(model, pose)
                at = [(m[0][3], m[1][3], m[2][3]) for m in mats]
                wing = []
                for bone in (flight.WING_R, flight.WING_L):
                    m = mats[bone]
                    for x, y, z, _ in model.tmd.obj_verts(self.skeleton[bone][0]):
                        wing.append(tuple(sum(m[i][k] * v for k, v in enumerate((x, y, z))) + m[i][3] for i in range(3)))
                for bone in (2, 3, 4, 5, 11, 12, 13, 14, 15):
                    a, b = at[bone], at[self.skeleton[bone][1]]
                    ab = [q - p for p, q in zip(a, b)]
                    size = sum(v * v for v in ab) or 1
                    for w in wing:
                        t = min(1, max(0, sum((w[i] - a[i]) * ab[i] for i in range(3)) / size))
                        closest = min(closest, sum((w[i] - a[i] - t * ab[i]) ** 2 for i in range(3)) ** .5)
            self.assertGreater(closest, 45, (slot, closest))      # the links are about 35 units from the middle line

    def test_storage(self):
        self.assertLessEqual(self.proof['field_flight']['storage']['resident_bytes'], 100352)
        self.assertTrue(self.proof['field_flight']['storage']['fits'])


if __name__ == '__main__':
    unittest.main()
