"""Finishers written and painted here, one per species (keyed by species id): the shots, second half. Each one is
thrown, spat or fired at one enemy; the ones that fly in a straight line miss a target that walks away."""
import math

import numpy as np

from tools.technique_effects.finishers import ahead, band, flicker, gather
from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, fbm, glow, grid, iv, polar, ring, segment, \
    star

SMILE = ['#402000', '#c07800', '#ffd020', '#fff8a0']
BLAST = ['#000000', '#601800', '#e05010', '#ffb030', '#fff0a0', '#ffffff']
POLLEN = ['#000000', '#504000', '#c0a010', '#f8e040', '#ffffc0']
LEAF = ['#000000', '#104010', '#40a030', '#b0f060', '#ffffd0']
INK = ['#04040c', '#141030', '#2c2868', '#5868c0', '#c0d0ff']
MIST = ['#000000', '#101840', '#3050a0', '#80b0e0', '#e0f0ff']
KIWI = ['#301808', '#704018', '#b07830', '#e8c070', '#fff0c0']
DUST = ['#000000', '#403020', '#907850', '#d0c090', '#fff8e0']
PEARL = ['#000000', '#203060', '#6090d0', '#c0e0ff', '#ffffff']
ROSE = ['#000000', '#502040', '#c060a0', '#ffc0e0', '#ffffff']
VOLT = ['#000000', '#302060', '#7050e0', '#f0e040', '#ffffc0', '#ffffff']
DREAM = ['#000000', '#200838', '#602090', '#c050c0', '#ff90d0', '#ffe0f0']
BRASS = ['#000000', '#3a2400', '#906010', '#e0b040', '#fff0a0', '#ffffff']
TIME = ['#000000', '#083840', '#209090', '#70e0d0', '#e0fff8']
VENOM = ['#000000', '#200830', '#701090', '#b040d0', '#e8a0ff']
SILK = ['#000000', '#404048', '#909098', '#d8d8e0', '#ffffff']
ACID = ['#000000', '#103008', '#409010', '#a0e020', '#f0ff90']
IRON = ['#08080c', '#202028', '#404450', '#70788c', '#c0c8e0']
SMOKE = ['#000000', '#201c18', '#504840', '#908880', '#d0c8c0']
SEA = ['#000000', '#002840', '#0070a0', '#30c0e0', '#c0f8ff', '#ffffff']
SCALE = ['#001018', '#004058', '#0090a8', '#60e0e0', '#f0ffff']
SPIRIT = ['#000000', '#300838', '#a02090', '#ff60c0', '#ffd0f0', '#ffffff']
STEEL = ['#101018', '#383c48', '#787c90', '#b8c0d0', '#f0f4ff']
REDTIP = ['#200000', '#700808', '#d01818', '#ff7040', '#ffe0a0']
GHOST = ['#000000', '#002820', '#108060', '#50e0a0', '#d0ffe8', '#ffffff']
ARMY = ['#081008', '#283820', '#506840', '#90a870', '#e0f0c0']
SUN = ['#000000', '#601800', '#e04800', '#ff9818', '#ffe060', '#ffffe0']
EARTH = ['#000000', '#402008', '#a05818', '#f0a040', '#ffe8a0']
ABYSS = ['#000000', '#100020', '#400870', '#9030c0', '#e090ff']
NULL = ['#000000', '#202020', '#606060', '#b0b0b0', '#ffffff']
DATA = ['#000000', '#002808', '#00801c', '#20e050', '#b0ffc0', '#ffffff']
GLITCH = ['#000000', '#400030', '#c01080', '#ff60c0', '#ffe0f8']
PHOENIX = ['#000000', '#700800', '#e83000', '#ff8c10', '#ffe050', '#ffffff']


# ----------------------------------------------------------------- paintings
def smiley(laugh=False):
    """A round bomb with a face (the palette runs from the face's lines to its shine)."""
    x, y = grid()
    r = np.hypot(x - 16, y - 16)
    body = np.where(r < 13, 0.62 + 0.3 * clip(1 - np.hypot(x - 12, y - 10) / 9), 0.0)
    rim = (r > 11.5) & (r < 13)
    eyes = (np.hypot((x - 11.5) / 1.5, (y - 12.5) / 2.4) < 1) | (np.hypot((x - 20.5) / 1.5, (y - 12.5) / 2.4) < 1)
    rr = np.hypot(x - 16, y - 15)
    if laugh:
        mouth = (rr < 8.5) & (y > 18)
    else:
        mouth = (np.abs(rr - 7.5) < 1.1) & (y > 18)
    return np.where(r < 13, np.where(eyes | mouth | rim, 0.12, body), 0.0)


def burst(seed, spikes=9):
    """An explosion: a ragged ball with tongues thrown out of it."""
    r, ang = polar()
    edge = 8.5 + 3.5 * np.cos(ang * spikes + seed) * fbm(seed) * 2 + 3.5 * fbm(seed + 3)
    return clip(1.15 - r / edge) ** 0.7 * (0.55 + 0.7 * fbm(seed + 7))


def cloud(seed):
    """A soft lump of smoke or dust."""
    r, _ = polar()
    return clip(clip(1 - r / 14.5) ** 0.7 * (0.3 + 1.1 * fbm(seed)))


def grains(seed, count=14):
    """A handful of specks."""
    r = np.random.default_rng(seed)
    x, y = grid()
    lum = np.zeros((32, 32))
    for _ in range(count):
        cx, cy, s = 4 + r.random() * 24, 4 + r.random() * 24, 1.0 + r.random() * 1.4
        lum = np.maximum(lum, clip(1.3 - np.hypot(x - cx, y - cy) / s))
    return clip(lum)


def blossom():
    """A five-petalled flower seen from above."""
    r, ang = polar()
    edge = 4 + 9 * np.abs(np.cos(ang * 2.5)) ** 0.8
    return clip(clip(1.2 - r / edge) * (0.5 + 0.5 * clip(r / 8)) + 0.9 * clip(1 - r / 3.0))


def blob(seed):
    """A gout of ink: an uneven ball with a gleam."""
    x, y = grid()
    r, ang = polar()
    edge = 10 + 2.5 * np.sin(ang * 3 + seed) + 1.5 * np.sin(ang * 5 + 2 * seed)
    return np.where(r < edge, 0.3 + 0.3 * clip(1 - r / edge) + 0.7 * clip(1 - np.hypot(x - 12, y - 11) / 4.0), 0.0)


def splat(seed):
    """Ink thrown against something: a blot with fingers."""
    r, ang = polar()
    g = np.random.default_rng(seed)
    edge = 5.5 + sum(9.0 * np.abs(np.cos((ang - g.random() * 6.3) / 2)) ** 260 for _ in range(7))
    return np.where(r < edge, 0.3 + 0.45 * clip(1 - r / 8), 0.0)


def teardrop():
    x, y = grid()
    t = clip((y - 3) / 26)
    w = 6.5 * t ** 1.4 * np.sqrt(clip(1 - (np.clip(t - 0.75, 0, 1) / 0.25) ** 2))
    return np.where((np.abs(x - 16) < w) & (y > 3), 0.35 + 0.5 * clip(1 - np.hypot(x - 14, y - 22) / 3.0), 0.0)


def kiwi(step):
    """A small round bird seen head-on: a tuft, two eyes, a long beak, two legs (the palette is its feathers)."""
    x, y = grid()
    r = np.hypot((x - 16) / 10.0, (y - 14) / 9.5)
    body = np.where(r < 1, 0.45 + 0.35 * clip(1 - np.hypot(x - 13, y - 9) / 9) + 0.12 * (fbm(81) > 0.5), 0.0)
    tuft = np.maximum(segment(16, 6, 13, 1, 1.4), segment(16, 6, 19, 1, 1.4)) > 0.3
    eyes = (np.hypot(x - 12, y - 11) < 1.7) | (np.hypot(x - 20, y - 11) < 1.7)
    beak = (np.abs(x - 16) < 1.8 - 0.07 * (y - 13)) & (y > 13) & (y < 23)
    lift = 2 if step else 0
    legs = (segment(12, 22, 11, 30 - lift, 1.2) > 0.3) | (segment(20, 22, 21, 28 + lift, 1.2) > 0.3)
    lum = np.where(tuft | legs, 0.3, body)
    lum = np.where(beak, 0.98, lum)
    return np.where(eyes, 0.1, lum)


def feather():
    x, y = grid()
    u, v = (x - 16) * 0.8 + (y - 16) * 0.6, -(x - 16) * 0.6 + (y - 16) * 0.8
    return clip(1.2 - ((u / 4.0) ** 2 + (v / 12.0) ** 2)) * (0.5 + 0.5 * clip(1 - np.abs(u) / 1.2))


def pearl():
    """A pearl: a round body, light along one rim and a gleam."""
    x, y = grid()
    r = np.hypot(x - 16, y - 16)
    body = (r < 11) * (0.38 + 0.3 * clip((r - 5) / 6))
    return clip(body + clip(1 - np.hypot(x - 12, y - 11) / 4.5) + 0.5 * clip(1 - np.abs(r - 10) / 1.5) * (y > 16))


def bubble():
    x, y = grid()
    r = np.hypot(x - 16, y - 16)
    return clip(clip(1 - np.abs(r - 10) / 1.6) + 0.9 * clip(1 - np.hypot(x - 12, y - 11) / 2.5))


def crown():
    """Water thrown up: a ring of spouts, tall in the middle."""
    x, y = grid()
    lum = np.zeros((32, 32))
    for cx, top, w in ((16, 2, 3.2), (9, 9, 2.6), (23, 9, 2.6), (4, 17, 2.0), (28, 17, 2.0)):
        t = clip((y - top) / (31 - top))
        lum = np.maximum(lum, clip(1.2 - np.abs(x - cx) / (w * (0.3 + t))) * (y > top))
    return clip(lum * (0.6 + 0.5 * fbm(93)))


def fan():
    """Water thrown up from one point: jets spread like a fan from the cell's foot."""
    x, y = grid()
    dx, dy = x - 16, 31.5 - y
    a, rr = np.arctan2(dx, dy), np.hypot(dx, dy)
    jets = 0.35 + 0.65 * np.abs(np.cos(a * 4.5)) ** 3
    reach = 30 * (1 - 0.45 * np.abs(a)) * (0.8 + 0.4 * fbm(95))
    return clip(jets * clip(1.3 - rr / reach) * clip(rr / 5) * (np.abs(a) < 1.15) * 1.3)


def spark_ball(seed):
    """A knot of current: crooked arms out of a bright heart."""
    g = np.random.default_rng(seed)
    lum = glow(6, 1.0)
    for k in range(7):
        a = k * 0.9 + g.random() * 0.5
        px, py = 16.0, 16.0
        for j in range(3):
            a += (g.random() - 0.5) * 1.6
            qx, qy = px + 5.0 * math.cos(a), py + 5.0 * math.sin(a)
            lum = np.maximum(lum, segment(px, py, qx, qy, 1.5 - 0.3 * j))
            px, py = qx, qy
    return clip(lum)


def bolt(seed):
    """A bolt from the top of the cell to its foot."""
    g = np.random.default_rng(seed)
    pts = [(16 + (g.random() - 0.5) * 18 * (0 < k < 6), 1 + 5 * k) for k in range(7)]
    lum = np.zeros((32, 32))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        lum = np.maximum(lum, segment(x0, y0, x1, y1, 1.8))
    return clip(lum)


def swirl(turn=0.0):
    """Smoke wound into a spiral."""
    r, ang = polar()
    arm = np.cos(ang * 2 - r * 0.55 + turn)
    return clip(clip(arm) ** 0.8 * clip(1 - r / 15) ** 0.5 * (0.6 + 0.6 * fbm(101)) + 0.5 * glow(5, 1.0))


def eye():
    """An open eye: two lids and a slit pupil."""
    x, y = grid()
    lid = 7.5 * np.sqrt(clip(1 - ((x - 16) / 14.0) ** 2))
    rim = clip(1 - np.abs(np.abs(y - 16) - lid) / 1.4) * (np.abs(x - 16) < 14)
    iris = clip(1 - np.abs(np.hypot(x - 16, y - 16) - 5.5) / 1.3)
    pupil = clip(1.3 - np.hypot((x - 16) / 1.4, (y - 16) / 5.0))
    return clip(rim + iris * (np.abs(y - 16) < lid) + pupil)


