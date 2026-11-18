"""Sound matching and source-to-engine timing without source discs."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from tools import dcbsound, dcbefe, dw2efe
from tools.derive.steps import effects


class Mapping(unittest.TestCase):
    def test_matching_prefers_same_spectrum_and_duration(self):
        def tone(hz, secs):
            t = np.arange(int(dcbsound.RATE * secs)) / dcbsound.RATE
            return dcbsound.features(np.sin(t * hz * 2 * np.pi) * np.exp(-t * 3))
        source = tone(440, .4)
        candidates = {1: tone(3000, .4), 2: tone(440, .4), 3: tone(440, 1.6)}
        self.assertEqual(min(candidates, key=lambda i: dcbsound.distance(source, candidates[i])), 2)
        self.assertIsNone(dcbsound.features(np.zeros(100)))

    def test_cues_use_first_spawn_and_loudest_hit(self):
        cast = SimpleNamespace(instances=[SimpleNamespace(kind=15, start=10, end=50)], length=50,
                               events=[(4, 3, (66,)), (13, 3, (70,)), (20, 3, (145,)), (0, 2, (1,))])
        hit = SimpleNamespace(events=[(1, 3, (66,)), (20, 3, (70,))])
        self.assertEqual(dcbsound.cues(cast, hit, {66: 14, 70: 28}, {66: .2, 70: .8}),
                         {'sounds': [[0, 14], [6, 28]], 'hit_sound': 28})
        cast.events = []
        self.assertEqual(dcbsound.cues(cast, None, {}, {}), {'sounds': []})

    def test_derive_passes_engine_ticks_and_hit_sound(self):
        entry = {'dcb': {'attack': 1, 'hit': 2, 'fit': [4, 1, 24]},
                 'sounds': [[0, 14], [11, 28]], 'hit_sound': 47}
        with patch.object(dcbefe, 'build', return_value=(b'chunk', {})) as build:
            self.assertEqual(effects.dcb_effect('disc', '252', entry, b'table'), (b'chunk', {}))
        build.assert_called_once_with('disc', entry['dcb'], b'table', 0x1fc,
                                      sounds=[(0, 14), (11 * dw2efe.ENGINE_HZ // 60, 28)], hit_sound=47)

    def test_sound_timeline_compresses_with_cast_poses(self):
        attack = object.__new__(dcbefe.Attack)
        attack.cast_tr = SimpleNamespace(instances=[SimpleNamespace(kind=15, start=10, end=130)], length=130)
        attack.notes = {}
        with patch.object(attack, 'effects', return_value=([(1, 'cast')], [])), \
                patch.object(dcbefe, 'convert_skill', return_value=(b'chunk', {})) as convert:
            attack.convert(b'table', ladder=((4, 1, 24),),
                           sounds=[(20, 28), (20, 28), (21, 14), (21, 47)], hit_sound=47)
        self.assertEqual(convert.call_args.kwargs['sounds'], [(10, 28), (10, 14)])
        self.assertEqual(convert.call_args.kwargs['hit_sound'], 47)


if __name__ == '__main__':
    unittest.main()
