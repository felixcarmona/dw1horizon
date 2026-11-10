"""Awaited tamer walks must aim far enough inside a tile: the engine's arrival test is the tile, not the point.

`walk(tamer, x, z)` / `run(...)` followed by `await tamer` (`tamer.walk(x, z)` in Python, or `wait=False` then
`tamer.arrived()`) ends only on a tick where the tamer stands on the same 100-unit tile as (x, z)
(tickEntityWalkTo, decomp/src/main/tamer.c; getModelTile, map_collision.c). Each tick the tamer turns to the point and
moves a fixed step: 20 units walking, 50 running (docs/reference/motion.md). Near the point it overshoots back and
forth by up to a step; a point closer than half a step to a tile edge can make every one of those positions fall
outside the tile, and the tamer turns in place forever (the Birdra Transport steps in File City did, from the top of
the steps). A point at least half a step plus one unit inside every edge always lands one of them inside. The tile's
centre is the usual fix: the tamer still stops on the same tile, where it enters it.

`await narrator` / `await all` (WAIT_FOR_ENTITY 255) waits for every scripted movement, the tamer's too.

The original game has such targets: generating story/base proves its lifted code by compiling it, under `off()`.
"""
import contextlib

STEP = {'walk': 20, 'run': 50}
CHECK = [True]


@contextlib.contextmanager
def off():
    """No check inside: compiles that prove lifted original code against the disc (lift.verify, readable.check_file)."""
    CHECK.append(False)
    try: yield
    finally: CHECK.pop()


def _tile(v, axis):
    """getModelTile on one axis (0: x, 1: z): C division truncates, so the tiles next to 0 are 99 wide."""
    if axis == 0: return int(v / 100) + 50 - (v < 0)
    return 50 - int(v / 100) - (v > 0)


def tile_span(v, axis):
    """The inclusive integer range of the tile holding v on one axis."""
    k = _tile(v, axis); lo = hi = v
    while _tile(lo - 1, axis) == k: lo -= 1
    while _tile(hi + 1, axis) == k: hi += 1
    return lo, hi


def margin(x, z):
    """Units from (x, z) to the nearest edge of its tile, inside it (0: on the tile's last row of units)."""
    (xl, xh), (zl, zh) = tile_span(x, 0), tile_span(z, 1)
    return min(x - xl, xh - x, z - zl, zh - z)


def centre(x, z):
    """The multiple of 50 at the middle of (x, z)'s tile: 49 or more units inside every edge."""
    def mid(lo, hi): return int(round((lo + hi) / 100.0)) * 50
    return mid(*tile_span(x, 0)), mid(*tile_span(z, 1))


def too_close(gait, x, z):
    """None, or why an awaited `gait` ('walk' or 'run') of the tamer to (x, z) can stall."""
    if not CHECK[-1]: return None
    need = STEP[gait] // 2 + 1
    m = margin(x, z)
    if m >= need: return None
    cx, cz = centre(x, z)
    return (f'the tamer {"walks" if gait == "walk" else "runs"} to ({x}, {z}) and the script waits for him, but that point '
            f'is {m} units from the edge of its 100-unit tile: the walk ends only on that tile, and a {gait} step of '
            f'{STEP[gait]} units can overshoot it every tick, turning him in place forever',
            f'aim at least {need} units inside the tile: its centre is ({cx}, {cz}) '
            '(tools/dws/checks/walk_targets.py)')