def dial():
    """A clock's face: a rim and twelve marks, the quarters longer."""
    r, ang = polar()
    k = np.round(ang / (np.pi / 6))
    near = np.abs(ang - k * np.pi / 6) * r
    long_ = (k % 3 == 0)
    marks = clip(1.3 - near / 1.0) * (r < 12.5) * (r > np.where(long_, 8.0, 10.5))
    return clip(ring(14, 1.5) + marks + 0.6 * glow(3, 1.0))


def hand(length, width):
    """A clock hand from the middle of the cell upwards."""
    x, y = grid()
    w = width * clip((y - (16 - length)) / length + 0.15)
    return clip(1.3 - np.abs(x - 16) / np.maximum(w, 0.3)) * (y < 17.5) * (y > 16 - length)


def numeral_arc():
    """A broken ring: time's ripple."""
    r, ang = polar()
    return clip(1 - np.abs(r - 12.5) / 1.6) * (np.cos(ang * 6) > -0.3)


def web():
    """A spider's web: eight threads and three sagging rounds."""
    r, ang = polar()
    spokes = clip(1.2 - np.abs(np.sin(ang * 4)) * r / 0.9) * (r < 15)
    sag = np.abs(np.cos(ang * 4)) ** 0.7
    rounds = sum(clip(1 - np.abs(r - R * (0.82 + 0.18 * sag)) / 0.9) for R in (5.0, 9.5, 14.0))
    return clip(spokes * 0.9 + rounds)


def tangle(seed):
    """A ball of thread."""
    g = np.random.default_rng(seed)
    lum = np.zeros((32, 32))
    for _ in range(9):
        a, b = g.random() * 6.3, g.random() * 6.3
        lum = np.maximum(lum, segment(16 + 9 * math.cos(a), 16 + 9 * math.sin(a), 16 + 9 * math.cos(b),
                                      16 + 9 * math.sin(b), 1.2))
    return clip(lum + 0.4 * glow(10, 1.0))


def cannonball():
    x, y = grid()
    r = np.hypot(x - 16, y - 16)
    return np.where(r < 11, 0.15 + 0.3 * clip(1 - r / 11) + 0.75 * clip(1 - np.hypot(x - 12, y - 11) / 4.0), 0.0)


def muzzle_flash(points=6):
    r, ang = polar()
    edge = 3 + 12 * np.abs(np.cos(ang * points / 2)) ** 5 * (0.6 + 0.4 * np.cos(ang - 0.3))
    return clip(1.1 - r / np.maximum(edge, 0.5)) ** 0.6


def fish():
    """A fish with a harpoon for a snout, swimming to the right (the palette is its scales)."""
    x, y = grid()
    body = np.hypot((x - 14) / 9.0, (y - 16) / 5.0) < 1
    tail = (x < 7) & (np.abs(y - 16) < (7 - x) * 1.1 + 1) & (x > 0.5)
    fin = (np.abs(x - 13) < 3) & (y < 12) & (y > 8 + np.abs(x - 13))
    spear = (x > 21) & (np.abs(y - 16) < (31.5 - x) * 0.22 + 0.4)
    eye_ = np.hypot(x - 19, y - 14.5) < 1.4
    shade = 0.4 + 0.3 * clip((16 - y) / 5) + 0.15 * (np.sin(x * 1.6) > 0)
    lum = np.where(body, shade, np.where(tail | fin, 0.3, 0.0))
    lum = np.where(spear, 0.98, lum)
    return np.where(eye_, 0.1, lum)


def spray(seed):
    """Water torn off something fast: streaks and drops."""
    x, y = grid()
    return clip(clip(1 - np.abs(y - 16) / (2 + 9 * x / 32)) * fbm(seed, 32, 32) * 1.8 - 0.25) * clip(x / 6)


def needle():
    """A needle lying along the cell, its point to the right."""
    x, y = grid()
    w = 0.5 + 2.6 * clip((30 - x) / 30) ** 0.6
    core = clip(1.4 - np.abs(y - 16) / w) * (x < 31) * (x > 1)
    halo = 0.35 * clip(1 - np.abs(y - 16) / 7.0) * clip((x - 2) / 8) * clip((31 - x) / 4)
    return clip(core + halo)


def thread_line():
    x, y = grid()
    return clip(1 - np.abs(y - 16) / 1.6) * (0.5 + 0.5 * np.sin(x * 0.9) ** 2)


def cross_flare():
    """A long four-armed glint, one arm longer."""
    x, y = grid()
    a = clip(1 - np.abs(y - 16) / 1.5) * clip(1 - np.abs(x - 16) / 15.5)
    b = clip(1 - np.abs(x - 16) / 1.5) * clip(1 - np.abs(y - 16) / 10.0)
    return clip(a + b + glow(5, 1.0))


def arrow_bomb():
    """A finned bomb falling nose down (the palette is its metal)."""
    x, y = grid()
    body = (np.abs(x - 16) < 4.5) & (y > 6) & (y < 22)
    nose = (y >= 22) & (np.abs(x - 16) < (31 - y) * 0.52)
    fins = (y <= 9) & (y > 1) & (np.abs(x - 16) < 3.5 + (9 - y) * 0.8) & (np.abs(x - 16) > 1.0)
    band_ = body & (np.abs(y - 12) < 1.2)
    lum = np.where(body, 0.45 + 0.4 * clip(1 - np.abs(x - 14) / 3.0), 0.0)
    lum = np.where(fins, 0.3, lum)
    lum = np.where(band_, 0.12, lum)
    return np.where(nose, 0.8, lum)


def flame_tail():
    """A jet's flame, hot at its foot, pointing up the cell."""
    x, y = grid()
    t = clip((30 - y) / 26)
    w = 6 * (1 - t) ** 0.7 + 0.5
    return clip(1.2 - np.abs(x - 16 - 1.5 * np.sin(y * 0.8)) / w) * (y < 30) * (y > 3) * (0.35 + 0.8 * (1 - t))


def skull():
    """A skull seen head-on."""
    x, y = grid()
    cranium = np.hypot((x - 16) / 10.5, (y - 13) / 10.0) < 1
    jaw = (np.abs(x - 16) < 6.0) & (y >= 20) & (y < 28)
    sockets = (np.hypot((x - 11.5) / 3.2, (y - 14) / 3.6) < 1) | (np.hypot((x - 20.5) / 3.2, (y - 14) / 3.6) < 1)
    nose = (np.abs(x - 16) < (y - 17) * 0.5) & (y > 17) & (y < 21)
    teeth = jaw & (np.abs(((x - 10.5) % 3) - 1.5) < 0.45) & (y > 23)
    lum = np.where(cranium | jaw, 0.7 + 0.3 * clip(1 - np.hypot(x - 13, y - 8) / 9), 0.0)
    return np.where(sockets | nose | teeth, 0.0, lum)


def tracer():
    x, y = grid()
    return clip(1.2 - np.abs(y - 16) / (1.0 + 3.0 * x / 32)) * clip(x / 5) * (0.6 + 0.5 * fbm(131))


def wisp(seed):
    """A rag of mist rising."""
    x, y = grid()
    cx = 16 + 4 * np.sin(y * 0.35 + seed)
    return clip(1.1 - np.abs(x - cx) / (2 + 5 * clip((y - 2) / 28))) * clip((y - 1) / 6) * clip((31 - y) / 5) * \
        (0.5 + 0.7 * fbm(seed))


def missile():
    """A fat missile flying to the right (the palette is its plating)."""
    x, y = grid()
    body = (x > 5) & (x < 23) & (np.abs(y - 16) < 6.5)
    nose = (x >= 23) & (np.hypot((x - 23) / 8.0, (y - 16) / 6.5) < 1)
    fins = (x <= 9) & (x > 1) & (np.abs(y - 16) < 6.5 + (9 - x) * 0.9) & (np.abs(y - 16) > 2.0)
    lum = np.where(body | nose, 0.4 + 0.45 * clip(1 - np.abs(y - 12.5) / 3.5), 0.0)
    lum = np.where(fins, 0.28, lum)
    lum = np.where(body & (np.abs(x - 19) < 1.3), 0.12, lum)
    face = (np.hypot(x - 26, y - 14) < 1.3) | ((np.abs(np.hypot(x - 25, y - 15) - 3.5) < 0.8) & (y > 16.5) & (x > 23))
    return np.where(face & nose, 0.1, lum)


def jet():
    """A rocket's flame lying along the cell, hot at its right end."""
    x, y = grid()
    t = clip(x / 30)
    w = 1.0 + 6.5 * t ** 0.8
    return clip(1.25 - np.abs(y - 16 - 1.3 * np.sin(x * 0.9)) / w) * (0.25 + 0.9 * t) * (x < 31)


def sun(seed):
    """A ball of fire with a grained skin and a hot rim."""
    r, ang = polar()
    skin = (r < 12.5) * (0.5 + 0.55 * fbm(seed)) * (0.7 + 0.4 * clip(r / 12))
    rim = clip(1 - np.abs(r - 12.5) / 2.0)
    lick = clip(1 - np.abs(r - 14.2) / 1.6) * clip(np.cos(ang * 7 + seed) * 1.5)
    return clip(skin + rim + 0.7 * lick)


def corona(points=12):
    """Rays around something bright."""
    r, ang = polar()
    rays = np.abs(np.cos(ang * points / 2)) ** 6 * (0.6 + 0.4 * np.cos(ang * 3) ** 2)
    return clip(rays * clip(1 - r / 16) ** 0.6 * clip(r / 5))


def firewall(seed):
    """A sheet of flame standing on the cell's foot."""
    x, y = grid()
    top = 4 + 9 * fbm(seed)[0][None, :].repeat(32, 0) + 6 * np.abs(x - 16) / 16
    return clip((y - top) / 6) * clip(1.2 - np.abs(x - 16) / 13.0) * (0.45 + 0.7 * fbm(seed + 4)) * (0.6 + 0.4 * y / 32)


def rock():
    x, y = grid()
    d = np.abs(x - 16) / 8.0 + np.abs(y - 16) / 10.0 + 0.25 * np.sin(x * 0.9) * np.sin(y * 0.7)
    return np.where(d < 1, 0.35 + 0.5 * clip((16 - y) / 10 + (16 - x) / 20), 0.0)


def pentagon(turn=0.0, width=1.5):
    """The outline of a pentagon."""
    pts = [(16 + 13 * math.cos(turn + 2 * math.pi * k / 5 - math.pi / 2),
            16 + 13 * math.sin(turn + 2 * math.pi * k / 5 - math.pi / 2)) for k in range(5)]
    lum = np.zeros((32, 32))
    for k in range(5):
        lum = np.maximum(lum, segment(*pts[k], *pts[(k + 1) % 5], width))
    return clip(lum)


def void_rim(seed):
    """The torn edge of a hole."""
    r, ang = polar()
    edge = 11.5 + 2.0 * np.sin(ang * 5 + seed) * fbm(seed)
    return clip(1 - np.abs(r - edge) / (1.2 + 2.5 * fbm(seed + 2))) + 0.3 * clip(1 - np.abs(r - edge - 2) / 3)


def hole(radius=12.0):
    r, _ = polar()
    return clip((radius - r) / 2.0)


def streak_in():
    """A sliver drawn towards the middle."""
    x, y = grid()
    return clip(1.2 - np.abs(x - 16) / (0.6 + 2.0 * clip((y - 2) / 28))) * clip((y - 1) / 4) * clip((31 - y) / 3)


def block():
    x, y = grid()
    inside = (np.abs(x - 16) < 11) & (np.abs(y - 16) < 11)
    edge = inside & ((np.abs(x - 16) > 8.5) | (np.abs(y - 16) > 8.5))
    return np.where(edge, 1.0, np.where(inside, 0.4, 0.0))


def bit(one):
    """A 1 or a 0 in thick strokes."""
    x, y = grid()
    if one:
        lum = np.maximum(segment(16, 5, 16, 27, 2.4), segment(16, 5, 11, 10, 2.2))
        return clip(np.maximum(lum, segment(11, 27, 21, 27, 2.2)) * 1.4)
    r = np.hypot((x - 16) / 7.5, (y - 16) / 11.0)
    return clip(1.3 - np.abs(r - 0.85) / 0.25)


def mosaic(seed, cellsize=4):
    """Squares switched on at random."""
    g = np.random.default_rng(seed)
    n = 32 // cellsize
    m = (g.random((n, n)) > 0.55) * (0.4 + 0.6 * g.random((n, n)))
    lum = np.kron(m, np.ones((cellsize, cellsize)))
    x, y = grid()
    return lum * ((x % cellsize > 0.6) & (y % cellsize > 0.6)) * clip(1.4 - np.hypot(x - 16, y - 16) / 15)


