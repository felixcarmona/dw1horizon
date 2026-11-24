"""Finishers written and painted here for the Digimon that rush their target (keyed by species id). The attacker does
not leave its place in a battle, so each rush is shown as what it throws ahead of itself: a claw's wake, a rolling
shell, a diving shape of light. Written like finishers.py, with the same kit."""
import math

import numpy as np

from tools.technique_effects.finishers import CRIMSON, FIRE, GOLD, VIOLET, ahead, arc, band, column, fireball, \
    gather, puff, tongue
from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, crescent, fbm, glow, grid, iv, polar, ring, \
    segment, star

WOLF = ['#000000', '#102060', '#3070e0', '#90d0ff', '#ffffff']
VEE = ['#000000', '#081868', '#2060e0', '#80c8ff', '#ffffff']
WOOD = ['#2a1404', '#6a3810', '#a86828', '#d8a050', '#ffe8b0']
POW = ['#000000', '#803000', '#ffb020', '#fff0a0', '#ffffff']
PLATE = ['#3a2a08', '#806010', '#c89820', '#f0d050', '#fff8c0']
DUST = ['#000000', '#3a3020', '#807058', '#c8b898', '#f0e8d8']
STING = ['#000000', '#063010', '#18a030', '#90ff60', '#ffffff']
MAGENTA = ['#000000', '#400030', '#c01880', '#ff80d0', '#ffffff']
MACH = ['#000000', '#203860', '#70a8e0', '#d8f0ff', '#ffffff']
RUST = ['#000000', '#500808', '#d03018', '#ffa060', '#ffffff']
WATER = ['#000000', '#082050', '#1060c0', '#50c0f0', '#e0ffff']
STEEL = ['#181c28', '#384050', '#687890', '#b0c0d0', '#ffffff']
SHADE = ['#000000', '#404040', '#909090', '#d0d0d0', '#ffffff']
GHOST = ['#000000', '#181040', '#5038b0', '#a898ff', '#f0f0ff']
SNAIL = ['#40102a', '#802050', '#c04880', '#f090b8', '#ffe8f0']
SLIME = ['#000000', '#0c3008', '#40a020', '#a0f040', '#f0ffc0']
PAW = ['#000000', '#603010', '#f0a020', '#fff080', '#ffffff']
PINK = ['#000000', '#501030', '#e04890', '#ffa8d0', '#ffffff']
TEAL = ['#082028', '#105058', '#30a0a8', '#a0f0e8', '#ffffff']
SPARK = ['#000000', '#802000', '#ff8010', '#ffe060', '#ffffff']
IVORY = ['#40300c', '#806830', '#b8a060', '#f0e0a0', '#ffffff']
HOLY = ['#000000', '#604808', '#e0b030', '#fff0a0', '#ffffff']
SKY = ['#000000', '#103060', '#4090e0', '#b0e0ff', '#ffffff']
HORN = ['#000000', '#101c40', '#4060b0', '#a0c0f0', '#ffffff']
WHITE = (128, 128, 128)


# ----------------------------------------------------------------- paintings
def turned(turn):
    x, y = grid()
    c, s = math.cos(turn), math.sin(turn)
    return (x - 16) * c + (y - 16) * s, -(x - 16) * s + (y - 16) * c


def claws(turn, seed=3, n=3, gap=7.0, bow=4.0):
    """The wake of a paw: parallel bowed streaks, the middle one the longest."""
    u, v = turned(turn)
    lum = np.zeros((32, 32))
    for k in range(n):
        side = k - (n - 1) / 2
        reach = 15.5 - 2.5 * abs(side)
        line = v - side * gap - bow * (1 - (u / 15.0) ** 2) + bow / 2
        width = 2.5 * clip(1 - (np.abs(u) / reach) ** 2) ** 0.6
        lum = np.maximum(lum, clip(1.25 - np.abs(line) / np.maximum(width, 0.2)) * (np.abs(u) < reach))
    return clip(lum) * (0.8 + 0.3 * fbm(seed))


def streak(seed=7, half=9.0):
    """A speed line for a band: bright and wide at its head (the right), thinning to nothing behind."""
    x, y = grid()
    t = x / 32.0
    return clip(1 - np.abs(y - 16) / (half * (0.25 + 0.75 * t))) ** 1.2 * t ** 1.3 * (0.7 + 0.5 * fbm(seed))


def vee():
    """A letter V with a haze about it."""
    x, y = grid()
    d = np.abs((y - 26) + np.abs(x - 16) * 1.6)
    inside = (y > 3) & (np.abs(x - 16) < 14)
    return clip(clip(1.35 - d / 2.6) + 0.3 * clip(1 - d / 8.0)) * inside


def comet(seed):
    """For a band: a ragged head at the right and a tail that frays behind it."""
    x, y = grid()
    head = clip(1 - np.hypot(x - 24, y - 16) / (7 + 2 * fbm(seed))) ** 0.6
    tail = clip(1 - np.abs(y - 16) / (1.5 + 6.5 * x / 26)) * (x < 26) * (x / 26) ** 0.8 * (0.5 + 0.9 * fbm(seed + 3))
    return clip(np.maximum(head, tail))


def mallet():
    """A wooden mallet hanging head down: a banded barrel under its handle."""
    x, y = grid()
    head = (np.abs(x - 16) < 12) & (y > 15) & (y < 30)
    hoop = head & (np.abs(x - 16) > 8.5)
    grain = 0.5 + 0.14 * np.sin(y * 1.9) + 0.12 * (y < 19)
    handle = (np.abs(x - 16) < 1.9) & (y > 1) & (y <= 15)
    return np.where(hoop, 1.0, np.where(head, grain, np.where(handle, 0.8, 0.0)))


def knock():
    """The jagged star of a comic-book blow."""
    r, ang = polar()
    edge = 7.5 + 6.5 * np.abs(((ang * 9 / (2 * np.pi)) % 1.0) - 0.5) * 2
    return clip((edge - r) / 1.5) * (0.55 + 0.45 * clip(r / 9.0))


def plated_ball():
    """A curled-up body: a ball of overlapping plates, lit from above."""
    r, _ = polar()
    x, y = grid()
    body = clip((13.5 - r) / 1.5)
    plates = 0.42 + 0.4 * np.abs(np.cos(np.hypot(x - 16, y - 34) * 0.62))
    light = 0.25 * clip(1 - np.hypot(x - 12, y - 11) / 9.0)
    rim = 0.35 * clip(1 - np.abs(r - 12.5) / 1.3)
    return clip(body * (plates + light + rim) + 0.08 * body)


def needle(width=3.2):
    """For a band: a spike, thick at the wrist (the left), a point at the right."""
    x, y = grid()
    w = width * clip(1 - x / 31.5) ** 0.7 + 0.35
    return clip(1.3 - np.abs(y - 16) / w) * clip(x / 2.5)


def dart():
    """For a band: a swept-wing shape flying to the right."""
    x, y = grid()
    wing = clip(1.3 - np.abs(np.abs(y - 16) - (27 - x) * 0.62) / 2.2) * (x > 6) * (x < 28)
    body = clip(1.2 - np.abs(y - 16) / (2.6 * clip((x - 2) / 26.0) + 0.3)) * (x > 2) * (x < 30)
    return clip(np.maximum(wing, body))


def feather():
    u, v = turned(0.7)
    vane = clip(1.15 - (u / 13.5) ** 2 - (v / 4.2) ** 2)
    barbs = 0.6 + 0.4 * np.abs(np.cos(u * 1.5 - np.abs(v) * 0.9))
    return clip(vane * barbs + 0.6 * clip(1 - np.abs(v) / 0.9) * (np.abs(u) < 14.5))


def torpedo():
    """For a band: a hull with a round nose (the right), a porthole and tail fins."""
    x, y = grid()
    half = 5.6 * np.sqrt(clip(1 - (np.clip(x - 20, 0, None) / 9.5) ** 2))
    hull = (np.abs(y - 16) < half) & (x > 7) & (x < 29.5)
    fins = (x > 2) & (x <= 9) & (np.abs(y - 16) < 11 - (x - 2) * 0.9)
    shade = 0.5 + 0.42 * clip(1 - np.abs(y - 13.5) / 2.6)
    port = clip(1.2 - np.abs(np.hypot(x - 21.5, y - 16) - 2.2) / 1.0)
    return clip(np.where(hull, shade, np.where(fins, 0.3, 0.0)) + hull * port * 0.5)


def bubble():
    x, y = grid()
    return clip(ring(7.0, 1.3) + 0.8 * clip(1 - np.hypot(x - 13, y - 12.5) / 2.2))


def drop():
    """A drop falling: round below, a point above."""
    x, y = grid()
    ball = clip((6.0 - np.hypot(x - 16, y - 20)) / 1.5)
    tip = clip(1.2 - np.abs(x - 16) / np.maximum((y - 5) * 0.42, 0.2)) * (y > 5) * (y < 20)
    return clip(np.maximum(ball, tip) * (0.6 + 0.4 * clip(1 - np.hypot(x - 14, y - 18) / 5.0)))


