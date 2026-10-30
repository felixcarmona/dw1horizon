"""Mutable palette-index texture + helpers shared by build.py."""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from idx import load

# the disc's files: tools/localize/build.py --extracted (LOCALIZE_EXTRACTED), else the repository's extracted/
EXT = os.path.join(os.environ.get('LOCALIZE_EXTRACTED') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'extracted'), '')


def c15(v):
    return (0, 0, 0, 0) if v == 0 else ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3, 255)


class Tex:
    def __init__(self, rel, entry=0):
        self.rel, self.entry = rel, entry
        w, h, px, cl, bpp = load(EXT + rel, entry)
        self.w, self.h, self.cl, self.bpp = w, h, cl, bpp
        self.p = bytearray(px(x, y) for y in range(h) for x in range(w))

    def copy(self):
        t = Tex.__new__(Tex)
        t.__dict__.update(self.__dict__)
        t.p = bytearray(self.p)
        return t

    def g(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.p[y * self.w + x]
        return -1

    def s(self, x, y, v):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.p[y * self.w + x] = v
        else:
            raise IndexError((x, y))

    def fill(self, x0, y0, x1, y1, v):  # inclusive-exclusive
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.s(x, y, v)

    def block(self, x0, y0, w, h):
        return [[self.g(x0 + i, y0 + j) for i in range(w)] for j in range(h)]

    def paste(self, blk, x0, y0, skip=None):
        for j, row in enumerate(blk):
            for i, v in enumerate(row):
                if skip is not None and v == skip:
                    continue
                self.s(x0 + i, y0 + j, v)

    def image(self, clut=0, crop=None, bg=None):
        from tools.image import Image   # (previews only)
        pal = self.cl[4][clut]
        im = Image.new('RGBA', (self.w, self.h))
        im.putdata([c15(pal[v]) for v in self.p])
        if crop:
            u, v, w, h = crop
            im = im.crop((u, v, u + w, v + h))
        if bg is not None:
            b = Image.new('RGBA', im.size, bg + (255,))
            b.alpha_composite(im)
            im = b
        return im

    def save_idx(self, path):
        open(path, 'wb').write(bytes(self.p))


def outline(ink, mode='R'):
    """Outline pixels around an ink set. 8 = full 8-dilation; 'R' = 8-dilation except the
    diagonal-only bumps beside a diagonal step (matches the game's 1-px label fonts and TIME UP)."""
    out = set()
    for (x, y) in ink:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                q = (x + dx, y + dy)
                if q in ink:
                    continue
                if dx and dy and mode == 'R':
                    if (x + dx, y) not in ink and (x, y + dy) not in ink and \
                            ((x + dx, y - dy) in ink or (x - dx, y + dy) in ink):
                        continue
                out.add(q)
    return out


def mask(rows, ch='#'):
    """list of strings -> set of (x,y)."""
    return {(x, y) for y, r in enumerate(rows) for x, c in enumerate(r) if c == ch}


def holes(ink_and_outline, x0, y0, x1, y1):
    """Pixels inside [x0,x1)x[y0,y1) not reachable from the border without crossing the set."""
    from collections import deque
    seen = set(); dq = deque()
    for x in range(x0 - 1, x1 + 1):
        for y in (y0 - 1, y1):
            dq.append((x, y))
    for y in range(y0 - 1, y1 + 1):
        for x in (x0 - 1, x1):
            dq.append((x, y))
    while dq:
        q = dq.popleft()
        if q in seen or q in ink_and_outline:
            continue
        x, y = q
        if not (x0 - 1 <= x <= x1 and y0 - 1 <= y <= y1):
            continue
        seen.add(q)
        dq.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])
    return {(x, y) for x in range(x0, x1) for y in range(y0, y1)} - seen - ink_and_outline
