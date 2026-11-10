"""Diaboromon's idle, walk, condition walk and run: whole loops at the field speeds, no jump between two ticks, planted
feet, four clips that read differently, inside the resident animation buffer.

Needs the final model (tools/models/edit.py get 237 writes it to build/imported-model-edit/edit)."""
import math
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'models'))
import numpy as np

import animsheet
import mmd
import motionstorage
from tools.models.field_animations import diaboromon_gait as gen

MODEL = Path(os.environ.get('DIABOROMON_MODEL', 'build/imported-model-edit/edit/237-Diaboromon.MMD'))
SKELETON = [(i - 1, p) for i, p in enumerate(gen.PARENTS)]
NB = len(gen.PARENTS)


def _degrees(a, b):
    ra, rb = np.array(mmd.rot_matrix(*a[3:6])), np.array(mmd.rot_matrix(*b[3:6]))
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(ra.T @ rb) - 1) / 2))))


class DiaboromonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEL.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the final Diaboromon model and the player DW1 extraction')
        mmd.exe().skeleton[237] = SKELETON
        mmd.exe().bone_count[237] = NB
        cls.model = mmd.MMD.parse(MODEL.read_bytes(), NB)
        cls.model.type = 237
        cls.clips = {s: animsheet.slot_frames(cls.model, NB, s)[0] for s in gen.SLOTS}

    def test_lengths_speeds_and_seamless_loops(self):
        for slot, ticks, speed in ((0, gen.IDLE_TICKS, 0), (2, 48, 20), (3, 60, 13), (4, 36, 38)):
            frames = self.clips[slot]
            self.assertEqual(len(frames) - 1, ticks)
            self.assertEqual({frames[i][0][8] - frames[i + 1][0][8] for i in range(ticks)}, {speed})
            self.assertEqual({tuple(f[0][6:8]) for f in frames}, {(0, 0)})
            for bone in range(1, NB):
                for channel in range(3, 9):
                    gap = abs(frames[-1][bone][channel] - frames[0][bone][channel]) % 4096
                    self.assertLessEqual(min(gap, 4096 - gap), 1, (slot, bone, channel))

    def test_no_bone_jumps_between_two_ticks(self):
        # the old transfer turned a hand 138 degrees in one tick; 60 fps blends each Euler angle on its own
        for slot, frames in self.clips.items():
            for t in range(len(frames) - 1):
                for bone in range(1, NB):
                    self.assertLess(_degrees(frames[t][bone], frames[t + 1][bone]), 25, (slot, t, bone))
                    for channel in (3, 4, 5):
                        step = (frames[t + 1][bone][channel] - frames[t][bone][channel] + 2048) % 4096 - 2048
                        self.assertLessEqual(abs(step), gen.MAX_STEP, (slot, t, bone, channel))

    def test_feet_stay_planted_and_above_the_floor(self):
        verts = {b: np.array(self.model.tmd.obj_verts(o), float)[:, :3] for b, (o, _) in enumerate(SKELETON) if o >= 0}
        for slot in gen.SLOTS:
            frames = self.clips[slot]
            lows = {end: [] for end in (9, 13, 19, 23)}
            for f in frames[:-1]:
                w = np.array(mmd.bone_matrices(self.model, f), float)
                for end in lows:
                    p = verts[end] @ w[end, :3, :3].T + w[end, :3, 3]
                    # the stored angles are rounded: a planted claw wavers by a couple of units, never more
                    self.assertLess(p[:, 1].max(), 2.5, (slot, end))
                    lows[end].append((p[:, 1].max(), w[end, 2, 3]))
            if slot == 0:
                continue
            for end, track in lows.items():
                down = [z for y, z in track if y > -3]
                self.assertGreater(len(down), 0.3 * len(track), (slot, end))
                # on the ground the foot keeps its place while the body moves on
                runs = [b - a for (ya, a), (yb, b) in zip(track, track[1:]) if ya > -1.5 and yb > -1.5]
                self.assertLess(max(abs(d) for d in runs), 3, (slot, end))

    def test_the_four_clips_differ(self):
        verts = {b: np.array(self.model.tmd.obj_verts(o), float)[:, :3] for b, (o, _) in enumerate(SKELETON) if o >= 0}

        def points(f):
            f = [list(b) for b in f]
            f[0] = [4096] * 3 + [0] * 6
            w = np.array(mmd.bone_matrices(self.model, f), float)
            return np.concatenate([verts[b] @ w[b, :3, :3].T + w[b, :3, 3] for b in sorted(verts)])
        shapes = {s: [points(fr[int(i * (len(fr) - 1) / 24)]) for i in range(24)] for s, fr in self.clips.items()}
        for i, a in enumerate(gen.SLOTS):
            for b in gen.SLOTS[i + 1:]:
                rms = np.mean([np.sqrt(((pa - pb) ** 2).sum(1).mean()) for pa, pb in zip(shapes[a], shapes[b])])
                self.assertGreater(rms, 30, (a, b))

    def test_fits_the_resident_buffer(self):
        audit = motionstorage.audit(MODEL.read_bytes(), NB)
        self.assertTrue(audit['fits'], audit)
        self.assertLessEqual(audit['resident_bytes'], audit['resident_limit'])


if __name__ == '__main__':
    unittest.main()
