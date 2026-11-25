"""Finishers written and painted here for seventeen species whose finisher is a beam (keyed by species id): each
one's light comes from where its Digimon would fire it, and looks and lands as its name says."""
import math

import numpy as np

from tools.technique_effects.finishers import ahead, band, bar, column, fireball, gather, puff, tongue
from tools.technique_effects.kit import FRAME, POS, Fx, at, clip, fbm, glow, grid, polar, ring, segment, star

GREY = ['#000000', '#808080', '#ffffff']
INFERNO = ['#000000', '#200000', '#800008', '#e01010', '#ff7030', '#ffe0a0']
SONAR = ['#000000', '#082860', '#2080e0', '#80e0ff', '#ffffff']
EMBER = ['#000000', '#601000', '#e03000', '#ff8000', '#ffd040', '#ffffff']
SUN = ['#000000', '#803000', '#ff9000', '#ffe040', '#ffffc0', '#ffffff']
VOLT = ['#000000', '#28085a', '#8030e0', '#d090ff', '#ffffff']
NIGHT = ['#000000', '#100820', '#402070', '#9050d0', '#e0b0ff']
HADOU = ['#000000', '#701000', '#f04000', '#ffa020', '#fff0a0', '#ffffff']
ATOM = ['#000000', '#003838', '#00b0a0', '#70ffd0', '#ffffff']
BULB = ['#000000', '#504000', '#e0c020', '#ffff90', '#ffffff']
BONE = ['#000000', '#3a3000', '#a09020', '#f0e060', '#ffffd0', '#ffffff']
PHARAOH = ['#000000', '#403000', '#b08810', '#f8d040', '#fff8b0', '#ffffff']
TURQUOISE = ['#000000', '#004050', '#10b0b0', '#90fff0']
NECRO = ['#000000', '#300000', '#a00010', '#ff2020', '#ff9080', '#ffffff']
RAIDEN = ['#000000', '#604000', '#f0a000', '#ffe060', '#ffffff']
DYNAMO = ['#000000', '#083050', '#1890d0', '#70e0ff', '#ffffff']
MUZZLE = ['#000000', '#602000', '#f07000', '#ffd060', '#ffffff']
HELL = ['#000000', '#400030', '#c01060', '#ff5020', '#ffc040', '#ffffff']
WATER = ['#000000', '#062870', '#1870d0', '#60c8ff', '#e0ffff']
JEWEL = ['#000000', '#500030', '#e02080', '#ff90c0', '#ffffff']
EMERALD = ['#000000', '#004020', '#10c060', '#90ffb0', '#ffffff']


# ----------------------------------------------------------------- paintings
def torrent(seed):
    """A ragged stream: a band whose middle wanders and whose edge is torn."""
    x, y = grid()
    n = fbm(seed)
    return clip(1 - np.abs(y - 16 - 6 * (n - 0.5)) / (9 + 5 * fbm(seed + 3))) ** 0.8 * (0.6 + 0.6 * n)


def void_orb():
    """A ball with nothing inside: a bright skin and a small ember at its heart."""
    r, _ = polar()
    return clip(clip(1 - np.abs(r - 11.5) / 2.2) + (r < 11.5) * 0.14 * fbm(55) + 0.6 * clip(1 - r / 3.5))


def lance():
    """A spear of flame: broad where it leaves, a point where it ends."""
    x, y = grid()
    w = 12 * clip(1 - x / 31) ** 0.6 + 0.5
    return clip(1.15 - np.abs(y - 16) / w) * (0.7 + 0.4 * fbm(61))


def cone(seed):
    """A breath that opens as it goes: narrow at the mouth, wide and torn at the far end."""
    x, y = grid()
    w = 3 + 12 * (x / 32) ** 0.8
    return clip(1.1 - np.abs(y - 16) / w) ** 0.8 * (0.5 + 0.75 * fbm(seed)) * clip((32 - x) / 7)


def sun_disc():
    r, _ = polar()
    return clip((10 - r) / 1.5) * (0.7 + 0.4 * fbm(71))


def corona(turn):
    """Twelve short rays round a disc."""
    return star(12, 9, 6.5, 3, turn)


def thin(half=4.0):
    x, y = grid()
    return clip(1 - np.abs(y - 16) / half)


def zig(seed):
    """A bolt across the cell that turns sharply at every joint."""
    r = np.random.default_rng(seed)
    xs = np.linspace(0, 32, 7)
    ys = [16.0] + [16 + (1 if k % 2 else -1) * (5 + 7 * r.random()) for k in range(5)] + [16.0]
    lum = np.zeros((32, 32))
    for k in range(6):
        lum = np.maximum(lum, segment(xs[k], ys[k], xs[k + 1], ys[k + 1], 1.7))
    return lum


def bolt(seed):
    """A bolt from the top of the cell to its foot, with one fork."""
    r = np.random.default_rng(seed)
    ys = np.linspace(0, 32, 7)
    xs = [16.0] + [16 + (1 if k % 2 else -1) * (3 + 6 * r.random()) for k in range(5)] + [16.0]
    lum = np.zeros((32, 32))
    for k in range(6):
        lum = np.maximum(lum, segment(xs[k], ys[k], xs[k + 1], ys[k + 1], 2.0))
    side = 9 if seed % 2 else -9
    return np.maximum(lum, 0.8 * segment(xs[3], ys[3], xs[3] + side, ys[3] + 9, 1.3))


def block(seed):
    """Broken picture: a scatter of square blocks."""
    r = np.random.default_rng(seed)
    on = (r.random((8, 8)) > 0.62) * (0.5 + 0.5 * r.random((8, 8)))
    return np.kron(on, np.ones((4, 4)))


def slit():
    x, y = grid()
    return clip((1 - (np.abs(x - 16) / 3.2 + np.abs(y - 16) / 14.5)) * 3)


def fist():
    """A fist seen knuckles first: four knuckles over the folded fingers, the thumb across them."""
    x, y = grid()
    body = ((np.abs(x - 16) / 12.0) ** 4 + (np.abs(y - 18) / 9.5) ** 4) < 1
    lum = body * 0.55
    for cx in (7.0, 13.0, 19.0, 25.0):
        lum = np.maximum(lum, clip((4.2 - np.hypot(x - cx, y - 9.5)) / 1.5) * 0.95)
    for gx in (10.0, 16.0, 22.0):
        lum = lum * (1 - 0.7 * clip(1 - np.abs(x - gx) / 0.9) * (y > 7) * (y < 19))
    thumb = clip((1 - np.hypot((x - 13.5) / 8.5, (y - 22.5) / 3.4)) * 3)
    lum = lum * (1 - 0.6 * clip((1 - np.hypot((x - 13.5) / 9.5, (y - 22.0) / 4.4)) * 3) * (thumb < 0.2))
    return clip(np.maximum(lum, thumb * 0.9))


def rail():
    """A beam with a hard core and a soft sheath."""
    x, y = grid()
    d = np.abs(y - 16)
    return clip(np.where(d < 4, 1.0, 0.55 * clip(1 - (d - 4) / 9)))


def hexring():
    r, ang = polar()
    h = r * np.cos(((ang + np.pi / 6) % (np.pi / 3)) - np.pi / 6)
    return clip(1 - np.abs(h - 11) / 1.7)


def atom(turn):
    """Three orbits crossing over a nucleus."""
    x, y = grid()
    lum = clip((3.2 - np.hypot(x - 16, y - 16)) / 1.2)
    for k in range(3):
        a = turn + k * np.pi / 3
        u = (x - 16) * math.cos(a) + (y - 16) * math.sin(a)
        v = -(x - 16) * math.sin(a) + (y - 16) * math.cos(a)
        lum = np.maximum(lum, clip(1 - np.abs(np.hypot(u / 13.5, v / 4.6) - 1) * 4.5))
    return lum


