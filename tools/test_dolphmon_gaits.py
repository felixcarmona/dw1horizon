"""Dolphmon's idle, walk, condition walk and run are four different, seamless dolphin movements.

Needs its current model (tools/models/edit.py get 238 writes it to build/imported-model-edit/edit)."""
import json
import math
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy
import animsheet
import mmd
from tools.models.field_animations import dolphmon_gaits as gaits

SOURCE = Path(os.environ.get('DOLPHMON_MODEL', 'build/imported-model-edit/edit/238-Dolphmon.MMD'))
NB = gaits.NB
NAMES = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}


class DolphmonGaits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the imported Dolphmon model and the player DW1 extraction')
        record = json.loads(next(Path('content/species').glob('238-*.json')).read_text())
        cls.skeleton = record['model']['skeleton']
        cls.before = SOURCE.read_bytes()
        cls.after, cls.proof = gaits.build(cls.before, cls.skeleton)
        cls.model = cls.parse(cls.after)
        cls.clips = {s: animsheet.slot_frames(cls.model, NB, s) for s in gaits.SLOTS}

    @classmethod
    def parse(cls, data):
        mmd.exe().add_type(238, cls.skeleton)
        model = mmd.MMD.parse(data, NB)
        model.type = 238
        return model

    def test_ticks_and_speed(self):
        expected = {0: (72, 0), 2: (20, 22), 3: (30, 14), 4: (14, 40)}
        for slot, (ticks, speed) in expected.items():
            frames, loop, _ = self.clips[slot]
            self.assertEqual(loop, 0)
            self.assertEqual(len(frames) - 1, ticks)
            self.assertEqual(frames[0][0][8] - frames[-1][0][8], ticks * speed)

    def test_loops_are_seamless_and_smooth(self):
        for slot, (frames, _, _) in self.clips.items():
            for bone in range(1, NB):
                self.assertEqual(frames[0][bone][3:6], frames[-1][bone][3:6], (slot, bone))
                for a, b in zip(frames, frames[1:]):
                    for c in range(3, 6):
                        step = abs(a[bone][c] - b[bone][c])
                        step = min(step, 4096 - step)   # a degree is about 11.4 units
                        self.assertLess(step, 4096 * 38 / 360, (slot, bone, c))

    def test_the_four_clips_differ(self):
        # the old clips were one stream: every pair was identical
        angles = {s: numpy.array([[f[b][3:6] for b in range(1, NB)] for f in fs[:-1]], float) / 4096 * 360
                  for s, (fs, _, _) in self.clips.items()}

        def resample(a, n=48):
            return numpy.array([a[int(k * len(a) / n)] for k in range(n)])
        slots = sorted(angles)
        for i, a in enumerate(slots):
            for b in slots[i + 1:]:
                A, B = resample(angles[a]), resample(angles[b])
                diff = min(float(numpy.abs(A - numpy.roll(B, k, 0)).mean()) for k in range(48))
                self.assertGreater(diff, 1.2, (NAMES[a], NAMES[b]))
        periods = {len(self.clips[s][0]) for s in self.clips}
        self.assertEqual(len(periods), 4)

    def test_nothing_moves_vertically(self):
        """No clip rises or sinks: the body bone keeps one height, the whole mesh stays on the floor, the centroid
        stays put and the nose and the fluke tip stay near their rest height."""
        model = self.model
        verts = {b: numpy.array(model.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(self.skeleton) if oi >= 0}
        nose, tail = {}, {}
        for slot, (frames, _, _) in self.clips.items():
            low, centre, nose[slot], tail[slot] = [], [], [], []
            self.assertEqual({f[1][7] for f in frames}, {frames[0][1][7]}, NAMES[slot])
            for f in frames[:-1]:
                g = [list(v) for v in f]
                g[0] = [4096] * 3 + [0] * 6
                w = numpy.array(mmd.bone_matrices(model, g))
                placed = {b: v @ w[b, :3, :3].T + w[b, :3, 3] for b, v in verts.items()}
                everything = numpy.vstack(list(placed.values()))
                low.append(-float(everything[:, 1].max()))
                centre.append(-float(everything[:, 1].mean()))
                nose[slot].append(-float(placed[2][placed[2][:, 2].argmin()][1]))
                tail[slot].append(-float(placed[10][placed[10][:, 2].argmax()][1]))
            self.assertGreaterEqual(min(low), -1., NAMES[slot])
            self.assertLessEqual(max(low), 1., NAMES[slot])
            self.assertLessEqual(max(centre) - min(centre), 1., NAMES[slot])
        rest = float(numpy.median(nose[2]))
        for slot in self.clips:
            for tip in (nose[slot], tail[slot]):
                self.assertLessEqual(max(abs(x - rest) for x in tip), 6., NAMES[slot])

    def test_the_head_keeps_facing_forward(self):
        """Turned too far, the head hides the far eye behind its own cheek: its yaw in the world stays small."""
        for slot, (frames, _, _) in self.clips.items():
            for f in frames[:-1]:
                g = [list(v) for v in f]
                g[0] = [4096] * 3 + [0] * 6
                forward = numpy.array(mmd.bone_matrices(self.model, g))[2, :3, :3] @ numpy.array([0., 0., -1.])
                self.assertLess(abs(math.degrees(math.atan2(forward[0], -forward[2]))), 10., NAMES[slot])

    def test_only_the_four_field_slots_change(self):
        old = self.parse(self.before)
        new = self.model
        self.assertEqual(new.tmd.build(), old.tmd.build())
        self.assertEqual(sorted(self.proof['field_gaits']['storage']['resident_bytes'] for _ in [0]),
                         [self.proof['field_gaits']['storage']['resident_bytes']])
        self.assertLessEqual(self.proof['field_gaits']['storage']['resident_bytes'], 100352)

    def test_footsteps_keep_their_sounds(self):
        _, _, events = self.clips[2]
        self.assertEqual([e[1] for e in events], ['sound'])


if __name__ == '__main__':
    unittest.main()
