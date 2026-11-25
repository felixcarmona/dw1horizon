"""Finishers that reach every enemy, written and painted here, one per species (keyed by species id). Each one is
its Digimon's own attack: its pictures, how it crosses the field and what it leaves on each enemy."""
import math

import numpy as np

from tools.technique_effects.finishers import band, flicker, gather
from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, fbm, glow, grid, iv, polar, ring, \
    segment, star

CHITIN = ['#000000', '#0c2810', '#3a7a28', '#a8e060', '#f0ffc0', '#ffffff']
SHELL = ['#1a0e04', '#4a2c10', '#8a5a20', '#d8b060', '#fff0c0']
DARKFIRE = ['#000000', '#3a0000', '#a01000', '#f05000', '#ffb020', '#fff0a0']
BONE = ['#201810', '#6a5a40', '#c8b890', '#f8f0d8', '#ffffff']
DUST = ['#000000', '#302418', '#70583c', '#b89c70', '#e8d8b0']
WATER = ['#000000', '#082060', '#1860c0', '#50b0f0', '#c0f0ff', '#ffffff']
PETAL = ['#000000', '#600030', '#d02070', '#ff80b0', '#ffe0f0', '#ffffff']
LEAF = ['#000000', '#083808', '#289020', '#80e050', '#e0ffb0']
MOLTEN = ['#140808', '#402018', '#a03010', '#ff7010', '#ffd060', '#ffffff']
GHOSTFIRE = ['#000000', '#081050', '#1848d0', '#40b0ff', '#c0f0ff', '#ffffff']
ABYSS = ['#000000', '#081828', '#104858', '#30909a', '#a0e0d8', '#e8fff8']
PUMPKIN = ['#201000', '#803000', '#e06000', '#ff9818', '#ffd860', '#ffffff']
CANDY = ['#000000', '#500858', '#c030c0', '#ff90e0', '#ffffff']
STEEL = ['#101018', '#404860', '#8898b8', '#d0e0f8', '#ffffff']
VOLT = ['#000000', '#403000', '#c09000', '#ffe040', '#ffffc0', '#ffffff']
CANNON = ['#000000', '#402000', '#c05000', '#ffa020', '#ffe890', '#ffffff']
SMOKE = ['#000000', '#181818', '#484848', '#909090', '#d0d0d0']
RED = ['#000000', '#500008', '#d01810', '#ff7040', '#ffe0c0']
BLUE = ['#000000', '#081060', '#2050e0', '#70b0ff', '#ffffff']
AMBER = ['#000000', '#403000', '#c08800', '#ffd840', '#ffffe0']
SKYGOLD = ['#000000', '#403000', '#b08820', '#ffe070', '#ffffff']
DIGI = ['#000000', '#003010', '#00a030', '#40ff60', '#d0ffd0']
BOMB = ['#101020', '#303048', '#707088', '#d0d0e0', '#ff8020']
DARKSONG = ['#000000', '#200030', '#6010a0', '#c040e0', '#ffa0ff']
BRASS = ['#000000', '#604000', '#e0a000', '#ffe060', '#ffffff']
HELLFIRE = ['#000000', '#300010', '#900020', '#e03010', '#ff9040', '#ffe0a0']
JADE = ['#000000', '#003828', '#10a070', '#70f0b0', '#f0fff0']
PAPERWHITE = ['#404840', '#a0b0a0', '#e8f0e0', '#ffffff']
ROCK = ['#100808', '#3a2818', '#806040', '#c0a070', '#f0e0b0']
GLOOM = ['#000000', '#200040', '#6020a0', '#b060f0', '#f0d0ff']
DRUM = ['#180000', '#700808', '#c81818', '#e8a030', '#fff0b0']
SPINE = ['#000000', '#102040', '#2070a0', '#70d0e0', '#f0ffff']
VENOM = ['#000000', '#300838', '#8020a0', '#e060f0', '#ffd0ff']


# ----------------------------------------------------------------- paintings
def pincer(flip=False):
    """One jaw of a stag beetle: a toothed crescent open to one side."""
    x, y = grid()
    if flip:
        x = 32 - x
    r, ang = np.hypot(x - 16, y - 16), np.arctan2(y - 16, x - 16)
    lum = clip((14 - r) / 1.5) * clip((np.hypot(x - 21.5, y - 16) - 11.5) / 1.5)
    return clip(lum * (0.72 + 0.28 * np.cos(ang * 9)) * (0.65 + 0.35 * clip((r - 8) / 5)))


def cut(turn):
    """A straight cut: a line that thins to a point at both ends."""
    c, s = math.cos(turn), math.sin(turn)
    x, y = grid()
    u, v = (x - 16) * c + (y - 16) * s, -(x - 16) * s + (y - 16) * c
    w = 2.6 * clip(1 - (np.abs(u) / 15.5) ** 2)
    return clip(1.3 - np.abs(v) / np.maximum(w, 0.15)) * (np.abs(u) < 15.5)


def horn(lean=0.0):
    """A horn of a shell: a ridged cone, its point up."""
    x, y = grid()
    t = clip((y - 2) / 28)
    d = np.abs(x - 16 - lean * (1 - t) * 6) / (1 + 8 * t)
    return (d < 1) * (y > 2) * (y < 30) * clip(0.4 + 0.5 * clip(1 - d) + 0.14 * np.sin(y * 1.3))


def gout(seed):
    """A gout of flame: a ragged mass with a hot heart, off-centre."""
    x, y = grid()
    r = np.hypot((x - 15) / 1.25, y - 16)
    return clip(1 - r / (8.5 + 5 * fbm(seed))) ** 0.6 * (0.55 + 0.7 * fbm(seed + 3))


def lick(seed):
    """A flame that curls to one side as it rises."""
    x, y = grid()
    t = clip((y - 2) / 28)
    cx = 16 + 6 * (1 - t) ** 2 * math.cos(seed) + 2 * np.sin(t * 7 + seed)
    w = 6.5 * t ** 0.7 * np.sqrt(clip(1 - (clip(t - 0.75) / 0.25) ** 2))
    return clip(1.2 - np.abs(x - cx) / np.maximum(w, 0.3)) * (y > 2) * (0.4 + 0.8 * t) * (0.8 + 0.4 * fbm(int(seed * 7) + 1))


def bone():
    """A long bone: a shaft with two knuckles at each end."""
    x, y = grid()
    lum = 0.75 * segment(7, 16, 25, 16, 3.4)
    for cx, cy in ((6, 12), (6, 20), (26, 12), (26, 20)):
        lum = np.maximum(lum, clip((4.4 - np.hypot(x - cx, y - cy)) / 1.3))
    return clip(lum * (0.6 + 0.4 * clip((20 - y) / 9)) + 0.25 * (lum > 0.3))


def crest(seed):
    """A wave seen from the side: a body of water under a line of foam that curls."""
    x, y = grid()
    top = 9 + 5 * np.cos((x - 8 - seed) / 32 * 2 * np.pi) + 2.5 * fbm(seed + 60)
    body = clip((y - top) / 2.5) * (0.4 + 0.4 * clip(1 - (y - top) / 20))
    foam = clip(1 - np.abs(y - top) / 2.4)
    return clip(body + 0.95 * foam) * clip((31.5 - y) / 5 + 0.2)


def note(double=False):
    """A written note: a head, a stem and a flag (two heads under a beam when double)."""
    x, y = grid()
    heads = [(11, 24)] if not double else [(8, 24), (21, 22)]
    lum = np.zeros((32, 32))
    for hx, hy in heads:
        lum = np.maximum(lum, clip((1 - np.hypot((x - hx) / 4.6, (y - hy) / 3.4)) * 3))
        lum = np.maximum(lum, segment(hx + 4, hy, hx + 4, hy - 17, 1.3))
    if double:
        lum = np.maximum(lum, segment(12, 7, 25, 5, 2.0))
    else:
        lum = np.maximum(lum, segment(15, 7, 22, 12, 1.8))
    return clip(lum)


def drop():
    """A falling drop: round below, a point above."""
    x, y = grid()
    ball = clip((6.5 - np.hypot(x - 16, y - 21)) / 1.5)
    tip = clip(1.3 - np.abs(x - 16) / np.maximum((y - 5) * 0.42, 0.2)) * (y > 5) * (y < 21)
    return clip(np.maximum(ball, tip) * (0.6 + 0.4 * clip(1 - np.hypot(x - 14, y - 19) / 5)))


def flower(turn=0.0):
    """A flower thrown as a blade: five pointed petals round a bright eye."""
    r, ang = polar()
    edge = 3.5 + 10.5 * np.abs(np.cos((ang + turn) * 2.5)) ** 1.6
    return clip(clip((edge - r) / 1.4) * (0.45 + 0.55 * clip(r / 11)) + clip((3.2 - r) / 1.2))


def leaf():
    x, y = grid()
    u, v = (x - 16) * 0.7 + (y - 16) * 0.7, -(x - 16) * 0.7 + (y - 16) * 0.7
    return clip(clip(1.2 - ((u / 13) ** 2 + (v / 4.5) ** 2)) * (0.55 + 0.45 * clip(1 - np.abs(v) / 1.2)))


def molten(seed):
    """A ball of metal: a white-hot inside showing through a dark crust."""
    r, _ = polar()
    crust = fbm(seed)
    inside = np.where(crust > 0.5, 0.2, 0.55 + 0.9 * (0.5 - crust))
    return clip((r < 12.5) * inside + clip(1 - np.abs(r - 12.5) / 2.0) * 0.8)


def gust(seed):
    """A streak of wind: a wavering line with a thinner one beside it, pointed at both ends."""
    x, y = grid()
    taper = clip(np.sin(x / 32 * np.pi)) ** 0.6
    a = clip(1.2 - np.abs(y - 15 - 3 * np.sin(x / 5.0 + seed)) / (1 + 3.2 * taper))
    b = 0.6 * clip(1.2 - np.abs(y - 23 - 2 * np.sin(x / 4.0 + seed * 2)) / (0.6 + 1.4 * taper))
    return clip(np.maximum(a, b) * taper * (0.6 + 0.6 * fbm(seed + 70)))


def curl():
    """A curl of mist: a spiral that widens outwards."""
    r, ang = polar()
    turn = (ang + np.pi) / (2 * np.pi)
    return clip(1 - np.abs(r - (3 + 9.5 * turn)) / (0.8 + 2.6 * turn)) * (0.4 + 0.6 * turn)


