"""The finishers fought at arm's length, written for this game: the blows (a tail, a hammer, a whip, pincers, a fist)
and the breaths (gales, clouds, heat). Each one has its own paintings and its own choreography; none holds anything
of a disc. What each one plays is in its docstring; how it hits is in content/finishers/imports.json."""
import math

import numpy as np

from tools.technique_effects.finishers import ahead, band, gather, puff
from tools.technique_effects.kit import FRAME, POS, Fx, at, clip, crescent, fbm, glow, grid, polar, ring, segment, star

STONE = ['#3a2c20', '#7a6048', '#b8a080', '#f0e0c0']
DUST = ['#000000', '#3a2a18', '#8a6a40', '#d8b880', '#fff0d0']
STORM = ['#000000', '#102060', '#2868e0', '#70c8ff', '#fff8a0', '#ffffff']
FORGE = ['#2a3048', '#5a6890', '#a0b8e0', '#ffe060', '#ffffff']
FROST = ['#000000', '#103070', '#4090e0', '#b0e8ff', '#ffffff']
GLACIER = ['#284878', '#5088c8', '#a8d8f8', '#ffffff']
ROSE = ['#000000', '#500020', '#d02060', '#ff80b0', '#ffffff']
VINE = ['#0a3010', '#208030', '#60c040', '#d0f080']
MIST = ['#000000', '#203868', '#6090d0', '#c0e0ff', '#ffffff']
PRISM = ['#000000', '#302070', '#6060e0', '#90e0ff', '#ffffff']
VOLT = ['#000000', '#103050', '#2090c0', '#80f0ff', '#ffffff']
CHROME = ['#303848', '#6878a0', '#b0c0e0', '#ffffff']
AURORA = ['#000000', '#083850', '#10a0a0', '#80ffe0', '#ffffff']
SLUDGE = ['#000000', '#283008', '#607818', '#a8c830', '#e8ff90']
MURK = ['#101808', '#384818', '#688028', '#a0b848']
WOOD = ['#2a1808', '#6a4018', '#a87830', '#e0c070']
LEAF = ['#103008', '#308018', '#70c030', '#d0f080']
HEAT = ['#000000', '#400020', '#c01030', '#ff6020', '#ffe060', '#ffffff']
SHELL = ['#601008', '#c03018', '#f08050', '#ffe0c0']
FOAM = ['#000000', '#104060', '#30a0d0', '#a0f0ff', '#ffffff']
DEEP = ['#000000', '#001858', '#0060c0', '#40c0f0', '#d0ffff']
MANE = ['#000000', '#501800', '#e04800', '#ffb020', '#ffff90', '#ffffff']
ALIEN = ['#000000', '#201048', '#5030c0', '#40e0c0', '#e0fff0']
BANANA = ['#000000', '#402800', '#c07000', '#ffd030', '#ffffa0', '#ffffff']
KI = ['#000000', '#502000', '#e06010', '#ffc060', '#ffffff']
SHOCK = ['#000000', '#203060', '#80a0ff', '#ffffff']
GORE = ['#000000', '#380004', '#a00010', '#ff2030', '#ffa0a0']
FUME = ['#000000', '#301020', '#804060', '#e0a0c0']


# ----------------------------------------------------------------- paintings
def spiked_ball():
    """A ball with eight spikes, lit from the upper left."""
    r, ang = polar()
    x, y = grid()
    edge = 8.5 + 6.5 * np.abs(np.cos(ang * 4)) ** 12
    shade = 0.3 + 0.55 * clip(1 - np.hypot(x - 12, y - 11) / 13)
    return np.where(r < 8.5, shade, np.where(r < edge, 0.95, 0.0))


def rock(seed):
    r, ang = polar()
    edge = 9 + 2.5 * np.sin(ang * 3 + seed) + 1.5 * np.cos(ang * 5 + 2 * seed)
    return (r < edge) * (0.3 + 0.6 * fbm(seed + 60))


def hammer():
    """A war hammer, head down."""
    x, y = grid()
    head = (np.abs(x - 16) < 12) & (y > 17) & (y < 30)
    handle = (np.abs(x - 16) < 2.2) & (y >= 2) & (y <= 17)
    lum = np.where(head, 0.5 + 0.2 * (y < 21), 0.0)
    lum = np.where(head & (np.abs(x - 16) > 8.5), 0.98, lum)
    return np.where(handle, 0.3 + 0.15 * (x < 16), lum)


def bolt(seed):
    """A crooked line of current across the cell."""
    r = np.random.default_rng(seed)
    pts = [(3 + 4.3 * k, 16 + (r.random() - 0.5) * 20 * (0 < k < 6)) for k in range(7)]
    lum = np.zeros((32, 32))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        lum = np.maximum(lum, segment(x0, y0, x1, y1, 1.8))
    return clip(np.maximum(lum, 0.8 * segment(pts[2][0], pts[2][1], pts[2][0] + 6, pts[2][1] + (8 if seed % 2 else -8), 1.3)))


def snowflake():
    lum = np.zeros((32, 32))
    for k in range(6):
        a = k * math.pi / 3
        c, s = math.cos(a), math.sin(a)
        lum = np.maximum(lum, segment(16, 16, 16 + 13 * c, 16 + 13 * s, 1.3))
        for side in (-1, 1):
            b = a + side * math.pi / 3
            lum = np.maximum(lum, segment(16 + 8 * c, 16 + 8 * s, 16 + 8 * c + 4 * math.cos(b), 16 + 8 * s + 4 * math.sin(b), 1.1))
    return clip(lum)


def gusts(seed):
    """Lines of wind along the cell."""
    r = np.random.default_rng(seed)
    lum = np.zeros((32, 32))
    for k in range(6):
        y = 4 + 4.6 * k + r.random() * 2
        lum = np.maximum(lum, segment(r.random() * 10, y, 20 + r.random() * 11, y, 1.9) * (0.6 + 0.4 * r.random()))
    return lum


def icicle():
    """A spike of ice, point up."""
    x, y = grid()
    w = 0.4 + 8 * clip((y - 1) / 30)
    body = clip(1.3 - np.abs(x - 16) / w) * (y > 1)
    return clip(body * (0.55 + 0.45 * (x < 16)) + 0.5 * clip(1 - np.abs(x - 16) / 1.2) * (y > 1))


def vine():
    """A stem along the cell with four thorns."""
    x, y = grid()
    yc = 16 + 2.5 * np.sin(x * 2 * np.pi / 32)
    lum = (np.abs(y - yc) < 4.2) * 0.5
    lum = np.maximum(lum, (np.abs(y - yc + 1.5) < 1.3) * 0.75)
    for xk, up in ((4, -1), (12, 1), (20, -1), (28, 1)):
        yk = 16 + 2.5 * math.sin(xk * 2 * math.pi / 32)
        lum = np.maximum(lum, 0.95 * (segment(xk, yk, xk + 2.5, yk + up * 10, 2.2) > 0.3))
    return lum


def leaf():
    x, y = grid()
    u, v = ((x - 16) + (y - 16)) * 0.707, (-(x - 16) + (y - 16)) * 0.707
    body = (u / 13) ** 2 + (v / 5.5) ** 2 < 1
    return body * (0.45 + 0.5 * (np.abs(v) < 0.9))


def hexcrystal():
    """A six-sided crystal seen from its point: a rim, three facets and its spine."""
    x, y = grid()
    ax, ay = np.abs(x - 16), np.abs(y - 16)
    d = np.maximum(ax, 0.866 * ay + 0.5 * ax) / 12
    face = (d < 1) * (0.3 + 0.25 * (x < 16) + 0.2 * (y < 16))
    rim = clip(1 - np.abs(1 - d) * 6) * (d < 1.08)
    return clip(np.maximum(face, rim) + clip(1 - ax / 0.9) * (d < 1) * 0.6)


def mandible():
    """One blade of a stag beetle's pincer, its tip to the right, teeth on its upper edge."""
    x, y = grid()
    t = clip((x - 2) / 28)
    yc = 21 - 9 * np.sin(t * np.pi / 2)
    w = 5.5 * (1 - t) ** 0.7 + 0.6
    body = (np.abs(y - yc) < w) & (x > 2)
    teeth = ((x % 7) < 2.5) & (y < yc - w + 0.5) & (y > yc - w - 2.5) & (t < 0.8) & (x > 2)
    return np.where(body | teeth, 0.4 + 0.35 * (y < yc) + 0.22 * (np.abs(y - yc) > w - 1.2), 0.0)


def xcut():
    return clip(np.maximum(segment(4, 4, 28, 28, 1.4), segment(4, 28, 28, 4, 1.4)) + 0.6 * glow(8, 1.2))


def claw_jaw(lower=False):
    """Half of a crab's claw, hinged at the middle of the cell's left edge: closed, the two halves make the claw."""
    x, y = grid()
    if lower:
        y = 32 - y
    t = clip(x / 31)
    top = 15.5 - 12.5 * np.sin(np.pi * np.clip(0.12 + 0.88 * t, 0, 1)) ** 0.75
    bot = 15.5 - 4.5 * np.sin(np.pi * t) ** 1.2 + 1.3 * (np.sin(x * 1.5) > 0) * (t > 0.25) * (t < 0.9)
    inside = (y > top) & (y < bot)
    return np.where(inside, 0.35 + 0.6 * clip(1 - (y - top) / 5), 0.0)


def jaw_arc():
    """The upper jaw of a mouth of water: an arch with five teeth hanging from it."""
    x, y = grid()
    r = np.hypot(x - 16, y - 24)
    lum = clip(1 - np.abs(r - 13) / 2.6) * (y < 24)
    for xk in (7, 11.5, 16, 20.5, 25):
        yk = 24 - math.sqrt(max(11 ** 2 - (xk - 16) ** 2, 0))
        lum = np.maximum(lum, 0.9 * segment(xk, yk + 1, xk, yk + 7, 1.5))
    return clip(lum)


