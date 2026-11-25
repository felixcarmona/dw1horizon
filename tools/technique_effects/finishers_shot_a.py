"""Finishers written and painted here for the imported Digimon whose finisher is a shot (the first half of them, by
species id): bubbles, arrows, torpedoes, needles, hearts. One function per species; what flies, how it flies and
whom it hits are each one's own."""
import math

import numpy as np

from tools.technique_effects.finishers import GOLD, ahead, band, column, flicker, gather, puff
from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, crescent, fbm, glow, grid, iv, polar, ring, \
    segment, star

SOAP = ['#000000', '#104858', '#40a8c0', '#b0f0f0', '#ffffff']
VENOMFIRE = ['#000000', '#1c4000', '#6c9010', '#f0a020', '#fff0a0', '#ffffff']
SILK = ['#000000', '#587860', '#c8e0c8', '#ffffff']
HOLY = ['#000000', '#6a2a70', '#e070c0', '#ffd0f0', '#ffffff']
HORN = ['#182028', '#586878', '#a8b8c0', '#f4f8f8']
EXHAUST = ['#000000', '#5a0800', '#d03000', '#ff9010', '#ffe880']
FROST = ['#000000', '#0a2060', '#3080d0', '#a0e0ff', '#ffffff']
REDWHITE = ['#000000', '#500008', '#d01020', '#ff8080', '#ffffff']
WIND = ['#000000', '#205060', '#70c0d0', '#e0ffff']
SCALD = ['#000000', '#701008', '#e04818', '#ffb050', '#fff0c0']
STEAM = ['#000000', '#505050', '#b0b0b0', '#ffffff']
CANDLE = ['#000000', '#102870', '#e05810', '#ffc030', '#fff8d0']
WAX = ['#000000', '#806848', '#e8d8b0', '#ffffff']
CORAL = ['#3a0818', '#b02848', '#ff7888', '#ffe0e0']
SEA = ['#000000', '#0a3070', '#3090e0', '#b0e8ff', '#ffffff']
VOLT = ['#000000', '#102080', '#4060ff', '#a0d0ff', '#ffffff']
YELLOW = ['#000000', '#604000', '#e0b000', '#fff080', '#ffffff']
HADES = ['#000000', '#3a0850', '#b01020', '#ff7010', '#ffe060']
SMOKE = ['#000000', '#201820', '#584858', '#a090a0']
PINK = ['#000000', '#801048', '#f04090', '#ffa0c8', '#ffffff']
AQUA = ['#000000', '#106080', '#50c0e0', '#c0f8ff', '#ffffff']
STEEL = ['#101820', '#405870', '#90a8b8', '#e8f0f0']
NUKE = ['#000000', '#0c4010', '#40c020', '#d0ff60', '#ffffff']
FLESH = ['#281018', '#803040', '#d07068', '#f8d8c0']
STING = ['#000000', '#4a2800', '#b07018', '#f0d060', '#ffffff']
VENOM = ['#000000', '#300848', '#8020b0', '#d070f0', '#f8d0ff']
SHROOM = ['#281030', '#7030a0', '#c080e0', '#fff0d0']
SPORE = ['#000000', '#3a1060', '#9040c0', '#e0a0f0', '#ffffff']
KISS = ['#000000', '#90083a', '#ff3070', '#ff90b0', '#ffffff']


# ----------------------------------------------------------------- paintings
def bubble():
    """A soap bubble: a thin skin, almost nothing inside, a window of light and its echo."""
    r, _ = polar()
    x, y = grid()
    return clip(0.9 * ring(12.5, 1.5) + (r < 12.5) * 0.1 + clip(1 - np.hypot(x - 11, y - 10) / 3.5)
                + 0.5 * clip(1 - np.hypot(x - 21, y - 22) / 2.0))


def boil_bubble(seed):
    """A bubble of boiling water: a thick skin and blobs churning inside."""
    r, _ = polar()
    x, y = grid()
    return clip(ring(12, 2.2) + (r < 12) * clip(fbm(seed) * 1.9 - 0.75) + 0.7 * clip(1 - np.hypot(x - 11, y - 10) / 3.0))


def heart(scale=11.0, cy=15.0):
    x, y = grid()
    u, v = (x - 16) / scale, -(y - cy) / scale
    f = (u * u + v * v - 1) ** 3 - u * u * v ** 3
    shine = clip(1 - np.hypot(x - 16 + 0.45 * scale, y - cy + 0.4 * scale) / (0.4 * scale))
    return clip(-f * 12 + 0.3) * (f < 0.02) * (0.6 + 0.4 * shine)


def lips():
    """A kiss mark: a cupid's bow over a full lower lip."""
    x, y = grid()
    dx = np.abs(x - 16)
    span = np.sqrt(clip(1 - (dx / 13.0) ** 2))
    up = 7.0 * span * (0.62 + 0.38 * np.abs(np.sin(dx * np.pi / 13.0)))
    low = 8.0 * span
    upper = (y < 15.2) & (y > 15.2 - up)
    lower = (y > 16.4) & (y < 16.4 + low)
    return clip(upper * 0.7 + lower * (0.72 + 0.28 * clip(1 - np.hypot(x - 16, y - 20) / 4.0)))


def web(turn=0.0):
    """A spider's net: eight spokes and three sagging rounds of thread."""
    r, ang = polar()
    a = ((ang + turn + np.pi / 8) % (np.pi / 4)) - np.pi / 8
    spokes = clip(1 - r * np.abs(np.sin(a)) / 0.8) * (r < 15)
    rr = r / (1 - 0.16 * (1 - (a / (np.pi / 8)) ** 2))
    rounds = sum(clip(1 - np.abs(rr - k) / 0.9) for k in (5.5, 10.0, 14.5)) * (r < 15.5)
    return clip(spokes + rounds)


def silk_ball():
    r, _ = polar()
    return clip((9 - r) / 2.0) * (0.55 + 0.6 * fbm(71))


def thread():
    return clip(segment(4, 26, 28, 6, 1.0) + 0.6 * segment(10, 28, 24, 12, 0.7))


def bow():
    """A drawn bow seen from the side: the arc and its string."""
    r, ang = polar(cx=6.0)
    arc_ = clip(1 - np.abs(r - 13) / 1.7) * (np.abs(ang) < 1.15)
    string = segment(11.3, 4.1, 3.0, 16, 0.8) + segment(11.3, 27.9, 3.0, 16, 0.8)
    return clip(arc_ + 0.7 * string)


def arrow():
    """An arrow flying to the right: a shaft that brightens towards a broad head."""
    x, y = grid()
    shaft = segment(1, 16, 26, 16, 1.4) * (0.3 + 0.7 * x / 26)
    head = ((x > 20) & (np.abs(y - 16) < (31.5 - x) * 0.6)) * 1.0
    fletch = ((x < 7) & (np.abs(y - 16) < 5 - 0.7 * x)) * 0.6
    return clip(np.maximum(np.maximum(shaft, head), fletch))


def feather():
    x, y = grid()
    u, v = (x - 16) * 0.8 + (y - 16) * 0.6, -(x - 16) * 0.6 + (y - 16) * 0.8
    vane = clip(1.2 - ((u / 4.5) ** 2 + (v / 13.0) ** 2))
    barbs = 0.75 + 0.25 * np.cos(v * 1.6 + np.abs(u) * 1.5)
    return clip(vane * barbs * (1 - 0.5 * clip(1 - np.abs(u) / 0.8)) + 0.9 * clip(1 - np.abs(u) / 0.7) * (np.abs(v) < 14))


def harpoon():
    """A horn flying point first to the right: a ridged cone with a collar."""
    x, y = grid()
    w = 7.5 * clip((31.5 - x) / 28.0)
    body = (np.abs(y - 16) < w) & (x > 3)
    ridge = 0.5 + 0.3 * (((x + (y - 16) * 1.3) % 6) < 3)
    edge = np.abs(np.abs(y - 16) - w) < 1.0
    return np.where(body, np.where(x < 7, 0.95, np.where(edge, 0.2, ridge + 0.2 * (y < 15))), 0.0)


def jet():
    """An exhaust flame streaming to the left of the cell."""
    x, y = grid()
    half = 7.0 * (x / 31.5) ** 0.7
    return clip(1 - np.abs(y - 16) / np.maximum(half, 0.3)) * (x / 31.5) * (0.6 + 0.7 * fbm(77))


def spike():
    """A splinter of ice."""
    x, y = grid()
    d = np.abs(x - 16) / (0.5 + 5.0 * clip((y - 2) / 28.0)) + clip((y - 28) / 3)
    return clip((1 - d) * 3) * (y > 2) * (0.6 + 0.4 * (x < 16))


def swirl(turn=0.0):
    """A ball of energy with three arms winding into it."""
    r, ang = polar()
    arms = 0.5 + 0.5 * np.cos(3 * ang + r * 0.55 + turn)
    return clip(clip(1 - np.abs(r - 12) / 2.2) + (r < 12) * (0.15 + 0.8 * arms * clip(r / 5.0)))


def ribbon(turn=0.0):
    return clip(crescent(13.0, 12.4, 2.6, turn) * 1.4)


def candleflame(seed, lean=0.0):
    """A candle's flame: pointed, leaning, dim at its foot where the wick is."""
    x, y = grid()
    t = clip((y - 1) / 29.0)
    w = 8.5 * t ** 0.9 * np.sqrt(clip(1 - (np.clip(t - 0.75, 0, 1) / 0.25) ** 2))
    cx = 16 + lean * (1 - t) * 6 + 1.5 * np.sin(t * 6 + seed)
    outer = clip(1.25 - np.abs(x - cx) / np.maximum(w, 0.3)) * (y > 1)
    foot = clip((t - 0.62) / 0.3) * clip(1 - np.abs(x - 16) / 4.0)
    return clip(outer * (0.55 + 0.6 * t) * (0.85 + 0.3 * fbm(seed))) * (1 - 0.8 * foot)


