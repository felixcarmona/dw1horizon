"""Puppetmon (181): planted soles under the original's pelvis, and spring-driven chest, head, arms and hammer."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import animstudio
import mmd
import motionstorage
from tools.models.field_animations import puppetmon_field as field

BONES = 18
BUFFER = 100352
TICKS = {0: 104, 2: 28, 3: 36, 4: 20}                    # idle, walk, condition walk, run: two strides (idle: two breaths of weight)
SPEEDS = {2: 22.0, 3: 12.0, 4: 42.0}                     # units per tick
RESIDENT = 98890


class PuppetmonField(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files, tims = list(source.glob('181-*.MMD')), list(source.glob('181-*.TIM'))
        if not files or not tims:
            raise unittest.SkipTest('needs the imported 181 model (edit.py get 181)')
        cls.record = json.loads(next(Path('content/species').glob('181-*.json')).read_text())
        cls.rig = cls.record['model']['skeleton']
        cls.source = files[0].read_bytes()
        cls.data, cls.proof = field.build(cls.source, cls.rig)
        cls.tmp = tempfile.mkdtemp(prefix='puppetmon-')
        Path(cls.tmp, 'm.MMD').write_bytes(cls.data)
        Path(cls.tmp, 'm.TIM').write_bytes(tims[0].read_bytes())
        cls.model = mmd.MMD.parse(cls.data, BONES)
        cls.model.type = 181
        cls.old = mmd.MMD.parse(cls.source, BONES)
        cls.old.type = 181

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.model, BONES, slot)[0]

    @staticmethod
    def speed(frames):
        return abs(frames[-1][0][8] - frames[0][0][8])/(len(frames) - 1)

    def test_only_the_four_field_programs_change_and_the_mesh_is_exact(self):
        self.assertEqual(self.proof['mesh_exact'], True)
        self.assertEqual(self.proof['source_sha256'], field.SOURCE_SHA256)
        self.assertEqual(sorted(self.proof['changed_slots']), [0, 2, 3, 4])
        table = self.old.anims.table
        for slot in range(len(table)):
            if slot in (0, 2, 3, 4):
                continue
            if table[slot] is None:
                continue
            self.assertEqual(self.model.anims.anims[self.model.anims.table[slot]].build(),
                             self.old.anims.anims[table[slot]].build(), slot)

    def test_a_changed_source_stops(self):
        with self.assertRaises(ValueError):
            field.build(self.source + b'\0', self.rig)

    def test_field_ticks(self):
        self.assertEqual({s: len(self.frames(s)) - 1 for s in TICKS}, TICKS)

    def test_gait_speeds_are_the_rows_and_ordered(self):
        speeds = {s: self.speed(self.frames(s)) for s in SPEEDS}
        for slot, want in SPEEDS.items():
            self.assertAlmostEqual(speeds[slot], want, delta=.8, msg=slot)
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])
        self.assertTrue(15 <= 22 <= 31 and 35 <= 42 <= 52)

    def test_soles_are_planted_and_never_visibly_below_the_floor(self):
        for slot in TICKS:
            _, results = animstudio.metrics(animstudio.Model(f'{self.tmp}/m.MMD:181:{self.tmp}/m.TIM', slot))
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 12, (slot, bone))       # the original slid 35, 50 and 18 % in the walk, tired walk and run
                self.assertLess(worst, 35, (slot, bone))      # and at worst 90, 209 and 47 %
        for check in self.proof['checks']:
            self.assertLessEqual(check['lowest_point'], 9, check['slot'])

    def test_loops_close(self):
        for slot in TICKS:
            frames = self.frames(slot)
            for bone in range(BONES):
                np.testing.assert_allclose(mmd.rot_matrix(*frames[0][bone][3:6]), mmd.rot_matrix(*frames[-1][bone][3:6]),
                                           atol=.02, err_msg=f'{slot} {bone}')

    def test_no_tick_jumps(self):
        for slot in TICKS:
            frames = self.frames(slot)
            steps = [max(abs(a - b) for pa, pb in zip(f, g) for a, b in zip(pa[3:6], pb[3:6])) for f, g in zip(frames, frames[1:])]
            self.assertLess(max(steps), 2.5*max(np.median(steps), 1), slot)

    def test_the_strides_differ_and_the_upper_body_is_never_still(self):
        for slot in (2, 3, 4):
            frames = self.frames(slot)
            half = (len(frames) - 1)//2
            for bone in (3, 5, 6, 9, 10):    # head, the shoulders and elbows: the second stride is not the first
                diff = max(abs(a - b) for f, g in zip(frames[:half], frames[half:2*half]) for a, b in zip(f[bone][3:6], g[bone][3:6]))
                self.assertGreater(diff, 3, (slot, bone))
        idle = self.frames(0)
        for bone in (2, 3):
            self.assertGreater(max(f[bone][3] for f in idle) - min(f[bone][3] for f in idle), 20, bone)

    def test_the_buffer_holds(self):
        info = motionstorage.require(self.data, BONES)
        self.assertTrue(info['fits'])
        self.assertLess(info['resident_bytes'], BUFFER)
        self.assertEqual(info['resident_bytes'], RESIDENT)
        for read in info['cold_reads']:
            self.assertTrue(read['fits'], read)


if __name__ == '__main__':
    unittest.main()