def pincer_cut(turn):
    """A straight cut, a hair wide at its ends, with a haze along it."""
    u, v = turned(turn)
    width = 2.6 * clip(1 - (np.abs(u) / 15.5) ** 2) ** 0.8 + 0.15
    return clip(clip(1.3 - np.abs(v) / width) + 0.3 * clip(1 - np.abs(v) / 6.0)) * (np.abs(u) < 15.5)


def talon(turn):
    """A hooked claw."""
    r, _ = polar()
    return clip(crescent(12.5, 11.0, 4.5, turn) * (0.5 + 0.7 * clip((r - 7) / 5.0)))


def reaper(turn=0.5):
    """A scythe's blade: a wide crescent, its outer edge the brightest."""
    r, _ = polar()
    return clip(crescent(14.5, 13.0, 5.5, turn) * (0.35 + 0.9 * clip((r - 9.5) / 4.5)))


def spiral_shell():
    """A snail's shell seen from the side: a spiral groove, knobs on its rim."""
    r, ang = polar(16, 16.5)
    body = clip((11.5 - r) / 1.5)
    groove = 0.5 + 0.5 * np.cos(r * 1.3 - ang)
    knobs = clip(1 - np.abs(r - 12.5) / 2.2) * clip(np.cos(ang * 7) * 2 - 0.7)
    return clip(body * (0.4 + 0.55 * groove) + knobs + 0.08 * body)


def paw():
    """A cat's paw print: a pad and four toes."""
    x, y = grid()
    lum = clip((7.6 - np.hypot((x - 16) / 1.2, y - 21.5)) / 1.5)
    for cx, cy in ((6.5, 12), (12.5, 6.5), (19.5, 6.5), (25.5, 12)):
        lum = np.maximum(lum, clip((3.5 - np.hypot(x - cx, y - cy)) / 1.2))
    return clip(lum)


def saw():
    """A saw blade: eight hooked teeth round a disc with a hub."""
    r, ang = polar()
    teeth = 10.5 + 4.0 * ((ang * 8 / (2 * np.pi)) % 1.0)
    body = clip((teeth - r) / 1.2)
    swirl = 0.42 + 0.22 * np.cos(r * 0.9 - ang * 2)
    hub = clip(1 - np.abs(r - 3.5) / 1.3)
    edge = clip(1 - np.abs(r - teeth + 1.0) / 1.4)
    return clip(body * (swirl + 0.5 * hub) + 0.6 * edge * body + 0.08 * body)


def tusk():
    """For a band: a tusk that curves up to its point (the right), lit along its back."""
    x, y = grid()
    t = x / 31.5
    cy = 22 - 10 * t ** 1.8
    w = 5.2 * clip(1 - t) ** 0.75 + 0.4
    d = (y - cy) / w
    return clip(1.3 - np.abs(d)) * (0.55 + 0.45 * clip(0.6 - d)) * clip(x / 2.0)


def horn():
    """For a band: a straight ringed horn, its point at the right."""
    x, y = grid()
    w = 9.5 * clip(1 - x / 31.5) + 0.5
    return clip(1.3 - np.abs(y - 16) / w) * (0.7 + 0.3 * np.cos(x * 1.3)) * clip(x / 2.0)


def triangle():
    """The outline of a triangle, point up."""
    pts = [(16 + 13 * math.cos(a), 17 + 13 * math.sin(a)) for a in (-math.pi / 2, math.pi / 6, 5 * math.pi / 6)]
    lum = np.zeros((32, 32))
    for k in range(3):
        lum = np.maximum(lum, segment(*pts[k], *pts[(k + 1) % 3], 1.7))
    return clip(lum * 1.2)


def sword():
    """A sword held point up: blade, guard, grip."""
    x, y = grid()
    blade = clip(1.3 - np.abs(x - 16) / (2.6 * clip((y - 0.5) / 5.0) + 0.2)) * (y > 0.5) * (y < 22)
    fuller = 0.35 * clip(1 - np.abs(x - 16) / 0.8) * (y > 5) * (y < 21)
    guard = clip(1.3 - np.abs(y - 23) / 1.5) * (np.abs(x - 16) < 8.5)
    grip = clip(1.3 - np.abs(x - 16) / 1.4) * (y >= 24) * (y < 30.5)
    return clip(np.maximum(np.maximum(blade * 0.8 + fuller, guard), grip * 0.7))


def sweep():
    """One long cut seen whole: a shallow bow from side to side, razor-edged."""
    x, y = grid()
    bow = (y - 19) + 9.0 * (1 - ((x - 16) / 15.5) ** 2) - 4.5
    width = 3.0 * clip(1 - (np.abs(x - 16) / 15.5) ** 2) ** 0.6
    edge = clip(1.25 - np.abs(bow) / np.maximum(width, 0.2))
    wake = 0.4 * clip(1 - np.abs(bow - 4) / 5.0) * (bow > 0) * clip(1 - (np.abs(x - 16) / 14.0) ** 2)
    return clip(edge + wake) * (np.abs(x - 16) < 15.5)


def sliver():
    return segment(6, 26, 26, 6, 1.7)


def thread():
    x, y = grid()
    return clip(1 - np.abs(x - 16) / 1.3)


# ----------------------------------------------------------------- shared pieces
def to_target(fx, name):
    """Throw the flying instance `name` from just before the caster's chest at the target's chest."""
    fx.aim(); ahead(fx, fx.AT, fx.CHEST, 30); fx.vcopy(fx.DEST, fx.TCHEST); fx.call(name)


def wake(fx, out, steps):
    """In a flying instance: out = the point it passed `steps` ticks ago."""
    fx.vcopy(out, iv(FREE)); fx.vmul(out, -steps); fx.vadd(out, POS)


# ----------------------------------------------------------------- WereGarurumon
def wolf_claw():
    """Cold glints run to WereGarurumon's paws; a blue streak leaps at the target and two rakes of three claws tear
    down across it one after the other, shreds flying from each."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(WOLF)
    fx.paint(0, claws(0.95)); fx.paint(1, claws(-0.95, seed=6)); fx.paint(2, glow(15, 1.2)); fx.paint(3, streak(7))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, sliver())
    tint, cold = fx.colour(*WHITE), fx.colour(40, 80, 128)
    gather(fx, 'glint', 12, 4, (110, 128, 128), 90, 520, 5)
    fx.particle('rake1', 1, 7, 0, WHITE, None, grow=40, flat=((0, 0), (32, 32), (0, 0)), fade=True)
    fx.particle('rake2', 1, 9, 1, WHITE, None, grow=50, flat=((0, 0), (32, 32), (0, 0)), fade=True)
    fx.particle('chill', 2, 7, 2, (40, 80, 128), None, grow=25, fade=True)
    fx.particle('shred', 18, 10, 5, (120, 128, 128), (90, 170), grow=-8, speed=80, lift=15, gravity=7, spread=80,
                spin=25)
    fx.particle('fleck', 10, 8, 4, WHITE, (70, 120), grow=-8, spread=300)
    fx.label('main'); fx.when(0, 'howl'); fx.when(4, 'leap'); fx.when(11, 'second')
    fx.br(fx.NOW, '>', 3, 'main_end'); fx.emit('glint', fx.CHEST, 2)
    fx.label('main_end'); fx.end(13)
    fx.label('howl'); fx.sound(-55); fx.ret()
    fx.label('leap'); fx.sound(3); to_target(fx, 'dash'); fx.ret()
    fx.travel('dash', 1, 3, 'dash_render', 'first')
    fx.label('dash_render')
    wake(fx, fx.TV2, 2); band(fx, fx.TV2, POS, 120, cold, 3); band(fx, fx.TV2, POS, 55, tint, 3); fx.ret()
    fx.label('first')
    fx.sound(13); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 420)
    fx.vcopy(fx.AT, fx.TCHEST); fx.sub_(at(fx.AT, 1), 110); fx.emit('rake1')
    fx.emit('chill', fx.TCHEST); fx.emit('shred', times=6); fx.hit(); fx.ret()
    fx.label('second')
    fx.sound(16); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 500)
    fx.vcopy(fx.AT, fx.TCHEST); fx.sub_(at(fx.AT, 1), 130); fx.emit('rake2')
    fx.emit('chill', fx.TCHEST); fx.emit('shred', times=10); fx.emit('fleck', times=8); fx.ret()
    return fx


# ----------------------------------------------------------------- Veemon
def vee_head_butt():
    """A blue light swells on Veemon's brow and shoots head first at the target as a blunt comet; where it butts, a
    great white V flashes up with a second one behind it."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(VEE)
    fx.paint(0, vee()); fx.paint(1, glow(15, 1.2)); fx.paint(2, comet(5)); fx.paint(3, ring(13, 2.0))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, comet(12))
    tint, blue = fx.colour(*WHITE), fx.colour(50, 80, 128)
    brow = fx.vec()
    gather(fx, 'mote', 12, 4, (90, 110, 128), 80, 480, 5)
    fx.particle('lamp', 1, 6, 1, (90, 110, 128), 60, grow=40)
    fx.particle('after', 8, 6, 1, (40, 70, 128), 300, grow=-40, fade=True)
    fx.particle('vflash', 1, 10, 0, WHITE, None, grow=45, flat=((0, 0), (-22, -22), (0, 0)), fade=True)
    fx.particle('vecho', 1, 12, 0, (50, 90, 128), None, grow=85, flat=((0, 0), (-30, -30), (0, 0)), fade=True)
    fx.particle('bump', 2, 7, 3, (100, 120, 128), 120, grow=85, fade=True)
    fx.particle('daze', 14, 12, 4, WHITE, (80, 150), grow=-7, speed=60, lift=45, gravity=7, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(6, 'go')
    fx.br(fx.NOW, '>', 4, 'main_end'); fx.emit('mote', brow, 2)
    fx.label('main_end'); fx.end(7)
    fx.label('begin')
    fx.vcopy(brow, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), 9, 0, 10); fx.sub_(at(brow, 1), fx.T3)
    ahead(fx, brow, brow, 20); fx.emit('lamp', brow); fx.sound(-55); fx.ret()
    fx.label('go')
    fx.sound(3); fx.aim(); fx.vcopy(fx.AT, brow); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('butt'); fx.ret()
    fx.travel('butt', 1, 5, 'butt_render', 'butt_arrive', every='butt_trail')
    fx.label('butt_trail'); fx.emit('after', POS); fx.ret()
    fx.label('butt_render')
    wake(fx, fx.TV2, 3); band(fx, fx.TV2, POS, 280, blue, 2); band(fx, fx.TV2, POS, 170, tint, 5)
    fx.sprite(POS, blue, 300, cell=1); fx.ret()
    fx.label('butt_arrive')
    fx.sound(7); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 300)
    fx.emit('vflash', fx.TCHEST); fx.emit('vecho'); fx.emit('bump', times=2); fx.emit('daze', times=12)
    fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- Puppetmon