def droplet():
    x, y = grid()
    body = clip((7 - np.hypot(x - 16, y - 20)) / 1.5)
    tip = clip(1.2 - np.abs(x - 16) / (0.4 + 5.5 * clip((y - 4) / 14.0))) * (y > 4) * (y < 20)
    return clip(np.maximum(body, tip)) * (0.6 + 0.4 * clip(1 - np.hypot(x - 14, y - 18) / 3.5))


def coral(seed):
    """A lump of coral: a trunk that forks twice, with knobs at the tips."""
    r = np.random.default_rng(seed)
    lum = np.zeros((32, 32))

    def grow(x0, y0, ang, length, width, depth):
        nonlocal lum
        x1, y1 = x0 + length * math.cos(ang), y0 + length * math.sin(ang)
        lum = np.maximum(lum, segment(x0, y0, x1, y1, width) * (0.45 + 0.18 * (3 - depth)))
        if depth == 0:
            x, y = grid()
            lum = np.maximum(lum, clip((2.3 - np.hypot(x - x1, y - y1)) / 1.2))
            return
        for turn in (-0.6 - 0.4 * r.random(), 0.5 + 0.5 * r.random()):
            grow(x1, y1, ang + turn, length * 0.72, width * 0.8, depth - 1)
    for k in range(3):
        grow(16, 17, -np.pi / 2 + 2.1 * k + 0.4 * r.random(), 5.5, 2.6, 2)
    return clip(lum)


def chunk():
    x, y = grid()
    d = np.abs(x - 16 - 0.3 * (y - 16)) / 6.0 + np.abs(y - 16 + 0.4 * (x - 16)) / 8.0
    return clip((1 - d) * 3) * (0.55 + 0.45 * (y < 16))


def bolt(seed, width=2.0, sway=10.0):
    """A stroke of lightning across the cell from left to right, with two forks."""
    r = np.random.default_rng(seed)
    pts = [(0.5 + 5.2 * k, 16 + (r.random() - 0.5) * 2 * sway * (0 < k < 6)) for k in range(7)]
    lum = np.zeros((32, 32))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        lum = np.maximum(lum, segment(x0, y0, x1, y1, width))
    for k in (2, 4):
        lum = np.maximum(lum, 0.75 * segment(pts[k][0], pts[k][1], pts[k][0] + 6, pts[k][1] + (8 if k == 2 else -8),
                                             width * 0.6))
    return clip(lum * 1.2)


def ball_lightning(seed):
    """A small hard core with crooked arcs leaping out of it."""
    r = np.random.default_rng(seed)
    lum = glow(7.5, 0.8)
    for k in range(5):
        ang = 2 * np.pi * k / 5 + r.random()
        x0, y0 = 16.0, 16.0
        for step in range(3):
            ang += (r.random() - 0.5) * 1.6
            x1, y1 = x0 + 4.6 * math.cos(ang), y0 + 4.6 * math.sin(ang)
            lum = np.maximum(lum, segment(x0, y0, x1, y1, 1.3 - 0.25 * step))
            x0, y0 = x1, y1
    return clip(lum)


def magma(seed):
    """A black ball split by glowing cracks."""
    r, _ = polar()
    cracks = clip(1 - np.abs(fbm(seed) - 0.5) * 11)
    return clip((r < 12.5) * (0.1 + cracks) * clip((13.5 - r) / 3 + 0.4) + 0.35 * ring(12.5, 1.3))


def torpedo():
    """A torpedo heading right: a capsule with a bright nose band and tail fins."""
    x, y = grid()
    half = np.where(x > 25, 5.0 * np.sqrt(clip(1 - ((x - 25) / 5.5) ** 2)), 5.0)
    body = (np.abs(y - 16) < half) & (x > 5)
    fins = (x > 2) & (x < 9) & (np.abs(y - 16) < 10 - (x - 2) * 0.7) & (np.abs(y - 16) > 2)
    shade = 0.4 + 0.45 * clip(1 - np.abs(y - 14) / 5.0)
    return np.where(body, np.where((x > 21) & (x < 25), 0.98, shade), np.where(fins, 0.3, 0.0))


def spout():
    """A column of thrown water: wide at the foot, frothing at the head."""
    x, y = grid()
    w = 4.5 + 5.0 * (y / 32.0) + 2.5 * clip(1 - np.abs(y - 6) / 5.0)
    return clip(1.15 - np.abs(x - 16) / w) * (0.5 + 0.7 * fbm(83)) * clip((y - 0.5) / 4.0)


def missile():
    """A living missile heading right: a ribbed, swollen body and a hot tip."""
    x, y = grid()
    half = 7.0 * np.sin(np.pi * clip((x - 1) / 31.0)) ** 0.55
    body = (np.abs(y - 16) < half) & (x > 1)
    rib = 0.55 + 0.2 * ((x % 5) < 3.5) + 0.2 * (y < 15)
    return np.where(body, np.where(x > 27, 0.98, np.where((x % 5) < 1.2, 0.15, rib)), 0.0)


def nukeball(seed):
    r, _ = polar()
    return clip(clip(1 - r / (12.5 + 2.5 * fbm(seed))) ** 0.5 * (0.5 + 0.8 * fbm(seed + 3)))


def needle():
    """A stinger flying point first to the right."""
    x, y = grid()
    w = 0.5 + 2.4 * clip(x / 18.0) * clip((31.5 - x) / 9.0)
    return clip(1.3 - np.abs(y - 16) / w) * (0.35 + 0.65 * x / 31.5)


def blob():
    """A drop of venom: a bubble with a thick skin."""
    r, _ = polar()
    x, y = grid()
    return clip(clip((9.5 - r) / 1.5) * (0.4 + 0.5 * clip(r / 9.5) ** 2) + 0.7 * clip(1 - np.hypot(x - 13, y - 12) / 2.6))


def mushroom():
    """A toadstool: a spotted cap, dark gills, a pale stem."""
    x, y = grid()
    cap = (((x - 16) / 13.0) ** 2 + ((y - 15) / 10.0) ** 2 < 1) & (y < 16)
    spots = sum(np.hypot(x - cx, y - cy) < rad for cx, cy, rad in ((10, 10, 2.4), (18, 8.5, 2.0), (24, 12, 1.8))) > 0
    gills = (np.abs(x - 16) < 11) & (y >= 16) & (y < 18)
    stem = (np.abs(x - 16) < 3.6 + 0.12 * (y - 18)) & (y >= 18) & (y < 30)
    return np.where(cap, np.where(spots, 0.98, 0.42 + 0.2 * (y < 10)), np.where(gills, 0.12, np.where(stem, 0.88, 0.0)))


def spores(seed):
    """A handful of drifting specks."""
    r = np.random.default_rng(seed)
    x, y = grid()
    lum = np.zeros((32, 32))
    for _ in range(10):
        ang, rad = r.random() * 2 * np.pi, 3 + r.random() * 10
        lum = np.maximum(lum, clip((1.3 + r.random() - np.hypot(x - 16 - rad * math.cos(ang),
                                                                y - 16 - rad * math.sin(ang))) / 1.0))
    return clip(lum)


def wavefront(seed):
    """A front of heat moving right: a ragged crescent."""
    return clip(crescent(14.0, 12.0, 5.5, np.pi) * (0.55 + 0.9 * fbm(seed)))


# ----------------------------------------------------------------- shared pieces
def muzzle_at(fx, out, tenths, reach):
    """out = the caster's feet lifted by that many tenths of its height and moved `reach` towards the target."""
    fx.vcopy(out, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), tenths, 0, 10); fx.sub_(at(out, 1), fx.T3)
    ahead(fx, out, out, reach)


def sides(fx, side, width):
    """side = a vector of that length across the line from the caster to the target (on the ground plane)."""
    ok = fx.label()
    fx.vcopy(fx.TV, fx.TGT); fx.vsub(fx.TV, fx.SRC); fx.set(at(fx.TV, 1), 0)
    fx.vlen(fx.T, fx.TV); fx.br(fx.T, '>', 0, ok); fx.set(fx.T, 1)
    fx.label(ok)
    fx.lin(at(side, 0), at(fx.TV, 2), width, 0, fx.T); fx.set(at(side, 1), 0)
    fx.lin(at(side, 2), at(fx.TV, 0), -width, 0, fx.T)


def homing(fx, name, count, ticks, render, arrive, every=None, fields=0):
    """Define the routine `name`: an instance that leaves AT and reaches the target's chest in `ticks` ticks, turning
    after it if it moves; `arrive` is called there. Its last step is the instance vector at FREE."""
    pool = fx.pool(name, count, 3 + fields)
    step = iv(FREE)
    go = fx.label()
    fx.begin(name, pool, render, inherit=False)
    fx.vcopy(POS, fx.AT); fx.vset(step, 0, 0, 0); fx.ret()
    fx.label(name + '_tick')
    fx.br(FRAME, '>=', ticks, go)
    fx.aim(); fx.vcopy(step, fx.TCHEST); fx.vsub(step, POS)
    fx.lin(fx.T, FRAME, -1, ticks); fx.vdiv(step, fx.T); fx.vadd(POS, step)
    if every:
        fx.call(every)
    fx.ret()
    fx.label(go)
    fx.call(arrive)
    fx.set(FRAME, -1); fx.ret()
    return pool


def hop(fx, out, ticks, height):
    """out = the instance's place lifted along an arc: `height` at the middle of a flight of `ticks` ticks."""
    fx.lin(fx.T, FRAME, 2048, 0, ticks); fx.sin(fx.T2, fx.T, height)
    fx.vcopy(out, POS); fx.sub_(at(out, 1), fx.T2)


def dart(fx, head, n, half, colour, cell, clut=0, blend='add'):
    """A cell drawn along the instance's flight: from n steps behind `head` to it."""
    fx.vcopy(fx.TV, iv(FREE)); fx.vmul(fx.TV, n); fx.vcopy(fx.TV2, head); fx.vsub(fx.TV2, fx.TV)
    band(fx, fx.TV2, head, half, colour, cell, clut, blend)


