"""Veedramon's (203) jaw hinges about its own X axis only in the walk, tired walk and run.

The source tired and run clips swung the jaw sideways (yaw up to 24 degrees, roll up to 15) and pushed it up through the upper
jaw (pitch to -22) because the head stood still while the jaw did the acting. The profile now drives the jaw (bone 4, child of
the head, bone 3) with a lagging damped spring on the stride and nothing else.

Needs the imported model (`tools/models/edit.py get 203` writes build/imported-model-edit/edit; VEEDRAMON_MODEL names another path).
"""
import json
import math
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import gaits

SOURCE = Path(os.environ.get('VEEDRAMON_MODEL', 'build/imported-model-edit/edit/203-Veedramon.MMD'))
JAW, HEAD = 4, 3
DEG = 360 / 4096
PITCH = {2: (4.5, 10), 3: (9, 17), 4: (5, 14)}      # opening in degrees: the idle rests at 5.2 and opens to 10
YAW_ROLL_LIMIT = 2.0


class VeedramonJaw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the imported Veedramon model (tools/models/edit.py get 203) and the DW1 extraction')
        cls.skeleton = json.loads(next(Path('content/species').glob('203-*.json')).read_text())['model']['skeleton']
        cls.after, _ = gaits.build(SOURCE.read_bytes(), cls.skeleton)
        mmd.exe().add_type(203, cls.skeleton)
        cls.model = mmd.MMD.parse(cls.after, len(cls.skeleton))
        cls.model.type = 203
        cls.clips = {s: animsheet.slot_frames(cls.model, len(cls.skeleton), s)[0] for s in (0, 2, 3, 4)}

    def test_profile_drives_the_jaw_itself(self):
        cfg = gaits.PROFILES[203]
        self.assertEqual(cfg['jaw']['bone'], JAW)
        self.assertNotIn('source_aux', cfg)          # the source clips' jaw is the one that slid sideways

    def test_jaw_is_a_pure_hinge(self):
        for slot in (2, 3, 4):
            for tick, pose in enumerate(self.clips[slot]):
                x, y, z = (v * DEG for v in pose[JAW][3:6])
                self.assertLessEqual(abs(y), YAW_ROLL_LIMIT, (slot, tick, 'yaw'))
                self.assertLessEqual(abs(z), YAW_ROLL_LIMIT, (slot, tick, 'roll'))

    def test_jaw_opens_a_natural_amount(self):
        for slot, (low, high) in PITCH.items():
            pitches = [pose[JAW][3] * DEG for pose in self.clips[slot]]
            self.assertGreaterEqual(min(pitches), low, slot)
            self.assertLessEqual(max(pitches), high, slot)
            self.assertGreater(max(pitches) - min(pitches), 1.5, (slot, 'the jaw moves'))
            self.assertLess(max(pitches) - min(pitches), 6, (slot, 'a small amount'))

    def test_jaw_moves_smoothly_and_the_loop_closes(self):
        for slot in (2, 3, 4):
            pitches = [pose[JAW][3] * DEG for pose in self.clips[slot]]
            self.assertLess(abs(pitches[0] - pitches[-1]), .3, slot)
            self.assertLess(max(abs(b - a) for a, b in zip(pitches, pitches[1:])), 2.5, slot)

    def test_nothing_else_changes_with_the_jaw(self):
        # the same profile on the same source with the jaw taken out of the config differs only in the jaw's rotation
        cfg = dict(gaits.PROFILES[203])
        cfg.pop('jaw')
        other, _ = gaits.build_profile(SOURCE.read_bytes(), self.skeleton, 203, cfg)
        parsed = mmd.MMD.parse(other, len(self.skeleton))
        parsed.type = 203
        for slot in (2, 3, 4):
            reference = animsheet.slot_frames(parsed, len(self.skeleton), slot)[0]
            for tick, (a, b) in enumerate(zip(reference, self.clips[slot])):
                for bone in range(len(a)):
                    if bone != JAW:
                        self.assertEqual(a[bone], b[bone], (slot, tick, bone))

    def test_follow_through_is_authored_and_the_bars_hold(self):
        cfg = gaits.PROFILES[203]
        self.assertTrue(cfg['waves'] and cfg['head_bob'] and cfg['vary'])
        import motionstorage
        self.assertTrue(motionstorage.audit(self.after, len(self.skeleton))['fits'])

    def test_jaw_series_is_periodic_and_steady(self):
        cfg = gaits.PROFILES[203]
        series = gaits.jaw_series(cfg, 3, 18, 54)
        self.assertEqual(len(series), 55)
        self.assertLess(abs(series[0] - series[-1]), 1e-3)
        self.assertTrue(all(math.isfinite(v) for v in series))


if __name__ == '__main__':
    unittest.main()
