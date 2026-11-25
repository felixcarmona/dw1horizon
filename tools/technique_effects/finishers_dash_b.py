"""Finishers written and painted here for the Digimon whose finisher is a charge or a cut at close quarters (keyed by
species id). The attacker stays where it stands: what crosses the field is the blow itself, a claw, a pair of tusks, a
blade of light, and it lands on the target."""
import math

import numpy as np

from tools.technique_effects.finishers import GOLD, ahead, band, disc, flicker
from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, crescent, fbm, glow, grid, iv, polar, ring, \
    segment, star

LION = ['#000000', '#501800', '#c06000', '#ffb020', '#fff0a0', '#ffffff']
IVORY = ['#000000', '#3a2a18', '#a08860', '#e8dcc0', '#ffffff']
DUST = ['#000000', '#2a1c10', '#70583a', '#b8a080', '#e8dcc8']
SAND = ['#000000', '#402808', '#b07820', '#f0d060', '#fffbe0']
ADAMANT = ['#000000', '#0c1c40', '#4070c0', '#b0d8ff', '#ffffff']
AMBER = ['#000000', '#402000', '#c08020', '#fff0c0', '#ffffff']
BEAR = ['#000000', '#081838', '#2858b0', '#80b8ff', '#f0f8ff']
PLUME = ['#000000', '#405070', '#a0c0e0', '#ffffff']
TEAL = ['#000000', '#003838', '#10a090', '#70f0d0', '#f0fff8']
JUNGLE = ['#000000', '#0a3008', '#40a020', '#c0f040', '#ffffd0']
EMBERSTEEL = ['#000000', '#502000', '#e07010', '#ffd060', '#ffffff']
DEVA = ['#000000', '#30103a', '#9030a0', '#f090e0', '#fff0ff']
STEEL = ['#000000', '#202838', '#7080a0', '#d0e0f8', '#ffffff']
RAGE = ['#000000', '#400000', '#c01010', '#ff7040', '#ffe0c0']
LILAC = ['#000000', '#201040', '#7060c0', '#d0c8ff', '#ffffff']
INDIGO = ['#000000', '#0a0830', '#3030b0', '#80a0ff', '#f0f8ff']
BLOODRED = ['#000000', '#400008', '#c00818', '#ff5040', '#ffd0c0']
MARBLE = ['#000000', '#303848', '#90a0c0', '#e8f0ff', '#ffffff']
FILTH = ['#000000', '#2a2008', '#6a6a10', '#b0c030', '#f0ff90']
SHELL = ['#1a0c04', '#4a2810', '#8a5020', '#c89050']
KENDO = ['#000000', '#601800', '#e04000', '#ffb020', '#fff0a0', '#ffffff']
BAMBOO = ['#201000', '#806020', '#d0b060', '#fff0c0']
FURY = ['#000000', '#300008', '#a00018', '#ff3838', '#ffd0b0']
MOONSTEEL = ['#000000', '#0c2028', '#307080', '#a0e0e0', '#ffffff']
OMNI = ['#000000', '#102060', '#3070f0', '#a0d8ff', '#ffffff']
GREYFIRE = ['#000000', '#602000', '#f07010', '#ffc850', '#fffbe0']


# ----------------------------------------------------------------- paintings
def turned(turn):
    x, y = grid()
    c, s = math.cos(turn), math.sin(turn)
    return (x - 16) * c + (y - 16) * s, -(x - 16) * s + (y - 16) * c


def rakes(turn, count=3, gap=7.0):
    """Parallel claw marks: bowed gashes, thick at the middle and sharp at both ends."""
    u, v = turned(turn)
    lum = np.zeros((32, 32))
    for k in range(count):
        o = (k - (count - 1) / 2) * gap
        w = 2.3 * clip(1 - (np.abs(u) / 14.5) ** 2) ** 0.6
        lum = np.maximum(lum, clip(1.3 - np.abs(v - o - 3.0 * (1 - (u / 14.5) ** 2) + 1.5) / np.maximum(w, 0.2))
                         * (np.abs(u) < 14.5))
    return clip(lum)


def fangs():
    """Two fangs pointing down, side by side."""
    x, y = grid()
    lum = np.zeros((32, 32))
    for cx in (9.5, 22.5):
        w = 5.2 * clip((30 - y) / 27) ** 0.8
        lum = np.maximum(lum, clip(1.25 - np.abs(x - cx) / np.maximum(w, 0.3)) * (y > 3) * (0.65 + 0.35 * (x < cx)))
    return clip(lum)


def mane():
    """A lion's mane seen head-on: a ragged crown of locks round a dark face."""
    r, ang = polar()
    locks = 9.5 + 4.5 * np.abs(np.cos(ang * 5.5)) ** 1.5 + 1.5 * fbm(63)
    return clip((locks - r) / 2.0) * clip((r - 3.5) / 3.0) * (0.6 + 0.5 * fbm(65))


def tusk(flip=False):
    """A mammoth's tusk seen from the front: thick at the root, sweeping down, out and up to a point."""
    lum = np.zeros((32, 32))
    n = 14
    for k in range(n):
        a0, a1 = -0.35 + 3.7 * k / n, -0.35 + 3.7 * (k + 1) / n
        w = 3.8 - 3.0 * k / n
        lum = np.maximum(lum, segment(14 + 11 * math.cos(a0), 12 + 11 * math.sin(a0),
                                      14 + 11 * math.cos(a1), 12 + 11 * math.sin(a1), w))
    lum = clip(lum * 1.6) * (0.7 + 0.4 * fbm(73))
    return lum[:, ::-1] if flip else lum


def rock():
    """A chip of stone: an uneven lump with one lit face."""
    x, y = grid()
    d = np.maximum(np.abs(x - 16) / 8.0 + np.abs(y - 16) / 11.0, np.abs(x - 14) / 9.5)
    return clip((1 - d) * 4) * (0.5 + 0.5 * (x + y < 30))


def cloud(seed):
    r, _ = polar()
    return clip(clip(1 - r / 14) ** 0.8 * (0.35 + 1.0 * fbm(seed)))


def plate():
    """A segment of a scorpion's tail: an armoured band with a bright rim and a ridge."""
    x, y = grid()
    d = np.maximum(np.abs(x - 16) / 11.5, np.abs(y - 16) / 8.0) ** 2 + (np.abs(x - 16) / 13) ** 4
    body = (d < 1) * (0.42 + 0.2 * (y < 15))
    rim = clip(1 - np.abs(1 - d) * 3.5) * (d < 1.15)
    ridge = clip(1 - np.abs(y - 13) / 1.2) * (np.abs(x - 16) < 8) * 0.5
    return clip(np.maximum(body, rim) + ridge)


def stinger():
    """The blade at the tail's end: a hooked sickle, its point down."""
    return clip(crescent(13.5, 12.0, 5.5, -1.1) * 1.4)


def spike():
    """A thrust seen as a streak: a tall thin splinter of light."""
    x, y = grid()
    return clip(1 - np.abs(x - 16) / (3.2 * clip(1 - np.abs(y - 16) / 16) ** 0.7 + 0.01))


def streak():
    """A speed line across the cell."""
    x, y = grid()
    return clip(1 - np.abs(y - 16) / (2.6 * clip(1 - np.abs(x - 16) / 16) ** 0.7 + 0.01))


def needle(turn=0.0):
    """A cut as thin as a hair, from edge to edge."""
    u, v = turned(turn)
    return clip(1 - np.abs(v) / (1.5 * clip(1 - np.abs(u) / 16) ** 0.5 + 0.01))


def tiger():
    """A tiger's face head-on: ears, stripes across the brow and the cheeks, two slanted eyes."""
    x, y = grid()
    r = np.hypot(x - 16, (y - 17.5) / 1.05)
    head = clip((11.5 - r) / 2.0) * 0.72
    ears = np.maximum(clip((4.2 - np.hypot(x - 7, y - 7)) / 1.5), clip((4.2 - np.hypot(x - 25, y - 7)) / 1.5)) * 0.72
    stripes = np.zeros((32, 32))
    for x0, y0, x1, y1 in ((16, 6, 16, 11), (12, 7, 13, 11), (20, 7, 19, 11), (5, 16, 9, 17), (5, 20, 9, 20),
                           (27, 16, 23, 17), (27, 20, 23, 20)):
        stripes = np.maximum(stripes, segment(x0, y0, x1, y1, 1.2))
    eyes = np.maximum(segment(10, 14, 14, 16, 1.4), segment(22, 14, 18, 16, 1.4))
    nose = clip((2.2 - np.hypot(x - 16, y - 21)) / 1.0)
    return clip(np.maximum(head, ears) * (1 - 0.75 * stripes) + eyes + 0.5 * nose)


def hexplate():
    """A six-sided plate of armour: a bright rim and three lit facets."""
    r, ang = polar()
    d = r * np.cos(np.mod(ang, np.pi / 3) - np.pi / 6)
    facet = np.floor(np.mod(ang, 2 * np.pi) / (np.pi / 3)).astype(int) % 2
    return clip((d < 12) * (0.3 + 0.22 * facet) + clip(1 - np.abs(12 - d) / 1.4) * (d < 13.5))


def splinter():
    x, y = grid()
    d = np.abs(x - 16 + 0.5 * (y - 16)) / 4.5 + np.abs(y - 16) / 12.0
    return clip((1 - d) * 3) * (0.55 + 0.45 * (x > 16))


def paw():
    """A bear's paw from below: the pad, four toes and the claws beyond them."""
    x, y = grid()
    pad = clip((1 - ((x - 16) / 8.5) ** 2 - ((y - 22) / 6.5) ** 2) * 3) * 0.6
    lum = pad
    for tx, ty, cx, cy in ((6, 14, 3, 6), (12, 9.5, 11, 1), (20, 9.5, 21, 1), (26, 14, 29, 6)):
        lum = np.maximum(lum, clip((3.4 - np.hypot(x - tx, y - ty)) / 1.2) * 0.6)
        lum = np.maximum(lum, segment(tx + (cx - tx) * 0.35, ty + (cy - ty) * 0.35, cx, cy, 1.5))
    return clip(lum)