def drop():
    x, y = grid()
    ball = clip((7 - np.hypot(x - 16, y - 21)) / 1.5)
    w = 6.5 * clip((y - 4) / 14)
    cone = clip(1.2 - np.abs(x - 16) / np.maximum(w, 0.3)) * (y > 4) * (y < 21)
    return clip(np.maximum(ball, cone)) * (0.6 + 0.4 * clip(1 - np.hypot(x - 13.5, y - 19) / 5))


def bubble():
    x, y = grid()
    return clip(ring(9.5, 1.7) * 0.85 + clip(1 - np.hypot(x - 12, y - 11) / 2.6))


def blob(seed):
    """A lumpy billow: five soft balls run together."""
    x, y = grid()
    r = np.random.default_rng(seed)
    lum = np.zeros((32, 32))
    for _ in range(5):
        cx, cy, rad = 16 + (r.random() - 0.5) * 12, 16 + (r.random() - 0.5) * 12, 6 + 3 * r.random()
        lum = np.maximum(lum, clip(1 - np.hypot(x - cx, y - cy) / rad) ** 0.6)
    return clip(lum * (0.45 + 0.8 * fbm(seed)))


def stink():
    """A wavy line of reek rising."""
    x, y = grid()
    xc = 16 + 5 * np.sin(y * 0.55)
    return clip(1 - np.abs(x - xc) / 2.3) * clip(np.minimum(y - 1, 31 - y) / 5)


def twig():
    """A forked branch, its tips to the right."""
    x, y = grid()
    lum = np.maximum(segment(2, 19, 30, 13, 2.7), segment(13, 17, 26, 4, 1.9))
    lum = np.maximum(lum, segment(8, 18, 19, 28, 1.7))
    lum = np.maximum(lum, clip(1 - np.hypot(x - 3.5, y - 19) / 4.5))
    return (lum > 0.25) * (0.4 + 0.5 * fbm(171))


def splinter():
    x, y = grid()
    return (segment(6, 22, 26, 10, 1.8) > 0.3) * (0.6 + 0.35 * (x < 16))


def thwack(n, turn=0.0):
    """A comic blow: a burst of n fat rays, white at its heart."""
    r, ang = polar()
    edge = 5 + 9.5 * np.abs(np.cos(ang * n / 2 + turn)) ** 2.5
    return (r < edge) * clip(1.15 - r / edge) ** 0.8


def wavefront(seed):
    """Three fronts of a wave bulging to the right."""
    x, y = grid()
    r = np.hypot(x + 6, y - 16)
    f = clip(1.2 - np.abs(r - 33) / 3.6) + 0.7 * clip(1.1 - np.abs(r - 26) / 2.8) + 0.45 * clip(1 - np.abs(r - 20) / 2.2)
    return clip(f * (0.6 + 0.7 * fbm(seed)) * clip(1.15 - np.abs(y - 16) / 15.0))


def feather():
    x, y = grid()
    u, v = ((x - 16) + (y - 16)) * 0.707, (-(x - 16) + (y - 16)) * 0.707
    body = clip(1.2 - ((u / 13) ** 2 + (v / 4.5) ** 2))
    barbs = 0.55 + 0.45 * np.abs(np.sin((u + np.abs(v)) * 1.6))
    return clip(body * barbs + clip(1 - np.abs(v) / 0.8) * (np.abs(u) < 14) * 0.8)


def jet(seed):
    """A jet of flame along the cell, widening to the right, streaked."""
    x, y = grid()
    w = 5.5 + 6.5 * (x / 32) + 4 * (fbm(seed) - 0.5)
    streak = 0.55 + 0.6 * np.repeat(fbm(seed + 3)[:, ::4], 4, axis=1)
    return clip(clip(1.25 - np.abs(y - 16) / w) * streak)


def flare():
    return clip(glow(13, 1.5) + 0.9 * segment(1, 16, 31, 16, 1.3) + 0.6 * segment(16, 6, 16, 26, 1.1))


def lock(lean):
    """A lock of a burning mane: a curling flame with a second, smaller tip."""
    x, y = grid()
    t = clip((y - 1) / 30)
    foot = np.sqrt(clip(1 - (np.clip(t - 0.75, 0, 1) / 0.25) ** 2))
    cx = 16 + lean * 7 * (1 - t) ** 2 * np.cos(t * 3)
    main = clip(1.25 - np.abs(x - cx) / np.maximum(0.4 + 8 * t ** 0.7 * foot, 0.3))
    t2 = clip((y - 11) / 20)
    side = clip(1.2 - np.abs(x - (16 - lean * 7 * (1 - t2))) / np.maximum(5 * t2 ** 0.7 * foot, 0.3)) * (y > 11)
    return clip(np.maximum(main, 0.85 * side)) * (y > 1) * (0.4 + 0.8 * t) * (0.75 + 0.5 * fbm(181))


def comet():
    """A body thrown to the right: a bright head and the wake behind it."""
    x, y = grid()
    head = clip(1 - np.hypot(x - 23, y - 16) / 8) ** 0.5
    t = clip(x / 23)
    tail = clip(1 - np.abs(y - 16) / (0.5 + 7.5 * t ** 0.8)) * t ** 1.4 * (x <= 23) * (0.5 + 0.7 * fbm(191))
    return clip(np.maximum(head, tail))


def jagged(seed, n):
    """A burst with n uneven spikes, white at its heart."""
    rng = np.random.default_rng(seed)
    rad = np.array([10 + 5.5 * rng.random() if k % 2 == 0 else 4.5 + 3 * rng.random() for k in range(2 * n)])
    r, ang = polar()
    a = (ang + np.pi) / (2 * np.pi) * 2 * n
    i = np.floor(a).astype(int) % (2 * n)
    f = a - np.floor(a)
    edge = rad[i] * (1 - f) + rad[(i + 1) % (2 * n)] * f
    return (r < edge) * clip(1.15 - r / edge) ** 0.8


def chevron():
    x, y = grid()
    d = np.abs(np.abs(y - 16) - (26 - x) * 0.85)
    return clip(1 - d / 2.3) * (x > 5) * (x < 27.5)


def star5():
    """A five-point star, a point up."""
    r, ang = polar()
    a = np.abs(((ang + np.pi / 2 + np.pi / 5) % (2 * np.pi / 5)) - np.pi / 5)
    edge = 14 * 6 * math.sin(math.pi / 5) / (14 * np.sin(a) + 6 * np.sin(np.pi / 5 - a))
    return (r < edge) * (0.55 + 0.45 * clip(1 - (edge - r) / 2.2))


def fist():
    """A fist seen from the side, knuckles to the right."""
    x, y = grid()
    body = ((x - 14) / 10.5) ** 4 + ((y - 16) / 11.5) ** 4 < 1
    lum = body * (0.4 + 0.3 * clip(1 - np.hypot(x - 9, y - 9) / 18))
    for yk in (7.5, 13, 18.5, 24):
        lum = np.maximum(lum, 0.95 * clip((4.6 - np.hypot(x - 24.5, y - yk)) / 1.4))
    for yk in (10.2, 15.7, 21.2):
        lum = np.where((np.abs(y - yk) < 0.6) & (x > 16) & (x < 27) & (lum > 0), 0.22, lum)
    return np.where(((x - 14) / 7) ** 2 + ((y - 23) / 3.4) ** 2 < 1, 0.8, lum)


def whipseg(seed):
    """A length of a whip of thick liquid, two drips hanging from it."""
    x, y = grid()
    yc = 13 + 3 * np.sin(x * 2 * np.pi / 32 + seed)
    body = clip(1.3 - np.abs(y - yc) / (4.2 + 1.3 * np.sin(x * 4 * np.pi / 32 + seed)))
    for xk in (7 + 3 * seed, 21 + 2 * seed):
        yk = 13 + 3 * math.sin(xk * 2 * math.pi / 32 + seed)
        w = 2.2 * (1 - clip((y - yk) / 12)) + 0.3
        body = np.maximum(body, 0.8 * clip(1 - np.abs(x - xk) / w) * (y > yk) * (y < yk + 12))
    return clip(body * (0.7 + 0.4 * fbm(200 + seed)))


def splat(seed):
    x, y = grid()
    rng = np.random.default_rng(seed)
    r, ang = polar()
    p = rng.random(3) * 6
    edge = 7 + 3 * np.sin(ang * 3 + p[0]) + 2.5 * np.sin(ang * 7 + p[1]) + 1.5 * np.sin(ang * 11 + p[2])
    lum = clip((edge - r) / 2)
    for _ in range(6):
        a, d = rng.random() * 6.28, 11 + 3 * rng.random()
        lum = np.maximum(lum, clip(1 - np.hypot(x - 16 - d * math.cos(a), y - 16 - d * math.sin(a)) / 2.0))
    return clip(lum * (0.6 + 0.5 * fbm(seed)))


def wisp():
    x, y = grid()
    xc = 16 + 6 * np.sin(y * 0.35 + 1)
    return clip(1 - np.abs(x - xc) / 4.5) ** 1.2 * clip(np.minimum(y - 1, 31 - y) / 7) * (0.5 + 0.7 * fbm(211))


def spout():
    """A column of water thrown up, a crown of spray on it."""
    x, y = grid()
    w = 4 + 5 * (y / 32) + 2 * np.sin(y * 0.8)
    body = clip(1.2 - np.abs(x - 16) / w) * (0.5 + 0.7 * np.repeat(fbm(221)[::4, :], 4, axis=0)) * (y > 3)
    return clip(np.maximum(body, 0.8 * clip(1 - np.hypot(x - 16, y - 5) / 6)))


def icechip():
    x, y = grid()
    d = np.abs(x - 16 + 0.5 * (y - 16)) / 4.5 + np.abs(y - 16) / 11
    return clip((1 - d) * 3) * (0.55 + 0.45 * (x + y < 32))


