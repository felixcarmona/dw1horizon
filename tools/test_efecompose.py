#!/usr/bin/env python3
"""Composed effects (tools/efecompose.py) and their check (tools/efecheck.py check_composed).

The colour tests run anywhere; the ones on real templates need the player's disc extraction
(extracted/ETCHI/EFEDAT.EFE) and are skipped without it."""
import os
import struct
import unittest

from tools import efecheck as C
from tools import efecompose as X

ARCHIVE = X.ARCHIVE


def template(n):
    with open(ARCHIVE, 'rb') as f:
        f.seek(n * X.CHUNK)
        return f.read(X.CHUNK)


class Colours(unittest.TestCase):
    def test_no_visible_colour_becomes_transparent(self):
        for stp in (0, 1):
            v = X.to15((0, 0, 0), stp)
            self.assertNotEqual(v & 0x7FFF, 0)
            self.assertEqual(bool(v & 0x8000), bool(stp))

    def test_ramp_follows_brightness(self):
        f = X.mapper({'ramp': ['#000000', '#00ff00']})
        self.assertEqual(f((255, 0, 0)), (0, 255, 0))
        self.assertEqual(f((0, 0, 0)), (0, 0, 0))
        self.assertEqual(f((128, 128, 128))[1], 128)

    def test_hue_keeps_value(self):
        f = X.mapper({'hue': 120, 'saturation': 0.5})
        r, g, b = f((200, 40, 40))
        self.assertEqual(max(r, g, b), g)
        self.assertEqual(g, 200)

    def test_main_hue(self):
        red, green = [(220, 20, 20)] * 10, [(20, 220, 20)] * 30
        self.assertAlmostEqual(C.hue_of([red]), 0, delta=1)
        self.assertAlmostEqual(C.hue_of([red + green]), 120, delta=20)
        self.assertIsNone(C.hue_of([[(90, 90, 90)] * 5]))
        self.assertEqual(C.hue_distance(350, 10), 20)


@unittest.skipUnless(os.path.exists(ARCHIVE), 'needs the disc extraction')
class Composed(unittest.TestCase):
    SPEC = {'recolour': {'ramp': ['#14001e', '#5a1494', '#c870ff', '#f4dcff']}, 'scale': 1.3}

    def setUp(self):
        self.t = template(62)

    def test_composition_keeps_the_technique(self):
        ours, info = X.compose(self.t, self.SPEC)
        self.assertEqual(len(ours), X.CHUNK)
        self.assertEqual(X.launch_table(ours), X.launch_table(self.t))
        allowed = X.allowed_bytes(self.t, self.SPEC)
        self.assertTrue(all(i in allowed for i in range(X.CHUNK) if ours[i] != self.t[i]))
        clut, rows, cols, *_ = X.tim_layout(self.t)
        for k in range(rows * cols):
            a, b = (struct.unpack_from('<H', c, clut + 2 * k)[0] for c in (self.t, ours))
            self.assertEqual(a == 0, b == 0)            # transparent stays, visible stays visible
            self.assertEqual(a & 0x8000, b & 0x8000)    # semi-transparency kept
        self.assertEqual(info['kept'], X.header(self.t)['tmdEnd'] + X.HEADER)

    def test_check_passes(self):
        ours, _ = X.compose(self.t, self.SPEC)
        rep = C.check_composed(self.t, ours, self.SPEC, 280)
        self.assertEqual(rep['fails'], [])
        self.assertGreater(rep['distinct'], C.MIN_DISTINCT)

    def test_check_fails_the_template_itself_and_a_wrong_hue(self):
        rep = C.check_composed(self.t, self.t, {}, 280)
        self.assertTrue(any('too close' in x for x in rep['fails']))
        ours, _ = X.compose(self.t, self.SPEC)
        rep = C.check_composed(self.t, ours, self.SPEC, 100)
        self.assertTrue(any('hue' in x for x in rep['fails']))

    def test_check_fails_a_dark_recolour(self):
        spec = {'recolour': {'ramp': ['#000000', '#020002']}}
        ours, _ = X.compose(self.t, spec)
        rep = C.check_composed(self.t, ours, spec)
        self.assertTrue(any('mostly empty' in x for x in rep['fails']))

    def test_check_fails_a_changed_script(self):
        ours, _ = X.compose(self.t, self.SPEC)
        code = sorted(X.code_bytes(self.t))
        bad = bytearray(ours)
        bad[X.HEADER + code[len(code) // 2]] ^= 0x01
        rep = C.check_composed(self.t, bytes(bad), self.SPEC, 280)
        self.assertTrue(any('outside the palette' in x for x in rep['fails']))

    def test_texture_copy(self):
        with open(ARCHIVE, 'rb') as f:
            archive = f.read()
        t = template(72)
        spec = {'texture': [{'from': 105, 'rect': [0, 0, 32, 32], 'palettes': [[0, 0]]}]}
        ours, info = X.compose(t, spec, archive)
        src = template(105)
        for (a, n), (b, _n) in zip(X.texture_rect(src, [0, 0, 32, 32]), X.texture_rect(ours, [0, 0, 32, 32])):
            self.assertEqual(ours[b:b + n], src[a:a + n])
        self.assertEqual(info['texture from'], [105])
        allowed = X.allowed_bytes(t, spec)
        self.assertTrue(all(i in allowed for i in range(X.CHUNK) if ours[i] != t[i]))
        with self.assertRaises(ValueError):
            X.compose(t, spec)                          # needs the archive
        with self.assertRaises(ValueError):
            X.texture_rect(t, [1, 0, 32, 32])           # not on a byte

    def test_check_splits_at_the_hit(self):
        t = template(93)                                # a technique the simulation deals a hit with
        spec = {'recolour': {'ramp': ['#001020', '#1060a0', '#60c0ff', '#e0f4ff']}}
        ours, _ = X.compose(t, spec)
        rep = C.check_composed(t, ours, spec, 200)
        self.assertEqual(sorted(rep['phases']), ['cast', 'hit'])
        self.assertEqual(len(rep['hits']), 1)
        self.assertEqual(rep['fails'], [])

    def test_every_composed_entry_passes(self):
        import json
        with open(X.OWN_EFFECTS) as f:
            spec = json.load(f)
        with open(ARCHIVE, 'rb') as f:
            archive = f.read()
        for key, e in spec.items():
            if key == 'note' or 'compose' not in e:
                continue
            with self.subTest(key):
                t = X.template_of(archive, e)
                ours, info = X.compose(t, e['compose'], archive)
                self.assertLessEqual(len(ours), X.CHUNK)
                rep = C.check_composed(t, ours, e['compose'], e.get('check', {}).get('hue'))
                self.assertEqual(rep['fails'], [])


if __name__ == '__main__':
    unittest.main()