def lens(turn=0.0):
    """A blade's flash: a long leaf of light with a white edge all round."""
    u, v = turned(turn)
    w = 4.2 * clip(1 - (np.abs(u) / 15.5) ** 2)
    d = np.abs(v) / np.maximum(w, 0.2)
    return clip((d < 1) * (0.45 + 0.55 * d ** 2) + clip(1 - np.abs(v) / 1.0) * (np.abs(u) < 14))


def feather():
    """A feather: a leaf with a spine and barbs."""
    u, v = turned(0.6)
    body = clip(1.2 - (u / 4.2) ** 2 - (v / 13.5) ** 2) * (0.62 + 0.3 * np.sin(v * 2.4 + np.abs(u)))
    spine = clip(1 - np.abs(u) / 0.8) * (np.abs(v) < 14)
    return clip(np.maximum(body, 0.9 * spine * (body > 0)))


def whirl(turn):
    """A whirlwind seen down its axis: three arms winding into an eye."""
    r, ang = polar()
    arms = clip(np.cos(3 * (ang + turn) - r * 0.55)) ** 1.5
    return clip(arms * clip(1 - r / 15.5) ** 0.5 * clip(r / 3.0) + 0.5 * clip(1 - np.abs(r - 14) / 1.5) * arms)


def windarc():
    r, ang = polar()
    return clip(clip(1 - np.abs(r - 11.5) / 1.8) * clip(np.cos(ang + 0.8) * 1.6))


def speck():
    r, _ = polar()
    return clip((3.5 - r) / 1.5)


def axe(flip=False):
    """An axe blade: a broad bearded crescent with a bright edge, on a stub of haft."""
    x, y = grid()
    outer = np.hypot(x - 9, y - 16)
    inner = np.hypot(x + 3, y - 16)
    blade = (outer < 14) & (inner > 14) & (np.abs(y - 16) < 13.5)
    edge = clip(1 - np.abs(outer - 13) / 1.6) * blade
    haft = (np.abs(x - 9.5) < 1.6) & (np.abs(y - 16) < 15)
    lum = clip(blade * 0.5 + edge + haft * 0.4)
    return lum[:, ::-1] if flip else lum


def greatsword():
    """A knight's sword, point down: pommel, grip, a broad guard and a fullered blade."""
    x, y = grid()
    w = np.minimum(3.6, 3.6 * clip((31.5 - y) / 5.0))
    blade = (np.abs(x - 16) < w) & (y > 9)
    edge = blade & (np.abs(x - 16) > w - 1.2)
    fuller = blade & (np.abs(x - 16) < 0.8) & (y < 26)
    guard = (np.abs(y - 8.5) < 1.6) & (np.abs(x - 16) < 9.5)
    grip = (np.abs(x - 16) < 1.4) & (y > 2) & (y < 8)
    pommel = np.hypot(x - 16, y - 2.2) < 2.2
    return clip(blade * 0.62 + edge * 0.4 - fuller * 0.25 + guard * 0.95 + grip * 0.45 + pommel * 0.8)


def cleft():
    """The wake of a blow from above: a tall wedge, wide at the foot."""
    x, y = grid()
    w = 1.0 + 6.5 * clip(y / 32.0) ** 1.6
    return clip(1.2 - np.abs(x - 16) / w) * clip(y / 5.0) * (0.75 + 0.35 * fbm(113))


def pinwheel(turn):
    """Three sickle blades round a hub."""
    x, y = grid()
    lum = clip((2.6 - np.hypot(x - 16, y - 16)) / 1.0)
    for k in range(3):
        a = turn + 2 * math.pi * k / 3
        cx, cy = 16 + 5.5 * math.cos(a), 16 + 5.5 * math.sin(a)
        d, ang = np.hypot(x - cx, y - cy), np.arctan2(y - cy, x - cx)
        lum = np.maximum(lum, clip(1 - np.abs(d - 8.0) / 2.0) * clip(np.cos(ang - a - 0.9) * 1.6))
    return clip(lum * 1.3)


def fleck():
    return clip(crescent(8.0, 7.0, 3.0, 0.5) * 1.5)


def wisp(seed):
    """A ghost light: a flame that curls as it climbs."""
    x, y = grid()
    t = clip((30 - y) / 28)
    cx = 16 + 4.0 * np.sin(t * 4.5 + seed) * t
    w = 6.0 * np.sin(np.pi * clip(t * 0.95 + 0.05)) ** 0.7 * (1 - 0.5 * t)
    return clip(1.2 - np.abs(x - cx) / np.maximum(w, 0.3)) * (y < 30) * (y > 2) * (0.5 + 0.7 * fbm(seed))


def diver():
    """A winged shape stooping: two swept wings and a body, head down."""
    x, y = grid()
    wings = np.maximum(segment(16, 27, 3, 5, 2.6), segment(16, 27, 29, 5, 2.6))
    web = (np.abs(x - 16) < (27 - y) * 0.6) & (y > 7 + np.abs(x - 16) * 0.55) & (y < 27)
    body = segment(16, 9, 16, 30, 2.8)
    return clip(np.maximum(np.maximum(wings, body), web * 0.42))


def upstreak():
    return streak().T


def roach(phase):
    """A cockroach from above: head, a seamed shell, six legs and two feelers."""
    x, y = grid()
    shell = clip((1 - ((x - 16) / 5.5) ** 2 - ((y - 18) / 9.0) ** 2) * 3) * 0.8
    seam = clip(1 - np.abs(x - 16) / 0.8) * (y > 11) * 0.4
    head = clip((3.4 - np.hypot(x - 16, y - 7.5)) / 1.2) * 0.6
    lum = np.maximum(shell - seam * (shell > 0), head)
    for s in (-1, 1):
        lum = np.maximum(lum, 0.7 * segment(16 + s, 5, 16 + s * (8 - phase), 0.5, 0.9))
        for ly, ty in ((13, 9 + phase), (18, 18 - phase), (23, 27 + phase * 0.5)):
            lum = np.maximum(lum, 0.7 * segment(16 + s * 4.5, ly, 16 + s * 12.5, ty, 1.0))
    return clip(lum)


def splat(seed):
    """A gob of muck: a ragged blob with drips."""
    r, ang = polar()
    edge = 6.0 + 7.0 * fbm(seed)
    lum = clip((edge - r) / 1.5)
    x, y = grid()
    for dx, dy, rad in ((-9, 8, 2.4), (8, 10, 2.0), (10, -8, 2.2), (-6, -11, 1.8)):
        lum = np.maximum(lum, clip((rad - np.hypot(x - 16 - dx, y - 16 - dy)) / 1.0))
    return lum * (0.6 + 0.4 * fbm(seed + 3))


def fishbone():
    lum = segment(7, 16, 26, 16, 1.2)
    for k in range(4):
        lum = np.maximum(lum, segment(11 + 4 * k, 10 + k, 11 + 4 * k, 22 - k, 1.0))
    lum = np.maximum(lum, clip((4.0 - np.hypot(grid()[0] - 6, grid()[1] - 16)) / 1.2))
    return clip(np.maximum(lum, np.maximum(segment(26, 16, 30, 11, 1.1), segment(26, 16, 30, 21, 1.1))))


def shinai():
    """A bamboo sword, tip up: four slats bound at three places, a round guard and a long grip."""
    x, y = grid()
    stick = (np.abs(x - 16) < 2.2) & (y > 1) & (y < 31)
    bind = stick & ((np.abs(y - 3) < 1.0) | (np.abs(y - 10) < 0.8) | (np.abs(y - 17) < 0.8))
    guard = (np.abs(y - 23) < 1.3) & (np.abs(x - 16) < 5.0)
    grip = stick & (y > 24)
    return np.where(guard, 1.0, np.where(bind, 0.3, np.where(grip, 0.5, stick * 0.8)))


def blaze(seed):
    """A flame with a forked top."""
    x, y = grid()
    t = clip((31 - y) / 29)
    w = np.maximum(7.5 * (1 - t) ** 0.7, 0.3)
    left = clip(1.2 - np.abs(x - (16 - 5.5 * t ** 1.3)) / w)
    right = clip(1.2 - np.abs(x - (16 + 4.0 * t)) / (w * 0.8)) * (t < 0.8)
    return clip(np.maximum(left, right)) * (y < 31) * (0.45 + 0.75 * fbm(seed)) * (0.5 + 0.6 * (1 - t))


def scribble(seed):
    """A furious scrawl: a line that goes everywhere."""
    r = np.random.default_rng(seed)
    pts = [(2 + 28 * r.random(), 3 + 26 * r.random()) for _ in range(9)]
    pts[0], pts[-1] = (0.5, 16), (31.5, 16)
    lum = np.zeros((32, 32))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        lum = np.maximum(lum, segment(x0, y0, x1, y1, 1.6))
    return clip(lum * 1.3)


def sliteye():
    """A glaring eye: an almond of light with a slit of dark."""
    x, y = grid()
    w = 5.5 * clip(1 - ((x - 16) / 14.0) ** 2)
    lum = clip(1.3 - np.abs(y - 16 + 0.25 * (x - 16)) / np.maximum(w, 0.2))
    return clip(lum * (1 - 0.85 * clip(1.6 - np.abs(x - 16) / 1.2)))


def jag(seed):
    """A burst with no two spikes alike."""
    r, ang = polar()
    rng = np.random.default_rng(seed)
    edge = 4.0 + sum(rng.uniform(2, 5) * np.abs(np.cos((ang + rng.uniform(0, 6)) * k)) ** 6 for k in (2.5, 3.5, 4.5))
    return clip(1 - r / edge) ** 0.6


def greatblade():
    """A sword as long as a horse, lying along the cell: a dark flat, a bright edge, a point at the far end."""
    x, y = grid()
    w = np.minimum(6.0, 6.0 * clip((31.5 - x) / 9.0))
    inside = (np.abs(y - 16) < w)
    edge = inside & ((y - 16) > w - 2.2)
    back = inside & ((y - 16) < -w + 1.0)
    return clip(inside * 0.7 + edge * 0.5 + back * 0.3) * (0.85 + 0.25 * fbm(153))