def puppet_pummel():
    """Three mallets come down on their strings over the target, left, right and middle, each one knocking a jagged
    star and splinters out of it; the last is the hardest."""
    fx = Fx(delay=8, cast_sound=0)
    wood, hot = fx.palette(WOOD), fx.palette(POW)
    fx.paint(0, mallet()); fx.paint(1, knock()); fx.paint(2, sliver()); fx.paint(3, ring(13, 2.0))
    fx.paint(4, thread()); fx.paint(5, star(4, 2, 9, 6))
    tint = fx.colour(*WHITE)
    off, blows = fx.var(), fx.var()
    fx.particle('pow', 3, 4, 1, WHITE, None, grow=60, clut=hot)
    fx.particle('chip', 18, 12, 2, WHITE, (90, 160), grow=-6, speed=70, lift=40, gravity=9, spread=60, spin=30,
                clut=wood, blend=None)
    fx.particle('thud', 3, 7, 3, (128, 110, 70), 150, grow=80, fade=True, sy=7, clut=hot)
    fx.particle('recoil', 3, 5, 0, WHITE, 400, flat=((0, 0), (-70, -70), (0, 0)), clut=wood, blend=None)
    fx.particle('stars', 10, 12, 5, WHITE, (90, 160), grow=-7, speed=65, lift=50, gravity=8, spread=60, clut=hot)
    fx.label('main'); fx.when(0, 'begin'); fx.when(2, 'left'); fx.when(7, 'right'); fx.when(12, 'middle'); fx.end(13)
    fx.label('begin'); fx.set(blows, 0); fx.sound(-55); fx.ret()
    fx.label('left'); fx.set(off, -150); fx.jmp('drop')
    fx.label('right'); fx.set(off, 150); fx.jmp('drop')
    fx.label('middle'); fx.set(off, 0)
    fx.label('drop')
    fx.sound(13); fx.aim(); fx.vcopy(fx.DEST, fx.TGT); fx.add(at(fx.DEST, 0), off); fx.add(at(fx.DEST, 2), off)
    fx.lin(fx.T, at(fx.TSIZE, 1), 1, 30); fx.sub_(at(fx.DEST, 1), fx.T)
    fx.vcopy(fx.AT, fx.DEST); fx.sub_(at(fx.AT, 1), 900); fx.call('hammer'); fx.ret()
    fx.travel('hammer', 3, 3, 'hammer_render', 'hammer_arrive')
    fx.label('hammer_render')
    fx.vcopy(fx.TV, POS); fx.sub_(at(fx.TV, 1), 900); fx.sprite(fx.TV, tint, 60, 1500, cell=4, clut=wood)
    fx.sprite(POS, tint, 420, cell=0, clut=wood, blend=None); fx.ret()
    fx.label('hammer_arrive')
    fx.sound(20); fx.add(blows, 1); fx.lin(fx.SZ, blows, 110, 330)
    fx.emit('recoil', POS); fx.add(at(fx.AT, 1), 170)
    fx.emit('pow'); fx.emit('thud'); fx.emit('chip', times=5)
    fx.br(blows, '<', 3, 'hammer_hit'); fx.sound(7); fx.emit('stars', times=10)
    fx.label('hammer_hit'); fx.aim(); fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- Armadillomon
def diamond_shell():
    """Armadillomon's curled, plated ball rolls along the ground at the target, kicking up dust and glinting, and
    bounces off it in a burst of grit. A target that moves away is missed."""
    fx = Fx(delay=8, cast_sound=0)
    plate, dust = fx.palette(PLATE), fx.palette(DUST)
    fx.paint(0, plated_ball()); fx.paint(1, puff(3)); fx.paint(2, puff(8)); fx.paint(3, star(4, 2, 10, 7))
    fx.paint(4, ring(13, 2.0)); fx.paint(5, clip(glow(7, 0.6) * (0.6 + 0.6 * fbm(4))))
    tint = fx.colour(*WHITE)
    low, roll = fx.vec(), fx.var()
    fx.particle('kick', 14, 9, 1, (128, 120, 105), (140, 220), grow=22, flat=((-10, 10), (-16, -4), (-10, 10)),
                spread=120, clut=dust, blend='half')
    fx.particle('glint', 8, 5, 3, WHITE, (110, 190), grow=-18, spread=220, clut=plate)
    fx.particle('grit', 16, 12, 5, WHITE, (50, 90), speed=55, lift=45, gravity=9, spread=80, clut=dust, blend=None)
    fx.particle('cloud', 8, 11, 2, (128, 120, 105), (220, 320), grow=26, speed=20, lift=6, spread=160, clut=dust,
                blend='half')
    fx.particle('bang', 2, 7, 4, (128, 120, 80), 140, grow=80, fade=True, clut=plate)
    fx.particle('rebound', 1, 10, 0, WHITE, 300, flat=((0, 0), (-75, -75), (0, 0)), gravity=11, spin=-40, clut=plate,
                blend=None)
    fx.label('main'); fx.when(0, 'begin'); fx.when(6, 'loose')
    fx.br(fx.NOW, '>', 5, 'main_end'); fx.emit('kick', fx.SRC)
    fx.label('main_end'); fx.end(7)
    fx.label('begin'); fx.call('curl'); fx.sound(-55); fx.ret()
    curl = fx.pool('curl', 1)
    fx.begin('curl', curl, 'curl_render', inherit=False)
    ahead(fx, POS, fx.SRC, 30); fx.sub_(at(POS, 1), 140); fx.ret()
    fx.label('curl_tick'); fx.life(5); fx.ret()
    fx.label('curl_render')
    fx.lin(fx.T3, FRAME, 56, 100); fx.lin(fx.T2, FRAME, 50)
    fx.sprite(POS, tint, fx.T3, cell=0, clut=plate, blend=None, rot=fx.T2); fx.ret()
    fx.label('loose')
    fx.sound(3); fx.aim(); ahead(fx, fx.AT, fx.SRC, 30); fx.sub_(at(fx.AT, 1), 140)
    fx.vcopy(fx.DEST, fx.TGT); fx.sub_(at(fx.DEST, 1), 140); fx.call('ball'); fx.ret()
    fx.shot('ball', 1, 75, 22, 'ball_render', 'ball_arrive', miss='ball_miss', every='ball_trail')
    fx.label('ball_trail')
    fx.vcopy(low, POS); fx.add(at(low, 1), 120); fx.emit('kick', low, 2); fx.emit('glint', POS); fx.ret()
    fx.label('ball_miss'); fx.emit('cloud', POS, 3); fx.ret()
    fx.label('ball_render')
    fx.lin(roll, FRAME, 55); fx.sprite(POS, tint, 390, cell=0, clut=plate, blend=None, rot=roll); fx.ret()
    fx.label('ball_arrive')
    fx.sound(7); fx.emit('rebound', POS); fx.emit('bang', times=2); fx.emit('glint', times=5)
    fx.emit('grit', times=14); fx.emit('cloud', times=6); fx.ret()
    return fx