def dashring():
    r, ang = polar()
    return clip(1 - np.abs(r - 12) / 2.2) * (np.cos(ang * 6) > -0.2)


def tri():
    x, y = grid()
    return ((y < 26) & (y > 8) & (np.abs(x - 16) < (y - 8) * 0.5)) * (0.6 + 0.4 * (x < 16))


# ----------------------------------------------------------------- shared pieces
def line(fx, fwd, n=100):
    """fwd = the way from the caster to the target on the ground, `n` long."""
    ok = fx.label()
    fx.vcopy(fwd, fx.TGT); fx.vsub(fwd, fx.SRC); fx.set(at(fwd, 1), 0)
    fx.vlen(fx.T, fwd); fx.br(fx.T, '>', 0, ok); fx.set(fx.T, 1)
    fx.label(ok)
    fx.vmul(fwd, n); fx.vdiv(fwd, fx.T)


def along_line(fx, out, base, fwd, dist, n=100):
    """out = base moved `dist` along fwd (a number or a variable; fwd is n long)."""
    fx.vcopy(fx.TV, fwd); fx.vmul(fx.TV, dist); fx.vdiv(fx.TV, n)
    if out != base:
        fx.vcopy(out, base)
    fx.vadd(out, fx.TV)


def axes(fx, along, across, fwd, ang, length, width, n=100):
    """The two half axes of a slab standing in the plane of the line to the target, its length raised by an angle
    (4096 a turn) over the ground."""
    fx.cos(fx.T, ang, length); fx.sin(fx.T2, ang, length)
    fx.vcopy(along, fwd); fx.vmul(along, fx.T); fx.vdiv(along, n); fx.lin(at(along, 1), fx.T2, -1)
    fx.cos(fx.T, ang, width); fx.sin(fx.T2, ang, width)
    fx.vcopy(across, fwd); fx.vmul(across, fx.T2); fx.vdiv(across, n); fx.set(at(across, 1), fx.T)


def slab(fx, centre, along, across, colour, cell, clut=0, blend='add'):
    """A cell standing in the world: its left edge at centre - along, its top at centre - across."""
    q = fx.Q
    for k, (sa, sc) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        fx.vcopy(q[k], centre)
        (fx.vadd if sa > 0 else fx.vsub)(q[k], along)
        (fx.vadd if sc > 0 else fx.vsub)(q[k], across)
    fx.quad(q[0], q[1], q[2], q[3], colour, cell, clut, blend)


def prop(fx, name, life, every=None, count=1):
    """Define the routine `name`: an instance that stands at AT for `life` ticks, drawn by the label name_render
    (written by the caller); every: a label called each tick."""
    pool = fx.pool(name, count)
    fx.begin(name, pool, name + '_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label(name + '_tick'); fx.life(life)
    if every:
        fx.call(every)
    fx.ret()


def during(fx, first, last, body, every=1):
    """In main: run body() on the ticks first..last (one in `every`)."""
    skip = fx.label()
    fx.br(fx.NOW, '<', first, skip); fx.br(fx.NOW, '>', last, skip)
    if every > 1:
        fx.set(fx.T, fx.NOW); fx.mod(fx.T, every); fx.br(fx.T, '!=', 0, skip)
    body()
    fx.label(skip)


def mouth_of(fx, out, height=8, reach=30):
    """out = the caster's mouth: that many tenths of its height up, a little ahead of it."""
    fx.vcopy(out, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), height, 0, 10); fx.sub_(at(out, 1), fx.T3)
    ahead(fx, out, out, reach)


def flow(fx, vel, src, ticks):
    """vel = what carries a particle from src to the target's chest in that many ticks."""
    fx.vcopy(vel, fx.TCHEST); fx.vsub(vel, src); fx.vdiv(vel, ticks)


def alternate(fx, first, second):
    """Run first() on even frames of the instance, second() on odd ones."""
    other, done = fx.label(), fx.label()
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '!=', 0, other)
    first(); fx.jmp(done)
    fx.label(other); second()
    fx.label(done)


# ----------------------------------------------------------------- Ankylomon
def tail_hammer():
    """A spiked ball of stone swings over in a high arc from Ankylomon's side and comes down on the target; rocks fly,
    dust rolls out in a ring, and the ground jumps a second time."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(STONE); fx.palette(DUST)
    fx.paint(0, spiked_ball(), cut=0.1); fx.paint(1, rock(1), cut=0.1); fx.paint(2, puff(51)); fx.paint(3, ring(13, 2.4))
    fx.paint(4, thwack(7, 0.3)); fx.paint(5, glow(15, 1.2))
    tint = fx.colour(128, 128, 128)
    fwd, pivot, ball = fx.vec(), fx.vec(), fx.vec()
    ang = fx.var()
    fx.particle('wake', 10, 5, 5, (90, 70, 40), 320, grow=-50, clut=1)
    fx.particle('rock', 16, 16, 1, (128, 128, 128), (120, 210), speed=45, lift=70, gravity=12, spread=120, blend=None,
                spin=25)
    fx.particle('dust', 18, 14, 2, (110, 90, 60), (170, 250), grow=22, flat=((-30, 30), (-22, -6), (-30, 30)), clut=1,
                fade=True)
    fx.particle('wave', 3, 9, 3, (128, 110, 80), 160, grow=110, clut=1, fade=True, sy=5)
    fx.particle('crack', 2, 6, 4, (128, 128, 128), 330, grow=28, clut=1, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(8, 'slam'); fx.when(12, 'quake'); fx.end(13)
    fx.label('begin')
    line(fx, fwd); along_line(fx, pivot, fx.TGT, fwd, -550)
    fx.set(ang, 1750); fx.call('mace_at'); fx.emit('mace', fx.TGT); fx.sound(15); fx.ret()
    fx.label('mace_at')                     # the ball on its arc, from the angle
    fx.cos(fx.T, ang, 550); fx.sin(fx.T2, ang, 550)
    along_line(fx, ball, pivot, fwd, fx.T); fx.sub_(at(ball, 1), fx.T2); fx.ret()
    prop(fx, 'mace', 10, every='mace_move')
    fx.label('mace_move')
    fx.lin(ang, FRAME, -200, 1750); fx.br(ang, '>', 400, 'mace_go'); fx.set(ang, 400)
    fx.label('mace_go'); fx.call('mace_at'); fx.br(FRAME, '>', 7, 'noop'); fx.emit('wake', ball); fx.ret()
    fx.label('mace_render')
    fx.lin(fx.T3, FRAME, 45); fx.sprite(ball, tint, 470, cell=0, blend=None, rot=fx.T3); fx.ret()
    fx.label('slam')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 520)
    fx.emit('crack', ball); fx.emit('wave', fx.TGT); fx.emit('rock', fx.TGT, 9)
    for k in range(8):
        fx.circle(fx.TV, 512 * k, 230, -40); fx.vadd(fx.TV, fx.TGT); fx.emit('dust', fx.TV)
    fx.ret()
    fx.label('quake')
    fx.sound(20); fx.emit('wave', fx.TGT, 2); fx.emit('rock', fx.TGT, 7)
    for k in range(8):
        fx.circle(fx.TV, 512 * k + 256, 400, -30); fx.vadd(fx.TV, fx.TGT); fx.emit('dust', fx.TV)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Zudomon
def vulcans_hammer():
    """Sparks run up into a hammer hanging high over the target; it drops, and where it lands a ring of energy bursts
    out, then another, with bolts dancing over the spot."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(STORM); fx.palette(FORGE)
    fx.paint(0, hammer(), cut=0.1); fx.paint(1, clip(ring(12.5, 2.6) * (0.55 + 0.9 * fbm(61)))); fx.paint(2, bolt(3))
    fx.paint(3, bolt(8)); fx.paint(4, star(4, 1.5, 12, 10)); fx.paint(5, glow(15, 1.2)); fx.paint(6, star(8, 2, 13, 12))
    tint, halo = fx.colour(128, 128, 128), fx.colour(50, 90, 128)
    top = fx.vec()
    gather(fx, 'mote', 12, 4, (128, 128, 90), 90, 520, 5)
    fx.particle('streak', 8, 5, 5, (60, 100, 128), 280, grow=-45)
    fx.particle('burst', 2, 7, 6, (128, 128, 128), None, grow=70, fade=True)
    fx.particle('wave', 4, 9, 1, (110, 128, 128), 150, grow=120, fade=True, sy=6)
    fx.particle('arc', 10, 4, 2, (128, 128, 128), (240, 340), spread=420)
    fx.particle('arc2', 10, 4, 3, (128, 128, 128), (240, 340), spread=420)
    fx.particle('spark', 16, 12, 4, (128, 128, 90), (70, 130), grow=-6, speed=80, lift=30, gravity=8, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(10, 'land'); fx.when(13, 'echo')
    for t in (11, 13, 15, 17):
        fx.when(t, 'crackle')
    during(fx, 0, 4, lambda: fx.emit('mote', top, 2))
    fx.end(18)
    fx.label('begin')
    fx.vcopy(top, fx.TGT); fx.lin(fx.T, at(fx.TSIZE, 1), 1, 900); fx.sub_(at(top, 1), fx.T)
    fx.emit('maul', top); fx.sound(-55); fx.ret()
    prop(fx, 'maul', 12, every='maul_move')
    fx.label('maul_move')
    fx.br(FRAME, '<', 5, 'noop'); fx.br(FRAME, '>', 8, 'noop')
    fx.add(at(POS, 1), 225); fx.emit('streak', POS); fx.ret()
    fx.label('maul_render')
    fx.lin(fx.T3, FRAME, 20, 420); fx.sprite(POS, halo, fx.T3, cell=5)
    fx.sprite(POS, tint, 640, cell=0, clut=1, blend=None); fx.ret()
    fx.label('land')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 600)
    fx.emit('burst', fx.TCHEST); fx.emit('arc', times=4); fx.emit('arc2', times=4); fx.emit('spark', times=12)
    fx.emit('wave', fx.TGT); fx.ret()
    fx.label('echo'); fx.sound(13); fx.emit('wave', fx.TGT); fx.ret()
    fx.label('crackle'); fx.emit('arc', fx.TCHEST, 2); fx.emit('arc2', times=2); fx.ret()
    return fx