def lightblade():
    """A blade of light: a broad band that narrows to a point at the far end."""
    x, y = grid()
    w = np.minimum(11.0, 11.0 * clip((32 - x) / 8.0))
    return clip(1 - np.abs(y - 16) / np.maximum(w, 0.2)) ** 0.7 * (0.85 + 0.25 * fbm(163))


def glyphs(seed):
    """A line of written signs: lit and unlit squares in a band."""
    r = np.random.default_rng(seed)
    lum = np.zeros((32, 32))
    for j in range(2):
        for k in range(6):
            if r.random() < 0.62:
                lum[9 + 7 * j:15 + 7 * j, 2 + 5 * k:6 + 5 * k] = 1.0
                if r.random() < 0.4:
                    lum[11 + 7 * j:13 + 7 * j, 3 + 5 * k:5 + 5 * k] = 0.3
    return lum


def bit():
    x, y = grid()
    d = np.maximum(np.abs(x - 16), np.abs(y - 16))
    return clip((d < 6) * 0.35 + ((d < 6) & (d > 3.6)) * 0.65)


# ----------------------------------------------------------------- shared pieces
class Lay:
    """The line of the attack on the ground: `fwd`, 100 long, from the caster to the target, `side` across it and
    `span`, the distance between them. The label `lay` works them out."""

    def __init__(self, fx):
        self.fx = fx
        self.fwd, self.side, self.span = fx.vec(), fx.vec(), fx.var()

    def code(self):
        fx, fwd, side = self.fx, self.fwd, self.side
        ok = fx.label()
        fx.label('lay')
        fx.vcopy(fwd, fx.TGT); fx.vsub(fwd, fx.SRC); fx.set(at(fwd, 1), 0)
        fx.vlen(self.span, fwd); fx.br(self.span, '>', 0, ok); fx.set(self.span, 1)
        fx.label(ok)
        fx.vmul(fwd, 100); fx.vdiv(fwd, self.span)
        fx.set(at(side, 0), at(fwd, 2)); fx.set(at(side, 1), 0); fx.lin(at(side, 2), at(fwd, 0), -1)
        fx.ret()


def moved(fx, out, base, vec, k, up=0):
    """out = base + vec * k / 100, lifted by `up` (out is not TV)."""
    fx.vcopy(fx.TV, vec); fx.vmul(fx.TV, k); fx.vdiv(fx.TV, 100)
    if out != base:
        fx.vcopy(out, base)
    fx.vadd(out, fx.TV)
    if up:
        fx.sub_(at(out, 1), up)


def clamp(fx, v, lo, hi):
    a, b = fx.label(), fx.label()
    fx.br(v, '>=', lo, a); fx.set(v, lo)
    fx.label(a)
    fx.br(v, '<=', hi, b); fx.set(v, hi)
    fx.label(b)


def stand(fx, name, count=1, fields=0):
    """Open the routine `name`: an instance that stands at AT, drawn by name_render."""
    pool = fx.pool(name, count, fields)
    fx.begin(name, pool, name + '_render', inherit=False)
    fx.vcopy(POS, fx.AT)
    return pool


# ----------------------------------------------------------------- SaberLeomon
def howling_crusher():
    """SaberLeomon roars, and the roar leaves it as a lion's head of amber light that bounds across the ground in one
    leap, fangs first; where it lands three claw marks open one after another."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(LION)
    fx.paint(0, rakes(0.5)); fx.paint(1, rakes(-0.6)); fx.paint(2, fangs()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, ring(13, 2.0)); fx.paint(6, cloud(61)); fx.paint(7, mane())
    tint, amber = fx.colour(128, 128, 128), fx.colour(128, 80, 24)
    fx.particle('roar', 3, 7, 5, (128, 100, 50), 120, grow=80, fade=True)
    fx.particle('trail', 12, 6, 7, (128, 80, 20), 420, grow=-50, fade=True)
    fx.particle('rake1', 1, 7, 0, (128, 128, 128), None, grow=40, fade=True)
    fx.particle('rake2', 1, 7, 1, (128, 128, 128), None, grow=45, fade=True)
    fx.particle('rake3', 1, 9, 0, (128, 128, 128), None, grow=60, fade=True, rot=75)
    fx.particle('dust', 8, 12, 6, (70, 50, 30), (160, 240), grow=14, lift=8, spread=200, fade=True)
    fx.particle('spark', 18, 11, 4, (128, 110, 60), (80, 150), grow=-8, speed=75, lift=30, gravity=7, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(2, 'again'); fx.when(5, 'leap')
    fx.when(14, 'second'); fx.when(16, 'third'); fx.end(17)
    fx.label('begin'); fx.emit('roar', fx.CHEST); fx.sound(-55); fx.ret()
    fx.label('again'); fx.emit('roar', fx.CHEST); fx.ret()
    fx.label('leap')
    fx.sound(3); fx.aim(); fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('pounce'); fx.ret()
    fx.travel('pounce', 1, 7, 'pounce_render', 'pounce_arrive', every='pounce_trail')
    fx.label('pounce_at')                   # TV2: where the head is on the arc of its leap
    fx.lin(fx.T3, FRAME, 292); fx.sin(fx.T2, fx.T3, 420)
    fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), fx.T2); fx.ret()
    fx.label('pounce_trail'); fx.call('pounce_at'); fx.emit('trail', fx.TV2); fx.ret()
    fx.label('pounce_render')
    fx.call('pounce_at')
    fx.sprite(fx.TV2, amber, 700, cell=3); fx.lin(fx.T3, FRAME, 25)
    fx.sprite(fx.TV2, tint, 560, cell=7, rot=fx.T3); fx.sprite(fx.TV2, tint, 340, cell=2); fx.ret()
    fx.label('pounce_arrive')
    fx.sound(16); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 560)
    fx.emit('rake1', fx.TCHEST); fx.emit('spark', times=6); fx.emit('dust', fx.TGT, 3); fx.ret()
    fx.label('second')
    fx.sound(16); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 600)
    fx.emit('rake2', fx.TCHEST); fx.emit('spark', times=5); fx.ret()
    fx.label('third')
    fx.sound(7); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 700)
    fx.emit('rake3', fx.TCHEST); fx.emit('roar'); fx.emit('spark', times=7); fx.ret()
    return fx


# ----------------------------------------------------------------- Mammothmon
def tusk_crusher():
    """Mammothmon stamps twice, raising dust, and a pair of great ivory tusks ploughs along the ground to the target
    in a cloud; they gore upwards through it and stones fly."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(IVORY); fx.palette(DUST)
    fx.paint(0, tusk()); fx.paint(1, tusk(True)); fx.paint(2, cloud(71)); fx.paint(3, cloud(77))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, rock()); fx.paint(6, ring(13, 2.2))
    tint, soft = fx.colour(128, 128, 128), fx.colour(90, 80, 60)
    lay = Lay(fx)
    fx.particle('stomp', 4, 9, 6, (110, 100, 80), 200, grow=70, fade=True, sy=6)
    fx.particle('dust', 18, 10, 2, (110, 100, 80), (200, 300), grow=22, lift=10, spread=160, fade=True, clut=1)
    fx.particle('dust2', 18, 10, 3, (110, 100, 80), (200, 300), grow=22, lift=10, spread=160, fade=True, clut=1)
    fx.particle('gore1', 1, 9, 0, (128, 128, 128), 660, grow=30, flat=((0, 0), (-75, -75), (0, 0)), fade=True)
    fx.particle('gore2', 1, 9, 1, (128, 128, 128), 660, grow=30, flat=((0, 0), (-75, -75), (0, 0)), fade=True)
    fx.particle('stone', 18, 14, 5, (128, 120, 100), (90, 170), grow=-5, speed=80, lift=70, gravity=10, spread=200,
                spin=25)
    fx.particle('flash', 2, 6, 4, (128, 120, 100), 300, grow=110, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(3, 'again'); fx.when(6, 'charge'); fx.end(7)
    fx.label('begin'); fx.emit('stomp', fx.SRC); fx.emit('dust', times=3); fx.sound(-55); fx.ret()
    fx.label('again'); fx.emit('stomp', fx.SRC); fx.emit('dust2', times=3); fx.sound(20); fx.ret()
    fx.label('charge')
    fx.sound(13); fx.aim(); fx.call('lay')
    moved(fx, fx.AT, fx.SRC, lay.fwd, 80); fx.vcopy(fx.DEST, fx.TGT); fx.call('ram'); fx.ret()
    lay.code()
    fx.travel('ram', 1, 7, 'ram_render', 'ram_arrive', every='ram_trail')
    fx.label('ram_trail'); fx.emit('dust', POS); fx.emit('dust2'); fx.ret()
    fx.label('ram_render')
    fx.lin(fx.T3, at(fx.SSIZE, 1), 4, 60, 10)
    fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), fx.T3); fx.sprite(fx.TV2, soft, 760, cell=4)
    for cell, k in ((0, 190), (1, -190)):
        moved(fx, fx.TV2, POS, lay.side, k); fx.sub_(at(fx.TV2, 1), fx.T3)
        fx.sprite(fx.TV2, tint, 660, cell=cell)
    fx.ret()
    fx.label('ram_arrive')
    fx.sound(15); fx.aim(); fx.hit()
    moved(fx, fx.TV2, fx.TCHEST, lay.side, 150); fx.emit('gore1', fx.TV2)
    moved(fx, fx.TV2, fx.TCHEST, lay.side, -150); fx.emit('gore2', fx.TV2)
    fx.emit('flash', fx.TCHEST); fx.emit('stone', fx.TGT, 14); fx.emit('stomp'); fx.emit('dust', times=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Scorpiomon
def tail_blade():
    """Scorpiomon's tail uncoils over its head segment by segment, the blade at its end held high above the target;
    it stabs straight down, and sand and sparks leap from the thrust."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(SAND)
    fx.paint(0, plate()); fx.paint(1, stinger()); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, cloud(81)); fx.paint(5, spike()); fx.paint(6, ring(13, 2.0))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 100, 40)
    tip, root = fx.vec(), fx.vec()
    links, stab = 8, 8
    fx.particle('pierce', 1, 7, 5, (128, 128, 128), 340, grow=20, sy=56, fade=True)
    fx.particle('sand', 16, 12, 4, (100, 80, 40), (140, 220), grow=12, speed=30, lift=30, gravity=4, spread=120,
                fade=True)
    fx.particle('spark', 14, 10, 3, (128, 120, 70), (80, 150), grow=-8, speed=70, lift=40, gravity=7, spread=60)
    fx.particle('wave', 2, 8, 6, (128, 100, 50), 160, grow=80, fade=True, sy=6)
    fx.label('main'); fx.when(0, 'begin'); fx.end(1)
    fx.label('begin'); fx.vcopy(fx.AT, fx.CHEST); fx.call('tail'); fx.sound(-55); fx.ret()
    stand(fx, 'tail'); fx.ret()
    fx.label('tail_tick')
    fx.life(stab + 10); fx.aim()
    fx.lin(fx.T3, FRAME, -260, 260 * stab); clamp(fx, fx.T3, 0, 480)
    fx.vcopy(tip, fx.TCHEST); fx.sub_(at(tip, 1), fx.T3)
    fx.vcopy(root, fx.CHEST); fx.sub_(at(root, 1), 60)
    fx.after(3, 'tail_whip'); fx.after(stab, 'tail_stab'); fx.ret()
    fx.label('tail_whip'); fx.sound(13); fx.ret()
    fx.label('tail_stab')
    fx.sound(16); fx.hit()
    fx.vcopy(fx.AT, fx.TCHEST); fx.sub_(at(fx.AT, 1), 200); fx.call('pierce')
    fx.emit('spark', fx.TCHEST, 10); fx.emit('sand', fx.TGT, 8); fx.emit('wave'); fx.ret()
    fx.label('tail_render')
    for k in range(1, links + 1):
        skip = fx.label()
        fx.br(FRAME, '<', (k - 1) // 2, skip); fx.br(FRAME, '>', stab + 11 - k, skip)
        fx.vcopy(fx.TV2, tip); fx.vsub(fx.TV2, root); fx.vmul(fx.TV2, k); fx.vdiv(fx.TV2, links); fx.vadd(fx.TV2, root)
        fx.sub_(at(fx.TV2, 1), int(4 * 250 * (k / links) * (1 - k / links)))
        if k < links:
            fx.sprite(fx.TV2, tint, 330 - 10 * k, cell=0)
        else:
            fx.sprite(fx.TV2, soft, 560, cell=2); fx.sprite(fx.TV2, tint, 460, cell=1)
        fx.label(skip)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Baihumon
def kongou():
    """Six plates of adamant close round Baihumon into a shell that rings as it hardens; the shell lets go a white
    tiger's head ringed with plates, which crosses the field in a blink and shatters on the target."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(ADAMANT); fx.palette(AMBER)
    fx.paint(0, tiger()); fx.paint(1, hexplate()); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, splinter()); fx.paint(5, ring(13, 2.0)); fx.paint(6, streak())
    tint, soft = fx.colour(128, 128, 128), fx.colour(50, 90, 128)
    harden, run = 9, 5
    fx.particle('ting', 6, 5, 3, (128, 128, 128), 200, grow=-24, spread=500)
    fx.particle('line', 12, 5, 6, (100, 120, 128), (320, 460), grow=-30, spread=160, fade=True)
    fx.particle('shard', 20, 13, 4, (120, 128, 128), (90, 170), grow=-5, speed=85, lift=40, gravity=8, spread=120,
                spin=30)
    fx.particle('scale', 8, 11, 1, (128, 128, 128), (150, 220), grow=-8, speed=60, lift=50, gravity=9, spread=100,
                spin=18)
    fx.particle('boom', 2, 8, 5, (110, 125, 128), 160, grow=95, fade=True)
    fx.particle('flare', 1, 7, 3, (128, 128, 128), None, grow=70, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(harden, 'launch'); fx.end(harden + 1)
    fx.label('begin'); fx.vcopy(fx.AT, fx.CHEST); fx.call('shell'); fx.sound(-55); fx.ret()
    stand(fx, 'shell'); fx.ret()
    fx.label('shell_tick')
    fx.life(harden); fx.set(fx.T2, FRAME); fx.mod(fx.T2, 3); fx.br(fx.T2, '!=', 0, 'noop')
    fx.sound(34); fx.emit('ting', POS); fx.ret()
    fx.label('shell_render')
    fx.lin(fx.T3, FRAME, -44, 470); fx.lin(fx.T2, fx.T3, 1, 0, 2)
    fx.sprite(POS, soft, 520, cell=2)
    for k in range(6):
        fx.lin(fx.T, FRAME, 180, 683 * k); fx.circle(fx.TV, fx.T, fx.T3, 0); fx.vadd(fx.TV, POS)
        (fx.add if k % 2 else fx.sub_)(at(fx.TV, 1), fx.T2)
        fx.sprite(fx.TV, tint, 230, cell=1)
    fx.ret()
    fx.label('launch')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('charge'); fx.ret()
    fx.travel('charge', 1, run, 'charge_render', 'charge_arrive', every='charge_trail')
    fx.label('charge_trail'); fx.emit('line', POS, 2); fx.emit('shard'); fx.ret()
    fx.label('charge_render')
    fx.sprite(POS, soft, 760, cell=2); fx.sprite(POS, tint, 520, cell=0, clut=1)
    for k in range(3):
        fx.lin(fx.T, FRAME, 620, 1365 * k); fx.circle(fx.TV, fx.T, 300, 0); fx.cos(at(fx.TV, 1), fx.T, 240)
        fx.vadd(fx.TV, POS); fx.sprite(fx.TV, tint, 170, cell=1)
    fx.ret()
    fx.label('charge_arrive')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 620)
    fx.emit('flare', fx.TCHEST); fx.emit('boom'); fx.emit('scale', times=6); fx.emit('shard', times=14); fx.ret()
    return fx


