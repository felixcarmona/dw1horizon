"""Decoded-scale audit: momentum accumulation, per-slot initialization and aliases."""
import sys
from pathlib import Path
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import mmd
from tools.models.scale_lock import measure


def clip(scale=4096, momentum=0):
    a = mmd.Anim()
    a.frame_count, a.has_scale = 5, True
    a.pose = [[scale] * 3 + [0] * 6]
    a.instrs = [dict(op='key', frame=1, bones=[dict(bone=1, div=1, vals={'sx': momentum})]), dict(op='end')]
    return a


def model(*clips):
    m = mmd.MMD()
    m.anims = mmd.AnimSection()
    m.anims.anims = list(clips)
    m.anims.table = [0, 0, 0] + list(range(1, len(clips)))
    return m


class ScaleAudit(unittest.TestCase):
    def test_small_momentum_accumulates_above_threshold(self):
        r = measure(model(clip(momentum=40)), [[-1, -1], [0, 0]])
        self.assertTrue(r['animated'])
        self.assertGreater(r['animated'][0]['channels'][0][3] - 4096, 82)

    def test_static_clips_with_different_initial_scales_are_reported(self):
        r = measure(model(clip(), clip(scale=8192)), [[-1, -1], [0, 0]])
        self.assertFalse(r['animated'])
        self.assertEqual(len(r['across_slots']), 3)
        self.assertEqual(r['occupied_slots'], 4)

    def test_quantization_noise_is_below_threshold(self):
        r = measure(model(clip(momentum=1)), [[-1, -1], [0, 0]])
        self.assertFalse(r['across_slots'])
        self.assertTrue(measure(model(clip(momentum=1)), [[-1, -1], [0, 0]], 0)['across_slots'])

    def test_late_scale_keys_are_audited_after_the_preview_limit(self):
        late = clip()
        late.frame_count = 705
        late.instrs.insert(-1, dict(op='key', frame=650,
                                   bones=[dict(bone=1, div=1, vals={'sx': 40})]))
        r = measure(model(clip(), late), [[-1, -1], [0, 0]])
        self.assertEqual([v['slot'] for v in r['animated']], [3])

    def test_large_feet_use_relative_threshold(self):
        r = measure(model(clip(scale=10240, momentum=40)), [[-1, -1], [0, 0]])
        self.assertFalse(r['across_slots'])


if __name__ == '__main__':
    unittest.main()