def scanline():
    x, y = grid()
    return clip(1 - np.abs(y - 16) / 2.2) * (0.5 + 0.5 * (np.sin(x * 1.3) > -0.2))


def firebird(flap):
    """A bird of flame flying at the viewer: a head with a beak, a fanned tail and two broad feathered wings, raised
    or swept down."""
    x, y = grid()
    d = np.abs(x - 16)
    body = clip(1.4 - np.hypot((x - 16) / 3.4, (y - 16.5) / 6.5))
    head = np.maximum(clip(1.5 - np.hypot(x - 16, y - 8.5) / 2.8), 1.0 * ((d < (13.5 - y) * 0.5) & (y > 9) & (y < 13.5)))
    if flap:
        top = 14.5 - 0.95 * d + 0.012 * d ** 2
    else:
        top = 11.0 - 0.35 * d + 0.065 * d ** 2
    thick = 1.5 + 7.5 * clip(1 - d / 15.5) ** 0.7
    scallop = 1.6 * np.abs(np.sin(d * 0.95))
    wing = (d > 1.5) & (d < 15.5) & (y > top) & (y < top + thick + scallop)
    wings = wing * (0.55 + 0.45 * clip(1 - (y - top) / 5.0))
    fan_ = (y > 20) & (d < (y - 19) * 0.62) * (y < 31.5)
    tail = fan_ * (0.45 + 0.5 * np.abs(np.cos(np.arctan2(x - 16, y - 18) * 5)))
    lum = np.maximum(np.maximum(body, head), np.maximum(wings, tail))
    return clip(lum * (0.8 + 0.4 * fbm(151)))


def plume():
    """A feather of fire."""
    x, y = grid()
    u, v = (x - 16) * 0.75 - (y - 16) * 0.66, (x - 16) * 0.66 + (y - 16) * 0.75
    return clip(1.25 - ((u / 4.5) ** 2 + (v / 13.0) ** 2)) * (0.45 + 0.6 * clip(1 - np.abs(u) / 1.5)) * \
        (0.7 + 0.5 * fbm(153))


# ----------------------------------------------------------------- shared pieces
def raised(fx, out, tenths, reach=0):
    """out = a point on the caster, `tenths` of its height up, `reach` past its radius towards the target."""
    fx.vcopy(out, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), tenths, 0, 10); fx.sub_(at(out, 1), fx.T3)
    if reach:
        ahead(fx, out, out, reach)


def lob(fx, out, ticks, height):
    """out = the travelling instance's place lifted along an arc that peaks `height` up, halfway."""
    fx.lin(fx.T, FRAME, 2048 // ticks); fx.sin(fx.T2, fx.T, height)
    fx.vcopy(out, POS); fx.sub_(at(out, 1), fx.T2)


def behind(fx, out, num, den=1):
    """out = where the flying instance (its step at FREE) was num/den ticks ago."""
    fx.vcopy(fx.TV, iv(FREE)); fx.vmul(fx.TV, num)
    if den != 1:
        fx.vdiv(fx.TV, den)
    fx.vcopy(out, POS); fx.vsub(out, fx.TV)


def sideways(fx, side, width):
    """side = a ground vector of that length across the line from the caster to the target."""
    ok = fx.label()
    fx.vcopy(fx.TV, fx.TGT); fx.vsub(fx.TV, fx.SRC); fx.set(at(fx.TV, 1), 0)
    fx.vlen(fx.T, fx.TV); fx.br(fx.T, '>', 0, ok); fx.set(fx.T, 1)
    fx.label(ok)
    fx.lin(at(side, 0), at(fx.TV, 2), width, 0, fx.T); fx.set(at(side, 1), 0)
    fx.lin(at(side, 2), at(fx.TV, 0), -width, 0, fx.T)


# ----------------------------------------------------------------- PrinceMamemon
def smiley_warhead():
    """PrinceMamemon tosses a grinning bomb high; it tumbles down its arc with a sputtering fuse, opens its mouth wide
    just before it lands on the target and goes up in a ball of fire, smoke and stars."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(SMILE); fx.palette(BLAST)
    fx.paint(0, smiley()); fx.paint(1, smiley(True)); fx.paint(2, burst(61)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(5, 2.5, 10, 5)); fx.paint(5, cloud(63)); fx.paint(6, ring(13, 2.2)); fx.paint(7, burst(67, 7))
    tint, warm = fx.colour(128, 128, 128), fx.colour(128, 90, 30)
    top = fx.vec()
    fly = 14
    fx.particle('fuse', 14, 6, 4, (128, 110, 60), (60, 100), grow=-9, speed=14, lift=12, clut=1, spin=30)
    fx.particle('boom', 1, 9, 2, (128, 128, 128), 220, grow=95, fade=True, clut=1)
    fx.particle('boom2', 1, 11, 7, (128, 110, 80), 160, grow=75, fade=True, clut=1, spin=6)
    fx.particle('wave', 1, 8, 6, (128, 100, 50), 160, grow=120, fade=True, clut=1)
    fx.particle('smoke', 8, 16, 5, (60, 50, 40), (220, 320), grow=16, speed=16, lift=16, spread=220, fade=True, clut=1)
    fx.particle('confetti', 18, 15, 4, (128, 128, 90), (80, 140), grow=-5, speed=75, lift=65, gravity=9, spread=80,
                spin=25, clut=1)
    fx.label('main'); fx.when(0, 'begin'); fx.end(1)
    fx.label('begin')
    raised(fx, top, 11, 30); fx.vcopy(fx.AT, top); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('bomb'); fx.sound(3); fx.ret()
    fx.travel('bomb', 1, fly, 'bomb_render', 'bomb_arrive', every='bomb_trail')
    fx.label('bomb_trail'); lob(fx, fx.TV2, fly, 520); fx.sub_(at(fx.TV2, 1), 110); fx.emit('fuse', fx.TV2); fx.ret()
    fx.label('bomb_render')
    lob(fx, fx.TV2, fly, 520)
    fx.lin(fx.F1, FRAME, 26); fx.lin(fx.T3, FRAME, 14, 300)
    fx.lin(fx.F2, fx.T3, 15, 0, 10); fx.sprite(fx.TV2, warm, fx.F2, cell=3, clut=1)
    fx.br(FRAME, '>=', fly - 4, 'bomb_laugh')
    fx.sprite(fx.TV2, tint, fx.T3, cell=0, blend=None, rot=fx.F1); fx.ret()
    fx.label('bomb_laugh'); fx.sprite(fx.TV2, tint, fx.T3, cell=1, blend=None); fx.ret()
    fx.label('bomb_arrive')
    fx.sound(15); fx.aim(); fx.hit()
    fx.emit('boom', fx.TCHEST); fx.emit('boom2'); fx.emit('wave'); fx.emit('smoke', times=6)
    fx.emit('confetti', times=16); fx.ret()
    return fx


# ----------------------------------------------------------------- Floramon
def rain_of_pollen():
    """Floramon's flower hands open and breathe out a slow yellow cloud that rolls to where the target stood, pollen
    glittering in it; it settles there and stings whoever is still inside."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(POLLEN); fx.palette(LEAF)
    fx.paint(0, cloud(71)); fx.paint(1, cloud(75)); fx.paint(2, grains(73)); fx.paint(3, grains(77, 9))
    fx.paint(4, blossom()); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, glow(15, 1.2))
    soft = fx.colour(90, 80, 20)
    hands, spot = fx.vec(), fx.vec()
    roll = 16
    fx.particle('bloom', 2, 10, 4, (128, 128, 128), 60, grow=26, fade=True, clut=1, spin=8)
    fx.particle('puff', 22, 12, 0, (84, 74, 20), (200, 300), grow=14, speed=16, spread=200, fade=True)
    fx.particle('puff2', 12, 12, 1, (70, 64, 16), (220, 320), grow=14, speed=16, spread=220, fade=True)
    fx.particle('grain', 20, 10, 2, (128, 128, 100), (150, 240), speed=22, gravity=2, spread=260, spin=14)
    fx.particle('glint', 14, 7, 5, (128, 128, 90), (60, 120), grow=-8, spread=380)
    fx.particle('settle', 10, 14, 3, (128, 120, 70), (220, 320), grow=6, speed=30, lift=24, gravity=3, spread=300,
                fade=True)
    fx.particle('sting', 1, 8, 6, (128, 120, 50), 200, grow=70, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.end(1)
    fx.label('begin')
    raised(fx, hands, 6, 40); fx.vcopy(spot, fx.TGT)
    fx.emit('bloom', hands); fx.sound(-55)
    fx.vcopy(fx.AT, hands); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('drift'); fx.ret()
    fx.travel('drift', 1, roll, 'noop', 'drift_arrive', every='drift_trail')
    fx.label('drift_trail')
    fx.emit('puff', POS, 2); fx.emit('puff2'); fx.emit('grain'); fx.emit('glint'); fx.ret()
    fx.label('drift_arrive')
    fx.sound(34); fx.strike(spot, 260)
    fx.vcopy(fx.AT, POS); fx.call('settle', 10); fx.call('sting'); fx.call('puff2', 4); fx.call('glint', 6); fx.ret()
    return fx


# ----------------------------------------------------------------- Octomon
def spurting_ink():
    """Octomon spits three gouts of black ink one after another, each trailing drops; the first that lands on the
    target blots it and splashes ink all around. A target that moves away is missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(INK); fx.palette(MIST)
    fx.paint(0, blob(1)); fx.paint(1, blob(4)); fx.paint(2, teardrop()); fx.paint(3, splat(5)); fx.paint(4, splat(9))
    fx.paint(5, cloud(83)); fx.paint(6, ring(12, 2.5))
    tint = fx.colour(128, 128, 128)
    mouth = fx.vec()
    landed = fx.const(0)
    first, gap = 3, 5
    fx.particle('drip', 18, 9, 2, (128, 128, 128), (90, 150), grow=-6, speed=8, gravity=9, spread=60, blend=None)
    fx.particle('squirt', 3, 6, 6, (90, 110, 128), 140, grow=60, fade=True, clut=1)
    fx.particle('blot', 3, 12, 3, (128, 128, 128), 260, grow=44, blend=None)
    fx.particle('blot2', 3, 12, 4, (128, 128, 128), 150, grow=44, blend=None, spin=3)
    fx.particle('murk', 6, 12, 5, (90, 90, 80), (260, 360), grow=18, spread=160, blend='sub', fade=True)
    fx.particle('fling', 22, 13, 2, (128, 128, 128), (100, 170), grow=-5, speed=60, lift=70, gravity=12, spread=80,
                blend=None, spin=20)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(3):
        fx.when(first + gap * k, 'spit')
    fx.end(first + 2 * gap + 1)
    fx.label('begin'); raised(fx, mouth, 5, 40); fx.sound(-55); fx.ret()
    fx.label('spit')
    fx.sound(3); fx.aim(); fx.vcopy(fx.AT, mouth); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('gout')
    fx.emit('squirt', mouth); fx.ret()
    fx.shot('gout', 3, 72, 24, 'gout_render', 'gout_arrive', miss='gout_miss', every='gout_trail')
    fx.label('gout_trail')
    fx.emit('drip', POS)
    fx.br(landed, '==', 0, 'noop')
    fx.aim(); fx.vcopy(fx.TV, fx.TCHEST); fx.vsub(fx.TV, POS); fx.vlen(fx.T, fx.TV)
    fx.br(fx.T, '>', 190, 'noop')
    fx.call('gout_splash'); fx.set(FRAME, -1); fx.ret()
    fx.label('gout_miss'); fx.emit('fling', POS, 4); fx.ret()
    fx.label('gout_render'); flicker(fx, POS, tint, 420, (0, 1), blend=None, every=2); fx.ret()
    fx.label('gout_arrive'); fx.set(landed, 1)
    fx.label('gout_splash')
    fx.sound(7); fx.emit('blot', POS); fx.emit('blot2'); fx.emit('murk', times=2); fx.emit('fling', times=7); fx.ret()
    return fx


# ----------------------------------------------------------------- Kiwimon
def pummel_peck():
    """A little kiwi bird drops at Kiwimon's feet and pelts along the ground at the target, bobbing and kicking up
    dust; it blows up in feathers against whoever it runs into. A target that moves out of its way is missed."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(KIWI); fx.palette(DUST); fx.palette(BLAST)
    fx.paint(0, kiwi(0)); fx.paint(1, kiwi(1)); fx.paint(2, cloud(85)); fx.paint(3, feather()); fx.paint(4, burst(87, 13))
    fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.2))
    tint = fx.colour(128, 128, 128)
    feet = fx.vec()
    fx.particle('hatch', 1, 6, 6, (128, 120, 80), 80, grow=60, fade=True, clut=1)
    fx.particle('dust', 20, 9, 2, (90, 80, 60), (130, 200), grow=16, speed=8, lift=10, spread=60, fade=True, clut=1)
    fx.particle('pop', 1, 8, 4, (128, 128, 128), 220, grow=80, fade=True, clut=2)
    fx.particle('shock', 1, 7, 6, (128, 100, 60), 140, grow=110, fade=True, clut=2)
    fx.particle('plume', 20, 18, 3, (128, 128, 128), (150, 230), speed=45, lift=60, gravity=5, spread=100, spin=18,
                blend=None)
    fx.particle('pip', 10, 10, 5, (128, 120, 80), (70, 130), grow=-7, speed=60, lift=30, gravity=6, spread=60, clut=2)
    fx.label('main'); fx.when(0, 'begin'); fx.when(4, 'go'); fx.end(5)
    fx.label('begin'); ahead(fx, feet, fx.SRC, 90); fx.emit('hatch', feet); fx.sound(34); fx.ret()
    fx.label('go'); fx.aim(); fx.vcopy(fx.AT, feet); fx.vcopy(fx.DEST, fx.TGT); fx.call('chick'); fx.ret()
    fx.shot('chick', 1, 62, 30, 'chick_render', 'chick_arrive', miss='chick_miss', every='chick_trail')
    fx.label('chick_trail')
    fx.emit('dust', POS)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 3); fx.br(fx.T2, '!=', 0, 'noop'); fx.sound(20); fx.ret()
    fx.label('chick_miss'); fx.emit('dust', POS, 5); fx.ret()
    fx.label('chick_render')
    fx.lin(fx.T, FRAME, 1024); fx.sin(fx.T3, fx.T, 50)
    fx.br(fx.T3, '>=', 0, 'chick_up'); fx.mul(fx.T3, -1)
    fx.label('chick_up')
    fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), 200); fx.sub_(at(fx.TV2, 1), fx.T3)
    flicker(fx, fx.TV2, tint, 470, (0, 1), blend=None, every=1); fx.ret()
    fx.label('chick_arrive')
    fx.sound(15); fx.vcopy(fx.AT, POS); fx.sub_(at(fx.AT, 1), 160)
    fx.call('pop'); fx.call('shock'); fx.call('plume', 16); fx.call('pip', 8); fx.call('dust', 5); fx.ret()
    return fx