# ----------------------------------------------------------------- Grizzlymon
def maul_attack():
    """A bear's paw of blue light as big as the target swings down on it from above and to one side, leaving four
    gashes; a second set crosses the first."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(BEAR)
    fx.paint(0, paw()); fx.paint(1, rakes(1.35, 4, 6.0)); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, cloud(91)); fx.paint(5, clip(crescent(14.5, 13.5, 4.5, 2.2) * 1.4)); fx.paint(6, ring(13, 2.0))
    fx.paint(7, rakes(-0.25, 4, 6.0))
    tint, soft = fx.colour(128, 128, 128), fx.colour(40, 80, 128)
    lay = Lay(fx)
    fx.particle('gash', 1, 9, 1, (128, 128, 128), None, grow=35, fade=True)
    fx.particle('gash2', 1, 8, 7, (128, 128, 128), None, grow=50, fade=True)
    fx.particle('wake', 6, 5, 5, (70, 100, 128), 560, grow=-30, fade=True)
    fx.particle('dust', 8, 12, 4, (50, 60, 80), (160, 240), grow=14, lift=8, spread=200, fade=True)
    fx.particle('spark', 16, 11, 3, (110, 120, 128), (80, 150), grow=-8, speed=75, lift=30, gravity=7, spread=80)
    fx.particle('thud', 3, 8, 6, (80, 110, 128), 180, grow=85, fade=True, sy=6)
    fx.label('main'); fx.when(0, 'begin'); fx.when(4, 'swat'); fx.when(12, 'rip'); fx.end(13)
    fx.label('begin'); fx.emit('thud', fx.SRC); fx.sound(-55); fx.ret()
    fx.label('swat')
    fx.sound(3); fx.aim(); fx.call('lay')
    moved(fx, fx.AT, fx.TCHEST, lay.side, -340, up=680); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('claw'); fx.ret()
    lay.code()
    fx.travel('claw', 1, 5, 'claw_render', 'claw_arrive', every='claw_trail')
    fx.label('claw_trail'); fx.emit('wake', POS); fx.ret()
    fx.label('claw_render')
    fx.lin(fx.T3, FRAME, 60, 380); fx.lin(fx.T2, fx.T3, 14, 0, 10)
    fx.sprite(POS, soft, fx.T2, cell=2); fx.sprite(POS, tint, fx.T3, cell=0); fx.ret()
    fx.label('claw_arrive')
    fx.sound(16); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 580)
    fx.emit('gash', fx.TCHEST); fx.emit('spark', times=8); fx.emit('thud', fx.TGT); fx.emit('dust', times=4); fx.ret()
    fx.label('rip')
    fx.sound(7); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 640)
    fx.emit('gash2', fx.TCHEST); fx.emit('spark', times=6); fx.ret()
    return fx


# ----------------------------------------------------------------- SlashAngemon
def golden_ripper():
    """Feathers drift from SlashAngemon's wings; five golden blades flash across the target from five sides faster than
    the eye, and a sixth, level and longer than the rest, lands the blow."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(GOLD); fx.palette(PLUME)
    fx.paint(0, lens()); fx.paint(1, feather()); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 1.5, 14, 12))
    fx.paint(4, lens(0.5)); fx.paint(5, needle()); fx.paint(6, lens(-0.75)); fx.paint(7, lens(1.3))
    angles = (4, 6, 7, 4, 6)
    for k, a in enumerate(angles):
        fx.particle(f'cut{k}', 1, 5, a, (128, 128, 128), 640 + 60 * k, grow=70, fade=True)
    fx.particle('ripper', 1, 10, 5, (128, 128, 128), 900, grow=130, fade=True)
    fx.particle('ripper2', 1, 8, 0, (128, 128, 128), 800, grow=70, fade=True)
    fx.particle('plume', 16, 16, 1, (128, 128, 128), (110, 170), flat=((-14, 14), (6, 18), (-14, 14)), spread=360,
                clut=1, spin=8)
    fx.particle('glint', 18, 10, 3, (128, 120, 80), (90, 170), grow=-8, speed=60, lift=20, gravity=4, spread=160)
    fx.particle('halo', 2, 8, 3, (128, 100, 40), 300, grow=110, fade=True)
    fx.particle('shine', 1, 8, 2, (128, 110, 60), None, grow=40, fade=True)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(len(angles)):
        fx.when(4 + 2 * k, f'slice{k}')
    fx.when(15, 'final'); fx.end(16)
    fx.label('begin')
    fx.vcopy(fx.AT, fx.CHEST); fx.sub_(at(fx.AT, 1), 260); fx.call('plume', 6); fx.sound(-55); fx.ret()
    for k in range(len(angles)):
        fx.label(f'slice{k}')
        fx.sound(13); fx.aim(); fx.emit(f'cut{k}', fx.TCHEST); fx.emit('glint', times=2); fx.ret()
    fx.label('final')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 420)
    fx.emit('ripper', fx.TCHEST); fx.emit('ripper2'); fx.emit('halo'); fx.emit('shine'); fx.emit('glint', times=10)
    fx.sub_(at(fx.AT, 1), 200); fx.call('plume', 6); fx.ret()
    return fx


