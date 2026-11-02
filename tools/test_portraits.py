#!/usr/bin/env python3
"""The hand-drawn icons of content/icons: each one packs into the game's icon format."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import portraits


class DrawnIcons(unittest.TestCase):
    def test_every_icon_packs(self):
        names = sorted(n for n in os.listdir(portraits.DRAWN) if n.endswith('.txt'))
        self.assertTrue(names)
        for name in names:
            with self.subTest(name):
                with open(os.path.join(portraits.DRAWN, name), encoding='ascii') as f:
                    self.assertEqual(len(portraits.drawn_icon(f.read())), portraits.ICON_SIZE)

    def test_idle_frames_differ(self):
        for name in sorted(n for n in os.listdir(portraits.DRAWN) if n.endswith('.txt')):
            with self.subTest(name):
                with open(os.path.join(portraits.DRAWN, name), encoding='ascii') as f:
                    _, frames = portraits.load_drawn(f.read())
                self.assertNotEqual(frames['idle'], frames['idle2'])


if __name__ == '__main__':
    unittest.main()