# ----------------------------------------------------------------- Syakomon
def pearl_shot():
    """Light wells up in Syakomon's open shell and a pearl leaves it, bubbles peeling off behind; it bursts on the
    target in a crown of water and a shower of bubbles."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(PEARL); fx.palette(ROSE)
    fx.paint(0, pearl()); fx.paint(1, bubble()); fx.paint(2, glow(15, 1.2)); fx.paint(3, crown())
    fx.paint(4, ring(13, 1.8)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, spray(91))
    tint, sheen, soft = fx.colour(128, 128, 128), fx.colour(128, 90, 110), fx.colour(50, 80, 128)
    shell = fx.vec()
    well, fly = 7, 7
    gather(fx, 'bead', 12, 5, (110, 120, 128), 80, 420, 5)
    fx.particle('lustre', 1, well, 2, (128, 100, 120), 60, grow=40, clut=1)
    fx.particle('wake', 16, 12, 1, (110, 120, 128), (60, 130), grow=4, speed=10, lift=14, spread=70, fade=True)
    fx.particle('spout', 1, 9, 3, (120, 128, 128), 320, grow=50, fade=True, sy=22)
    fx.particle('ripple', 2, 9, 4, (90, 120, 128), 160, grow=90, fade=True, sy=6)
    fx.particle('froth', 18, 16, 1, (120, 128, 128), (70, 150), speed=45, lift=55, gravity=5, spread=120, fade=True)
    fx.particle('gleam', 1, 6, 5, (128, 128, 128), 200, grow=70, fade=True, clut=1)
    fx.label('main'); fx.when(0, 'begin'); fx.when(well, 'fire')
    fx.br(fx.NOW, '>', well - 3, 'main_end'); fx.emit('bead', shell, 2)
    fx.label('main_end'); fx.end(well + 1)
    fx.label('begin'); raised(fx, shell, 5, 30); fx.emit('lustre', shell); fx.sound(-55); fx.ret()
    fx.label('fire')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, shell); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('orb'); fx.ret()
    fx.travel('orb', 1, fly, 'orb_render', 'orb_arrive', every='orb_trail')
    fx.label('orb_trail'); fx.emit('wake', POS, 2); fx.ret()
    fx.label('orb_render')
    fx.sprite(POS, soft, 420, cell=2); fx.sprite(POS, sheen, 300, cell=4, clut=1)
    fx.sprite(POS, tint, 230, cell=0); fx.ret()
    fx.label('orb_arrive')
    fx.sound(7); fx.aim(); fx.hit()
    fx.emit('gleam', fx.TCHEST); fx.emit('froth', times=14)
    fx.vcopy(fx.AT, fx.TGT); fx.sub_(at(fx.AT, 1), 200); fx.call('spout')
    fx.emit('ripple', fx.TGT); fx.ret()
    return fx


# ----------------------------------------------------------------- Gazimon
def e_stun_blast():
    """Current knots in Gazimon's jaws and is spat as a crackling ball that jumps forward along a jagged path; where
    it lands, bolts stab down on the target and leave it twitching. A target that moves away is missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(VOLT)
    fx.paint(0, spark_ball(3)); fx.paint(1, spark_ball(8)); fx.paint(2, bolt(5)); fx.paint(3, bolt(12))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, star(4, 1.5, 11, 9)); fx.paint(6, ring(13, 1.6))
    tint, haze = fx.colour(128, 128, 128), fx.colour(70, 50, 128)
    jaws = fx.vec()
    charge = 6
    fx.particle('knot', 1, charge, 0, (128, 128, 128), 60, grow=36, spin=40)
    fx.particle('fizz', 16, 5, 5, (128, 128, 110), (60, 130), grow=-10, spread=200)
    fx.particle('strike1', 3, 5, 2, (128, 128, 128), 420, sy=30, spread=160)
    fx.particle('strike2', 3, 5, 3, (128, 128, 128), 420, sy=30, spread=160)
    fx.particle('flash', 1, 6, 4, (128, 120, 128), 240, grow=60, fade=True)
    fx.particle('hoop', 2, 7, 6, (128, 120, 60), 120, grow=80, fade=True)
    fx.particle('twitch', 12, 6, 5, (128, 128, 90), (90, 170), grow=-10, speed=50, spread=120)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'spit')
    fx.br(fx.NOW, '>', charge, 'main_end'); fx.emit('fizz', jaws)
    fx.label('main_end'); fx.end(charge + 1)
    fx.label('begin'); raised(fx, jaws, 7, 40); fx.emit('knot', jaws); fx.sound(-55); fx.ret()
    fx.label('spit')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, jaws); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('ball'); fx.ret()
    fx.shot('ball', 1, 78, 24, 'ball_render', 'ball_arrive', miss='ball_miss', every='ball_trail')
    fx.label('ball_trail'); fx.emit('fizz', POS, 2); fx.ret()
    fx.label('ball_miss'); fx.emit('twitch', POS, 6); fx.ret()
    fx.label('ball_render')
    fx.rnd(fx.T3, -60, 60); fx.vcopy(fx.TV2, POS); fx.add(at(fx.TV2, 1), fx.T3)
    fx.sprite(fx.TV2, haze, 460, cell=4)
    fx.rnd(fx.F1, 0, 359); fx.rnd(fx.T3, 0, 1); fx.br(fx.T3, '==', 0, 'ball_b')
    fx.sprite(fx.TV2, tint, 380, cell=0, rot=fx.F1); fx.ret()
    fx.label('ball_b'); fx.sprite(fx.TV2, tint, 380, cell=1, rot=fx.F1); fx.ret()
    fx.label('ball_arrive')
    fx.sound(16); fx.vcopy(fx.KEEP, POS)
    fx.emit('flash', POS); fx.emit('hoop'); fx.emit('twitch', times=8)
    fx.vcopy(fx.AT, POS); fx.sub_(at(fx.AT, 1), 170); fx.call('strike1', 3); fx.call('strike2', 3)
    fx.vcopy(fx.AT, fx.KEEP); fx.call('after'); fx.ret()
    after = fx.pool('after', 1)
    fx.begin('after', after, 'noop', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('after_tick')
    fx.life(10)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 3); fx.br(fx.T2, '!=', 0, 'noop')
    fx.sound(34); fx.vcopy(fx.AT, POS); fx.sub_(at(fx.AT, 1), 170); fx.call('strike1'); fx.call('strike2')
    fx.emit('twitch', POS, 2); fx.ret()
    return fx


# ----------------------------------------------------------------- Tapirmon
def waking_dream():
    """Tapirmon breathes out a trail of violet dream-smoke that winds its way to the target and closes over it; an
    eye opens in the coil of smoke, stares, and the nightmare bursts."""
    fx = Fx(delay=8, cast_sound=1, draw=True)
    fx.palette(DREAM)
    fx.paint(0, swirl()); fx.paint(1, swirl(2.1)); fx.paint(2, eye()); fx.paint(3, cloud(103)); fx.paint(4, cloud(107))
    fx.paint(5, wisp(3)); fx.paint(6, star(4, 2, 9, 6)); fx.paint(7, glow(15, 1.2))
    tint, dim, wash = fx.colour(128, 128, 128), fx.colour(80, 50, 110), fx.vec()
    snout = fx.vec()
    reach, stare = 10, 12
    fx.particle('fume', 24, 12, 3, (70, 40, 100), (180, 260), grow=14, speed=10, lift=8, spread=120, fade=True)
    fx.particle('fume2', 12, 12, 4, (90, 40, 90), (160, 240), grow=14, speed=10, lift=8, spread=120, fade=True)
    fx.particle('ghost', 10, 14, 5, (110, 80, 128), (220, 320), flat=((-14, 14), (-50, -24), (-14, 14)), spread=260,
                fade=True)
    fx.particle('shard', 14, 10, 6, (128, 100, 128), (80, 150), grow=-8, speed=70, spread=80)
    fx.particle('pop', 1, 8, 7, (128, 90, 128), 260, grow=80, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.end(reach + stare + 12)
    fx.label('draw')
    fx.br(fx.NOW, '<', reach, 'noop'); fx.br(fx.NOW, '>', reach + stare, 'noop')
    fx.lin(fx.T, fx.NOW, 5, -5 * reach); fx.br(fx.T, '<', 34, 'draw_dim'); fx.set(fx.T, 34)
    fx.label('draw_dim'); fx.lin(fx.T2, fx.T, 1, 0, 2); fx.vset(wash, fx.T2, fx.T, fx.T2)
    fx.overlay(wash, blend='sub'); fx.ret()
    fx.label('begin')
    raised(fx, snout, 6, 40); fx.sound(-55)
    fx.vcopy(fx.AT, snout); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('drift'); fx.ret()
    fx.travel('drift', 1, reach, 'noop', 'drift_arrive', every='drift_trail')
    fx.label('drift_trail')
    fx.lin(fx.T, FRAME, 700); fx.sin(fx.T3, fx.T, 130); fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), fx.T3)
    fx.emit('fume', fx.TV2, 2); fx.emit('fume2'); fx.ret()
    fx.label('drift_arrive'); fx.aim(); fx.vcopy(fx.AT, fx.TCHEST); fx.call('coil'); fx.ret()
    coil = fx.pool('coil', 1)
    fx.begin('coil', coil, 'coil_render', inherit=False); fx.vcopy(POS, fx.AT); fx.sound(34); fx.ret()
    fx.label('coil_tick')
    fx.br(FRAME, '>', stare, 'coil_end')
    fx.aim(); fx.vcopy(POS, fx.TCHEST)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '!=', 0, 'noop'); fx.emit('ghost', POS); fx.ret()
    fx.label('coil_end')
    fx.sound(15); fx.aim(); fx.hit()
    fx.emit('pop', fx.TCHEST); fx.emit('shard', times=14); fx.emit('ghost', times=4); fx.set(FRAME, -1); fx.ret()
    fx.label('coil_render')
    fx.lin(fx.T3, FRAME, 60, 200); fx.br(fx.T3, '<', 620, 'coil_draw'); fx.set(fx.T3, 620)
    fx.label('coil_draw')
    fx.lin(fx.F1, FRAME, -22); fx.lin(fx.F2, FRAME, 31)
    fx.sprite(POS, dim, fx.T3, cell=1, rot=fx.F2)
    fx.lin(fx.T, fx.T3, 8, 0, 10); fx.sprite(POS, tint, fx.T, cell=0, rot=fx.F1)
    fx.br(FRAME, '<', 4, 'noop')            # the eye opens
    fx.lin(fx.T2, FRAME, 50, -180); fx.br(fx.T2, '<', 170, 'coil_eye'); fx.set(fx.T2, 170)
    fx.label('coil_eye'); fx.sprite(POS, tint, 300, fx.T2, cell=2); fx.ret()
    return fx