# ----------------------------------------------------------------- Brachiomon
def brachio_bubble():
    """A bubble swells at Brachiomon's mouth until it is as big as a Digimon, lets go and wobbles after its target with
    small bubbles in its wake; it bursts over it in a ring of spray."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(SOAP); fx.palette(PINK)
    fx.paint(0, bubble()); fx.paint(1, glow(15, 1.2)); fx.paint(2, droplet()); fx.paint(3, ring(13, 1.6))
    fx.paint(4, star(4, 2, 9, 6))
    tint, sheen = fx.colour(128, 128, 128), fx.colour(70, 40, 60)
    mouth = fx.vec()
    blow, fly = 12, 14
    fx.particle('mini', 16, 12, 0, (110, 128, 128), (60, 130), flat=((-10, 10), (-22, -6), (-10, 10)), spread=160)
    fx.particle('pop', 2, 8, 3, (128, 128, 128), None, grow=85, fade=True)
    fx.particle('mist', 2, 7, 1, (60, 100, 110), None, grow=40, fade=True)
    fx.particle('drop', 16, 12, 2, (120, 128, 128), (80, 150), grow=-6, speed=75, lift=45, gravity=10, spread=80)
    fx.particle('glint', 8, 8, 4, (128, 128, 128), (80, 140), grow=-9, spread=380)
    fx.label('main'); fx.when(0, 'begin'); fx.when(blow, 'loose'); fx.end(blow + 1)
    fx.label('begin'); muzzle_at(fx, mouth, 9, 90); fx.vcopy(fx.AT, mouth); fx.call('swell'); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(13); fx.vcopy(fx.AT, mouth); fx.call('big'); fx.ret()
    swell = fx.pool('swell', 1)
    fx.begin('swell', swell, 'swell_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('swell_tick'); fx.life(blow - 1); fx.emit('mini', POS); fx.ret()
    fx.label('swell_render')
    fx.lin(fx.T3, FRAME, 38, 50); fx.sprite(POS, tint, fx.T3, cell=0)
    fx.lin(fx.T2, fx.T3, 8, 0, 10); fx.sprite(POS, sheen, fx.T2, cell=0, clut=1, rot=140); fx.ret()
    homing(fx, 'big', 1, fly, 'big_render', 'big_arrive', every='big_wake')
    fx.label('big_wake'); fx.emit('mini', POS); fx.ret()
    fx.label('big_render')
    fx.lin(fx.T, FRAME, 700); fx.sin(fx.T2, fx.T, 50)
    fx.lin(fx.T3, fx.T2, 1, 500); fx.lin(fx.F1, fx.T2, -1, 500)
    fx.sprite(POS, tint, fx.T3, fx.F1, cell=0)
    fx.lin(fx.T3, fx.T3, 8, 0, 10); fx.lin(fx.F1, fx.F1, 8, 0, 10)
    fx.sprite(POS, sheen, fx.T3, fx.F1, cell=0, clut=1, rot=140); fx.ret()
    fx.label('big_arrive')
    fx.sound(7); fx.aim(); fx.hit()
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 320, 10)
    fx.emit('pop', fx.TCHEST); fx.emit('mist'); fx.emit('drop', times=14); fx.emit('glint', times=6)
    fx.emit('mini', times=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Kimeramon
def poison_wing():
    """Kimeramon's wings glow on either side of it and each throws a front of sickly heat; the two close on the target
    like a pair of jaws and it goes up in green and orange flame."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(VENOMFIRE)
    fx.paint(0, wavefront(5)); fx.paint(1, wavefront(9)); fx.paint(2, glow(15, 1.2)); fx.paint(3, candleflame(3))
    fx.paint(4, ring(13, 2.2)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, nukeball(15))
    tint, soft = fx.colour(128, 128, 128), fx.colour(70, 110, 30)
    side, left, right = fx.vec(), fx.vec(), fx.vec()
    charge, fly = 8, 7
    gather(fx, 'mote', 16, 5, (90, 128, 50), 90, 520, 5)
    fx.particle('lamp', 2, charge + 2, 2, (100, 128, 40), 80, grow=40)
    fx.particle('scorch', 16, 7, 6, (128, 110, 60), 260, grow=-30, fade=True)
    fx.particle('blast', 2, 9, 6, (128, 128, 128), None, grow=75, fade=True)
    fx.particle('shock', 2, 8, 4, (90, 128, 40), 160, grow=90, fade=True)
    fx.particle('lick', 12, 11, 3, (128, 120, 70), (190, 300), grow=-10, flat=((-20, 20), (-75, -35), (-20, 20)),
                spread=200)
    fx.particle('ash', 14, 14, 5, (90, 128, 40), (60, 120), grow=-4, speed=50, lift=50, gravity=6, spread=160)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose')
    fx.br(fx.NOW, '>', charge - 4, 'main_end'); fx.emit('mote', left); fx.emit('mote', right)
    fx.label('main_end'); fx.end(charge + 1)
    fx.label('lay')
    sides(fx, side, 380)
    fx.vcopy(left, fx.CHEST); fx.sub_(at(left, 1), 160); fx.vcopy(right, left)
    fx.vadd(left, side); fx.vsub(right, side); fx.ret()
    fx.label('begin'); fx.call('lay'); fx.emit('lamp', left); fx.emit('lamp', right); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.sound(3); fx.aim(); fx.vcopy(fx.DEST, fx.TCHEST)
    fx.vcopy(fx.AT, left); fx.call('gust'); fx.vcopy(fx.AT, right); fx.call('gust'); fx.ret()
    fx.travel('gust', 2, fly, 'gust_render', 'gust_arrive', every='gust_wake')
    fx.label('gust_wake'); fx.emit('scorch', POS); fx.ret()
    fx.label('gust_render')
    fx.sprite(POS, soft, 520, cell=2)
    fx.set(fx.T3, FRAME); fx.mod(fx.T3, 2); fx.br(fx.T3, '==', 0, 'gust_b')
    dart(fx, POS, 3, 230, tint, 0); fx.ret()
    fx.label('gust_b'); dart(fx, POS, 3, 230, tint, 1); fx.ret()
    fx.label('gust_arrive')
    fx.sound(15); fx.aim(); fx.hit()
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 300, 10)
    fx.emit('blast', fx.TCHEST); fx.emit('shock'); fx.emit('lick', times=6); fx.emit('ash', times=7); fx.ret()
    return fx