# ----------------------------------------------------------------- Stingmon
def spiking_strike():
    """A pink point lights on Stingmon's wrist; two thin feints flick out, then the stinger itself shoots the whole
    way as a green spike, runs the target through and stays in it a moment while sparks fly out of its far side."""
    fx = Fx(delay=8, cast_sound=0)
    green, rose = fx.palette(STING), fx.palette(MAGENTA)
    fx.paint(0, needle(8.5)); fx.paint(1, needle(4.5)); fx.paint(2, star(4, 1.5, 13, 12)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, ring(12, 1.6)); fx.paint(5, sliver())
    tint, dim = fx.colour(*WHITE), fx.colour(50, 100, 50)
    wrist, tip, push = fx.vec(), fx.vec(), fx.vec()
    lift = fx.var()
    fx.particle('bud', 1, 7, 3, WHITE, 60, grow=30, clut=rose)
    fx.particle('prick', 12, 8, 2, WHITE, (140, 240), grow=-16, spread=200)
    fx.particle('fly', 16, 10, 5, (110, 128, 100), (90, 160), grow=-8, speed=35, gravity=3, spread=60, drift=push,
                spin=30)
    fx.particle('halo', 2, 8, 4, WHITE, 120, grow=75, fade=True, clut=rose)
    fx.particle('flash', 1, 5, 3, (60, 110, 60), 220, grow=45, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(2, 'feint_high'); fx.when(4, 'feint_low'); fx.when(6, 'thrust')
    fx.end(7)
    fx.label('begin'); ahead(fx, wrist, fx.CHEST, 30); fx.emit('bud', wrist); fx.sound(-55); fx.ret()
    fx.label('feint_high'); fx.set(lift, -130); fx.jmp('feint_go')
    fx.label('feint_low'); fx.set(lift, 130)
    fx.label('feint_go')
    fx.sound(34); fx.aim(); fx.vcopy(fx.AT, wrist); fx.vcopy(fx.DEST, fx.TCHEST); fx.vadd(fx.DEST, wrist)
    fx.vdiv(fx.DEST, 2); fx.add(at(fx.DEST, 1), lift); fx.call('feint'); fx.ret()
    fx.travel('feint', 2, 2, 'feint_render', 'noop')
    fx.label('feint_render'); band(fx, wrist, POS, 80, tint, 1); fx.ret()
    fx.label('thrust')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, wrist); fx.vcopy(fx.DEST, fx.TCHEST)
    fx.vcopy(push, fx.DEST); fx.vsub(push, fx.AT); fx.vdiv(push, 10)
    fx.vcopy(tip, push); fx.vmul(tip, 4); fx.vadd(tip, fx.DEST); fx.call('spike'); fx.ret()
    fx.travel('spike', 1, 3, 'spike_render', 'spike_arrive')
    fx.label('spike_render')
    band(fx, wrist, POS, 170, dim, 0); band(fx, wrist, POS, 100, tint, 0); fx.sprite(POS, tint, 260, cell=2); fx.ret()
    fx.label('spike_arrive')
    fx.sound(16); fx.call('pin'); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 300)
    fx.emit('flash', fx.TCHEST); fx.emit('halo', tip); fx.emit('prick', times=8); fx.emit('fly', times=16)
    fx.hit(); fx.ret()
    pin = fx.pool('pin', 1)
    fx.begin('pin', pin, 'pin_render', inherit=False); fx.vcopy(POS, tip); fx.ret()
    fx.label('pin_tick'); fx.life(6); fx.emit('prick', POS); fx.ret()
    fx.label('pin_render')
    fx.lin(fx.T3, FRAME, -22, 170); fx.lin(fx.T2, fx.T3, 58, 0, 100)
    band(fx, wrist, POS, fx.T3, dim, 0); band(fx, wrist, POS, fx.T2, tint, 0)
    fx.lin(fx.T3, FRAME, -30, 260); fx.sprite(POS, tint, fx.T3, cell=2); fx.ret()
    return fx


# ----------------------------------------------------------------- Aquilamon
def mach_impulse():
    """A light climbs from Aquilamon high into the air, turns and dives on the target as a white dart with a red
    heart, leaving a string of shock rings behind it in the sky; where it lands the air booms out in three rings."""
    fx = Fx(delay=8, cast_sound=0)
    air, red = fx.palette(MACH), fx.palette(RUST)
    fx.paint(0, dart()); fx.paint(1, ring(12, 1.8)); fx.paint(2, streak(9)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, feather()); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13.5, 1.2))
    tint, pale = fx.colour(*WHITE), fx.colour(70, 100, 128)
    high = fx.vec()
    fx.particle('plume', 10, 8, 3, (70, 100, 128), 220, grow=-24, fade=True)
    fx.particle('cone', 8, 9, 1, (110, 125, 128), 110, grow=55, fade=True)
    fx.particle('boom1', 1, 9, 6, WHITE, 160, grow=120, fade=True)
    fx.particle('boom2', 1, 10, 1, (100, 120, 128), 120, grow=85, fade=True)
    fx.particle('boom3', 1, 11, 1, (128, 80, 60), 80, grow=55, fade=True, clut=red)
    fx.particle('crack', 1, 5, 3, WHITE, None, grow=50, fade=True)
    fx.particle('quill', 14, 16, 4, (128, 110, 100), (130, 200), speed=40, lift=30, gravity=4, spread=80, spin=14,
                clut=red)
    fx.label('main'); fx.when(0, 'begin'); fx.when(1, 'climb_go'); fx.when(6, 'dive_go'); fx.end(7)
    fx.label('begin')
    fx.aim(); ahead(fx, high, fx.CHEST, -320); fx.sub_(at(high, 1), 380); fx.sound(-55); fx.ret()
    fx.label('climb_go'); fx.sound(34); fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, high); fx.call('climb'); fx.ret()
    fx.travel('climb', 1, 4, 'climb_render', 'noop', every='climb_trail')
    fx.label('climb_trail'); fx.emit('plume', POS); fx.ret()
    fx.label('climb_render'); fx.sprite(POS, pale, 320, cell=3); fx.sprite(POS, tint, 200, cell=5); fx.ret()
    fx.label('dive_go')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, high); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('dive'); fx.ret()
    fx.travel('dive', 1, 5, 'dive_render', 'dive_arrive', every='dive_trail')
    fx.label('dive_trail'); fx.emit('cone', POS); fx.emit('plume'); fx.ret()
    fx.label('dive_render')
    wake(fx, fx.TV2, 2); band(fx, fx.TV2, POS, 290, pale, 2); band(fx, fx.TV2, POS, 250, tint, 0)
    fx.sprite(POS, tint, 170, cell=3, clut=red); fx.ret()
    fx.label('dive_arrive')
    fx.sound(7); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 420)
    fx.emit('crack', fx.TCHEST); fx.emit('boom1'); fx.emit('boom2'); fx.emit('boom3'); fx.emit('quill', times=12)
    fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- Flamedramon