# ----------------------------------------------------------------- GrapLeomon
def cyclone_turbine():
    """The wind gathers round GrapLeomon and leaves as a turbine of teal whirlwinds, one behind another, that bores
    across to the target and stands up there as a twister."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(TEAL)
    fx.paint(0, whirl(0)); fx.paint(1, whirl(np.pi / 3)); fx.paint(2, windarc()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, ring(13, 2.0)); fx.paint(6, speck())
    tint, soft, dim, wash = fx.colour(128, 128, 128), fx.colour(30, 110, 96), fx.colour(70, 110, 100), fx.vec()
    lay = Lay(fx)
    fx.particle('gust', 18, 6, 2, (100, 128, 120), (220, 340), grow=20, speed=40, spread=160, fade=True, spin=40)
    fx.particle('leaf', 20, 12, 6, (110, 128, 120), (50, 90), speed=60, lift=60, gravity=3, spread=200)
    fx.particle('pop', 2, 8, 5, (90, 128, 120), 160, grow=90, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(5, 'kick')
    fx.emit('gust', fx.CHEST)
    fx.end(6)
    fx.label('begin'); fx.emit('gust', fx.CHEST, 3); fx.sound(-55); fx.ret()
    fx.label('kick')
    fx.sound(13); fx.aim(); fx.call('lay'); fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, fx.TCHEST)
    fx.call('drill'); fx.ret()
    lay.code()
    fx.travel('drill', 1, 7, 'drill_render', 'drill_arrive', every='drill_trail')
    fx.label('drill_trail'); fx.emit('gust', POS); fx.ret()
    fx.label('drill_render')
    fx.sprite(POS, soft, 640, cell=3)
    for k in range(4):
        moved(fx, fx.TV2, POS, lay.fwd, -110 * k)
        fx.lin(fx.T3, FRAME, 50, 30 * k)
        fx.sprite(fx.TV2, tint if k == 0 else dim, 480 - 90 * k, cell=k % 2, rot=fx.T3)
    fx.ret()
    fx.label('drill_arrive')
    fx.sound(7); fx.aim(); fx.hit(); fx.vcopy(fx.AT, fx.TGT); fx.call('twister')
    fx.emit('pop', fx.TCHEST); fx.emit('leaf', fx.TGT, 12); fx.ret()
    stand(fx, 'twister'); fx.ret()
    fx.label('twister_tick'); fx.life(11); fx.emit('leaf', POS); fx.ret()
    fx.label('twister_render')
    fx.set(fx.T, 128); fx.br(FRAME, '<=', 6, 'twister_draw'); fx.lin(fx.T, FRAME, -24, 128 + 24 * 6)
    fx.label('twister_draw')
    fx.vset(wash, fx.T, fx.T, fx.T)
    for k in range(6):
        fx.vcopy(fx.TV2, POS)
        fx.lin(fx.T, FRAME, 8 * k, 110 * k + 40); fx.sub_(at(fx.TV2, 1), fx.T)
        fx.lin(fx.T3, FRAME, 400, 500 * k); fx.sin(fx.T, fx.T3, 40 + 14 * k); fx.add(at(fx.TV2, 0), fx.T)
        fx.lin(fx.T2, FRAME, 12, 240 + 80 * k); fx.lin(fx.T3, FRAME, 60, 40 * k)
        fx.sprite(fx.TV2, wash, fx.T2, cell=k % 2, rot=fx.T3)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Dinohyumon
def lizard_dance():
    """Four times a green blur darts through the target from a different side, kicking up dust where it sets off, and
    each time a burning cut is left across it; the fourth is the one that tells."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(JUNGLE); fx.palette(EMBERSTEEL)
    fx.paint(0, clip(crescent(14.5, 14.0, 3.2, 0.6) * 1.4)); fx.paint(1, clip(crescent(14.5, 14.0, 3.2, 2.5) * 1.4))
    fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6)); fx.paint(4, cloud(101)); fx.paint(5, ring(13, 2.0))
    fx.paint(6, clip(crescent(14.5, 14.0, 3.2, -1.0) * 1.4)); fx.paint(7, clip(crescent(14.5, 14.0, 3.2, 4.2) * 1.4))
    drift, spot, beat = fx.vec(), fx.vec(), fx.var()
    beats, gap = 4, 3
    for k, a in enumerate((0, 6, 1, 7)):
        fx.particle(f'cut{k}', 1, 6, a, (128, 128, 128), None, grow=40, fade=True, clut=1)
    fx.particle('blur', 4, 5, 2, (50, 128, 30), 460, drift=drift, fade=True, sy=11)
    fx.particle('step', 8, 9, 4, (60, 80, 40), (160, 220), grow=14, lift=6, fade=True)
    fx.particle('spark', 18, 11, 3, (128, 120, 70), (80, 150), grow=-8, speed=75, lift=30, gravity=7, spread=80,
                clut=1)
    fx.particle('final', 1, 9, 3, (128, 128, 128), None, grow=80, fade=True)
    fx.particle('halo', 2, 8, 5, (90, 128, 50), 160, grow=90, fade=True)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(beats):
        fx.when(3 + gap * k, 'beat')
    fx.end(3 + gap * (beats - 1) + 1)
    fx.label('begin'); fx.set(beat, 0); fx.sound(-55); fx.ret()
    fx.label('beat')
    fx.sound(13); fx.aim()
    fx.lin(fx.T3, beat, 1324, 512); fx.circle(spot, fx.T3, 340, 0)
    fx.vcopy(drift, spot); fx.vmul(drift, -2); fx.vdiv(drift, 5)
    fx.vadd(spot, fx.TGT); fx.emit('step', spot)
    fx.set(at(fx.AT, 1), at(fx.TCHEST, 1)); fx.call('blur')
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 500)
    for k in range(beats):
        nxt = fx.label()
        fx.br(beat, '!=', k, nxt); fx.emit(f'cut{k}', fx.TCHEST)
        fx.label(nxt)
    fx.emit('spark', fx.TCHEST, 4)
    fx.add(beat, 1); fx.br(beat, '<', beats, 'noop')
    fx.sound(15); fx.hit(); fx.add(fx.SZ, 200); fx.emit('final'); fx.emit('halo'); fx.emit('spark', times=8); fx.ret()
    return fx


