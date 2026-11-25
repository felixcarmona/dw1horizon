"""Finishers written and painted here, one per species (keyed by species id): the effect, how it travels and whom it
hits are ours, so each can behave as its Digimon's finisher should."""
import math

import numpy as np

from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, fbm, glow, grid, iv, polar, ring, \
    segment, star

FIRE = ['#000000', '#5a0800', '#d03000', '#ff9010', '#ffe880', '#ffffff']
ICE = ['#000000', '#0a2060', '#3080d0', '#a0e0ff', '#ffffff']
PLASMA = ['#000000', '#601000', '#f05000', '#ffc040', '#fff8c0', '#ffffff']
BLUEFIRE = ['#000000', '#081050', '#1848d0', '#40b0ff', '#c0f0ff', '#ffffff']
CRIMSON = ['#000000', '#400008', '#c01018', '#ff5040', '#ffc0b0', '#ffffff']
ROYAL = ['#000000', '#500010', '#d01840', '#ff80a0', '#ffffff']
AMETHYST = ['#000000', '#28084a', '#7828c0', '#c070f0', '#f0c8ff', '#ffffff']
VIOLET = ['#000000', '#200838', '#7010a0', '#d040e0', '#ffc0ff']
BLOOD = ['#000000', '#300004', '#900808', '#f03018', '#ffa060', '#ffe8c0']
GOLD = ['#000000', '#3a2000', '#a06808', '#f0b828', '#fff090', '#ffffff']
PAPER = ['#701010', '#d03020', '#e8c890', '#fffbe8']


# ----------------------------------------------------------------- paintings
def fireball(seed):
    """A ball of fire with a ragged edge."""
    r, _ = polar()
    return clip(1 - r / (11 + 4 * fbm(seed))) ** 0.7 * (0.65 + 0.6 * fbm(seed + 5))


def tongue(seed=2):
    """A flame: a point at the top, a round foot."""
    x, y = grid()
    t = np.clip((y - 2) / 28, 0, 1)
    w = 7.5 * t ** 0.8 * np.sqrt(clip(1 - (np.clip(t - 0.72, 0, 1) / 0.28) ** 2))
    cx = 16 + 2.2 * np.sin(t * 5)
    return clip(1.25 - np.abs(x - cx) / np.maximum(w, 0.3)) * (y > 2) * (0.45 + 0.75 * t) * (0.8 + 0.4 * fbm(seed))


def bar(seed=4):
    """A band across the cell: the body of a beam."""
    x, y = grid()
    return clip(1 - np.abs(y - 16) / 13.0) ** 0.9 * (0.8 + 0.3 * fbm(seed))


def column(seed=9):
    x, y = grid()
    return clip(1 - np.abs(x - 16) / 10.0) ** 0.7 * (0.75 + 0.35 * fbm(seed)) * clip((31.5 - y) / 3 + 0.4)


def puff(seed):
    r, _ = polar()
    return clip(clip(1 - r / 14) ** 0.8 * (0.35 + 1.0 * fbm(seed)))


def disc(radius=9.0):
    r, _ = polar()
    return clip((radius - r) / 1.5)


def diamond(lean=0.0):
    """A cut crystal: a rhombus with a bright rim and two facets."""
    x, y = grid()
    u = x - 16 - lean * (y - 16)
    d = np.abs(u) / 7.5 + np.abs(y - 16) / 14.5
    face = (d < 1) * (0.42 + 0.3 * (u < 0) + 0.2 * (y < 16))
    rim = clip(1 - np.abs(1 - d) * 5) * (d < 1.1)
    spine = clip(1 - np.abs(u) / 1.0) * (d < 1) * 0.5
    return clip(np.maximum(face, rim) + spine)


def shard():
    x, y = grid()
    d = np.abs(x - 16 - 0.4 * (y - 16)) / 5.0 + np.abs(y - 16) / 10.0
    return clip((1 - d) * 3) * (0.6 + 0.4 * (x < 16))


def slash(turn):
    """A blade's wake: a thin crescent with a hot edge."""
    x, y = grid()
    c, s = math.cos(turn), math.sin(turn)
    u, v = (x - 16) * c + (y - 16) * s, -(x - 16) * s + (y - 16) * c
    bow = v - 5.0 * (1 - (u / 15.0) ** 2) + 2.5
    width = 3.4 * clip(1 - (np.abs(u) / 15.5) ** 2) ** 0.7
    edge = clip(1.2 - np.abs(bow) / np.maximum(width, 0.2)) * (np.abs(u) < 15.5)
    wake = 0.35 * clip(1 - np.abs(bow - 3.0) / 4.0) * (np.abs(u) < 13) * (bow > 0)
    return clip(edge + wake) * (0.8 + 0.3 * fbm(21))


def arc(seed):
    """A crooked arc of current across the cell."""
    r = np.random.default_rng(seed)
    pts = [(2 + 4.6 * k, 16 + (r.random() - 0.5) * 16 * (0 < k < 6)) for k in range(7)]
    lum = np.zeros((32, 32))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        lum = np.maximum(lum, segment(x0, y0, x1, y1, 1.7))
    fork = segment(pts[3][0], pts[3][1], pts[3][0] + 5, pts[3][1] + (7 if seed % 2 else -7), 1.3)
    return clip(np.maximum(lum, 0.8 * fork))


def dragon_face():
    """A dragon of flame seen head-on: horns, two slanted eyes, a snout."""
    x, y = grid()
    r = np.hypot((x - 16) / 1.0, (y - 18) / 1.15)
    head = clip(1 - r / (10.5 + 2 * fbm(31))) ** 0.6 * (0.7 + 0.5 * fbm(33))
    horns = np.maximum(segment(9, 12, 3, 1, 2.6), segment(23, 12, 29, 1, 2.6))
    eyes = np.maximum(segment(9.5, 15, 13.5, 17, 1.5), segment(22.5, 15, 18.5, 17, 1.5))
    snout = clip(1 - np.hypot(x - 16, (y - 24) * 1.4) / 4.0) * 0.5
    return clip(np.maximum(head, horns) * (1 - eyes) + snout)


def talisman():
    """A slip of paper with a painted dot and band (the palette runs from ink to paper)."""
    x, y = grid()
    inside = (np.abs(x - 16) < 7) & (y > 2) & (y < 30)
    edge = inside & ((np.abs(x - 16) > 5.5) | (y < 4) | (y > 28))
    ink = (np.hypot(x - 16, y - 11) < 3.3) | ((np.abs(y - 22) < 1.6) & (np.abs(x - 16) < 4.5))
    return np.where(inside, np.where(ink, 0.22, np.where(edge, 0.6, 0.97)), 0.0)