def fire_rocket():
    """Flames climb round Flamedramon until it stands wreathed in them, and the whole blaze leaves it as a lance of
    fire with two flames corkscrewing round it; it goes through the target and blows a cone of fire out of its far
    side. A target that moves away is missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(FIRE)
    fx.paint(0, comet(3)); fx.paint(1, comet(9)); fx.paint(2, tongue(5)); fx.paint(3, fireball(5))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, clip(ring(12.5, 2.4) * (0.5 + fbm(19))))
    tint, soft = fx.colour(*WHITE), fx.colour(128, 60, 24)
    push = fx.vec()
    fx.particle('wreath', 18, 8, 2, (128, 100, 50), (200, 300), grow=-12, flat=((-8, 8), (-50, -28), (-8, 8)),
                spread=340)
    fx.particle('exhaust', 12, 6, 3, (128, 90, 40), 260, grow=-34, fade=True)
    fx.particle('cinder', 16, 10, 5, (128, 100, 50), (50, 100), speed=16, gravity=3, spread=120, fade=True)
    fx.particle('jet', 16, 9, 2, (128, 110, 60), (200, 320), grow=-10, speed=28, spread=120, drift=push, rot=90)
    fx.particle('blaze', 2, 8, 3, WHITE, None, grow=60, fade=True)
    fx.particle('hoop', 1, 8, 6, (128, 80, 30), 160, grow=85, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(7, 'launch')
    fx.br(fx.NOW, '>', 6, 'main_end'); fx.emit('wreath', fx.CHEST, 3)
    fx.label('main_end'); fx.end(8)
    fx.label('begin'); fx.sound(-55); fx.ret()
    fx.label('launch')
    fx.sound(3); to_target(fx, 'rocket')
    fx.vcopy(push, fx.DEST); fx.vsub(push, fx.AT); fx.set(at(push, 1), 0); fx.vdiv(push, 11); fx.ret()
    fx.shot('rocket', 1, 90, 20, 'rocket_render', 'rocket_arrive', miss='rocket_miss', every='rocket_trail')
    fx.label('rocket_trail'); fx.emit('exhaust', POS); fx.emit('cinder', POS); fx.ret()
    fx.label('rocket_miss'); fx.emit('cinder', POS, 6); fx.ret()
    fx.label('rocket_render')
    wake(fx, fx.TV2, 5); band(fx, fx.TV2, POS, 310, soft, 1)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '==', 0, 'rocket_other')
    band(fx, fx.TV2, POS, 210, tint, 0); fx.jmp('rocket_twist')
    fx.label('rocket_other'); band(fx, fx.TV2, POS, 210, tint, 1)
    fx.label('rocket_twist')
    fx.lin(fx.T3, FRAME, 800); fx.sin(fx.T, fx.T3, 170)
    wake(fx, fx.TV2, 1); fx.vcopy(fx.TV, fx.TV2); fx.add(at(fx.TV, 1), fx.T); fx.sprite(fx.TV, tint, 190, cell=2)
    fx.vcopy(fx.TV, fx.TV2); fx.sub_(at(fx.TV, 1), fx.T); fx.sprite(fx.TV, tint, 190, cell=2); fx.ret()
    fx.label('rocket_arrive')
    fx.sound(7); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 380)
    fx.emit('blaze', POS); fx.emit('hoop'); fx.emit('jet', times=14); fx.emit('cinder', times=8); fx.ret()
    return fx


# ----------------------------------------------------------------- Submarimon
def submarine_attack():
    """Bubbles rise round Submarimon and a ring pings out of it; a steel torpedo runs at the target in a wake of foam
    and bubbles, and a column of spray and a rain of drops go up where it rams. A target that moves away is missed."""
    fx = Fx(delay=8, cast_sound=0)
    sea, hull = fx.palette(WATER), fx.palette(STEEL)
    fx.paint(0, torpedo()); fx.paint(1, bubble()); fx.paint(2, puff(4)); fx.paint(3, drop()); fx.paint(4, column(9))
    fx.paint(5, glow(15, 1.2)); fx.paint(6, ring(13, 1.6)); fx.paint(7, streak(11, 12.0))
    tint, deep = fx.colour(*WHITE), fx.colour(40, 90, 128)
    fx.particle('rise', 16, 10, 1, (100, 128, 128), (60, 120), flat=((-6, 6), (-34, -18), (-6, 6)), spread=320)
    fx.particle('ping', 2, 8, 6, (80, 120, 128), 100, grow=75, fade=True, sy=6)
    fx.particle('foam', 12, 8, 2, (90, 120, 128), (180, 260), grow=-18, lift=5, spread=60, fade=True)
    fx.particle('spout', 4, 9, 4, (60, 100, 128), (220, 300), grow=14, flat=((-8, 8), (-60, -40), (-8, 8)),
                gravity=8, spread=120, sy=34, fade=True)
    fx.particle('rain', 18, 14, 3, (120, 128, 128), (70, 120), flat=((-34, 34), (-95, -50), (-34, 34)), gravity=11,
                spread=100)
    fx.particle('swell', 2, 9, 6, (100, 128, 128), 180, grow=95, fade=True, sy=6)
    fx.particle('splash', 2, 6, 5, (90, 120, 128), None, grow=45, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(3, 'sonar'); fx.when(6, 'launch')
    fx.br(fx.NOW, '>', 5, 'main_end'); fx.emit('rise', fx.CHEST, 2)
    fx.label('main_end'); fx.end(7)
    fx.label('begin'); fx.sound(-55)
    fx.label('sonar'); fx.sound(34); fx.emit('ping', fx.CHEST); fx.ret()
    fx.label('launch'); fx.sound(3); to_target(fx, 'fish'); fx.ret()
    fx.shot('fish', 1, 75, 22, 'fish_render', 'fish_arrive', miss='fish_miss', every='fish_trail')
    fx.label('fish_trail'); fx.emit('foam', POS); fx.emit('rise', POS); fx.ret()
    fx.label('fish_miss'); fx.emit('foam', POS, 4); fx.ret()
    fx.label('fish_render')
    wake(fx, fx.TV2, 6); band(fx, fx.TV2, POS, 210, deep, 7)
    wake(fx, fx.TV2, 4); band(fx, fx.TV2, POS, 180, tint, 0, clut=hull, blend=None); fx.ret()
    fx.label('fish_arrive')
    fx.sound(7); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 380)
    fx.emit('splash', POS); fx.vcopy(fx.AT, fx.TGT); fx.sub_(at(fx.AT, 1), 60)
    fx.emit('swell'); fx.emit('foam', times=5); fx.emit('spout', times=4); fx.emit('rain', times=16); fx.ret()
    return fx


# ----------------------------------------------------------------- GranKuwagamon
def x_scissor_claw():
    """Two violet mandibles open wide on either side of the target and snap shut on it: one cut, then the cut that
    crosses it, and the X they leave stays black in the air before it bursts."""
    fx = Fx(delay=8, cast_sound=0)
    edge, dark = fx.palette(VIOLET), fx.palette(SHADE)
    fx.paint(0, pincer_cut(np.pi * 0.25)); fx.paint(1, pincer_cut(np.pi * 0.75)); fx.paint(2, talon(0.0))
    fx.paint(3, talon(np.pi)); fx.paint(4, glow(15, 1.2)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, sliver())
    tint, dim = fx.colour(*WHITE), fx.colour(128, 60, 128)
    side = fx.var()
    fx.particle('cut1', 1, 6, 0, WHITE, None, grow=45, fade=True)
    fx.particle('cut2', 1, 6, 1, WHITE, None, grow=45, fade=True)
    fx.particle('scar1', 1, 13, 0, WHITE, None, grow=8, clut=dark, blend='sub')
    fx.particle('scar2', 1, 10, 1, WHITE, None, grow=8, clut=dark, blend='sub')
    fx.particle('nip', 16, 10, 6, (120, 80, 128), (90, 160), grow=-8, speed=75, lift=10, gravity=5, spread=60,
                spin=30)
    fx.particle('burst', 2, 8, 4, (100, 40, 128), None, grow=50, fade=True)
    fx.particle('mote', 12, 11, 5, (128, 100, 128), (80, 140), grow=-7, speed=85, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(6, 'first'); fx.when(9, 'second'); fx.when(16, 'pop'); fx.end(17)
    fx.label('begin')
    fx.sound(-55); fx.aim(); fx.set(side, -520); fx.call('jaw_place'); fx.call('jaw_a')
    fx.set(side, 520); fx.call('jaw_place'); fx.call('jaw_b'); fx.ret()
    fx.label('jaw_place')
    fx.vcopy(fx.DEST, fx.TCHEST); fx.vcopy(fx.AT, fx.DEST); fx.add(at(fx.AT, 0), side); fx.add(at(fx.AT, 2), side)
    fx.ret()
    for name, cell in (('jaw_a', 2), ('jaw_b', 3)):
        fx.travel(name, 1, 6, name + '_render', 'noop')
        fx.label(name + '_render')
        fx.lin(fx.T3, FRAME, 40, 300); fx.sprite(POS, tint, fx.T3, cell=cell); fx.sprite(POS, dim, 380, cell=4)
        fx.ret()
    fx.label('first')
    fx.sound(13); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 520)
    fx.emit('cut1', fx.TCHEST); fx.emit('scar1'); fx.emit('nip', times=6); fx.hit(); fx.ret()
    fx.label('second')
    fx.sound(16); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 520)
    fx.emit('cut2', fx.TCHEST); fx.emit('scar2'); fx.emit('nip', times=10); fx.ret()
    fx.label('pop')
    fx.sound(7); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 360)
    fx.emit('burst', fx.TCHEST, 2); fx.emit('mote', times=12); fx.ret()
    return fx


# ----------------------------------------------------------------- Devidramon
def crimson_claw():
    """Four red eyes open over Devidramon; a red streak lunges at the target and three talons rake down through it
    side by side, each dragging a trail of red that hangs in the air after them."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(CRIMSON)
    fx.paint(0, talon(np.pi * 0.5)); fx.paint(1, clip(glow(13, 0.9) * (0.6 + 0.6 * fbm(8)))); fx.paint(2, glow(15, 1.2))
    fx.paint(3, star(2, 1.5, 12, 6)); fx.paint(4, streak(13)); fx.paint(5, sliver())
    tint, red = fx.colour(*WHITE), fx.colour(128, 30, 30)
    eyes, landed = fx.vec(), fx.var()
    fx.particle('eye', 4, 7, 3, (128, 60, 50), 80, grow=30)
    fx.particle('gash', 30, 10, 1, (128, 56, 44), 240, grow=-14, fade=True, sy=40)
    fx.particle('rend', 2, 6, 2, (90, 20, 16), None, grow=30, fade=True)
    fx.particle('spray', 18, 11, 5, (128, 70, 60), (90, 160), grow=-8, flat=((-45, 45), (10, 60), (-45, 45)),
                gravity=6, spread=120, spin=20)
    fx.label('main'); fx.when(0, 'begin'); fx.when(4, 'lunge'); fx.end(5)
    fx.label('begin')
    fx.sound(-55); fx.vcopy(eyes, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), 1, 60); fx.sub_(at(eyes, 1), fx.T3)
    for dx, dy in ((-70, 0), (70, 0), (-110, -70), (110, -70)):
        fx.vcopy(fx.AT, eyes); fx.add(at(fx.AT, 0), dx); fx.add(at(fx.AT, 2), dx); fx.add(at(fx.AT, 1), dy)
        fx.emit('eye')
    fx.ret()
    fx.label('lunge'); fx.sound(3); to_target(fx, 'dash'); fx.ret()
    fx.travel('dash', 1, 3, 'dash_render', 'rake')
    fx.label('dash_render')
    wake(fx, fx.TV2, 2); band(fx, fx.TV2, POS, 220, red, 4); fx.ret()
    fx.label('rake')
    fx.sound(13); fx.aim()
    for k in (-150, 0, 150):
        fx.vcopy(fx.AT, fx.TCHEST); fx.add(at(fx.AT, 0), k - 110); fx.add(at(fx.AT, 2), k - 110)
        fx.vcopy(fx.DEST, fx.AT); fx.add(at(fx.DEST, 0), 220); fx.add(at(fx.DEST, 2), 220)
        fx.lin(fx.T, at(fx.TSIZE, 1), 6, 120, 10); fx.sub_(at(fx.AT, 1), fx.T)
        fx.lin(fx.T, at(fx.TSIZE, 1), 3, 60, 10); fx.add(at(fx.DEST, 1), fx.T)
        fx.call('claw')
    fx.set(landed, 0); fx.ret()
    fx.travel('claw', 3, 5, 'claw_render', 'claw_arrive', every='claw_trail')
    fx.label('claw_trail'); fx.emit('gash', POS); fx.ret()
    fx.label('claw_render'); fx.sprite(POS, tint, 360, cell=0); fx.sprite(POS, red, 150, cell=2); fx.ret()
    fx.label('claw_arrive')
    fx.emit('spray', POS, 6); fx.add(landed, 1); fx.br(landed, '!=', 2, 'noop')
    fx.sound(16); fx.aim(); fx.set(fx.SZ, 260); fx.emit('rend', fx.TCHEST, 2); fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- Phantomon