# ----------------------------------------------------------------- Wormmon
def sticky_net():
    """Wormmon spits a ball of silk that opens in the air into a turning net, falls over its target and draws tight
    round it, threads flying."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(SILK)
    fx.paint(0, web()); fx.paint(1, web(np.pi / 8)); fx.paint(2, glow(15, 1.2)); fx.paint(3, silk_ball())
    fx.paint(4, thread()); fx.paint(5, star(4, 2, 9, 6))
    tint, soft = fx.colour(128, 128, 128), fx.colour(50, 60, 50)
    mouth = fx.vec()
    spit, fly, bind = 4, 10, 12
    fx.particle('strand', 16, 8, 4, (110, 120, 110), (120, 200), grow=-8, spread=140, spin=14, fade=True)
    fx.particle('fling', 12, 11, 4, (128, 128, 128), (140, 220), grow=-8, speed=60, lift=40, gravity=8, spread=120,
                spin=22)
    fx.particle('tuft', 8, 9, 3, (90, 100, 90), (120, 200), grow=14, lift=8, spread=260, fade=True)
    fx.particle('glint', 8, 8, 5, (128, 128, 128), (70, 120), grow=-8, spread=320)
    fx.label('main'); fx.when(0, 'begin'); fx.when(spit, 'loose'); fx.end(spit + 1)
    fx.label('begin'); muzzle_at(fx, mouth, 6, 60); fx.emit('tuft', mouth); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(13); fx.vcopy(fx.AT, mouth); fx.call('net'); fx.ret()
    homing(fx, 'net', 1, fly, 'net_render', 'net_arrive', every='net_wake')
    fx.label('net_wake'); fx.emit('strand', POS); fx.ret()
    fx.label('net_render')
    fx.br(FRAME, '>', 2, 'net_open')
    fx.sprite(POS, tint, 170, cell=3); fx.ret()
    fx.label('net_open')
    fx.lin(fx.T3, FRAME, 60, -20); fx.lin(fx.T2, FRAME, 24)
    fx.sprite(POS, soft, fx.T3, cell=2); fx.sprite(POS, tint, fx.T3, cell=0, rot=fx.T2); fx.ret()
    fx.label('net_arrive')
    fx.sound(34); fx.aim(); fx.hit(); fx.vcopy(fx.AT, fx.TCHEST); fx.call('wrap')
    fx.emit('fling', times=8); fx.ret()
    wrap = fx.pool('wrap', 1, 1)
    wide = iv(FREE)
    fx.begin('wrap', wrap, 'wrap_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.lin(wide, at(fx.TSIZE, 1), 1, 140); fx.ret()
    fx.label('wrap_tick')
    fx.life(bind); fx.after(5, 'wrap_pull'); fx.ret()
    fx.label('wrap_pull'); fx.sound(20); fx.emit('tuft', POS, 4); fx.emit('glint', times=6); fx.emit('fling', times=4)
    fx.ret()
    fx.label('wrap_render')
    # wide open as it lands, pulled tight by tick 5, then held, trembling
    fx.lin(fx.T3, FRAME, -80, 260); fx.br(FRAME, '<', 5, 'wrap_draw')
    fx.set(fx.T3, FRAME); fx.mod(fx.T3, 2); fx.mul(fx.T3, 24)
    fx.label('wrap_draw')
    fx.add(fx.T3, wide); fx.lin(fx.T2, FRAME, -18, 240)
    fx.sprite(POS, soft, fx.T3, cell=2); fx.sprite(POS, tint, fx.T3, cell=0, rot=fx.T2); fx.ret()
    return fx


# ----------------------------------------------------------------- Angewomon
def celestial_arrow():
    """A golden bow takes shape before Angewomon as light gathers on it; she looses one long arrow of rose light that
    flies straight, shedding sparks, and breaks on what it strikes in a cross of light and falling feathers. A target
    that moves out of its line is missed."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(HOLY); fx.palette(GOLD)
    fx.paint(0, bow()); fx.paint(1, arrow()); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, feather()); fx.paint(5, ring(13, 2.0)); fx.paint(6, star(4, 2.5, 13, 10))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 70, 110)
    hand = fx.vec()
    draw, hold = 9, 14
    gather(fx, 'mote', 14, 3, (128, 120, 90), 80, 560, 6, clut=1)
    fx.particle('twinkle', 16, 7, 3, (128, 110, 128), (70, 130), grow=-10, spread=90)
    fx.particle('cross', 1, 9, 6, (128, 128, 128), None, grow=85, fade=True)
    fx.particle('halo', 2, 8, 5, (128, 80, 120), 150, grow=90, fade=True)
    fx.particle('plume', 12, 16, 4, (128, 128, 128), (130, 190), flat=((-22, 22), (-30, 6), (-22, 22)), gravity=3,
                spread=160, spin=9)
    fx.label('main'); fx.when(0, 'begin'); fx.when(draw, 'loose')
    fx.br(fx.NOW, '>', draw - 3, 'main_end'); fx.emit('mote', hand, 2)
    fx.label('main_end'); fx.end(draw + 1)
    fx.label('begin'); muzzle_at(fx, hand, 7, 90); fx.vcopy(fx.AT, hand); fx.call('bowl'); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, hand); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('shaft'); fx.ret()
    bowl = fx.pool('bowl', 1)
    fx.begin('bowl', bowl, 'bowl_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('bowl_tick'); fx.life(hold); fx.ret()
    fx.label('bowl_render')
    fx.lin(fx.T3, FRAME, 105, 90); fx.br(FRAME, '<', 6, 'bowl_draw')
    fx.set(fx.T3, 720); fx.br(FRAME, '<', hold - 3, 'bowl_draw')
    fx.lin(fx.T3, FRAME, -170, 170 * hold + 60)
    fx.label('bowl_draw')
    fx.lin(fx.T2, fx.T3, 1, 0, 2); fx.sprite(POS, soft, fx.T2, cell=2); fx.sprite(POS, tint, fx.T3, cell=0, clut=1); fx.ret()
    fx.shot('shaft', 1, 90, 22, 'shaft_render', 'shaft_arrive', miss='shaft_miss', every='shaft_wake')
    fx.label('shaft_wake'); fx.emit('twinkle', POS, 2); fx.ret()
    fx.label('shaft_miss'); fx.emit('twinkle', POS, 6); fx.ret()
    fx.label('shaft_render')
    dart(fx, POS, 5, 110, tint, 1); fx.sprite(POS, soft, 300, cell=2); fx.ret()
    fx.label('shaft_arrive')
    fx.sound(15); fx.set(fx.SZ, 700)
    fx.emit('cross', POS); fx.emit('halo'); fx.emit('plume', times=10); fx.emit('twinkle', times=6); fx.ret()
    return fx


# ----------------------------------------------------------------- Ikkakumon
def harpoon_torpedo():
    """Ikkakumon's horn leaves its head on a jet of flame, trailing smoke, and flies straight on; what it strikes is
    lost in a burst of frost and splinters of ice. A target that moves out of its line is missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(HORN); fx.palette(EXHAUST); fx.palette(FROST)
    fx.paint(0, harpoon()); fx.paint(1, puff(61)); fx.paint(2, glow(15, 1.2)); fx.paint(3, spike())
    fx.paint(4, ring(13, 2.0)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, jet())
    tint, hot = fx.colour(128, 128, 128), fx.colour(128, 110, 80)
    top = fx.vec()
    fire = 4
    fx.particle('flash', 2, 5, 2, (128, 100, 60), 160, grow=70, clut=1, fade=True)
    fx.particle('smoke', 18, 9, 1, (70, 70, 76), 100, grow=16, lift=5, blend='half', fade=False)
    fx.particle('frost', 2, 9, 2, (110, 128, 128), None, grow=70, clut=2, fade=True)
    fx.particle('wave', 2, 9, 4, (90, 120, 128), 200, grow=95, clut=2, fade=True, sy=6)
    fx.particle('splinter', 16, 13, 3, (128, 128, 128), (110, 200), grow=-6, speed=70, lift=70, gravity=11, spread=90,
                clut=2, spin=16)
    fx.particle('glint', 8, 8, 5, (128, 128, 128), (70, 130), grow=-8, spread=340, clut=2)
    fx.label('main'); fx.when(0, 'begin'); fx.when(fire, 'loose'); fx.end(fire + 1)
    fx.label('begin'); muzzle_at(fx, top, 10, 40); fx.emit('flash', top); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.sound(3); fx.aim(); fx.vcopy(fx.AT, top); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('horn')
    fx.emit('flash', top); fx.ret()
    fx.shot('horn', 1, 95, 22, 'horn_render', 'horn_arrive', miss='horn_miss', every='horn_wake')
    fx.label('horn_wake')
    fx.vcopy(fx.TV, iv(FREE)); fx.vmul(fx.TV, 3); fx.vcopy(fx.TV2, POS); fx.vsub(fx.TV2, fx.TV)
    fx.emit('smoke', fx.TV2); fx.ret()
    fx.label('horn_miss'); fx.emit('smoke', POS, 3); fx.ret()
    fx.label('horn_render')
    fx.vcopy(fx.TV, iv(FREE)); fx.vmul(fx.TV, 3); fx.vcopy(fx.KEEP, POS); fx.vsub(fx.KEEP, fx.TV)
    fx.vcopy(fx.TV2, fx.KEEP); fx.vsub(fx.TV2, fx.TV)
    band(fx, fx.TV2, fx.KEEP, 90, hot, 6, clut=1)
    fx.sprite(fx.KEEP, hot, 260, cell=2, clut=1)
    dart(fx, POS, 4, 150, tint, 0, blend=None); fx.ret()
    fx.label('horn_arrive')
    fx.sound(15); fx.set(fx.SZ, 420)
    fx.emit('frost', POS); fx.emit('wave'); fx.emit('splinter', times=14); fx.emit('glint', times=6); fx.ret()
    return fx


# ----------------------------------------------------------------- Silphymon
def top_gun():
    """A light in each of Silphymon's hands comes together before its chest into a red and white sphere with wind
    wound round it; thrown, it follows its target with two gusts circling it and breaks on it in a whirl."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(REDWHITE); fx.palette(WIND)
    fx.paint(0, swirl()); fx.paint(1, swirl(np.pi / 2)); fx.paint(2, glow(15, 1.2)); fx.paint(3, ribbon())
    fx.paint(4, ring(13, 2.0)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ribbon(np.pi))
    tint, soft, air = fx.colour(128, 128, 128), fx.colour(128, 50, 50), fx.colour(110, 128, 128)
    side, centre, vl, vr = fx.vec(), fx.vec(), fx.vec(), fx.vec()
    join, fly, whirl_life = 8, 10, 10
    fx.particle('lampl', 1, join, 2, (128, 70, 70), 120, grow=24, drift=vl)
    fx.particle('lampr', 1, join, 2, (128, 128, 128), 120, grow=24, drift=vr)
    fx.particle('gust', 16, 6, 3, (90, 128, 128), 230, grow=-28, clut=1, spin=30, fade=True)
    fx.particle('blast', 2, 8, 0, (128, 128, 128), None, grow=70, fade=True)
    fx.particle('shock', 2, 8, 4, (128, 128, 128), 160, grow=100, clut=1, fade=True, sy=7)
    fx.particle('chip', 14, 11, 5, (128, 100, 100), (70, 130), grow=-7, speed=70, lift=30, gravity=4, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(join, 'loose'); fx.end(join + 1)
    fx.label('begin')
    sides(fx, side, 260); ahead(fx, centre, fx.CHEST, 70)
    fx.vcopy(vl, side); fx.vdiv(vl, -join); fx.vcopy(vr, side); fx.vdiv(vr, join)
    fx.vcopy(fx.AT, centre); fx.vadd(fx.AT, side); fx.call('lampl')
    fx.vcopy(fx.AT, centre); fx.vsub(fx.AT, side); fx.call('lampr'); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(13); fx.vcopy(fx.AT, centre); fx.call('orb'); fx.ret()
    homing(fx, 'orb', 1, fly, 'orb_render', 'orb_arrive', every='orb_wake')
    fx.label('orb_wake'); fx.emit('gust', POS); fx.ret()
    fx.label('orb_render')
    fx.sprite(POS, soft, 560, cell=2); flicker(fx, POS, tint, 400, (0, 1), every=1)
    for k in range(2):
        fx.lin(fx.T, FRAME, 620, 2048 * k); fx.circle(fx.TV, fx.T, 250, 0); fx.sin(at(fx.TV, 1), fx.T, 120)
        fx.vadd(fx.TV, POS); fx.lin(fx.T2, FRAME, 54, 180 * k)
        fx.sprite(fx.TV, air, 260, cell=3, clut=1, rot=fx.T2)
    fx.ret()
    fx.label('orb_arrive')
    fx.sound(15); fx.aim(); fx.hit()
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 300, 10)
    fx.emit('blast', fx.TCHEST); fx.emit('chip', times=12); fx.vcopy(fx.AT, fx.TGT); fx.call('shock'); fx.call('whirl')
    fx.ret()
    whirl = fx.pool('whirl', 1, 1)
    tall = iv(FREE)
    fx.begin('whirl', whirl, 'whirl_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.set(tall, at(fx.TSIZE, 1)); fx.ret()
    fx.label('whirl_tick'); fx.life(whirl_life); fx.ret()
    fx.label('whirl_render')                # six gusts wind up round the target, widening as they climb
    fx.lin(fx.F1, FRAME, 26, 160)
    for k in range(6):
        fx.lin(fx.T, FRAME, 560, 683 * k); fx.circle(fx.TV, fx.T, fx.F1, 0); fx.vadd(fx.TV, POS)
        fx.lin(fx.T2, tall, FRAME, 0, whirl_life); fx.add(fx.T2, 60 * k); fx.sub_(at(fx.TV, 1), fx.T2)
        fx.lin(fx.T2, FRAME, 50, 60 * k)
        fx.sprite(fx.TV, air, 300, cell=6 if k % 2 else 3, clut=1, rot=fx.T2)
    fx.ret()
    return fx


# ----------------------------------------------------------------- RedOtamamon
def boiling_bubble():
    """RedOtamamon blows three scalding bubbles one after another; each hops through the air steaming and bursts on
    its target in a splash of boiling water."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(SCALD); fx.palette(STEAM)
    fx.paint(0, boil_bubble(3)); fx.paint(1, boil_bubble(9)); fx.paint(2, glow(15, 1.2)); fx.paint(3, puff(13))
    fx.paint(4, droplet()); fx.paint(5, ring(13, 2.2))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 60, 30)
    mouth = fx.vec()
    first, gap, fly, high = 3, 5, 9, 380
    fx.particle('steam', 16, 9, 3, (70, 70, 70), (110, 170), grow=14, lift=18, clut=1, spread=60, fade=True)
    fx.particle('splash', 3, 8, 5, (128, 110, 80), 140, grow=75, fade=True)
    fx.particle('scald', 18, 11, 4, (128, 128, 128), (90, 160), grow=-6, speed=60, lift=55, gravity=10, spread=70)
    fx.particle('vapour', 9, 12, 3, (90, 90, 90), (200, 280), grow=18, lift=22, clut=1, spread=160, fade=True)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(3):
        fx.when(first + gap * k, 'blow')
    fx.end(first + 2 * gap + 1)
    fx.label('begin'); muzzle_at(fx, mouth, 6, 60); fx.sound(-55); fx.ret()
    fx.label('blow')
    fx.sound(34); fx.aim(); fx.vcopy(fx.AT, mouth); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('bub')
    fx.emit('steam', mouth); fx.ret()
    fx.travel('bub', 3, fly, 'bub_render', 'bub_arrive', every='bub_wake')
    fx.label('bub_wake'); hop(fx, fx.TV, fly, high); fx.sub_(at(fx.TV, 1), 120); fx.emit('steam', fx.TV); fx.ret()
    fx.label('bub_render')
    hop(fx, fx.TV, fly, high)
    fx.lin(fx.T3, FRAME, 22, 150)
    fx.lin(fx.F1, fx.T3, 15, 0, 10); fx.sprite(fx.TV, soft, fx.F1, cell=2)
    flicker(fx, fx.TV, tint, fx.T3, (0, 1), every=2); fx.ret()
    fx.label('bub_arrive')
    fx.sound(7); fx.aim(); fx.hit()
    fx.emit('splash', fx.TCHEST); fx.emit('scald', times=6); fx.emit('vapour', times=3); fx.ret()
    return fx


# ----------------------------------------------------------------- Candlemon
def flame_bomber():
    """The flame on Candlemon's head swells and tears free; it is flung in a high arc, dripping wax, and where it comes
    down a ring of small flames stands up. Whoever has left that spot is not burnt."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(CANDLE); fx.palette(WAX)
    fx.paint(0, candleflame(3)); fx.paint(1, candleflame(8, 1.0)); fx.paint(2, glow(15, 1.2)); fx.paint(3, droplet())
    fx.paint(4, ring(13, 2.2)); fx.paint(5, candleflame(5, -1.0)); fx.paint(6, star(4, 2, 9, 6))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 80, 30)
    top = fx.vec()
    swell, fly, high = 8, 10, 560
    fx.particle('drip', 16, 10, 3, (128, 128, 128), (70, 110), grow=-4, flat=((-8, 8), (0, 10), (-8, 8)), gravity=7,
                clut=1)
    fx.particle('burst', 1, 8, 2, (128, 100, 50), 240, grow=80, fade=True)
    fx.particle('shock', 1, 8, 4, (128, 90, 40), 160, grow=95, fade=True, sy=6)
    fx.particle('stand', 12, 14, 5, (128, 128, 128), (220, 330), grow=-12, flat=((-6, 6), (-30, -12), (-6, 6)),
                spread=520)
    fx.particle('wax', 12, 12, 3, (128, 128, 128), (80, 130), grow=-5, speed=65, lift=60, gravity=10, spread=60,
                clut=1)
    fx.particle('spark', 10, 9, 6, (128, 110, 60), (60, 110), grow=-7, speed=20, lift=20, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(swell, 'fling'); fx.end(swell + 1)
    fx.label('begin')
    fx.vcopy(top, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), 1, 90); fx.sub_(at(top, 1), fx.T3)
    fx.vcopy(fx.AT, top); fx.call('wick'); fx.sound(-55); fx.ret()
    fx.label('fling')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, top); fx.vcopy(fx.DEST, fx.TGT); fx.sub_(at(fx.DEST, 1), 60)
    fx.call('bomb'); fx.ret()
    wick = fx.pool('wick', 1)
    fx.begin('wick', wick, 'wick_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('wick_tick'); fx.life(swell - 1); fx.emit('spark', POS); fx.ret()
    fx.label('wick_render')
    fx.lin(fx.T3, FRAME, 44, 120); fx.lin(fx.F1, fx.T3, 14, 0, 10)
    fx.vcopy(fx.TV, POS); fx.lin(fx.T, fx.F1, 1, 0, 3); fx.sub_(at(fx.TV, 1), fx.T)
    fx.sprite(fx.TV, soft, fx.F1, cell=2)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 4); fx.br(fx.T2, '>=', 2, 'wick_b')
    fx.sprite(fx.TV, tint, fx.T3, fx.F1, cell=1); fx.ret()
    fx.label('wick_b'); fx.sprite(fx.TV, tint, fx.T3, fx.F1, cell=5); fx.ret()
    fx.travel('bomb', 1, fly, 'bomb_render', 'bomb_arrive', every='bomb_wake')
    fx.label('bomb_wake'); hop(fx, fx.TV, fly, high); fx.emit('drip', fx.TV); fx.emit('spark', fx.TV); fx.ret()
    fx.label('bomb_render')
    hop(fx, fx.TV, fly, high)
    fx.sprite(fx.TV, soft, 520, cell=2)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 4); fx.br(fx.T2, '>=', 2, 'bomb_b')
    fx.sprite(fx.TV, tint, 340, 440, cell=1); fx.ret()
    fx.label('bomb_b'); fx.sprite(fx.TV, tint, 340, 440, cell=5); fx.ret()
    fx.label('bomb_arrive')
    fx.sound(7); fx.strike(POS, 220)
    fx.emit('burst', POS); fx.emit('shock'); fx.emit('stand', times=12); fx.emit('wax', times=10); fx.ret()
    return fx