# ----------------------------------------------------------------- Vikemon
def arctic_blizzard():
    """Two spiked balls of ice whirl round Vikemon; then a gale of snow and flakes blows from it over the target,
    and spikes of ice grow out of the ground where it stands and break."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(FROST); fx.palette(GLACIER)
    fx.paint(0, spiked_ball(), cut=0.1); fx.paint(1, snowflake()); fx.paint(2, gusts(71)); fx.paint(3, gusts(77))
    fx.paint(4, icicle()); fx.paint(5, glow(15, 1.2)); fx.paint(6, puff(73))
    tint, soft = fx.colour(128, 128, 128), fx.colour(80, 115, 128)
    mouth, vel = fx.vec(), fx.vec()
    fx.particle('flake', 24, 9, 1, (128, 128, 128), (80, 140), spread=240, speed=10, drift=vel, spin=18)
    fx.particle('snow', 12, 9, 6, (60, 90, 128), (150, 210), grow=18, spread=160, drift=vel, fade=True)
    fx.particle('glint', 10, 5, 5, (70, 110, 128), 220, grow=-35)
    fx.particle('chip', 14, 12, 4, (128, 128, 128), (60, 110), speed=60, lift=40, gravity=9, spin=25)
    fx.particle('frost', 2, 8, 5, (60, 100, 128), None, grow=40, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(9, 'blow'); fx.when(15, 'freeze')
    for t in (17, 19, 21, 23):
        fx.when(t, 'ice')
    during(fx, 9, 20, lambda: (fx.emit('flake', mouth, 2), fx.emit('snow')))
    fx.end(24)
    fx.label('begin')
    mouth_of(fx, mouth, 7, 40); flow(fx, vel, mouth, 7); fx.emit('stars', fx.CHEST); fx.sound(15); fx.ret()
    prop(fx, 'stars', 10, every='stars_move')
    fx.label('stars_move')
    fx.lin(fx.T3, FRAME, 450); fx.circle(fx.TV2, fx.T3, 340, 0); fx.vadd(fx.TV2, POS); fx.emit('glint', fx.TV2); fx.ret()
    fx.label('stars_render')
    fx.lin(fx.T2, FRAME, 50)
    for k in range(2):
        fx.lin(fx.T3, FRAME, 450, 2048 * k); fx.circle(fx.TV, fx.T3, 340, 0); fx.vadd(fx.TV, POS)
        fx.sprite(fx.TV, tint, 250, cell=0, clut=1, blend=None, rot=fx.T2)
    fx.ret()
    fx.label('blow'); fx.sound(3); fx.emit('gale', mouth); fx.ret()
    prop(fx, 'gale', 12)
    fx.label('gale_render')
    alternate(fx, lambda: band(fx, mouth, fx.TCHEST, 270, soft, 2), lambda: band(fx, mouth, fx.TCHEST, 270, soft, 3))
    fx.ret()
    fx.label('freeze')
    fx.sound(20); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 420)
    fx.emit('frost', fx.TCHEST); fx.emit('spike', fx.TGT); fx.ret()
    fx.label('ice')
    fx.vcopy(fx.TV2, fx.TGT)
    fx.rnd(fx.T, -190, 190); fx.add(at(fx.TV2, 0), fx.T); fx.rnd(fx.T, -190, 190); fx.add(at(fx.TV2, 2), fx.T)
    fx.emit('spike', fx.TV2); fx.sound(34); fx.ret()
    prop(fx, 'spike', 11, every='spike_break', count=5)
    fx.label('spike_break')
    fx.br(FRAME, '!=', 11, 'noop')
    fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), 200); fx.emit('chip', fx.TV2, 2); fx.ret()
    fx.label('spike_render')
    fx.lin(fx.T3, FRAME, 160, 80); fx.br(fx.T3, '<', 580, 'spike_draw'); fx.set(fx.T3, 580)
    fx.label('spike_draw'); fx.pillar(POS, 230, fx.T3, tint, cell=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Rosemon
def thorny_whipping():
    """A thorned vine lashes out from Rosemon three times, high, low and over the top, each crack on the target
    throwing petals and leaves; the third lands the blow."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(ROSE); fx.palette(VINE)
    fx.paint(0, vine(), cut=0.1); fx.paint(1, _petal()); fx.paint(2, _petal()[:, ::-1]); fx.paint(3, star(6, 1.5, 13, 12))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, clip(segment(3, 27, 29, 5, 1.7) + 0.5 * glow(7, 1.2))); fx.paint(6, leaf(), cut=0.1)
    tint = fx.colour(128, 128, 128)
    hand, mid, tip = fx.vec(), fx.vec(), fx.vec()
    turn = fx.var()
    fx.particle('petal', 14, 14, 1, (128, 128, 128), (140, 210), speed=40, lift=35, gravity=5, spread=80, spin=14)
    fx.particle('petal2', 14, 14, 2, (128, 128, 128), (140, 210), speed=40, lift=35, gravity=5, spread=80, spin=-14)
    fx.particle('crack', 3, 5, 3, (128, 128, 128), None, grow=22, fade=True)
    fx.particle('cut', 3, 6, 5, (128, 128, 128), 380, grow=25, fade=True, rot=turn)
    fx.particle('leaf', 10, 12, 6, (128, 128, 128), (100, 150), speed=50, lift=20, gravity=6, clut=1, blend=None, spin=20)
    lashes = ((4, 380, -60, 30), (10, 120, 70, 150), (16, 600, -20, 270))
    fx.label('main')
    for k, (t, _, _, _) in enumerate(lashes):
        fx.when(t, f'lash{k}'); fx.when(t + 2, f'snap{k}')
    fx.end(22)
    for k, (t, rise, dy, rot) in enumerate(lashes):
        fx.label(f'lash{k}')
        fx.aim(); ahead(fx, hand, fx.CHEST, 40); fx.vcopy(tip, fx.TCHEST); fx.add(at(tip, 1), dy)
        fx.vcopy(mid, hand); fx.vadd(mid, tip); fx.vdiv(mid, 2); fx.sub_(at(mid, 1), rise)
        fx.set(turn, rot); fx.emit('whip', hand); fx.sound(15); fx.ret()
        fx.label(f'snap{k}')
        fx.set(fx.SZ, 240 + 50 * k)
        fx.emit('crack', tip); fx.emit('cut'); fx.emit('petal', times=3 + 2 * k); fx.emit('petal2', times=3 + 2 * k)
        fx.emit('leaf', times=3)
        if k == 2:
            fx.aim(); fx.hit(); fx.sound(7)
        else:
            fx.sound(16)
        fx.ret()
    prop(fx, 'whip', 4)
    fx.label('whip_render')
    band(fx, hand, mid, 190, tint, 0, clut=1, blend=None)
    fx.br(FRAME, '<', 2, 'noop')
    band(fx, mid, tip, 190, tint, 0, clut=1, blend=None); fx.ret()
    return fx


def _petal():
    """A rose petal: a broad heart, pale at its edge."""
    x, y = grid()
    u, v = (x - 16) * 0.82 + (y - 16) * 0.57, -(x - 16) * 0.57 + (y - 16) * 0.82
    body = clip(1.3 - ((u / 8.5) ** 2 + (v / 11.0) ** 2)) * (1 - 0.8 * clip(1 - np.hypot(u, v + 12) / 4.0))
    return clip(body) * (0.55 + 0.45 * clip(np.hypot(u, v) / 9.0))