def shadow_scythe():
    """Wisps of shadow draw in to Phantomon; a dark crescent, pale along its edge, spins from it to the target and
    reaps through it in one wide sweep, and pale wisps drift up from where it cut."""
    fx = Fx(delay=8, cast_sound=0)
    pale, dark = fx.palette(GHOST), fx.palette(SHADE)
    fx.paint(0, reaper()); fx.paint(1, puff(12)); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, sweep()); fx.paint(5, puff(27)); fx.paint(6, clip(crescent(14.5, 13.0, 5.5, 0.5)))
    tint, shade, mist = fx.colour(*WHITE), fx.colour(110, 110, 110), fx.colour(50, 40, 100)
    turn = fx.var()
    gather(fx, 'wisp', 12, 1, (60, 50, 110), 170, 620, 5)
    fx.particle('trail', 10, 7, 5, (50, 40, 100), 300, grow=-30, fade=True)
    fx.particle('reap', 2, 10, 4, WHITE, None, grow=95, fade=True, sy=16)
    fx.particle('void', 1, 6, 4, (60, 60, 60), None, grow=95, fade=True, sy=16, clut=dark, blend='sub')
    fx.particle('soul', 14, 16, 1, (90, 80, 128), (110, 190), grow=-6, flat=((-10, 10), (-34, -16), (-10, 10)),
                spread=260, fade=True)
    fx.particle('glint', 10, 9, 3, WHITE, (70, 130), grow=-8, speed=70, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(5, 'swing')
    fx.br(fx.NOW, '>', 4, 'main_end'); fx.emit('wisp', fx.CHEST, 2)
    fx.label('main_end'); fx.end(6)
    fx.label('begin'); fx.sound(-55); fx.ret()
    fx.label('swing'); fx.sound(13); to_target(fx, 'blade'); fx.ret()
    fx.travel('blade', 1, 6, 'blade_render', 'blade_arrive', every='blade_trail')
    fx.label('blade_trail'); fx.emit('trail', POS); fx.ret()
    fx.label('blade_render')
    fx.lin(turn, FRAME, -65)
    fx.sprite(POS, shade, 560, cell=6, clut=dark, blend='sub', rot=turn)
    fx.sprite(POS, tint, 520, cell=0, rot=turn); fx.sprite(POS, mist, 420, cell=2); fx.ret()
    fx.label('blade_arrive')
    fx.sound(16); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 360)
    fx.emit('void', fx.TCHEST); fx.emit('reap', times=2); fx.emit('glint', times=10); fx.emit('soul', times=12)
    fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- ShellNumemon
def shell_attack():
    """Slime bubbles up round ShellNumemon; its shell is lobbed high, spinning and dripping, and comes down flat on
    the target's head, squashes, and bounces off in a splash of green."""
    fx = Fx(delay=8, cast_sound=0)
    shell, slime = fx.palette(SNAIL), fx.palette(SLIME)
    fx.paint(0, spiral_shell()); fx.paint(1, drop()); fx.paint(2, puff(15)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, ring(13, 2.0)); fx.paint(5, clip(glow(9, 0.5) * (0.5 + 0.7 * fbm(6))))
    tint = fx.colour(*WHITE)
    spot, turn = fx.vec(), fx.var()
    fx.particle('ooze', 12, 9, 5, (110, 128, 100), (90, 160), grow=-8, flat=((-6, 6), (-30, -14), (-6, 6)),
                spread=300, clut=slime)
    fx.particle('drip', 12, 10, 1, (110, 128, 100), (70, 110), gravity=9, spread=60, clut=slime)
    fx.particle('squash', 1, 3, 0, WHITE, 480, grow=40, sy=8, clut=shell, blend=None)
    fx.particle('bounce', 1, 11, 0, WHITE, 340, flat=((0, 0), (-80, -80), (0, 0)), gravity=11, spin=35, clut=shell,
                blend=None)
    fx.particle('splat', 16, 13, 1, (120, 128, 110), (90, 150), flat=((-50, 50), (-80, -30), (-50, 50)), gravity=10,
                spread=100, clut=slime)
    fx.particle('glop', 6, 9, 2, (100, 128, 90), (200, 300), grow=20, speed=18, spread=160, fade=True, clut=slime)
    fx.particle('bonk', 8, 11, 3, WHITE, (90, 150), grow=-7, speed=60, lift=40, gravity=6, spread=60, clut=shell)
    fx.particle('slap', 2, 7, 4, (128, 110, 120), 150, grow=85, fade=True, sy=6, clut=shell)
    fx.label('main'); fx.when(0, 'begin'); fx.when(4, 'lob')
    fx.br(fx.NOW, '>', 3, 'main_end'); fx.emit('ooze', fx.CHEST, 3)
    fx.label('main_end'); fx.end(5)
    fx.label('begin'); fx.sound(-55); fx.ret()
    fx.label('lob')
    fx.sound(3); fx.aim(); fx.vcopy(fx.AT, fx.SRC); fx.sub_(at(fx.AT, 1), at(fx.SSIZE, 1))
    fx.vcopy(fx.DEST, fx.TGT); fx.sub_(at(fx.DEST, 1), at(fx.TSIZE, 1)); fx.call('shell'); fx.ret()
    fx.travel('shell', 1, 8, 'shell_render', 'shell_arrive', every='shell_trail')
    fx.label('shell_place')                 # spot = where the lobbed shell is drawn: over its straight flight
    fx.lin(fx.T3, FRAME, 256); fx.sin(fx.T, fx.T3, 380)
    fx.vcopy(spot, POS); fx.sub_(at(spot, 1), fx.T); fx.ret()
    fx.label('shell_trail'); fx.call('shell_place'); fx.emit('drip', spot); fx.ret()
    fx.label('shell_render')
    fx.call('shell_place'); fx.lin(turn, FRAME, 50)
    fx.sprite(spot, tint, 420, cell=0, clut=shell, blend=None, rot=turn); fx.ret()
    fx.label('shell_arrive')
    fx.sound(7); fx.emit('squash', POS); fx.emit('bounce'); fx.emit('slap', times=2); fx.emit('bonk', times=8)
    fx.emit('splat', times=14); fx.emit('glop', times=5); fx.aim(); fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- Gatomon