# ----------------------------------------------------------------- Antylamon
def bunny_blades():
    """Antylamon's arms become axes: one great blade swings down across the target from the right, a second from the
    left, each leaving a heavy wake; the second is the one that cleaves."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(DEVA); fx.palette(STEEL)
    fx.paint(0, axe()); fx.paint(1, axe(True)); fx.paint(2, clip(crescent(14.5, 13.5, 5.0, 0.5) * 1.4))
    fx.paint(3, clip(crescent(14.5, 13.5, 5.0, np.pi - 0.5) * 1.4)); fx.paint(4, glow(15, 1.2))
    fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.0)); fx.paint(7, rock())
    tint, soft = fx.colour(128, 128, 128), fx.colour(110, 40, 128)
    lay = Lay(fx)
    hand = fx.var()
    fx.particle('wake1', 1, 8, 2, (128, 128, 128), None, grow=50, fade=True)
    fx.particle('wake2', 1, 8, 3, (128, 128, 128), None, grow=50, fade=True)
    fx.particle('spark', 18, 11, 5, (128, 128, 128), (80, 150), grow=-8, speed=75, lift=30, gravity=7, spread=80,
                clut=1)
    fx.particle('shock', 2, 8, 6, (128, 70, 128), 160, grow=90, fade=True)
    fx.particle('chip', 12, 13, 7, (110, 90, 110), (80, 140), grow=-4, speed=60, lift=70, gravity=10, spread=160,
                spin=25)
    fx.label('main'); fx.when(0, 'begin'); fx.when(3, 'first'); fx.when(10, 'second'); fx.end(11)
    fx.label('begin'); fx.sound(-55); fx.ret()
    fx.label('first'); fx.set(hand, 1); fx.jmp('swing_go')
    fx.label('second'); fx.set(hand, -1)
    fx.label('swing_go'); fx.sound(13); fx.aim(); fx.call('lay'); fx.vcopy(fx.AT, fx.TCHEST); fx.call('swing'); fx.ret()
    lay.code()
    stand(fx, 'swing', 2, 1)
    sgn = iv(FREE)
    fx.set(sgn, hand); fx.ret()
    fx.label('swing_tick')
    fx.life(6); fx.aim(); fx.vcopy(POS, fx.TCHEST); fx.after(4, 'swing_land'); fx.ret()
    fx.label('swing_land')
    fx.sound(16); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 620)
    fx.br(sgn, '<', 0, 'swing_left'); fx.emit('wake1', POS); fx.jmp('swing_both')
    fx.label('swing_left'); fx.emit('wake2', POS); fx.hit()
    fx.label('swing_both'); fx.emit('spark', times=8); fx.emit('shock'); fx.emit('chip', fx.TGT, 5); fx.ret()
    fx.label('swing_render')
    fx.lin(fx.T3, FRAME, -360, 1380); fx.cos(fx.T, fx.T3, 460); fx.mul(fx.T, sgn)
    moved(fx, fx.TV2, POS, lay.side, fx.T); fx.sin(fx.T2, fx.T3, 460); fx.sub_(at(fx.TV2, 1), fx.T2)
    fx.lin(fx.T2, FRAME, 32, -70); fx.mul(fx.T2, sgn)
    fx.sprite(fx.TV2, soft, 780, cell=4)
    fx.br(sgn, '<', 0, 'swing_draw'); fx.sprite(fx.TV2, tint, 640, cell=0, clut=1, rot=fx.T2); fx.ret()
    fx.label('swing_draw'); fx.sprite(fx.TV2, tint, 640, cell=1, clut=1, rot=fx.T2); fx.ret()
    return fx


# ----------------------------------------------------------------- Knightmon
def berserk_sword():
    """Rage burns red round Knightmon while a sword of steel as tall as a house takes shape in the air over the
    target; it hangs there a moment and falls point first, and the ground breaks under it."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(STEEL); fx.palette(RAGE)
    fx.paint(0, greatsword()); fx.paint(1, cleft()); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, rock()); fx.paint(5, ring(13, 2.2)); fx.paint(6, cloud(111))
    rage, wash = fx.colour(128, 50, 40), fx.vec()
    hang, land = 9, 12
    fx.particle('aura', 4, 8, 2, (128, 128, 128), 200, grow=70, fade=True, clut=1)
    fx.particle('cleave', 1, 8, 1, (128, 128, 128), 520, grow=30, sy=52, fade=True)
    fx.particle('wave', 3, 9, 5, (110, 120, 128), 200, grow=100, fade=True, sy=6)
    fx.particle('chip', 18, 14, 4, (120, 124, 128), (90, 170), grow=-5, speed=80, lift=80, gravity=10, spread=200,
                spin=25)
    fx.particle('dust', 8, 12, 6, (60, 64, 72), (200, 280), grow=18, lift=8, spread=260, fade=True)
    fx.particle('glint', 8, 5, 3, (128, 128, 128), 170, grow=-24, spread=260)
    fx.label('main'); fx.when(0, 'begin'); fx.when(2, 'burn'); fx.when(4, 'burn'); fx.when(6, 'burn'); fx.end(7)
    fx.label('begin'); fx.sound(-55); fx.vcopy(fx.AT, fx.TGT); fx.call('blade')
    fx.label('burn'); fx.emit('aura', fx.CHEST); fx.ret()
    stand(fx, 'blade'); fx.ret()
    fx.label('blade_tick')
    fx.life(land + 8); fx.br(FRAME, '>=', hang, 'blade_fall'); fx.aim(); fx.vcopy(POS, fx.TGT)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 3); fx.br(fx.T2, '!=', 1, 'noop')
    fx.vcopy(fx.AT, POS); fx.sub_(at(fx.AT, 1), 1100); fx.call('glint'); fx.ret()
    fx.label('blade_fall'); fx.after(hang, 'blade_drop'); fx.after(land, 'blade_land'); fx.ret()
    fx.label('blade_drop'); fx.sound(13); fx.ret()
    fx.label('blade_land')
    fx.sound(15); fx.aim(); fx.hit()
    fx.vcopy(fx.AT, POS); fx.sub_(at(fx.AT, 1), 700); fx.call('cleave')
    fx.emit('wave', POS); fx.emit('chip', times=14); fx.emit('dust', times=5); fx.ret()
    fx.label('blade_render')
    fx.set(fx.T3, 1100); fx.br(FRAME, '<', hang, 'blade_size')
    fx.lin(fx.T3, FRAME, -160, 1100 + 160 * (hang - 1)); clamp(fx, fx.T3, 640, 1100)
    fx.label('blade_size')
    fx.lin(fx.T2, FRAME, 70, 70); clamp(fx, fx.T2, 0, 420)
    fx.set(fx.T, 128); fx.br(FRAME, '<', land + 4, 'blade_draw'); fx.lin(fx.T, FRAME, -30, 128 + 30 * (land + 3))
    fx.label('blade_draw')
    fx.vset(wash, fx.T, fx.T, fx.T)
    fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), fx.T3)
    fx.br(FRAME, '>=', land, 'blade_steel')
    fx.lin(fx.T, fx.T2, 5, 0, 2); fx.sprite(fx.TV2, rage, fx.T, cell=2, clut=1)
    fx.label('blade_steel')
    fx.lin(fx.T, fx.T2, 3); fx.sprite(fx.TV2, wash, fx.T2, fx.T, cell=0); fx.ret()
    return fx


# ----------------------------------------------------------------- Kyukimon
def blade_twister():
    """The wind whirls up round Kyukimon and throws a wheel of three sickles that spins across the field; where it
    catches somebody it grinds on the spot, throwing cuts in every direction. A target that moves away is missed."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(LILAC)
    fx.paint(0, pinwheel(0)); fx.paint(1, pinwheel(np.pi / 3)); fx.paint(2, glow(15, 1.2)); fx.paint(3, windarc())
    fx.paint(4, star(4, 1.2, 14, 14)); fx.paint(5, ring(13, 2.0)); fx.paint(6, fleck())
    tint, soft = fx.colour(128, 128, 128), fx.colour(70, 60, 128)
    fx.particle('gust', 14, 6, 3, (110, 110, 128), (220, 320), grow=18, spread=200, fade=True, spin=45)
    fx.particle('fleck', 22, 9, 6, (128, 128, 128), (90, 150), speed=70, lift=20, gravity=5, spread=60, spin=40)
    fx.particle('nick', 8, 3, 4, (128, 128, 128), (480, 680), spin=3)
    fx.particle('pop', 2, 8, 5, (110, 100, 128), 160, grow=90, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(6, 'throw')
    fx.emit('gust', fx.CHEST)
    fx.end(7)
    fx.label('begin'); fx.sound(-55); fx.ret()
    fx.label('throw')
    fx.sound(13); fx.aim(); ahead(fx, fx.AT, fx.CHEST, 60); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('saw'); fx.ret()
    fx.shot('saw', 1, 80, 24, 'saw_render', 'saw_arrive', miss='saw_miss', every='saw_trail')
    fx.label('saw_trail'); fx.emit('gust', POS); fx.emit('fleck', POS); fx.ret()
    fx.label('saw_render')
    fx.sprite(POS, soft, 800, cell=2); flicker(fx, POS, tint, 620, (0, 1), every=1); fx.ret()
    fx.label('saw_miss'); fx.emit('fleck', POS, 6); fx.ret()
    fx.label('saw_arrive')
    fx.sound(16); fx.vcopy(fx.AT, POS); fx.call('grind'); fx.emit('pop', POS); fx.emit('fleck', times=6); fx.ret()
    stand(fx, 'grind'); fx.ret()
    fx.label('grind_tick')
    fx.life(7); fx.emit('fleck', POS, 2); fx.emit('nick', POS)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '!=', 0, 'noop'); fx.sound(13); fx.ret()
    fx.label('grind_render')
    fx.lin(fx.T3, FRAME, -24, 680)
    fx.sprite(POS, soft, 800, cell=2); flicker(fx, POS, tint, fx.T3, (0, 1), every=1); fx.ret()
    return fx


# ----------------------------------------------------------------- Musyamon
def ura_sword():
    """Ghost lights climb round Musyamon. One stroke: a white line through the target, there and gone. For a breath
    nothing happens; then the line opens red and blue fire rises all along it."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(INDIGO); fx.palette(BLOODRED)
    fx.paint(0, needle(-0.3)); fx.paint(1, wisp(3)); fx.paint(2, wisp(9)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, ring(13, 2.0)); fx.paint(6, lens(-0.3))
    lay = Lay(fx)
    stroke, open_ = 7, 13
    fx.particle('soul', 12, 10, 1, (90, 110, 128), (160, 240), grow=-8, flat=((-10, 10), (-45, -20), (-10, 10)),
                spread=420)
    fx.particle('soul2', 12, 10, 2, (90, 110, 128), (160, 240), grow=-8, flat=((-10, 10), (-45, -20), (-10, 10)),
                spread=420)
    fx.particle('iai', 1, 3, 6, (128, 128, 128), 1500)
    fx.particle('linger', 1, 8, 0, (80, 90, 128), 1400, fade=True)
    fx.particle('bleed', 1, 10, 6, (128, 128, 128), 800, grow=90, clut=1, fade=True)
    fx.particle('flame', 14, 11, 1, (128, 128, 128), (360, 500), grow=-14, flat=((-12, 12), (-60, -25), (-12, 12)),
                spread=100)
    fx.particle('flame2', 14, 11, 2, (128, 128, 128), (320, 440), grow=-14, flat=((-12, 12), (-60, -25), (-12, 12)),
                spread=100, clut=1)
    fx.particle('spark', 14, 10, 4, (128, 128, 128), (80, 150), grow=-8, speed=70, lift=30, gravity=6, spread=80)
    fx.particle('halo', 2, 8, 5, (128, 128, 128), 160, grow=90, fade=True, clut=1)
    fx.label('main'); fx.when(0, 'begin'); fx.when(stroke, 'stroke'); fx.when(open_, 'open')
    fx.br(fx.NOW, '>', 5, 'main_end'); fx.emit('soul', fx.CHEST); fx.emit('soul2')
    fx.label('main_end'); fx.end(open_ + 1)
    fx.label('begin'); fx.sound(-55); fx.ret()
    fx.label('stroke'); fx.sound(13); fx.aim(); fx.emit('iai', fx.TCHEST); fx.emit('linger'); fx.ret()
    fx.label('open')
    fx.sound(15); fx.aim(); fx.hit(); fx.call('lay')
    fx.emit('bleed', fx.TCHEST); fx.emit('halo')
    for k in (-2, -1, 0, 1, 2):
        moved(fx, fx.TV2, fx.TCHEST, lay.side, 150 * k); fx.add(at(fx.TV2, 1), 45 * k)
        fx.emit('flame', fx.TV2); fx.emit('flame2')
    fx.emit('spark', fx.TCHEST, 8); fx.ret()
    lay.code()
    return fx