# ----------------------------------------------------------------- Sorcermon
def crystal_cloud():
    """A sparkling fog rolls from Sorcermon's staff to the target and closes round it; six crystals of ice circle in
    the fog, drawing in, and shatter together."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(MIST); fx.palette(PRISM)
    fx.paint(0, puff(81)); fx.paint(1, puff(87)); fx.paint(2, hexcrystal()); fx.paint(3, star(4, 1.2, 14, 16))
    fx.paint(4, glow(15, 1.2))
    tint, dim = fx.colour(128, 128, 128), fx.colour(30, 50, 80)
    start = fx.vec()
    fx.particle('fog', 20, 12, 0, (50, 70, 100), (220, 320), grow=16, speed=8, spread=200, fade=True)
    fx.particle('fog2', 20, 12, 1, (50, 70, 100), (220, 320), grow=16, speed=8, spread=200, fade=True)
    fx.particle('twinkle', 14, 5, 3, (128, 128, 128), (90, 170), spread=400, clut=1)
    fx.particle('chip', 14, 12, 2, (128, 128, 128), (60, 100), speed=55, lift=45, gravity=9, clut=1, spin=22)
    fx.particle('flash', 2, 7, 4, (90, 110, 128), None, grow=50, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(14, 'bite'); fx.when(24, 'burst'); fx.end(25)
    fx.label('begin')
    ahead(fx, start, fx.CHEST, 60); fx.set(fx.SZ, 200); fx.emit('flash', start)
    fx.vcopy(fx.DEST, fx.TCHEST); fx.call('cloud'); fx.sound(-55); fx.ret()
    fx.travel('cloud', 1, 8, 'cloud_render', 'cloud_arrive', every='cloud_trail')
    fx.label('cloud_trail'); fx.emit('fog', POS); fx.emit('fog2'); fx.emit('twinkle'); fx.ret()
    fx.label('cloud_render'); fx.sprite(POS, dim, 520, cell=4); fx.ret()
    fx.label('cloud_arrive'); fx.sound(34); fx.emit('swirl', fx.TCHEST); fx.ret()
    prop(fx, 'swirl', 14, every='swirl_fog')
    fx.label('swirl_fog')
    alternate(fx, lambda: (fx.emit('fog', POS), fx.emit('twinkle')), lambda: fx.emit('fog2', POS)); fx.ret()
    fx.label('swirl_render')
    fx.lin(fx.F1, FRAME, -15, 400)
    for k in range(6):
        fx.lin(fx.T3, FRAME, 330, 683 * k); fx.circle(fx.TV, fx.T3, fx.F1, 0); fx.vadd(fx.TV, POS)
        fx.lin(fx.T3, fx.T3, 2); fx.sin(fx.T, fx.T3, 70); fx.add(at(fx.TV, 1), fx.T)
        fx.lin(fx.T2, FRAME, 12, 30 * k); fx.sprite(fx.TV, tint, 170, cell=2, clut=1, rot=fx.T2)
    fx.ret()
    fx.label('bite'); fx.sound(20); fx.aim(); fx.hit(); fx.ret()
    fx.label('burst')
    fx.sound(7); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 420)
    fx.emit('flash', fx.TCHEST); fx.emit('chip', times=12); fx.emit('twinkle', times=6); fx.ret()
    return fx


# ----------------------------------------------------------------- Kokuwamon
def mini_scissor_claws():
    """Current hums on Kokuwamon; two steel blades snap shut on the target from in front and behind with a spark, then
    two more from above and below, and the current they leave jumps over it."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(VOLT); fx.palette(CHROME)
    fx.paint(0, mandible(), cut=0.1); fx.paint(1, bolt(5)); fx.paint(2, bolt(9)); fx.paint(3, star(4, 1.5, 12, 10))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, xcut())
    tint = fx.colour(128, 128, 128)
    fwd, along, across, c, off = fx.vec(), fx.vec(), fx.vec(), fx.vec(), fx.vec()
    upright = fx.var()
    fx.particle('flash', 2, 5, 5, (128, 128, 128), None, grow=22, fade=True)
    fx.particle('spark', 16, 10, 3, (128, 128, 128), (70, 130), grow=-7, speed=80, lift=20, gravity=6, spread=60)
    fx.particle('zap', 8, 3, 1, (128, 128, 128), (240, 340), spread=300)
    fx.particle('zap2', 8, 3, 2, (128, 128, 128), (240, 340), spread=300)
    fx.label('main'); fx.when(0, 'hum'); fx.when(4, 'snip1'); fx.when(6, 'bite1'); fx.when(10, 'snip2')
    fx.when(12, 'bite2')
    for t in (13, 15, 17):
        fx.when(t, 'jolt')
    during(fx, 0, 3, lambda: (fx.emit('zap', fx.CHEST), fx.emit('zap2')))
    fx.end(19)
    fx.label('hum'); fx.sound(-55); line(fx, fwd); fx.ret()
    fx.label('snip1'); fx.aim(); fx.set(upright, 0); fx.emit('snip', fx.TCHEST); fx.sound(15); fx.ret()
    fx.label('snip2'); fx.aim(); fx.set(upright, 1); fx.emit('snip', fx.TCHEST); fx.sound(15); fx.ret()
    fx.label('bite1')
    fx.sound(16); fx.set(fx.SZ, 260)
    fx.emit('flash', fx.TCHEST); fx.emit('spark', times=6); fx.ret()
    fx.label('bite2')
    fx.sound(7); fx.aim(); fx.hit(); fx.set(fx.SZ, 330)
    fx.emit('flash', fx.TCHEST); fx.emit('spark', times=10); fx.ret()
    fx.label('jolt'); fx.emit('zap', fx.TCHEST); fx.emit('zap2'); fx.ret()
    prop(fx, 'snip', 5)
    fx.label('snip_render')
    fx.lin(fx.T3, FRAME, -190, 640); fx.br(fx.T3, '>', 260, 'snip_gap'); fx.set(fx.T3, 260)
    fx.label('snip_gap'); fx.br(upright, '!=', 0, 'snip_up')
    fx.vcopy(along, fwd); fx.vmul(along, 26); fx.vdiv(along, 10); fx.vset(across, 0, 190, 0)
    fx.vcopy(off, fwd); fx.vmul(off, fx.T3); fx.vdiv(off, 100); fx.jmp('snip_draw')
    fx.label('snip_up')
    fx.vset(along, 0, 260, 0); fx.vcopy(across, fwd); fx.vmul(across, 19); fx.vdiv(across, 10)
    fx.vset(off, 0, fx.T3, 0)
    fx.label('snip_draw')
    fx.vcopy(c, POS); fx.vsub(c, off); slab(fx, c, along, across, tint, 0, clut=1, blend=None)
    fx.vcopy(c, POS); fx.vadd(c, off); fx.vmul(along, -1); slab(fx, c, along, across, tint, 0, clut=1, blend=None)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Quetzalmon