def emblem(turn=0.0):
    """A knight's shield: a rim, a dim face and a ring at its heart."""
    x, y = grid()
    c, s = math.cos(turn), math.sin(turn)
    x, y = 16 + (x - 16) * c - (y - 16) * s, 16 + (x - 16) * s + (y - 16) * c
    w = np.where(y < 13, 10.5, 10.5 * np.sqrt(clip(1 - ((y - 13) / 16.5) ** 2)))
    d = np.abs(x - 16) / np.maximum(w, 0.01)
    body = (d < 1) & (y > 3)
    rim = body & ((d > 0.78) | (y < 5.2))
    r = np.hypot(x - 16, y - 13)
    heart = clip(1 - np.abs(r - 4.2) / 1.4)
    chevron = clip(1 - np.abs((y - 20) - np.abs(x - 16) * 0.9) / 1.3) * (np.abs(x - 16) < 5)
    return clip(np.where(rim, 1.0, body * 0.38) + body * np.maximum(heart, chevron))


def mandala():
    """A wheel: two rings, a line of scallops between them and eight beads."""
    r, ang = polar()
    scallop = clip(1 - np.abs(r - (9.2 + 2.2 * np.abs(np.cos(ang * 4)))) / 1.1)
    beads = clip(np.cos(ang * 8 + np.pi) * 2 - 1.0) * clip(1 - np.abs(r - 13) / 2.6)
    return clip(ring(13.5, 1.4) + ring(6.0, 1.0) + 0.8 * scallop + beads)


def petal(flip=False):
    x, y = grid()
    if flip:
        x = 32 - x
    u, v = (x - 16) * 0.82 + (y - 16) * 0.57, -(x - 16) * 0.57 + (y - 16) * 0.82
    body = clip(1.25 - ((u / 5.5) ** 2 + (v / 11.5) ** 2)) * (1 - 0.6 * clip(1 - np.hypot(u, v + 12.5) / 3.0))
    return clip(body) * (0.6 + 0.4 * clip(1 - np.abs(u) / 4.0))


def bead():
    r, _ = polar()
    x, y = grid()
    return clip(clip((8.5 - r) / 1.5) * (0.5 + 0.2 * (1 - r / 9)) + 0.6 * clip(1 - np.hypot(x - 13, y - 12.5) / 3.2))


def sigil(turn=0.0):
    """A circle with a five-point star drawn inside it."""
    lum = ring(13.5, 1.5) + ring(10.5, 0.8)
    pts = [(16 + 10.5 * math.cos(turn + 2 * math.pi * k / 5 - math.pi / 2),
            16 + 10.5 * math.sin(turn + 2 * math.pi * k / 5 - math.pi / 2)) for k in range(5)]
    for k in range(5):
        lum = np.maximum(lum, 0.9 * segment(*pts[k], *pts[(k + 2) % 5], 1.2))
    return clip(lum)


def round_shot():
    """A shot with nothing at its heart: a bright rim and a faint haze."""
    return clip(ring(7.0, 3.0) + 0.35 * glow(15, 1.2))


def sphere(seed):
    """A ball of energy: a bright skin over a churning inside."""
    r, _ = polar()
    return clip(clip(1 - np.abs(r - 12) / 2.6) + (r < 12) * (0.1 + 0.42 * fbm(seed)) * clip(r / 9.0))


def dome():
    """The upper half of a ball, standing on the cell's middle line."""
    x, y = grid()
    r = np.hypot(x - 16, y - 16)
    return clip(clip(1 - np.abs(r - 13) / 2.4) + (r < 13) * (0.22 + 0.5 * fbm(41))) * clip((17.0 - y) / 3.5)


# ----------------------------------------------------------------- shared pieces
def gather(fx, name, count, cell, colour, size, radius, ticks, clut=0):
    """Define the routine `name`: a mote born somewhere within `radius` of AT that flies into AT in `ticks` ticks."""
    pool = fx.pool(name, count, 3)
    col, vel = fx.colour(*colour), iv(FREE)
    fx.begin(name, pool, name + '_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.scatter(POS, radius)
    fx.vcopy(vel, fx.AT); fx.vsub(vel, POS); fx.vdiv(vel, ticks); fx.ret()
    fx.label(name + '_tick'); fx.life(ticks - 1); fx.vadd(POS, vel); fx.ret()
    fx.label(name + '_render'); fx.sprite(POS, col, size, cell=cell, clut=clut); fx.ret()
    return pool


def ahead(fx, out, base, reach):
    """out = base moved towards the target, `reach` past the caster's own radius (on the ground plane)."""
    ok = fx.label()
    fx.vcopy(fx.TV, fx.TGT); fx.vsub(fx.TV, fx.SRC); fx.set(at(fx.TV, 1), 0)
    fx.vlen(fx.T, fx.TV); fx.br(fx.T, '>', 0, ok); fx.set(fx.T, 1)
    fx.label(ok)
    fx.lin(fx.T2, at(fx.SSIZE, 0), 1, reach)
    fx.vmul(fx.TV, fx.T2); fx.vdiv(fx.TV, fx.T)
    fx.vcopy(out, base); fx.vadd(out, fx.TV)


def band(fx, a, b, half, colour, cell, clut=0, blend='add'):
    """A beam between two points: the cell stretched from a to b, `half` above and below the line."""
    q = fx.Q
    for k, (p, sign) in enumerate(((a, -1), (b, -1), (a, 1), (b, 1))):
        fx.vcopy(q[k], p)
        (fx.sub_ if sign < 0 else fx.add)(at(q[k], 1), half)
    fx.quad(q[0], q[1], q[2], q[3], colour, cell, clut, blend)


def flicker(fx, pos, colour, size, cells, clut=0, blend='add', every=2):
    """A sprite that swaps between two cells every few ticks."""
    other, done = fx.label(), fx.label()
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2 * every); fx.br(fx.T2, '>=', every, other)
    fx.sprite(pos, colour, size, cell=cells[0], clut=clut, blend=blend); fx.jmp(done)
    fx.label(other); fx.sprite(pos, colour, size, cell=cells[1], clut=clut, blend=blend)
    fx.label(done)


