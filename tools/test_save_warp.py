#!/usr/bin/env python3
"""A save-harness warp must survive field updates between debugger memory writes."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import struct
import unittest
from tools.dev.saves.releases import Emu


class Field:
    def __init__(self, fail=False):
        self.paused = False
        self.fail = fail
        self.values = {'CURRENT_SCREEN': 300, 'TARGET_MAP': 301, 'TAMER_STATE': 0}

    def api(self, path):
        self.paused = path.endswith('pause')
        if not self.paused: self.tick()
        return b''

    def tick(self):
        if self.paused: return
        if self.values['TAMER_STATE'] == 5:
            self.values['CURRENT_SCREEN'] = self.values['TARGET_MAP']
            self.values['TAMER_STATE'] = 0
        else:
            self.values['TARGET_MAP'] = 301  # the field's exit-trigger update

    def poke(self, name, data):
        if self.fail: raise RuntimeError('injected write failure')
        self.values[name] = struct.unpack('<h' if name == 'TARGET_MAP' else '<B', data)[0]
        self.tick()

    def wait(self, seconds): self.tick()
    def ram(self): return self.values
    def peek(self, name, fmt, ram=None): return self.values.get(name, 0)


class WarpTests(unittest.TestCase):
    def test_exit_update_cannot_replace_requested_destination(self):
        field = Field()
        self.assertTrue(Emu.warp(field, 218))
        self.assertEqual(field.values['CURRENT_SCREEN'], 218)
        self.assertFalse(field.paused)

    def test_old_separate_writes_lose_the_destination(self):
        field = Field()
        field.poke('TAMER_SUB_STATE', b'\0')
        field.poke('TARGET_MAP', struct.pack('<h', 218))
        field.poke('CURRENT_EXIT', b'\0')
        field.poke('TAMER_STATE', b'\x05')
        self.assertEqual(field.values['CURRENT_SCREEN'], 301)

    def test_write_failure_resumes_the_emulator(self):
        field = Field(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'injected'):
            Emu.warp(field, 218)
        self.assertFalse(field.paused)


if __name__ == '__main__':
    unittest.main()