def freezing_wave():
    """Five fronts of freezing wind leave Quetzalmon one after another, growing as they cross to the target; the
    first one to arrive freezes it in a star of frost, and icy feathers fly from each that follows."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(AURORA)
    fx.paint(0, wavefront(91)); fx.paint(1, wavefront(97)); fx.paint(2, feather()); fx.paint(3, star(6, 2, 13, 10))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, star(4, 1.2, 12, 14))
    tint = fx.colour(128, 128, 128)
    mouth, fwd, along, across = fx.vec(), fx.vec(), fx.vec(), fx.vec()
    fx.particle('mote', 16, 5, 5, (100, 128, 120), (60, 120), spread=300)
    fx.particle('feather', 16, 14, 2, (128, 128, 128), (110, 170), speed=35, lift=30, gravity=4, spread=120, spin=10)
    fx.particle('bloom', 2, 12, 3, (128, 128, 128), None, grow=35, fade=True, spin=4)
    fx.particle('haze', 6, 8, 4, (30, 90, 80), 260, grow=40, fade=True)
    fx.label('main'); fx.when(0, 'begin')
    for t in (2, 4, 6, 8, 10):
        fx.when(t, 'send')
    fx.when(11, 'chill'); fx.end(20)
    fx.label('begin'); line(fx, fwd); mouth_of(fx, mouth, 7, 40); fx.sound(-55); fx.ret()
    fx.label('send')
    fx.aim(); fx.vcopy(fx.AT, mouth); along_line(fx, fx.DEST, fx.TCHEST, fwd, 60); fx.call('front'); fx.sound(15)
    fx.ret()
    fx.travel('front', 5, 8, 'front_render', 'front_arrive', every='front_trail')
    fx.label('front_trail'); fx.emit('mote', POS); fx.ret()
    fx.label('front_render')
    fx.lin(fx.T3, FRAME, 9, 110); fx.vcopy(along, fwd); fx.vmul(along, fx.T3); fx.vdiv(along, 100)
    fx.lin(fx.T3, FRAME, 50, 180); fx.vset(across, 0, fx.T3, 0)
    alternate(fx, lambda: slab(fx, POS, along, across, tint, 0), lambda: slab(fx, POS, along, across, tint, 1))
    fx.ret()
    fx.label('front_arrive'); fx.emit('haze', POS); fx.emit('feather', times=3); fx.sound(34); fx.ret()
    fx.label('chill')
    fx.sound(20); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 380)
    fx.emit('bloom', fx.TCHEST); fx.emit('feather', times=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Raremon
def buffalo_breath():
    """Raremon heaves out a rolling green-brown gas that swells as it crosses to the target and hangs on it,
    bubbling, dripping and reeking."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(SLUDGE); fx.palette(MURK)
    fx.paint(0, blob(101)); fx.paint(1, blob(107), cut=0.2); fx.paint(2, bubble()); fx.paint(3, drop()); fx.paint(4, stink())
    fx.paint(5, glow(15, 1.2))
    mouth, vel = fx.vec(), fx.vec()
    fx.particle('gas', 22, 9, 0, (70, 90, 30), (110, 170), grow=30, speed=8, spread=60, drift=vel)
    fx.particle('murk', 14, 9, 1, (128, 128, 128), (130, 190), grow=28, spread=60, drift=vel, clut=1, blend='half')
    fx.particle('bub', 12, 10, 2, (100, 128, 60), (40, 90), grow=4, flat=((-12, 12), (-30, -10), (-12, 12)), spread=280)
    fx.particle('hang', 14, 14, 1, (128, 128, 128), (240, 340), grow=10, flat=((-10, 10), (-14, -4), (-10, 10)),
                spread=260, clut=1, blend='half')
    fx.particle('glare', 8, 12, 0, (50, 70, 20), (260, 340), grow=12, flat=((-10, 10), (-14, -4), (-10, 10)), spread=220)
    fx.particle('drip', 8, 10, 3, (100, 128, 50), (60, 100), gravity=7, spread=260)
    fx.particle('reek', 4, 14, 4, (90, 128, 40), (220, 280), flat=((0, 0), (-24, -24), (0, 0)), spread=220, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(9, 'reach')
    for t in (12, 16, 20):
        fx.when(t, 'stench')
    during(fx, 1, 12, lambda: (fx.emit('gas', mouth, 2), fx.emit('murk')))
    during(fx, 9, 22, lambda: (fx.emit('hang', fx.TCHEST), fx.emit('bub')))
    during(fx, 10, 22, lambda: (fx.emit('drip', fx.TCHEST), fx.emit('glare')), every=2)
    fx.end(24)
    fx.label('begin'); mouth_of(fx, mouth, 7, 40); flow(fx, vel, mouth, 8); fx.sound(-55); fx.sound(3); fx.ret()
    fx.label('reach'); fx.sound(7); fx.aim(); fx.hit(); fx.ret()
    fx.label('stench')
    fx.vcopy(fx.TV2, fx.TCHEST); fx.lin(fx.T, at(fx.TSIZE, 1), 4, 0, 10); fx.sub_(at(fx.TV2, 1), fx.T)
    fx.emit('reek', fx.TV2); fx.sound(11); fx.ret()
    return fx


# ----------------------------------------------------------------- Woodmon
def twig_tap():
    """A forked branch swings down on the target from above, then back up from below, each tap with a smack, a burst of
    leaves and splinters; the second one lands the blow."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(WOOD); fx.palette(LEAF)
    fx.paint(0, twig(), cut=0.1); fx.paint(1, leaf(), cut=0.1); fx.paint(2, splinter(), cut=0.1); fx.paint(3, thwack(5))
    fx.paint(4, crescent(13, 11.5, 5, 0)); fx.paint(5, glow(15, 1.2))
    tint = fx.colour(128, 128, 128)
    fwd, pivot, along, across, c = fx.vec(), fx.vec(), fx.vec(), fx.vec(), fx.vec()
    ang, back = fx.var(), fx.var()
    fx.particle('leaf', 16, 14, 1, (128, 128, 128), (110, 170), speed=45, lift=30, gravity=5, spread=100, clut=1,
                blend=None, spin=16)
    fx.particle('chip', 12, 12, 2, (128, 128, 128), (60, 110), speed=60, lift=40, gravity=9, blend=None, spin=30)
    fx.particle('smack', 2, 6, 3, (128, 128, 128), None, grow=24, clut=1, fade=True)
    fx.particle('swish', 2, 5, 4, (80, 128, 60), 300, grow=20, clut=1, fade=True, rot=back)
    fx.label('main'); fx.when(0, 'begin'); fx.when(4, 'tap1'); fx.when(6, 'smack1'); fx.when(11, 'tap2')
    fx.when(13, 'smack2'); fx.end(18)
    fx.label('begin'); line(fx, fwd); fx.emit('leaf', fx.CHEST, 4); fx.sound(-55); fx.ret()
    for k in (1, 2):
        fx.label(f'tap{k}')
        fx.aim(); along_line(fx, pivot, fx.TCHEST, fwd, -620); fx.set(back, 180 * (k - 1))
        fx.emit('tap', pivot); fx.sound(15); fx.ret()
        fx.label(f'smack{k}')
        fx.set(fx.SZ, 250 + 70 * k)
        fx.emit('smack', fx.TCHEST); fx.emit('swish'); fx.emit('leaf', times=4 + 2 * k); fx.emit('chip', times=3 + 2 * k)
        if k == 2:
            fx.aim(); fx.hit(); fx.sound(7)
        else:
            fx.sound(16)
        fx.ret()
    prop(fx, 'tap', 5)
    fx.label('tap_render')
    fx.br(back, '!=', 0, 'tap_back')
    fx.lin(ang, FRAME, -420, 760); fx.br(ang, '>', -80, 'tap_draw'); fx.set(ang, -80); fx.jmp('tap_draw')
    fx.label('tap_back')
    fx.lin(ang, FRAME, 400, -560); fx.br(ang, '<', 240, 'tap_draw'); fx.set(ang, 240)
    fx.label('tap_draw')
    axes(fx, along, across, fwd, ang, 380, 150)
    fx.vcopy(c, POS); fx.vadd(c, along); slab(fx, c, along, across, tint, 0, blend=None); fx.ret()
    return fx


# ----------------------------------------------------------------- Cyclonemon
def hyper_heat():
    """Rings of heat draw in on Cyclonemon's arm; it lets go a white-hot jet that runs to the target and holds on
    it, molten drops spraying up from where it bites while the muzzle throws rings."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(HEAT)
    fx.paint(0, jet(111)); fx.paint(1, jet(117)); fx.paint(2, ring(13, 1.6)); fx.paint(3, drop()); fx.paint(4, glow(15, 1.2))
    fx.paint(5, flare())
    tint, edge = fx.colour(128, 128, 128), fx.colour(128, 50, 40)
    muzzle, step = fx.vec(), fx.vec()
    wide, core = fx.var(), fx.var()
    fx.particle('draw', 6, 5, 2, (128, 60, 40), 440, grow=-75)
    fx.particle('puff', 8, 6, 2, (128, 70, 40), 110, grow=60, fade=True)
    fx.particle('molten', 22, 12, 3, (128, 128, 128), (60, 120), grow=-4, speed=45, lift=60, gravity=10, spread=80)
    fx.particle('sear', 3, 5, 5, (128, 128, 128), None, grow=30, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(6, 'fire'); fx.when(9, 'burn'); fx.when(13, 'sear2')
    during(fx, 0, 5, lambda: fx.emit('draw', muzzle), every=2)
    fx.end(20)
    fx.label('begin'); mouth_of(fx, muzzle, 6, 50); fx.sound(-55); fx.ret()
    fx.label('fire')
    fx.sound(13); fx.aim(); fx.vcopy(step, fx.TCHEST); fx.vsub(step, muzzle); fx.vdiv(step, 3)
    fx.emit('jet', muzzle); fx.ret()
    fx.label('burn')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 380); fx.emit('sear', fx.TCHEST); fx.ret()
    fx.label('sear2'); fx.sound(16); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 300); fx.emit('sear', fx.TCHEST); fx.ret()
    prop(fx, 'jet', 12, every='jet_move')
    fx.label('jet_move')
    fx.br(FRAME, '>', 3, 'jet_hold'); fx.vadd(POS, step); fx.ret()
    fx.label('jet_hold')
    fx.emit('molten', POS, 2)
    alternate(fx, lambda: fx.emit('puff', muzzle), lambda: None); fx.ret()
    fx.label('jet_render')
    fx.set(wide, 125); fx.br(FRAME, '<', 9, 'jet_draw'); fx.lin(wide, FRAME, -30, 395)
    fx.label('jet_draw')
    fx.lin(core, wide, 1, 0, 2)
    alternate(fx, lambda: (band(fx, muzzle, POS, wide, edge, 0), band(fx, muzzle, POS, core, tint, 1)),
              lambda: (band(fx, muzzle, POS, wide, edge, 1), band(fx, muzzle, POS, core, tint, 0)))
    fx.lin(fx.T3, wide, 3); fx.sprite(POS, tint, fx.T3, cell=5); fx.sprite(muzzle, edge, fx.T3, cell=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Crabmon
def scissor_magic():
    """A great red claw opens beside the target and snaps shut on it, then opens wider and snaps again; each snap
    leaves a crossed cut of light, and bubbles and glints rise from it."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(SHELL); fx.palette(FOAM)
    fx.paint(0, claw_jaw(), cut=0.1); fx.paint(1, claw_jaw(True), cut=0.1); fx.paint(2, xcut()); fx.paint(3, bubble())
    fx.paint(4, star(4, 1.2, 13, 14)); fx.paint(5, glow(15, 1.2))
    tint = fx.colour(128, 128, 128)
    fwd, pivot, along, across, c = fx.vec(), fx.vec(), fx.vec(), fx.vec(), fx.vec()
    ang, size, wide = fx.var(), fx.var(), fx.var()
    fx.particle('cut', 2, 6, 2, (128, 128, 128), None, grow=20, clut=1, fade=True)
    fx.particle('bub', 18, 14, 3, (110, 128, 128), (40, 100), grow=3, flat=((-25, 25), (-40, -10), (-25, 25)),
                spread=180, clut=1)
    fx.particle('glint', 12, 6, 4, (128, 128, 128), (90, 170), grow=-8, spread=380, clut=1)
    fx.particle('foam', 4, 8, 5, (40, 100, 128), 220, grow=45, clut=1, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(4, 'open1'); fx.when(6, 'snap1'); fx.when(10, 'open2')
    fx.when(12, 'snap2')
    during(fx, 12, 18, lambda: (fx.emit('bub', fx.TCHEST), fx.emit('glint')))
    fx.end(20)
    fx.label('begin'); line(fx, fwd); fx.sound(-55); fx.ret()
    for k in (1, 2):
        fx.label(f'open{k}')
        fx.aim(); fx.set(size, 300 + 70 * k); fx.lin(wide, size, 55, 0, 100)
        fx.lin(fx.T3, size, -2, 100); along_line(fx, pivot, fx.TCHEST, fwd, fx.T3)
        fx.emit('claw', pivot); fx.sound(15); fx.ret()
        fx.label(f'snap{k}')
        fx.set(fx.SZ, 230 + 60 * k)
        fx.emit('cut', fx.TCHEST); fx.emit('foam'); fx.emit('bub', times=3 * k); fx.emit('glint', times=3)
        if k == 2:
            fx.aim(); fx.hit(); fx.sound(7)
        else:
            fx.sound(16)
        fx.ret()
    prop(fx, 'claw', 6)
    fx.label('claw_render')
    fx.lin(ang, FRAME, -280, 600); fx.br(ang, '>', 0, 'claw_draw'); fx.set(ang, 0)
    fx.label('claw_draw')
    axes(fx, along, across, fwd, ang, size, wide)
    fx.vcopy(c, POS); fx.vadd(c, along); slab(fx, c, along, across, tint, 0, blend=None)
    fx.mul(ang, -1); axes(fx, along, across, fwd, ang, size, wide)
    fx.vcopy(c, POS); fx.vadd(c, along); slab(fx, c, along, across, tint, 1, blend=None); fx.ret()
    return fx


# ----------------------------------------------------------------- Ebidramon
def pincer_crusher():
    """Two jaws of water rise over and under the target and close on it; they press, rings of pressure drawing in,
    and then crush: ice and water burst out and a spout stands where it was."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(DEEP)
    fx.paint(0, jaw_arc()); fx.paint(1, np.flipud(jaw_arc())); fx.paint(2, drop()); fx.paint(3, ring(13, 1.8))
    fx.paint(4, icechip()); fx.paint(5, glow(15, 1.2)); fx.paint(6, spout())
    tint, soft = fx.colour(128, 128, 128), fx.colour(30, 70, 128)
    gap = fx.var()
    fx.particle('bub', 10, 8, 3, (60, 100, 128), (40, 80), flat=((-8, 8), (-30, -12), (-8, 8)), spread=420)
    fx.particle('press', 6, 5, 3, (90, 120, 128), 560, grow=-95)
    fx.particle('shard', 14, 12, 4, (128, 128, 128), (70, 130), speed=70, lift=40, gravity=9, spread=60, spin=25)
    fx.particle('drop', 14, 12, 2, (100, 128, 128), (60, 110), speed=50, lift=80, gravity=12, spread=80)
    fx.particle('burst', 2, 7, 5, (128, 128, 128), None, grow=60, fade=True)
    fx.particle('spout', 3, 10, 6, (100, 128, 128), 260, grow=22, lift=40, fade=True, sy=40)
    fx.label('main'); fx.when(0, 'begin'); fx.when(13, 'crush'); fx.when(15, 'gush')
    during(fx, 0, 5, lambda: fx.emit('bub', fx.TCHEST))
    fx.end(20)
    fx.label('begin'); fx.emit('jaws', fx.TCHEST); fx.sound(-55); fx.ret()
    prop(fx, 'jaws', 12, every='jaws_press')
    fx.label('jaws_press')
    fx.br(FRAME, '<', 5, 'noop')
    alternate(fx, lambda: (fx.emit('press', POS), fx.sound(15)), lambda: None); fx.ret()
    fx.label('jaws_render')
    fx.lin(gap, FRAME, -110, 540); fx.br(FRAME, '<', 5, 'jaws_draw')
    fx.set(gap, FRAME); fx.mod(gap, 2); fx.mul(gap, 35); fx.add(gap, 95)
    fx.label('jaws_draw')
    fx.lin(fx.T3, FRAME, 30, 200); fx.sprite(POS, soft, fx.T3, cell=5)
    fx.vcopy(fx.TV, POS); fx.sub_(at(fx.TV, 1), gap); fx.sprite(fx.TV, tint, 600, 420, cell=0)
    fx.vcopy(fx.TV, POS); fx.add(at(fx.TV, 1), gap); fx.sprite(fx.TV, tint, 600, 420, cell=1); fx.ret()
    fx.label('crush')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 520)
    fx.emit('burst', fx.TCHEST); fx.emit('shard', times=12); fx.emit('drop', times=10); fx.ret()
    fx.label('gush'); fx.sound(20); fx.emit('spout', fx.TGT, 2); fx.emit('drop', fx.TCHEST, 4); fx.ret()
    return fx


