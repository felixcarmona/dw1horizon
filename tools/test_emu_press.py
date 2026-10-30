#!/usr/bin/env python3
"""Interrupted harness input must not leave the game holding a button."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import unittest
from unittest.mock import patch
from tools.dev import emulator as emu


class PressTests(unittest.TestCase):
    def test_interruption_releases_button(self):
        with patch.object(emu, 'api', return_value=b'ok CROSS') as api, \
                patch.object(emu.time, 'sleep', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                emu.press('CROSS', 30)
        self.assertEqual([c.args[0] for c in api.call_args_list], [
            '/api/v1/lua/press?button=CROSS', '/api/v1/lua/release?button=CROSS'])

    def test_normal_press_keeps_duration_and_result(self):
        with patch.object(emu, 'api', return_value=b'ok START') as api, \
                patch.object(emu.time, 'sleep') as sleep:
            self.assertEqual(emu.press('START', 30), 'ok START 30')
        sleep.assert_called_once_with(.5)
        self.assertEqual(api.call_args.args, ('/api/v1/lua/release?button=START',))


if __name__ == '__main__':
    unittest.main()
