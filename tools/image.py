# SPDX-License-Identifier: MIT
# Historical compatibility arithmetic is attributed in image-license.txt.
"""Small byte-backed raster API for repository tools; no optional imports at load time.

PNG, cropping, masks, compositing, nearest/box resizing and median cut use only
Python. JPEG and review-sheet drawing use OpenCV, loaded on demand. High quality
resizing uses separable 22-bit coefficients and clips between passes, preserving
our historical 8-bit RGB rasters. This is a deliberately limited API, not a general
image library. Review labels use the repository bitmap fonts (not the requested TTF).
"""

import builtins
import math
import struct
import zlib
from enum import IntEnum
from types import SimpleNamespace


class Resampling(IntEnum):
    NEAREST = 0
    LANCZOS = 1
    BILINEAR = 2
    BICUBIC = 3
    BOX = 4


def _color(value, mode):
    n = len(mode) if mode != "P" else 1
    if isinstance(value, str):
        names = dict(
            black="#000000",
            white="#ffffff",
            red="#ff0000",
            green="#008000",
            blue="#0000ff",
            yellow="#ffff00",
            cyan="#00ffff",
            magenta="#ff00ff",
            gray="#808080",
            grey="#808080",
            orange="#ffa500",
            transparent="#00000000",
        )
        value = names.get(value.lower(), value)
        if value.startswith("#"):
            s = value[1:]
            if len(s) in (3, 4):
                s = "".join(c * 2 for c in s)
            value = tuple(bytes.fromhex(s))
        else:
            raise ValueError(f"unknown colour: {value}")
    if isinstance(value, int):
        return (value,) * n
    value = tuple(value)
    if n == 1:
        return value[:1]
    return (value + (255,))[:n]


def _chunk(kind, body):
    return (
        struct.pack(">I", len(body))
        + kind
        + body
        + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    )