def pumpkin(lit=False):
    """A carved pumpkin: ribs, a stem, two eyes and a jagged mouth (dark, or burning when lit)."""
    x, y = grid()
    d = np.hypot((x - 16) / 13.5, (y - 18.5) / 11)
    body = (d < 1) * (0.6 + 0.2 * np.cos((x - 16) / 13.5 * np.pi * 2.6) - 0.15 * d)
    stem = ((np.abs(x - 16.5) < 1.8) & (y > 4) & (y < 9)) * 0.32
    eyes = ((np.abs(x - 10.5) < (y - 11) * 0.8) | (np.abs(x - 21.5) < (y - 11) * 0.8)) & (y > 11) & (y < 16.5)
    mouth = (y > 20) & (y < 25) & (np.abs(x - 16) < 8.5) & ((((x - 0.5) // 2.5) % 2 == 0) | (y < 22.5))
    return np.where((eyes | mouth) & (d < 0.95), 1.0 if lit else 0.1, np.maximum(body, stem))


def rind():
    """A broken piece of pumpkin."""
    x, y = grid()
    r = np.hypot(x - 16, y - 22)
    return clip((r < 12) * (r > 6) * (np.abs(x - 16) < (22 - y) * 0.9) * (0.5 + 0.4 * (r > 10)))


def axe():
    """A two-headed axe on a short haft."""
    x, y = grid()
    haft = 0.42 * segment(16, 30, 16, 5, 1.5)
    r = np.hypot(x - 16, y - 10)
    blade = (r < 12) & (r > 3) & (np.abs(y - 10) < 2.5 + 0.8 * np.abs(x - 16)) & (np.abs(x - 16) > 2.5)
    return clip(np.maximum(haft, blade * (0.55 + 0.45 * clip((r - 8.5) / 2.5))))


def bolt(seed, width=2.0):
    """A stroke of lightning from the top of the cell to its foot, with a fork."""
    r = np.random.default_rng(seed)
    pts = [(16 + (r.random() - 0.5) * 17 * (0 < k < 7), 4.5 * k) for k in range(8)]
    lum = np.zeros((32, 32))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        lum = np.maximum(lum, segment(x0, y0, x1, y1, width))
    fork = segment(pts[3][0], pts[3][1], pts[3][0] + (8 if seed % 2 else -8), pts[3][1] + 8, width * 0.6)
    return clip(np.maximum(lum, 0.75 * fork))


def gash():
    """What an axe leaves: a wedge, wide at one end."""
    x, y = grid()
    u, v = (x - 16) * 0.8 + (y - 16) * 0.6, -(x - 16) * 0.6 + (y - 16) * 0.8
    return clip(1.3 - np.abs(v) / np.maximum(0.3 + 3.6 * clip((u + 14) / 28), 0.2)) * (np.abs(u) < 14)


def shell_round():
    """A cannon shell flying to the right: a driving band, a rounded nose."""
    x, y = grid()
    body = (x > 5) & (x < 19) & (np.abs(y - 16) < 5.5)
    nose = (x >= 19) & (np.hypot((x - 19) / 9.0, (y - 16) / 5.5) < 1)
    stripe = (np.abs(x - 9) < 1.3) & (np.abs(y - 16) < 5.5)
    return clip((body | nose) * (0.55 + 0.4 * clip(1 - np.abs(y - 14) / 4)) + stripe * 0.4)


def burstball(seed):
    """An explosion: a ragged ball of fire with spikes."""
    r, ang = polar()
    edge = 6 + 6.5 * np.abs(np.cos(ang * 3.5 + seed)) ** 2 + 3.5 * fbm(seed)
    return clip(1 - r / edge) ** 0.5 * (0.6 + 0.6 * fbm(seed + 9))


def force(seed):
    """A ball of force: two arms of light winding into a bright heart."""
    r, ang = polar()
    arms = 0.5 + 0.5 * np.cos(ang * 2 + r * 0.75 + seed)
    return clip(clip(1 - r / 13.5) ** 0.5 * (0.3 + 0.7 * arms) + clip(1 - r / 5) ** 1.2)


def trefoil():
    """Three lobes of light from one heart."""
    r, ang = polar()
    return clip(1 - r / (4 + 10.5 * np.abs(np.cos(ang * 1.5 + np.pi / 2)) ** 3)) ** 0.6


def bladearc():
    """A blade of air seen from ahead: a wide bow, thick at its middle, with a haze under it."""
    x, y = grid()
    yc = 7 + 15 * ((x - 16) / 16.0) ** 2
    w = 3.2 * clip(1 - (np.abs(x - 16) / 16.0) ** 2) ** 0.6
    edge = clip(1.3 - np.abs(y - yc) / np.maximum(w, 0.2))
    haze = 0.3 * clip(1 - (y - yc) / 9.0) * (y > yc) * clip(1 - np.abs(x - 16) / 14.0)
    return clip(edge + haze)


def ripple():
    """Two thin arcs, one inside the other: air pushed aside."""
    r, ang = polar(16, 30)
    inside = np.abs(ang + np.pi / 2) < 1.05
    return clip(np.maximum(clip(1 - np.abs(r - 25) / 1.3), 0.7 * clip(1 - np.abs(r - 17) / 1.1)) * inside)


def feather():
    x, y = grid()
    u, v = (x - 16) * 0.6 + (y - 16) * 0.8, -(x - 16) * 0.8 + (y - 16) * 0.6
    vane = clip(1.2 - ((u / 14) ** 2 + (v / 4.2) ** 2))
    barbs = 0.7 + 0.3 * np.cos((u + np.abs(v) * 1.5) * 1.6)
    return clip(np.maximum(vane * barbs * 0.75, clip(1 - np.abs(v) / 0.9) * (np.abs(u) < 15)))


def bomb():
    """A round bomb with a lit fuse (the palette's last colour is the spark)."""
    x, y = grid()
    r = np.hypot(x - 15, y - 19)
    ball = (r < 9.5) * (0.3 + 0.5 * clip(1 - np.hypot(x - 11.5, y - 15) / 4.5))
    fuse = 0.55 * segment(20, 12, 24, 6, 1.2)
    spark = clip((2.6 - np.hypot(x - 25, y - 5)) / 1.0)
    return np.where(spark > 0.3, 1.0, np.maximum(ball, fuse))


def pixel():
    """A square of light with a brighter edge."""
    x, y = grid()
    d = np.maximum(np.abs(x - 16), np.abs(y - 16))
    return (d < 10) * (0.55 + 0.45 * (d > 7.5))


def brackets():
    """The four corners of a square: a target marker."""
    x, y = grid()
    d = np.maximum(np.abs(x - 16), np.abs(y - 16))
    corner = (np.abs(x - 16) > 7) & (np.abs(y - 16) > 7)
    cross = ((np.abs(x - 16) < 0.9) | (np.abs(y - 16) < 0.9)) & (d < 4)
    return 1.0 * (((d < 14.5) & (d > 12) & corner) | cross)


def digits(swap=False):
    """A one and a nought."""
    one, nought = (9, 23) if not swap else (23, 9)
    x, y = grid()
    lum = np.maximum(segment(one, 6, one, 26, 1.5), segment(one - 3, 9, one, 6, 1.3))
    r = np.hypot((x - nought) / 5.0, (y - 16) / 10.0)
    return clip(np.maximum(lum, clip(1 - np.abs(r - 0.85) * 5)))


def soundarc():
    """Sound leaving a mouth: three arcs, each wider than the last."""
    r, ang = polar(2, 16)
    lum = np.zeros((32, 32))
    for k, rad in enumerate((9, 17, 25)):
        lum = np.maximum(lum, clip(1 - np.abs(r - rad) / (1.2 + 0.4 * k)) * (np.abs(ang) < 0.5 + 0.12 * k))
    return clip(lum)


def spirit(seed):
    """A ball of dark power: a bright skin, a churning inside and two slanted eyes."""
    r, _ = polar()
    eyes = np.maximum(segment(9.5, 13, 13.5, 16, 1.4), segment(22.5, 13, 18.5, 16, 1.4))
    return clip(clip(1 - np.abs(r - 12) / 2.4) + (r < 12) * (0.15 + 0.45 * fbm(seed)) + 0.9 * eyes * (r < 11))


def hellflame(seed):
    """A flame with two hollow eyes in it."""
    x, y = grid()
    t = clip((y - 1) / 30)
    w = 11 * t ** 0.6 * np.sqrt(clip(1 - (clip(t - 0.8) / 0.2) ** 2))
    d = np.abs(x - 16 - 2.5 * np.sin(t * 6 + seed)) / np.maximum(w, 0.3)
    eyes = np.maximum(segment(10, 18, 14, 21, 1.7), segment(22, 18, 18, 21, 1.7))
    return clip(1.2 - d) * (y > 1) * (0.45 + 0.65 * t) * (0.75 + 0.5 * fbm(seed)) * (1 - 0.92 * eyes)


def shide():
    """A paper streamer of a shrine: a strip folded in zigzag."""
    pts = [(11, 1), (21, 7), (11, 13), (21, 19), (11, 25), (19, 31)]
    lum = np.zeros((32, 32))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        lum = np.maximum(lum, clip(segment(x0, y0, x1, y1, 3.0) * 3))
    return clip(lum * (0.75 + 0.25 * fbm(90)))


def streak():
    """A line of moving air for a band: a bright thread in a soft sheath, pointed at both ends."""
    x, y = grid()
    taper = clip(np.sin(x / 32 * np.pi)) ** 0.5
    return clip(clip(1.2 - np.abs(y - 16) / (0.8 + 2.2 * taper)) + 0.35 * clip(1 - np.abs(y - 16) / 9.0)) * taper


def spike(seed):
    """A shard of rock thrust up: a jagged point, one face in the light."""
    x, y = grid()
    t = clip((y - 1) / 30)
    cx = 16 + 4 * (1 - t) * math.sin(seed)
    w = 1 + 10 * t + 1.5 * np.sin(y * 0.9 + seed)
    d = (x - cx) / w
    return (np.abs(d) < 1) * (y > 1) * clip(0.32 + 0.38 * (d < -0.1) + 0.25 * fbm(seed + 20) + 0.2 * (np.abs(d) > 0.8))


def pebble():
    r, _ = polar()
    x, y = grid()
    return clip((r < 5 + 3 * fbm(77)) * (0.45 + 0.4 * (y < 16)))


def drum():
    """A thunder drum: a golden rim, a red skin and three commas turning on it."""
    x, y = grid()
    r = np.hypot(x - 16, y - 16)
    lum = np.where(r < 12.5, 0.55, 0.0)
    for k in range(3):
        a = 2 * np.pi * k / 3
        cx, cy = 16 + 5.5 * math.cos(a), 16 + 5.5 * math.sin(a)
        head = np.hypot(x - cx, y - cy) < 3.1
        ang = np.arctan2(y - 16, x - 16)
        tail = (np.abs(r - 7.5) < 1.3) & (((ang - a) % (2 * np.pi)) < 1.3)
        lum = np.where((head | tail) & (r < 12), 0.1, lum)
    return np.where(np.abs(r - 13.3) < 1.5, 1.0, lum)


def needle():
    """A spine for a band: thick at its root, a point at its tip."""
    x, y = grid()
    w = 0.3 + 3.0 * (1 - x / 32.0)
    return clip(1.25 - np.abs(y - 16) / w) * (x > 1) * (0.6 + 0.4 * (y < 16))


def puffball():
    """A blown-up fish: a round body bristling with spines."""
    r, ang = polar()
    edge = 8 + 6 * np.abs(np.cos(ang * 7)) ** 5
    return clip(clip((edge - r) / 1.2) * (0.5 + 0.3 * fbm(13)) + 0.5 * clip(1 - np.abs(r - 8) / 1.5))


# ----------------------------------------------------------------- shared pieces
def to_target(fx, out, length=None):
    """out = the way from the caster to the target on the ground plane (scaled to `length` when given)."""
    ok = fx.label()
    fx.vcopy(out, fx.TGT); fx.vsub(out, fx.SRC); fx.set(at(out, 1), 0)
    if length is None:
        return
    fx.vlen(fx.T, out); fx.br(fx.T, '>', 0, ok); fx.set(fx.T, 1)
    fx.label(ok)
    fx.vmul(out, length); fx.vdiv(out, fx.T)


def side(fx, out, src):
    """out = src turned a quarter on the ground plane."""
    fx.lin(at(out, 0), at(src, 2), -1); fx.set(at(out, 1), 0); fx.set(at(out, 2), at(src, 0))


def part(fx, out, a, b, num, den):
    """out = a + (b - a) * num / den (num may be a variable)."""
    fx.vcopy(out, b); fx.vsub(out, a); fx.vmul(out, num); fx.vdiv(out, den); fx.vadd(out, a)


def dim(fx, vec, life, top=128):
    """vec = a grey that goes from `top` to black over an instance's life."""
    fx.lin(fx.T, FRAME, -top, top, life + 1); fx.vset(vec, fx.T, fx.T, fx.T)


def window(fx, lo, hi, body):
    """In a handler: run body() only between those frames of the instance."""
    skip = fx.label()
    fx.br(FRAME, '<', lo, skip); fx.br(FRAME, '>', hi, skip)
    body()
    fx.label(skip)


def stand(fx, name, count, life, draw, tick=None, fields=1):
    """Define the routine `name`: an instance that stays at AT for `life` ticks, keeping SZ as its size (iv(FREE));
    draw(size) paints it every frame and tick(size) runs every tick."""
    pool = fx.pool(name, count, fields)
    size = iv(FREE)
    fx.begin(name, pool, name + '_render', inherit=False); fx.vcopy(POS, fx.AT); fx.set(size, fx.SZ); fx.ret()
    fx.label(name + '_tick'); fx.life(life)
    if tick:
        tick(size)
    fx.ret()
    fx.label(name + '_render'); draw(size); fx.ret()
    return size


def lob(fx, name, count, ticks, height, body, arrive, every=None):
    """Define the routine `name`: something thrown from AT to DEST in `ticks` ticks along an arc `height` tall;
    body(pos) paints it at its place on the arc."""
    fx.travel(name, count, ticks, name + '_render', arrive, every=every)
    fx.label(name + '_render')
    fx.set(fx.T, ticks); fx.sub_(fx.T, FRAME); fx.mul(fx.T, FRAME); fx.lin(fx.T, fx.T, 4 * height, 0, ticks * ticks)
    fx.vcopy(fx.TV, POS); fx.sub_(at(fx.TV, 1), fx.T)
    body(fx.TV); fx.ret()


def streaks(fx, name, count, life, cell, colour, half, tail, clut=0):
    """Define the routine `name`: a streak born at AT that flies DEST a tick (a velocity), drawn as a band from
    its head back `tail` steps."""
    pool = fx.pool(name, count, 3)
    vel, col = iv(FREE), fx.colour(*colour)
    fx.begin(name, pool, name + '_render', inherit=False); fx.vcopy(POS, fx.AT); fx.vcopy(vel, fx.DEST); fx.ret()
    fx.label(name + '_tick'); fx.life(life); fx.vadd(POS, vel); fx.ret()
    fx.label(name + '_render')
    fx.vcopy(fx.TV, vel); fx.vmul(fx.TV, tail); fx.vcopy(fx.TV2, POS); fx.vsub(fx.TV2, fx.TV)
    fx.vcopy(fx.TV, POS); band(fx, fx.TV2, fx.TV, half, col, cell, clut); fx.ret()
    return pool


def reached(fx, name, speed, start, on_due, delay=None):
    """Define the routine `name_all`: for every enemy, something that waits where it stands until a front leaving
    the caster at `speed` a tick (from the radius `start`) gets there, then runs on_due(tall) (tall: the enemy's
    height) with the instance standing at the enemy's feet. delay: that many ticks for everybody instead."""
    wait = fx.var()
    pool = fx.pool(name, 4, 2)
    due, tall = iv(FREE), iv(FREE + 4)
    fx.label(name + '_all')

    def one():
        if delay is not None:
            fx.set(wait, delay)
        else:
            go = fx.label()
            fx.vcopy(fx.TV, fx.TGT); fx.vsub(fx.TV, fx.SRC); fx.set(at(fx.TV, 1), 0); fx.vlen(wait, fx.TV)
            fx.sub_(wait, start); fx.div(wait, speed); fx.br(wait, '>=', 1, go); fx.set(wait, 1)
            fx.label(go)
        fx.vcopy(fx.AT, fx.TGT); fx.call(name)
    fx.each_target(one); fx.ret()
    fx.begin(name, pool, 'noop', inherit=False)
    fx.vcopy(POS, fx.AT); fx.set(due, wait); fx.set(tall, at(fx.TSIZE, 1)); fx.ret()
    fx.label(name + '_tick'); fx.br(FRAME, '<', due, 'noop')
    on_due(tall)
    fx.set(FRAME, -1); fx.ret()


def chest_of(fx, out, tall):
    """out = the chest of whoever stands at the instance's place and is `tall` high."""
    fx.vcopy(out, POS); fx.lin(fx.T, tall, 6, 0, 10); fx.sub_(at(out, 1), fx.T)


def everyone(fx):
    """Nobody is left out: whoever was not hit yet is hit now, wherever it stands."""
    fx.strike(fx.SRC, 8000)


# ----------------------------------------------------------------- Okuwamon
def duo_scissor_claw():
    """Two great toothed jaws of green light open at Okuwamon's sides and snap shut on the field; where they close,
    every enemy is cut twice, one stroke crossing the other."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(CHITIN)
    fx.paint(0, pincer()); fx.paint(1, pincer(True)); fx.paint(2, cut(0.7)); fx.paint(3, cut(-0.7))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, star(4, 2, 9, 6))
    tint, soft, fade = fx.colour(128, 128, 128), fx.colour(40, 90, 30), fx.vec()
    aim, fwd, lat = fx.vec(), fx.vec(), fx.vec()
    close = 9
    fx.particle('spark', 18, 10, 5, (120, 128, 90), (70, 130), grow=-7, speed=70, lift=20, gravity=6, spread=60)
    fx.particle('flash', 4, 5, 4, (90, 128, 70), None, grow=40, fade=True)
    fx.particle('wake', 16, 5, 4, (30, 80, 24), 300, grow=-40, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(close, 'snip'); fx.when(close + 12, 'sure'); fx.end(close + 13)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin')
    fx.vcopy(aim, fx.TCHEST); to_target(fx, fwd, 620); side(fx, lat, fwd)
    fx.vcopy(fx.DEST, aim)
    fx.vcopy(fx.AT, fx.CHEST); fx.vadd(fx.AT, lat); fx.call('jawa')
    fx.vcopy(fx.AT, fx.CHEST); fx.vsub(fx.AT, lat); fx.call('jawb')
    fx.sound(-55); fx.ret()
    for name, cell in (('jawa', 0), ('jawb', 1)):
        fx.travel(name, 1, close, name + '_render', 'jaw_arrive', every='jaw_trail')
        fx.label(name + '_render')
        fx.lin(fx.T3, FRAME, 30, 380); fx.sprite(POS, soft, 700, cell=4); fx.sprite(POS, tint, fx.T3, cell=cell)
        fx.ret()
    fx.label('jaw_trail'); fx.emit('wake', POS); fx.ret()
    fx.label('jaw_arrive'); fx.set(fx.SZ, 420); fx.emit('flash', POS); fx.ret()
    fx.label('snip')
    fx.sound(13)

    def each():
        fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 320, 10); fx.vcopy(fx.AT, fx.TCHEST); fx.call('cross')
    fx.each_target(each); fx.ret()

    def cross_draw(size):
        def first():
            fx.lin(fx.T3, FRAME, 70); fx.add(fx.T3, size); dim(fx, fade, 6)
            fx.sprite(POS, fade, fx.T3, cell=2)

        def second():
            fx.lin(fx.T3, FRAME, 70, -280); fx.add(fx.T3, size)
            fx.lin(fx.T, FRAME, -18, 200); fx.vset(fade, fx.T, fx.T, fx.T)
            fx.sprite(POS, fade, fx.T3, cell=3)
        window(fx, 0, 5, first); window(fx, 4, 10, second)

    def cross_tick(size):
        def again():
            fx.sound(16); fx.set(fx.SZ, size); fx.emit('flash', POS); fx.emit('spark', times=5)
        skip = fx.label(); fx.br(FRAME, '!=', 4, skip); again(); fx.label(skip)
        skip = fx.label(); fx.br(FRAME, '!=', 0, skip); fx.emit('spark', POS, 4); fx.label(skip)
    stand(fx, 'cross', 4, 10, cross_draw, cross_tick)
    return fx


# ----------------------------------------------------------------- Tortomon
def strong_carapace():
    """The horns of Tortomon's shell glow and leave it in three volleys, tumbling high over the field and coming
    down point first on every enemy in a burst of dust and splinters."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(SHELL); fx.palette(DUST)
    fx.paint(0, horn()); fx.paint(1, horn(0.8)); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, clip(glow(14, 0.8) * (0.3 + fbm(5)))); fx.paint(5, cut(1.2))
    tint, top = fx.colour(128, 128, 128), fx.vec()
    fx.particle('bud', 8, 6, 2, (128, 100, 50), 60, grow=40, fade=True)
    fx.particle('dust', 12, 10, 4, (110, 100, 80), 200, grow=35, lift=6, spread=120, clut=1, fade=True)
    fx.particle('chip', 18, 12, 5, (128, 128, 128), (90, 150), grow=-5, speed=60, lift=50, gravity=10, spread=60,
                spin=30, blend=None)
    fx.particle('glint', 6, 4, 3, (128, 120, 80), 260, grow=-40)
    fx.label('main'); fx.when(0, 'begin')
    fx.br(fx.NOW, '>', 5, 'main_go'); fx.emit('bud', top); fx.scatter(fx.AT, 260); fx.call('glint')
    fx.label('main_go'); fx.when(6, 'volley'); fx.when(24, 'sure'); fx.end(25)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin')
    fx.vcopy(top, fx.SRC); fx.lin(fx.T, at(fx.SSIZE, 1), 1, 60); fx.sub_(at(top, 1), fx.T); fx.sound(-55); fx.ret()
    fx.label('volley')
    fx.sound(3)

    def each():
        for name in ('horna', 'hornb', 'hornc'):
            fx.vcopy(fx.AT, top); fx.scatter(fx.AT, 200)
            fx.vcopy(fx.DEST, fx.TCHEST); fx.scatter(fx.DEST, 150); fx.call(name)
    fx.each_target(each); fx.ret()
    for k, (name, ticks) in enumerate((('horna', 9), ('hornb', 12), ('hornc', 15))):
        def body(pos, k=k):
            fx.lin(fx.T2, FRAME, 50 if k != 1 else -50)
            fx.sprite(pos, tint, 330, cell=k % 2, blend=None, rot=fx.T2)
        lob(fx, name, 4, ticks, 420 + 120 * k, body, 'horn_arrive')
    fx.label('horn_arrive')
    fx.sound(20); fx.strike(POS, 320); fx.emit('dust', POS, 2); fx.emit('chip', times=4); fx.ret()
    return fx


# ----------------------------------------------------------------- DarkTyrannomon
def fire_blast():
    """DarkTyrannomon breathes a river of fire and swings its head: the stream sweeps from one end of the enemy line
    to the other, and whoever it passes over is left burning."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(DARKFIRE)
    fx.paint(0, gout(3)); fx.paint(1, gout(9)); fx.paint(2, glow(15, 1.3)); fx.paint(3, lick(0.5))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, lick(2.6))
    aim, mouth, fwd, lat, end = fx.vec(), fx.vec(), fx.vec(), fx.vec(), fx.vec()
    first, mid, last = 1, 9, 17
    fx.particle('gouta', 22, 6, 0, (128, 110, 80), (230, 330), grow=28, lift=6, spread=60, fade=True)
    fx.particle('goutb', 22, 6, 1, (128, 110, 80), (230, 330), grow=28, lift=6, spread=60, fade=True)
    fx.particle('ember', 16, 12, 4, (128, 90, 40), (50, 100), speed=30, lift=30, gravity=3, spread=120, fade=True)
    fx.particle('burn', 12, 10, 3, (128, 110, 70), (200, 300), grow=-10, flat=((-12, 12), (-55, -25), (-12, 12)),
                spread=140)
    fx.particle('burn2', 12, 10, 5, (128, 110, 70), (200, 300), grow=-10, flat=((-12, 12), (-55, -25), (-12, 12)),
                spread=140)
    fx.particle('flare', 4, 7, 2, (128, 70, 30), None, grow=50, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(mid, 'scorch'); fx.when(last + 6, 'sure')
    fx.br(fx.NOW, '<', first, 'main_end'); fx.br(fx.NOW, '>', last, 'main_end')
    fx.lin(fx.T3, fx.NOW, 1, -mid); fx.vcopy(end, lat); fx.vmul(end, fx.T3); fx.vdiv(end, mid - first)
    fx.vadd(end, aim)
    for name, num in (('gouta', 3), ('goutb', 6), ('gouta', 8), ('goutb', 10)):
        part(fx, fx.AT, mouth, end, num, 10); fx.call(name)
    fx.emit('ember', end)
    fx.set(fx.T3, fx.NOW); fx.mod(fx.T3, 4); fx.br(fx.T3, '!=', 1, 'main_end'); fx.sound(4)
    fx.label('main_end'); fx.end(last + 7)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin')
    fx.vcopy(aim, fx.TCHEST); to_target(fx, fwd, 760); side(fx, lat, fwd)
    fx.vcopy(mouth, fx.SRC); fx.lin(fx.T, at(fx.SSIZE, 1), 8, 0, 10); fx.sub_(at(mouth, 1), fx.T)
    fx.vcopy(fx.TV, fwd); fx.vdiv(fx.TV, 5); fx.vadd(mouth, fx.TV); fx.sound(3); fx.ret()
    fx.label('scorch')
    fx.sound(15)

    def each():
        fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 260, 10)
        fx.emit('flare', fx.TCHEST); fx.emit('burn', fx.TGT, 4); fx.emit('burn2', times=4)
    fx.each_target(each); fx.ret()
    return fx


# ----------------------------------------------------------------- SkullMammothmon
def s_bone_crusher():
    """SkullMammothmon hurls a bone as long as itself. It goes out spinning to one side, crosses the whole enemy
    line and comes back round the other, cracking on everything in its way."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(BONE); fx.palette(DUST)
    fx.paint(0, bone()); fx.paint(1, glow(15, 1.2)); fx.paint(2, star(6, 2, 10, 5)); fx.paint(3, cut(0.3))
    fx.paint(4, clip(glow(14, 0.8) * (0.3 + fbm(7))))
    tint, fwd, lat = fx.colour(128, 128, 128), fx.vec(), fx.vec()
    turn = 24
    fx.particle('whoosh', 14, 5, 1, (70, 64, 50), 420, grow=-50, fade=True)
    fx.particle('crack', 6, 6, 2, (128, 128, 110), 240, grow=70, fade=True)
    fx.particle('chip', 16, 11, 3, (128, 124, 110), (90, 150), grow=-6, speed=70, lift=30, gravity=8, spin=40)
    fx.particle('dust', 8, 9, 4, (110, 100, 80), 220, grow=30, lift=5, clut=1, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(turn + 2, 'sure'); fx.end(turn + 3)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin')
    to_target(fx, fwd)
    fx.vmul(fwd, 28); fx.vdiv(fwd, 20); side(fx, lat, fwd)
    fx.vcopy(fx.AT, fx.CHEST); fx.call('club'); fx.sound(3); fx.ret()
    club = fx.pool('club', 1)
    fx.begin('club', club, 'club_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('club_tick')
    fx.br(FRAME, '>', turn, 'die')
    # out to one side, across, and back: the way to the target turned by an angle that swings, times how far out
    fx.lin(fx.T3, FRAME, 1400 // turn, -700)
    fx.lin(fx.T2, FRAME, 2048 // turn); fx.sin(fx.F1, fx.T2, 1024)
    fx.cos(fx.T, fx.T3, 1024); fx.mul(fx.T, fx.F1); fx.div(fx.T, 1024)
    fx.vcopy(fx.TV, fwd); fx.vmul(fx.TV, fx.T); fx.vdiv(fx.TV, 1024)
    fx.sin(fx.T, fx.T3, 1024); fx.mul(fx.T, fx.F1); fx.div(fx.T, 1024)
    fx.vcopy(fx.TV2, lat); fx.vmul(fx.TV2, fx.T); fx.vdiv(fx.TV2, 1024)
    fx.vcopy(POS, fx.CHEST); fx.vadd(POS, fx.TV); fx.vadd(POS, fx.TV2)
    fx.emit('whoosh', POS)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 4); fx.br(fx.T2, '!=', 0, 'club_hit'); fx.sound(13)
    fx.label('club_hit')
    fx.strike(POS, 450); fx.br(fx.HIT, '==', 0, 'noop')
    fx.sound(7); fx.emit('crack', POS); fx.emit('chip', times=6); fx.emit('dust', times=2); fx.ret()
    fx.label('club_render')
    fx.lin(fx.T2, FRAME, 55); fx.sprite(POS, tint, 620, cell=0, blend=None, rot=fx.T2); fx.ret()
    return fx


# ----------------------------------------------------------------- Plesiomon
def sad_water_blast():
    """Plesiomon sings: rings of sound and falling notes rise from its head. Then the song breaks into a wall of
    water that rolls across the field and goes up in spray on every enemy it meets."""
    fx = Fx(delay=8, cast_sound=45)
    fx.palette(WATER)
    fx.paint(0, crest(0)); fx.paint(1, crest(9)); fx.paint(2, glow(15, 1.2)); fx.paint(3, drop())
    fx.paint(4, ring(13.5, 1.4)); fx.paint(5, note()); fx.paint(6, clip(glow(14, 0.7) * (0.2 + fbm(15))))
    tint, soft = fx.colour(128, 128, 128), fx.colour(60, 100, 128)
    head, fwd, lat, step = fx.vec(), fx.vec(), fx.vec(), fx.vec()
    song, roll = 9, 10
    fx.particle('ringing', 4, 8, 4, (100, 128, 128), 120, grow=80, fade=True)
    fx.particle('tear', 12, 12, 5, (110, 128, 128), (130, 190), flat=((-14, 14), (6, 16), (-14, 14)), spread=420)
    fx.particle('spray', 30, 10, 3, (120, 128, 128), (70, 130), grow=-4, speed=40, lift=60, gravity=10, spread=160)
    fx.particle('foam', 10, 9, 6, (90, 110, 128), 240, grow=40, lift=10, spread=160, fade=True)
    fx.particle('column', 4, 9, 2, (70, 110, 128), None, grow=30, sy=30, lift=20, fade=True)
    fx.label('main'); fx.when(0, 'begin')
    for t in (0, 3, 6):
        fx.when(t, 'sing')
    fx.when(song, 'loose'); fx.when(song + roll, 'break'); fx.when(song + roll + 9, 'sure')
    fx.br(fx.NOW, '>', song, 'main_end'); fx.emit('tear', head)
    fx.label('main_end'); fx.end(song + roll + 10)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin')
    fx.vcopy(head, fx.SRC); fx.lin(fx.T, at(fx.SSIZE, 1), 1, 30); fx.sub_(at(head, 1), fx.T)
    to_target(fx, fwd); fx.vcopy(step, fwd); fx.vdiv(step, roll); to_target(fx, lat, 300); side(fx, fwd, lat)
    fx.vcopy(lat, fwd); fx.ret()
    fx.label('sing'); fx.sound(34); fx.emit('ringing', head); fx.ret()
    fx.label('loose'); fx.sound(11); fx.vcopy(fx.AT, fx.SRC); fx.call('wall'); fx.ret()
    wall = fx.pool('wall', 1)
    fx.begin('wall', wall, 'wall_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('wall_tick'); fx.life(roll + 5); fx.vadd(POS, step)
    fx.vcopy(fx.AT, lat); fx.rnd(fx.T3, -3, 3); fx.vmul(fx.AT, fx.T3); fx.vadd(fx.AT, POS)
    fx.sub_(at(fx.AT, 1), 260); fx.call('spray', 2); fx.ret()
    fx.label('wall_render')
    fx.lin(fx.T3, FRAME, 45, 180); fx.br(fx.T3, '<', 600, 'wall_draw'); fx.set(fx.T3, 600)
    fx.label('wall_draw')
    for k in range(-3, 4):
        fx.vcopy(fx.TV, lat); fx.vmul(fx.TV, k); fx.vadd(fx.TV, POS)
        fx.lin(fx.F2, fx.T3, 10 - abs(k), 0, 10)
        fx.pillar(fx.TV, 520, fx.F2, tint if k % 2 == 0 else soft, cell=(k + 3) % 2)
    fx.ret()
    fx.label('break')
    fx.sound(15)

    def each():
        fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 10, 200, 10)
        fx.emit('column', fx.TCHEST); fx.emit('foam', fx.TGT, 2); fx.emit('spray', fx.TCHEST, 6)
    fx.each_target(each); fx.ret()
    return fx


# ----------------------------------------------------------------- Blossomon
def ninja_flower():
    """Four flowers open around Blossomon, spinning faster and faster, and fly off like throwing stars with a tail of
    leaves, one for every enemy and the last for the first again; each breaks into petals where it cuts."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(PETAL); fx.palette(LEAF)
    fx.paint(0, flower()); fx.paint(1, flower(0.63)); fx.paint(2, leaf()); fx.paint(3, clip(leaf().T * 0.9))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, cut(0.9))
    tint, soft, aim, place = fx.colour(128, 128, 128), fx.colour(128, 50, 90), fx.vec(), fx.vec()
    idx = fx.var()
    bloom, flight = 8, 6
    fx.particle('bud', 4, bloom, 0, (128, 128, 128), 40, grow=36, spin=40)
    fx.particle('trail', 20, 7, 2, (100, 128, 80), (100, 150), grow=-8, speed=14, spin=25, clut=1, fade=True)
    fx.particle('shed', 24, 12, 3, (128, 120, 128), (90, 140), grow=-3, speed=60, lift=30, gravity=6, spin=30)
    fx.particle('nick', 5, 6, 5, (128, 128, 128), None, grow=50, fade=True)
    fx.particle('puff', 5, 6, 4, (128, 60, 100), 220, grow=50, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(bloom, 'throw'); fx.when(bloom + 3, 'last')
    fx.when(bloom + flight + 10, 'sure'); fx.end(bloom + flight + 11)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('at_ring')
    fx.lin(fx.T, idx, 1024, 300); fx.circle(place, fx.T, 320, 0); fx.vadd(place, fx.CHEST)
    fx.sub_(at(place, 1), 120); fx.add(idx, 1); fx.ret()
    fx.label('begin')
    fx.vcopy(aim, fx.TCHEST); fx.set(idx, 0)
    for _ in range(4):
        fx.call('at_ring'); fx.emit('bud', place)
    fx.set(idx, 0); fx.sound(34); fx.ret()
    fx.label('throw')
    fx.sound(13)

    def each():
        fx.call('at_ring'); fx.vcopy(fx.AT, place); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('blade')
    fx.each_target(each); fx.ret()
    fx.label('last')
    fx.sound(13); fx.set(idx, 3); fx.call('at_ring'); fx.vcopy(fx.AT, place); fx.vcopy(fx.DEST, aim)
    fx.call('blade'); fx.ret()
    fx.travel('blade', 5, flight, 'blade_render', 'blade_arrive', every='blade_trail')
    fx.label('blade_trail'); fx.emit('trail', POS); fx.ret()
    fx.label('blade_render')
    fx.lin(fx.T2, FRAME, 75); fx.sprite(POS, soft, 460, cell=4)
    fx.sprite(POS, tint, 360, cell=0, rot=fx.T2); fx.ret()
    fx.label('blade_arrive')
    fx.sound(16); fx.strike(POS, 330); fx.set(fx.SZ, 380)
    fx.emit('nick', POS); fx.emit('puff'); fx.emit('shed', times=6); fx.ret()
    return fx


# ----------------------------------------------------------------- SkullMeramon
def metal_fireball():
    """Blue flames run together in SkullMeramon's hands around a lump of metal that heats white under a black crust.
    Thrown high, it bursts where it lands and rains burning slag on every enemy."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(MOLTEN); fx.palette(GHOSTFIRE)
    fx.paint(0, molten(3)); fx.paint(1, molten(8)); fx.paint(2, glow(15, 1.2)); fx.paint(3, drop())
    fx.paint(4, lick(1.1)); fx.paint(5, ring(13, 2.2)); fx.paint(6, star(4, 2, 9, 6))
    tint, blue, hand, aim = fx.colour(128, 128, 128), fx.colour(60, 90, 128), fx.vec(), fx.vec()
    forge, flight = 8, 9
    gather(fx, 'wisp', 14, 4, (90, 110, 128), 190, 600, 6, clut=1)
    fx.particle('tail', 12, 7, 4, (80, 110, 128), 260, grow=-24, lift=10, clut=1, fade=True)
    fx.particle('drip', 12, 9, 3, (128, 110, 70), (70, 110), gravity=9, spread=60)
    fx.particle('blast', 2, 9, 2, (128, 100, 50), 300, grow=110, fade=True)
    fx.particle('shock', 2, 8, 5, (128, 80, 30), 200, grow=120, fade=True)
    fx.particle('slag', 18, 9, 3, (128, 120, 90), (110, 170), flat=((-8, 8), (55, 80), (-8, 8)), spread=260)
    fx.particle('sizzle', 12, 9, 4, (80, 110, 128), (160, 240), grow=-10, flat=((-10, 10), (-45, -20), (-10, 10)),
                spread=140, clut=1)
    fx.particle('fleck', 12, 12, 6, (128, 110, 60), (70, 130), grow=-6, speed=80, lift=60, gravity=9, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(forge, 'throw')
    fx.when(forge + flight + 12, 'sure')
    fx.br(fx.NOW, '>', forge - 3, 'main_end'); fx.emit('wisp', hand, 2)
    fx.label('main_end'); fx.end(forge + flight + 13)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin')
    fx.vcopy(aim, fx.TGT); to_target(fx, fx.TV2, 140)
    fx.vcopy(hand, fx.CHEST); fx.vadd(hand, fx.TV2); fx.sub_(at(hand, 1), 120)
    fx.vcopy(fx.AT, hand); fx.call('lump'); fx.sound(-55); fx.ret()

    def lump_draw(size):
        fx.lin(fx.T3, FRAME, 44, 60); fx.lin(fx.T, fx.T3, 15, 0, 10)
        fx.sprite(POS, blue, fx.T, cell=2, clut=1); flicker(fx, POS, tint, fx.T3, (0, 1), blend=None)
    stand(fx, 'lump', 1, forge - 1, lump_draw)
    fx.label('throw'); fx.sound(3); fx.vcopy(fx.AT, hand); fx.vcopy(fx.DEST, aim); fx.call('ball'); fx.ret()

    def ball_draw(pos):
        fx.sprite(pos, blue, 620, cell=2, clut=1); flicker(fx, pos, tint, 420, (0, 1), blend=None)
        fx.vcopy(fx.AT, pos)
    lob(fx, 'ball', 1, flight, 520, ball_draw, 'ball_arrive', every='ball_trail')
    fx.label('ball_trail')              # the tail and the drips leave the place the ball was last painted at
    fx.call('tail'); fx.call('drip'); fx.ret()
    fx.label('ball_arrive')
    fx.sound(15); fx.emit('blast', POS); fx.emit('shock'); fx.emit('fleck', times=12)
    fx.call('burn_all')                 # the slag comes down on everybody a moment after the burst

    def each():
        fx.hit()
    fx.each_target(each); fx.ret()

    def rain(tall):
        chest_of(fx, fx.AT, tall); fx.sub_(at(fx.AT, 1), 420); fx.call('slag', 7)
        fx.emit('sizzle', POS, 4); fx.sound(20)
    reached(fx, 'burn', 0, 0, rain, delay=4)
    return fx


# ----------------------------------------------------------------- MarineDevimon
def evil_wind():
    """The light goes out of the field and a wind from the deep blows through it from behind MarineDevimon: long
    streaks of cold air and curls of black mist that wrap every enemy as they pass."""
    fx = Fx(delay=8, cast_sound=45, draw=True)
    fx.palette(ABYSS)
    fx.paint(0, gust(1)); fx.paint(1, gust(2)); fx.paint(2, curl()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, clip(glow(14, 0.7) * (0.2 + fbm(25)))); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, clip(curl()[:, ::-1]))
    wash, fwd, lat, back = fx.vec(), fx.vec(), fx.vec(), fx.vec()
    blow, strike_at = 20, 10
    streaks(fx, 'gusta', 20, 12, 0, (110, 128, 128), 70, 3)
    streaks(fx, 'gustb', 20, 12, 1, (70, 110, 120), 55, 3)
    fx.particle('murk', 16, 10, 4, (70, 60, 50), (300, 420), grow=20, spread=500, blend='sub', fade=True, drift=None)
    fx.particle('coil', 12, 9, 2, (110, 128, 128), None, grow=18, spin=45, fade=True)
    fx.particle('coil2', 12, 9, 6, (60, 110, 120), None, grow=24, spin=-45, fade=True)
    fx.particle('rime', 16, 11, 5, (120, 128, 128), (60, 120), grow=-6, speed=60, lift=20, spread=120)
    fx.label('main'); fx.when(0, 'begin'); fx.when(strike_at, 'wrap'); fx.when(blow + 6, 'sure')
    fx.br(fx.NOW, '>', blow, 'main_end')
    for name in ('gusta', 'gustb', 'gusta'):
        fx.vcopy(fx.AT, lat); fx.rnd(fx.T3, -10, 10); fx.vmul(fx.AT, fx.T3); fx.vdiv(fx.AT, 10)
        fx.vadd(fx.AT, back); fx.rnd(fx.T3, 40, 520); fx.sub_(at(fx.AT, 1), fx.T3)
        fx.vcopy(fx.DEST, fwd); fx.call(name)
    part(fx, fx.AT, back, fx.TGT, fx.NOW, blow); fx.sub_(at(fx.AT, 1), 200); fx.call('murk')
    fx.set(fx.T3, fx.NOW); fx.mod(fx.T3, 5); fx.br(fx.T3, '!=', 0, 'main_end'); fx.sound(11)
    fx.label('main_end'); fx.end(blow + 7)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('draw')
    fx.set(fx.T, 60); fx.br(fx.NOW, '>', 6, 'draw_late'); fx.lin(fx.T, fx.NOW, 10)
    fx.label('draw_late'); fx.br(fx.NOW, '<', blow, 'draw_wash'); fx.lin(fx.T, fx.NOW, -9, 60 + 9 * blow)
    fx.br(fx.T, '>', 0, 'draw_wash'); fx.ret()
    fx.label('draw_wash'); fx.lin(fx.T2, fx.T, 7, 0, 10); fx.vset(wash, fx.T, fx.T2, fx.T2)
    fx.overlay(wash, blend='sub'); fx.ret()
    fx.label('begin')
    to_target(fx, fwd, 150); side(fx, lat, fwd); fx.vmul(lat, 6)
    fx.vcopy(back, fwd); fx.vmul(back, -4); fx.vadd(back, fx.SRC); fx.ret()
    fx.label('wrap')
    fx.sound(15)

    def each():
        fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 10, 220, 10)
        fx.emit('coil', fx.TCHEST, 2); fx.emit('coil2', times=2); fx.emit('rime', times=6)
    fx.each_target(each); fx.ret()
    return fx


# ----------------------------------------------------------------- Pumpkinmon
def trick_or_treat():
    """Sweets whirl up around Pumpkinmon, and over every enemy a great carved pumpkin, its face alight, drops out of
    the sky and bursts into rind and candy."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(PUMPKIN); fx.palette(CANDY)
    fx.paint(0, pumpkin()); fx.paint(1, pumpkin(True)); fx.paint(2, glow(15, 1.2)); fx.paint(3, rind())
    fx.paint(4, star(5, 3, 9, 3)); fx.paint(5, ring(13, 2.2))
    tint = fx.colour(128, 128, 128)
    conjure, fall = 6, 9
    fx.particle('sweet', 16, 10, 4, (128, 128, 128), (90, 150), flat=((-30, 30), (-70, -30), (-30, 30)), spread=200,
                spin=30, clut=1)
    fx.particle('blast', 4, 8, 2, (128, 100, 50), None, grow=70, fade=True)
    fx.particle('hoop', 4, 7, 5, (128, 90, 30), 160, grow=90, fade=True)
    fx.particle('chunk', 24, 13, 3, (128, 128, 128), (120, 190), grow=-4, speed=70, lift=60, gravity=10, spread=80,
                spin=35, blend=None)
    fx.particle('treat', 18, 13, 4, (128, 128, 128), (90, 140), grow=-4, speed=80, lift=70, gravity=9, spread=80,
                spin=30, clut=1)
    fx.label('main')
    fx.br(fx.NOW, '>', conjure, 'main_go'); fx.emit('sweet', fx.SRC, 2)
    fx.label('main_go'); fx.when(0, 'begin'); fx.when(conjure, 'call'); fx.when(conjure + fall + 10, 'sure')
    fx.end(conjure + fall + 11)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin'); fx.sound(34); fx.ret()
    fx.label('call')
    fx.sound(40)

    def each():
        fx.vcopy(fx.DEST, fx.TCHEST); fx.vcopy(fx.AT, fx.TCHEST); fx.sub_(at(fx.AT, 1), 1300)
        fx.rnd(fx.T, -200, 200); fx.add(at(fx.AT, 0), fx.T)
        fx.lin(fx.SZ, at(fx.TSIZE, 1), 10, 300, 10); fx.call('gourd')
    fx.each_target(each); fx.ret()
    fx.travel('gourd', 4, fall, 'gourd_render', 'gourd_arrive', fields=1)
    fx.label('gourd_render')
    fx.lin(fx.T3, FRAME, 22, 360); fx.lin(fx.T, FRAME, 14, -60)
    flicker(fx, POS, tint, fx.T3, (0, 1), blend=None, every=2); fx.ret()
    fx.label('gourd_arrive')
    fx.sound(15); fx.strike(POS, 340); fx.set(fx.SZ, 420)
    fx.emit('blast', POS); fx.emit('hoop'); fx.emit('chunk', times=6); fx.emit('treat', times=5); fx.ret()
    return fx


# ----------------------------------------------------------------- Boltmon
def tomahawk_crunch():
    """Current crawls over Boltmon's axe; it throws one spinning at every enemy and a second at the first, each
    trailing sparks and landing with a stroke of lightning out of the blade."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(STEEL); fx.palette(VOLT)
    fx.paint(0, axe()); fx.paint(1, bolt(4)); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, gash()); fx.paint(5, bolt(7)); fx.paint(6, clip(bolt(11).T))
    tint, hot, glowc = fx.colour(128, 128, 128), fx.colour(128, 128, 110), fx.colour(90, 80, 30)
    aim, hand = fx.vec(), fx.vec()
    charge, flight = 6, 7
    fx.particle('crackle', 8, 3, 6, (128, 128, 100), (240, 340), spread=300, clut=1)
    fx.particle('trail', 20, 6, 3, (128, 120, 60), (90, 150), grow=-12, spread=120, clut=1, fade=True)
    fx.particle('rift', 5, 7, 4, (128, 128, 128), None, grow=40, fade=True)
    fx.particle('spark', 20, 11, 3, (128, 128, 90), (70, 130), grow=-7, speed=80, lift=30, gravity=7, spread=60,
                clut=1)
    fx.particle('flash', 5, 5, 2, (128, 120, 70), 300, grow=60, clut=1, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'throw'); fx.when(charge + 4, 'again')
    fx.when(charge + flight + 14, 'sure')
    fx.br(fx.NOW, '>', charge + 3, 'main_end'); fx.emit('crackle', hand)
    fx.label('main_end'); fx.end(charge + flight + 15)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin')
    fx.vcopy(aim, fx.TCHEST); fx.vcopy(hand, fx.CHEST); fx.sub_(at(hand, 1), 160); fx.sound(-55); fx.ret()
    fx.label('throw')
    fx.sound(13)

    def each():
        fx.vcopy(fx.AT, hand); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('hawk')
    fx.each_target(each); fx.ret()
    fx.label('again'); fx.sound(13); fx.vcopy(fx.AT, hand); fx.vcopy(fx.DEST, aim); fx.call('hawk'); fx.ret()

    def hawk_draw(pos):
        fx.lin(fx.T2, FRAME, 65); fx.sprite(pos, glowc, 520, cell=2, clut=1)
        fx.sprite(pos, tint, 400, cell=0, blend=None, rot=fx.T2); fx.vcopy(fx.AT, pos)
    lob(fx, 'hawk', 5, flight, 160, hawk_draw, 'hawk_arrive', every='hawk_trail')
    fx.label('hawk_trail'); fx.call('trail'); fx.ret()
    fx.label('hawk_arrive')
    fx.sound(16); fx.strike(POS, 330); fx.set(fx.SZ, 380)
    fx.emit('rift', POS); fx.emit('flash'); fx.emit('spark', times=5); fx.vcopy(fx.AT, POS); fx.call('stroke')
    fx.ret()

    def stroke_draw(size):
        fx.vcopy(fx.TV, POS); fx.add(at(fx.TV, 1), 120)
        other, done = fx.label(), fx.label()
        fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '==', 1, other)
        fx.pillar(fx.TV, 330, 900, hot, cell=1, clut=1); fx.jmp(done)
        fx.label(other); fx.pillar(fx.TV, 330, 900, hot, cell=5, clut=1)
        fx.label(done)

    def stroke_tick(size):
        skip = fx.label(); fx.br(FRAME, '!=', 1, skip); fx.sound(7); fx.label(skip)
    stand(fx, 'stroke', 5, 4, stroke_draw, stroke_tick)
    return fx


# ----------------------------------------------------------------- ChaosLord
def chaos_cannon():
    """Light gathers in the barrel; the shot leaves in a ring of smoke and its shell crosses the field in a blink. The
    burst whites out the screen and sets off blast after blast across the enemy line, each leaving its smoke."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(CANNON); fx.palette(SMOKE)
    fx.paint(0, shell_round()); fx.paint(1, burstball(1)); fx.paint(2, glow(15, 1.2))
    fx.paint(3, clip(glow(14, 0.7) * (0.25 + fbm(35)))); fx.paint(4, ring(13, 2.4)); fx.paint(5, star(4, 2, 9, 6))
    fx.paint(6, burstball(4))
    tint, steel, wash = fx.colour(128, 128, 128), fx.colour(128, 128, 128), fx.vec()
    muzzle, aim = fx.vec(), fx.vec()
    charge, flight = 5, 4
    land = charge + flight + 1
    gather(fx, 'mote', 12, 5, (128, 110, 60), 90, 520, 4)
    fx.particle('muzzleflash', 2, 5, 1, (128, 128, 128), 200, grow=80, fade=True)
    fx.particle('smokering', 2, 9, 4, (100, 100, 100), 120, grow=70, clut=1, fade=True)
    fx.particle('smoke', 20, 14, 3, (90, 90, 90), (220, 320), grow=22, lift=14, spread=160, clut=1, fade=True)
    fx.particle('shock', 2, 8, 4, (128, 90, 40), 240, grow=150, fade=True)
    fx.particle('shrapnel', 20, 12, 5, (128, 110, 60), (70, 130), grow=-6, speed=90, lift=50, gravity=9, spread=100)
    fx.particle('pop', 4, 7, 2, (128, 90, 40), None, grow=60, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'fire'); fx.when(land, 'sure')
    for t in (land + 2, land + 4, land + 6, land + 8):
        fx.when(t, 'after')
    fx.br(fx.NOW, '>', charge - 2, 'main_end'); fx.emit('mote', muzzle, 2)
    fx.label('main_end'); fx.end(land + 12)
    fx.label('draw')
    fx.br(fx.NOW, '<', land, 'noop'); fx.br(fx.NOW, '>', land + 5, 'noop')
    fx.lin(fx.T, fx.NOW, -20, 20 * (land + 6)); fx.lin(fx.T2, fx.T, 8, 0, 10)
    fx.vset(wash, fx.T, fx.T2, fx.T2); fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    fx.vcopy(aim, fx.TCHEST); to_target(fx, fx.TV2, 170); fx.vcopy(muzzle, fx.CHEST); fx.vadd(muzzle, fx.TV2)
    fx.sound(-55); fx.ret()
    fx.label('fire')
    fx.sound(3); fx.emit('muzzleflash', muzzle); fx.emit('smokering'); fx.emit('smoke', times=3)
    fx.vcopy(fx.AT, muzzle); fx.vcopy(fx.DEST, aim); fx.call('round'); fx.ret()
    fx.travel('round', 1, flight, 'round_render', 'round_arrive', every='round_trail')
    fx.label('round_trail'); fx.emit('smoke', POS); fx.ret()
    fx.label('round_render')
    fx.vcopy(fx.TV, iv(FREE)); fx.vmul(fx.TV, 2); fx.vcopy(fx.TV2, POS); fx.vsub(fx.TV2, fx.TV)
    fx.vcopy(fx.TV, POS); band(fx, fx.TV2, fx.TV, 110, steel, 0); fx.sprite(POS, tint, 300, cell=2); fx.ret()
    fx.label('round_arrive')
    fx.sound(15); fx.set(fx.SZ, 420); fx.vcopy(fx.AT, POS); fx.call('boom')
    fx.emit('shock', POS); fx.emit('shrapnel', times=12); fx.emit('smoke', times=4); fx.ret()
    fx.label('sure')                    # the shell lands on this tick: the burst reaches everybody

    def each():
        fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 10, 240, 10); fx.emit('pop', fx.TCHEST)
    fx.each_target(each); fx.ret()
    fx.label('after')
    fx.sound(7); fx.vcopy(fx.AT, aim); fx.scatter(fx.AT, 1500); fx.set(at(fx.AT, 1), at(aim, 1))
    fx.set(fx.SZ, 260); fx.call('boom'); fx.call('smoke', 2); fx.call('shrapnel', 3); fx.ret()

    def boom_draw(size):
        fx.lin(fx.T3, FRAME, 70); fx.add(fx.T3, size); dim(fx, wash, 8)
        flicker(fx, POS, wash, fx.T3, (1, 6), every=2)
    stand(fx, 'boom', 5, 8, boom_draw)
    return fx


# ----------------------------------------------------------------- Deltamon
def triple_forces():
    """A ball of force swells before each of Deltamon's three heads, one red, one blue, one golden. They leave one
    after another for the same spot, and when the third joins the other two the three go off together in three rings."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(RED); fx.palette(BLUE); fx.palette(AMBER)
    fx.paint(0, force(0)); fx.paint(1, force(2.2)); fx.paint(2, glow(15, 1.2)); fx.paint(3, ring(13, 2.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, trefoil())
    tint, soft, fade = fx.colour(128, 128, 128), fx.colour(70, 70, 70), fx.vec()
    aim, lat = fx.vec(), fx.vec()
    heads = [fx.vec() for _ in range(3)]
    swell, gap, flight = 7, 3, 6
    last = swell + 2 * gap + flight
    for k in range(3):
        fx.particle(f'tail{k}', 6, 6, 2, (128, 128, 128), 300, grow=-36, clut=k, fade=True)
        fx.particle(f'hoop{k}', 2, 9, 3, (128, 128, 128), 160, grow=90 + 30 * k, clut=k, fade=True)
        fx.particle(f'bit{k}', 8, 11, 4, (128, 128, 128), (70, 130), grow=-6, speed=80, lift=30, gravity=6,
                    spread=80, clut=k)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(3):
        fx.when(swell + gap * k, f'go{k}')
    fx.when(last + 1, 'sure'); fx.end(last + 12)
    fx.label('begin')
    fx.vcopy(aim, fx.TCHEST); to_target(fx, lat, 300); side(fx, fx.TV2, lat); fx.vcopy(lat, fx.TV2)
    for k in range(3):
        fx.vcopy(heads[k], lat); fx.vmul(heads[k], k - 1); fx.vadd(heads[k], fx.CHEST)
        fx.lin(fx.T, at(fx.SSIZE, 1), 3, 60 * (k == 1), 10); fx.sub_(at(heads[k], 1), fx.T)
        fx.vcopy(fx.AT, heads[k]); fx.call(f'seed{k}')
    fx.sound(-55); fx.ret()
    for k in range(3):
        def seed_draw(size, k=k):
            fx.lin(fx.T3, FRAME, 34, 50); fx.lin(fx.T, fx.T3, 15, 0, 10)
            fx.sprite(POS, soft, fx.T, cell=2, clut=k); flicker(fx, POS, tint, fx.T3, (0, 1), clut=k)
        stand(fx, f'seed{k}', 1, swell + gap * k - 1, seed_draw)
        fx.label(f'go{k}')
        fx.sound(3); fx.vcopy(fx.AT, heads[k]); fx.vcopy(fx.DEST, aim); fx.call(f'orb{k}'); fx.ret()
        fx.travel(f'orb{k}', 1, flight, f'orb{k}_render', f'orb{k}_arrive', every=f'orb{k}_trail')
        fx.label(f'orb{k}_trail'); fx.emit(f'tail{k}', POS); fx.ret()
        fx.label(f'orb{k}_render')
        fx.sprite(POS, soft, 520, cell=2, clut=k); flicker(fx, POS, tint, 340, (0, 1), clut=k, every=1); fx.ret()
        fx.label(f'orb{k}_arrive')
        fx.sound(7 if k < 2 else 15); fx.emit(f'hoop{k}', POS); fx.emit(f'bit{k}', times=4)
        if k == 2:
            fx.emit('hoop0', POS); fx.emit('hoop1')
        fx.ret()
    fx.label('sure')

    def each():
        fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 8, 200, 10); fx.vcopy(fx.AT, fx.TCHEST); fx.call('unite')
        fx.emit('bit0', fx.TCHEST, 2); fx.emit('bit1', times=2); fx.emit('bit2', times=2)
    fx.each_target(each); fx.ret()

    def unite_draw(size):
        fx.lin(fx.T3, FRAME, 70); fx.add(fx.T3, size); dim(fx, fade, 9); fx.lin(fx.T2, FRAME, 14)
        for k in range(3):
            fx.sprite(POS, fade, fx.T3, cell=5, clut=k, rot=fx.T2 if k == 0 else 120 * k)
    stand(fx, 'unite', 4, 9, unite_draw)
    return fx


# ----------------------------------------------------------------- Gryphonmon
def legendary_blade():
    """Gryphonmon beats its wings once: feathers and rings of air gather, and a blade of wind as wide as the field
    leaves them and passes through the whole enemy line, opening a bright cut on each one."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(SKYGOLD)
    fx.paint(0, bladearc()); fx.paint(1, ripple()); fx.paint(2, glow(15, 1.2)); fx.paint(3, feather())
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, cut(1.45))
    tint, soft, fade = fx.colour(128, 128, 128), fx.colour(70, 60, 30), fx.vec()
    fwd, lat, step = fx.vec(), fx.vec(), fx.vec()
    beat, pass_at, flight = 7, 7, 12
    gather(fx, 'plume', 12, 3, (128, 128, 128), 170, 700, 6)
    fx.particle('airring', 3, 7, 1, (100, 100, 80), 200, grow=70, fade=True)
    fx.particle('wake', 14, 6, 2, (50, 44, 20), 520, grow=-30, fade=True)
    fx.particle('sever', 4, 7, 5, (128, 128, 128), None, grow=60, fade=True)
    fx.particle('down', 24, 14, 3, (128, 128, 128), (110, 170), grow=-3, speed=50, lift=45, gravity=4, spread=140,
                spin=20)
    fx.particle('glint', 12, 9, 4, (128, 128, 100), (80, 140), grow=-8, speed=60, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(3, 'ringing'); fx.when(beat, 'loose')
    fx.when(beat + pass_at, 'cutting'); fx.when(beat + flight + 2, 'sure')
    fx.br(fx.NOW, '>', beat - 2, 'main_end'); fx.emit('plume', fx.CHEST, 2)
    fx.label('main_end'); fx.end(beat + flight + 3)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('ringing'); fx.emit('airring', fx.CHEST); fx.ret()
    fx.label('begin')
    to_target(fx, fwd); fx.vcopy(step, fwd); fx.vdiv(step, pass_at)
    to_target(fx, fwd, 520); side(fx, lat, fwd); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(13); fx.emit('airring', fx.CHEST); fx.vcopy(fx.AT, fx.CHEST); fx.call('edge')
    fx.ret()
    edge = fx.pool('edge', 1)
    fx.begin('edge', edge, 'edge_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('edge_tick'); fx.life(flight); fx.vadd(POS, step); fx.emit('wake', POS)
    fx.vcopy(fx.AT, lat); fx.rnd(fx.T3, -10, 10); fx.vmul(fx.AT, fx.T3); fx.vdiv(fx.AT, 10); fx.vadd(fx.AT, POS)
    fx.call('glint'); fx.ret()
    fx.label('edge_render')
    fx.lin(fx.T, FRAME, -10, 128); fx.br(FRAME, '<', pass_at, 'edge_draw'); fx.lin(fx.T, FRAME, -22, 22 * flight + 30)
    fx.label('edge_draw'); fx.vset(fade, fx.T, fx.T, fx.T)
    fx.lin(fx.T3, FRAME, 12, 100)                 # the blade widens as it flies: lat * T3 / 100 to each side
    fx.vcopy(fx.TV, lat); fx.vmul(fx.TV, fx.T3); fx.vdiv(fx.TV, 100)
    q = fx.Q
    fx.vcopy(q[0], POS); fx.vsub(q[0], fx.TV); fx.vcopy(q[1], POS); fx.vadd(q[1], fx.TV)
    fx.vcopy(q[2], q[0]); fx.vcopy(q[3], q[1])
    fx.sub_(at(q[0], 1), 330); fx.sub_(at(q[1], 1), 330); fx.add(at(q[2], 1), 190); fx.add(at(q[3], 1), 190)
    fx.quad(q[0], q[1], q[2], q[3], fade, 0); fx.ret()
    fx.label('cutting')
    fx.sound(16)

    def each():
        fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 14, 340, 10)
        fx.emit('sever', fx.TCHEST); fx.emit('down', times=7)
    fx.each_target(each); fx.ret()
    return fx


# ----------------------------------------------------------------- Datamon
def digital_bomb():
    """A target marker closes on every enemy, ones and noughts flickering in it; a bomb takes shape over each marker,
    drops and goes off in squares of green light. A fourth goes astray beside the first."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(DIGI); fx.palette(BOMB)
    fx.paint(0, bomb()); fx.paint(1, pixel()); fx.paint(2, brackets()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, digits()); fx.paint(5, digits(True))
    tint, soft, fade = fx.colour(128, 128, 128), fx.colour(40, 128, 60), fx.vec()
    lock, fall = 7, 5
    fx.particle('bit', 30, 11, 1, (128, 128, 128), (60, 130), grow=-5, speed=85, lift=30, gravity=5, spread=60)
    fx.particle('cell', 5, 8, 1, (100, 128, 100), None, grow=80, fade=True)
    fx.particle('code', 12, 10, 4, (128, 128, 128), (110, 150), flat=((-10, 10), (-50, -25), (-10, 10)),
                spread=260, fade=True)
    fx.particle('flash', 5, 5, 3, (90, 128, 90), 300, grow=70, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(lock + fall + 12, 'sure'); fx.end(lock + fall + 13)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin')
    fx.sound(34)

    def each():
        fx.lin(fx.SZ, at(fx.TSIZE, 1), 10, 260, 10); fx.vcopy(fx.AT, fx.TCHEST); fx.call('mark')
    fx.vcopy(fx.KEEP, fx.TCHEST)
    fx.vcopy(fx.TV2, fx.TCHEST); fx.rnd(fx.T, 380, 520); fx.add(at(fx.TV2, 0), fx.T)
    fx.rnd(fx.T, -200, 200); fx.add(at(fx.TV2, 2), fx.T)
    fx.each_target(each)
    fx.set(fx.SZ, 380); fx.vcopy(fx.AT, fx.TV2); fx.call('mark'); fx.ret()

    def mark_draw(size):
        def locking():
            fx.lin(fx.T3, FRAME, -60, 60 * lock); fx.add(fx.T3, size)
            fx.lin(fx.T2, FRAME, 45 if lock else 0, -45 * lock)
            fx.sprite(POS, soft, fx.T3, cell=2, rot=fx.T2)
            fx.lin(fx.T3, size, 6, 0, 10); flicker(fx, POS, soft, fx.T3, (4, 5), every=1)

        def locked():
            fx.sprite(POS, tint, size, cell=2)
            fx.vcopy(fx.TV, POS); fx.lin(fx.T, FRAME, 150, -150 * (lock + fall)); fx.add(at(fx.TV, 1), fx.T)
            fx.sprite(fx.TV, tint, 330, cell=0, clut=1, blend=None)
        window(fx, 0, lock - 1, locking); window(fx, lock, lock + fall, locked)

    def mark_tick(size):
        def bang():
            fx.sound(15); fx.strike(POS, 340); fx.set(fx.SZ, 200)
            fx.emit('cell', POS); fx.emit('flash'); fx.emit('bit', times=8); fx.emit('code', times=3)
        skip = fx.label(); fx.br(FRAME, '!=', lock + fall, skip); bang(); fx.label(skip)
        skip = fx.label(); fx.br(FRAME, '!=', lock, skip); fx.sound(20); fx.label(skip)
    stand(fx, 'mark', 5, lock + fall, mark_draw, mark_tick)
    return fx


# ----------------------------------------------------------------- KingEtemon
def dark_spirits_dx():
    """KingEtemon lifts a ball of dark power with a face in it, notes circling round; it bursts into song, a ring of
    notes and sound that spreads over the whole field and shakes each enemy as it reaches it."""
    fx = Fx(delay=8, cast_sound=45)
    fx.palette(DARKSONG); fx.palette(BRASS)
    fx.paint(0, spirit(3)); fx.paint(1, spirit(8)); fx.paint(2, glow(15, 1.2)); fx.paint(3, note())
    fx.paint(4, note(True)); fx.paint(5, soundarc()); fx.paint(6, clip(soundarc()[:, ::-1]))
    tint, soft, dark, fade = fx.colour(128, 128, 128), fx.colour(90, 40, 128), fx.colour(90, 90, 90), fx.vec()
    hand, rad = fx.vec(), fx.var()
    swell, speed, reach = 10, 85, 16
    fx.particle('shake', 4, 7, 2, (128, 70, 128), None, grow=50, fade=True)
    fx.particle('ditty', 20, 12, 3, (128, 128, 128), (120, 170), speed=40, lift=50, gravity=3, spread=120, clut=1)
    fx.particle('pulse', 3, 7, 2, (100, 40, 128), 200, grow=120, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(swell, 'sing')
    fx.br(fx.NOW, '<', swell, 'main_end'); fx.lin(rad, fx.NOW, speed, 150 - speed * swell); fx.strike(fx.SRC, rad)
    fx.label('main_end'); fx.when(swell + reach + 3, 'sure'); fx.end(swell + reach + 4)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin')
    fx.vcopy(hand, fx.SRC); fx.lin(fx.T, at(fx.SSIZE, 1), 1, 120); fx.sub_(at(hand, 1), fx.T)
    fx.vcopy(fx.AT, hand); fx.call('ball'); fx.sound(-55); fx.ret()

    def ball_draw(size):
        fx.lin(fx.T3, FRAME, 40, 60); fx.lin(fx.T, fx.T3, 7, 0, 10)
        fx.sprite(POS, dark, fx.T, cell=2, blend='sub'); flicker(fx, POS, tint, fx.T3, (0, 1))
        for k in range(3):
            fx.lin(fx.T, FRAME, 300, 1365 * k); fx.lin(fx.T2, fx.T3, 8, 80, 10)
            fx.circle(fx.TV, fx.T, fx.T2, 0); fx.vadd(fx.TV, POS)
            fx.sprite(fx.TV, tint, 170, cell=3 + k % 2, clut=1)
    stand(fx, 'ball', 1, swell - 1, ball_draw)
    fx.label('sing')
    fx.sound(15); fx.emit('pulse', hand); fx.vcopy(fx.AT, fx.SRC); fx.call('chorus'); fx.call('jolt_all'); fx.ret()

    def jolted(tall):
        fx.sound(7); chest_of(fx, fx.AT, tall); fx.lin(fx.SZ, tall, 12, 280, 10)
        fx.call('shake'); fx.call('ditty', 6)
    reached(fx, 'jolt', speed, 150, jolted)
    chorus = fx.pool('chorus', 1)
    fx.begin('chorus', chorus, 'chorus_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('chorus_tick'); fx.life(reach + 4); fx.ret()
    fx.label('chorus_render')
    fx.set(fx.T, 128); fx.br(FRAME, '<=', reach, 'chorus_draw'); fx.lin(fx.T, FRAME, -28, 128 + 28 * reach)
    fx.label('chorus_draw')
    fx.vset(fade, fx.T, fx.T, fx.T)
    fx.lin(fx.T3, FRAME, speed, 150)
    for k in range(12):
        fx.lin(fx.T, FRAME, 40, 341 * k); fx.circle(fx.TV, fx.T, fx.T3, 0); fx.vadd(fx.TV, POS)
        fx.lin(fx.T2, FRAME, 700, 1365 * k); fx.sin(fx.F1, fx.T2, 70); fx.add(at(fx.TV, 1), fx.F1)
        fx.sub_(at(fx.TV, 1), 220)
        if k % 3 == 0:
            fx.sprite(fx.TV, fade, 330, cell=5 if k % 2 == 0 else 6)
        else:
            fx.sprite(fx.TV, fade, 210, cell=3 + k % 2, clut=1)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Creepymon
def evil_inferno():
    """The field darkens and fire the colour of blood breaks out of the ground all over it, each flame with two eyes
    in it; the tallest ones rise under the enemies themselves."""
    fx = Fx(delay=8, cast_sound=45, draw=True)
    fx.palette(HELLFIRE)
    fx.paint(0, hellflame(1)); fx.paint(1, hellflame(4)); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, lick(4.0)); fx.paint(5, clip(glow(14, 0.7) * (0.2 + fbm(45))))
    tint, wash, aim = fx.colour(128, 128, 128), fx.vec(), fx.vec()
    first, burn, last = 2, 10, 19
    fx.particle('ember', 24, 13, 3, (128, 90, 50), (50, 100), speed=20, lift=40, gravity=1, spread=200, fade=True)
    fx.particle('soot', 10, 10, 5, (60, 60, 60), (260, 340), grow=20, lift=20, spread=120, blend='sub', fade=True)
    fx.particle('tongue', 12, 8, 4, (128, 110, 80), (180, 260), grow=-10, flat=((-14, 14), (-60, -30), (-14, 14)),
                spread=160)
    fx.label('main'); fx.when(0, 'begin'); fx.when(burn, 'damn'); fx.when(last + 8, 'sure')
    fx.br(fx.NOW, '<', first, 'main_end'); fx.br(fx.NOW, '>', last, 'main_end')
    fx.vcopy(fx.AT, aim); fx.scatter(fx.AT, 1700); fx.set(at(fx.AT, 1), at(aim, 1))
    fx.rnd(fx.SZ, 380, 620); fx.call('pyre'); fx.call('ember')
    fx.set(fx.T3, fx.NOW); fx.mod(fx.T3, 4); fx.br(fx.T3, '!=', 2, 'main_end'); fx.sound(4)
    fx.label('main_end'); fx.end(last + 9)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('draw')
    fx.set(fx.T, 70); fx.br(fx.NOW, '>', 7, 'draw_late'); fx.lin(fx.T, fx.NOW, 10)
    fx.label('draw_late'); fx.br(fx.NOW, '<', last, 'draw_wash'); fx.lin(fx.T, fx.NOW, -9, 70 + 9 * last)
    fx.br(fx.T, '>', 0, 'draw_wash'); fx.ret()
    fx.label('draw_wash'); fx.lin(fx.T2, fx.T, 5, 0, 10); fx.vset(wash, fx.T2, fx.T, fx.T)
    fx.overlay(wash, blend='sub'); fx.ret()
    fx.label('begin'); fx.vcopy(aim, fx.TGT); fx.sound(-55); fx.ret()

    def pyre_draw(size):
        up, drawn = fx.label(), fx.label()
        fx.lin(fx.T3, FRAME, 1, 0, 1); fx.mul(fx.T3, size); fx.div(fx.T3, 3)
        fx.br(FRAME, '<', 3, up); fx.set(fx.T3, size)
        fx.br(FRAME, '<', 7, up); fx.lin(fx.T3, FRAME, -1, 10); fx.mul(fx.T3, size); fx.div(fx.T3, 3)
        fx.label(up)
        fx.br(fx.T3, '<', 20, drawn)
        fx.lin(fx.F2, fx.T3, 7, 0, 10)
        other, done = fx.label(), fx.label()
        fx.set(fx.T2, FRAME); fx.mod(fx.T2, 4); fx.br(fx.T2, '>=', 2, other)
        fx.pillar(POS, fx.F2, fx.T3, tint, cell=0); fx.jmp(done)
        fx.label(other); fx.pillar(POS, fx.F2, fx.T3, tint, cell=1)
        fx.label(done)
        fx.label(drawn)
    stand(fx, 'pyre', 14, 9, pyre_draw)
    fx.label('damn')
    fx.sound(15)

    def each():
        fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 22, 520, 10); fx.vcopy(fx.AT, fx.TGT); fx.call('pyre')
        fx.call('soot'); fx.emit('tongue', times=4); fx.emit('ember', times=4)
    fx.each_target(each); fx.ret()
    return fx


# ----------------------------------------------------------------- Fujinmon
def divine_wind():
    """A whirlwind opens around Fujinmon in three tiers of jade air that turn against each other and widen until
    they hold the whole field, paper streamers of a shrine riding them; each enemy is lifted in an updraught as the
    wind reaches it."""
    fx = Fx(delay=8, cast_sound=45)
    fx.palette(JADE); fx.palette(PAPERWHITE)
    fx.paint(0, streak()); fx.paint(1, shide()); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, ring(13.5, 1.3)); fx.paint(5, lick(5.3))
    tint, soft, fade = fx.colour(128, 128, 128), fx.colour(40, 110, 80), fx.vec()
    rad = fx.var()
    speed, reach = 80, 17
    fx.particle('paper', 16, 14, 1, (128, 128, 128), (150, 210), flat=((-20, 20), (-40, -10), (-20, 20)), spin=20,
                clut=1, blend=None)
    fx.particle('updraft', 12, 9, 5, (110, 128, 120), (220, 300), grow=-8, flat=((-10, 10), (-70, -40), (-10, 10)),
                spread=160)
    fx.particle('halo', 4, 8, 4, (90, 128, 110), None, grow=60, sy=7, lift=30, fade=True)
    fx.particle('mote', 16, 10, 3, (120, 128, 120), (60, 110), grow=-5, speed=40, lift=50, spread=160)
    fx.label('main'); fx.when(0, 'begin')
    fx.lin(rad, fx.NOW, speed, 160); fx.br(fx.NOW, '>', reach, 'main_end')
    fx.strike(fx.SRC, rad)
    fx.rnd(fx.T3, 0, 4095); fx.circle(fx.AT, fx.T3, rad, 0); fx.vadd(fx.AT, fx.SRC); fx.sub_(at(fx.AT, 1), 200)
    fx.call('paper')
    fx.set(fx.T3, fx.NOW); fx.mod(fx.T3, 5); fx.br(fx.T3, '!=', 0, 'main_end'); fx.sound(11)
    fx.label('main_end'); fx.when(reach + 5, 'sure'); fx.end(reach + 6)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin'); fx.vcopy(fx.AT, fx.SRC); fx.call('whirl'); fx.call('lift_all'); fx.ret()

    def lifted(tall):
        fx.sound(7); fx.lin(fx.SZ, tall, 10, 300, 10); fx.vcopy(fx.AT, POS); fx.call('halo')
        fx.call('updraft', 5); fx.call('mote', 5)
    reached(fx, 'lift', speed, 160, lifted)
    whirl = fx.pool('whirl', 1)
    fx.begin('whirl', whirl, 'whirl_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('whirl_tick'); fx.life(reach + 4); fx.ret()
    fx.label('whirl_render')
    fx.set(fx.T, 128); fx.br(FRAME, '<=', reach, 'whirl_draw'); fx.lin(fx.T, FRAME, -28, 128 + 28 * reach)
    fx.label('whirl_draw')
    fx.vset(fade, fx.T, fx.T, fx.T)
    for tier, (height, turn, share) in enumerate(((90, 190, 10), (330, -150, 8), (570, 230, 6))):
        fx.lin(fx.T3, FRAME, speed * share // 10, 160)
        for k in range(5):
            fx.lin(fx.T, FRAME, turn, 819 * k + 300 * tier)
            fx.circle(fx.TV, fx.T, fx.T3, 0); fx.vadd(fx.TV, POS); fx.sub_(at(fx.TV, 1), height)
            fx.add(fx.T, 330 if turn > 0 else -330)
            fx.circle(fx.TV2, fx.T, fx.T3, 0); fx.vadd(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), height + 50)
            band(fx, fx.TV, fx.TV2, 110, fade, 0)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Minotarumon
def darkside_quake():
    """Minotarumon's arm fills with dark light and comes down on the ground. Shards of rock burst up in a ring that
    runs outward from the blow, and a crag breaks out under every enemy it reaches."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(ROCK); fx.palette(GLOOM); fx.palette(DUST)
    fx.paint(0, spike(1)); fx.paint(1, spike(4)); fx.paint(2, glow(15, 1.2)); fx.paint(3, pebble())
    fx.paint(4, clip(glow(14, 0.7) * (0.25 + fbm(55)))); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, lick(0.2))
    tint, gloom, wash = fx.colour(128, 128, 128), fx.colour(110, 60, 128), fx.vec()
    fist, rad = fx.vec(), fx.var()
    slam, speed, reach = 6, 90, 14
    gather(fx, 'dark', 12, 5, (110, 70, 128), 100, 600, 5, clut=1)
    fx.particle('dustup', 16, 11, 4, (110, 100, 80), (220, 320), grow=28, lift=8, spread=200, clut=2, fade=True)
    fx.particle('rubble', 30, 13, 3, (128, 128, 128), (80, 150), grow=-3, speed=50, lift=75, gravity=10, spread=140,
                spin=30, blend=None)
    fx.particle('seep', 10, 7, 6, (110, 60, 128), (200, 280), grow=-12, lift=30, spread=100, clut=1, fade=True)
    fx.particle('thud', 2, 8, 2, (110, 60, 128), 260, grow=120, clut=1, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(slam, 'blow')
    fx.br(fx.NOW, '>', slam - 2, 'main_run'); fx.emit('dark', fist, 2)
    fx.label('main_run')
    fx.br(fx.NOW, '<', slam, 'main_end'); fx.br(fx.NOW, '>', slam + reach, 'main_end')
    fx.lin(rad, fx.NOW, speed, 200 - speed * slam); fx.strike(fx.SRC, rad)
    for _ in range(4):
        fx.rnd(fx.T3, 0, 4095); fx.circle(fx.AT, fx.T3, rad, 0); fx.vadd(fx.AT, fx.SRC)
        fx.rnd(fx.SZ, 260, 420); fx.call('crag')
    fx.call('rubble', 2); fx.call('dustup')
    fx.label('main_end'); fx.when(slam + reach + 4, 'sure'); fx.end(slam + reach + 5)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('draw')
    fx.br(fx.NOW, '<', slam, 'noop'); fx.br(fx.NOW, '>', slam + 3, 'noop')
    fx.lin(fx.T, fx.NOW, -16, 16 * (slam + 4)); fx.vset(wash, fx.T, fx.T, fx.T); fx.overlay(wash, blend='add')
    fx.ret()
    fx.label('begin')
    to_target(fx, fx.TV2, 160); fx.vcopy(fist, fx.CHEST); fx.vadd(fist, fx.TV2); fx.sub_(at(fist, 1), 200)
    fx.sound(-55); fx.ret()
    fx.label('blow')
    fx.sound(15); fx.vcopy(fx.AT, fist); fx.set(at(fx.AT, 1), at(fx.SRC, 1))
    fx.call('thud'); fx.call('dustup', 4); fx.call('rubble', 8); fx.call('upheave_all'); fx.ret()

    def heaved(tall):
        fx.sound(7); fx.lin(fx.SZ, tall, 14, 360, 10); fx.vcopy(fx.AT, POS); fx.call('crag')
        fx.call('seep', 3); fx.call('rubble', 6); fx.call('dustup', 2)
    reached(fx, 'upheave', speed, 200, heaved)

    def crag_draw(size):
        up, drawn = fx.label(), fx.label()
        fx.lin(fx.T3, FRAME, 1, 1); fx.mul(fx.T3, size); fx.div(fx.T3, 3)
        fx.br(FRAME, '<', 2, up); fx.set(fx.T3, size)
        fx.br(FRAME, '<', 7, up); fx.lin(fx.T3, FRAME, -1, 11); fx.mul(fx.T3, size); fx.div(fx.T3, 4)
        fx.label(up)
        fx.br(fx.T3, '<', 20, drawn)
        fx.lin(fx.F2, size, 6, 0, 10)
        fx.sprite(POS, gloom, fx.F2, cell=2, clut=1)
        fx.pillar(POS, fx.F2, fx.T3, tint, cell=0, blend=None)
        fx.label(drawn)
    stand(fx, 'crag', 24, 10, crag_draw)
    return fx


# ----------------------------------------------------------------- Raijinmon
def raijin_thunder():
    """Five thunder drums appear in an arch behind Raijinmon and are struck three times, each beat louder and brighter
    under a darkening sky. On the last one lightning comes down on every enemy, and twice more on the field."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(DRUM); fx.palette(VOLT)
    fx.paint(0, drum()); fx.paint(1, bolt(2, 2.4)); fx.paint(2, bolt(5, 2.4)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, ring(13, 2.0)); fx.paint(6, bolt(9, 2.4))
    tint, hot, wash = fx.colour(128, 128, 128), fx.colour(128, 128, 110), fx.vec()
    top, lat, aim, beat = fx.vec(), fx.vec(), fx.vec(), fx.var()
    beats, strike_at = (2, 6, 10), 13
    fx.particle('boom', 5, 6, 5, (128, 110, 50), 150, grow=70, clut=1, fade=True)
    fx.particle('spark', 24, 11, 4, (128, 128, 90), (70, 130), grow=-7, speed=85, lift=40, gravity=8, spread=80,
                clut=1)
    fx.particle('flash', 6, 6, 3, (128, 120, 70), None, grow=60, clut=1, fade=True)
    fx.label('main'); fx.when(0, 'begin')
    for t in beats:
        fx.when(t, 'drumbeat')
    fx.when(strike_at, 'thunder'); fx.when(strike_at + 3, 'stray'); fx.when(strike_at + 6, 'stray')
    fx.when(strike_at + 11, 'sure'); fx.end(strike_at + 12)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('draw')
    fx.br(fx.NOW, '>=', strike_at, 'draw_flash')
    fx.lin(fx.T, fx.NOW, 5); fx.vset(wash, fx.T, fx.T, fx.T); fx.overlay(wash, blend='sub'); fx.ret()
    fx.label('draw_flash')
    fx.br(fx.NOW, '>', strike_at + 4, 'noop')
    fx.lin(fx.T, fx.NOW, -18, 18 * (strike_at + 5)); fx.lin(fx.T2, fx.T, 6, 0, 10)
    fx.vset(wash, fx.T, fx.T, fx.T2); fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    fx.vcopy(aim, fx.TGT); to_target(fx, lat, 330); side(fx, fx.TV2, lat); fx.vcopy(lat, fx.TV2)
    fx.vcopy(top, fx.SRC); fx.lin(fx.T, at(fx.SSIZE, 1), 8, 0, 10); fx.sub_(at(top, 1), fx.T)
    fx.set(beat, 0); fx.vcopy(fx.AT, top); fx.call('drums'); fx.sound(34); fx.ret()
    fx.label('drumbeat')
    fx.sound(20); fx.set(beat, 3); fx.ret()
    drums = fx.pool('drums', 1)
    fx.begin('drums', drums, 'drums_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('drums_tick'); fx.life(strike_at + 3)
    fx.br(beat, '<=', 0, 'noop')
    fx.br(beat, '!=', 3, 'drums_fade')
    for k in (-2, 0, 2):
        fx.vcopy(fx.AT, lat); fx.vmul(fx.AT, k); fx.vadd(fx.AT, POS); fx.sub_(at(fx.AT, 1), 220 - 70 * abs(k))
        fx.call('boom')
    fx.label('drums_fade'); fx.sub_(beat, 1); fx.ret()
    fx.label('drums_render')
    fx.lin(fx.T3, beat, 40, 250); fx.br(FRAME, '>', 2, 'drums_draw'); fx.lin(fx.T3, FRAME, 90, 40)
    fx.label('drums_draw')
    for k in range(-2, 3):
        fx.vcopy(fx.TV, lat); fx.vmul(fx.TV, k); fx.vadd(fx.TV, POS)
        fx.sub_(at(fx.TV, 1), 220 - 40 * k * k)
        fx.sprite(fx.TV, tint, fx.T3, cell=0, blend=None)
    fx.ret()
    fx.label('thunder')
    fx.sound(15)

    def each():
        fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 300, 10); fx.vcopy(fx.AT, fx.TGT); fx.call('stroke')
        fx.emit('flash', fx.TCHEST); fx.emit('spark', times=6)
    fx.each_target(each); fx.ret()
    fx.label('stray')
    fx.sound(7); fx.vcopy(fx.AT, aim); fx.scatter(fx.AT, 1500); fx.set(at(fx.AT, 1), at(aim, 1))
    fx.set(fx.SZ, 300); fx.call('stroke'); fx.call('spark', 4); fx.ret()

    def stroke_draw(size):
        fx.vcopy(fx.TV, POS)
        for k, (lo, cell) in enumerate(((0, 1), (2, 2), (4, 6))):
            skip = fx.label()
            fx.set(fx.T2, FRAME); fx.mod(fx.T2, 6); fx.br(fx.T2, '<', lo, skip); fx.br(fx.T2, '>', lo + 1, skip)
            fx.pillar(fx.TV, 420, 1500, hot, cell=cell, clut=1)
            fx.label(skip)
    stand(fx, 'stroke', 6, 6, stroke_draw)
    return fx


# ----------------------------------------------------------------- Pukumon
def needle_squall():
    """Pukumon swells up, bristling, and lets go of its spines in three rings, one after another, each turned a
    little from the last, that fly out over the whole field; every enemy is pricked as the first ring gets to it."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(SPINE); fx.palette(VENOM)
    fx.paint(0, needle()); fx.paint(1, puffball()); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, ring(13, 2.0)); fx.paint(5, drop())
    tint, soft = fx.colour(128, 128, 128), fx.colour(70, 110, 128)
    rad, turn = fx.var(), fx.var()
    swell, gap, speed = 7, 3, 85
    last = swell + 2 * gap
    streaks(fx, 'spine', 36, 13, 0, (128, 128, 128), 60, 3)
    fx.particle('prick', 4, 6, 3, (128, 128, 128), None, grow=50, fade=True)
    fx.particle('ooze', 20, 11, 5, (128, 110, 128), (70, 120), grow=-4, speed=40, lift=40, gravity=8, spread=120,
                clut=1)
    fx.particle('blot', 4, 8, 2, (110, 50, 128), None, grow=30, clut=1, fade=True)
    fx.particle('poof', 3, 6, 4, (90, 128, 128), 200, grow=110, fade=True)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(3):
        fx.when(swell + gap * k, 'burst')
    fx.br(fx.NOW, '<', swell, 'main_end'); fx.lin(rad, fx.NOW, speed, 120 - speed * swell); fx.strike(fx.SRC, rad)
    fx.label('main_end'); fx.when(last + 15, 'sure'); fx.end(last + 16)
    fx.label('sure'); everyone(fx); fx.ret()
    fx.label('begin')
    fx.set(turn, 0); fx.set(fx.SZ, 0); fx.vcopy(fx.AT, fx.CHEST); fx.call('body'); fx.sound(-55); fx.ret()

    def body_draw(size):
        late, drawn = fx.label(), fx.label()
        fx.lin(fx.T3, FRAME, 50, 120); fx.br(FRAME, '<', swell, late)
        fx.set(fx.T2, FRAME); fx.mod(fx.T2, gap); fx.lin(fx.T3, fx.T2, 50, 380)
        fx.label(late)
        fx.lin(fx.T, fx.T3, 14, 0, 10); fx.sprite(POS, soft, fx.T, cell=2)
        fx.lin(fx.T2, FRAME, 9); fx.sprite(POS, tint, fx.T3, cell=1, rot=fx.T2)
        fx.label(drawn)
    stand(fx, 'body', 1, last + 2, body_draw)
    fx.label('burst')
    fx.sound(13); fx.emit('poof', fx.CHEST)
    for k in range(12):
        fx.lin(fx.T3, turn, 1, 341 * k); fx.circle(fx.DEST, fx.T3, speed, -6 - 4 * (k % 3))
        fx.vcopy(fx.AT, fx.CHEST); fx.call('spine')
    fx.br(turn, '!=', 0, 'burst_end'); fx.call('sting_all')
    fx.label('burst_end'); fx.add(turn, 114); fx.ret()

    def stung(tall):
        fx.sound(16); chest_of(fx, fx.AT, tall); fx.lin(fx.SZ, tall, 10, 260, 10)
        fx.call('prick'); fx.call('blot'); fx.call('ooze', 6)
    reached(fx, 'sting', speed, 120, stung)
    return fx


EFFECTS = {259: duo_scissor_claw, 261: strong_carapace, 265: fire_blast, 268: s_bone_crusher, 271: sad_water_blast,
           274: ninja_flower, 277: metal_fireball, 279: evil_wind, 280: trick_or_treat, 288: tomahawk_crunch,
           289: chaos_cannon, 292: triple_forces, 293: legendary_blade, 294: digital_bomb, 303: dark_spirits_dx,
           312: evil_inferno, 317: divine_wind, 330: darkside_quake, 333: raijin_thunder, 401: needle_squall}