# ----------------------------------------------------------------- Gargoylemon
def gargoyle_rush():
    """White streaks shoot up from Gargoylemon into the sky; a winged shape of marble light stoops from high above the
    field onto the target in a rain of feathers, and a golden ring bursts where it strikes."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(MARBLE); fx.palette(GOLD)
    fx.paint(0, diver()); fx.paint(1, feather()); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, upstreak()); fx.paint(5, ring(13, 2.0)); fx.paint(6, cloud(121))
    tint, gold = fx.colour(128, 128, 128), fx.colour(128, 110, 60)
    top = fx.vec()
    fx.particle('rise', 6, 6, 4, (110, 120, 128), 340, flat=((0, 0), (-170, -170), (0, 0)), fade=True, sy=40)
    fx.particle('plume', 20, 14, 1, (128, 128, 128), (110, 170), flat=((-16, 16), (4, 16), (-16, 16)), spread=220,
                spin=10)
    fx.particle('line', 10, 4, 4, (128, 128, 128), (260, 360), fade=True, sy=40, clut=1)
    fx.particle('boom', 3, 8, 5, (128, 128, 128), 160, grow=95, fade=True, clut=1)
    fx.particle('wave', 2, 9, 5, (128, 128, 128), 200, grow=100, fade=True, sy=6, clut=1)
    fx.particle('flare', 1, 7, 3, (128, 128, 128), None, grow=70, fade=True)
    fx.particle('dust', 8, 12, 6, (70, 76, 90), (180, 260), grow=16, lift=8, spread=240, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(6, 'dive')
    fx.br(fx.NOW, '>', 3, 'main_end'); fx.emit('rise', fx.CHEST)
    fx.label('main_end'); fx.end(7)
    fx.label('begin'); fx.sound(-55); fx.ret()
    fx.label('dive')
    fx.sound(3); fx.aim(); fx.vcopy(top, fx.TGT); fx.vadd(top, fx.SRC); fx.vdiv(top, 2); fx.sub_(at(top, 1), 1000)
    fx.vcopy(fx.AT, top); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('stoop'); fx.ret()
    fx.travel('stoop', 1, 8, 'stoop_render', 'stoop_arrive', every='stoop_trail')
    fx.label('stoop_trail'); fx.emit('plume', POS, 2); fx.emit('line'); fx.ret()
    fx.label('stoop_render')
    fx.sprite(POS, gold, 860, cell=2, clut=1); fx.sprite(POS, tint, 700, cell=0); fx.ret()
    fx.label('stoop_arrive')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 600)
    fx.emit('flare', fx.TCHEST); fx.emit('boom'); fx.emit('plume', times=10)
    fx.emit('wave', fx.TGT); fx.emit('dust', times=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Roachmon
def roach_rush():
    """Ten cockroaches scuttle out from under Roachmon and race across the ground in zigzags, leaving a stink behind
    them; they pile into the target and it all goes up in muck, flies and fish bones."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(FILTH); fx.palette(SHELL)
    fx.paint(0, roach(0)); fx.paint(1, roach(2)); fx.paint(2, cloud(131)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, speck()); fx.paint(5, splat(141)); fx.paint(6, fishbone())
    tint = fx.colour(128, 128, 128)
    lay = Lay(fx)
    run = 8
    fx.particle('stink', 12, 9, 2, (60, 90, 20), (170, 230), grow=16, lift=8, fade=True)
    fx.particle('reek', 4, 13, 2, (80, 110, 30), (320, 420), grow=30, speed=14, lift=10, spread=160, fade=True)
    fx.particle('muck', 14, 12, 5, (110, 128, 50), (120, 200), grow=-5, speed=70, lift=60, gravity=10, spread=80)
    fx.particle('fly', 12, 14, 4, (128, 128, 128), (40, 60), speed=60, spread=300, clut=1, blend=None)
    fx.particle('bone', 6, 13, 6, (128, 128, 128), (140, 190), speed=60, lift=70, gravity=10, spin=30, clut=1,
                blend=None)
    fx.label('main'); fx.when(0, 'begin'); fx.when(run + 3, 'crash')
    fx.br(fx.NOW, '>', 4, 'main_end'); fx.call('send', 2)
    fx.label('main_end'); fx.end(run + 4)
    fx.label('begin'); fx.sound(-55); fx.aim(); fx.call('lay'); fx.ret()
    fx.label('send'); fx.vcopy(fx.AT, fx.SRC); fx.vcopy(fx.DEST, fx.TGT); fx.call('bug'); fx.ret()
    lay.code()
    bug = fx.pool('bug', 10, 4)
    step, phase = iv(FREE), iv(FREE + 12)
    fx.begin('bug', bug, 'bug_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.scatter(POS, 300); fx.set(at(POS, 1), at(fx.SRC, 1))
    fx.vcopy(step, fx.DEST); fx.scatter(step, 160); fx.set(at(step, 1), at(fx.TGT, 1))
    fx.vsub(step, POS); fx.vdiv(step, run); fx.rnd(phase, 0, 4095); fx.ret()
    fx.label('bug_tick')
    fx.life(run); fx.vadd(POS, step); fx.br(FRAME, '!=', 4, 'noop'); fx.emit('stink', POS); fx.ret()
    fx.label('bug_render')
    fx.lin(fx.T3, FRAME, 900); fx.add(fx.T3, phase); fx.sin(fx.T, fx.T3, 80)
    moved(fx, fx.TV2, POS, lay.side, fx.T, up=50)
    flicker(fx, fx.TV2, tint, 270, (0, 1), clut=1, blend=None, every=1); fx.ret()
    fx.label('crash')
    fx.sound(7); fx.aim(); fx.hit()
    fx.emit('reek', fx.TCHEST, 3); fx.emit('muck', times=10); fx.emit('fly', times=10); fx.emit('bone', times=4)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Kotemon
def hot_head():
    """Flames climb Kotemon's bamboo sword; it shows over the target's head wrapped in fire, tips forward and comes
    down square on the crown: a star, a ring and a burst of flame to both sides."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(KENDO); fx.palette(BAMBOO)
    fx.paint(0, shinai()); fx.paint(1, blaze(3)); fx.paint(2, blaze(8)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(8, 3, 12, 5)); fx.paint(5, ring(13, 2.0)); fx.paint(6, star(4, 2, 9, 6))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 70, 20)
    head = fx.vec()
    raise_, men = 2, 9
    fx.particle('fire', 16, 7, 1, (128, 110, 60), (190, 270), grow=-14, flat=((-10, 10), (-50, -25), (-10, 10)),
                spread=140)
    fx.particle('fire2', 16, 7, 2, (128, 110, 60), (190, 270), grow=-14, flat=((-10, 10), (-50, -25), (-10, 10)),
                spread=140)
    fx.particle('men', 1, 8, 4, (128, 128, 128), None, grow=70, fade=True)
    fx.particle('halo', 2, 8, 5, (128, 90, 30), 140, grow=80, fade=True, sy=7)
    fx.particle('burst', 12, 10, 1, (128, 120, 70), (240, 340), grow=-16, flat=((-75, 75), (-40, -5), (-75, 75)),
                spread=60)
    fx.particle('ember', 14, 12, 6, (128, 110, 60), (70, 120), grow=-6, speed=60, lift=50, gravity=7, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(raise_, 'raise')
    fx.emit('fire', fx.CHEST); fx.emit('fire2')
    fx.end(raise_ + 1)
    fx.label('begin'); fx.sound(-55); fx.ret()
    fx.label('raise'); fx.sound(3); fx.vcopy(fx.AT, fx.TGT); fx.call('stick'); fx.ret()
    stand(fx, 'stick'); fx.ret()
    fx.label('stick_tick')
    fx.life(men + 4); fx.aim()
    fx.vcopy(head, fx.TGT); fx.sub_(at(head, 1), at(fx.TSIZE, 1))
    fx.call('stick_at'); fx.emit('fire', fx.TV2); fx.emit('fire2')
    fx.after(men, 'stick_men'); fx.ret()
    fx.label('stick_at')                    # TV2: the middle of the sword
    fx.lin(fx.T3, FRAME, -65, 65 * men); clamp(fx, fx.T3, 0, 260)
    fx.vcopy(fx.TV2, head); fx.sub_(at(fx.TV2, 1), fx.T3); fx.sub_(at(fx.TV2, 1), 120); fx.ret()
    fx.label('stick_men')
    fx.sound(16); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 420)
    fx.emit('men', head); fx.emit('halo'); fx.emit('burst', times=10); fx.emit('ember', times=10); fx.ret()
    fx.label('stick_render')
    fx.call('stick_at')
    fx.lin(fx.T2, FRAME, -18, 18 * men); clamp(fx, fx.T2, 0, 70)
    fx.sprite(fx.TV2, soft, 640, cell=3)
    fx.sprite(fx.TV2, tint, 200, 680, cell=0, clut=1, blend=None, rot=fx.T2); fx.ret()
    return fx


# ----------------------------------------------------------------- NeoCrimson
def blind_attack():
    """Two red eyes open over NeoCrimson and the field goes dark. Red scrawls lash out at nothing, here, there; then
    one of them finds a fighter, and a jagged bolt tears from NeoCrimson straight into it."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(FURY)
    fx.paint(0, scribble(1)); fx.paint(1, scribble(2)); fx.paint(2, glow(15, 1.2)); fx.paint(3, sliteye())
    fx.paint(4, jag(5)); fx.paint(5, disc(11)); fx.paint(6, streak())
    tint, wash = fx.colour(128, 128, 128), fx.vec()
    head, mid = fx.vec(), fx.vec()
    lay = Lay(fx)
    find = 11
    fx.particle('eye', 2, find + 2, 3, (128, 128, 128), 200, grow=5)
    fx.particle('wild', 10, 3, 0, (128, 70, 60), (420, 620), spread=1300, spin=1)
    fx.particle('wild2', 10, 3, 1, (128, 70, 60), (420, 620), spread=1300, spin=1)
    fx.particle('crash', 1, 8, 4, (128, 128, 128), None, grow=80, fade=True)
    fx.particle('void', 2, 7, 5, (110, 110, 110), 160, grow=60, blend='sub', fade=True)
    fx.particle('shred', 18, 10, 6, (128, 70, 60), (180, 280), grow=-12, speed=90, spread=80, spin=1)
    fx.label('main'); fx.when(0, 'begin'); fx.when(find, 'charge')
    fx.br(fx.NOW, '<', 3, 'main_end'); fx.br(fx.NOW, '>=', find - 1, 'main_end')
    fx.emit('wild', mid)
    fx.set(fx.T2, fx.NOW); fx.mod(fx.T2, 2); fx.br(fx.T2, '!=', 0, 'main_end'); fx.emit('wild2'); fx.sound(13)
    fx.label('main_end'); fx.end(find + 6)
    fx.label('draw')
    fx.br(fx.NOW, '<', 1, 'noop')
    fx.lin(fx.T, fx.NOW, 12); fx.br(fx.NOW, '<=', find, 'draw_dim'); fx.lin(fx.T, fx.NOW, -16, 16 * (find + 5))
    fx.label('draw_dim'); clamp(fx, fx.T, 0, 72); fx.vset(wash, fx.T, fx.T, fx.T); fx.overlay(wash, blend='sub')
    fx.ret()
    fx.label('begin')
    fx.sound(-55); fx.aim(); fx.call('lay')
    fx.vcopy(head, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), 9, 0, 10); fx.sub_(at(head, 1), fx.T3)
    moved(fx, fx.TV2, head, lay.side, 80); fx.emit('eye', fx.TV2)
    moved(fx, fx.TV2, head, lay.side, -80); fx.emit('eye', fx.TV2)
    fx.vcopy(mid, fx.TCHEST); fx.vadd(mid, fx.CHEST); fx.vdiv(mid, 2); fx.ret()
    lay.code()
    fx.label('charge')
    fx.sound(15); fx.aim(); fx.hit(); fx.vcopy(fx.AT, fx.CHEST); fx.call('bolt')
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 560)
    fx.emit('crash', fx.TCHEST); fx.emit('void'); fx.emit('shred', times=14); fx.ret()
    stand(fx, 'bolt'); fx.ret()
    fx.label('bolt_tick'); fx.life(4); fx.aim(); fx.ret()
    fx.label('bolt_render')
    fx.lin(fx.T3, FRAME, -44, 280)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '!=', 0, 'bolt_other')
    band(fx, fx.CHEST, fx.TCHEST, fx.T3, tint, 0); fx.jmp('bolt_ends')
    fx.label('bolt_other'); band(fx, fx.CHEST, fx.TCHEST, fx.T3, tint, 1)
    fx.label('bolt_ends'); fx.lin(fx.T2, fx.T3, 2)
    fx.sprite(fx.CHEST, tint, fx.T2, cell=2); fx.sprite(fx.TCHEST, tint, fx.T2, cell=2); fx.ret()
    return fx


