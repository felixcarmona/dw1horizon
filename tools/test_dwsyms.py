#!/usr/bin/env python3
"""Proof that dwsyms.detect_build tells apart worktree builds with the same code start.
Builds a fake RAM image from each of several builds under build/decomp-* and checks the
detection returns that build (or an identical twin); also --syms/DW_SYMS. Skips if <2 builds."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import os, sys, unittest, tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools.dev import symbols as dwsyms


def ram_of(name):
    e = open(dwsyms.CANDIDATES[name][0], 'rb').read()
    load = int.from_bytes(e[0x18:0x1C], 'little') & 0x1FFFFFFF
    r = bytearray(0x200000); r[load:load + len(e) - 0x800] = e[0x800:]
    return bytes(r)


def same_start():
    """Pairs of builds whose first 0x60000 bytes of text are equal (the old detection could not tell them apart)."""
    seen, pairs = {}, []
    for n, (p, _) in dwsyms.CANDIDATES.items():
        try: e = open(p, 'rb').read()
        except OSError: continue
        k = (int.from_bytes(e[0x1C:0x20], 'little'), e[0x800:0x800 + 0x60000])
        for m in seen.get(k, []): pairs.append((m, n))
        seen.setdefault(k, []).append(n)
    return pairs


class T(unittest.TestCase):
    def test_exact(self):
        names = [n for n in dwsyms.CANDIDATES if os.path.exists(dwsyms.CANDIDATES[n][0])]
        if len(names) < 2: self.skipTest('need builds')
        for n in names[:12]:
            got = dwsyms.detect_build(ram_of(n), log=False)
            self.assertIsNotNone(got, n)
            self.assertEqual(dwsyms.table(got), dwsyms.table(n), n)

    def test_same_start(self):
        for a, b in same_start()[:6]:
            ra = ram_of(a)
            got = dwsyms.detect_build(ra, log=False)
            self.assertEqual(dwsyms.table(got), dwsyms.table(a), (a, b))

    def test_explicit(self):
        n = next(iter(dwsyms.CANDIDATES))
        self.assertEqual(dwsyms.detect_build(b'', n, log=False), n)

    def test_unloaded(self):
        self.assertIsNone(dwsyms.detect_build(bytes(0x200000), log=False))


class WideIds(unittest.TestCase):
    def test_explicit_disc_executable_keeps_wide_inventory(self):
        from tools.dev import game_state as gamestate
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            disc = Path(tmp) / 'build/test-disc'
            (disc / 'exe').mkdir(parents=True)
            exe = disc / 'exe/SLUS_010.32'
            exe.touch()
            (disc / 'SCRN.DAT').touch()
            self.assertTrue(dwsyms.wide_ids(str(exe)))
            with patch.object(gamestate, 'BUILD', str(exe)):
                fmt = gamestate.schema()['inventory.types'][1]
                self.assertEqual(fmt, '30h')
                self.assertEqual(gamestate.encode(0, fmt, [-1] * 30), [(0, b'\xff' * 60)])
                self.assertEqual(gamestate.schema()['current_screen'][1], 'h')

    def test_explicit_language_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            disc = Path(tmp) / 'test-disc'
            (disc / 'exe-ja').mkdir(parents=True)
            exe = disc / 'exe-ja/SLUS_010.32'
            exe.touch()
            (disc / 'SCRN.DAT').touch()
            self.assertTrue(dwsyms.wide_ids(str(exe)))

    def test_explicit_decomp_header_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            exe = tree / 'build/us/psx/gcc/SLUS_010.32'
            exe.parent.mkdir(parents=True)
            exe.touch()
            header = tree / 'include/dw/ids.h'
            header.parent.mkdir(parents=True)
            header.write_text('typedef int16_t ScreenId;')
            self.assertTrue(dwsyms.wide_ids(str(exe)))
            header.write_text('typedef uint8_t ScreenId;')
            self.assertFalse(dwsyms.wide_ids(str(exe)))

    def test_original_has_byte_ids(self):
        self.assertFalse(dwsyms.wide_ids('orig'))


if __name__ == '__main__': unittest.main()