# ----------------------------------------------------------------- Guilmon
def pyrosphere():
    """Sparks gather at Guilmon's mouth into a ball of fire with a white heart; it flies straight, trailing flames,
    and bursts in a ring where it lands. A target that moves away is missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(FIRE)
    fx.paint(0, fireball(3)); fx.paint(1, fireball(11)); fx.paint(2, glow(15, 1.3)); fx.paint(3, tongue())
    fx.paint(4, ring(13, 2.2)); fx.paint(5, star(4, 2, 9, 6))
    hot, soft = fx.colour(128, 128, 128), fx.colour(128, 70, 30)
    mouth = fx.vec()
    gather(fx, 'spark', 14, 5, (128, 110, 60), 90, 560, 6)
    fx.particle('core', 1, 7, 0, (128, 128, 128), 40, grow=32)
    fx.particle('tail', 14, 6, 3, (128, 90, 40), 250, grow=-30, lift=6, fade=True)
    fx.particle('ember', 16, 12, 5, (128, 100, 50), (50, 100), speed=14, gravity=3, spread=80, fade=True)
    fx.particle('blast', 2, 8, 0, (128, 128, 128), None, grow=70, fade=True)
    fx.particle('shock', 2, 8, 4, (128, 80, 30), 140, grow=90, fade=True)
    fx.particle('lick', 10, 10, 3, (128, 100, 50), (160, 260), grow=-12, flat=((-25, 25), (-70, -30), (-25, 25)),
                spread=120)
    fx.particle('chip', 12, 12, 5, (128, 120, 70), (70, 130), grow=-6, speed=70, lift=30, gravity=8, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(7, 'spit')
    fx.br(fx.NOW, '>', 5, 'main_end'); fx.emit('spark', mouth, 2)
    fx.label('main_end'); fx.end(8)
    fx.label('begin')
    fx.vcopy(mouth, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), 8, 0, 10); fx.sub_(at(mouth, 1), fx.T3)
    ahead(fx, mouth, mouth, 30)
    fx.emit('core', mouth); fx.sound(-55); fx.ret()
    fx.label('spit')
    fx.sound(3); fx.aim(); fx.vcopy(fx.AT, mouth); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('ball'); fx.ret()
    fx.shot('ball', 1, 80, 24, 'ball_render', 'ball_arrive', miss='ball_miss', every='ball_trail')
    fx.label('ball_trail'); fx.emit('tail', POS); fx.emit('ember', POS); fx.ret()
    fx.label('ball_miss'); fx.emit('ember', POS, 6); fx.ret()
    fx.label('ball_render')
    fx.sprite(POS, soft, 440, cell=2); flicker(fx, POS, hot, 310, (0, 1), every=1); fx.ret()
    fx.label('ball_arrive')
    fx.sound(7)
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 280, 10)
    fx.emit('blast', POS); fx.emit('shock'); fx.emit('lick', times=8); fx.emit('chip', times=10); fx.ret()
    return fx


# ----------------------------------------------------------------- Renamon
def diamond_storm():
    """Eight crystals take shape in a ring over Renamon and fall one after another on the spot where its target
    stands, breaking there. Whoever is still on that spot when the fourth lands is hit."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(ICE)
    fx.paint(0, diamond()); fx.paint(1, glow(15, 1.3)); fx.paint(2, star(4, 2, 9, 6)); fx.paint(3, shard())
    fx.paint(4, ring(13, 2.0)); fx.paint(5, diamond(0.45))
    tint, soft = fx.colour(128, 128, 128), fx.colour(50, 90, 128)
    spot, place = fx.vec(), fx.vec()
    seeded, loosed, idx = fx.var(), fx.var(), fx.var()
    first, flight = 10, 5
    fx.particle('bud', 8, 10, 0, (110, 128, 128), 50, grow=18)
    fx.particle('twinkle', 12, 6, 2, (128, 128, 128), (60, 110), grow=-8, spread=120)
    fx.particle('chip', 20, 12, 3, (120, 128, 128), (70, 130), grow=-5, speed=60, lift=45, gravity=10, spread=80,
                spin=20)
    fx.particle('frost', 4, 8, 1, (60, 100, 128), 160, grow=40, fade=True)
    fx.particle('wave', 2, 9, 4, (90, 120, 128), 200, grow=90, fade=True, sy=6)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(8):
        fx.when(k, 'seed'); fx.when(first + k, 'loose')
    fx.when(first + 3 + flight, 'impact'); fx.end(first + 8 + flight)
    fx.label('begin'); fx.vcopy(spot, fx.TGT); fx.set(seeded, 0); fx.set(loosed, 0); fx.ret()
    fx.label('at_ring')                     # place = the idx-th point of the ring over the caster
    fx.lin(fx.T, idx, 512, 256); fx.circle(place, fx.T, 300, 0); fx.vadd(place, fx.SRC)
    fx.lin(fx.T, at(fx.SSIZE, 1), 1, 170); fx.sub_(at(place, 1), fx.T); fx.ret()
    fx.label('seed')
    fx.set(idx, seeded); fx.add(seeded, 1); fx.call('at_ring'); fx.emit('bud', place); fx.sound(34); fx.ret()
    fx.label('loose')
    fx.set(idx, loosed); fx.add(loosed, 1); fx.call('at_ring')
    fx.vcopy(fx.DEST, spot); fx.scatter(fx.DEST, 340); fx.lin(at(fx.DEST, 1), at(spot, 1), 1, -50)
    fx.vcopy(fx.AT, place); fx.call('crystal'); fx.ret()
    fx.travel('crystal', 8, flight, 'crystal_render', 'crystal_arrive', every='crystal_trail')
    fx.label('crystal_trail'); fx.emit('twinkle', POS); fx.ret()
    fx.label('crystal_render'); fx.sprite(POS, soft, 320, cell=1); fx.sprite(POS, tint, 240, cell=5); fx.ret()
    fx.label('crystal_arrive'); fx.sound(20); fx.emit('chip', POS, 3); fx.emit('frost', POS); fx.ret()
    fx.label('impact'); fx.strike(spot, 250); fx.emit('wave', spot); fx.sound(7); fx.ret()
    return fx