def _read_png(raw):
    pos, packed, palette, trans = 8, bytearray(), None, None
    while pos < len(raw):
        length, kind = struct.unpack_from(">I4s", raw, pos)
        body = raw[pos + 8 : pos + 8 + length]
        if len(body) != length or pos + 12 + length > len(raw):
            raise ValueError("truncated PNG chunk")
        (crc,) = struct.unpack_from(">I", raw, pos + 8 + length)
        if zlib.crc32(kind + body) & 0xFFFFFFFF != crc:
            raise ValueError("PNG CRC mismatch")
        pos += length + 12
        if kind == b"IHDR":
            w, h, depth, ct, comp, filt, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = list(body)
        elif kind == b"tRNS":
            trans = body
        elif kind == b"IDAT":
            packed.extend(body)
        elif kind == b"IEND":
            break
    if interlace or comp or filt or depth not in (1, 2, 4, 8) or (depth != 8 and ct not in (0, 3)):
        raise ValueError("PNG requires non-interlaced 1/2/4/8-bit grey/palette or 8-bit RGB(A)")
    mode = {0: "L", 2: "RGB", 3: "P", 4: "LA", 6: "RGBA"}[ct]
    channels = 1 if ct == 3 else len(mode)
    stride, bpp = (w * channels * depth + 7) // 8, max(1, (channels * depth + 7) // 8)
    data = zlib.decompress(packed)
    if len(data) != h * (stride + 1):
        raise ValueError("PNG scanline length mismatch")
    pixels, prev = bytearray(), bytearray(stride)
    for y in range(h):
        start = y * (stride + 1)
        kind = data[start]
        row = bytearray(data[start + 1 : start + 1 + stride])
        if kind > 4:
            raise ValueError("unknown PNG filter")
        if kind:
            for x in range(stride):
                a = row[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                if kind == 1:
                    v = a
                elif kind == 2:
                    v = b
                elif kind == 3:
                    v = (a + b) // 2
                else:
                    pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                    v = a if pa <= pb and pa <= pc else b if pb <= pc else c
                row[x] = (row[x] + v) & 255
        prev = row
        if depth == 8:
            pixels.extend(row)
        else:
            mask = (1 << depth) - 1
            pixels.extend(
                ((row[x * depth // 8] >> (8 - depth - x * depth % 8)) & mask)
                * (255 // mask if ct == 0 else 1)
                for x in range(w)
            )
    im = Raster(mode, (w, h), pixels)
    im.palette = palette
    if trans is not None:
        im.info["transparency"] = (
            trans if mode == "P" else struct.unpack(">" + "H" * (len(trans) // 2), trans)
        )
        if ct == 0 and depth < 8:
            im.info["transparency"] = (im.info["transparency"][0] * (255 // ((1 << depth) - 1)),)
    return im


class Raster:
    def __init__(self, mode, size, data):
        if mode not in ("L", "LA", "RGB", "RGBA", "P"):
            raise ValueError(f"unsupported mode {mode}")
        self.mode, self.size = mode, tuple(map(int, size))
        self.width, self.height = self.size
        self.channels = 1 if mode == "P" else len(mode)
        if min(self.size) < 1:
            raise ValueError("image dimensions must be positive")
        self.data = bytearray(data)
        if len(self.data) != self.width * self.height * self.channels:
            raise ValueError("pixel buffer length mismatch")
        self.palette, self.info = None, {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        pass

    def copy(self):
        im = Raster(self.mode, self.size, self.data)
        im.palette = self.palette[:] if self.palette else None
        im.info = self.info.copy()
        return im

    def __array__(self, dtype=None, copy=None):
        import numpy as np

        a = np.frombuffer(self.data, dtype=np.uint8).reshape(
            (self.height, self.width) + ((self.channels,) if self.channels > 1 else ())
        )
        if dtype is not None:
            a = a.astype(dtype)
        return a.copy() if copy else a

    def tobytes(self):
        return bytes(self.data)

    def load(self):
        return self

    def __getitem__(self, xy):
        return self.getpixel(xy)

    def __setitem__(self, xy, value):
        self.putpixel(xy, value)

    def _offset(self, xy):
        x, y = map(int, xy)
        if x < 0:
            x += self.width
        if y < 0:
            y += self.height
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(xy)
        return (y * self.width + x) * self.channels

    def getpixel(self, xy):
        i = self._offset(xy)
        return self.data[i] if self.channels == 1 else tuple(self.data[i : i + self.channels])

    def putpixel(self, xy, value):
        i = self._offset(xy)
        self.data[i : i + self.channels] = bytes(_color(value, self.mode))

    def getdata(self):
        n = self.channels
        return (
            list(self.data)
            if n == 1
            else [tuple(self.data[i : i + n]) for i in range(0, len(self.data), n)]
        )

    def putdata(self, values):
        n = self.channels
        raw = bytearray(values) if n == 1 else bytearray(c for p in values for c in p)
        if len(raw) != len(self.data):
            raise ValueError("pixel count mismatch")
        self.data[:] = raw

    def putpalette(self, palette):
        self.palette = list(palette)

    def getpalette(self):
        return self.palette

    def convert(self, mode):
        if mode == self.mode:
            return self.copy()
        if mode == "P":
            return self.quantize()
        if (
            mode in ("RGB", "RGBA")
            and self.mode in ("RGB", "RGBA", "L")
            and "transparency" not in self.info
        ):
            channels = len(mode)
            count = self.width * self.height
            out = bytearray(count * channels)
            for channel in range(3):
                out[channel::channels] = self.data[
                    (channel if self.mode != "L" else 0) :: self.channels
                ]
            if channels == 4:
                out[3::4] = self.data[3::4] if self.mode == "RGBA" else bytes([255]) * count
            return Raster(mode, self.size, out)
        out = bytearray()
        trans = self.info.get("transparency")
        for p in self.getdata():
            if self.mode == "P":
                rgb = tuple(self.palette[p * 3 : p * 3 + 3])
                a = trans[p] if isinstance(trans, bytes) and p < len(trans) else 255
            elif self.mode == "L":
                rgb = (p, p, p)
                a = 0 if trans == (p,) else 255
            elif self.mode == "LA":
                rgb = (p[0],) * 3
                a = p[1]
            else:
                rgb = p[:3]
                a = p[3] if self.mode == "RGBA" else 0 if trans == rgb else 255
            if mode in ("L", "LA"):
                grey = (rgb[0] * 19595 + rgb[1] * 38470 + rgb[2] * 7471 + 32768) >> 16
                out.extend((grey, a) if mode == "LA" else (grey,))
            else:
                out.extend(rgb + (a,) if mode == "RGBA" else rgb)
        return Raster(mode, self.size, out)

    def crop(self, box):
        l, t, r, b = map(round, box)
        if r <= l or b <= t:
            raise ValueError("empty crop")
        out = new(self.mode, (r - l, b - t))
        out.palette = self.palette
        out.info = self.info.copy()
        n = self.channels
        for y in range(max(0, t), min(b, self.height)):
            x0, x1 = max(0, l), min(r, self.width)
            if x1 > x0:
                dst = ((y - t) * out.width + x0 - l) * n
                src = (y * self.width + x0) * n
                out.data[dst : dst + (x1 - x0) * n] = self.data[src : src + (x1 - x0) * n]
        return out

    def paste(self, source, box=None, mask=None):
        box = box or (0, 0)
        if not isinstance(source, Raster):
            if len(box) != 4:
                raise ValueError("solid paste needs rectangle")
            source = new(self.mode, (box[2] - box[0], box[3] - box[1]), source)
        if len(box) == 4 and tuple(box[2 + i] - box[i] for i in (0, 1)) != source.size:
            raise ValueError("paste size mismatch")
        x, y = map(int, box[:2])
        source = source.convert(self.mode) if source.mode != self.mode else source
        if mask is not None and mask.size != source.size:
            raise ValueError("mask size mismatch")
        n = self.channels
        for sy in range(max(0, -y), min(source.height, self.height - y)):
            sx0, sx1 = max(0, -x), min(source.width, self.width - x)
            if sx0 >= sx1:
                continue
            si = (sy * source.width + sx0) * n
            di = ((sy + y) * self.width + x + sx0) * n
            count = (sx1 - sx0) * n
            if mask is None:
                self.data[di : di + count] = source.data[si : si + count]
            else:
                for sx in range(sx0, sx1):
                    mi = (sy * mask.width + sx) * mask.channels
                    a = mask.data[mi + mask.channels - 1]
                    for c in range(n):
                        self.data[di + c] = (
                            source.data[si + c] * a + self.data[di + c] * (255 - a) + 127
                        ) // 255
                    si += n
                    di += n

    def getchannel(self, channel):
        i = self.mode.index(channel) if isinstance(channel, str) else channel
        return Raster("L", self.size, self.data[i :: self.channels])

    def split(self):
        return tuple(self.getchannel(i) for i in range(self.channels))

    def putalpha(self, alpha):
        im = self.convert("RGBA")
        values = (
            alpha.convert("L").data
            if isinstance(alpha, Raster)
            else bytes([alpha]) * (self.width * self.height)
        )
        if len(values) != self.width * self.height:
            raise ValueError("alpha dimensions mismatch")
        im.data[3::4] = values
        self.__dict__.update(im.__dict__)

    def getbbox(self):
        data = (
            self.data[3::4]
            if self.mode == "RGBA"
            else [
                any(self.data[i : i + self.channels])
                for i in range(0, len(self.data), self.channels)
            ]
        )
        on = [i for i, v in enumerate(data) if v]
        return (
            (
                min(i % self.width for i in on),
                min(i // self.width for i in on),
                max(i % self.width for i in on) + 1,
                max(i // self.width for i in on) + 1,
            )
            if on
            else None
        )

    def resize(self, size, resample=Resampling.BICUBIC):
        size = tuple(map(int, size))
        if size == self.size:
            return self.copy()
        if min(size) < 1:
            raise ValueError("invalid resize dimensions")
        if resample == Resampling.NEAREST or self.mode == "P":
            n = self.channels
            w, h = size
            out = bytearray()
            xs = []
            center = self.width / w * 0.5
            for x in range(w):
                xs.append(min(self.width - 1, int(center)) * n)
                center += self.width / w
            center = self.height / h * 0.5
            for y in range(h):
                row = min(self.height - 1, int(center)) * self.width * n
                center += self.height / h
                for x in xs:
                    out.extend(self.data[row + x : row + x + n])
            im = Raster(self.mode, size, out)
            im.palette = self.palette
            im.info = self.info.copy()
            return im
        # Fixed-point separable filters: preserve rounding and intermediate clipping.
        return _resize(self, size, resample)

    def thumbnail(self, size, resample=Resampling.BICUBIC):
        factor = min(1, size[0] / self.width, size[1] / self.height)
        im = self.resize(
            (max(1, round(self.width * factor)), max(1, round(self.height * factor))), resample
        )
        self.__dict__.update(im.__dict__)

    def quantize(self, colors=256, method=0, **kwargs):
        from tools.mediancut import quantize

        pal, indices = quantize(self.convert("RGB").getdata(), colors)
        im = Raster("P", self.size, indices)
        im.palette = [c for p in pal for c in p]
        return im

    def alpha_composite(self, other, dest=(0, 0)):
        if self.mode != "RGBA":
            raise ValueError("alpha_composite requires RGBA")
        other = other.convert("RGBA")
        x, y = dest
        for sy in range(max(0, -y), min(other.height, self.height - y)):
            for sx in range(max(0, -x), min(other.width, self.width - x)):
                si = (sy * other.width + sx) * 4
                di = ((sy + y) * self.width + sx + x) * 4
                s = other.data[si : si + 4]
                d = self.data[di : di + 4]
                a = s[3] * 255 + d[3] * (255 - s[3])
                if not s[3]:
                    continue
                coefficient = s[3] * 255 * 255 * 128 // a
                colours = []
                for c in range(3):
                    value = s[c] * coefficient + d[c] * (255 * 128 - coefficient) + (128 << 7)
                    colours.append((((value >> 8) + value) >> 8) >> 7)
                value = a + 128
                self.data[di : di + 4] = bytes(colours + [((value >> 8) + value) >> 8])

    def save(self, path, format=None, **kwargs):
        fmt = (format or str(path).rsplit(".", 1)[-1]).upper()
        if fmt == "PNG" and not hasattr(path, "write"):
            # Re-exporting accepted art must not change its historical PNG bytes.
            try:
                previous = open_image(path)
            except (OSError, ValueError, KeyError, struct.error, zlib.error):
                previous = None
            if previous is not None and (
                previous.mode == self.mode
                and previous.size == self.size
                and previous.data == self.data
                and previous.palette == self.palette
                and previous.info.get("transparency") == self.info.get("transparency")
            ):
                return
        if fmt not in ("PNG", "APNG"):
            import cv2
            import numpy as np

            mode = "RGBA" if fmt == "WEBP" and self.mode == "RGBA" else "RGB"
            a = np.array(self.convert(mode))[:, :, [2, 1, 0, 3] if mode == "RGBA" else [2, 1, 0]]
            params = []
            if fmt in ("JPEG", "JPG"):
                params = [
                    cv2.IMWRITE_JPEG_QUALITY,
                    kwargs.get("quality", 75),
                    cv2.IMWRITE_JPEG_OPTIMIZE,
                    int(kwargs.get("optimize", False)),
                    cv2.IMWRITE_JPEG_PROGRESSIVE,
                    int(kwargs.get("progressive", False)),
                ]
            elif fmt == "WEBP":
                params = [cv2.IMWRITE_WEBP_QUALITY, kwargs.get("quality", 80)]
            ok, raw = cv2.imencode("." + fmt.lower(), a, params)
            if not ok:
                raise ValueError("image encode failed")
            raw = raw.tobytes()
        else:
            ct = {"L": 0, "RGB": 2, "P": 3, "LA": 4, "RGBA": 6}[self.mode]
            raw = b"\x89PNG\r\n\x1a\n" + _chunk(
                b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, ct, 0, 0, 0)
            )
            if self.mode == "P":
                raw += _chunk(b"PLTE", bytes(self.palette))
                if "transparency" in self.info:
                    raw += _chunk(b"tRNS", bytes(self.info["transparency"]))
            stride = self.width * self.channels
            raw += _chunk(
                b"IDAT",
                zlib.compress(
                    b"".join(
                        b"\0" + self.data[y * stride : (y + 1) * stride] for y in range(self.height)
                    ),
                    kwargs.get("compress_level", 6),
                ),
            ) + _chunk(b"IEND", b"")
        if hasattr(path, "write"):
            path.write(raw)
        else:
            with builtins.open(path, "wb") as f:
                f.write(raw)


def _weights(src, dst, kind):
    def kernel(x):
        x = abs(x)
        if kind == Resampling.BOX:
            return float(x <= 0.5)
        if kind == Resampling.BILINEAR:
            return max(0, 1 - x)
        if kind == Resampling.BICUBIC:
            return (
                ((1.5 * x - 2.5) * x * x + 1)
                if x < 1
                else ((-0.5 * x + 2.5) * x - 4) * x + 2
                if x < 2
                else 0
            )
        if x == 0:
            return 1.0
        return (
            math.sin(math.pi * x) * math.sin(math.pi * x / 3) / (math.pi * math.pi * x * x / 3)
            if x < 3
            else 0.0
        )

    support = {
        Resampling.BOX: 0.5,
        Resampling.BILINEAR: 1,
        Resampling.BICUBIC: 2,
        Resampling.LANCZOS: 3,
    }[kind]
    scale = src / dst
    fs = max(scale, 1)
    result = []
    for i in range(dst):
        center = (i + 0.5) * scale
        lo = max(0, int(center - support * fs + 0.5))
        hi = min(src, int(center + support * fs + 0.5))
        ws = [kernel((x - center + 0.5) / fs) for x in range(lo, hi)]
        # Match the historical C loop on every Python (float sum changed in 3.12).
        total = 0.0
        for weight in ws:
            total += weight
        ws = [int(v / total * (1 << 22) + (0.5 if v >= 0 else -0.5)) for v in ws]
        result.append((lo, ws))
    return result


def _resize(im, size, kind):
    if im.mode in ("RGBA", "LA"):
        # Premultiply before filtering to avoid colour leaking from transparent pixels.
        n = im.channels
        data = im.data[:]
        for i in range(0, len(data), n):
            for c in range(n - 1):
                data[i + c] = (data[i + c] * data[i + n - 1] + 127) // 255
        im = Raster(im.mode, im.size, data)
    else:
        n = im.channels
    w, h = size
    oldw, oldh = im.size
    data = im.data
    if w != oldw:
        weights = _weights(oldw, w, kind)
        out = bytearray(w * oldh * n)
        for y in range(oldh):
            for x, (lo, ws) in enumerate(weights):
                for c in range(n):
                    val = (1 << 21) + sum(
                        data[(y * oldw + lo + j) * n + c] * k for j, k in enumerate(ws)
                    )
                    out[(y * w + x) * n + c] = max(0, min(255, val >> 22))
        data = out
    if h != oldh:
        weights = _weights(oldh, h, kind)
        out = bytearray(w * h * n)
        for y, (lo, ws) in enumerate(weights):
            for x in range(w * n):
                val = (1 << 21) + sum(data[(lo + j) * w * n + x] * k for j, k in enumerate(ws))
                out[y * w * n + x] = max(0, min(255, val >> 22))
        data = out
    if im.mode in ("RGBA", "LA"):
        for i in range(0, len(data), n):
            a = data[i + n - 1]
            if a:
                for c in range(n - 1):
                    data[i + c] = min(255, data[i + c] * 255 // a)
    return Raster(im.mode, size, data)


def new(mode, size, color=0):
    return Raster(mode, size, bytes(_color(color, mode)) * (int(size[0]) * int(size[1])))


def frombytes(mode, size, data):
    return Raster(mode, size, data)


def fromarray(array, mode=None):
    if array.dtype.name == "bool":
        array = array.astype("uint8") * 255
    if array.dtype.name != "uint8":
        raise ValueError("fromarray requires uint8 pixels")
    mode = mode or ("L" if array.ndim == 2 else {2: "LA", 3: "RGB", 4: "RGBA"}[array.shape[2]])
    return Raster(mode, (array.shape[1], array.shape[0]), array.tobytes())


def open_image(path):
    if hasattr(path, "read"):
        raw = path.read()
    else:
        with builtins.open(path, "rb") as f:
            raw = f.read()
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return _read_png(raw)
    import cv2
    import numpy as np

    a = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
    if a is None:
        raise ValueError(f"cannot decode image {path}")
    if a.ndim == 3:
        a = a[:, :, [2, 1, 0, 3] if a.shape[2] == 4 else [2, 1, 0]]
    return fromarray(a)


def composite(a, b, mask):
    out = b.copy()
    out.paste(a, (0, 0), mask)
    return out


Image = SimpleNamespace(
    Image=Raster,
    new=new,
    open=open_image,
    frombytes=frombytes,
    fromarray=fromarray,
    composite=composite,
    Resampling=Resampling,
    MEDIANCUT=0,
    **{k: v for k, v in Resampling.__members__.items()},
)


_REVIEW_GLYPHS = None


def _review_glyphs():
    global _REVIEW_GLYPHS
    if _REVIEW_GLYPHS is None:
        from pathlib import Path
        import re

        glyphs = {}
        folder = Path(__file__).with_name("font")
        for name in ("extra.txt", "b.txt", "japanese.txt"):
            current = None
            for line in (folder / name).read_text().splitlines():
                match = re.fullmatch(r"glyph (\S)(?: (\d+))?", line)
                if match:
                    current = [int(match[2]) if match[2] else None, []]
                    glyphs[match[1]] = current
                elif current is not None and re.fullmatch(r"[.#]+", line):
                    current[1].append(line)
        result = {}
        for char, (advance, rows) in glyphs.items():
            if advance is None:
                ink = [x for row in rows for x, value in enumerate(row) if value == "#"]
                left, right = (min(ink), max(ink) + 1) if ink else (0, 1)
                rows = [row[left:right] for row in rows]
                advance = right - left + 1
            width = max(map(len, rows))
            mask = Raster(
                "L",
                (width, len(rows)),
                bytes(255 if c == "#" else 0 for row in rows for c in row.ljust(width, ".")),
            )
            result[char] = (advance, mask)
        arrow = (
            ["........."] * 2
            + [".....#...", "......#..", "########.", "......#..", ".....#..."]
            + ["........."] * 4
        )
        for char, rows in (("→", arrow), ("←", [r[::-1] for r in arrow])):
            result[char] = (
                10,
                Raster("L", (9, 11), bytes(255 if c == "#" else 0 for row in rows for c in row)),
            )
        result[" "] = (4, new("L", (4, 11)))
        _REVIEW_GLYPHS = result
    return _REVIEW_GLYPHS


class _Font:
    def __init__(self, size=12):
        self.size = size

    def glyph(self, char):
        glyphs = _review_glyphs()
        return glyphs.get(char, glyphs["?"])

    def getbbox(self, text):
        lines = str(text).split("\n")
        width = max(sum(self.glyph(c)[0] for c in line) for line in lines)
        return (0, 0, math.ceil(width * self.size / 11), math.ceil(len(lines) * self.size * 1.3))


ImageFont = SimpleNamespace(
    load_default=lambda **kw: _Font(kw.get("size", 12)),
    truetype=lambda path, size, **kw: _Font(size),
)


class _Draw:
    def __init__(self, im, mode=None):
        self.im = im

    def _draw(self, fn):
        import numpy as np
        import cv2

        a = np.asarray(self.im)
        fn(cv2, a)

    def textlength(self, text, font=None, **kw):
        return (font or _Font()).getbbox(text)[2]

    def textbbox(self, xy, text, font=None, **kw):
        x, y = xy
        _, _, w, h = (font or _Font()).getbbox(text)
        return (x, y, x + w, y + h)

    def text(self, xy, text, fill=0, font=None, anchor=None, stroke_width=0, **kw):
        font = font or _Font()
        x, y = map(int, xy)
        text = str(text)
        if anchor:
            _, _, w, h = font.getbbox(text)
            if anchor[0] == "m":
                x -= w // 2
            elif anchor[0] == "r":
                x -= w
            if anchor[-1] == "m":
                y -= h // 2
            elif anchor[-1] in ("b", "s"):
                y -= h
        color = _color(fill, self.im.mode)

        for row, line in enumerate(text.split("\n")):
            pen = 0
            for char in line:
                advance, glyph = font.glyph(char)
                width = max(1, round(glyph.width * font.size / 11))
                height = max(1, round(glyph.height * font.size / 11))
                mask = glyph.resize((width, height), Resampling.NEAREST)
                position = (x + round(pen * font.size / 11), y + round(row * font.size * 1.3))
                self.im.paste(new(self.im.mode, mask.size, color), position, mask)
                pen += advance

    def rectangle(self, box, fill=None, outline=None, width=1):
        import numpy as np

        pts = np.array(box).reshape(-1, 2).astype(int)
        a, b = map(tuple, (pts[0], pts[-1]))

        def paint(cv, img):
            if fill is not None:
                cv.rectangle(img, a, b, _color(fill, self.im.mode), -1)
            if outline is not None:
                cv.rectangle(img, a, b, _color(outline, self.im.mode), width)

        self._draw(paint)

    def rounded_rectangle(self, box, radius=0, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = map(int, box)
        r = min(int(radius), (x1 - x0) // 2, (y1 - y0) // 2)

        def paint(cv, img):
            col = _color(fill if fill is not None else outline, self.im.mode)
            thick = -1 if fill is not None else width
            cv.rectangle(img, (x0 + r, y0), (x1 - r, y1), col, thick)
            cv.rectangle(img, (x0, y0 + r), (x1, y1 - r), col, thick)
            for x, y in ((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)):
                cv.circle(img, (x, y), r, col, thick)

        self._draw(paint)

    def line(self, xy, fill=None, width=1, **kw):
        import numpy as np

        p = np.array(xy, dtype="int32").reshape(-1, 2)
        self._draw(
            lambda cv, a: cv.polylines(a, [p], False, _color(fill or 0, self.im.mode), width)
        )

    def polygon(self, xy, fill=None, outline=None, width=1):
        import numpy as np

        p = np.array(xy, dtype="int32").reshape(-1, 2)

        def paint(cv, a):
            if fill is not None:
                cv.fillPoly(a, [p], _color(fill, self.im.mode))
            if outline is not None:
                cv.polylines(a, [p], True, _color(outline, self.im.mode), width)

        self._draw(paint)

    def ellipse(self, box, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = map(int, box)
        center = ((x0 + x1) // 2, (y0 + y1) // 2)
        axes = ((x1 - x0) // 2, (y1 - y0) // 2)

        def paint(cv, a):
            if fill is not None:
                cv.ellipse(a, center, axes, 0, 0, 360, _color(fill, self.im.mode), -1)
            if outline is not None:
                cv.ellipse(a, center, axes, 0, 0, 360, _color(outline, self.im.mode), width)

        self._draw(paint)


def _difference(a, b):
    if a.mode != b.mode or a.size != b.size:
        raise ValueError("image mismatch")
    return Raster(a.mode, a.size, bytes(abs(x - y) for x, y in zip(a.data, b.data)))


def _add(a, b, scale=1.0, offset=0):
    if a.mode != b.mode or a.size != b.size:
        raise ValueError("image mismatch")
    return Raster(
        a.mode,
        a.size,
        bytes(max(0, min(255, int((x + y) / scale + offset))) for x, y in zip(a.data, b.data)),
    )


class _Stat:
    def __init__(self, im):
        self.mean = [
            sum(im.data[c :: im.channels]) / (im.width * im.height) for c in range(im.channels)
        ]


ImageDraw = SimpleNamespace(Draw=_Draw)
ImageChops = SimpleNamespace(difference=_difference, add=_add)
ImageStat = SimpleNamespace(Stat=_Stat)