# ----------------------------------------------------------------- Lynxmon
def blazing_mane():
    """Lynxmon's mane flares up in a crown of curling flames with sparks pouring off it; then it breathes a cone of
    fire that widens to the target and leaves it burning."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(MANE)
    fx.paint(0, lock(1)); fx.paint(1, lock(-1)); fx.paint(2, blob(121)); fx.paint(3, blob(127)); fx.paint(4, star(4, 2, 9, 6))
    fx.paint(5, glow(15, 1.2))
    tint = fx.colour(128, 128, 128)
    mouth, vel, crown = fx.vec(), fx.vec(), fx.vec()
    fx.particle('gout', 20, 8, 2, (128, 110, 70), (90, 130), grow=44, spread=40, speed=6, drift=vel, fade=True)
    fx.particle('gout2', 20, 8, 3, (128, 110, 70), (90, 130), grow=44, spread=40, speed=6, drift=vel, fade=True)
    fx.particle('ember', 16, 12, 4, (128, 110, 60), (50, 100), flat=((-10, 10), (-40, -15), (-10, 10)), spread=320)
    fx.particle('lick', 12, 10, 0, (128, 110, 60), (190, 280), grow=-12, flat=((-20, 20), (-65, -30), (-20, 20)),
                spread=240)
    fx.particle('whoof', 2, 7, 5, (128, 90, 40), None, grow=55, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(6, 'roar'); fx.when(13, 'burn')
    during(fx, 0, 8, lambda: fx.emit('ember', crown))
    during(fx, 6, 16, lambda: (fx.emit('gout', mouth), fx.emit('gout2')))
    during(fx, 13, 22, lambda: fx.emit('lick', fx.TGT))
    fx.end(23)
    fx.label('begin')
    mouth_of(fx, mouth, 7, 40); flow(fx, vel, mouth, 7)
    fx.vcopy(crown, fx.SRC); fx.lin(fx.T, at(fx.SSIZE, 1), 8, 0, 10); fx.sub_(at(crown, 1), fx.T)
    fx.emit('mane', crown); fx.sound(-55); fx.ret()
    prop(fx, 'mane', 10)
    fx.label('mane_render')
    fx.lin(fx.F1, FRAME, 55, 200); fx.br(FRAME, '<', 7, 'mane_draw'); fx.lin(fx.F1, FRAME, -130, 1500)
    fx.label('mane_draw')
    for k in range(7):
        fx.lin(fx.T3, FRAME, 70, 585 * k); fx.circle(fx.TV, fx.T3, 190, 0); fx.vadd(fx.TV, POS)
        fx.vcopy(fx.TV2, fx.TV); fx.lin(fx.T, fx.F1, 1, 0, 2); fx.sub_(at(fx.TV2, 1), fx.T)
        fx.sprite(fx.TV2, tint, 230, fx.F1, cell=k % 2)
    fx.ret()
    fx.label('roar'); fx.sound(3); fx.set(fx.SZ, 200); fx.emit('whoof', mouth); fx.ret()
    fx.label('burn')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 420); fx.emit('whoof', fx.TCHEST); fx.ret()
    return fx


# ----------------------------------------------------------------- Vemmon
def vemmon_crash():
    """Rings close on Vemmon; it throws itself at the target as a comet, bursts on it in a jagged flash that sends
    chevrons of shock on beyond, and bounces back in an arc."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(ALIEN)
    fx.paint(0, comet()); fx.paint(1, jagged(131, 11)); fx.paint(2, chevron()); fx.paint(3, dashring())
    fx.paint(4, glow(15, 1.2)); fx.paint(5, tri())
    tint, soft = fx.colour(128, 128, 128), fx.colour(60, 50, 128)
    fwd, along, across, c = fx.vec(), fx.vec(), fx.vec(), fx.vec()
    fx.particle('pulse', 4, 6, 3, (90, 128, 110), 600, grow=-85, spin=12)
    fx.particle('ghost', 8, 5, 4, (50, 60, 128), 320, grow=-45)
    fx.particle('bang', 2, 8, 1, (128, 128, 128), None, grow=35, fade=True)
    fx.particle('bit', 16, 12, 5, (128, 128, 128), (100, 170), speed=75, lift=30, gravity=7, spread=60, spin=30)
    fx.label('main'); fx.when(0, 'begin'); fx.when(1, 'throb'); fx.when(3, 'throb'); fx.when(5, 'launch')
    fx.when(9, 'crash'); fx.end(11)
    fx.label('begin'); line(fx, fwd); fx.sound(-55); fx.ret()
    fx.label('throb'); fx.emit('pulse', fx.CHEST); fx.ret()
    fx.label('launch')
    fx.sound(15); fx.aim(); fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('comet'); fx.ret()
    fx.travel('comet', 1, 4, 'comet_render', 'comet_arrive', every='comet_trail')
    fx.label('comet_trail'); fx.emit('ghost', POS); fx.ret()
    fx.label('comet_render')
    fx.vcopy(along, fwd); fx.vmul(along, 3); fx.vset(across, 0, 170, 0)
    along_line(fx, c, POS, fwd, -130); slab(fx, c, along, across, tint, 0)
    fx.sprite(POS, soft, 420, cell=4); fx.ret()
    fx.label('comet_arrive')
    fx.sound(7); fx.set(fx.SZ, 560)
    fx.emit('bang', POS); fx.emit('bit', times=12); fx.call('shock')
    fx.vcopy(fx.AT, POS); fx.vcopy(fx.DEST, fx.CHEST); fx.call('rebound'); fx.ret()
    fx.label('crash'); fx.aim(); fx.hit(); fx.ret()
    prop(fx, 'shock', 7)
    fx.label('shock_render')
    for k in range(3):
        fx.br(FRAME, '<', k, 'noop')
        fx.lin(fx.T3, FRAME, 55, 130 + 120 * k); along_line(fx, c, POS, fwd, fx.T3)
        fx.vcopy(along, fwd); fx.vmul(along, 8); fx.vdiv(along, 10); fx.vset(across, 0, 150 + 60 * k, 0)
        slab(fx, c, along, across, tint, 2)
    fx.ret()
    fx.travel('rebound', 1, 6, 'rebound_render', 'noop')
    fx.label('rebound_render')
    fx.lin(fx.T3, FRAME, 341); fx.sin(fx.T, fx.T3, 320)
    fx.vcopy(fx.TV, POS); fx.sub_(at(fx.TV, 1), fx.T)
    fx.sprite(fx.TV, soft, 380, cell=4); fx.sprite(fx.TV, tint, 200, cell=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Monmon
def swing_swing():
    """A streak of light swings in a spiral round the target and smacks into it, then a wider one swings the other
    way and smacks harder; stars fly, and four of them are left circling over its head."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(BANANA)
    fx.paint(0, crescent(13, 11.0, 5, 0)); fx.paint(1, jagged(141, 8)); fx.paint(2, star5()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, thwack(6))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 90, 30)
    fwd, head, over = fx.vec(), fx.vec(), fx.vec()
    way, reach, ang = fx.var(), fx.var(), fx.var()
    fx.particle('trail', 12, 6, 3, (128, 100, 40), 300, grow=-42)
    fx.particle('smack', 2, 7, 1, (128, 128, 128), None, grow=28, fade=True)
    fx.particle('ray', 2, 6, 4, (128, 110, 60), None, grow=40, fade=True)
    fx.particle('pop', 16, 14, 2, (128, 128, 128), (90, 150), speed=55, lift=45, gravity=7, spread=60, spin=20)
    fx.label('main'); fx.when(0, 'begin'); fx.when(3, 'go1'); fx.when(9, 'smack1'); fx.when(10, 'go2')
    fx.when(16, 'smack2'); fx.end(17)
    fx.label('begin'); line(fx, fwd); fx.sound(-55); fx.ret()
    for k in (1, 2):
        fx.label(f'go{k}')
        fx.aim(); fx.set(way, 620 if k == 1 else -620); fx.set(reach, 330 + 110 * k)
        fx.emit('swing', fx.TCHEST); fx.sound(15); fx.ret()
        fx.label(f'smack{k}')
        fx.set(fx.SZ, 260 + 80 * k)
        fx.emit('smack', fx.TCHEST); fx.emit('ray'); fx.emit('pop', times=4 + 4 * k)
        if k == 2:
            fx.aim(); fx.hit(); fx.sound(7)
            fx.vcopy(over, fx.TGT); fx.lin(fx.T, at(fx.TSIZE, 1), 1, 120); fx.sub_(at(over, 1), fx.T)
            fx.emit('dizzy', over)
        else:
            fx.sound(16)
        fx.ret()
    prop(fx, 'swing', 6, every='swing_move')
    fx.label('swing_move')
    fx.set(ang, FRAME); fx.mul(ang, way); fx.add(ang, 1024)
    fx.lin(fx.T3, FRAME, 1, -6); fx.mul(fx.T3, reach); fx.div(fx.T3, -6)
    fx.cos(fx.T, ang, fx.T3); fx.sin(fx.T2, ang, fx.T3)
    along_line(fx, head, POS, fwd, fx.T); fx.sub_(at(head, 1), fx.T2); fx.emit('trail', head); fx.ret()
    fx.label('swing_render')
    fx.lin(fx.T3, FRAME, 40); fx.sprite(head, soft, 420, cell=3); fx.sprite(head, tint, 260, cell=2, rot=fx.T3); fx.ret()
    prop(fx, 'dizzy', 11)
    fx.label('dizzy_render')
    for k in range(4):
        fx.lin(fx.T3, FRAME, 420, 1024 * k); fx.circle(fx.TV, fx.T3, 170, 0); fx.vadd(fx.TV, POS)
        fx.lin(fx.T2, FRAME, 25, 20 * k); fx.sprite(fx.TV, tint, 130, cell=2, rot=fx.T2)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Bearmon
def bear_fist():
    """Light gathers on Bearmon's paw; a great fist drives straight into the target, growing as it comes, and stops
    there in a burst while three rings of the blow go on through it."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(KI); fx.palette(SHOCK)
    fx.paint(0, fist()); fx.paint(1, gusts(151)); fx.paint(2, star(12, 2, 14, 20)); fx.paint(3, ring(13, 2.2))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, star(4, 2, 9, 6))
    tint, dim = fx.colour(128, 128, 128), fx.colour(90, 50, 20)
    fwd, hand, along, across, c = fx.vec(), fx.vec(), fx.vec(), fx.vec(), fx.vec()
    nth = fx.var()
    gather(fx, 'mote', 12, 5, (128, 110, 60), 80, 480, 5)
    fx.particle('wind', 1, 5, 4, (128, 80, 30), 60, grow=55)
    fx.particle('burst', 2, 7, 2, (128, 128, 128), None, grow=60, clut=1, fade=True)
    fx.particle('ring', 4, 7, 3, (128, 128, 128), None, grow=40, clut=1, fade=True)
    fx.particle('chip', 14, 12, 5, (128, 120, 70), (70, 130), grow=-6, speed=75, lift=25, gravity=7, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(5, 'throw'); fx.when(8, 'land')
    for t in (9, 10, 11):
        fx.when(t, 'through')
    during(fx, 0, 3, lambda: fx.emit('mote', hand, 2))
    fx.end(13)
    fx.label('begin')
    line(fx, fwd); ahead(fx, hand, fx.CHEST, 40); fx.set(nth, 0); fx.emit('wind', hand); fx.sound(-55); fx.ret()
    fx.label('throw')
    fx.sound(15); fx.aim(); fx.vcopy(fx.AT, hand); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('punch'); fx.ret()
    fx.travel('punch', 1, 3, 'punch_render', 'punch_arrive')
    fx.label('punch_render'); fx.lin(fx.F1, FRAME, 70, 190); fx.jmp('fist_draw')
    fx.label('fist_draw')                   # the fist at POS, F1 its half size, the wind of it behind
    fx.vcopy(along, fwd); fx.vmul(along, fx.F1); fx.vdiv(along, 100); fx.vset(across, 0, fx.F1, 0)
    slab(fx, POS, along, across, tint, 0)
    fx.lin(fx.T3, fx.F1, -1, -260); along_line(fx, c, POS, fwd, fx.T3)
    fx.vcopy(along, fwd); fx.vmul(along, 26); fx.vdiv(along, 10); fx.lin(at(across, 1), fx.F1, 8, 0, 10)
    slab(fx, c, along, across, dim, 1); fx.ret()
    fx.label('punch_arrive'); fx.emit('hold', POS); fx.ret()
    prop(fx, 'hold', 4)
    fx.label('hold_render'); fx.lin(fx.F1, FRAME, -12, 420); fx.jmp('fist_draw')
    fx.label('land')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 560)
    fx.emit('burst', fx.TCHEST); fx.emit('chip', times=12); fx.ret()
    fx.label('through')
    fx.lin(fx.T3, nth, 170, 120); along_line(fx, c, fx.TCHEST, fwd, fx.T3)
    fx.lin(fx.SZ, nth, -90, 400); fx.add(nth, 1); fx.emit('ring', c); fx.sound(16); fx.ret()
    return fx


