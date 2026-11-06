"""Disc-derived Square artwork preserves native Confirm and needs no resident painter."""
from pathlib import Path
import hashlib
import struct
import tempfile
from types import SimpleNamespace
import unittest

from tools.care_badge import FILES, _tim, stamp
from tools.localize.systemw import CARE_BUTTON_RECTS


def fixture(japanese=False):
    palette = [(0x111 * i) & 0x7fff for i in range(256)]
    palette[12 * 16 + 8] = 0
    pixels = bytearray([255] * 16384)
    for y in range(55, 67):
        for x in range(76, 124, 2):
            pixels[y * 128 + x // 2] = 0x88
    for frame in range(3):
        for y in range(5):
            for x in range(8 if japanese else 6):
                u, v = 76 + frame * 16 + 4 + x, 55 + 2 + (frame == 2) + y
                offset, shift = v * 128 + u // 2, 4 * (u & 1)
                pixels[offset] = (pixels[offset] & ~(15 << shift)) | ((7 if japanese else 12) << shift)
    return bytearray(struct.pack('<II', 16, 8) + struct.pack('<IHHHH', 524, 96, 488, 16, 16) +
                     struct.pack('<256H', *palette) + struct.pack('<IHHHH', 16396, 320, 128, 64, 128) + pixels)


def badge_hash(data, entry=0):
    pixels, words, _ = _tim(data, entry)
    payload = bytearray()
    for u, v, w, h in CARE_BUTTON_RECTS:
        for y in range(v, v + h):
            start = pixels + y * words * 2 + u // 2
            payload.extend(data[start:start + w // 2])
    start = pixels + 124 * words * 2 + 64
    payload.extend(data[start:start + 32])
    return hashlib.sha256(payload).hexdigest()


class CareBadge(unittest.TestCase):
    def test_only_reserved_cells_change_and_stamp_is_idempotent(self):
        for japanese in (False, True):
            with self.subTest(japanese=japanese):
                data = fixture(japanese)
                original = bytes(data)
                pixels, words, _ = _tim(data, 0)
                allowed = set()
                for u, v, w, h in CARE_BUTTON_RECTS:
                    for y in range(v, v + h):
                        start = pixels + y * words * 2 + u // 2
                        allowed.update(range(start, start + w // 2))
                start = pixels + 124 * words * 2 + 64
                allowed.update(range(start, start + 32))
                stamp(data)
                changed = {i for i, (old, new) in enumerate(zip(original, data)) if old != new}
                self.assertTrue(changed)
                self.assertLessEqual(changed, allowed)  # Includes original TIM CLUT and all Confirm pixels.
                first = bytes(data)
                stamp(data)
                self.assertEqual(bytes(data), first)

    def test_unknown_native_art_fails_without_a_partial_write(self):
        data = fixture()
        pixels, _, _ = _tim(data, 0)
        data[pixels:] = bytes([255] * 16384)
        original = bytes(data)
        with self.assertRaisesRegex(ValueError, 'unrecognized'):
            stamp(data)
        self.assertEqual(data, original)

    @unittest.skipUnless(Path('extracted/ETCDAT/ETCTIM.BIN').exists(), 'needs the source UI textures')
    def test_standalone_and_stack_match_the_previous_emulator_art(self):
        for path, entry in FILES:
            with self.subTest(path=path):
                data = bytearray(Path('extracted', path).read_bytes())
                stamp(data, entry)
                self.assertEqual(badge_hash(data, entry),
                                 'b1e7b69c9135dc9c8adfabb3961ad5abf8f821796cac6af46d09c3af413aceb9')

    def test_single_language_derive_keeps_the_native_ui_assets(self):
        from tools.derive.steps import localize
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            # A stack of nine compatible TIMs exercises the entry-eight upload.
            for path, entry in FILES:
                source = root / 'extracted' / path
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(fixture() * (entry + 1))
            out = root / 'out'
            ctx = SimpleNamespace(root=str(root), env={},
                                  path=lambda *parts: str(out.joinpath(*parts)), log=lambda line: None)
            localize.build(ctx)
            self.assertEqual({disc for _, disc in localize.outputs(ctx) if disc}, {p for p, _ in FILES})
            for path, entry in FILES:
                data = bytearray((out / 'lang-tex/en' / path).read_bytes())
                expected = bytearray((root / 'extracted' / path).read_bytes())
                stamp(expected, entry)
                self.assertEqual(data, expected)


if __name__ == '__main__':
    unittest.main()
