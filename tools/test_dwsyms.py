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


class FileLocalSymbols(unittest.TestCase):
    """`static` variables (MOD_BOOT_LANGUAGE, the Cheats menu's labCount) are in the executable's ELF symbols but not on a
    line of their own in the linker map: the harness must still find them (the first-boot language picker is answered by
    reading MOD_BOOT_LANGUAGE)."""

    @staticmethod
    def elf(symbols):
        """A minimal ELF32-LE with a symbol table: symbols = [(name, value, binding, type)]."""
        import struct
        names = b'\0' + b''.join(n.encode() + b'\0' for n, *_ in symbols)
        offsets, at = [], 1
        for n, *_ in symbols: offsets.append(at); at += len(n) + 1
        entries = b'\0' * 16 + b''.join(struct.pack('<IIIBBH', o, v, 4, (b << 4) | t, 0, 1)
                                        for o, (n, v, b, t) in zip(offsets, symbols))
        shoff = 0x34 + len(names) + len(entries)
        head = b'\x7fELF\x01\x01\x01' + b'\0' * 9 + struct.pack('<HHIIIIIHHHHHH', 2, 8, 1, 0, 0, shoff, 0, 0x34, 0, 0, 40, 3, 0)
        sh = lambda *f: struct.pack('<10I', *f)
        sections = sh(*[0] * 10) + sh(0, 3, 0, 0, 0x34, len(names), 0, 0, 1, 0) + \
            sh(0, 2, 0, 0, 0x34 + len(names), len(entries), 1, 1, 4, 16)
        return head + names + entries + sections

    def test_locals_are_read_and_globals_and_functions_are_not(self):
        data = self.elf([('MOD_BOOT_LANGUAGE', 0x80135988, 0, 1), ('MAIN_MENU_TICKS', 0x80135000, 1, 1),
                         ('localFunction', 0x80010000, 0, 2)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.elf'; path.write_bytes(data)
            self.assertEqual(dwsyms.elf_locals(str(path)), {'MOD_BOOT_LANGUAGE': 0x80135988})

    def test_a_name_two_files_both_make_static_is_left_out(self):
        data = self.elf([('count', 0x80100000, 0, 1), ('count', 0x80100004, 0, 1), ('ok', 0x80100008, 0, 1)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.elf'; path.write_bytes(data)
            self.assertEqual(dwsyms.elf_locals(str(path)), {'ok': 0x80100008})

    def test_not_an_elf_or_missing_file_gives_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.elf'; path.write_bytes(b'nope')
            self.assertEqual(dwsyms.elf_locals(str(path)), {})
            self.assertEqual(dwsyms.elf_locals(str(Path(tmp) / 'missing')), {})

    def test_table_of_an_explicit_executable_holds_its_statics(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'SLUS_010.32'
            exe.touch()
            Path(str(exe) + '.elf').write_bytes(self.elf([('MOD_BOOT_LANGUAGE', 0x80135988, 0, 1),
                                                          ('MAIN_MENU_TICKS', 0x1, 0, 1)]))
            Path(str(exe) + '.elf.map').write_text('                0x0000000080134e70                MAIN_MENU_TICKS\n')
            table = dwsyms.table(dwsyms.explicit_build(str(exe)))
            self.assertEqual(table['MOD_BOOT_LANGUAGE'], 0x80135988)
            self.assertEqual(table['MAIN_MENU_TICKS'], 0x80134e70)   # the map's global wins


if __name__ == '__main__': unittest.main()
