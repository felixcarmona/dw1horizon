"""Pillow's MEDIANCUT quantizer (Image.quantize(colors, method=MEDIANCUT), kmeans 0) in plain Python, the same
palette and indices: the localize step's tournament banners are quantized with it on the player's path, which has no
Pillow (docs/derive.md).

    quantize(pixels, colors) -> (palette [(r, g, b)], indices)     pixels: [(r, g, b)] row-major

A port of Pillow 12.3.0's src/libImaging/Quant.c (quantize, median_cut, splitlists, map_image_pixels_from_median_box)
and QuantHeap.c, step for step where the result depends on it:
  - the colour table is keyed by PIXEL_HASH (a 32-bit hash): two colours with the same hash are one entry, the first
    one seen (Pillow's pixel_cmp compares the hashes); its count is both's. Above 65536 entries Pillow rescales the
    colours (not ported: a banner has at most 256 x 256 pixels; quantize refuses more entries);
  - boxes are split in the order of Pillow's binary heap on their pixel counts (ties as its heap leaves them), along
    the axis of the largest range weighted 77/150/29, the higher values going left, the split value's run kept left;
    a box of volume 1 is not split;
  - palette entries are numbered in the tree's order (left first), each the rounded average of the pixels in its box;
  - each colour is mapped from its box's entry to the nearest entry (squared RGB distance) found among the entries no
    farther than twice that distance from it, in order of distance then index, as Quant.c's distance tables.
Standard library only.
"""

MAX_HASH_ENTRIES = 65536


def _hash(r, g, b):
    return ((r * 463) ^ ((g << 8) * 10069) ^ ((b << 16) * 64997)) & 0xFFFFFFFF


class _Box:
    __slots__ = ('cols', 'count', 'l', 'r', 'volume')

    def __init__(self, cols, count):
        self.cols, self.count, self.l, self.r, self.volume = cols, count, None, None, -1

    def bounds(self, axis):
        vals = [c[axis] for c in self.cols]
        return max(vals), min(vals)


class _Heap:
    """QuantHeap.c: a binary heap on [1..n], the largest pixel count on top."""
    def __init__(self):
        self.h = [None]

    @staticmethod
    def cf(a, b):
        return a.count - b.count

    def add(self, v):
        h = self.h
        h.append(None)
        k = len(h) - 1
        while k != 1:
            if self.cf(v, h[k // 2]) <= 0:
                break
            h[k] = h[k // 2]
            k >>= 1
        h[k] = v

    def remove(self):
        h = self.h
        n = len(h) - 1
        if not n:
            return None
        top, v = h[1], h[n]
        h.pop()
        n -= 1
        k = 1
        while k * 2 <= n:
            l = k * 2
            if l < n and self.cf(h[l], h[l + 1]) < 0:
                l += 1
            if self.cf(v, h[l]) > 0:
                break
            h[k] = h[l]
            k = l
        if n:
            h[k] = v
        return top


def _volume(b):
    if b.volume < 0:
        if not b.cols:
            b.volume = 0
        else:
            v = 1
            for axis in range(3):
                hi, lo = b.bounds(axis)
                v *= hi - lo + 1
            b.volume = v
    return b.volume


def _split(node):
    """Quant.c split + splitlists: the node's colours in two boxes (node.l: the high side of the axis)."""
    f = []
    for axis, w in enumerate((77, 150, 29)):
        hi, lo = node.bounds(axis)
        f.append((hi - lo) * w)
    axis = 0
    for i in (1, 2):
        if f[axis] < f[i]:
            axis = i
    cols = sorted(node.cols, key=lambda c: -c[axis])        # (membership depends on values only)
    left, n0, i = 0, 0, 0
    while i < len(cols):
        left += cols[i][3]
        n0 += cols[i][3]
        i += 1
        if left * 2 > node.count:
            break
    if i < len(cols):
        v = cols[i - 1][axis]
        while i < len(cols) and cols[i][axis] == v:
            n0 += cols[i][3]
            i += 1
    lo_part, hi_part = cols[:i], cols[i:]
    if not hi_part:                                          # (the last value's run goes right)
        v = cols[-1][axis]
        j = len(cols)
        while j > 0 and cols[j - 1][axis] == v:
            j -= 1
        lo_part, hi_part = cols[:j], cols[j:]
        n0 = sum(c[3] for c in lo_part)
    node.l = _Box(lo_part, n0)
    node.r = _Box(hi_part, node.count - n0)
    node.cols = None


def quantize(pixels, colors):
    """-> (palette [(r, g, b)], indices) as Pillow's quantize(colors, MEDIANCUT) of an RGB image of these pixels."""
    table = {}                                               # hash -> [r, g, b, count] (the first colour seen)
    for p in pixels:
        k = _hash(*p)
        e = table.get(k)
        if e is None:
            table[k] = [p[0], p[1], p[2], 1]
        else:
            e[3] += 1
    if len(table) > MAX_HASH_ENTRIES:
        raise ValueError(f'{len(table)} colours: Pillow rescales above {MAX_HASH_ENTRIES} (not ported)')
    root = _Box([tuple(e) for e in table.values()], len(pixels))
    heap = _Heap()
    heap.add(root)
    n = colors
    while True:
        n -= 1
        if not n:
            break
        while True:
            b = heap.remove()
            if b is None:
                break
            if _volume(b) != 1:
                break
        if b is None:
            break
        _split(b)
        heap.add(b.l)
        heap.add(b.r)
    box_of = {}                                              # hash -> palette entry
    entries = [0]

    def annotate(b):
        if b.l is not None:
            annotate(b.l); annotate(b.r)
            return
        for c in b.cols:
            box_of[_hash(c[0], c[1], c[2])] = entries[0]
        if b.cols:
            entries[0] += 1
    annotate(root)
    npal = entries[0]
    sums = [[0, 0, 0, 0] for _ in range(npal)]
    for p in pixels:
        s = sums[box_of[_hash(*p)]]
        s[0] += p[0]; s[1] += p[1]; s[2] += p[2]; s[3] += 1
    pal = [tuple(int(.5 + s[i] / s[3]) for i in range(3)) for s in sums]
    dist = [[(a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2 for b in pal] for a in pal]
    order = [sorted(range(npal), key=lambda j, row=row: (row[j], j)) for row in dist]
    seen, out = {}, []
    for p in pixels:
        v = seen.get(p)
        if v is None:
            box = box_of[_hash(*p)]
            q = pal[box]
            best = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 + (q[2] - p[2]) ** 2
            v, limit, row = box, best << 2, dist[box]
            for j in order[box]:
                if row[j] > limit:
                    break
                q = pal[j]
                d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 + (q[2] - p[2]) ** 2
                if d < best:
                    best, v = d, j
            seen[p] = v
        out.append(v)
    return pal, out
