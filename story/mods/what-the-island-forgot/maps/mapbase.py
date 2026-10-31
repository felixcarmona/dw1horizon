"""Shared bits of the map recipes: where the player's extracted disc is, a base map scrubbed of everything that is not
structure (sprite pixels, instances, placed Digimon, exits), the camera, pixel <-> world, the tile loop."""
import contextlib, io, math, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dwmap  # noqa: E402
from maps import reach  # noqa: E402

TOOLS = os.path.join(ROOT, 'tools')
MOD = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def extracted(name):
    """extracted/MAP/MAPn/NAME (no extension): the player's own map files."""
    base = os.path.join(ROOT, 'extracted', 'MAP')
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d, name + '.MAP')
        if os.path.isfile(p):
            return p[:-4]
    sys.exit(f'{name}.MAP is not in extracted/MAP (extract the disc first)')


def base_map(name, distance=None, pitch=None):
    """A map of the disc as the structure of a new one: its sprite pixels zeroed, instances hidden, Digimon and exits
    cleared, and, if given, the camera at `distance` from the origin looking `pitch` degrees down (yaw 0)."""
    import struct
    m = dwmap.MapFile(open(extracted(name) + '.MAP', 'rb').read())
    tims = []
    for raw in m.tims:
        raw = bytearray(raw); clut_len = struct.unpack_from('<I', raw, 8)[0]; p = 8 + clut_len + 12
        raw[p:] = bytes(len(raw) - p); tims.append(bytes(raw))
    m.tims = tims
    for inst in m.instances:
        inst['flag'] = 1; inst['frames'] = [-1] * 8
    del m.digimon[:]; m.digimon_count = 0
    for w in m.warps:
        w.update({'x': 0, 'y': 0, 'z': 0, 'rotation': 0, 'targetMap': -1, 'targetExit': -1})   # y too: MAYO04B's warps sit at y 2600 and a player who arrives there floats; a battle then puts the partner 2600 above the enemy and never ends (2026-10-21)
    m.collision = [0x80] * 10000
    m.regionA, m.regionB = [5, -1, -1, -1], [-1, -1, -1, -1]   # the header's 'partner regions' (compared with the partner's favoured region) as GIAS04
                                                              # has them: with MAYO04B's ([8,-1,-1,-1]) the SECOND battle on a screen crashed the game
                                                              # (CPU at 0x68/0x1910), with these two battles run fine (2026-10-21, tested on 314)
    if distance is not None:
        m.camera.update({'vpx': 0, 'vpy': int(-distance * math.sin(math.radians(pitch)) / 2),
                         'vpz': int(-distance * math.cos(math.radians(pitch)) / 2), 'vrx': 0, 'vry': 0, 'vrz': 0})
    return m


def import_png(base_name, png, out_tfs, new_palette=True):
    """The background: our PNG as a TFS with the tile layout of the base map (a new palette: every pixel is ours).
    dwmap.py import-png, called in this process (tools/derive runs the recipes in one process)."""
    e = extracted(base_name)
    dwmap.import_png(e + '.MAP', e + '.TFS', png, out_tfs, new_palette)


def bg(argv):
    """`dwmap.py bg ARGV...` (a retouch of the player's background, the palette kept) in this process; its report is
    kept quiet as when it ran as a command, and shown only when it fails."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            dwmap.bg_main([str(a) for a in argv])
    except SystemExit as e:
        if e.code not in (None, 0): sys.exit(buf.getvalue() + str(e.code))


class Cam:
    """pixel <-> world on the ground plane of a map's camera."""
    def __init__(self, m):
        self.m = m; self.basis = dwmap.camera_basis(m)
        self.W, self.H = m.width * 128, m.height * 128

    def world(self, u, v):
        m = self.m; vp, bx, by, bz = self.basis
        cx = (u - m.width * 64) / m.projection; cy = (v - m.height * 64) / m.projection
        d = [bx[i] * cx + by[i] * cy + bz[i] for i in range(3)]; t = -vp[1] / d[1]
        return int(round(vp[0] + t * d[0])), int(round(vp[2] + t * d[2]))

    def pixel(self, x, z):
        p = dwmap.project(self.m, self.basis, (x, 0, z))
        return (int(p[0]), int(p[1])) if p else None

    def rotation(self, a, b):
        """heading from world a towards world b: 0 = +Z, 1024 = +X."""
        return int(round(math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) / 360 * 4096)) % 4096

    def arrival_rotation(self, a, b):
        """Engine heading towards b: 0 = -Z, 1024 = -X (map.c/_atan)."""
        return (self.rotation(a, b) + 2048) % 4096

    def tiles(self):
        """every tile with its centre's pixel: (tx, tz, u, v) or u, v None when off screen."""
        for tz in range(100):
            for tx in range(100):
                wx, wz = (tx - 50) * 100 + 50, (49 - tz) * 100 + 50
                p = self.pixel(wx, wz)
                yield tx, tz, (p[0] if p else None), (p[1] if p else None)


def reachable(m):
    return reach.from_spawn_coordinates(m)


def check_arrivals(m, name=''):
    return reach.check_recipe_arrivals(m, name)


def inside(poly, u, v):
    """is pixel (u, v) inside the polygon (even-odd rule)?"""
    hit = False; n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > v) != (y1 > v) and u < x0 + (v - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def trim_exit(m, warp, spawn, face, inset=200):
    """Trim the approach side of an exit by two tiles, retaining a two-row strip.

    Work on the existing trigger mask, preserving hand-tuned floors and mouths.
    Narrow exits already only two rows deep keep that usable depth.
    """
    points = [(i, i % 100 * 100 - 4950, 4950 - i // 100 * 100)
              for i, tile in enumerate(m.collision) if tile == 110 + warp]
    if not points:
        raise ValueError(f'warp {warp} has no exit tiles')
    xs = [x for _, x, _ in points]; zs = [z for _, _, z in points]
    # Face points can lead diagonally across the room. Trim the bounding edge
    # nearest the arrival, so the closest trigger retreats too (e.g. the ladder).
    gap, dx, dz = max((min(xs) - spawn[0], -1, 0), (spawn[0] - max(xs), 1, 0),
                      (min(zs) - spawn[1], 0, -1), (spawn[1] - max(zs), 0, 1))
    if gap <= 0:                                        # an irregular mouth surrounds the arrival's bounding box
        dx, dz = face[0] - spawn[0], face[1] - spawn[1]
        length = math.hypot(dx, dz)
        if not length:
            raise ValueError('exit arrival must face away from its mouth')
        dx, dz = dx / length, dz / length
    tiles = [(i, x * dx + z * dz) for i, x, z in points]
    limit = max(min(v for _, v in tiles) + 100, max(v for _, v in tiles) - inset)
    for i, v in tiles:
        if v > limit + 1e-6:
            m.collision[i] = 0