# ----------------------------------------------------------------- MaloMyotismon
def melting_blood():
    """Blood wells in MaloMyotismon's hand and runs out into a swaying whip that lashes the target and clings to it,
    dripping; where it bit, the target seethes, bubbles and fumes rising."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(GORE); fx.palette(FUME)
    fx.paint(0, whipseg(1)); fx.paint(1, whipseg(2)); fx.paint(2, drop()); fx.paint(3, splat(161)); fx.paint(4, bubble())
    fx.paint(5, glow(15, 1.2)); fx.paint(6, wisp())
    tint = fx.colour(128, 128, 128)
    hand, d, pa, pb = fx.vec(), fx.vec(), fx.vec(), fx.vec()
    out, half = fx.var(), fx.var()
    gather(fx, 'bead', 10, 2, (128, 50, 50), 90, 420, 4)
    fx.particle('drip', 16, 10, 2, (128, 128, 128), (60, 100), gravity=8, spread=50)
    fx.particle('splat', 3, 7, 3, (128, 128, 128), None, grow=45, fade=True, spin=5)
    fx.particle('gout', 12, 12, 2, (128, 128, 128), (60, 110), speed=50, lift=50, gravity=10, spread=60)
    fx.particle('bub', 10, 9, 4, (128, 70, 70), (40, 90), grow=5, flat=((-8, 8), (-22, -8), (-8, 8)), spread=260)
    fx.particle('fume', 10, 14, 6, (128, 128, 128), (170, 250), flat=((-6, 6), (-26, -12), (-6, 6)), spread=240, clut=1,
                fade=True)
    fx.particle('sear', 2, 8, 5, (128, 30, 30), None, grow=30, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(3, 'crack'); fx.when(7, 'lash'); fx.when(15, 'melt')
    during(fx, 0, 2, lambda: fx.emit('bead', hand, 3))
    during(fx, 8, 22, lambda: fx.emit('bub', fx.TCHEST))
    during(fx, 9, 22, lambda: fx.emit('fume', fx.TCHEST), every=2)
    fx.end(24)
    fx.label('begin'); ahead(fx, hand, fx.CHEST, 40); fx.sound(-55); fx.ret()
    fx.label('crack')
    fx.aim(); fx.vcopy(d, fx.TCHEST); fx.vsub(d, hand); fx.vdiv(d, 6); fx.emit('whip', hand); fx.sound(15); fx.ret()
    fx.label('lash')
    fx.sound(16); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 420)
    fx.emit('splat', fx.TCHEST); fx.emit('sear'); fx.emit('gout', times=8); fx.ret()
    fx.label('melt')
    fx.sound(7); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 320)
    fx.emit('splat', fx.TCHEST); fx.emit('sear'); fx.emit('gout', times=4); fx.emit('drip', times=4); fx.ret()
    prop(fx, 'whip', 12, every='whip_drip')
    fx.label('whip_drip')
    fx.rnd(fx.T3, 1, 5); fx.vcopy(fx.TV2, d); fx.vmul(fx.TV2, fx.T3); fx.vadd(fx.TV2, POS); fx.emit('drip', fx.TV2)
    fx.ret()
    fx.label('whip_render')
    fx.lin(out, FRAME, 2, 1)
    fx.set(half, 95); fx.br(FRAME, '<', 9, 'whip_draw'); fx.lin(half, FRAME, -24, 311)
    fx.label('whip_draw')
    fx.vcopy(pa, POS)
    for k, amp in enumerate((60, 130, 170, 150, 90, 0), 1):
        fx.br(out, '<', k, 'noop')
        fx.vcopy(pb, d); fx.vmul(pb, k); fx.vadd(pb, POS)
        if amp:
            fx.lin(fx.T3, FRAME, 520, 700 * k); fx.sin(fx.T, fx.T3, amp); fx.sub_(at(pb, 1), fx.T)
        band(fx, pa, pb, half, tint, k % 2)
        fx.vcopy(pa, pb)
    fx.ret()
    return fx


EFFECTS = {189: tail_hammer, 219: vulcans_hammer, 220: arctic_blizzard, 230: thorny_whipping, 242: crystal_cloud,
           247: mini_scissor_claws, 249: freezing_wave, 264: buffalo_breath, 272: twig_tap, 281: hyper_heat,
           284: scissor_magic, 305: pincer_crusher, 323: blazing_mane, 331: vemmon_crash, 352: swing_swing,
           353: bear_fist, 406: melting_blood}
