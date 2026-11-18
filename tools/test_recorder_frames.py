#!/usr/bin/env python3
"""The emulator clip recorder (tools/dev/emulator.py record) shows every refresh of the game's display at the
console's rate: no wall clock, one video frame per refresh, contiguous game frame numbers."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import unittest
from tools.dev import emulator


class Recorder(unittest.TestCase):
    def test_game_rate_is_the_console_refresh(self):
        self.assertEqual(emulator.GAME_HZ, 60)

    def test_script_samples_every_vsync_without_wall_clock(self):
        lua = emulator.RECORD_LUA % dict(stop=60, raw='/x', size=emulator.FRAME_BYTES)
        self.assertIn("'GPU::Vsync'", lua)
        self.assertIn('takeScreenShot', lua)
        self.assertIn('REC.n >= REC.stop', lua)
        for wall in ('os.time', 'os.clock', 'pauseEmulator'):
            self.assertNotIn(wall, lua)

    def test_game_drawing_every_second_refresh(self):
        pics = [b'a', b'a', b'b', b'b', b'c', b'c']
        self.assertEqual(emulator.drawn_frames(pics), [0, 0, 2, 2, 4, 4])

    def test_sixty_fps_game_has_every_refresh_new(self):
        pics = [bytes([i]) for i in range(6)]
        self.assertEqual(emulator.drawn_frames(pics), list(range(6)))

    def test_one_entry_per_refresh_and_picture_may_return(self):
        pics = [b'a', b'b', b'a']
        self.assertEqual(emulator.drawn_frames(pics), [0, 1, 2])


if __name__ == '__main__':
    unittest.main()
