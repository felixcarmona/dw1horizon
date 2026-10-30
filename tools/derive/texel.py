"""Integer texel masks and deterministic texture placement, without FFTs."""
from functools import lru_cache
import math

from .arraymath import Array, bool_


@lru_cache(maxsize=512)
def _footprint(uvs):
    x0 = math.floor(min(p[0] for p in uvs)); y0 = math.floor(min(p[1] for p in uvs))
    x1 = math.floor(max(p[0] for p in uvs)); y1 = math.floor(max(p[1] for p in uvs))
    width, height = x1 - x0 + 1, y1 - y0 + 1
    out = bytearray(width * height)
    triangles = ((0, 1, 2),) if len(uvs) == 3 else ((0, 1, 2), (1, 3, 2))
    for indices in triangles:
        tri = [uvs[i] for i in indices]
        left = min(p[0] for p in tri); right = max(p[0] for p in tri)
        top = min(p[1] for p in tri); bottom = max(p[1] for p in tri)
        axes = []
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            nx, ny = b[1] - a[1], a[0] - b[0]
            if nx == ny == 0: continue
            projections = [p[0] * nx + p[1] * ny for p in tri]
            axes.append((nx, ny, min(projections) - 1e-9, max(projections) + 1e-9))
        for y in range(y0, y1 + 1):
            if y + .999 < top or y > bottom: continue
            for x in range(x0, x1 + 1):
                offset = (y - y0) * width + x - x0
                if out[offset] or x + .999 < left or x > right: continue
                for nx, ny, lo, hi in axes:
                    # Evaluate the same square corners and operation order as
                    # the original separating-axis test, including its epsilon.
                    xx, yy = x + .999, y + .999
                    ps = (x*nx+y*ny, xx*nx+y*ny, x*nx+yy*ny, xx*nx+yy*ny)
                    if max(ps) < lo or min(ps) > hi: break
                else: out[offset] = 1
    return x0, y0, width, height, bytes(out)


def footprint(uvs):
    x, y, width, height, data = _footprint(tuple(tuple(p) for p in uvs))
    return x, y, Array(bytearray(data), (height, width), bool_)


def window_pair(intervals, size=128):
    """Two page windows with the original uncovered-area cost and first tie.

    A vertical interval fits window w exactly when hi-size <= w <= lo.
    Coverage at a and b, minus their intersection, gives the covered area.
    Prefix/suffix counts replace thousands of temporary array masks. Areas
    are texel counts (or the integer blink penalty), so all sums are exact
    in the original float64 calculation too.
    """
    starts = [[0] * (size + 1) for _ in range(size + 1)]
    delta = [0] * (size + 2)
    total = 0
    for lo, hi, area in intervals:
        weight = int(area)
        if weight != area or weight < 0:
            raise ValueError('window areas must be nonnegative integers')
        total += weight
        left, right = max(0, hi - size), min(size, lo)
        if left <= right:
            starts[left][right] += weight
            delta[left] += weight; delta[right + 1] -= weight
    if total > 1 << 53:
        raise ValueError('window area exceeds exact float64 integer range')
    coverage, value = [], 0
    for change in delta[:-1]:
        value += change; coverage.append(value)
    active = [0] * (size + 1)
    both = [0] * (size + 1)
    best = None
    for a in range(size + 1):
        row = starts[a]
        value = 0
        for b in range(size, -1, -1):
            active[b] += row[b]
            value += active[b]; both[b] = value
        for b in range(a, size + 1):
            cost = float(total - coverage[a] - coverage[b] + both[b]) + .01 * (abs(a) + abs(b - size))
            if best is None or cost < best[0]:
                best = cost, a, b
    return best[1], best[2]


def _bits(row):
    # String-to-integer conversion is in C and avoids one large shift per texel.
    return int(''.join('1' if v else '0' for v in reversed(list(row))), 2)


def place(occ, mask, align=None):
    """Bottommost then leftmost free placement, with optional x congruence.

    A bit of `candidates` represents a possible x. A set mask texel at dx
    invalidates the x values in occupied_row >> dx. The integer operations
    check all horizontal placements at once, with exact integer collisions.
    """
    height, width = occ.shape; h, w = mask.shape
    if h > height or w > width: return None
    occupied = [_bits(row) for row in occ]
    rows = []
    for dy, row in enumerate(mask):
        bits = _bits(row); positions = []
        while bits:
            bit = bits & -bits; positions.append(bit.bit_length() - 1); bits ^= bit
        if positions: rows.append((dy, positions))
    # Dense rows reject candidates sooner. This does not affect selection order.
    rows.sort(key=lambda r: -len(r[1]))
    step, rem = (1, 0) if align is None else (align[0], align[1] % align[0])
    allowed = sum(1 << x for x in range(rem, width - w + 1, step))
    for y in range(height - h, -1, -1):
        candidates = allowed
        for dy, positions in rows:
            occupied_row = occupied[y + dy]
            if occupied_row:
                for dx in positions:
                    candidates &= ~(occupied_row >> dx)
                    if not candidates: break
            if not candidates: break
        if candidates:
            return (candidates & -candidates).bit_length() - 1, y
    return None
