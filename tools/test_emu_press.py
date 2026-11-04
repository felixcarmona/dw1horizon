#!/usr/bin/env python3
"""Interrupted harness input must not leave the game holding a button."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import unittest
from unittest.mock import patch
from tools.dev import emulator as emu


class FakeEmulator:
    """api() answers: a button press, its release, the CPU cycle counter (it advances `step` cycles per read, or never when
    `step` is 0: a paused emulator) and the still."""
    def __init__(self, step=emu.CYCLES_PER_FRAME // 2):
        self.cycles, self.step, self.calls = 1_000_000, step, []

    def __call__(self, path, *a, **k):
        self.calls.append(path)
        if 'getCPUCycles' in path:
            self.cycles += self.step
            return f'{self.cycles}ULL'.encode()
        return b'ok BUTTON'


class PressTests(unittest.TestCase):
    def test_interruption_releases_button(self):
        fake = FakeEmulator()
        with patch.object(emu, 'api', fake), patch.object(emu.time, 'sleep', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                emu.press('CROSS', 30)
        self.assertEqual(fake.calls[0], '/api/v1/lua/press?button=CROSS')
        self.assertEqual(fake.calls[-1], '/api/v1/lua/release?button=CROSS')

    def test_interruption_while_reading_the_clock_releases_button(self):
        fake = FakeEmulator()
        real = fake.__call__
        def api(path, *a, **k):
            if 'getCPUCycles' in path: raise KeyboardInterrupt
            return real(path)
        with patch.object(emu, 'api', side_effect=api) as mocked:
            with self.assertRaises(KeyboardInterrupt):
                emu.press('CROSS', 30)
        self.assertEqual(mocked.call_args_list[-1].args[0], '/api/v1/lua/release?button=CROSS')

    def test_the_hold_lasts_the_asked_emulated_frames_not_wall_time(self):
        fake = FakeEmulator(step=1000)               # a loaded host: the emulator advances little per wall second
        with patch.object(emu, 'api', fake), patch.object(emu.time, 'sleep'):
            self.assertEqual(emu.press('START', 8), 'ok BUTTON 8')
        reads = [c for c in fake.calls if 'getCPUCycles' in c]
        held = (fake.cycles - 1_000_000) - 1000      # from the first read after the press to the release
        self.assertGreaterEqual(held, 8 * emu.CYCLES_PER_FRAME)
        self.assertEqual(fake.calls[0], '/api/v1/lua/press?button=START')
        self.assertEqual(fake.calls[-1], '/api/v1/lua/release?button=START')
        self.assertGreater(len(reads), 100)          # it waited for the emulator instead of sleeping a fixed time

    def test_a_paused_emulator_does_not_hang_the_press(self):
        fake = FakeEmulator(step=0)
        clock = iter(range(0, 10_000))
        with patch.object(emu, 'api', fake), patch.object(emu.time, 'sleep'), \
                patch.object(emu.time, 'time', side_effect=lambda: next(clock)):
            emu.press('START', 8)
        self.assertEqual(fake.calls[-1], '/api/v1/lua/release?button=START')

    def test_cycle_counter_text_is_parsed(self):
        with patch.object(emu, 'api', return_value=b'4780408154ULL'):
            self.assertEqual(emu.cpu_cycles(), 4780408154)


class ShotTests(unittest.TestCase):
    def png(self, rgb):
        import io
        from PIL import Image
        buffer = io.BytesIO(); Image.new('RGB', (4, 4), rgb).save(buffer, 'PNG')
        return buffer.getvalue()

    def test_a_black_still_is_taken_again(self):
        import tempfile, os
        stills = [b'', self.png((0, 0, 0)), self.png((10, 20, 30))]
        with tempfile.TemporaryDirectory() as d, patch.object(emu, 'api', side_effect=stills), patch.object(emu.time, 'sleep'):
            out = os.path.join(d, 'a.png')
            emu.shot(out)
            self.assertEqual(open(out, 'rb').read(), stills[2])
            self.assertEqual(os.listdir(d), ['a.png'])

    def test_a_screen_that_stays_black_is_saved_with_a_note(self):
        import tempfile, os, io, contextlib
        black = self.png((0, 0, 0))
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as d, patch.object(emu, 'api', return_value=black) as api, \
                patch.object(emu.time, 'sleep'), contextlib.redirect_stderr(err):
            out = os.path.join(d, 'a.png')
            emu.shot(out, tries=3)
            self.assertEqual(open(out, 'rb').read(), black)
        self.assertEqual(api.call_count, 3)
        self.assertIn('black', err.getvalue())


if __name__ == '__main__':
    unittest.main()