# ----------------------------------------------------------------- Zanbamon
def zanba_blade():
    """Dust rises under Zanbamon's hooves as it lifts a sword longer than the gap between the fighters; the blade
    sweeps level across the field in a wide arc, its wake behind it, and cuts the target as it passes."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(MOONSTEEL)
    fx.paint(0, greatblade()); fx.paint(1, cloud(151)); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, ring(13, 2.0)); fx.paint(5, needle())
    tint, lag1, lag2 = fx.colour(128, 128, 128), fx.colour(50, 90, 96), fx.colour(22, 50, 56)
    lay = Lay(fx)
    tip, reach = fx.vec(), fx.var()
    lift, cut, done = 6, 9, 12
    per = 700 // (cut - lift)
    fx.particle('dust', 12, 11, 1, (60, 76, 80), (180, 260), grow=16, lift=8, spread=260, fade=True)
    fx.particle('flash', 1, 7, 3, (128, 128, 128), None, grow=70, fade=True)
    fx.particle('line', 1, 9, 5, (128, 128, 128), 1300, grow=60, fade=True)
    fx.particle('halo', 2, 8, 4, (90, 128, 128), 160, grow=90, fade=True)
    fx.particle('spark', 16, 11, 3, (128, 128, 128), (80, 150), grow=-8, speed=80, lift=30, gravity=7, spread=80)
    fx.label('main'); fx.when(0, 'begin')
    fx.emit('dust', fx.SRC)
    fx.end(lift)
    fx.label('begin')
    fx.sound(-55); fx.aim(); fx.call('lay'); fx.lin(reach, lay.span, 1, 380)
    fx.vcopy(fx.AT, fx.CHEST); fx.call('sweep'); fx.ret()
    lay.code()
    stand(fx, 'sweep'); fx.ret()
    fx.label('sweep_tick'); fx.life(done + 1); fx.after(lift, 'sweep_go'); fx.after(cut, 'sweep_cut'); fx.ret()
    fx.label('sweep_go'); fx.sound(13); fx.ret()
    fx.label('sweep_cut')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 600)
    fx.emit('flash', fx.TCHEST); fx.emit('line'); fx.emit('halo'); fx.emit('spark', times=12)
    fx.emit('dust', fx.TGT, 4); fx.ret()
    fx.label('sweep_render')
    for k, colour in ((2, lag2), (1, lag1), (0, tint)):
        skip, held = fx.label(), fx.label()
        if k:
            fx.br(FRAME, '<', lift + k, skip)
        fx.set(fx.T3, -700); fx.br(FRAME, '<', lift, held)
        fx.lin(fx.T3, FRAME, per, -700 - per * (lift + k))
        fx.label(held)
        fx.cos(fx.T, fx.T3, reach); fx.sin(fx.T2, fx.T3, reach)
        moved(fx, tip, POS, lay.fwd, fx.T); moved(fx, tip, tip, lay.side, fx.T2)
        if not k:
            ok = fx.label()
            fx.br(FRAME, '>=', lift, ok); fx.lin(fx.T, FRAME, -110, 110 * lift); fx.sub_(at(tip, 1), fx.T)
            fx.label(ok)
        band(fx, POS, tip, 140, colour, 0)
        fx.label(skip)
    fx.sprite(POS, lag1, 300, cell=2); fx.ret()
    return fx


# ----------------------------------------------------------------- Omnimon
def transcendent_sword():
    """The Grey Sword lights: a blade of blue-white light with written signs burning orange along it grows from Omnimon
    across the field and through the target. Then it flares wide, the field goes white, and a tall cleft of light
    stands where the target is."""
    fx = Fx(delay=8, cast_sound=2, draw=True)
    fx.palette(OMNI); fx.palette(GREYFIRE)
    fx.paint(0, lightblade()); fx.paint(1, glyphs(1)); fx.paint(2, glyphs(2)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 1.5, 14, 12)); fx.paint(5, ring(13, 2.0)); fx.paint(6, cleft()); fx.paint(7, bit())
    tint, blue, fire, wash = fx.colour(128, 128, 128), fx.colour(50, 90, 128), fx.colour(128, 128, 128), fx.vec()
    lay = Lay(fx)
    tip, reach = fx.vec(), fx.var()
    grow, cut, last = 7, 10, 19
    fx.particle('cleave', 1, 9, 6, (128, 128, 128), 560, grow=30, sy=56, fade=True)
    fx.particle('cross', 1, 9, 4, (128, 128, 128), None, grow=110, fade=True)
    fx.particle('wave', 3, 9, 5, (90, 110, 128), 220, grow=110, fade=True, sy=6)
    fx.particle('bit', 20, 14, 7, (128, 128, 128), (70, 130), flat=((-20, 20), (-55, -20), (-20, 20)), spread=360,
                clut=1)
    fx.particle('glim', 10, 6, 7, (128, 128, 128), (80, 120), grow=-10, lift=20, spread=420, clut=1)
    fx.label('main'); fx.when(0, 'begin')
    fx.br(fx.NOW, '>', grow, 'main_end'); fx.emit('glim', fx.CHEST)
    fx.label('main_end'); fx.end(cut + 7)
    fx.label('draw')
    fx.br(fx.NOW, '<', cut, 'noop'); fx.br(fx.NOW, '>', cut + 5, 'noop')
    fx.lin(fx.T, fx.NOW, -16, 16 * (cut + 6)); fx.vset(wash, fx.T, fx.T, fx.T); fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    fx.sound(-55); fx.aim(); fx.call('lay'); fx.lin(reach, lay.span, 1, 560)
    fx.vcopy(fx.AT, fx.CHEST); fx.call('sword'); fx.ret()
    lay.code()
    stand(fx, 'sword'); fx.ret()
    fx.label('sword_tick'); fx.life(last); fx.after(2, 'sword_hum'); fx.after(cut, 'sword_cut'); fx.ret()
    fx.label('sword_hum'); fx.sound(13); fx.ret()
    fx.label('sword_cut')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 760)
    fx.vcopy(fx.AT, fx.TGT); fx.sub_(at(fx.AT, 1), 780); fx.call('cleave')
    fx.emit('cross', fx.TCHEST); fx.emit('bit', times=14); fx.emit('wave', fx.TGT); fx.ret()
    fx.label('sword_render')
    fx.set(fx.T3, reach); fx.mul(fx.T3, FRAME); fx.div(fx.T3, grow); clamp(fx, fx.T3, 0, reach)
    moved(fx, tip, POS, lay.fwd, fx.T3)
    fx.set(fx.T2, 110); fx.br(FRAME, '<', cut, 'sword_draw')
    fx.set(fx.T2, 280); fx.br(FRAME, '<', cut + 3, 'sword_draw')
    fx.lin(fx.T2, FRAME, -40, 40 * last + 20)
    fx.label('sword_draw')
    band(fx, POS, tip, fx.T2, blue, 0)
    fx.lin(fx.F1, fx.T2, 1, 0, 2); band(fx, POS, tip, fx.F1, tint, 0)
    fx.lin(fx.F1, fx.T2, 3); fx.sprite(POS, fire, fx.F1, cell=3, clut=1)
    fx.br(FRAME, '>', cut + 4, 'noop')
    for k in (1, 2, 3):
        fx.lin(fx.T, fx.T3, k, 0, 4); moved(fx, fx.TV2, POS, lay.fwd, fx.T)
        flicker(fx, fx.TV2, fire, 190, (1, 2), clut=1, every=2)
    fx.ret()
    return fx


EFFECTS = {258: howling_crusher, 267: tusk_crusher, 275: tail_blade, 276: kongou, 296: maul_attack,
           300: golden_ripper, 306: cyclone_turbine, 308: lizard_dance, 309: bunny_blades, 321: berserk_sword,
           322: blade_twister, 325: ura_sword, 327: gargoyle_rush, 332: roach_rush, 351: hot_head,
           402: blind_attack, 430: zanba_blade, 461: transcendent_sword}