def lightning_paw():
    """Gold sparks crackle on Gatomon's paw; a bolt jumps the gap to the target and a great glowing paw print stamps
    itself on it, pink behind gold, in a shower of stars."""
    fx = Fx(delay=8, cast_sound=0)
    gold, pink = fx.palette(PAW), fx.palette(PINK)
    fx.paint(0, paw()); fx.paint(1, arc(5)); fx.paint(2, arc(8)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, ring(13, 1.8)); fx.paint(6, arc(14))
    tint, warm = fx.colour(*WHITE), fx.colour(128, 100, 50)
    fist = fx.vec()
    fx.particle('fizz', 8, 3, 1, (128, 120, 80), (240, 340), spread=260)
    fx.particle('fizz2', 8, 3, 2, (128, 120, 80), (240, 340), spread=260)
    fx.particle('lamp', 1, 6, 3, (128, 100, 60), 80, grow=35)
    fx.particle('print', 1, 8, 0, WHITE, None, grow=42, fade=True)
    fx.particle('blush', 1, 8, 0, (128, 100, 120), None, grow=95, fade=True, clut=pink)
    fx.particle('pop', 2, 7, 5, (128, 110, 120), 140, grow=85, fade=True, clut=pink)
    fx.particle('twinkle', 16, 13, 4, WHITE, (90, 170), grow=-8, speed=70, lift=30, gravity=4, spread=80)
    fx.particle('heart', 10, 12, 4, (128, 110, 128), (80, 140), grow=-7, speed=55, lift=45, gravity=3, spread=120,
                clut=pink)
    fx.label('main'); fx.when(0, 'begin'); fx.when(5, 'pounce')
    fx.br(fx.NOW, '>', 4, 'main_end'); fx.emit('fizz', fist); fx.emit('fizz2')
    fx.label('main_end'); fx.end(6)
    fx.label('begin'); ahead(fx, fist, fx.CHEST, 30); fx.emit('lamp', fist); fx.sound(-55); fx.ret()
    fx.label('pounce')
    fx.sound(3); fx.aim(); fx.vcopy(fx.AT, fist); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('bolt'); fx.ret()
    fx.travel('bolt', 1, 3, 'bolt_render', 'bolt_arrive')
    fx.label('bolt_render')
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '==', 0, 'bolt_other')
    band(fx, fist, POS, 300, tint, 1); fx.jmp('bolt_head')
    fx.label('bolt_other'); band(fx, fist, POS, 300, tint, 6)
    fx.label('bolt_head'); fx.sprite(POS, warm, 300, cell=3); fx.ret()
    fx.label('bolt_arrive')
    fx.sound(16); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 260)
    fx.emit('print', fx.TCHEST); fx.emit('blush'); fx.emit('pop', times=2); fx.emit('twinkle', times=14)
    fx.emit('heart', times=9); fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- Gizamon
def spiral_saw():
    """A toothed blade spins up in front of Gizamon, runs at the target throwing sparks behind it, bites into it and
    grinds there, spraying sparks, before the cut goes through."""
    fx = Fx(delay=8, cast_sound=0)
    steel, hot = fx.palette(TEAL), fx.palette(SPARK)
    fx.paint(0, saw()); fx.paint(1, clip(ring(11, 2.2) * (0.4 + 1.0 * fbm(17)))); fx.paint(2, star(4, 2, 9, 6))
    fx.paint(3, glow(15, 1.2)); fx.paint(4, sliver())
    tint, cool = fx.colour(*WHITE), fx.colour(40, 110, 110)
    turn, back = fx.var(), fx.vec()
    fx.particle('spark', 24, 9, 4, WHITE, (90, 160), grow=-9, speed=45, lift=40, gravity=8, spread=60, drift=back,
                spin=30, clut=hot)
    fx.particle('fleck', 12, 6, 2, WHITE, (70, 130), grow=-10, spread=240, clut=hot)
    fx.particle('whirl', 2, 8, 1, (100, 128, 128), None, grow=55, fade=True, spin=40)
    fx.particle('flash', 1, 5, 3, (128, 110, 70), None, grow=40, fade=True, clut=hot)
    fx.label('main'); fx.when(0, 'begin'); fx.when(6, 'loose'); fx.end(7)
    fx.label('begin'); fx.sound(-55); fx.vset(back, 0, 0, 0); fx.call('wind'); fx.ret()
    wind = fx.pool('wind', 1)
    fx.begin('wind', wind, 'wind_render', inherit=False); ahead(fx, POS, fx.CHEST, 30); fx.ret()
    fx.label('wind_tick'); fx.life(5); fx.emit('fleck', POS); fx.ret()
    fx.label('wind_render')
    fx.lin(fx.T3, FRAME, 65, 110); fx.lin(turn, FRAME, 70)
    fx.sprite(POS, tint, fx.T3, cell=0, clut=steel, blend=None, rot=turn); fx.ret()
    fx.label('loose')
    fx.sound(13); to_target(fx, 'blade')
    fx.vcopy(back, fx.AT); fx.vsub(back, fx.DEST); fx.set(at(back, 1), 0); fx.vdiv(back, 18); fx.ret()
    fx.travel('blade', 1, 5, 'blade_render', 'blade_arrive', every='blade_trail')
    fx.label('blade_trail'); fx.emit('spark', POS, 2); fx.ret()
    fx.label('blade_render')
    fx.lin(turn, FRAME, 80); fx.sprite(POS, cool, 560, cell=3)
    fx.sprite(POS, tint, 440, cell=0, clut=steel, blend=None, rot=turn); fx.ret()
    fx.label('blade_arrive'); fx.sound(20); fx.vcopy(fx.AT, POS); fx.call('grind'); fx.ret()
    grind = fx.pool('grind', 1)
    fx.begin('grind', grind, 'grind_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('grind_tick')
    fx.life(6); fx.emit('spark', POS, 3); fx.emit('fleck'); fx.after(3, 'grind_rasp'); fx.after(6, 'bite'); fx.ret()
    fx.label('grind_rasp'); fx.sound(20); fx.ret()
    fx.label('grind_render')
    fx.lin(turn, FRAME, 95, 40); fx.rnd(fx.T, -18, 18); fx.vcopy(fx.TV, POS); fx.add(at(fx.TV, 1), fx.T)
    fx.sprite(fx.TV, cool, 580, cell=3); fx.sprite(fx.TV, tint, 460, cell=0, clut=steel, blend=None, rot=turn)
    fx.ret()
    fx.label('bite')
    fx.sound(16); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 360)
    fx.emit('flash', fx.TCHEST); fx.emit('whirl', times=2); fx.emit('spark', times=10); fx.emit('fleck', times=6)
    fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- Tuskmon