# ----------------------------------------------------------------- Growlmon
def plasma_blade():
    """Current crackles over Growlmon's arms, then two burning cuts cross on the target, the second one landing the
    blow and leaving arcs dancing on it."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(PLASMA)
    fx.paint(0, slash(np.pi * 0.25)); fx.paint(1, slash(np.pi * 0.75)); fx.paint(2, arc(5)); fx.paint(3, arc(8))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, star(4, 2, 9, 6))
    fx.particle('crackle', 8, 3, 2, (128, 110, 60), (220, 330), spread=440)
    fx.particle('crackle2', 8, 3, 3, (128, 110, 60), (220, 330), spread=440)
    fx.particle('cut1', 1, 7, 0, (128, 128, 128), None, grow=45, fade=True)
    fx.particle('cut2', 1, 8, 1, (128, 128, 128), None, grow=55, fade=True)
    fx.particle('heat', 2, 6, 4, (70, 30, 8), None, grow=20, fade=True)
    fx.particle('spark', 16, 11, 5, (128, 120, 70), (80, 150), grow=-8, speed=75, lift=20, gravity=6, spread=60)
    fx.particle('jolt', 8, 4, 2, (128, 120, 90), (230, 330), spread=280)
    fx.particle('jolt2', 8, 4, 3, (128, 120, 90), (230, 330), spread=280)
    fx.label('main'); fx.when(0, 'hum'); fx.when(6, 'first'); fx.when(10, 'second')
    for t in (11, 13, 15, 17):
        fx.when(t, 'shock')
    fx.br(fx.NOW, '>', 5, 'main_end'); fx.emit('crackle', fx.CHEST); fx.emit('crackle2')
    fx.label('main_end'); fx.end(18)
    fx.label('hum'); fx.sound(-55); fx.ret()
    fx.label('first')
    fx.sound(13); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 520)
    fx.emit('cut1', fx.TCHEST); fx.emit('heat'); fx.emit('spark', times=5); fx.ret()
    fx.label('second')
    fx.sound(16); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 600)
    fx.emit('cut2', fx.TCHEST); fx.emit('heat'); fx.emit('spark', times=10); fx.ret()
    fx.label('shock'); fx.aim(); fx.emit('jolt', fx.TCHEST); fx.emit('jolt2'); fx.ret()
    return fx


# ----------------------------------------------------------------- Kyubimon
def dragon_wheel():
    """Blue flames wheel round Kyubimon and pour into a dragon of fire that snakes along the line to where its target
    stood and beyond, burning everybody it passes through."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(BLUEFIRE)
    fx.paint(0, dragon_face()); fx.paint(1, fireball(13)); fx.paint(2, fireball(17)); fx.paint(3, tongue(6))
    fx.paint(4, clip(ring(12.5, 2.4) * (0.5 + 1.0 * fbm(19)))); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, glow(15, 1.2))
    tint, soft = fx.colour(128, 128, 128), fx.colour(40, 80, 128)
    step = fx.vec()
    spin, run = 10, 15
    fx.particle('seg', 14, 10, 1, (110, 120, 128), 330, grow=-26)
    fx.particle('ember', 16, 12, 5, (90, 110, 128), (50, 100), speed=10, gravity=2, spread=120, fade=True)
    fx.particle('burst', 3, 8, 2, (128, 128, 128), None, grow=60, fade=True)
    fx.particle('lick', 12, 10, 3, (100, 120, 128), (150, 240), grow=-12, flat=((-25, 25), (-70, -30), (-25, 25)),
                spread=140)
    fx.label('main'); fx.when(0, 'begin'); fx.when(spin, 'loose'); fx.end(spin + 1)
    fx.label('begin'); fx.call('wheel'); fx.ret()
    fx.label('loose')
    fx.sound(13); fx.aim(); fx.vcopy(step, fx.TGT); fx.vsub(step, fx.SRC); fx.set(at(step, 1), 0); fx.vdiv(step, 10)
    fx.vcopy(fx.AT, fx.SRC); fx.call('dragon'); fx.ret()
    wheel = fx.pool('wheel', 1)
    fx.begin('wheel', wheel, 'wheel_render', inherit=False); fx.vcopy(POS, fx.CHEST); fx.sound(-55); fx.ret()
    fx.label('wheel_tick'); fx.life(spin + 2); fx.ret()
    fx.label('wheel_render')
    fx.lin(fx.T3, FRAME, -22, 420)
    for k in range(6):
        fx.lin(fx.T, FRAME, 420, 683 * k); fx.circle(fx.TV, fx.T, fx.T3, 0); fx.vadd(fx.TV, POS)
        fx.sprite(fx.TV, tint, 210, cell=3)
    fx.lin(fx.T2, FRAME, 200); fx.lin(fx.T3, fx.T3, 12, 0, 10)
    fx.flat(fx.SRC, fx.T3, soft, cell=4, angle=fx.T2); fx.ret()
    dragon = fx.pool('dragon', 1, 1)
    sway = iv(FREE)
    fx.begin('dragon', dragon, 'dragon_render', inherit=False); fx.vcopy(POS, fx.AT); fx.set(sway, 0); fx.ret()
    fx.label('dragon_tick')
    fx.life(run)
    fx.vadd(POS, step)
    fx.lin(fx.T3, FRAME, 620); fx.sin(sway, fx.T3, 120)
    fx.vcopy(fx.TV, POS); fx.set(at(fx.TV, 1), at(fx.CHEST, 1)); fx.sub_(at(fx.TV, 1), sway)
    fx.vcopy(fx.TV2, fx.TV)
    fx.emit('seg', fx.TV2); fx.emit('ember', fx.TV2)
    fx.strike(POS, 230); fx.br(fx.HIT, '==', 0, 'noop')
    fx.sound(7); fx.set(fx.SZ, 420); fx.emit('burst', fx.TV2); fx.emit('lick', times=6); fx.ret()
    fx.label('dragon_render')
    fx.vcopy(fx.TV, POS); fx.set(at(fx.TV, 1), at(fx.CHEST, 1)); fx.sub_(at(fx.TV, 1), sway)
    fx.sprite(fx.TV, soft, 480, cell=6); fx.sprite(fx.TV, tint, 360, cell=0); fx.ret()
    return fx