# ----------------------------------------------------------------- Clockmon
def chrono_breaker():
    """A clock face of light opens in the air behind the target, its two hands racing round; they snap together at
    twelve, the field greys for a beat as time stops, and the dial breaks in rings that shake the target."""
    fx = Fx(delay=8, cast_sound=1, draw=True)
    fx.palette(TIME); fx.palette(BRASS)
    fx.paint(0, dial()); fx.paint(1, hand(13, 2.2)); fx.paint(2, hand(8.5, 3.0)); fx.paint(3, numeral_arc())
    fx.paint(4, glow(15, 1.2)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 1.6))
    tint, brass, wash = fx.colour(128, 128, 128), fx.colour(128, 110, 70), fx.vec()
    amber = fx.colour(56, 40, 16)
    wind, hold = 16, 5
    snap = wind + hold
    fx.particle('tick', 16, 8, 5, (128, 128, 110), (60, 120), grow=-7, spread=620, clut=1)
    fx.particle('ripple', 4, 9, 3, (128, 128, 128), 300, grow=110, fade=True, spin=9)
    fx.particle('ripple2', 3, 9, 6, (128, 110, 60), 200, grow=130, fade=True, clut=1)
    fx.particle('cog', 14, 12, 5, (128, 120, 80), (90, 160), grow=-6, speed=70, lift=30, gravity=6, spread=100,
                clut=1, spin=30)
    fx.particle('still', 1, 6, 4, (128, 128, 128), 300, grow=60, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.end(snap + 12)
    fx.label('draw')
    fx.br(fx.NOW, '<', wind, 'noop'); fx.br(fx.NOW, '>', snap + 2, 'noop')
    fx.vset(wash, 44, 28, 20); fx.overlay(wash, blend='sub'); fx.ret()
    fx.label('begin'); fx.vcopy(fx.AT, fx.TCHEST); fx.call('clock'); fx.sound(34); fx.ret()
    clock = fx.pool('clock', 1)
    fx.begin('clock', clock, 'clock_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.lin(fx.T, at(fx.TSIZE, 1), 5, 120, 10); fx.sub_(at(POS, 1), fx.T); fx.ret()
    fx.label('clock_tick')
    fx.br(FRAME, '==', wind, 'clock_stop'); fx.br(FRAME, '>=', snap, 'clock_break')
    fx.br(FRAME, '>', wind, 'noop')
    fx.emit('tick', POS)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 4); fx.br(fx.T2, '!=', 0, 'noop'); fx.sound(20); fx.ret()
    fx.label('clock_stop'); fx.sound(1); fx.emit('still', POS); fx.ret()
    fx.label('clock_break')
    fx.sound(15); fx.vcopy(fx.KEEP, POS); fx.aim(); fx.hit()
    fx.emit('ripple', fx.TCHEST, 1); fx.emit('ripple2'); fx.emit('cog', times=14)
    fx.emit('ripple', fx.KEEP); fx.emit('ripple2'); fx.set(FRAME, -1); fx.ret()
    fx.label('clock_render')
    fx.lin(fx.T3, FRAME, 110, 120); fx.br(fx.T3, '<', 760, 'clock_size'); fx.set(fx.T3, 760)
    fx.label('clock_size')
    fx.lin(fx.T, fx.T3, 13, 0, 10); fx.sprite(POS, amber, fx.T, cell=4, clut=1)
    fx.sprite(POS, tint, fx.T3, cell=0)
    # the hands: racing, then both at twelve
    fx.set(fx.F1, 0); fx.set(fx.F2, 0); fx.br(FRAME, '>=', wind, 'clock_hands')
    fx.lin(fx.F1, FRAME, -67, 67 * wind); fx.lin(fx.F2, FRAME, -22, 22 * wind + 360)
    fx.label('clock_hands')
    fx.sprite(POS, brass, fx.T3, cell=2, clut=1, rot=fx.F2)
    fx.sprite(POS, tint, fx.T3, cell=1, rot=fx.F1); fx.ret()
    return fx


# ----------------------------------------------------------------- Dokugumon
def poison_cobweb():
    """Dokugumon spits a knot of silk that unfolds into a wide web as it flies and wraps round the target; venom runs
    along the threads, drips from them and boils off in green fumes."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(SILK); fx.palette(VENOM); fx.palette(ACID)
    fx.paint(0, web()); fx.paint(1, tangle(7)); fx.paint(2, teardrop()); fx.paint(3, cloud(111))
    fx.paint(4, bubble()); fx.paint(5, thread_line()); fx.paint(6, glow(15, 1.2))
    tint, venom = fx.colour(128, 128, 128), fx.colour(128, 70, 128)
    jaws, held = fx.vec(), fx.vec()
    fly, cling = 9, 14
    fx.particle('strand', 10, 5, 5, (100, 100, 110), (150, 220), grow=-14, spread=60, spin=40)
    fx.particle('drop', 16, 10, 2, (128, 128, 128), (70, 120), speed=10, gravity=8, spread=360, clut=1, fade=True)
    fx.particle('fume', 12, 14, 3, (60, 110, 30), (180, 260), grow=14, flat=((-10, 10), (-36, -16), (-10, 10)),
                spread=260, clut=2, fade=True)
    fx.particle('boil', 12, 10, 4, (100, 128, 60), (50, 110), grow=5, flat=((-8, 8), (-40, -20), (-8, 8)),
                spread=300, clut=2)
    fx.particle('snap', 1, 7, 6, (110, 60, 128), 260, grow=70, fade=True, clut=1)
    fx.label('main'); fx.when(0, 'begin'); fx.end(1)
    fx.label('begin')
    raised(fx, jaws, 4, 40); fx.sound(3)
    fx.vcopy(fx.AT, jaws); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('net'); fx.ret()
    fx.travel('net', 1, fly, 'net_render', 'net_arrive', every='net_trail')
    fx.label('net_trail'); fx.emit('strand', POS); fx.ret()
    fx.label('net_render')
    fx.lin(fx.F1, FRAME, 35)
    fx.br(FRAME, '>', 2, 'net_open')
    fx.sprite(POS, tint, 220, cell=1, rot=fx.F1); fx.ret()
    fx.label('net_open')
    fx.lin(fx.T3, FRAME, 95, -60); fx.sprite(POS, tint, fx.T3, cell=0, rot=fx.F1); fx.ret()
    fx.label('net_arrive')
    fx.sound(16); fx.aim(); fx.hit(); fx.vcopy(fx.AT, fx.TCHEST); fx.call('wrap'); fx.emit('snap', fx.TCHEST); fx.ret()
    wrap = fx.pool('wrap', 1)
    fx.begin('wrap', wrap, 'wrap_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('wrap_tick')
    fx.life(cling)
    fx.aim(); fx.vcopy(POS, fx.TCHEST)
    fx.emit('drop', POS); fx.emit('boil', POS)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '!=', 0, 'noop'); fx.emit('fume', POS)
    fx.br(FRAME, '!=', 4, 'noop'); fx.sound(34); fx.ret()
    fx.label('wrap_render')
    # the web draws tight round the target, the venom's colour creeping into it
    fx.lin(fx.T3, FRAME, -40, 760); fx.br(fx.T3, '>', 420, 'wrap_draw'); fx.set(fx.T3, 420)
    fx.label('wrap_draw')
    fx.lin(fx.F1, FRAME, 6, 35 * fly)
    fx.lin(fx.T, FRAME, -9, 128); fx.vset(held, fx.T, fx.T, fx.T)
    fx.br(FRAME, '<', cling - 4, 'wrap_web'); fx.lin(fx.T, FRAME, -22, 22 * cling + 20); fx.vset(held, fx.T, fx.T, fx.T)
    fx.label('wrap_web')
    fx.sprite(POS, held, fx.T3, cell=0, rot=fx.F1)
    fx.lin(fx.T, FRAME, 12, 10); fx.br(fx.T, '<', 128, 'wrap_venom'); fx.set(fx.T, 128)
    fx.label('wrap_venom')
    fx.br(FRAME, '<', cling - 4, 'wrap_v2'); fx.lin(fx.T, FRAME, -26, 26 * cling + 20)
    fx.label('wrap_v2'); fx.vset(held, fx.T, fx.T, fx.T)
    fx.lin(fx.F2, fx.F1, 1, 22); fx.sprite(POS, held, fx.T3, cell=0, clut=1, rot=fx.F2); fx.ret()
    return fx


# ----------------------------------------------------------------- Hookmon
def captain_cannon():
    """Hookmon's ship cannon goes off in a tongue of flame and a roll of smoke; the iron ball flies low and fast with
    smoke curling off it, and breaks on whoever it meets in fire and splinters. A target that moves away is missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(IRON); fx.palette(BLAST); fx.palette(SMOKE)
    fx.paint(0, cannonball()); fx.paint(1, muzzle_flash()); fx.paint(2, cloud(121)); fx.paint(3, cloud(125))
    fx.paint(4, burst(123, 11)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.4)); fx.paint(7, rock())
    tint = fx.colour(128, 128, 128)
    bore = fx.vec()
    fx.particle('flash', 1, 4, 1, (128, 128, 128), 300, grow=110, fade=True, clut=1, spin=10)
    fx.particle('roll', 8, 16, 2, (100, 96, 90), (200, 300), grow=20, speed=14, lift=10, spread=160, fade=True, clut=2)
    fx.particle('reek', 18, 10, 3, (70, 66, 62), 170, grow=12, lift=6, fade=True, clut=2)
    fx.particle('crash', 1, 8, 4, (128, 128, 128), 240, grow=90, fade=True, clut=1)
    fx.particle('shock', 1, 7, 6, (128, 100, 60), 160, grow=120, fade=True, clut=1)
    fx.particle('splinter', 14, 14, 7, (128, 128, 128), (60, 120), speed=65, lift=70, gravity=11, spread=80,
                blend=None, spin=25)
    fx.particle('cinder', 12, 11, 5, (128, 110, 60), (70, 130), grow=-6, speed=60, lift=30, gravity=6, spread=60, clut=1)
    fx.label('main'); fx.when(0, 'begin'); fx.end(1)
    fx.label('begin')
    raised(fx, bore, 6, 80); fx.sound(15); fx.emit('flash', bore); fx.emit('roll', times=6)
    fx.vcopy(fx.AT, bore); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('ball'); fx.ret()
    fx.shot('ball', 1, 96, 20, 'ball_render', 'ball_arrive', miss='ball_miss', every='ball_trail')
    fx.label('ball_trail'); fx.emit('reek', POS); fx.ret()
    fx.label('ball_miss'); fx.emit('roll', POS, 2); fx.ret()
    fx.label('ball_render'); fx.sprite(POS, tint, 340, cell=0, blend=None); fx.ret()
    fx.label('ball_arrive')
    fx.sound(7); fx.emit('crash', POS); fx.emit('shock'); fx.emit('splinter', times=12); fx.emit('cinder', times=10)
    fx.emit('roll', times=2); fx.ret()
    return fx