def bulb(lit):
    """A glass bulb on its screw base, its filament cold or burning."""
    x, y = grid()
    r = np.hypot(x - 16, y - 12.5)
    glass = clip(1 - np.abs(r - 10) / 1.3) * (y < 20.5)
    neck = (np.abs(x - 16) < 4.5) & (y > 20.5) & (y < 29)
    base = neck * (0.45 + 0.4 * ((y.astype(int) % 3) == 0))
    wire = np.zeros((32, 32))
    pts = [(12, 20), (12, 13), (14, 9), (16, 13), (18, 9), (20, 13), (20, 20)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        wire = np.maximum(wire, segment(x0, y0, x1, y1, 1.2))
    inner = (r < 9.5) * clip(1 - r / 11) * (0.9 if lit else 0.0)
    return clip(np.maximum(glass * (1.0 if lit else 0.6), base) + wire * (1.0 if lit else 0.4) + inner)


def spoke():
    """A ray of a flash: bright and broad at its root, gone at its tip."""
    x, y = grid()
    w = 5 * clip(1 - x / 32) + 0.6
    return clip(1 - np.abs(y - 16) / w) * clip(1.1 - x / 31)


def skull():
    x, y = grid()
    cranium = clip((10.5 - np.hypot(x - 16, (y - 12.5) * 1.05)) / 1.3)
    jaw = ((np.abs(x - 16) < 5.5) & (y > 19) & (y < 27.5)) * 1.0
    lum = np.maximum(cranium, jaw) * 0.85
    for cx in (11.5, 20.5):
        lum = lum * (1 - clip((3.4 - np.hypot(x - cx, y - 13.5)) / 1.0))
    lum = lum * (1 - clip((1.8 - np.hypot((x - 16) * 1.3, y - 18.5)) / 0.8))
    for tx in (13.0, 16.0, 19.0):
        lum = lum * (1 - 0.8 * clip(1 - np.abs(x - tx) / 0.7) * (y > 22.5) * (y < 27.5))
    return clip(lum)


def ankh():
    x, y = grid()
    loop = clip(1 - np.abs(np.hypot((x - 16) / 4.6, (y - 8.5) / 6.0) - 1) * 3.2)
    return clip(np.maximum(np.maximum(loop, segment(16, 15, 16, 29.5, 1.9)), segment(8.5, 17.5, 23.5, 17.5, 1.9)))


def eyeball(open_):
    """An eye between its lids, open by that share: a veined white, a round iris, a slit pupil."""
    x, y = grid()
    h = np.maximum(0.9, open_ * 11.5) * np.sqrt(clip(1 - ((x - 16) / 14.5) ** 2))
    inside = clip((h - np.abs(y - 16)) / 1.2)
    rim = clip(1 - np.abs(h - np.abs(y - 16)) / 1.4) * (np.abs(x - 16) < 14.5)
    r = np.hypot(x - 16, y - 16)
    iris = clip((7.5 - r) / 1.2) * (0.55 + 0.45 * clip(r / 7.5))
    pupil = clip(1.6 - (np.abs(x - 16) / 1.6 + np.abs(y - 16) / 6.5) * 1.2)
    white = 0.32 + 0.25 * fbm(91)
    return clip(inside * np.maximum(white, iris) * (1 - 0.9 * clip(pupil)) + rim)


def soul():
    """A wisp: a round head and a tail that thins out below it."""
    x, y = grid()
    w = np.where(y < 11, np.sqrt(clip(36 - (y - 11) ** 2)), 6 * clip(1 - (y - 11) / 20) ** 1.3)
    cx = 16 + 2.5 * np.sin(y / 4.0) * clip((y - 11) / 20)
    eyes = clip((1.6 - np.hypot(x - 13.5, y - 10)) / 0.8) + clip((1.6 - np.hypot(x - 18.5, y - 10)) / 0.8)
    return clip(clip(1.2 - np.abs(x - cx) / np.maximum(w, 0.3)) * (y > 5) * (0.5 + 0.5 * clip(1 - (y - 5) / 26))
                * (1 - 0.8 * clip(eyes)))


def shell():
    """A cannon's bolt: a hot core in a broken ring."""
    r, ang = polar()
    return clip(clip(1 - r / 6.5) ** 0.5 + ring(10.5, 1.8) * (np.cos(ang * 4) > -0.3))


def rotor():
    """A dynamo's rotor: a toothed wheel with spokes."""
    r, ang = polar()
    edge = 10.5 + 3.0 * (np.cos(ang * 8) > 0)
    wheel = (r < edge) * (r > 7.0) * 0.85
    spokes = clip(1 - np.abs(np.sin(ang * 2)) * r / 1.6) * (r < 8) * 0.8
    return clip(wheel + spokes + clip((3.2 - r) / 1.2))


def blob():
    """A ball of water: a clear body, a bright rim and a highlight."""
    r, _ = polar()
    x, y = grid()
    return clip(clip((10 - r) / 2) * (0.32 + 0.2 * (1 - r / 10)) + 0.75 * clip(1 - np.hypot(x - 12.5, y - 12) / 3.5)
                + 0.55 * ring(10, 1.3))


def spout(seed):
    """A standing column of water with slanted streaks running up it."""
    x, y = grid()
    w = 9.5 + 2.0 * np.sin(y / 3.0)
    streak = 0.6 + 0.4 * np.sin(x * 1.3 + y * 0.9)
    return clip(1 - np.abs(x - 16) / w) ** 0.6 * streak * clip(y / 5) * (0.75 + 0.35 * fbm(seed))


def drop():
    x, y = grid()
    w = np.where(y < 20, 6 * clip((y - 6) / 14), np.sqrt(clip(36 - (y - 20) ** 2)))
    return clip(1.2 - np.abs(x - 16) / np.maximum(w, 0.3)) * (y > 6) * (0.6 + 0.4 * (x < 16))


def cat_eye():
    """A cat's eye: an almond with a bright rim and a slit down its middle."""
    x, y = grid()
    h = 8.5 * np.sqrt(clip(1 - ((x - 16) / 14.5) ** 2))
    almond = clip((h - np.abs(y - 16)) / 1.5)
    pupil = clip(1 - np.abs(x - 16) / 1.9) * (np.abs(y - 16) < h)
    rim = clip(1 - np.abs(h - np.abs(y - 16)) / 1.3) * (np.abs(x - 16) < 14.5)
    return clip(almond * 0.7 * (1 - 0.95 * pupil) + rim * 0.6)


def gem():
    x, y = grid()
    d = np.abs(x - 16) / 7.0 + np.abs(y - 16) / 10.5
    return clip((1 - d) * 2.5) * (0.6 + 0.4 * (x < 16)) + 0.4 * clip(1 - np.abs(1 - d) * 5) * (d < 1.1)


# ----------------------------------------------------------------- shared pieces
def env(fx, v, life, peak, rise=2, fall=4, flick=0, clock=FRAME):
    """v = a size that swells to `peak` in `rise` ticks, holds (throbbing by `flick`) and shrinks to nothing over the
    last `fall` ticks of `life`."""
    mid, down, done = fx.label(), fx.label(), fx.label()
    fx.br(clock, '>=', rise, mid); fx.lin(v, clock, peak, peak // 3, rise); fx.jmp(done)
    fx.label(mid); fx.br(clock, '>=', life - fall, down)
    fx.set(v, clock); fx.mod(v, 2); fx.mul(v, flick); fx.add(v, peak); fx.jmp(done)
    fx.label(down); fx.lin(v, clock, -peak, peak * life // fall + 6, fall)
    fx.label(done)


def along(fx, out, a, b, num, den):
    """out = the point num/den of the way from a to b."""
    fx.vcopy(out, b); fx.vsub(out, a); fx.vmul(out, num); fx.vdiv(out, den); fx.vadd(out, a)


def above(fx, out, base, size, tenths):
    """out = base lifted by that many tenths of a fighter's height."""
    fx.vcopy(out, base); fx.lin(fx.T, at(size, 1), tenths, 0, 10); fx.sub_(at(out, 1), fx.T)


def sideways(fx, side, amount):
    """side = the ground vector across the line from the caster to the target, `amount` long."""
    ok = fx.label()
    fx.vcopy(fx.TV, fx.TGT); fx.vsub(fx.TV, fx.SRC); fx.set(at(fx.TV, 1), 0)
    fx.vlen(fx.T, fx.TV); fx.br(fx.T, '>', 0, ok); fx.set(fx.T, 1)
    fx.label(ok)
    fx.lin(at(side, 0), at(fx.TV, 2), amount, 0, fx.T); fx.set(at(side, 1), 0)
    fx.lin(at(side, 2), at(fx.TV, 0), -amount, 0, fx.T)


def holder(fx, name, life, render, tick=None):
    """Define the routine `name`: an instance that stands at AT for `life` ticks, drawn by the label `render`; tick: a
    label called every tick of its life."""
    pool = fx.pool(name, 1)
    fx.begin(name, pool, render, inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label(name + '_tick'); fx.life(life)
    if tick:
        fx.call(tick)
    fx.ret()
    return pool


def alt(fx, clock, every, first, second):
    """Run first() and second() by turns, swapping every few ticks of the clock."""
    other, done = fx.label(), fx.label()
    fx.set(fx.T2, clock); fx.mod(fx.T2, 2 * every); fx.br(fx.T2, '>=', every, other)
    first(); fx.jmp(done)
    fx.label(other); second()
    fx.label(done)


# ----------------------------------------------------------------- Diaboromon
def inferno_missile():
    """A hollow red ball with a black heart swells on Diaboromon's chest as sparks fall into it, then tears open into
    a ragged red torrent with a black core that holds on the target, bursts on it and leaves soot hanging."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(INFERNO); fx.palette(GREY)
    fx.paint(0, torrent(51)); fx.paint(1, glow(15, 1.2)); fx.paint(2, void_orb()); fx.paint(3, ring(13, 2.0))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, puff(53)); fx.paint(6, torrent(57))
    red, white, dark = fx.colour(128, 44, 30), fx.colour(128, 128, 128), fx.colour(120, 120, 120)
    muzzle, w = fx.vec(), fx.var()
    charge, life = 9, 11
    gather(fx, 'mote', 14, 4, (128, 50, 40), 90, 560, 5)
    fx.particle('flare', 1, 8, 1, (128, 60, 40), None, grow=70, fade=True)
    fx.particle('shock', 3, 8, 3, (128, 50, 40), 140, grow=95, fade=True)
    fx.particle('cinder', 18, 13, 4, (128, 70, 40), (60, 120), grow=-6, speed=85, lift=30, gravity=7, spread=80)
    fx.particle('soot', 10, 14, 5, (90, 90, 90), (180, 260), grow=16, lift=14, spread=140, clut=1, blend='sub',
                fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose'); fx.when(charge + 2, 'smite')
    fx.when(charge + 6, 'echo')
    fx.br(fx.NOW, '>', charge - 3, 'main_end'); fx.emit('mote', muzzle, 2)
    fx.label('main_end'); fx.end(charge + life)
    fx.label('begin'); ahead(fx, muzzle, fx.CHEST, 60); fx.vcopy(fx.AT, muzzle); fx.call('orb'); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(13); fx.vcopy(fx.AT, muzzle); fx.call('blast'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 320, 10)
    fx.emit('flare', fx.TCHEST); fx.emit('shock'); fx.emit('cinder', times=12); fx.emit('soot', times=4); fx.ret()
    fx.label('echo'); fx.sound(16); fx.aim(); fx.emit('shock', fx.TCHEST); fx.emit('soot', times=4); fx.ret()
    holder(fx, 'orb', charge + life - 2, 'orb_render')
    fx.label('orb_render')
    env(fx, w, charge + life - 2, 320, rise=charge, fall=4, flick=30)
    fx.lin(fx.T3, w, 16, 0, 10); fx.sprite(POS, red, fx.T3, cell=1)
    fx.sprite(POS, dark, w, cell=1, clut=1, blend='sub')
    fx.sprite(POS, white, w, cell=2); fx.ret()
    holder(fx, 'blast', life, 'blast_render', tick='aim')
    fx.label('blast_render')
    env(fx, w, life, 200, rise=2, fall=4, flick=40)
    alt(fx, FRAME, 1, lambda: band(fx, muzzle, fx.TCHEST, w, red, 0), lambda: band(fx, muzzle, fx.TCHEST, w, red, 6))
    fx.lin(fx.T3, w, 1, 0, 2); band(fx, muzzle, fx.TCHEST, fx.T3, dark, 0, clut=1, blend='sub')
    fx.lin(fx.T3, w, 2); fx.sprite(fx.TCHEST, red, fx.T3, cell=1); fx.ret()
    return fx


# ----------------------------------------------------------------- Dolphmon
def pulse_blast():
    """Dolphmon's head sends out six rings of sound, one after another; each swells as it swims to the target and
    breaks on it in ripples and spray. The first to arrive lands the blow."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(SONAR)
    fx.paint(0, ring(12, 1.6)); fx.paint(1, clip(ring(12.5, 1.2) + 0.7 * ring(8, 1.0))); fx.paint(2, glow(15, 1.2))
    fx.paint(3, star(4, 2, 9, 6))
    tint, soft = fx.colour(128, 128, 128), fx.colour(40, 80, 128)
    head, first = fx.vec(), fx.var()
    fx.particle('ping', 6, 6, 0, (128, 128, 128), 60, grow=45, fade=True)
    fx.particle('ripple', 8, 8, 1, (128, 128, 128), 160, grow=85, fade=True)
    fx.particle('fizz', 18, 9, 3, (128, 128, 128), (60, 120), grow=-6, speed=70, spread=260)
    fx.travel('pulse', 6, 6, 'pulse_render', 'pulse_hit')
    fx.label('main'); fx.when(0, 'begin')
    for t in (2, 4, 6, 8, 10, 12):
        fx.when(t, 'send')
    fx.end(13)
    fx.label('begin')
    above(fx, head, fx.SRC, fx.SSIZE, 9); ahead(fx, head, head, 30); fx.set(first, 0); fx.sound(-55); fx.ret()
    fx.label('send')
    fx.sound(40); fx.aim(); fx.vcopy(fx.AT, head); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('pulse')
    fx.emit('ping', head); fx.ret()
    fx.label('pulse_render')
    fx.lin(fx.T3, FRAME, 60, 120); fx.sprite(POS, tint, fx.T3, cell=0)
    fx.lin(fx.T3, fx.T3, 7, 0, 10); fx.sprite(POS, soft, fx.T3, cell=2); fx.ret()
    fx.label('pulse_hit')
    fx.emit('ripple', POS); fx.emit('fizz', times=3)
    fx.br(first, '!=', 0, 'pulse_more'); fx.set(first, 1)
    fx.aim(); fx.hit(); fx.sound(15); fx.emit('ripple', fx.TCHEST); fx.ret()
    fx.label('pulse_more'); fx.sound(34); fx.ret()
    return fx


# ----------------------------------------------------------------- Shadramon
def flare_buster():
    """Fire gathers into a ball on Shadramon's horn; the ball stretches into a spear of flame that runs through the
    target and past it, leaving a row of flames standing on the ground it crossed, and the target goes up in a burst."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(EMBER)
    fx.paint(0, lance()); fx.paint(1, tongue(63)); fx.paint(2, fireball(64)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, fireball(66))
    hot, tint = fx.colour(128, 128, 128), fx.colour(128, 70, 30)
    horn, tip, past, w = fx.vec(), fx.vec(), fx.vec(), fx.var()
    charge, life = 8, 10
    gather(fx, 'mote', 12, 4, (128, 100, 60), 80, 520, 5)
    fx.particle('flame', 18, 12, 1, (128, 128, 128), (220, 340), grow=-10, lift=12, spread=90, fade=True)
    fx.particle('burst', 2, 9, 2, (128, 128, 128), None, grow=75, fade=True)
    fx.particle('ember', 16, 14, 4, (128, 100, 60), (50, 110), grow=-4, speed=60, lift=45, gravity=5, spread=120)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose'); fx.when(charge + 3, 'smite')
    fx.br(fx.NOW, '>', charge - 3, 'main_end'); fx.emit('mote', horn, 2)
    fx.label('main_end'); fx.end(charge + 4)
    fx.label('begin')
    above(fx, horn, fx.SRC, fx.SSIZE, 10); ahead(fx, horn, horn, 20)
    fx.vcopy(fx.AT, horn); fx.call('seed'); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.sound(13); fx.aim(); along(fx, past, horn, fx.TCHEST, 13, 10); fx.vcopy(fx.AT, horn); fx.call('spear'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 300, 10)
    fx.emit('burst', fx.TCHEST); fx.emit('ember', times=12); fx.ret()
    holder(fx, 'seed', charge + 2, 'seed_render')
    fx.label('seed_render')
    fx.lin(fx.T3, FRAME, 36, 90)
    alt(fx, FRAME, 2, lambda: fx.sprite(POS, hot, fx.T3, cell=2), lambda: fx.sprite(POS, hot, fx.T3, cell=5))
    fx.lin(fx.T3, fx.T3, 15, 0, 10); fx.sprite(POS, tint, fx.T3, cell=3); fx.ret()
    holder(fx, 'spear', life, 'spear_render', tick='spear_step')
    fx.label('spear_step')                  # a flame is left on the ground under the spear
    fx.rnd(fx.T3, 2, 12); along(fx, fx.TV2, fx.SRC, fx.TGT, fx.T3, 10); fx.sub_(at(fx.TV2, 1), 120)
    fx.emit('flame', fx.TV2, 2); fx.ret()
    fx.label('spear_render')
    reach = fx.label()
    fx.lin(fx.T3, FRAME, 1, 1); fx.br(fx.T3, '<', 4, reach); fx.set(fx.T3, 4)
    fx.label(reach); along(fx, tip, horn, past, fx.T3, 4)
    env(fx, w, life, 160, rise=2, fall=4, flick=36)
    band(fx, horn, tip, w, tint, 0); fx.lin(fx.T3, w, 1, 0, 2); band(fx, horn, tip, fx.T3, hot, 0)
    fx.lin(fx.T3, w, 2); fx.sprite(horn, tint, fx.T3, cell=3); fx.ret()
    return fx


# ----------------------------------------------------------------- Solarmon
def solar_flare():
    """Solarmon's face becomes a small sun, its corona flickering wider and wider, until it flashes: the whole field
    whites out for a moment and a fan of rays leaves it, the middle one burning the target under a rising heat."""
    fx = Fx(delay=8, cast_sound=2, draw=True)
    fx.palette(SUN)
    fx.paint(0, corona(0.0)); fx.paint(1, corona(np.pi / 12)); fx.paint(2, sun_disc()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, thin()); fx.paint(5, star(4, 2.5, 13, 10)); fx.paint(6, ring(13, 2.0))
    tint, warm, wash = fx.colour(128, 128, 128), fx.colour(128, 90, 40), fx.vec()
    sun, w, size = fx.vec(), fx.var(), fx.var()
    rays = [fx.vec() for _ in range(5)]
    charge, life = 10, 8
    fx.particle('flare', 1, 9, 5, (128, 128, 128), None, grow=80, fade=True)
    fx.particle('halo', 2, 9, 6, (128, 110, 60), 160, grow=95, fade=True)
    fx.particle('heat', 14, 13, 3, (128, 100, 50), (80, 150), grow=-6, spread=300,
                flat=((-10, 10), (-45, -20), (-10, 10)))
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'flash'); fx.when(charge + 1, 'smite')
    fx.end(charge + life + 2)
    fx.label('draw')
    fx.br(fx.NOW, '<', charge, 'noop'); fx.br(fx.NOW, '>', charge + 6, 'noop')
    fx.lin(fx.T, fx.NOW, -30, 30 * (charge + 7)); fx.lin(fx.T2, fx.T, 6, 0, 10); fx.vset(wash, fx.T, fx.T, fx.T2)
    fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin'); fx.vcopy(sun, fx.CHEST); fx.vcopy(fx.AT, sun); fx.call('orb'); fx.sound(-55); fx.ret()
    fx.label('flash')
    fx.sound(13); fx.aim()
    for k, off in enumerate(((0, 0, 0), (0, -420, 0), (0, 300, 0), (380, -160, 380), (-380, -160, -380))):
        fx.vcopy(fx.TV, fx.TCHEST)
        for j in range(3):
            if off[j]:
                fx.add(at(fx.TV, j), off[j])
        along(fx, rays[k], sun, fx.TV, 3 if k else 1, 2 if k else 1)
    fx.vcopy(fx.AT, sun); fx.call('fan'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 14, 340, 10)
    fx.emit('flare', fx.TCHEST); fx.emit('halo'); fx.emit('heat', times=12); fx.ret()
    holder(fx, 'orb', charge + life, 'orb_render')
    fx.label('orb_render')
    env(fx, size, charge + life, 400, rise=charge, fall=3, flick=40)
    fx.lin(fx.T3, size, 22, 0, 10)
    alt(fx, FRAME, 1, lambda: fx.sprite(POS, warm, fx.T3, cell=0), lambda: fx.sprite(POS, warm, fx.T3, cell=1))
    fx.sprite(POS, tint, size, cell=2); fx.lin(fx.T3, size, 2); fx.sprite(POS, warm, fx.T3, cell=3); fx.ret()
    holder(fx, 'fan', life, 'fan_render')
    fx.label('fan_render')
    env(fx, w, life, 70, rise=1, fall=4, flick=24)
    for k in range(1, 5):
        band(fx, sun, rays[k], w, warm, 4)
    fx.lin(fx.T3, w, 3); band(fx, sun, rays[0], fx.T3, warm, 4); band(fx, sun, rays[0], w, tint, 4); fx.ret()
    return fx


# ----------------------------------------------------------------- VioletElecmon
def jamming_thunder():
    """Violet current crawls over VioletElecmon, then a bolt jumps to the target in three crooked legs that never
    stand still; where it lands the air breaks up into blocks of static for a while."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(VOLT)
    fx.paint(0, zig(1)); fx.paint(1, zig(2)); fx.paint(2, zig(3)); fx.paint(3, glow(15, 1.2)); fx.paint(4, block(4))
    fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, block(9))
    tint, edge = fx.colour(128, 128, 128), fx.colour(100, 50, 128)
    src, m1, m2, w = fx.vec(), fx.vec(), fx.vec(), fx.var()
    charge, life = 7, 9
    fx.particle('crackle', 8, 3, 0, (128, 128, 128), (180, 280), spread=380)
    fx.particle('crackle2', 8, 3, 1, (128, 128, 128), (180, 280), spread=380)
    fx.particle('jam', 12, 3, 4, (128, 128, 128), (120, 230), spread=440)
    fx.particle('jam2', 12, 3, 6, (128, 90, 128), (120, 230), spread=440)
    fx.particle('spark', 14, 11, 5, (128, 110, 128), (60, 120), grow=-6, speed=80, lift=20, gravity=7, spread=60)
    fx.particle('flash', 1, 6, 3, (128, 100, 128), None, grow=60, fade=True)
    fx.label('main'); fx.when(0, 'hum'); fx.when(charge, 'loose'); fx.when(charge + 1, 'smite')
    fx.br(fx.NOW, '>=', charge, 'main_jam'); fx.emit('crackle', fx.CHEST); fx.emit('crackle2'); fx.jmp('main_end')
    fx.label('main_jam'); fx.br(fx.NOW, '<', charge + 1, 'main_end')
    fx.aim(); fx.emit('jam', fx.TCHEST); fx.emit('jam2')
    fx.label('main_end'); fx.end(charge + 14)
    fx.label('hum'); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.sound(13); ahead(fx, src, fx.CHEST, 30); fx.call('bolt_step'); fx.vcopy(fx.AT, src); fx.call('bolt'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 10, 260, 10)
    fx.emit('flash', fx.TCHEST); fx.emit('spark', times=12); fx.ret()
    holder(fx, 'bolt', life, 'bolt_render', tick='bolt_step')
    fx.label('bolt_step')                   # the two joints of the bolt jump every tick
    fx.aim()
    along(fx, m1, src, fx.TCHEST, 1, 3); fx.scatter(m1, 320)
    along(fx, m2, src, fx.TCHEST, 2, 3); fx.scatter(m2, 320); fx.ret()
    fx.label('bolt_render')
    env(fx, w, life, 90, rise=1, fall=3, flick=30)
    fx.lin(fx.T3, w, 22, 0, 10)
    for a, b, cell in ((src, m1, 0), (m1, m2, 1), (m2, fx.TCHEST, 2)):
        band(fx, a, b, fx.T3, edge, cell); band(fx, a, b, w, tint, cell)
    fx.lin(fx.T3, w, 3)
    for p in (src, m1, m2, fx.TCHEST):
        fx.sprite(p, edge, fx.T3, cell=3)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Vilemon
def nightmare_shock():
    """The field darkens as Vilemon's eye narrows to a slit of light; a writhing rope of shadow crawls from it to the
    target, rings of dusk close in on the victim one after another, and the last one snaps shut in a burst."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(NIGHT); fx.palette(GREY)
    fx.paint(0, slit()); fx.paint(1, glow(15, 1.2)); fx.paint(2, ring(13, 1.8)); fx.paint(3, puff(81))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, puff(83))
    tint, violet, dark, wash = fx.colour(128, 128, 128), fx.colour(90, 50, 128), fx.colour(120, 120, 120), fx.vec()
    eye, p, k, reach, w = fx.vec(), fx.vec(), fx.var(), fx.var(), fx.var()
    charge, life = 6, 13
    fx.particle('glint', 1, charge, 0, (128, 128, 128), 60, grow=40, sy=44)
    fx.particle('close', 3, 8, 2, (110, 60, 128), 780, grow=-88)
    fx.particle('pop', 1, 8, 1, (110, 70, 128), None, grow=70, fade=True)
    fx.particle('shred', 16, 13, 4, (110, 80, 128), (60, 120), grow=-5, speed=70, lift=10, gravity=6, spread=80)
    fx.particle('gloom', 8, 12, 5, (100, 100, 100), (200, 300), grow=12, lift=8, spread=200, clut=1, blend='sub',
                fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose')
    fx.when(charge + 4, 'grip'); fx.when(charge + 6, 'smite'); fx.when(charge + 8, 'grip'); fx.when(charge + 11, 'snap')
    fx.end(charge + life + 1)
    fx.label('draw')
    fx.lin(fx.T, fx.NOW, 10); fx.br(fx.NOW, '<', 4, 'draw_on'); fx.set(fx.T, 40)
    fx.br(fx.NOW, '<', 15, 'draw_on'); fx.lin(fx.T, fx.NOW, -8, 160)
    fx.label('draw_on'); fx.vset(wash, fx.T, fx.T, fx.T); fx.overlay(wash, blend='sub'); fx.ret()
    fx.label('begin')
    above(fx, eye, fx.SRC, fx.SSIZE, 8); ahead(fx, eye, eye, 20); fx.emit('glint', eye); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(13); fx.vcopy(fx.AT, eye); fx.call('rope'); fx.ret()
    fx.label('grip'); fx.sound(34); fx.aim(); fx.emit('close', fx.TCHEST); fx.ret()
    fx.label('smite')
    fx.sound(20); fx.aim(); fx.hit(); fx.emit('close', fx.TCHEST); fx.emit('gloom', times=4)
    fx.emit('shred', times=6); fx.ret()
    fx.label('snap')
    fx.sound(15); fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 320, 10)
    fx.emit('pop', fx.TCHEST); fx.emit('shred', times=10); fx.emit('gloom', times=4); fx.ret()
    holder(fx, 'rope', life, 'rope_render', tick='aim')
    fx.label('rope_render')
    env(fx, w, life, 200, rise=1, fall=3, flick=24)
    fx.lin(reach, FRAME, 2, 1); fx.set(k, 1)
    fx.label('rope_loop'); fx.br(k, '>', reach, 'rope_end')
    along(fx, p, eye, fx.TCHEST, k, 9)
    fx.lin(fx.T3, FRAME, 420); fx.lin(fx.T2, k, 640); fx.add(fx.T3, fx.T2); fx.sin(fx.T, fx.T3, 90)
    fx.add(at(p, 1), fx.T)
    fx.lin(fx.T3, w, 16, 0, 10); fx.sprite(p, dark, fx.T3, cell=3, clut=1, blend='sub')
    fx.sprite(p, violet, w, cell=1)
    fx.add(k, 1); fx.br(k, '<=', 8, 'rope_loop')
    fx.label('rope_end')
    fx.sprite(eye, tint, 130, 360, cell=0); fx.lin(fx.T3, w, 14, 0, 10); fx.sprite(eye, violet, fx.T3, cell=1)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Marsmon
def mugen_hadou():
    """Flames climb round Marsmon as he draws back; his punch leaves his arm as a burning fist that grows as it flies,
    trailing fire, and lands with a star of impact. A flurry of smaller fists hammers the same spot after it."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(HADOU)
    fx.paint(0, fist()); fx.paint(1, glow(15, 1.2)); fx.paint(2, tongue(101)); fx.paint(3, star(8, 3, 14, 8))
    fx.paint(4, ring(13, 2.2)); fx.paint(5, star(4, 2, 9, 6))
    tint, warm = fx.colour(128, 128, 128), fx.colour(128, 80, 40)
    hand, p, size = fx.vec(), fx.vec(), fx.var()
    charge, flight = 7, 6
    fx.particle('aura', 14, 9, 2, (128, 128, 128), (180, 280), grow=-8, lift=40, spread=260, fade=True)
    fx.particle('trail', 12, 7, 2, (128, 110, 90), (160, 240), grow=-14, lift=14, spread=70, fade=True)
    fx.particle('impact', 1, 8, 3, (128, 128, 128), None, grow=85, fade=True)
    fx.particle('shock', 2, 8, 4, (128, 100, 60), 180, grow=95, fade=True)
    fx.particle('jab', 8, 4, 0, (128, 128, 128), (200, 300), grow=26, spread=330)
    fx.particle('ember', 16, 13, 5, (128, 100, 60), (60, 120), grow=-5, speed=85, lift=30, gravity=7, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose'); fx.when(charge + flight, 'smite')
    for t in (2, 4, 6, 8):
        fx.when(charge + flight + t, 'flurry')
    fx.br(fx.NOW, '>=', charge, 'main_fly'); fx.emit('aura', fx.SRC, 2); fx.jmp('main_end')
    fx.label('main_fly'); fx.br(fx.NOW, '>', charge + flight, 'main_end')
    fx.aim(); fx.set(fx.T3, fx.NOW); fx.sub_(fx.T3, charge); along(fx, p, hand, fx.TCHEST, fx.T3, flight)
    fx.emit('trail', p, 2)
    fx.label('main_end'); fx.end(charge + flight + 10)
    fx.label('begin'); ahead(fx, hand, fx.CHEST, 80); fx.vcopy(p, hand); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(13); fx.vcopy(fx.AT, hand); fx.call('punch'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 320, 10)
    fx.emit('impact', fx.TCHEST); fx.emit('shock'); fx.emit('ember', times=10); fx.ret()
    fx.label('flurry')
    fx.sound(16); fx.aim(); fx.emit('jab', fx.TCHEST, 2); fx.emit('ember', times=2); fx.ret()
    holder(fx, 'punch', flight + 1, 'punch_render')
    fx.label('punch_render')
    fx.lin(size, FRAME, 60, 240)
    fx.lin(fx.T3, size, 18, 0, 10); fx.sprite(p, warm, fx.T3, cell=1)
    fx.sprite(p, tint, size, cell=0); fx.ret()
    return fx


# ----------------------------------------------------------------- HiAndromon
def atomic_ray():
    """An atom lights up on HiAndromon's chest, its orbits turning faster; a hair-thin line finds the target, then the
    full ray follows it: a hard green-white beam with six-sided collars running down its length, ending in a cross of
    light on the target."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(ATOM)
    fx.paint(0, rail()); fx.paint(1, atom(0.0)); fx.paint(2, atom(np.pi / 6)); fx.paint(3, hexring())
    fx.paint(4, glow(15, 1.2)); fx.paint(5, star(4, 2.5, 14, 10)); fx.paint(6, thin(2.5)); fx.paint(7, star(4, 2, 9, 6))
    tint, soft = fx.colour(128, 128, 128), fx.colour(50, 128, 110)
    core, p, w, k = fx.vec(), fx.vec(), fx.var(), fx.var()
    charge, life = 9, 12
    fx.particle('cross', 1, 10, 5, (128, 128, 128), None, grow=70, fade=True)
    fx.particle('collar', 3, 8, 3, (128, 128, 128), 160, grow=80, fade=True)
    fx.particle('bit', 18, 12, 7, (128, 128, 128), (60, 120), grow=-6, speed=90, lift=10, gravity=5, spread=70)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose'); fx.when(charge + 2, 'smite')
    fx.when(charge + 6, 'echo'); fx.end(charge + life)
    fx.label('begin'); ahead(fx, core, fx.CHEST, 50); fx.vcopy(fx.AT, core); fx.call('emblem'); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(13); fx.vcopy(fx.AT, core); fx.call('ray'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 13, 330, 10)
    fx.emit('cross', fx.TCHEST); fx.emit('collar'); fx.emit('bit', times=12); fx.ret()
    fx.label('echo'); fx.sound(34); fx.aim(); fx.emit('collar', fx.TCHEST); fx.emit('bit', times=6); fx.ret()
    holder(fx, 'emblem', charge + life - 1, 'emblem_render', tick='aim')
    fx.label('emblem_render')
    env(fx, w, charge + life - 1, 330, rise=charge, fall=3, flick=20)
    alt(fx, FRAME, 1, lambda: fx.sprite(POS, tint, w, cell=1), lambda: fx.sprite(POS, tint, w, cell=2))
    fx.lin(fx.T3, w, 15, 0, 10); fx.sprite(POS, soft, fx.T3, cell=4)
    fx.br(FRAME, '<', 4, 'noop'); fx.br(FRAME, '>=', charge, 'noop')
    band(fx, core, fx.TCHEST, 16, tint, 6); fx.ret()
    holder(fx, 'ray', life, 'ray_render', tick='aim')
    fx.label('ray_render')
    env(fx, w, life, 130, rise=2, fall=4, flick=20)
    fx.lin(fx.T3, w, 2); band(fx, core, fx.TCHEST, fx.T3, soft, 0); band(fx, core, fx.TCHEST, w, tint, 0)
    fx.set(k, 0)
    fx.label('ray_loop')
    fx.lin(fx.T3, k, 3); fx.add(fx.T3, FRAME); fx.add(fx.T3, FRAME); fx.mod(fx.T3, 12); fx.add(fx.T3, 1)
    along(fx, p, core, fx.TCHEST, fx.T3, 13)
    fx.lin(fx.T3, w, 28, 0, 10); fx.sprite(p, tint, fx.T3, cell=3)
    fx.add(k, 1); fx.br(k, '<', 4, 'ray_loop')
    fx.lin(fx.T3, w, 3); fx.sprite(fx.TCHEST, soft, fx.T3, cell=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Bulbmon
def bulb_flash():
    """A glass bulb hangs over Bulbmon, its filament stuttering on and off; then it catches, and the field goes white
    as spokes of glare shoot out of it in every direction and one broad shaft pins the target, left blinking in a
    swarm of after-images."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(BULB)
    fx.paint(0, bulb(False)); fx.paint(1, bulb(True)); fx.paint(2, spoke()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, bar()); fx.paint(5, star(4, 2, 12, 8)); fx.paint(6, ring(13, 2.0))
    tint, soft, wash = fx.colour(128, 128, 128), fx.colour(128, 120, 60), fx.vec()
    lamp, w, lit = fx.vec(), fx.var(), fx.var()
    tips = [fx.vec() for _ in range(8)]
    charge, life = 10, 9
    fx.particle('dazzle', 18, 5, 5, (128, 128, 128), (140, 260), grow=-20, spread=420)
    fx.particle('pop', 2, 8, 6, (128, 128, 100), 150, grow=90, fade=True)
    fx.particle('blind', 1, 9, 3, (128, 128, 110), None, grow=70, fade=True)
    fx.label('main'); fx.when(0, 'begin')
    for t, name in ((2, 'on'), (3, 'off'), (5, 'on'), (6, 'off'), (8, 'on'), (charge, 'flash'), (charge + 1, 'smite')):
        fx.when(t, name)
    fx.br(fx.NOW, '<=', charge + 1, 'main_end'); fx.aim(); fx.emit('dazzle', fx.TCHEST, 2)
    fx.label('main_end'); fx.end(charge + life + 3)
    fx.label('draw')
    fx.br(fx.NOW, '<', charge, 'noop'); fx.br(fx.NOW, '>', charge + 5, 'noop')
    fx.lin(fx.T, fx.NOW, -34, 34 * (charge + 6)); fx.lin(fx.T2, fx.T, 8, 0, 10); fx.vset(wash, fx.T, fx.T, fx.T2)
    fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    above(fx, lamp, fx.SRC, fx.SSIZE, 10); fx.set(lit, 0)
    for k, deg in enumerate((20, -20, 55, -55, 160, 200, 125, 235)):
        fx.vcopy(tips[k], lamp)
        fx.add(at(tips[k], 2), int(620 * math.cos(math.radians(deg))))
        fx.add(at(tips[k], 1), int(-620 * math.sin(math.radians(deg))))
    fx.vcopy(fx.AT, lamp); fx.call('glass'); fx.ret()
    fx.label('on'); fx.set(lit, 1); fx.sound(34); fx.ret()
    fx.label('off'); fx.set(lit, 0); fx.ret()
    fx.label('flash'); fx.set(lit, 1); fx.sound(13); fx.vcopy(fx.AT, lamp); fx.call('glare'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 13, 330, 10)
    fx.emit('blind', fx.TCHEST); fx.emit('pop'); fx.ret()
    holder(fx, 'glass', charge + life, 'glass_render')
    fx.label('glass_render')
    fx.br(lit, '!=', 0, 'glass_lit'); fx.sprite(POS, soft, 380, cell=0); fx.ret()
    fx.label('glass_lit'); fx.sprite(POS, tint, 380, cell=1); fx.sprite(POS, soft, 760, cell=3); fx.ret()
    holder(fx, 'glare', life, 'glare_render', tick='aim')
    fx.label('glare_render')
    env(fx, w, life, 110, rise=1, fall=4, flick=40)
    for k in range(8):
        band(fx, lamp, tips[k], w, soft, 2)
    fx.lin(fx.T3, w, 2); band(fx, lamp, fx.TCHEST, fx.T3, soft, 4); band(fx, lamp, fx.TCHEST, w, tint, 4)
    fx.ret()
    return fx


# ----------------------------------------------------------------- SkullSatamon
def nail_bone():
    """The stone on SkullSatamon's staff fills with a sick yellow light, high over his head; the beam it throws is
    wrapped in black lightning, and where it rests a pale skull lifts out of the target and drifts up among splinters
    of bone."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(BONE); fx.palette(GREY)
    fx.paint(0, rail()); fx.paint(1, zig(11)); fx.paint(2, zig(12)); fx.paint(3, glow(15, 1.2)); fx.paint(4, skull())
    fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.0)); fx.paint(7, star(4, 2.5, 12, 5))
    tint, sick, dark = fx.colour(128, 128, 128), fx.colour(120, 128, 40), fx.colour(128, 128, 128)
    stone, w = fx.vec(), fx.var()
    charge, life = 9, 12
    gather(fx, 'mote', 12, 5, (128, 128, 70), 90, 560, 5)
    fx.particle('ghost', 2, 15, 4, (128, 128, 128), 300, grow=14, lift=34, fade=True)
    fx.particle('ring', 2, 8, 6, (128, 128, 60), 150, grow=90, fade=True)
    fx.particle('shard', 16, 14, 7, (128, 128, 128), (120, 200), grow=-4, speed=85, lift=40, gravity=8, spread=70,
                spin=260)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose'); fx.when(charge + 2, 'smite')
    fx.when(charge + 7, 'rise')
    fx.br(fx.NOW, '>', charge - 3, 'main_end'); fx.emit('mote', stone, 2)
    fx.label('main_end'); fx.end(charge + life)
    fx.label('begin')
    above(fx, stone, fx.SRC, fx.SSIZE, 10); ahead(fx, stone, stone, 90)
    fx.vcopy(fx.AT, stone); fx.call('gem'); fx.sound(-55); fx.ret()
    fx.label('loose'); fx.sound(13); fx.vcopy(fx.AT, stone); fx.call('beam'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.emit('ring', fx.TCHEST); fx.emit('shard', times=10)
    fx.emit('ghost'); fx.ret()
    fx.label('rise'); fx.sound(20); fx.aim(); fx.emit('ghost', fx.TCHEST); fx.emit('shard', times=6); fx.ret()
    holder(fx, 'gem', charge + life - 1, 'gem_render')
    fx.label('gem_render')
    env(fx, w, charge + life - 1, 240, rise=charge, fall=3, flick=40)
    fx.sprite(POS, tint, w, cell=3); fx.lin(fx.T3, w, 2); fx.sprite(POS, sick, fx.T3, cell=3)
    fx.lin(fx.T3, w, 16, 0, 10); fx.sprite(POS, sick, fx.T3, cell=6); fx.ret()
    holder(fx, 'beam', life, 'beam_render', tick='aim')
    fx.label('beam_render')
    env(fx, w, life, 110, rise=2, fall=4, flick=20)
    fx.lin(fx.T3, w, 2); band(fx, stone, fx.TCHEST, fx.T3, sick, 0); band(fx, stone, fx.TCHEST, w, tint, 0)
    fx.lin(fx.T3, w, 2)
    alt(fx, FRAME, 1, lambda: band(fx, stone, fx.TCHEST, fx.T3, dark, 1, clut=1, blend='sub'),
        lambda: band(fx, stone, fx.TCHEST, fx.T3, dark, 2, clut=1, blend='sub'))
    fx.lin(fx.T3, w, 3); fx.sprite(fx.TCHEST, sick, fx.T3, cell=3); fx.ret()
    return fx


# ----------------------------------------------------------------- Pharaohmon
def pyramid_power():
    """Pharaohmon sends a line of gold into the sky over the target; there it draws a pyramid of light, edge by edge,
    around the victim. When the last edge meets the apex the pyramid fills: a shaft of gold pours down inside it and
    turquoise ankhs rise out of the glare."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(PHARAOH); fx.palette(TURQUOISE)
    fx.paint(0, thin(6.0)); fx.paint(1, column(111)); fx.paint(2, ankh()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, star(4, 2.5, 14, 10)); fx.paint(6, column(113))
    tint, gold, wide = fx.colour(128, 128, 128), fx.colour(128, 100, 40), fx.var()
    apex, foot, p, q = fx.vec(), fx.vec(), fx.vec(), fx.vec()
    base = [fx.vec() for _ in range(4)]
    build, life = 12, 24
    fx.particle('glyph', 6, 14, 2, (128, 128, 128), (170, 230), grow=4, lift=36, spread=300, clut=1, fade=True)
    fx.particle('dust', 18, 13, 4, (128, 110, 60), (60, 120), grow=-5, speed=50, lift=40, gravity=4, spread=260)
    fx.particle('crown', 1, 9, 5, (128, 128, 128), 300, grow=60, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(4, 'chime'); fx.when(8, 'chime'); fx.when(build, 'smite')
    fx.when(build + 4, 'echo'); fx.end(life + 1)
    fx.label('begin')
    fx.sound(-55); fx.aim(); fx.vcopy(foot, fx.TGT); fx.sub_(at(foot, 1), 20)
    fx.vcopy(apex, fx.TGT); fx.lin(fx.T, at(fx.TSIZE, 1), 10, 480, 10); fx.sub_(at(apex, 1), fx.T)
    for k, (dx, dz) in enumerate(((-420, -300), (420, -300), (420, 300), (-420, 300))):
        fx.vcopy(base[k], foot); fx.add(at(base[k], 0), dx); fx.add(at(base[k], 2), dz)
    fx.vcopy(fx.AT, foot); fx.call('tomb'); fx.ret()
    fx.label('chime'); fx.sound(34); fx.ret()
    fx.label('smite')
    fx.sound(13); fx.aim(); fx.hit(); fx.emit('crown', apex); fx.emit('dust', fx.TCHEST, 10)
    fx.emit('glyph', times=3); fx.ret()
    fx.label('echo'); fx.sound(15); fx.aim(); fx.emit('glyph', fx.TCHEST, 3); fx.emit('dust', times=8); fx.ret()
    holder(fx, 'tomb', life, 'tomb_render')
    fx.label('tomb_render')
    late = fx.label()
    fx.set(fx.T3, FRAME); fx.br(fx.T3, '<', 5, late); fx.set(fx.T3, 5)       # the line from the caster to the apex
    fx.label(late); along(fx, p, fx.CHEST, apex, fx.T3, 5)
    fx.br(FRAME, '>', build + 3, 'tomb_base'); band(fx, fx.CHEST, p, 30, gold, 0)
    fx.label('tomb_base')
    fx.br(FRAME, '<', 3, 'tomb_done')                                       # the base, drawn in four ticks
    fx.lin(fx.T3, FRAME, 1, -3); fx.br(fx.T3, '<', 4, 'tomb_b'); fx.set(fx.T3, 4)
    fx.label('tomb_b')
    for k in range(4):
        along(fx, p, base[k], base[(k + 1) % 4], fx.T3, 4); band(fx, base[k], p, 40, tint, 0)
    fx.br(FRAME, '<', 6, 'tomb_done')                                       # the edges, climbing to the apex
    fx.lin(fx.T3, FRAME, 1, -6); fx.br(fx.T3, '<', 6, 'tomb_e'); fx.set(fx.T3, 6)
    fx.label('tomb_e')
    for k in range(4):
        along(fx, p, base[k], apex, fx.T3, 6); band(fx, base[k], p, 50, tint, 0)
        fx.sprite(p, gold, 150, cell=3)
    fx.br(FRAME, '<', build, 'tomb_done')                                   # the shaft inside
    fx.set(fx.T2, FRAME); fx.sub_(fx.T2, build); env(fx, wide, life - build, 520, rise=2, fall=5, flick=50, clock=fx.T2)
    fx.vcopy(q, apex); fx.vsub(q, foot); fx.lin(fx.T3, at(q, 1), -1)
    alt(fx, FRAME, 1, lambda: fx.pillar(foot, wide, fx.T3, tint, cell=1),
        lambda: fx.pillar(foot, wide, fx.T3, tint, cell=6))
    fx.lin(fx.T3, wide, 1); fx.sprite(apex, gold, fx.T3, cell=3)
    fx.label('tomb_done'); fx.ret()
    return fx


# ----------------------------------------------------------------- Ghoulmon
def necro_eye():
    """A great eye opens in front of Ghoulmon, lid by lid; its slit pupil looses a needle of red light with motes
    winding round it, and the life it touches leaves the target as pale wisps that drift upward."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(NECRO); fx.palette(['#000000', '#103830', '#50a090', '#c0fff0', '#ffffff'])
    fx.paint(0, eyeball(0.08)); fx.paint(1, eyeball(0.5)); fx.paint(2, eyeball(1.0)); fx.paint(3, thin(3.0))
    fx.paint(4, glow(15, 1.2)); fx.paint(5, soul()); fx.paint(6, star(4, 2, 9, 6)); fx.paint(7, ring(13, 2.0))
    tint, red, dim = fx.colour(128, 128, 128), fx.colour(128, 30, 30), fx.colour(70, 14, 14)
    eye, p, w, k = fx.vec(), fx.vec(), fx.var(), fx.var()
    charge, life = 9, 13
    fx.particle('wisp', 8, 15, 5, (128, 128, 128), (190, 260), grow=3, lift=38, spread=220, clut=1, fade=True)
    fx.particle('sting', 1, 8, 4, (128, 40, 40), None, grow=60, fade=True)
    fx.particle('pulse', 2, 8, 7, (128, 40, 40), 150, grow=80, fade=True)
    fx.particle('fleck', 14, 12, 6, (128, 60, 60), (60, 110), grow=-5, speed=70, lift=20, gravity=5, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(3, 'creak'); fx.when(6, 'creak'); fx.when(charge, 'loose')
    fx.when(charge + 2, 'smite'); fx.when(charge + 5, 'drain'); fx.when(charge + 8, 'drain')
    fx.end(charge + life)
    fx.label('begin'); ahead(fx, eye, fx.CHEST, 90); fx.vcopy(fx.AT, eye); fx.call('orb'); fx.sound(-55); fx.ret()
    fx.label('creak'); fx.sound(34); fx.ret()
    fx.label('loose'); fx.sound(13); fx.vcopy(fx.AT, eye); fx.call('needle'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 11, 280, 10)
    fx.emit('sting', fx.TCHEST); fx.emit('pulse'); fx.emit('fleck', times=10); fx.emit('wisp', times=2); fx.ret()
    fx.label('drain'); fx.sound(20); fx.aim(); fx.emit('wisp', fx.TCHEST, 3); fx.emit('pulse'); fx.ret()
    holder(fx, 'orb', charge + life - 1, 'orb_render')
    fx.label('orb_render')
    fx.br(FRAME, '>=', charge + life - 4, 'orb_half'); fx.br(FRAME, '>=', 6, 'orb_open'); fx.br(FRAME, '>=', 3, 'orb_half')
    fx.sprite(POS, tint, 460, cell=0); fx.ret()
    fx.label('orb_half'); fx.sprite(POS, tint, 460, cell=1); fx.ret()
    fx.label('orb_open'); fx.sprite(POS, tint, 460, cell=2); fx.sprite(POS, dim, 800, cell=4); fx.ret()
    holder(fx, 'needle', life, 'needle_render', tick='aim')
    fx.label('needle_render')
    env(fx, w, life, 50, rise=1, fall=4, flick=14)
    fx.lin(fx.T3, w, 4); band(fx, eye, fx.TCHEST, fx.T3, dim, 3); band(fx, eye, fx.TCHEST, w, tint, 3)
    fx.set(k, 0)
    fx.label('needle_loop')
    fx.lin(fx.T3, k, 2); fx.add(fx.T3, FRAME); fx.mod(fx.T3, 10); fx.add(fx.T3, 1)
    along(fx, p, eye, fx.TCHEST, fx.T3, 11)
    fx.lin(fx.T3, FRAME, 700); fx.lin(fx.T2, k, 820); fx.add(fx.T3, fx.T2); fx.sin(fx.T, fx.T3, 110)
    fx.add(at(p, 1), fx.T); fx.sprite(p, red, 130, cell=4); fx.sprite(p, tint, 60, cell=4)
    fx.add(k, 1); fx.br(k, '<', 5, 'needle_loop')
    fx.lin(fx.T3, w, 6); fx.sprite(fx.TCHEST, red, fx.T3, cell=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Raidenmon
def raiden_strike():
    """Raidenmon throws a spark into the sky and storm cloud piles up over the target, flickering from inside; then
    the cloud lets go twice: two forked bolts stand between it and the ground, the field flashing with each, and
    current crawls over the earth where they struck."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(RAIDEN); fx.palette(['#000000', '#2c3850', '#6478a8', '#b8c8f0'])
    fx.paint(0, bolt(21)); fx.paint(1, bolt(22)); fx.paint(2, bolt(24)); fx.paint(3, puff(121)); fx.paint(4, glow(15, 1.2))
    fx.paint(5, zig(25)); fx.paint(6, star(4, 2, 9, 6)); fx.paint(7, puff(123))
    tint, amber, wash = fx.colour(128, 128, 128), fx.colour(128, 100, 30), fx.vec()
    sky, foot, w, tall, flash = fx.vec(), fx.vec(), fx.var(), fx.var(), fx.var()
    charge = 10
    fx.particle('cloud', 10, 18, 3, (128, 128, 128), (360, 480), grow=5, spread=340, clut=1, fade=True)
    fx.particle('cloud2', 8, 16, 7, (128, 128, 128), (320, 440), grow=5, spread=340, clut=1, fade=True)
    fx.particle('arc', 10, 3, 5, (128, 128, 128), (200, 320), spread=360)
    fx.particle('spark', 18, 12, 6, (128, 128, 100), (60, 120), grow=-6, speed=90, lift=50, gravity=9, spread=60)
    fx.particle('burn', 1, 7, 4, (128, 110, 50), None, grow=70, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'first'); fx.when(charge + 5, 'second')
    fx.br(fx.NOW, '>', charge + 4, 'main_arcs'); fx.br(fx.NOW, '<', 2, 'main_arcs')
    fx.set(fx.T3, fx.NOW); fx.mod(fx.T3, 2); fx.br(fx.T3, '!=', 0, 'main_arcs')
    fx.emit('cloud', sky); fx.emit('cloud2')
    fx.label('main_arcs'); fx.br(fx.NOW, '<', charge, 'main_end'); fx.br(fx.NOW, '>', charge + 10, 'main_end')
    fx.emit('arc', foot)
    fx.label('main_end'); fx.sub_(flash, 30); fx.end(charge + 14)
    fx.label('draw')
    fx.br(flash, '<=', 0, 'noop'); fx.lin(fx.T2, flash, 7, 0, 10); fx.vset(wash, fx.T2, fx.T2, flash)
    fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    fx.sound(-55); fx.set(flash, 0); fx.aim(); fx.vcopy(foot, fx.TGT); fx.sub_(at(foot, 1), 60)
    fx.vcopy(sky, fx.TGT); fx.lin(tall, at(fx.TSIZE, 1), 8, 470, 10); fx.sub_(at(sky, 1), tall)
    fx.vcopy(fx.AT, fx.CHEST); fx.call('spark_up'); fx.ret()
    fx.label('first')
    fx.sound(13); fx.aim(); fx.hit(); fx.set(flash, 110); fx.vcopy(fx.AT, fx.TGT); fx.call('strike')
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 300, 10); fx.emit('burn', fx.TCHEST); fx.emit('spark', times=10); fx.ret()
    fx.label('second')
    fx.sound(15); fx.aim(); fx.set(flash, 90); fx.vcopy(fx.AT, fx.TGT); fx.add(at(fx.AT, 0), 110); fx.call('strike')
    fx.emit('spark', fx.TCHEST, 8); fx.ret()
    holder(fx, 'spark_up', 6, 'up_render')
    fx.label('up_render')
    along(fx, fx.TV, fx.CHEST, sky, FRAME, 5); fx.sprite(fx.TV, tint, 150, cell=6); fx.sprite(fx.TV, amber, 320, cell=4)
    fx.ret()
    pool = fx.pool('strike', 2)
    fx.begin('strike', pool, 'strike_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('strike_tick'); fx.life(5); fx.ret()
    fx.label('strike_render')
    fx.lin(w, FRAME, -70, 480); fx.set(fx.T3, FRAME); fx.mod(fx.T3, 3)
    fx.br(fx.T3, '==', 1, 'strike_b'); fx.br(fx.T3, '==', 2, 'strike_c')
    fx.pillar(POS, w, tall, tint, cell=0); fx.jmp('strike_glow')
    fx.label('strike_b'); fx.pillar(POS, w, tall, tint, cell=1); fx.jmp('strike_glow')
    fx.label('strike_c'); fx.pillar(POS, w, tall, tint, cell=2)
    fx.label('strike_glow')
    fx.lin(fx.T3, w, 2); fx.pillar(POS, fx.T3, tall, amber, cell=4)
    fx.vcopy(fx.TV, POS); fx.sub_(at(fx.TV, 1), tall); fx.sprite(fx.TV, amber, 700, cell=4); fx.ret()
    return fx


# ----------------------------------------------------------------- Cannondramon
def dynamo_cannon():
    """The two dynamos on Cannondramon's back spin up, one over each shoulder, until both glow; then the cannons fire
    by turns, six shells in all, each kicking a flash out of its muzzle and bursting orange on the target. The first
    one in lands the blow."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(DYNAMO); fx.palette(MUZZLE)
    fx.paint(0, rotor()); fx.paint(1, shell()); fx.paint(2, glow(15, 1.2)); fx.paint(3, fireball(131))
    fx.paint(4, star(6, 3, 14, 6)); fx.paint(5, ring(13, 2.2)); fx.paint(6, star(4, 2, 9, 6))
    tint, blue = fx.colour(128, 128, 128), fx.colour(40, 90, 128)
    left, right, side, spin, first, turn = fx.vec(), fx.vec(), fx.vec(), fx.var(), fx.var(), fx.var()
    charge = 8
    fx.particle('kick', 6, 4, 4, (128, 128, 128), 260, grow=40, clut=1, fade=True)
    fx.particle('boom', 6, 8, 3, (128, 128, 128), 240, grow=50, clut=1, fade=True, spread=120)
    fx.particle('wave', 6, 7, 5, (128, 128, 128), 140, grow=80, fade=True)
    fx.particle('scrap', 18, 12, 6, (128, 110, 70), (60, 120), grow=-6, speed=90, lift=30, gravity=8, spread=70, clut=1)
    fx.travel('round', 6, 5, 'round_render', 'round_hit')
    fx.label('main'); fx.when(0, 'begin')
    for n in range(6):
        fx.when(charge + 2 * n, 'fire')
    fx.add(spin, 90); fx.lin(fx.T3, fx.NOW, 40); fx.add(spin, fx.T3); fx.end(charge + 12)
    fx.label('begin')
    fx.sound(-55); fx.set(first, 0); fx.set(turn, 0); fx.set(spin, 0); sideways(fx, side, 230)
    above(fx, left, fx.SRC, fx.SSIZE, 11); above(fx, right, fx.SRC, fx.SSIZE, 7)
    ahead(fx, left, left, -160); ahead(fx, right, right, 120); fx.vadd(left, side); fx.vsub(right, side)
    fx.vcopy(fx.AT, left); fx.call('dynamo'); fx.ret()
    fx.label('fire')
    fx.sound(40); fx.aim(); fx.vcopy(fx.DEST, fx.TCHEST); fx.scatter(fx.DEST, 90)
    fx.add(turn, 1); fx.set(fx.T3, turn); fx.mod(fx.T3, 2); fx.br(fx.T3, '==', 0, 'fire_right')
    fx.vcopy(fx.AT, left); fx.jmp('fire_go')
    fx.label('fire_right'); fx.vcopy(fx.AT, right)
    fx.label('fire_go'); fx.emit('kick', fx.AT); fx.call('round'); fx.ret()
    fx.label('round_render')
    fx.lin(fx.T3, FRAME, 900); fx.sprite(POS, tint, 230, cell=1, rot=fx.T3); fx.sprite(POS, blue, 420, cell=2); fx.ret()
    fx.label('round_hit')
    fx.emit('boom', POS); fx.emit('wave'); fx.emit('scrap', times=3)
    fx.br(first, '!=', 0, 'round_more'); fx.set(first, 1); fx.aim(); fx.hit(); fx.sound(15); fx.ret()
    fx.label('round_more'); fx.sound(16); fx.ret()
    holder(fx, 'dynamo', charge + 13, 'dynamo_render')
    fx.label('dynamo_render')
    grown = fx.label()
    fx.lin(fx.T2, FRAME, 40, 120); fx.br(fx.T2, '<', 300, grown); fx.set(fx.T2, 300)
    fx.label(grown)
    for m in (left, right):
        fx.sprite(m, tint, fx.T2, cell=0, rot=spin)
    fx.lin(fx.T2, fx.T2, 18, 0, 10)
    for m in (left, right):
        fx.sprite(m, blue, fx.T2, cell=2)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Armageddemon
def ultimate_flare():
    """Armageddemon draws the air in, embers streaming into its jaws, and breathes it back out as a cone of crimson
    and gold fire that widens until it swallows the target; three blasts go off inside it one after another and black
    smoke climbs out of what is left."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(HELL); fx.palette(GREY)
    fx.paint(0, cone(141)); fx.paint(1, cone(143)); fx.paint(2, fireball(145)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, puff(147)); fx.paint(6, fireball(149)); fx.paint(7, cone(151))
    tint, deep = fx.colour(128, 128, 128), fx.colour(128, 50, 80)
    jaws, far, w = fx.vec(), fx.vec(), fx.var()
    charge, life = 8, 14
    gather(fx, 'mote', 16, 4, (128, 80, 90), 100, 640, 5)
    fx.particle('blast', 4, 9, 2, (128, 128, 128), 300, grow=70, fade=True)
    fx.particle('blast2', 3, 9, 6, (128, 128, 128), 300, grow=70, fade=True)
    fx.particle('ember', 18, 14, 4, (128, 90, 80), (60, 130), grow=-5, speed=95, lift=40, gravity=7, spread=120)
    fx.particle('smoke', 10, 16, 5, (100, 100, 100), (240, 340), grow=14, lift=26, spread=200, clut=1, blend='sub',
                fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose'); fx.when(charge + 3, 'smite')
    fx.when(charge + 6, 'again'); fx.when(charge + 9, 'again'); fx.when(charge + 12, 'fume')
    fx.br(fx.NOW, '>', charge - 3, 'main_end'); fx.emit('mote', jaws, 3)
    fx.label('main_end'); fx.end(charge + life + 2)
    fx.label('begin')
    above(fx, jaws, fx.SRC, fx.SSIZE, 7); ahead(fx, jaws, jaws, 110); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.sound(13); fx.aim(); along(fx, far, jaws, fx.TCHEST, 5, 4); fx.vcopy(fx.AT, jaws); fx.call('breath'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.emit('blast', fx.TCHEST); fx.emit('ember', times=8); fx.ret()
    fx.label('again')
    fx.sound(16); fx.aim(); fx.vcopy(fx.TV2, fx.TCHEST); fx.scatter(fx.TV2, 240)
    fx.emit('blast2', fx.TV2); fx.emit('ember', times=5); fx.emit('smoke', times=3); fx.ret()
    fx.label('fume'); fx.aim(); fx.emit('smoke', fx.TCHEST, 4); fx.ret()
    holder(fx, 'breath', life, 'breath_render')
    fx.label('breath_render')
    env(fx, w, life, 440, rise=3, fall=5, flick=50)
    fx.set(fx.T3, FRAME); fx.mod(fx.T3, 3); fx.br(fx.T3, '==', 1, 'breath_b'); fx.br(fx.T3, '==', 2, 'breath_c')
    band(fx, jaws, far, w, tint, 0); fx.jmp('breath_core')
    fx.label('breath_b'); band(fx, jaws, far, w, tint, 1); fx.jmp('breath_core')
    fx.label('breath_c'); band(fx, jaws, far, w, tint, 7)
    fx.label('breath_core')
    fx.lin(fx.T3, w, 13, 0, 10); band(fx, jaws, far, fx.T3, deep, 0)
    fx.lin(fx.T3, w, 1); fx.sprite(jaws, deep, fx.T3, cell=3); fx.ret()
    return fx


# ----------------------------------------------------------------- Suijinmon
def water_spiral():
    """Two ropes of water wind out of Suijinmon's hands round one another, corkscrewing all the way to the target;
    when they close on it a spout bursts up from under its feet and comes down again as rain."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(WATER)
    fx.paint(0, blob()); fx.paint(1, spout(161)); fx.paint(2, spout(163)); fx.paint(3, drop()); fx.paint(4, ring(13, 2.0))
    fx.paint(5, glow(15, 1.2))
    tint, deep = fx.colour(128, 128, 128), fx.colour(40, 80, 128)
    hands, side, p, off = fx.vec(), fx.vec(), fx.vec(), fx.vec()
    k, reach, ang, c, tall, wide = fx.var(), fx.var(), fx.var(), fx.var(), fx.var(), fx.var()
    flight, life, n = 6, 20, 10
    fx.particle('rain', 22, 14, 3, (128, 128, 128), (80, 140), speed=70, lift=85, gravity=12, spread=120)
    fx.particle('foam', 3, 9, 4, (128, 128, 128), 160, grow=85, fade=True)
    fx.particle('spray', 10, 6, 5, (60, 100, 128), (100, 180), grow=-12, spread=120)
    fx.label('main'); fx.when(0, 'begin'); fx.when(flight + 1, 'smite'); fx.when(flight + 5, 'fall')
    fx.br(fx.NOW, '>', flight + 6, 'main_end'); fx.emit('spray', hands)
    fx.label('main_end'); fx.end(life)
    fx.label('begin')
    fx.sound(40); ahead(fx, hands, fx.CHEST, 70); sideways(fx, side, 128)
    fx.vcopy(fx.AT, hands); fx.call('helix'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.emit('foam', fx.TGT); fx.emit('rain', fx.TCHEST, 12)
    fx.vcopy(fx.AT, fx.TGT); fx.call('geyser'); fx.ret()
    fx.label('fall'); fx.sound(34); fx.aim(); fx.emit('foam', fx.TGT); fx.emit('rain', fx.TCHEST, 10); fx.ret()
    holder(fx, 'helix', flight + 8, 'helix_render', tick='aim')
    fx.label('helix_render')
    fx.lin(reach, FRAME, 2, 1)                       # the head of the ropes; their tail lets go after they land
    fx.set(k, 1); fx.br(FRAME, '<', flight + 2, 'helix_loop'); fx.lin(k, FRAME, 2, -2 * flight - 2)
    fx.label('helix_loop'); fx.br(k, '>', reach, 'helix_end'); fx.br(k, '>', n, 'helix_end')
    along(fx, p, hands, fx.TCHEST, k, n)
    fx.lin(ang, FRAME, 560); fx.lin(fx.T2, k, 520); fx.sub_(ang, fx.T2)
    fx.sin(fx.T3, ang, 150); fx.cos(c, ang, 150)
    fx.vcopy(off, side); fx.vmul(off, c); fx.vdiv(off, 128); fx.sub_(at(off, 1), fx.T3)
    fx.vadd(p, off); fx.sprite(p, tint, 190, cell=0)
    fx.vsub(p, off); fx.vsub(p, off); fx.sprite(p, tint, 190, cell=0)
    fx.add(k, 1); fx.jmp('helix_loop')
    fx.label('helix_end'); fx.ret()
    holder(fx, 'geyser', 10, 'geyser_render')
    fx.label('geyser_render')
    env(fx, tall, 10, 1000, rise=3, fall=4, flick=60)
    fx.lin(wide, tall, 1, 220, 3)
    alt(fx, FRAME, 1, lambda: fx.pillar(POS, wide, tall, tint, cell=1), lambda: fx.pillar(POS, wide, tall, tint, cell=2))
    fx.lin(fx.T3, wide, 15, 0, 10); fx.pillar(POS, fx.T3, tall, deep, cell=5); fx.ret()
    return fx


# ----------------------------------------------------------------- Bastemon
def cat_laser():
    """Two green cat's eyes open in the air over Bastemon, slit pupils narrowing; each looses a thin rose-coloured
    ray, and the two sweep in from either side, scoring sparks, until they cross on the target in a star of light and
    a scatter of jewels."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(JEWEL); fx.palette(EMERALD)
    fx.paint(0, cat_eye()); fx.paint(1, thin(3.0)); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2.5, 14, 10))
    fx.paint(4, gem()); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.0))
    tint, rose = fx.colour(128, 128, 128), fx.colour(128, 50, 90)
    left, right, side, enda, endb, off = fx.vec(), fx.vec(), fx.vec(), fx.vec(), fx.vec(), fx.vec()
    lid, w, sweep = fx.var(), fx.var(), fx.var()
    charge, cross, life = 6, 7, 13
    fx.particle('score', 14, 8, 5, (128, 90, 110), (60, 110), grow=-8, speed=50, lift=30, gravity=6, spread=40)
    fx.particle('shine', 1, 10, 3, (128, 128, 128), None, grow=80, fade=True, spin=200)
    fx.particle('halo', 2, 8, 6, (128, 70, 100), 150, grow=85, fade=True)
    fx.particle('jewel', 16, 15, 4, (128, 128, 128), (90, 150), speed=80, lift=60, gravity=9, spread=60, spin=300)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose'); fx.when(charge + cross, 'smite')
    fx.br(fx.NOW, '<=', charge, 'main_end'); fx.br(fx.NOW, '>=', charge + cross, 'main_end')
    fx.emit('score', enda); fx.emit('score', endb)
    fx.label('main_end'); fx.end(charge + life + 2)
    fx.label('begin')
    fx.sound(34); sideways(fx, side, 150); above(fx, left, fx.SRC, fx.SSIZE, 10)
    ahead(fx, right, left, -170); ahead(fx, left, left, 170)
    fx.vcopy(enda, fx.TCHEST); fx.vcopy(endb, fx.TCHEST)
    fx.vcopy(fx.AT, left); fx.call('eyes'); fx.ret()
    fx.label('loose'); fx.sound(40); fx.vcopy(fx.AT, left); fx.call('rays'); fx.ret()
    fx.label('smite')
    fx.sound(15); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 14, 360, 10)
    fx.emit('shine', fx.TCHEST); fx.emit('halo'); fx.emit('jewel', times=14); fx.ret()
    holder(fx, 'eyes', charge + life, 'eyes_render')
    fx.label('eyes_render')
    env(fx, lid, charge + life, 240, rise=5, fall=3, flick=0)
    for m in (left, right):
        fx.sprite(m, tint, 320, lid, cell=0, clut=1)
    fx.ret()
    holder(fx, 'rays', life, 'rays_render', tick='rays_step')
    fx.label('rays_step')                            # the two ends close in on the target, then stay on it
    closed = fx.label()
    fx.aim(); fx.lin(sweep, FRAME, -1, cross); fx.br(sweep, '>', 0, closed); fx.set(sweep, 0)
    fx.label(closed)
    fx.vcopy(off, side); fx.vmul(off, sweep); fx.vmul(off, 5); fx.vdiv(off, cross)
    fx.lin(fx.T3, sweep, 420, 0, cross); fx.add(at(off, 1), fx.T3)
    fx.vcopy(enda, fx.TCHEST); fx.vadd(enda, off)
    fx.set(at(off, 1), 0); fx.vcopy(endb, fx.TCHEST); fx.vsub(endb, off); fx.sub_(at(endb, 1), fx.T3)
    fx.ret()
    fx.label('rays_render')
    env(fx, w, life, 44, rise=1, fall=3, flick=14)
    fx.lin(fx.T3, w, 3)
    for a, b in ((left, enda), (right, endb)):
        band(fx, a, b, fx.T3, rose, 1); band(fx, a, b, w, tint, 1)
        fx.lin(fx.T2, w, 5); fx.sprite(b, rose, fx.T2, cell=2)
    fx.ret()
    return fx


EFFECTS = {237: inferno_missile, 238: pulse_blast, 250: flare_buster, 251: solar_flare, 256: jamming_thunder,
           295: nightmare_shock, 297: mugen_hadou, 302: atomic_ray, 313: bulb_flash, 314: nail_bone,
           319: pyramid_power, 329: necro_eye, 336: raiden_strike, 405: dynamo_cannon, 407: ultimate_flare,
           408: water_spiral, 432: cat_laser}
