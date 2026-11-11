"""Kokuwamon's carried arm (field_animations/kokuwamon_arm.py): the arm chain 13/14 that the source clips left stiff swings in
the idle, walk, condition walk and run, alternating with the other arm, and nothing else changes (boots, body, other arm,
claws, travel, other programs). Needs the delta model and the DW1 extraction:

    python3 tools/models/edit.py get 247      (writes build/imported-model-edit/edit/247-Kokuwamon.MMD)"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'models'))
import numpy as np
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import kokuwamon, kokuwamon_arm as gen, pace

SOURCE = Path(os.environ.get('KOKUWAMON_MODEL', 'build/imported-model-edit/edit/247-Kokuwamon.MMD'))
SKELETON = [(i - 1, p) for i, p in enumerate(kokuwamon.PARENTS)]
NB = len(SKELETON)
SPEEDS = {2: 20, 3: 13.3, 4: 38}
MOVED = {gen.COVER, gen.SHOULDER, gen.FOREARM}


def _clips(data):
    mmd.exe().skeleton[247] = SKELETON
    mmd.exe().bone_count[247] = NB
    model = mmd.MMD.parse(data, NB)
    model.type = 247
    return model, {s: animsheet.slot_frames(model, NB, s)[0] for s in range(5)}


def _degrees(a, b):
    ra, rb = np.array(mmd.rot_matrix(*a[3:6])), np.array(mmd.rot_matrix(*b[3:6]))
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(ra.T @ rb) - 1) / 2))))


class KokuwamonArm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the Kokuwamon delta model and the player DW1 extraction')
        data = SOURCE.read_bytes()
        mmd.exe().skeleton[247] = SKELETON
        mmd.exe().bone_count[247] = NB
        cls.final_bytes, cls.report = pace.build(data, SKELETON)
        profiles = json.loads(pace.MANIFEST.read_text())
        profiles['247'].pop('after_generator')
        with tempfile.TemporaryDirectory() as tmp:
            plain = Path(tmp) / 'pace.json'
            plain.write_text(json.dumps(profiles))
            keep, pace.MANIFEST = pace.MANIFEST, plain
            try:
                before_bytes, _ = pace.build(data, SKELETON)
            finally:
                pace.MANIFEST = keep
        cls.model, cls.new = _clips(cls.final_bytes)
        cls.old_model, cls.old = _clips(before_bytes)

    def test_the_manifest_runs_the_arm_layer(self):
        self.assertEqual(json.loads(pace.MANIFEST.read_text())['247']['after_generator'], gen.__name__)

    def test_the_arm_swings_in_every_field_clip(self):
        # the stiff arm: the shoulder 13 never moved and the forearm 14 about three degrees in the walks
        floor = {0: 3, 2: 8, 3: 8, 4: 8}
        for slot, frames in self.new.items():
            if slot not in floor:
                continue
            for bone, least in ((gen.FOREARM, floor[slot]), (gen.SHOULDER, floor[slot] / 2)):
                spread = max(_degrees(frames[a][bone], frames[b][bone]) for a in range(len(frames)) for b in range(a))
                self.assertGreater(spread, least, (slot, bone))
                moving = {tuple(f[bone][3:6]) for f in frames}
                self.assertGreater(len(moving), 5, (slot, bone))

    def test_it_alternates_with_the_other_arm(self):
        for slot in (2, 3, 4):
            frames = self.new[slot]
            ticks = len(frames) - 1
            mine = [frames[t][gen.FOREARM][3] for t in range(ticks)]
            other = [frames[t][gen.OTHER_FOREARM][3] for t in range(ticks)]
            mine = [v - sum(mine) / ticks for v in mine]
            other = [v - sum(other) / ticks for v in other]
            self.assertLess(sum(a * b for a, b in zip(mine, other)), 0, slot)   # not forward together

    def test_only_the_arm_cover_shoulder_and_forearm_change(self):
        for slot in range(5):
            a, b = self.old[slot], self.new[slot]
            self.assertEqual(len(a), len(b))
            for t in range(len(a)):
                for bone in range(NB):
                    if bone in MOVED and slot in gen.SLOTS:
                        continue
                    self.assertEqual(a[t][bone], b[t][bone], (slot, t, bone))
            if slot not in gen.SLOTS:
                self.assertEqual(self.old_model.anims.table[slot] is None, self.model.anims.table[slot] is None)
        for slot in gen.SLOTS:
            for t in range(len(self.old[slot])):
                for bone in MOVED:
                    self.assertEqual(self.old[slot][t][bone][6:9], self.new[slot][t][bone][6:9], (slot, t, bone))
        self.assertEqual(self.old_model.tmd.build(), self.model.tmd.build())

    def test_loops_close_and_travel_is_unchanged(self):
        for slot, speed in SPEEDS.items():
            frames = self.new[slot]
            ticks = len(frames) - 1
            self.assertAlmostEqual((frames[0][0][8] - frames[-1][0][8]) / ticks, speed, delta=0.1, msg=slot)
            self.assertEqual([f[0] for f in frames], [f[0] for f in self.old[slot]])
        for slot in gen.SLOTS:
            frames = self.new[slot]
            for bone in MOVED:
                for c in range(3, 9):
                    gap = abs(frames[-1][bone][c] - frames[0][bone][c]) % 4096
                    self.assertLessEqual(min(gap, 4096 - gap), 1, (slot, bone, c))

    def test_no_jump_between_two_ticks(self):
        for slot in gen.SLOTS:
            frames = self.new[slot]
            for t in range(len(frames) - 1):
                for bone in MOVED:
                    self.assertLess(_degrees(frames[t][bone], frames[t + 1][bone]), 12, (slot, t, bone))

    def test_inside_the_resident_buffer(self):
        report = motionstorage.require(self.final_bytes, NB)
        self.assertLess(report['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