# ----------------------------------------------------------------- Divermon
def striking_fish():
    """Divermon hurls his harpoon fish: it darts in a straight line in a sleeve of spray and bubbles and drives into
    whoever is in its way, throwing up a spout of water. A target that moves away is missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(SCALE); fx.palette(SEA)
    fx.paint(0, fish()); fx.paint(1, spray(141)); fx.paint(2, bubble()); fx.paint(3, fan()); fx.paint(4, ring(13, 2.0))
    fx.paint(5, glow(15, 1.2)); fx.paint(6, teardrop()); fx.paint(7, spray(147))
    tint, wet = fx.colour(128, 128, 128), fx.colour(70, 110, 128)
    arm, back = fx.vec(), fx.vec()
    fx.particle('swirl', 2, 6, 4, (80, 120, 128), 100, grow=60, fade=True, clut=1)
    fx.particle('fizz', 20, 10, 2, (110, 128, 128), (50, 110), grow=4, speed=12, lift=10, spread=110, clut=1, fade=True)
    fx.particle('geyser', 1, 10, 3, (120, 128, 128), 380, grow=55, fade=True, sy=26, clut=1)
    fx.particle('wave', 2, 9, 4, (80, 120, 128), 180, grow=100, fade=True, sy=6, clut=1)
    fx.particle('drops', 20, 14, 6, (110, 128, 128), (80, 150), grow=-4, speed=55, lift=75, gravity=11, spread=100,
                clut=1)
    fx.particle('stab', 1, 6, 5, (128, 128, 128), 200, grow=70, fade=True, clut=1)
    fx.label('main'); fx.when(0, 'begin'); fx.when(4, 'throw'); fx.end(5)
    fx.label('begin'); raised(fx, arm, 8, 60); fx.emit('swirl', arm); fx.sound(-55); fx.ret()
    fx.label('throw')
    fx.sound(13); fx.aim(); fx.emit('swirl', arm)
    fx.vcopy(fx.AT, arm); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('dart'); fx.ret()
    fx.shot('dart', 1, 100, 20, 'dart_render', 'dart_arrive', miss='dart_miss', every='dart_trail')
    fx.label('dart_trail'); behind(fx, fx.TV2, 2); fx.emit('fizz', fx.TV2, 2); fx.ret()
    fx.label('dart_miss'); fx.emit('fizz', POS, 6); fx.ret()
    fx.label('dart_render')
    behind(fx, back, 7, 2); band(fx, back, POS, 210, wet, 1, clut=1)
    behind(fx, back, 5, 1); band(fx, back, POS, 110, wet, 7, clut=1)
    behind(fx, back, 4, 1); band(fx, back, POS, 150, tint, 0, blend=None); fx.ret()
    fx.label('dart_arrive')
    fx.sound(7); fx.emit('stab', POS); fx.emit('drops', times=16)
    fx.aim(); fx.vcopy(fx.AT, fx.TGT); fx.sub_(at(fx.AT, 1), 230); fx.call('geyser'); fx.emit('wave', fx.TGT); fx.ret()
    return fx


# ----------------------------------------------------------------- Arukenimon
def spirit_needle():
    """Threads of light draw together between Arukenimon's fingers into one long needle; it is gone in a blink, a
    straight line of pink left hanging in the air behind it, and whoever it runs through is lit by a cross of light.
    A target that moves away is missed."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(SPIRIT)
    fx.paint(0, needle()); fx.paint(1, thread_line()); fx.paint(2, cross_flare()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 1.5, 12, 10)); fx.paint(5, ring(13, 1.4)); fx.paint(6, streak_in())
    tint, rose = fx.colour(128, 128, 128), fx.colour(128, 50, 100)
    palm, tail_, trace = fx.vec(), fx.vec(), fx.vec()
    spin_ = 8
    fx.particle('fibre', 16, 5, 6, (128, 90, 120), (160, 260), grow=-20, spread=420, spin=50)
    fx.particle('mote', 16, 8, 4, (128, 100, 128), (50, 100), grow=-6, spread=70)
    fx.particle('pierce', 1, 8, 2, (128, 128, 128), 300, grow=120, fade=True)
    fx.particle('pierce2', 1, 10, 2, (128, 70, 110), 200, grow=90, fade=True, rot=45)
    fx.particle('hoop', 2, 7, 5, (128, 80, 120), 100, grow=100, fade=True)
    fx.particle('fleck', 14, 10, 4, (128, 110, 128), (70, 130), grow=-7, speed=70, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(spin_, 'loose')
    fx.br(fx.NOW, '>', spin_ - 2, 'main_end'); fx.emit('fibre', palm, 2)
    fx.label('main_end'); fx.end(spin_ + 1)
    fx.label('begin'); raised(fx, palm, 8, 70); fx.vcopy(fx.AT, palm); fx.call('spindle'); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, palm); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('pin')
    fx.vcopy(fx.AT, palm); fx.call('line'); fx.ret()
    spindle = fx.pool('spindle', 1)
    fx.begin('spindle', spindle, 'spindle_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('spindle_tick'); fx.life(spin_ - 1); fx.ret()
    fx.label('spindle_render')
    fx.lin(fx.T3, FRAME, 55, 80); fx.lin(fx.T2, FRAME, 6, 14)
    fx.sprite(POS, rose, 300, cell=3); fx.sprite(POS, tint, fx.T3, fx.T2, cell=0); fx.ret()
    fx.shot('pin', 1, 130, 14, 'pin_render', 'pin_arrive', every='pin_trail')
    fx.label('pin_trail'); fx.vcopy(trace, POS); fx.emit('mote', POS); fx.ret()
    fx.label('pin_render')
    behind(fx, tail_, 4); band(fx, tail_, POS, 70, tint, 0)
    fx.sprite(POS, rose, 260, cell=3); fx.ret()
    fx.label('pin_arrive')
    fx.sound(16); fx.vcopy(trace, POS)
    fx.emit('pierce', POS); fx.emit('pierce2'); fx.emit('hoop'); fx.emit('fleck', times=12); fx.ret()
    line = fx.pool('line', 1)               # the line the needle leaves in the air
    fx.begin('line', line, 'line_render', inherit=False); fx.vcopy(POS, fx.AT); fx.vcopy(trace, fx.AT); fx.ret()
    fx.label('line_tick'); fx.life(16); fx.ret()
    fx.label('line_render')
    fx.lin(fx.T3, FRAME, -3, 52)
    fx.lin(fx.T, FRAME, -7, 120); fx.vset(fx.TV2, fx.T, fx.T, fx.T)
    band(fx, POS, trace, fx.T3, fx.TV2, 1); fx.ret()
    return fx


# ----------------------------------------------------------------- Maildramon
def mail_bomber():
    """Three finned bombs leave Maildramon's back on columns of smoke, climb out of sight and come whistling straight
    down on the target one after another, each going up in a burst of fire and iron."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(STEEL); fx.palette(BLAST); fx.palette(SMOKE)
    fx.paint(0, arrow_bomb()); fx.paint(1, flame_tail()); fx.paint(2, burst(127, 10)); fx.paint(3, cloud(129))
    fx.paint(4, ring(13, 2.2)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, glow(15, 1.2)); fx.paint(7, rock())
    tint, hot = fx.colour(128, 128, 128), fx.colour(128, 100, 60)
    back, sky = fx.vec(), fx.vec()
    landed = fx.const(0)
    up, first, gap, fall = 6, 9, 4, 5
    fx.particle('rise', 3, up, 0, (128, 128, 128), 230, flat=((-12, 12), (-200, -170), (-12, 12)), spread=160,
                blend=None, rot=180)
    fx.particle('plumeup', 16, 10, 3, (90, 86, 80), (150, 220), grow=14, speed=10, spread=200, fade=True, clut=2)
    fx.particle('puff', 14, 8, 3, (70, 66, 62), 150, grow=10, fade=True, clut=2)
    fx.particle('boom', 3, 8, 2, (128, 128, 128), 200, grow=80, fade=True, clut=1, spin=5)
    fx.particle('shock', 3, 7, 4, (128, 100, 60), 140, grow=100, fade=True, clut=1, sy=7)
    fx.particle('scrap', 18, 13, 7, (128, 128, 128), (50, 100), speed=60, lift=75, gravity=11, spread=80, blend=None,
                spin=25)
    fx.particle('spark', 12, 10, 5, (128, 110, 60), (70, 130), grow=-7, speed=65, lift=30, gravity=6, spread=60, clut=1)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(3):
        fx.when(first + gap * k, 'drop')
    fx.br(fx.NOW, '>', up, 'main_end'); fx.emit('plumeup', back, 2)
    fx.label('main_end'); fx.end(first + 2 * gap + 1)
    fx.label('begin'); raised(fx, back, 10); fx.sound(13); fx.emit('rise', back, 3); fx.ret()
    fx.label('drop')
    fx.sound(3); fx.aim(); fx.vcopy(fx.DEST, fx.TGT); fx.scatter(fx.DEST, 200); fx.set(at(fx.DEST, 1), at(fx.TGT, 1))
    fx.vcopy(sky, fx.DEST); fx.sub_(at(sky, 1), 1500); fx.vcopy(fx.AT, sky); fx.call('bomb'); fx.ret()
    fx.travel('bomb', 3, fall, 'bomb_render', 'bomb_arrive', every='bomb_trail')
    fx.label('bomb_trail'); fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), 200); fx.emit('puff', fx.TV2); fx.ret()
    fx.label('bomb_render')
    fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), 300); fx.sprite(fx.TV2, hot, 200, 330, cell=1, clut=1)
    fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), 110); fx.sprite(fx.TV2, tint, 260, cell=0, blend=None); fx.ret()
    fx.label('bomb_arrive')
    fx.sound(15); fx.vcopy(fx.KEEP, POS); fx.vcopy(fx.AT, POS); fx.sub_(at(fx.AT, 1), 120)
    fx.call('boom'); fx.call('scrap', 6); fx.call('spark', 4); fx.emit('shock', fx.KEEP)
    fx.br(landed, '!=', 0, 'noop'); fx.set(landed, 1); fx.aim(); fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- Mummymon
def necrophobia():
    """Mummymon's gun cracks: a white flash at the muzzle, a streak across the field in the same instant, and from the
    wound a pale skull rises through the target with wisps of grave-mist."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(GHOST); fx.palette(NULL)
    fx.paint(0, skull()); fx.paint(1, tracer()); fx.paint(2, muzzle_flash(4)); fx.paint(3, wisp(1)); fx.paint(4, wisp(4))
    fx.paint(5, glow(15, 1.2)); fx.paint(6, star(4, 2, 9, 6)); fx.paint(7, ring(13, 1.6))
    tint, pale = fx.colour(128, 128, 128), fx.colour(60, 128, 100)
    muzzle, mark, shade = fx.vec(), fx.vec(), fx.vec()
    aimt = 5
    gather(fx, 'dread', 12, 6, (90, 128, 110), 70, 380, 4)
    fx.particle('crack', 1, 4, 2, (128, 128, 128), 260, grow=90, fade=True, clut=1)
    fx.particle('casing', 6, 10, 6, (128, 128, 128), (60, 110), grow=-6, speed=40, lift=40, gravity=8, clut=1)
    fx.particle('bite', 1, 6, 5, (128, 128, 128), 220, grow=60, fade=True, clut=1)
    fx.particle('halo', 2, 8, 7, (80, 128, 110), 140, grow=90, fade=True)
    fx.particle('mist', 14, 16, 3, (70, 128, 100), (220, 320), flat=((-10, 10), (-44, -22), (-10, 10)), spread=240,
                fade=True)
    fx.particle('mist2', 10, 16, 4, (60, 110, 100), (220, 320), flat=((-10, 10), (-44, -22), (-10, 10)), spread=240,
                fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(aimt, 'shoot')
    fx.br(fx.NOW, '>', aimt - 2, 'main_end'); fx.emit('dread', muzzle, 2)
    fx.label('main_end'); fx.end(aimt + 1)
    fx.label('begin'); raised(fx, muzzle, 7, 90); fx.sound(-55); fx.ret()
    fx.label('shoot')
    fx.sound(15); fx.aim(); fx.vcopy(mark, fx.TCHEST); fx.hit()
    fx.emit('crack', muzzle); fx.emit('casing', times=5)
    fx.emit('bite', mark); fx.emit('halo')
    fx.vcopy(fx.AT, muzzle); fx.call('streak'); fx.vcopy(fx.AT, mark); fx.call('fear'); fx.ret()
    streak = fx.pool('streak', 1)
    fx.begin('streak', streak, 'streak_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('streak_tick'); fx.life(5); fx.ret()
    fx.label('streak_render')
    fx.lin(fx.T3, FRAME, -14, 80); fx.lin(fx.T, FRAME, -24, 128); fx.vset(shade, fx.T, fx.T, fx.T)
    band(fx, POS, mark, fx.T3, shade, 1, clut=1); fx.ret()
    fear = fx.pool('fear', 1)
    fx.begin('fear', fear, 'fear_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('fear_tick')
    fx.life(20); fx.sub_(at(POS, 1), 22)
    fx.after(2, 'fear_moan')
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '!=', 0, 'noop')
    fx.vcopy(fx.AT, mark); fx.call('mist'); fx.call('mist2'); fx.ret()
    fx.label('fear_moan'); fx.sound(1); fx.ret()
    fx.label('fear_render')
    fx.lin(fx.T3, FRAME, 22, 200)
    fx.lin(fx.T, FRAME, 30, 10); fx.br(fx.T, '<', 128, 'fear_in'); fx.set(fx.T, 128)
    fx.label('fear_in')
    fx.br(FRAME, '<', 13, 'fear_draw'); fx.lin(fx.T, FRAME, -16, 16 * 21)
    fx.label('fear_draw')
    fx.lin(fx.T2, fx.T, 1, 0, 2); fx.vset(shade, fx.T2, fx.T, fx.T2)
    fx.lin(fx.F1, fx.T3, 14, 0, 10); fx.sprite(POS, shade, fx.F1, cell=5)
    fx.vset(shade, fx.T, fx.T, fx.T); fx.sprite(POS, shade, fx.T3, cell=0); fx.ret()
    return fx


# ----------------------------------------------------------------- MegaGargomon
def giant_missile():
    """The two great missiles on MegaGargomon's shoulders light up and leave together on roaring flames, trailing
    smoke; they come down on the target one after the other and the second explosion swallows the first."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(ARMY); fx.palette(BLAST); fx.palette(SMOKE)
    fx.paint(0, missile()); fx.paint(1, jet()); fx.paint(2, burst(133, 11)); fx.paint(3, cloud(135))
    fx.paint(4, ring(13, 2.4)); fx.paint(5, glow(15, 1.2)); fx.paint(6, star(4, 2, 9, 6)); fx.paint(7, cloud(139))
    tint, hot, wash = fx.colour(128, 128, 128), fx.colour(128, 110, 70), fx.vec()
    side, left, right, back = fx.vec(), fx.vec(), fx.vec(), fx.vec()
    landed = fx.const(0)
    boomt = fx.const(-100)
    light, fly = 6, 11
    fx.particle('ignite', 2, light, 5, (128, 100, 50), 80, grow=50, clut=1)
    fx.particle('exhaust', 26, 12, 3, (90, 86, 80), 180, grow=16, lift=4, spread=40, fade=True, clut=2)
    fx.particle('boom', 2, 10, 2, (128, 128, 128), 280, grow=110, fade=True, clut=1, spin=4)
    fx.particle('shock', 2, 8, 4, (128, 100, 60), 200, grow=150, fade=True, clut=1, sy=7)
    fx.particle('pall', 10, 18, 7, (80, 74, 68), (260, 380), grow=18, speed=18, lift=20, spread=280, fade=True, clut=2)
    fx.particle('shrapnel', 18, 12, 6, (128, 110, 60), (90, 160), grow=-7, speed=85, lift=50, gravity=8, spread=80,
                clut=1)
    fx.label('main'); fx.when(0, 'begin'); fx.when(light, 'launch1'); fx.when(light + 3, 'launch2')
    fx.end(light + 4)
    fx.label('draw')
    fx.lin(fx.T, fx.NOW, 1, 0); fx.sub_(fx.T, boomt); fx.br(fx.T, '>', 5, 'noop'); fx.br(fx.T, '<', 0, 'noop')
    fx.lin(fx.T, fx.T, -14, 76); fx.lin(fx.T2, fx.T, 2, 0, 3); fx.lin(fx.T3, fx.T, 1, 0, 3)
    fx.vset(wash, fx.T, fx.T2, fx.T3); fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    sideways(fx, side, 170)
    raised(fx, left, 10); fx.vcopy(right, left); fx.vadd(left, side); fx.vsub(right, side)
    fx.emit('ignite', left); fx.emit('ignite', right); fx.sound(-55); fx.ret()
    fx.label('launch1'); fx.vcopy(fx.AT, left); fx.jmp('launch')
    fx.label('launch2'); fx.vcopy(fx.AT, right)
    fx.label('launch'); fx.sound(13); fx.aim(); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('rocket'); fx.ret()
    fx.travel('rocket', 2, fly, 'rocket_render', 'rocket_arrive', every='rocket_trail')
    fx.label('rocket_trail'); behind(fx, fx.TV2, 3); fx.emit('exhaust', fx.TV2, 2); fx.ret()
    fx.label('rocket_render')
    behind(fx, back, 7); behind(fx, fx.TV2, 3)
    fx.vcopy(fx.KEEP, fx.TV2); band(fx, back, fx.KEEP, 110, hot, 1, clut=1)
    fx.sprite(fx.KEEP, hot, 300, cell=5, clut=1)
    behind(fx, back, 4); band(fx, back, POS, 130, tint, 0, blend=None); fx.ret()
    fx.label('rocket_arrive')
    fx.sound(15); fx.set(boomt, fx.NOW); fx.aim()
    fx.emit('boom', fx.TCHEST); fx.emit('pall', times=5); fx.emit('shrapnel', times=9); fx.emit('shock', fx.TGT)
    fx.br(landed, '!=', 0, 'noop'); fx.set(landed, 1); fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- WarGreymon
def terra_force():
    """Streams of the earth's fire rise from the ground all round WarGreymon and pour into a small sun over his head,
    rays turning round it; he hurls it down, and where it lands a wall of flame stands up through the target and throws
    burning rock."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(SUN); fx.palette(EARTH)
    fx.paint(0, sun(51)); fx.paint(1, sun(57)); fx.paint(2, corona()); fx.paint(3, firewall(161))
    fx.paint(4, firewall(167)); fx.paint(5, streak_in()); fx.paint(6, glow(15, 1.2)); fx.paint(7, rock())
    tint, warm, wash = fx.colour(128, 128, 128), fx.colour(128, 80, 24), fx.vec()
    top, spot = fx.vec(), fx.vec()
    landt = fx.const(-100)
    swell, fly = 15, 6
    stream = fx.pool('stream', 20, 3)       # fire drawn up out of the ground into the sun
    svel, scol = iv(FREE), fx.colour(128, 96, 40)
    fx.begin('stream', stream, 'stream_render', inherit=False)
    fx.vcopy(POS, fx.SRC); fx.scatter(POS, 1300); fx.set(at(POS, 1), at(fx.SRC, 1))
    fx.vcopy(svel, top); fx.vsub(svel, POS); fx.vdiv(svel, 8); fx.ret()
    fx.label('stream_tick'); fx.life(7); fx.vadd(POS, svel); fx.ret()
    fx.label('stream_render'); fx.sprite(POS, scol, 90, 260, cell=5); fx.ret()
    fx.particle('trail', 10, 6, 6, (128, 70, 20), 460, grow=-55, fade=True)
    fx.particle('ember', 16, 12, 6, (128, 100, 40), (40, 80), speed=30, lift=20, gravity=3, spread=300, fade=True)
    fx.particle('flashball', 1, 8, 6, (128, 110, 70), 300, grow=140, fade=True)
    fx.particle('boulder', 16, 15, 7, (128, 128, 128), (70, 140), speed=65, lift=85, gravity=11, spread=200, clut=1,
                blend=None, spin=20)
    fx.particle('scorch', 12, 12, 6, (128, 80, 30), (120, 200), grow=-10, flat=((-30, 30), (-80, -40), (-30, 30)),
                spread=260)
    fx.label('main'); fx.when(0, 'begin')
    fx.br(fx.NOW, '>', swell - 4, 'main_end'); fx.call('stream', 2)
    fx.label('main_end'); fx.end(swell + fly + 16)
    fx.label('draw')
    fx.lin(fx.T, fx.NOW, 1, 0); fx.sub_(fx.T, landt); fx.br(fx.T, '<', 0, 'draw_glow'); fx.br(fx.T, '>', 6, 'noop')
    fx.lin(fx.T, fx.T, -13, 84); fx.lin(fx.T2, fx.T, 1, 0, 2); fx.lin(fx.T3, fx.T, 1, 0, 6)
    fx.vset(wash, fx.T, fx.T2, fx.T3); fx.overlay(wash, blend='add'); fx.ret()
    fx.label('draw_glow')                   # the sun lights the field while it grows
    fx.br(fx.NOW, '>', swell + fly, 'noop')
    fx.lin(fx.T, fx.NOW, 2, 0); fx.br(fx.T, '<', 26, 'draw_warm'); fx.set(fx.T, 26)
    fx.label('draw_warm'); fx.lin(fx.T2, fx.T, 1, 0, 2); fx.vset(wash, fx.T, fx.T2, 0); fx.overlay(wash, blend='add')
    fx.ret()
    fx.label('begin')
    fx.vcopy(top, fx.SRC); fx.lin(fx.T, at(fx.SSIZE, 1), 1, 330); fx.sub_(at(top, 1), fx.T)
    fx.vcopy(fx.AT, top); fx.call('orb'); fx.sound(-55); fx.ret()
    orb = fx.pool('orb', 1, 3)
    step = iv(FREE)
    fx.begin('orb', orb, 'orb_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('orb_tick')
    fx.br(FRAME, '<', swell, 'noop')
    fx.br(FRAME, '==', swell, 'orb_throw')
    fx.br(FRAME, '>=', swell + fly, 'orb_land')
    fx.vadd(POS, step); fx.emit('trail', POS); fx.emit('ember', POS, 2); fx.ret()
    fx.label('orb_throw')
    fx.sound(3); fx.aim(); fx.vcopy(spot, fx.TGT)
    fx.vcopy(step, spot); fx.sub_(at(step, 1), 150); fx.vsub(step, POS); fx.vdiv(step, fly); fx.ret()
    fx.label('orb_land')
    fx.sound(15); fx.set(landt, fx.NOW); fx.aim(); fx.vcopy(spot, fx.TGT); fx.hit()
    fx.vcopy(fx.AT, spot); fx.sub_(at(fx.AT, 1), 150)
    fx.call('flashball'); fx.call('boulder', 14); fx.call('scorch', 10)
    fx.vcopy(fx.AT, spot); fx.call('pyre'); fx.set(FRAME, -1); fx.ret()
    fx.label('orb_render')
    fx.lin(fx.T3, FRAME, 34, 60); fx.br(FRAME, '<', swell, 'orb_draw'); fx.set(fx.T3, 570)
    fx.label('orb_draw')
    fx.lin(fx.F1, FRAME, 7); fx.lin(fx.T, fx.T3, 21, 0, 10)
    fx.sprite(POS, warm, fx.T, cell=2, rot=fx.F1)
    fx.lin(fx.F1, FRAME, -5, 15); fx.lin(fx.T, fx.T3, 16, 0, 10); fx.sprite(POS, warm, fx.T, cell=2, rot=fx.F1)
    flicker(fx, POS, tint, fx.T3, (0, 1), every=2); fx.ret()
    pyre = fx.pool('pyre', 1)               # the wall of flame where it lands
    fx.begin('pyre', pyre, 'pyre_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('pyre_tick'); fx.life(13); fx.ret()
    fx.label('pyre_render')
    fx.lin(fx.T3, FRAME, 150, 300); fx.br(fx.T3, '<', 1100, 'pyre_h'); fx.set(fx.T3, 1100)
    fx.label('pyre_h')
    fx.lin(fx.T, FRAME, 30, 520)
    fx.lin(fx.T2, FRAME, -10, 128); fx.br(FRAME, '<', 6, 'pyre_c'); fx.lin(fx.T2, FRAME, -9, 122)
    fx.label('pyre_c'); fx.lin(fx.F1, fx.T2, 2, 0, 3); fx.vset(wash, fx.T2, fx.T2, fx.F1)
    fx.set(fx.F2, FRAME); fx.mod(fx.F2, 4); fx.br(fx.F2, '>=', 2, 'pyre_b')
    fx.pillar(POS, fx.T, fx.T3, wash, cell=3); fx.ret()
    fx.label('pyre_b'); fx.pillar(POS, fx.T, fx.T3, wash, cell=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Apocalymon
def darkness_zone():
    """Slivers of the dark fall inwards from all sides onto the target while the light goes out of the field; a
    black sphere with a torn violet rim closes round it, five-sided walls turning on its skin, then collapses to a
    point and breaks apart."""
    fx = Fx(delay=8, cast_sound=1, draw=True)
    fx.palette(ABYSS); fx.palette(NULL)
    fx.paint(0, void_rim(5)); fx.paint(1, void_rim(9)); fx.paint(2, hole()); fx.paint(3, pentagon())
    fx.paint(4, pentagon(math.pi / 5, 1.2)); fx.paint(5, streak_in()); fx.paint(6, glow(15, 1.2))
    fx.paint(7, star(4, 1.5, 11, 9))
    tint, dark, violet, wash = fx.colour(128, 128, 128), fx.colour(128, 128, 128), fx.colour(110, 50, 128), fx.vec()
    close, hold = 12, 9
    crush = close + hold
    gather(fx, 'sliver', 24, 5, (110, 60, 128), 150, 1500, 7)
    fx.particle('facet', 12, 14, 3, (128, 80, 128), (130, 220), grow=-8, speed=70, lift=30, gravity=4, spread=60,
                spin=22)
    fx.particle('facet2', 8, 14, 4, (90, 90, 128), (130, 220), grow=-8, speed=70, lift=30, gravity=4, spread=60,
                spin=-17)
    fx.particle('point', 1, 7, 7, (128, 128, 128), 200, grow=110, fade=True, clut=1)
    fx.particle('echo', 2, 9, 0, (128, 70, 128), 200, grow=120, fade=True, spin=8)
    fx.label('main'); fx.when(0, 'begin')
    fx.br(fx.NOW, '>', close, 'main_end'); fx.aim(); fx.emit('sliver', fx.TCHEST, 2)
    fx.label('main_end'); fx.end(crush + 12)
    fx.label('draw')
    fx.br(fx.NOW, '>', crush + 1, 'noop')
    fx.lin(fx.T, fx.NOW, 7, 0); fx.br(fx.T, '<', 72, 'draw_dim'); fx.set(fx.T, 72)
    fx.label('draw_dim'); fx.lin(fx.T2, fx.T, 2, 0, 3); fx.vset(wash, fx.T, fx.T, fx.T2)
    fx.overlay(wash, blend='sub'); fx.ret()
    fx.label('begin'); fx.vcopy(fx.AT, fx.TCHEST); fx.call('zone'); fx.sound(-55); fx.ret()
    zone = fx.pool('zone', 1)
    fx.begin('zone', zone, 'zone_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('zone_tick')
    fx.br(FRAME, '>=', crush + 3, 'zone_break')
    fx.aim(); fx.vcopy(POS, fx.TCHEST)
    fx.after(close, 'zone_shut'); fx.ret()
    fx.label('zone_shut'); fx.sound(34); fx.ret()
    fx.label('zone_break')
    fx.sound(15); fx.aim(); fx.hit()
    fx.emit('point', fx.TCHEST); fx.emit('echo'); fx.emit('facet', times=12); fx.emit('facet2', times=8)
    fx.set(FRAME, -1); fx.ret()
    fx.label('zone_render')
    # the sphere: growing, held, then crushed to nothing
    fx.lin(fx.T3, FRAME, 62, 40); fx.br(FRAME, '<', close, 'zone_draw')
    fx.set(fx.T3, 62 * close + 40); fx.br(FRAME, '<', crush, 'zone_draw')
    fx.lin(fx.T3, FRAME, -260, 260 * (crush + 3))
    fx.label('zone_draw')
    fx.sprite(POS, dark, fx.T3, cell=2, blend='sub')
    fx.lin(fx.T, fx.T3, 9, 0, 10); fx.sprite(POS, dark, fx.T, cell=2, blend='sub')
    fx.lin(fx.T, fx.T3, 12, 0, 10); fx.lin(fx.F1, FRAME, 9)
    flicker(fx, POS, violet, fx.T, (0, 1), every=2)
    fx.br(FRAME, '<', 5, 'noop')
    fx.lin(fx.T, fx.T3, 7, 0, 10); fx.sprite(POS, violet, fx.T, cell=3, rot=fx.F1)
    fx.lin(fx.F2, FRAME, -13); fx.lin(fx.T, fx.T3, 4, 0, 10); fx.sprite(POS, tint, fx.T, cell=4, rot=fx.F2); fx.ret()
    return fx


# ----------------------------------------------------------------- Kurisarimon
def data_crusher():
    """Kurisarimon compiles a block of raw data before it, ones and zeroes streaming into it, and fires it; the block
    stutters across the field in jumps and breaks over the target in a storm of squares and scan lines."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(DATA); fx.palette(GLITCH)
    fx.paint(0, block()); fx.paint(1, bit(True)); fx.paint(2, bit(False)); fx.paint(3, mosaic(3)); fx.paint(4, mosaic(8))
    fx.paint(5, scanline()); fx.paint(6, glow(15, 1.2)); fx.paint(7, mosaic(13, 8))
    tint, green, pink = fx.colour(128, 128, 128), fx.colour(40, 128, 60), fx.colour(128, 50, 110)
    core = fx.vec()
    build, fly = 8, 8
    gather(fx, 'one', 10, 1, (90, 128, 100), 110, 520, 5)
    gather(fx, 'zero', 10, 2, (90, 128, 100), 110, 520, 5)
    fx.particle('lag', 12, 4, 0, (40, 128, 60), 260, grow=-30, fade=True)
    fx.particle('digit', 12, 10, 1, (100, 128, 110), (90, 150), flat=((-30, 30), (-50, -10), (-30, 30)), spread=200,
                fade=True)
    fx.particle('digit0', 12, 10, 2, (100, 128, 110), (90, 150), flat=((-30, 30), (-50, -10), (-30, 30)), spread=200,
                fade=True)
    fx.particle('tile', 18, 9, 0, (90, 128, 100), (60, 130), speed=80, spread=160, grow=-4)
    fx.particle('scan', 8, 6, 5, (128, 60, 110), (500, 700), sy=3, spread=420, clut=1,
                flat=((0, 0), (-20, 20), (0, 0)))
    fx.particle('crash', 1, 7, 6, (90, 128, 100), 300, grow=80, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(build, 'send')
    fx.br(fx.NOW, '>', build - 3, 'main_end'); fx.emit('one', core); fx.emit('zero', core)
    fx.label('main_end'); fx.end(build + 1)
    fx.label('begin'); raised(fx, core, 6, 150); fx.vcopy(fx.AT, core); fx.call('compile'); fx.sound(-55); fx.ret()
    fx.label('send')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, core); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('packet'); fx.ret()
    comp = fx.pool('compile', 1)
    fx.begin('compile', comp, 'compile_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('compile_tick'); fx.life(build - 1); fx.ret()
    fx.label('compile_render')
    fx.lin(fx.T3, FRAME, 40, 60); fx.sprite(POS, green, fx.T3, cell=6)
    fx.lin(fx.T3, FRAME, 34, 50); flicker(fx, POS, tint, fx.T3, (3, 4), every=1); fx.ret()
    fx.travel('packet', 1, fly, 'packet_render', 'packet_arrive', every='packet_trail')
    fx.label('packet_trail'); fx.emit('lag', POS); fx.emit('digit', POS); fx.ret()
    fx.label('packet_render')
    fx.rnd(fx.T3, -90, 90); fx.vcopy(fx.TV2, POS); fx.add(at(fx.TV2, 0), fx.T3)
    fx.rnd(fx.T3, -90, 90); fx.add(at(fx.TV2, 1), fx.T3)
    fx.sprite(fx.TV2, pink, 420, cell=7, clut=1)
    fx.sprite(POS, green, 520, cell=6); fx.sprite(POS, tint, 320, cell=0)
    flicker(fx, POS, tint, 260, (3, 4), every=1); fx.ret()
    fx.label('packet_arrive')
    fx.sound(16); fx.aim(); fx.hit(); fx.vcopy(fx.AT, fx.TCHEST); fx.call('corrupt')
    fx.call('crash'); fx.call('tile', 14); fx.call('digit', 4); fx.call('digit0', 4); fx.ret()
    corrupt = fx.pool('corrupt', 1)
    fx.begin('corrupt', corrupt, 'corrupt_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('corrupt_tick')
    fx.life(13); fx.aim(); fx.vcopy(POS, fx.TCHEST)
    fx.emit('scan', POS)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 3); fx.br(fx.T2, '!=', 0, 'noop')
    fx.sound(20); fx.emit('digit', POS); fx.emit('digit0', POS); fx.emit('tile', POS, 2); fx.ret()
    fx.label('corrupt_render')
    fx.br(FRAME, '>', 10, 'noop')
    fx.lin(fx.T, at(fx.TSIZE, 1), 1, 240)
    fx.rnd(fx.T3, -80, 80); fx.vcopy(fx.TV2, POS); fx.add(at(fx.TV2, 0), fx.T3)
    flicker(fx, fx.TV2, green, fx.T, (3, 7), every=1)
    fx.rnd(fx.T3, -80, 80); fx.vcopy(fx.TV2, POS); fx.add(at(fx.TV2, 2), fx.T3)
    flicker(fx, fx.TV2, pink, fx.T, (4, 3), clut=1, every=1); fx.ret()
    return fx


# ----------------------------------------------------------------- Garudamon
def wing_blade():
    """Flames spiral up off Garudamon's wings and knit into a great bird of fire over her head; it beats its wings
    once and dives in a straight line, shedding burning feathers, and whoever it strikes is wrapped in its wings as
    it bursts. A target that moves away is missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(PHOENIX)
    fx.paint(0, firebird(True)); fx.paint(1, firebird(False)); fx.paint(2, plume()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, burst(171, 5)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.2))
    tint, warm = fx.colour(128, 128, 128), fx.colour(128, 70, 24)
    top = fx.vec()
    form = 10
    gather(fx, 'lick', 20, 2, (128, 100, 50), 170, 900, 6)
    fx.particle('shed', 22, 12, 2, (128, 90, 40), (150, 230), grow=-9, speed=18, gravity=3, spread=200, spin=22,
                fade=True)
    fx.particle('spark', 14, 9, 5, (128, 110, 60), (50, 100), grow=-6, speed=20, spread=160)
    fx.particle('wings', 1, 9, 0, (128, 128, 128), 420, grow=110, fade=True)
    fx.particle('fire', 2, 9, 4, (128, 110, 80), 220, grow=80, fade=True, spin=6)
    fx.particle('hoop', 1, 8, 6, (128, 80, 30), 160, grow=110, fade=True)
    fx.particle('quill', 18, 14, 2, (128, 110, 60), (140, 220), grow=-6, speed=60, lift=55, gravity=7, spread=80,
                spin=28)
    fx.label('main'); fx.when(0, 'begin'); fx.when(form, 'dive')
    fx.br(fx.NOW, '>', form - 3, 'main_end'); fx.emit('lick', top, 2)
    fx.label('main_end'); fx.end(form + 1)
    fx.label('begin')
    fx.vcopy(top, fx.SRC); fx.lin(fx.T, at(fx.SSIZE, 1), 1, 300); fx.sub_(at(top, 1), fx.T)
    fx.vcopy(fx.AT, top); fx.call('hatch'); fx.sound(-55); fx.ret()
    hatch = fx.pool('hatch', 1)
    fx.begin('hatch', hatch, 'hatch_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('hatch_tick'); fx.life(form - 1); fx.ret()
    fx.label('hatch_render')
    fx.lin(fx.T3, FRAME, 50, 100); fx.lin(fx.T, fx.T3, 14, 0, 10)
    fx.sprite(POS, warm, fx.T, cell=3)
    fx.br(FRAME, '>=', form - 4, 'hatch_spread')
    fx.sprite(POS, tint, fx.T3, cell=1); fx.ret()
    fx.label('hatch_spread'); fx.sprite(POS, tint, fx.T3, cell=0); fx.ret()
    fx.label('dive')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, top); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('bird'); fx.ret()
    fx.shot('bird', 1, 88, 24, 'bird_render', 'bird_arrive', miss='bird_miss', every='bird_trail',
            extent=(110, 190, 110))
    fx.label('bird_trail'); fx.emit('shed', POS, 2); fx.emit('spark', POS); fx.ret()
    fx.label('bird_miss'); fx.emit('quill', POS, 6); fx.ret()
    fx.label('bird_render')
    fx.sprite(POS, warm, 760, cell=3); flicker(fx, POS, tint, 600, (0, 1), every=2); fx.ret()
    fx.label('bird_arrive')
    fx.sound(15); fx.emit('wings', POS); fx.emit('fire', times=2); fx.emit('hoop'); fx.emit('quill', times=16)
    fx.ret()
    return fx


EFFECTS = {270: smiley_warhead, 273: rain_of_pollen, 278: spurting_ink, 282: pummel_peck, 283: pearl_shot,
           285: e_stun_blast, 287: waking_dream, 290: chrono_breaker, 298: poison_cobweb, 299: captain_cannon,
           304: striking_fish, 311: spirit_needle, 324: mail_bomber, 334: necrophobia, 335: giant_missile,
           373: terra_force, 400: darkness_zone, 431: data_crusher, 460: wing_blade}