# ----------------------------------------------------------------- WarGrowlmon
def atomic_blaster():
    """Two lights swell on WarGrowlmon's chest cannons and let go two red beams side by side, which run down the line
    past the target throwing rings; everybody on that line is hit as the beams reach them."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(CRIMSON)
    fx.paint(0, bar()); fx.paint(1, glow(15, 1.2)); fx.paint(2, ring(13, 2.0)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, puff(23))
    tint, edge = fx.colour(128, 128, 128), fx.colour(128, 36, 30)
    step, side, left, right = fx.vec(), fx.vec(), fx.vec(), fx.vec()
    span = fx.var()
    charge, sweep, hold = 8, 7, 15
    gather(fx, 'mote', 16, 3, (128, 90, 70), 80, 460, 5)
    fx.particle('lamp', 2, charge, 1, (128, 80, 60), 40, grow=30)
    fx.particle('shock', 6, 7, 2, (128, 70, 50), 120, grow=70, fade=True)
    fx.particle('cinder', 20, 14, 3, (128, 90, 60), (50, 100), flat=((-8, 8), (-30, -10), (-8, 8)), spread=160,
                fade=True)
    fx.particle('smoke', 12, 14, 4, (50, 24, 22), (170, 250), grow=14, lift=10, spread=110, fade=True)
    fx.particle('blast', 3, 8, 1, (128, 128, 128), None, grow=60, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'fire')
    fx.br(fx.NOW, '>', charge - 4, 'main_end'); fx.emit('mote', left); fx.emit('mote', right)
    fx.label('main_end'); fx.end(charge + 1)
    fx.label('lay')                         # the line to the target: a step along it, half the gap, the two muzzles
    fx.vcopy(step, fx.TGT); fx.vsub(step, fx.SRC); fx.set(at(step, 1), 0)
    fx.vlen(span, step); fx.br(span, '>', 0, 'lay_ok'); fx.set(span, 1)
    fx.label('lay_ok')
    fx.lin(at(side, 0), at(step, 2), 120, 0, span); fx.set(at(side, 1), 0)
    fx.lin(at(side, 2), at(step, 0), -120, 0, span)
    ahead(fx, left, fx.CHEST, 20)
    fx.vcopy(right, left); fx.vadd(left, side); fx.vsub(right, side)
    fx.vdiv(step, 5); fx.ret()
    fx.label('begin'); fx.call('lay'); fx.emit('lamp', left); fx.emit('lamp', right); fx.sound(-55); fx.ret()
    fx.label('fire'); fx.sound(13); fx.aim(); fx.call('lay'); fx.vcopy(fx.AT, fx.SRC); fx.call('beam'); fx.ret()
    beam = fx.pool('beam', 1)
    fx.begin('beam', beam, 'beam_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('beam_tick')
    fx.life(hold)
    fx.br(FRAME, '>', sweep, 'beam_smoke')
    fx.vadd(POS, step)
    fx.vcopy(fx.TV2, POS); fx.set(at(fx.TV2, 1), at(fx.CHEST, 1))
    fx.emit('shock', fx.TV2); fx.emit('cinder', times=2)
    fx.strike(POS, 230); fx.br(fx.HIT, '==', 0, 'noop')
    fx.sound(16); fx.set(fx.SZ, 460); fx.emit('blast', fx.TV2); fx.ret()
    fx.label('beam_smoke')                  # the line smokes behind the beams
    fx.rnd(fx.T3, 1, sweep); fx.vcopy(fx.TV2, step); fx.vmul(fx.TV2, fx.T3); fx.vadd(fx.TV2, fx.SRC)
    fx.set(at(fx.TV2, 1), at(fx.CHEST, 1)); fx.emit('smoke', fx.TV2); fx.emit('cinder'); fx.ret()
    fx.label('beam_render')
    fx.lin(fx.T3, FRAME, 30, 30); fx.br(FRAME, '<', 2, 'beam_draw')
    fx.set(fx.T3, FRAME); fx.mod(fx.T3, 2); fx.mul(fx.T3, 30); fx.add(fx.T3, 130); fx.br(FRAME, '<', hold - 5, 'beam_draw')
    fx.lin(fx.T3, FRAME, -26, 26 * hold + 8)
    fx.label('beam_draw')
    fx.lin(fx.F1, fx.T3, 1, 0, 2)
    for muzzle, move in ((left, fx.vadd), (right, fx.vsub)):
        fx.vcopy(fx.TV, POS); fx.set(at(fx.TV, 1), at(fx.CHEST, 1)); move(fx.TV, side)
        band(fx, muzzle, fx.TV, fx.T3, edge, 0)
        band(fx, muzzle, fx.TV, fx.F1, tint, 0)
        fx.lin(fx.T2, fx.T3, 2); fx.sprite(fx.TV, tint, fx.T2, cell=1); fx.sprite(muzzle, edge, fx.T2, cell=1)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Taomon
def talisman_of_light():
    """Four paper talismans fly to the corners of a square round the target; lines of light join them into a seal that
    turns, and a moment later a golden column rises inside it. Only who is still inside the seal then is hit."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(GOLD); fx.palette(PAPER)
    fx.paint(0, talisman()); fx.paint(1, bar(7)); fx.paint(2, glow(15, 1.2)); fx.paint(3, column())
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, ring(13, 2.0))
    tint, gold = fx.colour(128, 128, 128), fx.colour(128, 104, 50)
    line = [fx.vec() for _ in range(4)]
    form, burn, side = 7, 21, 340
    fx.particle('glint', 16, 12, 4, (128, 128, 100), (80, 150), grow=-7, speed=40, lift=40, gravity=4, spread=260)
    fx.particle('flare', 1, 8, 2, (128, 120, 80), None, grow=50, fade=True)
    fx.particle('ripple', 2, 9, 5, (128, 104, 50), 240, grow=90, fade=True, sy=6)
    fx.label('main'); fx.when(0, 'begin'); fx.end(1)
    fx.label('begin'); fx.vcopy(fx.AT, fx.TGT); fx.call('seal'); fx.ret()
    seal = fx.pool('seal', 1)
    fx.begin('seal', seal, 'seal_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('seal_tick')
    fx.life(burn + 10); fx.after(form, 'seal_lock'); fx.after(burn, 'seal_burn'); fx.ret()
    fx.label('seal_lock'); fx.sound(34); fx.ret()
    fx.label('seal_burn')
    fx.sound(15); fx.strike(POS, side + 20)
    fx.vcopy(fx.AT, POS); fx.sub_(at(fx.AT, 1), 260); fx.set(fx.SZ, 620)
    fx.call('flare'); fx.call('glint', 14); fx.emit('ripple', POS); fx.ret()
    fx.label('seal_render')
    # the corners: on their way from the caster, then standing, then turning with the seal
    fx.set(fx.T3, 0); fx.br(FRAME, '<', form, 'seal_corners'); fx.lin(fx.T3, FRAME, 26, -26 * form)
    fx.label('seal_corners')
    for k in range(4):
        there = fx.label()
        fx.lin(fx.T, fx.T3, 1, 512 + 1024 * k); fx.circle(fx.Q[k], fx.T, side, 0); fx.vadd(fx.Q[k], POS)
        fx.sub_(at(fx.Q[k], 1), 260)
        fx.br(FRAME, '>=', form, there)
        fx.vcopy(fx.TV2, fx.CHEST); fx.vsub(fx.TV2, fx.Q[k]); fx.lin(fx.T, FRAME, -1, form)
        fx.vmul(fx.TV2, fx.T); fx.vdiv(fx.TV2, form); fx.vadd(fx.Q[k], fx.TV2)
        fx.label(there)
    fx.br(FRAME, '>', burn + 3, 'seal_light')
    for k in range(4):
        fx.sprite(fx.Q[k], gold, 280, cell=2)
        fx.sprite(fx.Q[k], tint, 170, 240, cell=0, clut=1, blend=None)
    fx.label('seal_light')
    fx.br(FRAME, '<', form, 'noop')
    fx.lin(fx.T2, FRAME, 9, 12 - 9 * form); fx.br(fx.T2, '<', 52, 'seal_lines'); fx.set(fx.T2, 52)
    fx.label('seal_lines')
    fx.br(FRAME, '<', burn + 4, 'seal_join'); fx.lin(fx.T2, FRAME, -8, 8 * (burn + 11))
    fx.label('seal_join')
    for k in range(4):
        a, b = fx.Q[k], fx.Q[(k + 1) % 4]
        for j, (p, sign) in enumerate(((a, -1), (b, -1), (a, 1), (b, 1))):
            fx.vcopy(line[j], p)
            (fx.sub_ if sign < 0 else fx.add)(at(line[j], 1), fx.T2)
        fx.quad(line[0], line[1], line[2], line[3], gold, cell=1)
    # the column
    fx.br(FRAME, '<', burn, 'noop'); fx.br(FRAME, '>', burn + 8, 'noop')
    fx.lin(fx.T3, FRAME, -50, 560 + 50 * burn)
    fx.pillar(POS, fx.T3, 1200, gold, cell=3)
    fx.lin(fx.T3, fx.T3, 6, 0, 10)
    fx.pillar(POS, fx.T3, 1200, tint, cell=3); fx.ret()
    return fx


# ----------------------------------------------------------------- Gallantmon
def final_purification():
    """The shield's emblem lights up before Gallantmon and turns as light pours into it; then it lets go a wide white
    beam with a crimson edge that follows its target and bursts on it in a star."""
    fx = Fx(delay=8, cast_sound=2, draw=True)
    fx.palette(ROYAL); fx.palette(GOLD)
    fx.paint(0, emblem()); fx.paint(1, emblem(np.pi / 4)); fx.paint(2, bar(15)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2.5, 13, 10)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.0))
    tint, edge, wash = fx.colour(128, 128, 128), fx.colour(128, 30, 44), fx.vec()
    muzzle = fx.vec()
    charge, smite, ray_life = 10, 12, 11
    gather(fx, 'mote', 14, 5, (128, 110, 110), 80, 640, 6)
    fx.particle('flare', 1, 9, 4, (128, 128, 128), None, grow=80, fade=True)
    fx.particle('halo', 2, 8, 6, (128, 60, 70), 160, grow=90, fade=True)
    fx.particle('glint', 14, 12, 5, (128, 128, 128), (90, 170), grow=-8, speed=80, lift=20, gravity=5, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose'); fx.when(smite, 'smite')
    fx.br(fx.NOW, '>', charge - 3, 'main_end'); fx.emit('mote', muzzle, 2)
    fx.label('main_end'); fx.end(charge + ray_life + 3)
    fx.label('draw')
    fx.br(fx.NOW, '<', smite, 'noop'); fx.br(fx.NOW, '>', smite + 5, 'noop')
    fx.lin(fx.T, fx.NOW, -12, 12 * (smite + 6)); fx.vset(wash, fx.T, fx.T, fx.T)
    fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    ahead(fx, muzzle, fx.CHEST, 70); fx.vcopy(fx.AT, muzzle); fx.call('crest'); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(13); fx.call('ray'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit()
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 14, 340, 10)
    fx.emit('flare', fx.TCHEST); fx.emit('halo'); fx.emit('glint', times=14); fx.ret()
    crest = fx.pool('crest', 1)
    fx.begin('crest', crest, 'crest_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('crest_tick'); fx.life(charge + ray_life); fx.ret()
    fx.label('crest_render')
    fx.lin(fx.T3, FRAME, 28, 60); fx.br(FRAME, '<', charge, 'crest_draw')
    fx.set(fx.T3, 340); fx.br(FRAME, '<', charge + ray_life - 4, 'crest_draw')
    fx.lin(fx.T3, FRAME, -80, 80 * (charge + ray_life) + 20)
    fx.label('crest_draw')
    fx.lin(fx.T, fx.T3, 14, 0, 10); fx.sprite(POS, edge, fx.T, cell=3)
    flicker(fx, POS, tint, fx.T3, (0, 1), clut=1, every=2); fx.ret()
    ray = fx.pool('ray', 1)
    fx.begin('ray', ray, 'ray_render', inherit=False); fx.vcopy(POS, muzzle); fx.ret()
    fx.label('ray_tick'); fx.life(ray_life); fx.aim(); fx.ret()
    fx.label('ray_render')
    fx.lin(fx.T3, FRAME, 60, 40); fx.br(FRAME, '<', 2, 'ray_draw')
    fx.set(fx.T3, FRAME); fx.mod(fx.T3, 2); fx.mul(fx.T3, 36); fx.add(fx.T3, 210); fx.br(FRAME, '<', ray_life - 3, 'ray_draw')
    fx.lin(fx.T3, FRAME, -56, 56 * ray_life + 30)
    fx.label('ray_draw')
    band(fx, muzzle, fx.TCHEST, fx.T3, edge, 2)
    fx.lin(fx.T2, fx.T3, 1, 0, 2); band(fx, muzzle, fx.TCHEST, fx.T2, tint, 2)
    fx.lin(fx.T2, fx.T3, 2); fx.sprite(fx.TCHEST, tint, fx.T2, cell=3); fx.ret()
    return fx


# ----------------------------------------------------------------- Sakuyamon
def amethyst_mandala():
    """A violet wheel with four golden beads opens from Sakuyamon's feet across the field among falling petals; a ring
    closes on each enemy as the wheel reaches it, and that is when it is hit."""
    fx = Fx(delay=8, cast_sound=45)
    fx.palette(AMETHYST); fx.palette(GOLD)
    fx.paint(0, mandala()); fx.paint(1, petal()); fx.paint(2, glow(15, 1.2)); fx.paint(3, bead())
    fx.paint(4, ring(13.5, 1.6)); fx.paint(5, petal(True)); fx.paint(6, star(4, 2, 9, 6))
    tint, soft, fade = fx.colour(128, 128, 128), fx.colour(96, 50, 128), fx.vec()
    rad, wait = fx.var(), fx.var()
    speed, reach = 70, 18
    fx.particle('fall', 14, 16, 1, (128, 110, 128), (90, 150), flat=((-12, 12), (10, 24), (-12, 12)), spread=300)
    fx.particle('fall2', 14, 16, 5, (128, 110, 128), (90, 150), flat=((-12, 12), (10, 24), (-12, 12)), spread=300)
    fx.particle('bloom', 4, 8, 2, (128, 100, 128), None, grow=45, fade=True)
    fx.particle('glint', 16, 12, 6, (128, 120, 128), (80, 150), grow=-7, speed=50, lift=40, gravity=5, spread=120)
    fx.label('main'); fx.when(0, 'begin')
    fx.lin(rad, fx.NOW, speed, 150)
    fx.br(fx.NOW, '>', reach, 'main_end')
    fx.rnd(fx.T3, 0, 4095); fx.circle(fx.AT, fx.T3, rad, 0); fx.vadd(fx.AT, fx.SRC); fx.sub_(at(fx.AT, 1), 420)
    fx.call('fall'); fx.call('fall2')
    fx.br(fx.NOW, '<', 2, 'main_end')
    fx.strike(fx.SRC, rad)
    fx.label('main_end'); fx.end(reach + 5)
    fx.label('begin')
    fx.call('wheel')

    def mark():
        fx.vcopy(fx.TV, fx.TGT); fx.vsub(fx.TV, fx.SRC); fx.set(at(fx.TV, 1), 0); fx.vlen(wait, fx.TV)
        fx.sub_(wait, 150); fx.div(wait, speed); fx.br(wait, '>=', 2, 'mark_go'); fx.set(wait, 2)
        fx.label('mark_go'); fx.vcopy(fx.AT, fx.TGT); fx.call('ward')
    fx.each_target(mark); fx.ret()
    ward = fx.pool('ward', 4, 2)
    due, tall = iv(FREE), iv(FREE + 4)
    fx.begin('ward', ward, 'ward_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.set(due, wait); fx.set(tall, at(fx.TSIZE, 1)); fx.ret()
    fx.label('ward_tick')
    fx.lin(fx.T, due, 1, 8); fx.br(FRAME, '>', fx.T, 'die')
    fx.br(FRAME, '!=', due, 'noop')
    fx.sound(7); fx.lin(fx.SZ, tall, 12, 280, 10)
    fx.vcopy(fx.AT, POS); fx.lin(fx.T, tall, 6, 0, 10); fx.sub_(at(fx.AT, 1), fx.T)
    fx.call('bloom'); fx.call('glint', 6); fx.ret()
    fx.label('ward_render')
    fx.set(fx.T, due); fx.sub_(fx.T, FRAME); fx.br(fx.T, '>', 5, 'noop'); fx.br(fx.T, '<', 0, 'noop')
    fx.lin(fx.T3, fx.T, 70, 170); fx.lin(fx.T2, FRAME, 120)
    fx.vcopy(fx.TV, POS); fx.sub_(at(fx.TV, 1), 30)
    fx.flat(fx.TV, fx.T3, tint, cell=4, angle=fx.T2); fx.ret()
    wheel = fx.pool('wheel', 1)
    fx.begin('wheel', wheel, 'wheel_render', inherit=False); fx.vcopy(POS, fx.SRC); fx.sub_(at(POS, 1), 14); fx.ret()
    fx.label('wheel_tick'); fx.life(reach + 5); fx.ret()
    fx.label('wheel_render')
    fx.set(fx.T, 128); fx.br(FRAME, '<=', reach, 'wheel_draw'); fx.lin(fx.T, FRAME, -24, 128 + 24 * reach)
    fx.label('wheel_draw')
    fx.vset(fade, fx.T, fx.T, fx.T)
    fx.lin(fx.T3, FRAME, speed, 150)
    for k in range(16):
        fx.lin(fx.T, FRAME, 50, 256 * k); fx.circle(fx.TV, fx.T, fx.T3, 0); fx.vadd(fx.TV, POS)
        if k % 4 == 0:
            fx.sub_(at(fx.TV, 1), 90); fx.sprite(fx.TV, fade, 190, cell=3, clut=1)
        else:
            fx.sub_(at(fx.TV, 1), 50); fx.sprite(fx.TV, fade, 170, cell=1 if k % 2 else 5)
    fx.lin(fx.T3, FRAME, 60, 120); fx.br(FRAME, '<', 5, 'wheel_seal'); fx.set(fx.T3, 420)
    fx.label('wheel_seal')
    fx.lin(fx.T2, FRAME, 60); fx.flat(POS, fx.T3, fade, cell=0, angle=fx.T2)
    fx.lin(fx.T3, fx.T3, 6, 0, 10); fx.lin(fx.T2, FRAME, -90)
    fx.flat(POS, fx.T3, soft, cell=0, angle=fx.T2); fx.ret()
    return fx


# ----------------------------------------------------------------- Beelzemon
def corona_blaster():
    """A circle with a star in it opens before the gun and three black shots rimmed in violet leave through it one
    after another, each aimed anew. The first one that connects deals the damage."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(VIOLET)
    fx.paint(0, sigil()); fx.paint(1, round_shot()); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, disc()); fx.paint(5, ring(13, 2.0)); fx.paint(6, sigil(np.pi / 5))
    tint, rim, dark = fx.colour(128, 128, 128), fx.colour(120, 50, 128), fx.colour(120, 120, 120)
    muzzle = fx.vec()
    landed = fx.const(0)
    first, gap = 8, 4
    fx.particle('flash', 3, 4, 2, (128, 90, 128), 200, grow=50, fade=True)
    fx.particle('wisp', 18, 6, 2, (90, 30, 120), 150, grow=-20, fade=True)
    fx.particle('void', 3, 7, 4, (120, 120, 120), 100, grow=50, blend='sub', fade=True)
    fx.particle('halo', 3, 8, 5, (128, 70, 128), 120, grow=90, fade=True)
    fx.particle('chip', 18, 11, 3, (128, 90, 128), (70, 130), grow=-7, speed=70, spread=60)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(3):
        fx.when(first + gap * k, 'fire')
    fx.end(first + 2 * gap + 1)
    fx.label('begin')
    ahead(fx, muzzle, fx.CHEST, 100); fx.vcopy(fx.AT, muzzle); fx.call('seal'); fx.sound(-55); fx.ret()
    fx.label('fire')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, muzzle); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('bullet')
    fx.emit('flash', muzzle); fx.ret()
    fx.shot('bullet', 3, 95, 20, 'bullet_render', 'bullet_arrive', every='bullet_trail')
    fx.label('bullet_trail')
    fx.emit('wisp', POS)
    fx.br(landed, '==', 0, 'noop')          # the engine no longer stops a shot on a target already hit: do it here
    fx.aim(); fx.vcopy(fx.TV, fx.TCHEST); fx.vsub(fx.TV, POS); fx.vlen(fx.T, fx.TV)
    fx.br(fx.T, '>', 190, 'noop')
    fx.call('bullet_burst'); fx.set(FRAME, -1); fx.ret()
    fx.label('bullet_render')
    fx.sprite(POS, dark, 170, cell=4, blend='sub'); fx.sprite(POS, rim, 280, cell=1); fx.ret()
    fx.label('bullet_arrive'); fx.set(landed, 1)
    fx.label('bullet_burst')
    fx.sound(16); fx.emit('void', POS); fx.emit('halo'); fx.emit('chip', times=6); fx.ret()
    seal = fx.pool('seal', 1)
    last = first + 2 * gap + 5
    fx.begin('seal', seal, 'seal_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('seal_tick'); fx.life(last); fx.ret()
    fx.label('seal_render')
    fx.lin(fx.T3, FRAME, 44, 60); fx.br(FRAME, '<', first, 'seal_draw')
    fx.set(fx.T3, 400); fx.br(FRAME, '<', last - 4, 'seal_draw')
    fx.lin(fx.T3, FRAME, -90, 90 * last + 40)
    fx.label('seal_draw')
    fx.lin(fx.T, fx.T3, 13, 0, 10); fx.sprite(POS, rim, fx.T, cell=2)
    flicker(fx, POS, tint, fx.T3, (0, 6), every=2); fx.ret()
    return fx


# ----------------------------------------------------------------- BlackWarGreymon
def terra_destroyer():
    """Red motes climb from all around into a ball that swells over BlackWarGreymon's head, black at its heart, while
    the light of the field sinks; it is thrown at the spot where the target stands and goes up in a red dome that reaches every enemy."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(BLOOD)
    fx.paint(0, sphere(51)); fx.paint(1, sphere(57)); fx.paint(2, glow(15, 1.2)); fx.paint(3, dome())
    fx.paint(4, ring(13, 2.2)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, disc(10))
    tint, dark, wash = fx.colour(128, 128, 128), fx.colour(128, 128, 128), fx.vec()
    spot, top, step = fx.vec(), fx.vec(), fx.vec()
    swell, fly = 16, 7
    land = swell + fly + 1
    gather(fx, 'mote', 20, 5, (128, 60, 40), 100, 1000, 7)
    fx.particle('trail', 10, 6, 2, (128, 40, 24), 420, grow=-50, fade=True)
    fx.particle('cap', 1, 12, 3, (128, 128, 128), 420, grow=95, fade=True)
    fx.particle('blast', 2, 9, 2, (128, 90, 60), 300, grow=120, fade=True)
    fx.particle('debris', 20, 14, 5, (128, 80, 50), (80, 160), grow=-6, speed=70, lift=70, gravity=9, spread=300)
    fx.label('main'); fx.when(0, 'begin')
    fx.br(fx.NOW, '>', swell - 3, 'main_end'); fx.emit('mote', top, 2)
    fx.label('main_end'); fx.end(land + 10)
    fx.label('draw')
    fx.br(fx.NOW, '<', 3, 'noop')
    fx.br(fx.NOW, '>=', land, 'draw_blast')
    fx.lin(fx.T, fx.NOW, 6, -18); fx.br(fx.T, '<', 66, 'draw_dim'); fx.set(fx.T, 66)
    fx.label('draw_dim'); fx.vset(wash, fx.T, fx.T, fx.T); fx.overlay(wash, blend='sub'); fx.ret()
    fx.label('draw_blast')
    fx.br(fx.NOW, '>', land + 6, 'noop')
    fx.lin(fx.T, fx.NOW, -14, 14 * (land + 7)); fx.lin(fx.T2, fx.T, 1, 0, 4)
    fx.vset(wash, fx.T, fx.T2, fx.T2); fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    fx.vcopy(top, fx.SRC); fx.lin(fx.T, at(fx.SSIZE, 1), 1, 440); fx.sub_(at(top, 1), fx.T)
    fx.vcopy(fx.AT, top); fx.call('orb'); fx.sound(-55); fx.ret()
    orb = fx.pool('orb', 1)
    fx.begin('orb', orb, 'orb_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('orb_tick')
    fx.br(FRAME, '<', swell, 'noop')
    fx.br(FRAME, '==', swell, 'orb_throw')
    fx.br(FRAME, '>=', land, 'orb_land')
    fx.vadd(POS, step); fx.emit('trail', POS); fx.ret()
    fx.label('orb_throw')
    fx.sound(3); fx.aim(); fx.vcopy(spot, fx.TGT)
    fx.vcopy(step, spot); fx.vsub(step, POS); fx.vdiv(step, fly); fx.ret()
    fx.label('orb_land')
    fx.sound(15); fx.each_target(fx.hit)          # the blast reaches every enemy
    fx.emit('cap', spot); fx.emit('blast'); fx.emit('debris', times=16); fx.call('scar')
    fx.set(FRAME, -1); fx.ret()
    fx.label('orb_render')
    fx.lin(fx.T3, FRAME, 30, 60); fx.br(FRAME, '<', swell, 'orb_draw'); fx.set(fx.T3, 540)
    fx.label('orb_draw')
    fx.lin(fx.T, fx.T3, 7, 0, 10); fx.sprite(POS, dark, fx.T, cell=6, blend='sub')
    flicker(fx, POS, tint, fx.T3, (0, 1), every=2); fx.ret()
    scar = fx.pool('scar', 1)
    fx.begin('scar', scar, 'scar_render', inherit=False); fx.vcopy(POS, spot); fx.sub_(at(POS, 1), 14); fx.ret()
    fx.label('scar_tick'); fx.life(10); fx.ret()
    fx.label('scar_render')
    fx.lin(fx.T3, FRAME, 85, 220)
    fx.lin(fx.T, FRAME, -11, 124); fx.lin(fx.T2, fx.T, 1, 0, 3); fx.vset(wash, fx.T, fx.T2, fx.T2)
    fx.flat(POS, fx.T3, wash, cell=4); fx.ret()
    return fx


EFFECTS = {433: pyrosphere, 354: diamond_storm, 320: plasma_blade, 409: dragon_wheel, 326: atomic_blaster,
           315: talisman_of_light, 318: final_purification, 316: amethyst_mandala, 403: corona_blaster,
           404: terra_destroyer}