def slamming_tusk():
    """Tuskmon paws the ground, and its charge goes out ahead of it as two great ivory tusks ploughing a bank of
    dust; they gore the target and toss upward, throwing stones and dust into the air."""
    fx = Fx(delay=8, cast_sound=0)
    bone, dust = fx.palette(IVORY), fx.palette(DUST)
    fx.paint(0, tusk()); fx.paint(1, puff(3)); fx.paint(2, puff(8)); fx.paint(3, knock()); fx.paint(4, glow(15, 1.2))
    fx.paint(5, clip(glow(7, 0.6) * (0.6 + 0.6 * fbm(4)))); fx.paint(6, ring(13, 2.0))
    tint = fx.colour(*WHITE)
    side, low, span = fx.vec(), fx.vec(), fx.var()
    fx.particle('paw', 12, 9, 1, (128, 120, 105), (150, 230), grow=22, flat=((-12, 12), (-18, -6), (-12, 12)),
                spread=160, clut=dust, blend='half')
    fx.particle('plough', 18, 8, 2, (100, 94, 82), (160, 220), grow=18, flat=((-10, 10), (-22, -8), (-10, 10)),
                spread=140, clut=dust, blend='half')
    fx.particle('toss', 2, 7, 0, WHITE, 520, flat=((0, 0), (-70, -70), (0, 0)), rot=-70, clut=bone, blend=None)
    fx.particle('thud', 1, 6, 3, (128, 120, 90), None, grow=50, fade=True, clut=bone)
    fx.particle('stone', 16, 14, 5, WHITE, (60, 110), flat=((-40, 40), (-100, -55), (-40, 40)), gravity=11,
                spread=120, clut=dust, blend=None)
    fx.particle('bank', 8, 12, 1, (128, 120, 105), (260, 360), grow=26, speed=20, lift=14, spread=200, clut=dust,
                blend='half')
    fx.particle('quake', 2, 8, 6, (128, 120, 100), 160, grow=90, fade=True, sy=6, clut=bone)
    fx.label('main'); fx.when(0, 'begin'); fx.when(6, 'charge')
    fx.br(fx.NOW, '>', 5, 'main_end'); fx.emit('paw', fx.SRC, 2)
    fx.label('main_end'); fx.end(7)
    fx.label('begin'); fx.sound(-55); fx.ret()
    fx.label('charge')
    fx.sound(3); to_target(fx, 'gore')
    fx.vcopy(side, fx.DEST); fx.vsub(side, fx.AT); fx.set(at(side, 1), 0)
    fx.vlen(span, side); fx.br(span, '>', 0, 'charge_ok'); fx.set(span, 1)
    fx.label('charge_ok')
    fx.set(fx.T, at(side, 0)); fx.lin(at(side, 0), at(side, 2), 140, 0, span); fx.lin(at(side, 2), fx.T, -140, 0, span)
    fx.ret()
    fx.travel('gore', 1, 6, 'gore_render', 'gore_arrive', every='gore_trail')
    fx.label('gore_trail')
    fx.vcopy(low, POS); fx.set(at(low, 1), at(fx.SRC, 1)); fx.sub_(at(low, 1), 60); fx.emit('plough', low, 2); fx.ret()
    fx.label('gore_render')
    for move in (fx.vadd, fx.vsub):
        wake(fx, fx.TV2, 4); fx.vcopy(fx.TV, POS); move(fx.TV, side); move(fx.TV2, side)
        band(fx, fx.TV2, fx.TV, 210, tint, 0, clut=bone, blend=None)
    fx.ret()
    fx.label('gore_arrive')
    fx.sound(7); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 360)
    fx.vcopy(fx.AT, fx.TCHEST); fx.vadd(fx.AT, side); fx.emit('toss'); fx.vcopy(fx.AT, fx.TCHEST)
    fx.vsub(fx.AT, side); fx.emit('toss'); fx.emit('thud', fx.TCHEST)
    fx.vcopy(fx.AT, fx.TGT); fx.sub_(at(fx.AT, 1), 60); fx.emit('quake', times=2); fx.emit('stone', times=14)
    fx.emit('bank', times=7); fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- Valkyrimon
def feral_sword():
    """A sword of light takes shape over Valkyrimon as glints run to it; it falls away into one cut that sweeps out
    to the target, widening as it goes, and passes through it as a single bright line; white feathers drift down
    after it."""
    fx = Fx(delay=8, cast_sound=0)
    holy, sky = fx.palette(HOLY), fx.palette(SKY)
    fx.paint(0, sword()); fx.paint(1, sweep()); fx.paint(2, feather()); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, star(2, 1.2, 14, 14)); fx.paint(6, ring(13, 1.6))
    tint, blue = fx.colour(*WHITE), fx.colour(60, 100, 128)
    over = fx.vec()
    gather(fx, 'glint', 14, 3, (128, 120, 90), 90, 620, 5)
    fx.particle('edge', 1, 7, 0, WHITE, 180, grow=42, sy=30)
    fx.particle('aura', 1, 7, 4, (50, 90, 128), 200, grow=60, clut=sky)
    fx.particle('gleam', 1, 8, 5, WHITE, None, grow=160, fade=True, sy=3)
    fx.particle('part', 2, 8, 6, (80, 110, 128), 140, grow=90, fade=True, sy=5, clut=sky)
    fx.particle('shine', 12, 9, 3, WHITE, (80, 150), grow=-9, speed=75, spread=100)
    fx.particle('plume', 14, 20, 2, (128, 128, 128), (130, 200), flat=((-22, 22), (-30, 6), (-22, 22)), gravity=2,
                spread=260, spin=9, clut=sky)
    fx.label('main'); fx.when(0, 'begin'); fx.when(7, 'swing')
    fx.br(fx.NOW, '>', 5, 'main_end'); fx.emit('glint', over, 2)
    fx.label('main_end'); fx.end(8)
    fx.label('begin')
    fx.vcopy(over, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), 1, 60); fx.sub_(at(over, 1), fx.T3)
    fx.emit('aura', over); fx.emit('edge'); fx.sound(-55); fx.ret()
    fx.label('swing'); fx.sound(13); to_target(fx, 'cut'); fx.ret()
    fx.travel('cut', 1, 4, 'cut_render', 'cut_arrive')
    fx.label('cut_render')
    fx.lin(fx.T3, FRAME, 150, 300); fx.lin(fx.T2, fx.T3, 5, 0, 10)
    fx.lin(fx.T, fx.T3, 13, 0, 10); fx.lin(fx.F1, fx.T2, 13, 0, 10)
    fx.sprite(POS, blue, fx.T, fx.F1, cell=1, clut=sky); fx.sprite(POS, tint, fx.T3, fx.T2, cell=1); fx.ret()
    fx.label('cut_arrive')
    fx.sound(16); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 500)
    fx.emit('gleam', fx.TCHEST); fx.emit('part', times=2); fx.emit('shine', times=10); fx.emit('plume', times=12)
    fx.hit(); fx.ret()
    return fx


# ----------------------------------------------------------------- Triceramon
def tri_horn_attack():
    """Three lights kindle at Triceramon's horns with a triangle drawn between them; three horns of blue steel fly
    from them and close on the target as one point, and a three-pointed star of gold breaks out where they meet."""
    fx = Fx(delay=8, cast_sound=0)
    blue, gold = fx.palette(HORN), fx.palette(GOLD)
    fx.paint(0, horn()); fx.paint(1, star(3, 3, 12, 4, turn=np.pi / 6)); fx.paint(2, glow(15, 1.2))
    fx.paint(3, triangle()); fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, ring(13, 1.8)); fx.paint(6, streak(15))
    tint, soft = fx.colour(*WHITE), fx.colour(50, 80, 128)
    brow, met = fx.vec(), fx.var()
    spots = ((0, -260), (-170, 40), (170, 40))
    fx.particle('lamp', 3, 7, 2, (90, 110, 128), 50, grow=30)
    fx.particle('frame', 1, 7, 3, (90, 110, 128), 200, grow=70)
    fx.particle('trail', 18, 5, 4, (100, 120, 128), (80, 130), grow=-16, spread=60)
    fx.particle('tristar', 1, 10, 1, WHITE, None, grow=70, fade=True, spin=8, clut=gold)
    fx.particle('delta', 2, 9, 3, (128, 110, 60), 160, grow=95, fade=True, clut=gold)
    fx.particle('dent', 3, 5, 2, WHITE, 200, grow=40, fade=True)
    fx.particle('shard', 16, 12, 4, WHITE, (90, 160), grow=-8, speed=80, lift=20, gravity=6, spread=60, clut=gold)
    fx.label('main'); fx.when(0, 'begin'); fx.when(7, 'charge'); fx.end(8)
    fx.label('place')                       # AT = the horn at (T2 sideways, T3 up) of the brow
    fx.vcopy(fx.AT, brow); fx.add(at(fx.AT, 0), fx.T2); fx.add(at(fx.AT, 2), fx.T2); fx.add(at(fx.AT, 1), fx.T3)
    fx.ret()
    fx.label('begin')
    fx.sound(-55); fx.set(met, 0); ahead(fx, brow, fx.CHEST, 30); fx.emit('frame', brow)
    for dx, dy in spots:
        fx.set(fx.T2, dx); fx.set(fx.T3, dy); fx.call('place'); fx.emit('lamp')
    fx.ret()
    fx.label('charge')
    fx.sound(3); fx.aim()
    for dx, dy in spots:
        fx.set(fx.T2, dx); fx.set(fx.T3, dy); fx.call('place'); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('spear')
    fx.ret()
    fx.travel('spear', 3, 4, 'spear_render', 'spear_arrive', every='spear_trail')
    fx.label('spear_trail'); fx.emit('trail', POS); fx.ret()
    fx.label('spear_render')
    wake(fx, fx.TV2, 4); band(fx, fx.TV2, POS, 230, soft, 6); band(fx, fx.TV2, POS, 170, tint, 0); fx.ret()
    fx.label('spear_arrive')
    fx.emit('dent', POS); fx.emit('shard', times=4); fx.add(met, 1); fx.br(met, '<', 3, 'noop')
    fx.sound(7); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 360)
    fx.emit('tristar', fx.TCHEST); fx.emit('delta', times=2); fx.emit('shard', times=4); fx.hit(); fx.ret()
    return fx


EFFECTS = {62: wolf_claw, 180: vee_head_butt, 181: puppet_pummel, 185: diamond_shell, 187: spiking_strike,
           188: mach_impulse, 195: fire_rocket, 202: submarine_attack, 210: x_scissor_claw, 216: crimson_claw,
           229: shadow_scythe, 231: shell_attack, 234: lightning_paw, 239: spiral_saw, 253: slamming_tusk,
           255: feral_sword, 257: tri_horn_attack}
