"""The check the patch path runs on every disc it writes: each language file's slot rows name files of THAT disc, with
that disc's sectors and sizes (isowriter.verify_lang_slots). Run for the layout of every base disc the release lists."""
import json
import pathlib
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools import isowriter as iw

SLOT = 0x80090818
COUNT = 6


def patch(names, lead=0x40):
    """A language patch: one DWLP run holding the slot rows of `names` (an empty row ends them)."""
    rows = bytearray(8 * COUNT)
    for i, name in enumerate(names):
        rows[8 * i + 5:8 * i + 8] = (iw.filename_hash(name) & 0xFFFFFF).to_bytes(3, 'little')
    return b'DWLP' + struct.pack('<III', 1, SLOT, len(rows)) + bytes(rows)


class VerifyLanguageSlots(unittest.TestCase):
    def test_every_base_layout(self):
        bases = sorted((ROOT / 'mods/base-discs').glob('dw1-*.json'))
        self.assertGreaterEqual(len(bases), 7)
        for n, path in enumerate(bases):
            files = sorted(json.loads(path.read_text())['files'])
            names = [f.split('/')[-1] for f in files if f.endswith('.TFS')][:COUNT - 1]
            self.assertTrue(names, path.name)
            # a layout of its own per base: other sectors and sizes, as another release's disc has
            where = {f.split('/')[-1]: (300 + 97 * n + 3 * i, 2048 * (i + 1) + 77 * n) for i, f in enumerate(files)}
            langs = {'SCN/LANGES.BIN': bytearray(patch(names)), 'SCN/LANGEN.BIN': bytearray(patch(names[:2])),
                     'SCN/LANGZH.BIN': bytearray(patch([]))}
            for data in langs.values():
                iw.rewrite_lang_slot(data, (SLOT, COUNT), where)
            got = iw.verify_lang_slots((SLOT, COUNT), langs, where)
            self.assertEqual(got, {'SCN/LANGES.BIN': len(names), 'SCN/LANGEN.BIN': 2, 'SCN/LANGZH.BIN': 0}, path.name)
            # the layout of another disc, or rows never rewritten, are refused
            other = {k: (lba + 1, size) for k, (lba, size) in where.items()}
            with self.assertRaises(ValueError):
                iw.verify_lang_slots((SLOT, COUNT), langs, other)
            with self.assertRaises(ValueError):
                iw.verify_lang_slots((SLOT, COUNT), {'SCN/LANGES.BIN': patch(names)}, where)
            # a row whose file the disc lacks is refused too (rewrite_lang_slot skips it silently)
            missing = dict(where); del missing[names[0]]
            with self.assertRaises(ValueError):
                iw.verify_lang_slots((SLOT, COUNT), langs, missing)


if __name__ == '__main__':
    unittest.main()