# ----------------------------------------------------------------- Gesomon
def coral_crusher():
    """Gesomon hurls three jagged lumps of coral one after another, each spinning in a sheath of sea water and aimed
    anew; each breaks where it lands, and a target that has moved off is not hit by it."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(CORAL); fx.palette(SEA)
    fx.paint(0, coral(3)); fx.paint(1, coral(8)); fx.paint(2, glow(15, 1.2)); fx.paint(3, chunk())
    fx.paint(4, ring(13, 2.2)); fx.paint(5, droplet()); fx.paint(6, coral(14))
    tint, soft = fx.colour(128, 128, 128), fx.colour(40, 90, 128)
    mouth = fx.vec()
    first, gap, fly = 5, 4, 6
    gather(fx, 'bead', 12, 5, (90, 120, 128), 110, 520, 5, clut=1)
    fx.particle('spray', 16, 7, 5, (90, 120, 128), (70, 120), grow=-8, speed=14, gravity=4, clut=1, spread=80)
    fx.particle('shard', 18, 12, 3, (128, 128, 128), (90, 160), grow=-5, speed=65, lift=55, gravity=10, spread=60,
                blend=None, spin=24)
    fx.particle('splash', 3, 8, 4, (90, 120, 128), 150, grow=80, clut=1, fade=True, sy=7)
    fx.particle('foam', 3, 7, 2, (70, 110, 128), 240, grow=50, clut=1, fade=True)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(3):
        fx.when(first + gap * k, 'fire')
    fx.br(fx.NOW, '>', first - 2, 'main_end'); fx.emit('bead', mouth, 2)
    fx.label('main_end'); fx.end(first + 2 * gap + 1)
    fx.label('begin'); muzzle_at(fx, mouth, 5, 80); fx.sound(-55); fx.ret()
    fx.label('fire')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, mouth); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('lump')
    fx.ret()
    fx.travel('lump', 3, fly, 'lump_render', 'lump_arrive', every='lump_wake')
    fx.label('lump_wake'); fx.emit('spray', POS, 2); fx.ret()
    fx.label('lump_render')
    fx.sprite(POS, soft, 520, cell=2, clut=1)
    fx.lin(fx.T2, FRAME, 55)
    fx.set(fx.T3, FRAME); fx.mod(fx.T3, 6); fx.br(fx.T3, '>=', 3, 'lump_b')
    fx.sprite(POS, tint, 450, cell=0, blend=None, rot=fx.T2); fx.ret()
    fx.label('lump_b'); fx.sprite(POS, tint, 450, cell=6, blend=None, rot=fx.T2); fx.ret()
    fx.label('lump_arrive')
    fx.sound(20); fx.strike(POS, 200)
    fx.emit('foam', POS); fx.emit('shard', times=6); fx.emit('spray', times=3)
    fx.vcopy(fx.AT, POS); fx.add(at(fx.AT, 1), 200); fx.call('splash'); fx.ret()
    return fx


# ----------------------------------------------------------------- Wizardmon
def thunder_ball():
    """Sparks jump at the tip of Wizardmon's staff and knot into a ball of lightning; it rolls after its target,
    spitting arcs, and when it reaches it forks of lightning leap out all round and keep the target twitching."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(VOLT); fx.palette(YELLOW)
    fx.paint(0, ball_lightning(1)); fx.paint(1, ball_lightning(2)); fx.paint(2, glow(15, 1.2)); fx.paint(3, bolt(5, 1.6))
    fx.paint(4, bolt(7, 1.6)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.0))
    tint, soft = fx.colour(128, 128, 128), fx.colour(50, 70, 128)
    tip = fx.vec()
    knot, fly = 8, 11
    fx.particle('arc', 10, 3, 3, (128, 128, 128), (200, 320), clut=1, spread=200, spin=1)
    fx.particle('arc2', 10, 3, 4, (128, 128, 128), (200, 320), spread=200, spin=1)
    fx.particle('flash', 2, 7, 2, (110, 120, 128), None, grow=70, fade=True)
    fx.particle('shock', 2, 8, 6, (128, 128, 90), 150, grow=95, clut=1, fade=True)
    fx.particle('fork', 8, 5, 3, (128, 128, 128), (420, 560), clut=1, spread=260, spin=1)
    fx.particle('fork2', 8, 5, 4, (128, 128, 128), (420, 560), spread=260, spin=1)
    fx.particle('spark', 14, 10, 5, (128, 128, 90), (70, 130), grow=-8, speed=70, lift=20, gravity=5, spread=60,
                clut=1)
    fx.label('main'); fx.when(0, 'begin'); fx.when(knot, 'loose')
    fx.br(fx.NOW, '>', knot - 1, 'main_end'); fx.emit('arc', tip); fx.emit('arc2')
    fx.label('main_end'); fx.end(knot + 1)
    fx.label('begin'); muzzle_at(fx, tip, 11, 70); fx.vcopy(fx.AT, tip); fx.call('seed'); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(13); fx.vcopy(fx.AT, tip); fx.call('ball'); fx.ret()
    seed = fx.pool('seed', 1)
    fx.begin('seed', seed, 'seed_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('seed_tick'); fx.life(knot - 1); fx.ret()
    fx.label('seed_render')
    fx.lin(fx.T3, FRAME, 40, 60); fx.lin(fx.F1, fx.T3, 15, 0, 10)
    fx.sprite(POS, soft, fx.F1, cell=2); flicker(fx, POS, tint, fx.T3, (0, 1), clut=1, every=1); fx.ret()
    homing(fx, 'ball', 1, fly, 'ball_render', 'ball_arrive', every='ball_wake')
    fx.label('ball_wake'); fx.emit('arc', POS); fx.emit('arc2'); fx.ret()
    fx.label('ball_render')
    fx.sprite(POS, soft, 600, cell=2); flicker(fx, POS, tint, 420, (0, 1), clut=1, every=1); fx.ret()
    fx.label('ball_arrive')
    fx.sound(15); fx.aim(); fx.hit()
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 320, 10)
    fx.emit('flash', fx.TCHEST); fx.emit('shock'); fx.emit('fork', times=4); fx.emit('fork2', times=4)
    fx.emit('spark', times=12); fx.call('twitch'); fx.ret()
    twitch = fx.pool('twitch', 1)
    fx.begin('twitch', twitch, 'noop', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('twitch_tick')
    fx.life(9); fx.set(fx.T3, FRAME); fx.mod(fx.T3, 2); fx.br(fx.T3, '!=', 0, 'noop')
    fx.aim(); fx.emit('arc', fx.TCHEST, 2); fx.emit('arc2', times=2); fx.ret()
    return fx


# ----------------------------------------------------------------- Infermon
def hades_grenade():
    """Darkness gathers in Infermon's mouth into a black ball veined with fire; it is shot out straight, smoking, and
    what it strikes goes up in a pillar of hellfire under a cap of smoke. A target that moves out of its line is
    missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(HADES); fx.palette(SMOKE)
    fx.paint(0, magma(4)); fx.paint(1, magma(12)); fx.paint(2, glow(15, 1.2)); fx.paint(3, puff(29))
    fx.paint(4, ring(13, 2.2)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, clip((10 - polar()[0]) / 1.5))
    fx.paint(7, nukeball(33))
    tint, soft, dark = fx.colour(128, 128, 128), fx.colour(90, 20, 60), fx.colour(128, 128, 128)
    mouth = fx.vec()
    load = 7
    gather(fx, 'mote', 14, 5, (110, 40, 128), 90, 620, 6)
    fx.particle('soot', 16, 8, 3, (70, 60, 70), 150, grow=18, lift=6, clut=1, fade=True)
    fx.particle('pyre', 10, 10, 7, (128, 128, 128), (260, 360), grow=14, flat=((-10, 10), (-75, -45), (-10, 10)),
                spread=120, fade=True)
    fx.particle('cap', 3, 13, 3, (100, 90, 100), 300, grow=40, lift=50, clut=1, spread=100, fade=True)
    fx.particle('shock', 2, 8, 4, (128, 60, 40), 160, grow=95, fade=True, sy=6)
    fx.particle('cinder', 14, 13, 5, (128, 90, 50), (70, 130), grow=-6, speed=70, lift=70, gravity=9, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(load, 'fire')
    fx.br(fx.NOW, '>', load - 3, 'main_end'); fx.emit('mote', mouth, 2)
    fx.label('main_end'); fx.end(load + 1)
    fx.label('begin'); muzzle_at(fx, mouth, 6, 60); fx.vcopy(fx.AT, mouth); fx.call('core'); fx.sound(-55); fx.ret()
    fx.label('fire')
    fx.sound(3); fx.aim(); fx.vcopy(fx.AT, mouth); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('nade'); fx.ret()
    core = fx.pool('core', 1)
    fx.begin('core', core, 'core_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('core_tick'); fx.life(load - 1); fx.ret()
    fx.label('core_render')
    fx.lin(fx.T3, FRAME, 42, 50)
    fx.sprite(POS, dark, fx.T3, cell=6, blend='sub'); flicker(fx, POS, tint, fx.T3, (0, 1), every=2); fx.ret()
    fx.shot('nade', 1, 85, 22, 'nade_render', 'nade_arrive', miss='nade_miss', every='nade_wake')
    fx.label('nade_wake'); fx.emit('soot', POS); fx.ret()
    fx.label('nade_miss'); fx.emit('soot', POS, 4); fx.ret()
    fx.label('nade_render')
    fx.sprite(POS, soft, 520, cell=2)
    fx.sprite(POS, dark, 360, cell=6, blend='sub'); flicker(fx, POS, tint, 360, (0, 1), every=2); fx.ret()
    fx.label('nade_arrive')
    fx.sound(15)
    fx.emit('pyre', POS, 8); fx.emit('cinder', times=12)
    fx.vcopy(fx.AT, POS); fx.sub_(at(fx.AT, 1), 260); fx.call('cap', 3)
    fx.vcopy(fx.AT, POS); fx.add(at(fx.AT, 1), 200); fx.call('shock'); fx.ret()
    return fx


# ----------------------------------------------------------------- MarineAngemon
def ocean_love():
    """Three bubbles with a pink heart in each leave MarineAngemon one after another and float, swaying, after the
    target; each bursts on it into small hearts, and with the third a great heart opens over it."""
    fx = Fx(delay=8, cast_sound=45)
    fx.palette(PINK); fx.palette(AQUA)
    fx.paint(0, heart()); fx.paint(1, bubble()); fx.paint(2, glow(15, 1.2)); fx.paint(3, heart(6.0, 16.0))
    fx.paint(4, ring(13, 1.8)); fx.paint(5, star(4, 2, 9, 6))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 60, 100)
    front = fx.vec()
    first, gap, fly = 3, 5, 12
    fx.particle('mini', 14, 10, 1, (110, 128, 128), (50, 100), flat=((-8, 8), (-18, -6), (-8, 8)), clut=1,
                spread=120)
    fx.particle('pop', 3, 8, 4, (110, 128, 128), 160, grow=70, clut=1, fade=True)
    fx.particle('love', 18, 13, 3, (128, 128, 128), (110, 170), grow=-4, flat=((-28, 28), (-40, -14), (-28, 28)),
                spread=120)
    fx.particle('bloom', 1, 10, 0, (128, 128, 128), 260, grow=70, fade=True)
    fx.particle('twinkle', 12, 9, 5, (128, 128, 128), (70, 130), grow=-8, spread=420)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(3):
        fx.when(first + gap * k, 'blow')
    fx.end(first + 2 * gap + 1)
    fx.label('begin'); muzzle_at(fx, front, 6, 70); fx.vcopy(fx.AT, front); fx.call('last'); fx.sound(-55); fx.ret()
    last = fx.pool('last', 1)
    fx.begin('last', last, 'noop', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('last_tick'); fx.life(first + 2 * gap + fly + 3); fx.after(first + 2 * gap + fly + 1, 'last_go'); fx.ret()
    fx.label('last_go')
    fx.sound(2); fx.aim(); fx.vcopy(fx.AT, fx.TCHEST); fx.sub_(at(fx.AT, 1), 140); fx.call('bloom'); fx.ret()
    fx.label('blow'); fx.sound(34); fx.vcopy(fx.AT, front); fx.call('hb'); fx.ret()
    homing(fx, 'hb', 3, fly, 'hb_render', 'hb_arrive', every='hb_wake')
    fx.label('hb_wake'); fx.emit('mini', POS); fx.ret()
    fx.label('hb_render')
    fx.lin(fx.T, FRAME, 520); fx.sin(fx.T2, fx.T, 90)
    fx.vcopy(fx.TV, POS); fx.sub_(at(fx.TV, 1), fx.T2)
    fx.sprite(fx.TV, soft, 380, cell=2)
    fx.lin(fx.T3, fx.T2, 1, 0, 3); fx.add(fx.T3, 230); fx.sprite(fx.TV, tint, fx.T3, cell=0)
    fx.sprite(fx.TV, tint, 380, cell=1, clut=1); fx.ret()
    fx.label('hb_arrive')
    fx.sound(7); fx.aim(); fx.hit()
    fx.emit('pop', fx.TCHEST); fx.emit('love', times=6); fx.emit('twinkle', times=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Thundermon
def thunder_volt():
    """Current crackles on the two maces at Thundermon's sides; both let go at once, and two crooked strokes of
    lightning meet on the target and hold it for a moment in a cage of sparks."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(YELLOW); fx.palette(VOLT)
    fx.paint(0, bolt(11, 2.4, 9)); fx.paint(1, bolt(13, 2.4, 9)); fx.paint(2, glow(15, 1.2)); fx.paint(3, bolt(17, 1.5))
    fx.paint(4, ring(13, 1.8)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, star(6, 2.5, 12, 5))
    tint, soft = fx.colour(128, 128, 128), fx.colour(50, 70, 128)
    side, left, right = fx.vec(), fx.vec(), fx.vec()
    charge, hold = 8, 8
    fx.particle('crackle', 12, 3, 3, (128, 128, 128), (180, 280), spread=180, spin=1)
    fx.particle('lamp', 2, charge + hold, 6, (128, 128, 100), 60, grow=22, spin=20)
    fx.particle('jolt', 12, 3, 3, (128, 128, 128), (260, 380), spread=300, spin=1)
    fx.particle('cage', 2, 8, 4, (128, 128, 90), 420, grow=-30, fade=True)
    fx.particle('spark', 16, 10, 5, (128, 128, 90), (70, 130), grow=-8, speed=70, lift=30, gravity=6, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose')
    fx.br(fx.NOW, '>', charge - 1, 'main_end'); fx.emit('crackle', left); fx.emit('crackle', right)
    fx.label('main_end'); fx.end(charge + 1)
    fx.label('begin')
    sides(fx, side, 250); fx.vcopy(left, fx.CHEST); fx.vcopy(right, left); fx.vadd(left, side); fx.vsub(right, side)
    fx.emit('lamp', left); fx.emit('lamp', right); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(15); fx.vcopy(fx.AT, fx.SRC); fx.call('volt'); fx.ret()
    volt = fx.pool('volt', 1)
    fx.begin('volt', volt, 'volt_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('volt_tick')
    fx.life(hold); fx.aim(); fx.after(1, 'volt_hit')
    fx.emit('jolt', fx.TCHEST); fx.emit('spark', times=2); fx.ret()
    fx.label('volt_hit'); fx.aim(); fx.hit(); fx.sound(16); fx.emit('cage', fx.TCHEST, 2); fx.ret()
    fx.label('volt_render')
    fx.lin(fx.T3, FRAME, -22, 22 * hold + 60)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '==', 0, 'volt_b')
    band(fx, left, fx.TCHEST, fx.T3, tint, 0); band(fx, right, fx.TCHEST, fx.T3, tint, 1); fx.jmp('volt_glow')
    fx.label('volt_b')
    band(fx, left, fx.TCHEST, fx.T3, tint, 1); band(fx, right, fx.TCHEST, fx.T3, tint, 0)
    fx.label('volt_glow')
    fx.lin(fx.T3, fx.T3, 3); fx.sprite(fx.TCHEST, soft, fx.T3, cell=2, clut=1)
    fx.sprite(left, soft, 360, cell=2, clut=1); fx.sprite(right, soft, 360, cell=2, clut=1); fx.ret()
    return fx


# ----------------------------------------------------------------- Tylomon
def torpedo_attack():
    """Two torpedoes leap from Tylomon's back one after the other, arc over and dive at the spot where the target
    stands, leaving bubbles behind; each throws up a column of water there. Whoever has left the spot is not hit."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(STEEL); fx.palette(SEA)
    fx.paint(0, torpedo()); fx.paint(1, bubble()); fx.paint(2, glow(15, 1.2)); fx.paint(3, spout())
    fx.paint(4, ring(13, 2.2)); fx.paint(5, droplet())
    tint, soft = fx.colour(128, 128, 128), fx.colour(50, 100, 128)
    back, side = fx.vec(), fx.vec()
    first, gap, fly, high = 2, 5, 9, 300
    fx.particle('puffo', 2, 5, 2, (90, 120, 128), 140, grow=60, clut=1, fade=True)
    fx.particle('fizz', 18, 9, 1, (100, 128, 128), (50, 110), flat=((-8, 8), (-16, -4), (-8, 8)), clut=1, spread=70)
    fx.particle('jet', 2, 11, 3, (128, 128, 128), 330, grow=26, clut=1, sy=40, fade=True)
    fx.particle('wave', 2, 9, 4, (90, 120, 128), 200, grow=95, clut=1, fade=True, sy=6)
    fx.particle('drop', 20, 13, 5, (110, 128, 128), (80, 150), grow=-5, speed=55, lift=85, gravity=11, spread=100,
                clut=1)
    fx.label('main'); fx.when(0, 'begin'); fx.when(first, 'launch'); fx.when(first + gap, 'launch')
    fx.end(first + gap + 1)
    fx.label('begin')
    sides(fx, side, 130); fx.vcopy(back, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), 1, 40); fx.sub_(at(back, 1), fx.T3)
    fx.vsub(back, side); fx.sound(-55); fx.ret()
    fx.label('launch')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, back); fx.vadd(back, side); fx.vadd(back, side)
    fx.vcopy(fx.DEST, fx.TGT); fx.sub_(at(fx.DEST, 1), 80)
    fx.emit('puffo', fx.AT); fx.call('torp'); fx.ret()
    fx.travel('torp', 2, fly, 'torp_render', 'torp_arrive', every='torp_wake')
    fx.label('torp_wake'); hop(fx, fx.TV, fly, high); fx.emit('fizz', fx.TV, 2); fx.ret()
    fx.label('torp_render')
    hop(fx, fx.KEEP, fly, high)
    fx.sprite(fx.KEEP, soft, 420, cell=2, clut=1)
    dart(fx, fx.KEEP, 3, 140, tint, 0, blend=None); fx.ret()
    fx.label('torp_arrive')
    fx.sound(15); fx.strike(POS, 220)
    fx.vcopy(fx.AT, POS); fx.sub_(at(fx.AT, 1), 380); fx.call('jet')
    fx.vcopy(fx.AT, POS); fx.add(at(fx.AT, 1), 60); fx.call('wave'); fx.call('drop', 10); fx.ret()
    return fx


# ----------------------------------------------------------------- MetalTyrannomon
def nuclear_laser():
    """A living missile leaves MetalTyrannomon's arm on a thread of smoke and hunts its target down; where it lands
    the field goes white and a green fireball climbs on a stem of smoke while ash falls."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(NUKE); fx.palette(FLESH); fx.palette(SMOKE)
    fx.paint(0, missile()); fx.paint(1, puff(47)); fx.paint(2, glow(15, 1.2)); fx.paint(3, nukeball(41))
    fx.paint(4, ring(13, 2.2)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, column(19))
    tint, soft, wash = fx.colour(128, 128, 128), fx.colour(70, 128, 40), fx.vec()
    arm, side = fx.vec(), fx.vec()
    fire, fly = 3, 12
    land = fire + fly
    fx.particle('flash', 1, 5, 2, (110, 128, 60), 180, grow=70, fade=True)
    fx.particle('smoke', 16, 10, 1, (90, 90, 96), 110, grow=16, clut=2, fade=True)
    fx.particle('ball', 2, 14, 3, (128, 128, 128), 320, grow=60, lift=26, fade=True)
    fx.particle('stem', 6, 12, 1, (110, 110, 110), 230, grow=10, lift=14, clut=2, spread=60, fade=True)
    fx.particle('shock', 2, 9, 4, (110, 128, 60), 180, grow=120, fade=True, sy=6)
    fx.particle('fallout', 16, 16, 5, (110, 128, 60), (60, 110), grow=-3, flat=((-30, 30), (-50, -10), (-30, 30)),
                gravity=4, spread=260)
    fx.label('main'); fx.when(0, 'begin'); fx.when(fire, 'loose'); fx.end(land + 9)
    fx.label('draw')
    fx.br(fx.NOW, '<', land, 'noop'); fx.br(fx.NOW, '>', land + 6, 'noop')
    fx.lin(fx.T, fx.NOW, -16, 16 * (land + 7)); fx.lin(fx.T2, fx.T, 2, 0, 3)
    fx.vset(wash, fx.T2, fx.T, fx.T2); fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    sides(fx, side, 170); ahead(fx, arm, fx.CHEST, 60); fx.vadd(arm, side); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(3); fx.vcopy(fx.AT, arm); fx.call('flash'); fx.call('msl'); fx.ret()
    homing(fx, 'msl', 1, fly, 'msl_render', 'msl_arrive', every='msl_wake')
    fx.label('msl_wake')
    fx.lin(fx.T3, FRAME, 800); fx.sin(fx.T2, fx.T3, 70)
    fx.vcopy(fx.TV, iv(FREE)); fx.vmul(fx.TV, 2); fx.vcopy(fx.TV2, POS); fx.vsub(fx.TV2, fx.TV)
    fx.sub_(at(fx.TV2, 1), fx.T2); fx.emit('smoke', fx.TV2); fx.ret()
    fx.label('msl_render')
    fx.vcopy(fx.TV, iv(FREE)); fx.vmul(fx.TV, 3); fx.vcopy(fx.KEEP, POS); fx.vsub(fx.KEEP, fx.TV)
    fx.sprite(fx.KEEP, soft, 320, cell=2)
    dart(fx, POS, 4, 160, tint, 0, clut=1, blend=None); fx.ret()
    fx.label('msl_arrive')
    fx.sound(15); fx.aim(); fx.hit()
    fx.vcopy(fx.AT, fx.TCHEST); fx.call('ball', 2); fx.call('fallout', 14)
    fx.vcopy(fx.AT, fx.TGT); fx.sub_(at(fx.AT, 1), 80); fx.call('stem', 6); fx.call('shock', 2); fx.ret()
    return fx


# ----------------------------------------------------------------- Flymon
def brown_stinger():
    """Flymon's tail spits three long stingers in a burst, each a brown streak tipped with venom; they drive into the
    target one after another, and violet venom spatters from the wounds and bubbles up."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(STING); fx.palette(VENOM)
    fx.paint(0, needle()); fx.paint(1, glow(15, 1.2)); fx.paint(2, blob()); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, ring(13, 2.2)); fx.paint(5, droplet())
    tint, soft = fx.colour(128, 128, 128), fx.colour(90, 40, 128)
    tail = fx.vec()
    landed = fx.const(0)
    first, gap, fly = 4, 3, 4
    fx.particle('buzz', 6, 4, 3, (128, 110, 60), (80, 140), grow=-10, spread=200)
    fx.particle('drip', 12, 7, 5, (128, 128, 128), (60, 100), grow=-6, gravity=5, clut=1)
    fx.particle('splat', 3, 7, 4, (128, 128, 128), 110, grow=60, clut=1, fade=True)
    fx.particle('ooze', 15, 11, 5, (128, 128, 128), (80, 140), grow=-5, speed=50, lift=40, gravity=9, spread=50,
                clut=1)
    fx.particle('prick', 3, 5, 3, (128, 128, 128), 380, grow=-50)
    fx.particle('miasma', 10, 14, 2, (128, 128, 128), (70, 150), grow=4, flat=((-8, 8), (-26, -10), (-8, 8)),
                clut=1, spread=260)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(3):
        fx.when(first + gap * k, 'fire')
    fx.br(fx.NOW, '>', first, 'main_end'); fx.emit('buzz', tail)
    fx.label('main_end'); fx.end(first + 2 * gap + 1)
    fx.label('begin'); muzzle_at(fx, tail, 3, 70); fx.sound(-55); fx.ret()
    fx.label('fire')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, tail); fx.vcopy(fx.DEST, fx.TCHEST); fx.scatter(fx.DEST, 140)
    fx.call('sting'); fx.ret()
    fx.travel('sting', 3, fly, 'sting_render', 'sting_arrive', every='sting_wake')
    fx.label('sting_wake'); fx.emit('drip', POS); fx.ret()
    fx.label('sting_render')
    dart(fx, POS, 3, 85, tint, 0); fx.sprite(POS, soft, 200, cell=1, clut=1); fx.ret()
    fx.label('sting_arrive')
    fx.sound(16); fx.aim(); fx.hit(); fx.add(landed, 1)
    fx.emit('prick', POS); fx.emit('splat'); fx.emit('ooze', times=5)
    fx.br(landed, '<', 3, 'noop')
    fx.emit('miasma', fx.TCHEST, 10); fx.ret()
    return fx


# ----------------------------------------------------------------- Mushroomon
def fungus_cruncher():
    """Mushroomon lobs a small toadstool, tumbling, at its target; it bursts over it in a violet cloud that hangs
    there shedding spores."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(SHROOM); fx.palette(SPORE)
    fx.paint(0, mushroom()); fx.paint(1, puff(31)); fx.paint(2, glow(15, 1.2)); fx.paint(3, spores(3))
    fx.paint(4, spores(8)); fx.paint(5, ring(13, 2.2)); fx.paint(6, puff(37))
    tint, soft = fx.colour(128, 128, 128), fx.colour(80, 40, 110)
    hand = fx.vec()
    throw, fly, high, hang = 3, 10, 440, 10
    fx.particle('trail', 12, 8, 3, (128, 128, 128), (120, 180), grow=6, clut=1, spin=10, fade=True)
    fx.particle('cloud', 8, 13, 1, (100, 70, 120), (260, 360), grow=22, lift=5, clut=1, spread=320, fade=True)
    fx.particle('cloud2', 6, 13, 6, (110, 90, 128), (220, 320), grow=24, lift=8, clut=1, spread=260, fade=True)
    fx.particle('spore', 12, 14, 3, (128, 128, 128), (200, 300), grow=8, speed=14, clut=1, spread=260, spin=8,
                fade=True)
    fx.particle('spore2', 12, 14, 4, (128, 128, 128), (200, 300), grow=8, speed=14, clut=1, spread=260, spin=-8,
                fade=True)
    fx.particle('ringp', 1, 8, 5, (110, 70, 128), 140, grow=90, clut=1, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(throw, 'loose'); fx.end(throw + 1)
    fx.label('begin'); muzzle_at(fx, hand, 9, 40); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, hand); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('cap'); fx.ret()
    fx.travel('cap', 1, fly, 'cap_render', 'cap_arrive', every='cap_wake')
    fx.label('cap_wake'); hop(fx, fx.TV, fly, high); fx.emit('trail', fx.TV); fx.ret()
    fx.label('cap_render')
    hop(fx, fx.TV, fly, high); fx.lin(fx.T3, FRAME, 42)
    fx.sprite(fx.TV, tint, 300, cell=0, blend=None, rot=fx.T3); fx.ret()
    fx.label('cap_arrive')
    fx.sound(7); fx.aim(); fx.hit()
    fx.emit('ringp', fx.TCHEST); fx.emit('cloud', times=6); fx.emit('cloud2', times=4)
    fx.emit('spore', times=5); fx.emit('spore2', times=5); fx.call('haze'); fx.ret()
    haze = fx.pool('haze', 1)
    fx.begin('haze', haze, 'noop', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('haze_tick')
    fx.life(hang); fx.set(fx.T3, FRAME); fx.mod(fx.T3, 2); fx.br(fx.T3, '!=', 0, 'noop')
    fx.aim(); fx.emit('spore', fx.TCHEST); fx.emit('spore2'); fx.emit('cloud2'); fx.ret()
    return fx


# ----------------------------------------------------------------- ExTyrannomon
def pretty_attack():
    """A kiss pops on ExTyrannomon's lips and turns into a big beating heart that drifts after the target, dropping
    little hearts; it breaks over it, and hearts and stars go round and round its head."""
    fx = Fx(delay=8, cast_sound=45)
    fx.palette(KISS); fx.palette(GOLD)
    fx.paint(0, heart()); fx.paint(1, lips()); fx.paint(2, glow(15, 1.2)); fx.paint(3, heart(6.0, 16.0))
    fx.paint(4, star(5, 3.5, 10, 3)); fx.paint(5, ring(13, 2.0))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 50, 80)
    mouth = fx.vec()
    smack, fly, daze_life = 6, 13, 14
    fx.particle('little', 14, 11, 3, (128, 128, 128), (110, 160), grow=-6, flat=((-8, 8), (4, 14), (-8, 8)),
                spread=80)
    fx.particle('burst', 1, 8, 0, (128, 128, 128), None, grow=80, fade=True)
    fx.particle('halo', 2, 8, 5, (128, 70, 100), 150, grow=90, fade=True)
    fx.particle('fly', 12, 12, 3, (128, 128, 128), (120, 180), grow=-5, speed=60, lift=40, gravity=6, spread=60)
    fx.particle('twink', 10, 10, 4, (128, 128, 128), (90, 150), grow=-7, speed=60, lift=30, gravity=4, clut=1,
                spread=60, spin=14)
    fx.label('main'); fx.when(0, 'begin'); fx.when(smack, 'blow'); fx.end(smack + 1)
    fx.label('begin'); muzzle_at(fx, mouth, 8, 70); fx.vcopy(fx.AT, mouth); fx.call('kiss'); fx.sound(-55); fx.ret()
    fx.label('blow'); fx.sound(34); fx.vcopy(fx.AT, mouth); fx.call('big'); fx.ret()
    kiss = fx.pool('kiss', 1)
    fx.begin('kiss', kiss, 'kiss_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('kiss_tick'); fx.life(smack + 1); fx.ret()
    fx.label('kiss_render')                 # the lips pop out big, settle, and fade into the heart
    fx.lin(fx.T3, FRAME, 150, 80); fx.br(FRAME, '<', 3, 'kiss_draw')
    fx.lin(fx.T3, FRAME, -40, 500)
    fx.label('kiss_draw')
    fx.lin(fx.T2, fx.T3, 13, 0, 10); fx.sprite(POS, soft, fx.T2, cell=2); fx.sprite(POS, tint, fx.T3, cell=1); fx.ret()
    homing(fx, 'big', 1, fly, 'big_render', 'big_arrive', every='big_wake')
    fx.label('big_wake'); fx.emit('little', POS); fx.ret()
    fx.label('big_render')
    fx.lin(fx.T, FRAME, 1024); fx.sin(fx.T2, fx.T, 60); fx.lin(fx.T3, fx.T2, 1, 400)
    fx.lin(fx.F1, fx.T3, 14, 0, 10); fx.sprite(POS, soft, fx.F1, cell=2); fx.sprite(POS, tint, fx.T3, cell=0); fx.ret()
    fx.label('big_arrive')
    fx.sound(7); fx.aim(); fx.hit()
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 320, 10)
    fx.emit('burst', fx.TCHEST); fx.emit('halo'); fx.emit('fly', times=8); fx.emit('twink', times=8)
    fx.vcopy(fx.AT, fx.TGT); fx.lin(fx.T3, at(fx.TSIZE, 1), 1, 60); fx.sub_(at(fx.AT, 1), fx.T3); fx.call('daze')
    fx.ret()
    daze = fx.pool('daze', 1)
    fx.begin('daze', daze, 'daze_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('daze_tick'); fx.life(daze_life); fx.after(4, 'daze_ring'); fx.ret()
    fx.label('daze_ring'); fx.sound(34); fx.ret()
    fx.label('daze_render')
    for k in range(6):
        fx.lin(fx.T, FRAME, 300, 683 * k); fx.circle(fx.TV, fx.T, 240, 0); fx.sin(at(fx.TV, 1), fx.T, 40)
        fx.vadd(fx.TV, POS)
        if k % 2:
            fx.lin(fx.T2, FRAME, 30); fx.sprite(fx.TV, tint, 150, cell=4, clut=1, rot=fx.T2)
        else:
            fx.sprite(fx.TV, tint, 170, cell=3)
    fx.ret()
    return fx


EFFECTS = {126: brachio_bubble, 182: poison_wing, 183: sticky_net, 190: celestial_arrow, 218: harpoon_torpedo,
           226: top_gun, 233: boiling_bubble, 235: flame_bomber, 240: coral_crusher, 241: thunder_ball,
           246: hades_grenade, 248: ocean_love, 252: thunder_volt, 254: torpedo_attack, 260: nuclear_laser,
           262: brown_stinger, 263: fungus_cruncher, 266: pretty_attack}
