"""Asset-free raster regression tests; run with plain Python, no image packages."""

import hashlib
import io
import random
import struct
import tempfile
from pathlib import Path
import unittest
import zlib

try:
    from tools.image import Image, ImageDraw, ImageFont, _chunk
except ModuleNotFoundError:
    from image import Image, ImageDraw, ImageFont, _chunk


class Images(unittest.TestCase):
    def test_modes_roundtrip(self):
        for mode in ("L", "LA", "RGB", "RGBA", "P"):
            with self.subTest(mode=mode):
                im = Image.new(mode, (3, 2))
                im.putdata(
                    list(range(6)) if mode in ("L", "P") else [(i,) * len(mode) for i in range(6)]
                )
                if mode == "P":
                    im.putpalette([0, 0, 0, 255, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14])
                    im.info["transparency"] = b"\x00\xff\x80"
                stream = io.BytesIO()
                im.save(stream, format="PNG")
                stream.seek(0)
                result = Image.open(stream)
                self.assertEqual(
                    (result.mode, result.size, result.tobytes()), (mode, im.size, im.tobytes())
                )
                self.assertEqual(result.convert("RGBA").tobytes(), im.convert("RGBA").tobytes())

    def test_png_compression_level(self):
        im = Image.new("RGB", (20, 20), "blue")
        raw, compressed = io.BytesIO(), io.BytesIO()
        im.save(raw, format="PNG", compress_level=0)
        im.save(compressed, format="PNG", compress_level=9)
        self.assertGreater(len(raw.getvalue()), len(compressed.getvalue()))
        self.assertEqual(Image.open(io.BytesIO(raw.getvalue())).tobytes(), im.tobytes())
        self.assertEqual(Image.open(io.BytesIO(compressed.getvalue())).tobytes(), im.tobytes())

    def test_optional_preview_codecs(self):
        try:
            import cv2
        except ImportError:
            self.skipTest("optional OpenCV preview encoders")
        rng = random.Random(37)
        im = Image.frombytes("RGB", (64, 64), bytes(rng.randrange(256) for _ in range(64 * 64 * 3)))
        with tempfile.TemporaryDirectory() as tmp:
            low, high, webp = [Path(tmp) / name for name in ("low.jpg", "high.jpg", "alpha.webp")]
            im.save(low, quality=10)
            im.save(high, quality=95, optimize=True, progressive=True)
            self.assertGreater(high.stat().st_size, low.stat().st_size)
            self.assertIn(b"\xff\xc2", high.read_bytes())
            rgba = im.convert("RGBA")
            rgba.putalpha(Image.frombytes("L", im.size, bytes(range(256)) * 16))
            rgba.save(webp, quality=84)
            decoded = Image.open(webp)
            self.assertEqual(decoded.mode, "RGBA")
            self.assertEqual(decoded.getchannel("A").tobytes(), rgba.getchannel("A").tobytes())

    def test_same_raster_retains_existing_png_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accepted.png"
            im = Image.new("RGBA", (2, 2), (7, 8, 9, 255))
            stream = io.BytesIO()
            im.save(stream, format="PNG")
            raw = stream.getvalue()
            raw = raw[:-12] + _chunk(b"tEXt", b"Comment\0historical encoder") + raw[-12:]
            path.write_bytes(raw)
            im.save(path)
            self.assertEqual(path.read_bytes(), raw)
            im.putpixel((0, 0), (8, 9, 10, 255))
            im.save(path)
            self.assertEqual(Image.open(path).tobytes(), im.tobytes())
            self.assertNotEqual(path.read_bytes(), raw)

    def test_all_png_filters(self):
        # Each row uses a different PNG filter, with independently encoded deltas.
        width = 4
        previous = bytes(width * 3)
        raw = bytearray()
        expected = bytearray()
        for kind in range(5):
            row = bytes((i * 19 + kind * 47) % 256 for i in range(width * 3))
            encoded = bytearray()
            for i, value in enumerate(row):
                a = row[i - 3] if i >= 3 else 0
                b = previous[i]
                c = previous[i - 3] if i >= 3 else 0
                p = a + b - c
                dist = [abs(p - v) for v in (a, b, c)]
                prediction = (0, a, b, (a + b) // 2, (a, b, c)[dist.index(min(dist))])[kind]
                encoded.append((value - prediction) % 256)
            raw.extend(bytes([kind]) + encoded)
            expected.extend(row)
            previous = row
        png = (
            b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, 5, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw))
            + _chunk(b"IEND", b"")
        )
        self.assertEqual(Image.open(io.BytesIO(png)).tobytes(), expected)
        damaged = bytearray(png)
        damaged[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "CRC"):
            Image.open(io.BytesIO(damaged))

    def test_packed_palette(self):
        png = (
            b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", 3, 1, 2, 3, 0, 0, 0))
            + _chunk(b"PLTE", bytes([0, 0, 0, 255, 0, 0, 0, 255, 0]))
            + _chunk(b"tRNS", b"\x00\xff\x80")
            + _chunk(b"IDAT", zlib.compress(b"\x00\x18"))
            + _chunk(b"IEND", b"")
        )
        im = Image.open(io.BytesIO(png))
        self.assertEqual(im.getdata(), [0, 1, 2])
        self.assertEqual(
            im.convert("RGBA").getdata(), [(0, 0, 0, 0), (255, 0, 0, 255), (0, 255, 0, 128)]
        )

    def test_packed_grey_transparency(self):
        png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", 3, 1, 2, 0, 0, 0, 0))
        png += (
            _chunk(b"tRNS", struct.pack(">H", 1))
            + _chunk(b"IDAT", zlib.compress(b"\x00\x18"))
            + _chunk(b"IEND", b"")
        )
        self.assertEqual(
            Image.open(io.BytesIO(png)).convert("RGBA").getdata(),
            [(0, 0, 0, 255), (85, 85, 85, 0), (170, 170, 170, 255)],
        )

    def test_crop_and_mask(self):
        base = Image.new("RGB", (3, 3), "blue")
        source = Image.new("RGB", (2, 2), "red")
        base.paste(source, (-1, 1), Image.new("L", (2, 2), 128))
        self.assertEqual(base.getpixel((0, 1)), (128, 0, 127))
        self.assertEqual(base.getpixel((1, 1)), (0, 0, 255))
        self.assertEqual(base.crop((-1, -1, 1, 1)).getdata(), [(0, 0, 0)] * 3 + [(0, 0, 255)])
        rgba = Image.new("RGBA", (2, 2))
        rgba.putpixel((1, 0), (0, 0, 0, 255))
        self.assertEqual(rgba.getbbox(), (1, 0, 2, 1))
        rgba.alpha_composite(Image.new("RGBA", (1, 1), (255, 0, 0, 128)), (1, 0))
        self.assertEqual(rgba.getpixel((1, 0)), (128, 0, 0, 255))

    def test_alpha_fixed_point_rounding(self):
        im = Image.new("RGBA", (1, 1), (65, 149, 170, 139))
        im.alpha_composite(Image.new("RGBA", (1, 1), (197, 65, 96, 221)))
        self.assertEqual(im.getpixel((0, 0)), (187, 72, 102, 240))
        # Fully transparent source preserves hidden destination RGB too.
        im = Image.new("RGBA", (1, 1), (2, 3, 4, 0))
        im.alpha_composite(Image.new("RGBA", (1, 1)))
        self.assertEqual(im.getpixel((0, 0)), (2, 3, 4, 0))

    def test_historical_resampling(self):
        # SHA-256 of old 8-bit resampling, recorded before removing the dependency.
        expected = {
            "RGB": [
                "4a7a720838261c3f2409330e655c2a3ce66090ad3f6a1734a7a9c4b13d8c2476",
                "ec99214f1b5f9089da31046eb3918d3b60f75260d76b27574e28809ef7e00498",
                "5b251d4e4efa45703a43a2ef38848e67b1ae647b5317a9b39256aadab9d25af1",
                "c1f7c5e903381d0df8a1803477d782d5b2e6a850cf1ebeccdc37ccb046e60d4d",
                "36419984cf146d31e8495571b577d1a320efa3cef23fc1934456df49d3fe33a8",
            ],
            "RGBA": [
                "955a144fc990b62a65706ae3ee409f1cc6c8aa484590c06e548ff1a9b6f24ff6",
                "50d064f06d5bed6f2ec8ffab20c2b2df84aad1b6e737e7d00a9d2f100a8a896e",
                "615327b3253365c4af08eafbcba369830c9b3a0a82c30e60b5e66d4023b3cac7",
                "9c597eedda0eccc47c9a7696027b0a871ab58fe3d2deb4af92b43df345d0cb0a",
                "021a167e63d420b8211efde16756cb7a7647f3bfd17f54349a860fcf47b45e01",
            ],
            "L": [
                "bb37f442a465b9c14c49cadb0869b2ceafd62b0f1c5c2bc188e426f38465f4ae",
                "81faa0c6721c324255d8bcb67d19523c61969c5a3ba6aed8f1e40f7baf24693e",
                "7ac73c17aa8b484f68a277304852a3390152b128d608726858a51935cd619b9e",
                "4259c43181b690174f0ab766351389c693ae22c73ec9fcb1c3133615264d6995",
                "10d70dc21a5b1ac3ae62a69471226491df4621bb44f1a81b94b8d40ab818e8cd",
            ],
        }
        rng = random.Random(12)
        for mode, hashes in expected.items():
            im = Image.frombytes(
                mode, (17, 13), bytes(rng.randrange(256) for _ in range(17 * 13 * len(mode)))
            )
            for method, digest in enumerate(hashes):
                with self.subTest(mode=mode, method=method):
                    self.assertEqual(
                        hashlib.sha256(im.resize((7, 5), method).tobytes()).hexdigest(), digest
                    )

    def test_multilingual_review_text_without_optional_packages(self):
        # Accents and Japanese must stay readable when the TTF backend is removed.
        canvas = Image.new("RGB", (240, 40))
        font = ImageFont.truetype("unused.ttf", 16)
        for char in ("é", "ñ", "日", "→"):
            self.assertNotEqual(font.glyph(char)[1].tobytes(), font.glyph("?")[1].tobytes())
        ImageDraw.Draw(canvas).text((2, 2), "Español 日本語", fill="white", font=font)
        self.assertIsNotNone(canvas.getbbox())

    def test_mediancut(self):
        im = Image.new("RGB", (2, 2))
        im.putdata([(255, 0, 0), (0, 0, 255)] * 2)
        self.assertEqual(im.quantize(2).convert("RGB").getdata(), im.getdata())


if __name__ == "__main__":
    unittest.main()
