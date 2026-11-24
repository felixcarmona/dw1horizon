"""The finishers that come as a volley (many shots, stars, fish, bats or meteors one after another), written for this
game with the kit: one function per species, each with its own paintings and its own choreography."""
import math

import numpy as np

from tools.technique_effects.finishers import BLUEFIRE, FIRE, GOLD, ICE, PLASMA, VIOLET, ahead, arc, band, column, \
    dome, fireball, flicker, petal, puff, round_shot, shard, slash, tongue
from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, fbm, glow, grid, iv, polar, ring, segment, \
    star

CACTUS = ['#000000', '#0c3a10', '#2c9a2c', '#a8e858', '#fffff0']
SEA = ['#081830', '#1850b0', '#40a0f0', '#b0e8ff', '#ffffff']
REEF = ['#301008', '#d04810', '#ff9820', '#ffe070', '#ffffff']
NIGHT = ['#000000', '#1c0c30', '#48208c', '#9c58e0', '#ff3048', '#ffffff']
STONE = ['#180804', '#4a2c18', '#7a5838', '#b08858', '#ff7810', '#ffe890']
STEEL = ['#101418', '#3c444c', '#7c8490', '#c8d0d8', '#f04020', '#ff8040']
SMOKE = ['#000000', '#30343c', '#70747c', '#b0b4bc']
STARLIGHT = ['#000000', '#182868', '#6890f0', '#d8e8ff', '#ffffff']


# ----------------------------------------------------------------- paintings
def drill(turn=0.0):
    """A drill seen from its point: a cone whose grooves wind in to a bright tip."""
    r, ang = polar()
    groove = 0.5 + 0.5 * np.cos(3 * ang + r * 0.75 + turn)
    return clip(clip((13 - r) / 1.5) * (0.28 + 0.6 * groove * (0.45 + r / 24)) + clip(1 - r / 4.5))


def streak(seed, sharp=1.5):
    """A shot's wake for a band: a hot head at the right, thinning to nothing at the left."""
    x, y = grid()
    t = x / 32
    return clip(1.2 - np.abs(y - 16) / (3 + 10 * t)) * t ** sharp * (0.7 + 0.4 * fbm(seed))


def plasma(seed):
    """A knot of plasma: a white heart inside a ragged, five-lobed corona."""
    r, ang = polar()
    edge = 7 + 5 * fbm(seed) + 2.5 * np.cos(ang * 5 + seed)
    return clip(clip(1 - r / edge) ** 0.5 * 1.2 * (0.6 + 0.5 * fbm(seed + 2)))


def five_star(turn=0.0, outer=14.0, inner=6.0, hollow=False):
    """A five-point star, one point up: solid with a bright heart, or only its outline."""
    r, ang = polar()
    a = math.pi / 5
    th = np.mod(ang + turn + math.pi / 2, 2 * a)
    th = np.minimum(th, 2 * a - th)
    d = outer * inner * math.sin(a) / (outer * np.sin(th) + inner * np.sin(a - th)) - r
    if hollow:
        return clip(1 - np.abs(d - 1.3) / 1.5)
    return clip(d / 1.4) * (0.5 + 0.5 * clip(1 - r / (outer * 0.7))) + 0.3 * clip(1 - np.abs(d - 1.0) / 1.0)


def fall_tail(seed):
    """What a falling thing leaves above it: wide and bright at the bottom, a thread at the top."""
    x, y = grid()
    t = y / 32
    return clip(1 - np.abs(x - 16) / (2 + 9 * t)) * t ** 1.3 * (0.6 + 0.6 * fbm(seed))


def holy():
    """An orb of light: a white heart, a thin halo and a long cross of rays."""
    r, _ = polar()
    return clip(clip(1 - r / 7.5) ** 0.5 + 0.7 * star(4, 1.2, 15, 14) + 0.45 * ring(10.5, 1.1))


def needle():
    """A cactus needle for a band: a thin line with its point at the right."""
    x, y = grid()
    t = x / 32
    return clip(1.3 - np.abs(y - 16) / (5.0 * (1 - t ** 3) + 0.3)) * (x > 1)


def whirl(turn):
    """Three curved arms: something spinning fast."""
    r, ang = polar()
    arms = 0.5 + 0.5 * np.cos(3 * ang - r * 0.45 + turn)
    return clip(arms ** 2 * clip(1 - r / 15) ** 0.4 * clip(r / 3))


def fish(fat=1.0):
    """A fish seen from its side, head up: outline, a lighter belly, an eye, fins and a forked tail."""
    x, y = grid()
    body = ((x - 16) / (5.5 * fat)) ** 2 + ((y - 13) / 9.5) ** 2
    tail = (y > 20) & (y < 30) & (np.abs(x - 16) < (y - 19) * 0.75) & ~((y > 26) & (np.abs(x - 16) < (y - 26) * 0.9))
    fin = (np.abs(y - 15) < 2.5) & (np.abs(x - 16) < 5.5 * fat + 3)
    lum = np.where(tail | fin, 0.5, 0.0)
    lum = np.where(body < 1, 0.58 + 0.38 * clip((16 - x) / (5 * fat)), lum)
    if fat > 1.2:
        lum = np.where((body < 0.8) & (np.abs(np.mod(y, 5) - 2.5) < 0.9), 0.32, lum)
    lum = np.where((body < 1) & (body > 0.78), 0.14, lum)
    return np.where(np.hypot(x - 14.3, y - 8) < 1.5, 0.1, lum)


def crown():
    """A splash: jets of water fanning up from one point, a drop at the end of each."""
    x, y = grid()
    lum = 0.6 * clip(1 - np.hypot(x - 16, (y - 29) * 1.6) / 9)
    for k in range(-3, 4):
        tip = (16 + k * 4.4, 5 + abs(k) * 3.4)
        lum = np.maximum(lum, segment(16 + k * 1.4, 29, *tip, 1.5))
        lum = np.maximum(lum, clip(1.3 - np.hypot(x - tip[0], y - tip[1]) / 2.0))
    return clip(lum)


def droplet():
    r, _ = polar()
    x, y = grid()
    return clip(clip((6.5 - r) / 1.5) * 0.55 + 0.6 * clip(1 - np.hypot(x - 14, y - 13.5) / 2.6))


def bat(up):
    """A bat seen head-on, its wings raised or lowered: dark body, lighter wing bones, two lit eyes."""
    x, y = grid()
    u = np.abs(x - 16)
    top = 14 + (-0.45 if up else 0.35) * u
    bottom = top + 9.5 - 0.33 * u - 3.2 * np.abs(np.sin(u * 0.67))
    wing = (u < 15.5) & (y > top) & (y < bottom)
    body = (np.hypot((x - 16) / 3.4, (y - 17) / 5.2) < 1) | ((np.abs(u - 2.3) < 1.4) & (y > 9.5) & (y < 13))
    lum = np.where(wing, 0.44, 0.0)
    lum = np.where(wing & (y < top + 1.7), 0.62, lum)
    lum = np.where(body, 0.27, lum)
    return np.where((np.abs(u - 1.5) < 1.0) & (np.abs(y - 15.2) < 1.0), 0.84, lum)


def rock(seed):
    """A lump of stone with glowing cracks."""
    x, y = grid()
    r, _ = polar()
    inside = r < 8.5 + 5.5 * fbm(seed)
    shade = 0.16 + 0.34 * fbm(seed + 3) + 0.12 * clip((20 - x - y * 0.3) / 10)
    cracks = np.abs(fbm(seed + 7) - 0.5) < 0.03
    return np.where(inside, np.where(cracks, 0.95, np.minimum(shade, 0.62)), 0.0)


def comet(seed):
    """A comet's head: a white heart in a ragged ball of cold fire."""
    r, _ = polar()
    return clip(clip(1 - r / (10 + 4 * fbm(seed))) ** 0.6 * (0.6 + 0.5 * fbm(seed + 4)) + clip(1 - r / 6) ** 0.8)


def missile():
    """A rocket, nose up: a red nose, a grey body with a dark band, fins."""
    x, y = grid()
    u = np.abs(x - 16)
    lum = np.where((y > 20) & (y < 28) & (u < 3.6 + (y - 20) * 0.8), 0.3, 0.0)
    lum = np.where((u < 3.8) & (y > 9) & (y < 26), 0.42 + 0.22 * (x < 16), lum)
    lum = np.where((u < 3.8) & (np.abs(y - 13.5) < 1.1), 0.14, lum)
    return np.where((y <= 9.5) & (y > 1.5) & (u < (y - 1.5) * 0.5), 0.8, lum)


# ----------------------------------------------------------------- shared pieces
def forward(fx, out, length):
    """out = the ground direction from the caster to the target, that long."""
    ok = fx.label()
    fx.vcopy(out, fx.TGT); fx.vsub(out, fx.SRC); fx.set(at(out, 1), 0)
    fx.vlen(fx.T, out); fx.br(fx.T, '>', 0, ok); fx.set(fx.T, 1)
    fx.label(ok)
    fx.vmul(out, length); fx.vdiv(out, fx.T)


def sideways(fx, out, fwd):
    """out = that ground vector turned a quarter."""
    fx.set(at(out, 0), at(fwd, 2)); fx.set(at(out, 1), 0); fx.lin(at(out, 2), at(fwd, 0), -1)


def ticker(fx, first, last, every, label):
    """In main: call the label on the ticks first, first + every ... up to last."""
    skip = fx.label()
    fx.br(fx.NOW, '<', first, skip); fx.br(fx.NOW, '>', last, skip)
    if every > 1:
        fx.lin(fx.T, fx.NOW, 1, -first); fx.mod(fx.T, every); fx.br(fx.T, '!=', 0, skip)
    fx.call(label)
    fx.label(skip)


def lob(fx, name, count, ticks, render, arrive, gravity=0, every=None, fields=0, setup=None):
    """Define the routine `name`: an instance thrown from AT that lands on DEST after `ticks` ticks, in a straight
    line or, with gravity, in an arc. Its velocity is the instance vector at FREE; `fields` more values follow it,
    which setup() fills in when it is born."""
    pool = fx.pool(name, count, 3 + fields)
    step, go = iv(FREE), fx.label()
    fx.begin(name, pool, render, inherit=False)
    fx.vcopy(POS, fx.AT); fx.vcopy(step, fx.DEST); fx.vsub(step, fx.AT); fx.vdiv(step, ticks)
    if gravity:
        fx.sub_(at(step, 1), gravity * (ticks - 1) // 2)
    if setup:
        setup()
    fx.ret()
    fx.label(name + '_tick'); fx.br(FRAME, '>=', ticks, go); fx.vadd(POS, step)
    if gravity:
        fx.add(at(step, 1), gravity)
    if every:
        fx.call(every)
    fx.ret()
    fx.label(go); fx.call(arrive); fx.set(FRAME, -1); fx.ret()
    return pool


def tail(fx, back):
    """TV = where the flying instance was `back` ticks ago."""
    fx.vcopy(fx.TV2, iv(FREE)); fx.vmul(fx.TV2, back); fx.vcopy(fx.TV, POS); fx.vsub(fx.TV, fx.TV2)


def above(fx, colour, width, height, cell, clut=0):
    """A tall sprite standing over the instance: the wake of something that falls."""
    fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), height // 2 + 20)
    fx.sprite(fx.TV2, colour, width, height, cell=cell, clut=clut)


def blow(fx):
    fx.label('blow'); fx.aim(); fx.hit(); fx.ret()


# ----------------------------------------------------------------- Digmon
def gold_rush():
    """Digmon's three drills spin up, throwing sparks, and five golden drill bits fly from them one after another,
    each boring into the target in a ring of light, stone chips and dust."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(GOLD)
    fx.paint(0, drill()); fx.paint(1, drill(2.0)); fx.paint(2, glow(15, 1.3)); fx.paint(3, ring(12, 2.4))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, shard()); fx.paint(6, streak(4)); fx.paint(7, puff(6))
    tint, soft, dull = fx.colour(128, 128, 128), fx.colour(128, 90, 30), fx.colour(120, 100, 60)
    muzzle, side, n = fx.vec(), fx.vec(), fx.var()
    first, gap, flight = 8, 3, 5
    fx.particle('rev', 3, 9, 0, (128, 128, 128), 70, grow=26, spin=50)
    fx.particle('grit', 14, 6, 4, (128, 110, 60), (50, 100), grow=-8, speed=22, spread=60)
    fx.particle('bore', 3, 7, 4, (128, 120, 70), 260, grow=60, fade=True, spin=70)
    fx.particle('chip', 15, 12, 5, (110, 90, 50), (100, 170), grow=-5, speed=55, lift=45, gravity=10, spread=60,
                spin=25)
    fx.particle('dust', 5, 10, 7, (70, 55, 30), 170, grow=32, lift=8, fade=True, spread=80)
    fx.label('main'); fx.when(0, 'begin')
    fx.br(fx.NOW, '>', first, 'main_run'); fx.emit('grit', muzzle)
    fx.label('main_run')
    ticker(fx, first, first + 4 * gap, gap, 'loose'); fx.when(first + flight + 1, 'blow')
    fx.end(first + 4 * gap + flight + 3)
    fx.label('begin')
    ahead(fx, muzzle, fx.CHEST, 60); forward(fx, fx.TV2, 150); sideways(fx, side, fx.TV2); fx.set(n, 0)
    for k in (-1, 0, 1):
        fx.vcopy(fx.TV, side); fx.vmul(fx.TV, k); fx.vcopy(fx.AT, muzzle); fx.vadd(fx.AT, fx.TV)
        fx.sub_(at(fx.AT, 1), 60 if k == 0 else 0); fx.call('rev')
    fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.lin(fx.T3, n); fx.mod(fx.T3, 3); fx.sub_(fx.T3, 1); fx.add(n, 1)
    fx.vcopy(fx.TV, side); fx.vmul(fx.TV, fx.T3); fx.vcopy(fx.AT, muzzle); fx.vadd(fx.AT, fx.TV)
    fx.aim(); fx.vcopy(fx.DEST, fx.TCHEST); fx.scatter(fx.DEST, 150); fx.call('bit'); fx.sound(4); fx.ret()
    lob(fx, 'bit', 4, flight, 'bit_render', 'bit_arrive', every='bit_trail')
    fx.label('bit_trail'); fx.emit('grit', POS); fx.ret()
    fx.label('bit_render')
    tail(fx, 2); band(fx, fx.TV, POS, 90, dull, 6)
    fx.sprite(POS, soft, 400, cell=2); fx.lin(fx.T2, FRAME, 55); fx.sprite(POS, tint, 290, cell=0, rot=fx.T2)
    fx.ret()
    fx.label('bit_arrive')
    fx.sound(20); fx.emit('bore', POS); fx.emit('chip', times=3); fx.emit('dust'); fx.ret()
    blow(fx)
    return fx


# ----------------------------------------------------------------- Magnamon
def plasma_shot():
    """Magnamon's armour glitters and four knots of golden plasma burst out of it to hang crackling over its
    shoulders; one by one they dart into the target and go off in a cross of light."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(GOLD); fx.palette(PLASMA)
    fx.paint(0, plasma(3)); fx.paint(1, plasma(8)); fx.paint(2, glow(15, 1.3)); fx.paint(3, arc(5))
    fx.paint(4, star(4, 1.5, 14, 12)); fx.paint(5, ring(13, 1.6)); fx.paint(6, star(4, 2, 9, 6)); fx.paint(7, arc(8))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 100, 40)
    place, n = fx.vec(), fx.var()
    pool = fx.pool('orb', 4, 4)
    step, idx = iv(FREE), iv(FREE + 12)
    fx.particle('glint', 10, 6, 6, (128, 128, 128), (90, 170), grow=-10, spread=260)
    fx.particle('wake', 14, 5, 2, (128, 100, 40), 210, grow=-32, fade=True)
    fx.particle('flare', 4, 8, 4, (128, 128, 128), 260, grow=80, fade=True, rot=45)
    fx.particle('halo', 4, 7, 0, (128, 128, 128), 200, grow=70, fade=True, clut=1)
    fx.particle('crackle', 8, 5, 7, (128, 128, 128), (220, 340), spin=90, spread=120)
    fx.particle('fleck', 12, 10, 6, (128, 120, 80), (60, 120), grow=-6, speed=50, lift=20, gravity=6)
    fx.label('main'); fx.when(0, 'begin')
    fx.br(fx.NOW, '>', 4, 'main_run'); fx.emit('glint', fx.CHEST, 2)
    fx.label('main_run')
    ticker(fx, 3, 6, 1, 'launch'); fx.when(16, 'blow'); fx.end(28)
    fx.label('begin'); fx.set(n, 0); fx.sound(-55); fx.ret()
    fx.label('launch')
    fx.lin(fx.T3, n, 1024, 512); fx.circle(place, fx.T3, 270, 0); fx.vadd(place, fx.CHEST)
    fx.lin(fx.T3, n, 60, 170); fx.sub_(at(place, 1), fx.T3)
    fx.call('orb'); fx.add(n, 1); fx.sound(34); fx.ret()
    fx.begin('orb', pool, 'orb_render', inherit=False)
    fx.vcopy(POS, fx.CHEST); fx.vcopy(step, place); fx.vsub(step, POS); fx.vdiv(step, 4); fx.set(idx, n); fx.ret()
    fx.label('orb_tick')
    fx.br(FRAME, '>=', 4, 'orb_hold'); fx.vadd(POS, step); fx.ret()
    fx.label('orb_hold')
    fx.lin(fx.T2, idx, 2, 8)
    fx.br(FRAME, '>', fx.T2, 'orb_fly'); fx.br(FRAME, '<', fx.T2, 'noop')
    fx.aim(); fx.vcopy(step, fx.TCHEST); fx.vsub(step, POS); fx.vdiv(step, 4); fx.sound(3); fx.ret()
    fx.label('orb_fly')
    fx.lin(fx.T2, idx, 2, 12); fx.br(FRAME, '>', fx.T2, 'orb_land')
    fx.vadd(POS, step); fx.emit('wake', POS); fx.ret()
    fx.label('orb_land')
    fx.sound(7); fx.emit('flare', POS); fx.emit('halo'); fx.emit('crackle', times=2); fx.emit('fleck', times=3)
    fx.set(FRAME, -1); fx.ret()
    fx.label('orb_render')
    fx.sprite(POS, soft, 440, cell=2); flicker(fx, POS, tint, 300, (0, 1), clut=1, every=1)
    fx.lin(fx.T2, FRAME, 75); fx.sprite(POS, tint, 360, cell=3, rot=fx.T2); fx.ret()
    blow(fx)
    return fx


# ----------------------------------------------------------------- Paildramon
def desperado_blaster():
    """Paildramon's two hip guns fire in turn, twelve blue tracers in a row with a flash at the muzzle and a spent
    case flung from every shot; each one flares and sparks on the target, and a last star bursts there."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(BLUEFIRE); fx.palette(GOLD)
    fx.paint(0, streak(4)); fx.paint(1, star(6, 2, 13, 5)); fx.paint(2, glow(15, 1.3)); fx.paint(3, ring(13, 1.6))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, round_shot()); fx.paint(6, segment(11, 16, 21, 16, 2.6))
    fx.paint(7, puff(4))
    tint, soft = fx.colour(128, 128, 128), fx.colour(60, 110, 128)
    gunl, gunr, side, n = fx.vec(), fx.vec(), fx.vec(), fx.var()
    fx.particle('flash', 4, 2, 1, (128, 128, 128), (280, 380), spin=60)
    fx.particle('case', 8, 10, 6, (128, 128, 128), 80, speed=18, lift=45, gravity=10, spin=40, clut=1)
    fx.particle('ping', 6, 5, 4, (128, 128, 128), 200, grow=50, fade=True, spin=30)
    fx.particle('pow', 6, 4, 2, (128, 128, 128), 260, grow=55, fade=True)
    fx.particle('spark', 16, 8, 4, (128, 128, 128), (100, 170), grow=-7, speed=55, lift=15, gravity=6)
    fx.particle('smoke', 4, 12, 7, (30, 50, 70), 150, grow=25, lift=10, fade=True)
    fx.particle('nova', 2, 8, 1, (128, 128, 128), 260, grow=90, fade=True)
    fx.label('main'); fx.when(0, 'begin'); ticker(fx, 2, 24, 2, 'fire'); fx.when(6, 'blow'); fx.when(27, 'finale')
    fx.end(30)
    fx.label('begin')
    forward(fx, fx.TV2, 130); sideways(fx, side, fx.TV2)
    fx.vcopy(gunl, fx.CHEST); fx.vadd(gunl, side); fx.vcopy(gunr, fx.CHEST); fx.vsub(gunr, side)
    fx.lin(fx.T3, at(fx.SSIZE, 1), 2, 0, 10); fx.add(at(gunl, 1), fx.T3); fx.add(at(gunr, 1), fx.T3)
    ahead(fx, gunl, gunl, 30); ahead(fx, gunr, gunr, 30); fx.set(n, 0); fx.ret()
    fx.label('fire')
    fx.lin(fx.T3, n); fx.mod(fx.T3, 2); fx.add(n, 1); fx.br(fx.T3, '!=', 0, 'fire_right')
    fx.vcopy(fx.AT, gunl); fx.jmp('fire_go')
    fx.label('fire_right'); fx.vcopy(fx.AT, gunr)
    fx.label('fire_go')
    fx.call('flash'); fx.call('case'); fx.aim(); fx.vcopy(fx.DEST, fx.TCHEST); fx.scatter(fx.DEST, 160)
    fx.call('slug'); fx.sound(4); fx.ret()
    lob(fx, 'slug', 3, 3, 'slug_render', 'slug_arrive')
    fx.label('slug_render')
    tail(fx, 2); band(fx, fx.TV, POS, 75, tint, 0); fx.sprite(POS, tint, 230, cell=2); fx.ret()
    fx.label('slug_arrive'); fx.emit('ping', POS); fx.emit('pow'); fx.emit('spark', times=2); fx.sound(20); fx.ret()
    fx.label('finale')
    fx.aim(); fx.emit('nova', fx.TCHEST); fx.emit('smoke', gunl); fx.emit('smoke', gunr); fx.sound(7); fx.ret()
    blow(fx)
    return fx


# ----------------------------------------------------------------- Pegasusmon
def star_shower():
    """Glitter rises from Pegasusmon into the sky, a point of light opens over the target, and six golden stars fall
    from it one after another, turning, each leaving stardust and bouncing little stars off the ground."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(GOLD); fx.palette(STARLIGHT)
    fx.paint(0, five_star()); fx.paint(1, star(4, 1.2, 15, 14)); fx.paint(2, glow(15, 1.3))
    fx.paint(3, five_star(0.0, 9.0, 4.0)); fx.paint(4, ring(13, 1.8)); fx.paint(5, fall_tail(3))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 100, 50)
    sky = fx.vec()
    fx.particle('rise', 12, 8, 1, (128, 128, 128), (70, 130), grow=-4, flat=((-12, 12), (-120, -80), (-12, 12)),
                spread=200, clut=1)
    fx.particle('nova', 1, 24, 1, (128, 128, 128), 220, grow=14, spin=9, clut=1)
    fx.particle('dust', 16, 7, 3, (128, 128, 128), (50, 90), grow=-7, speed=10, gravity=3, spread=70, spin=30)
    fx.particle('pop', 3, 7, 1, (128, 128, 128), 180, grow=65, fade=True)
    fx.particle('ripple', 3, 8, 4, (128, 110, 60), 130, grow=75, fade=True, sy=6)
    fx.particle('hop', 15, 12, 3, (128, 128, 128), (70, 120), grow=-3, speed=45, lift=60, gravity=12, spin=30)
    fx.label('main'); fx.when(0, 'begin')
    fx.br(fx.NOW, '>', 4, 'main_run'); fx.emit('rise', fx.CHEST, 2)
    fx.label('main_run')
    fx.when(4, 'open'); ticker(fx, 7, 22, 3, 'fall'); fx.when(14, 'blow'); fx.end(31)
    fx.label('begin'); fx.sound(-55); fx.ret()
    fx.label('open')
    fx.aim(); fx.vcopy(sky, fx.TGT); fx.sub_(at(sky, 1), 1050); fx.emit('nova', sky); fx.sound(34); fx.ret()
    fx.label('fall')
    fx.aim(); fx.vcopy(fx.AT, sky); fx.scatter(fx.AT, 300)
    fx.vcopy(fx.DEST, fx.TGT); fx.scatter(fx.DEST, 220); fx.lin(at(fx.DEST, 1), at(fx.TGT, 1), 1, -40)
    fx.call('star'); fx.sound(34); fx.ret()
    lob(fx, 'star', 4, 6, 'star_render', 'star_arrive', every='star_trail')
    fx.label('star_trail'); fx.emit('dust', POS); fx.ret()
    fx.label('star_render')
    above(fx, soft, 180, 560, 5); fx.sprite(POS, soft, 380, cell=2)
    fx.lin(fx.T2, FRAME, 35); fx.sprite(POS, tint, 270, cell=0, rot=fx.T2); fx.ret()
    fx.label('star_arrive')
    fx.sound(20); fx.emit('pop', POS); fx.emit('ripple'); fx.emit('hop', times=3); fx.ret()
    blow(fx)
    return fx


# ----------------------------------------------------------------- Seraphimon
def seventh_heaven():
    """Seven orbs of light appear one by one on a wheel that turns behind Seraphimon; each leaves the wheel in turn
    and strikes the target in a cross of rays, and with the seventh a pillar of light comes down on it among
    falling feathers."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(GOLD); fx.palette(ICE)
    fx.paint(0, holy()); fx.paint(1, glow(15, 1.3)); fx.paint(2, ring(13, 1.5)); fx.paint(3, star(4, 1.5, 15, 12))
    fx.paint(4, column(9)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, petal()); fx.paint(7, petal(True))
    tint, soft, wash = fx.colour(128, 128, 128), fx.colour(128, 100, 50), fx.vec()
    side, n = fx.vec(), fx.var()
    pool, beam = fx.pool('orb', 7, 4), fx.pool('pillar', 1, 0)
    step, idx = iv(FREE), iv(FREE + 12)
    first, gap, flight = 9, 2, 4
    last = first + 6 * gap + flight
    fx.particle('aura', 2, 10, 2, (128, 110, 70), 300, grow=60, fade=True)
    fx.particle('trail', 12, 5, 1, (128, 100, 50), 200, grow=-30, fade=True)
    fx.particle('flare', 4, 7, 3, (128, 128, 128), 240, grow=70, fade=True)
    fx.particle('halo', 4, 7, 1, (128, 110, 60), 220, grow=60, fade=True)
    fx.particle('mote', 14, 9, 5, (128, 128, 128), (60, 120), grow=-6, speed=45, lift=25, gravity=5)
    fx.particle('feather', 5, 18, 6, (128, 128, 128), (110, 160), flat=((-20, 20), (22, 40), (-20, 20)), spread=420,
                spin=7, clut=1, fade=True)
    fx.particle('plume', 5, 18, 7, (128, 128, 128), (110, 160), flat=((-20, 20), (22, 40), (-20, 20)), spread=420,
                spin=-7, clut=1, fade=True)
    fx.label('main'); fx.when(0, 'begin'); ticker(fx, 0, 6, 1, 'summon'); fx.when(last + 1, 'blow')
    fx.end(last + 3)
    fx.label('begin')
    forward(fx, fx.TV2, 100); sideways(fx, side, fx.TV2); fx.set(n, 0); fx.emit('aura', fx.CHEST); fx.ret()
    fx.label('summon'); fx.call('orb'); fx.add(n, 1); fx.sound(34); fx.ret()
    fx.label('on_wheel')                    # the orb's place on the wheel now
    fx.lin(fx.T, idx, 585); fx.lin(fx.T2, fx.NOW, 150); fx.add(fx.T, fx.T2)
    fx.cos(fx.T2, fx.T, 250); fx.vcopy(fx.TV, side); fx.vmul(fx.TV, fx.T2); fx.vdiv(fx.TV, 100)
    fx.sin(fx.T2, fx.T, 250); fx.vcopy(POS, fx.CHEST); fx.vadd(POS, fx.TV)
    fx.sub_(at(POS, 1), fx.T2); fx.sub_(at(POS, 1), 30); fx.ret()
    fx.begin('orb', pool, 'orb_render', inherit=False)
    fx.set(idx, n); fx.call('on_wheel'); fx.ret()
    fx.label('orb_tick')
    fx.lin(fx.T3, idx, gap, first)
    fx.br(fx.NOW, '>', fx.T3, 'orb_fly'); fx.br(fx.NOW, '==', fx.T3, 'orb_go'); fx.call('on_wheel'); fx.ret()
    fx.label('orb_go')
    fx.aim(); fx.vcopy(step, fx.TCHEST); fx.vsub(step, POS); fx.vdiv(step, flight); fx.sound(3); fx.ret()
    fx.label('orb_fly')
    fx.lin(fx.T3, idx, gap, first + flight); fx.br(fx.NOW, '>', fx.T3, 'orb_land')
    fx.vadd(POS, step); fx.emit('trail', POS); fx.ret()
    fx.label('orb_land')
    fx.sound(7); fx.emit('flare', POS); fx.emit('halo'); fx.emit('mote', times=2)
    fx.br(idx, '!=', 6, 'orb_done')
    fx.aim(); fx.vcopy(fx.AT, fx.TGT); fx.call('pillar')
    fx.vcopy(fx.AT, fx.TCHEST); fx.sub_(at(fx.AT, 1), 520); fx.call('feather', 5); fx.call('plume', 5)
    fx.label('orb_done'); fx.set(FRAME, -1); fx.ret()
    fx.label('orb_render'); fx.sprite(POS, soft, 330, cell=1); fx.sprite(POS, tint, 250, cell=0); fx.ret()
    fx.begin('pillar', beam, 'pillar_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.sound(48); fx.ret()
    fx.label('pillar_tick'); fx.life(10); fx.ret()
    fx.label('pillar_render')
    fx.lin(fx.T3, FRAME, -11, 128); fx.vset(wash, fx.T3, fx.T3, fx.T3)
    fx.lin(fx.T3, FRAME, -22, 420); fx.pillar(POS, fx.T3, 1700, wash, cell=4, clut=1)
    fx.pillar(POS, 300, 300, wash, cell=1); fx.ret()
    blow(fx)
    return fx


# ----------------------------------------------------------------- Togemon
def needle_spray():
    """Togemon spins into a green blur bristling with spines and needles fly off it all round; six bunches of them
    go straight at the target and prick it."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(CACTUS)
    fx.paint(0, whirl(0.0)); fx.paint(1, whirl(1.6)); fx.paint(2, needle()); fx.paint(3, star(12, 1.0, 14, 24))
    fx.paint(4, glow(15, 1.3)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 1.6))
    fx.paint(7, segment(8, 24, 24, 8, 1.3))
    tint, green, pale = fx.colour(128, 128, 128), fx.colour(70, 128, 60), fx.colour(110, 128, 90)
    place = fx.vec()
    spin = fx.pool('spin', 1, 0)
    fx.particle('prick', 8, 5, 5, (128, 128, 128), (190, 270), grow=-14, spread=60)
    fx.particle('ping', 4, 5, 4, (70, 128, 60), 200, grow=50, fade=True)
    fx.particle('splinter', 14, 9, 7, (128, 128, 128), (110, 170), grow=-5, speed=40, lift=30, gravity=8, spin=40)
    fx.label('main'); fx.when(0, 'begin'); ticker(fx, 2, 20, 1, 'stray_out'); ticker(fx, 4, 19, 3, 'volley')
    fx.when(9, 'blow'); fx.end(26)
    fx.label('begin'); fx.emit('spin', fx.CHEST); fx.sound(-55); fx.ret()
    fx.begin('spin', spin, 'spin_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('spin_tick'); fx.life(23); fx.ret()
    fx.label('spin_render')
    fx.sprite(POS, green, 460, cell=4)
    fx.lin(fx.T3, FRAME, -45); fx.sprite(POS, pale, 640, cell=3, rot=fx.T3)
    fx.lin(fx.T3, FRAME, 70)
    flicker(fx, POS, tint, 560, (0, 1), every=1)
    fx.ret()
    fx.label('stray_out')
    fx.lin(fx.T3, fx.NOW, 700); fx.circle(place, fx.T3, 700, 0); fx.vadd(place, fx.CHEST)
    fx.rnd(fx.T, -220, 120); fx.add(at(place, 1), fx.T)
    fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, place); fx.call('stray'); fx.ret()
    lob(fx, 'stray', 6, 5, 'quill_render', 'noop')
    fx.label('volley')
    fx.aim()
    for _ in range(3):
        fx.vcopy(fx.AT, fx.CHEST); fx.scatter(fx.AT, 140)
        fx.vcopy(fx.DEST, fx.TCHEST); fx.scatter(fx.DEST, 180); fx.call('quill')
    fx.sound(4); fx.ret()
    lob(fx, 'quill', 8, 4, 'quill_render', 'quill_arrive')
    fx.label('quill_render'); tail(fx, 2); band(fx, fx.TV, POS, 45, tint, 2); fx.ret()
    fx.label('quill_arrive'); fx.emit('prick', POS); fx.emit('ping'); fx.emit('splinter', times=2); fx.sound(20)
    fx.ret()
    blow(fx)
    return fx


# ----------------------------------------------------------------- Gomamon
def marching_fishes():
    """Water breaks open along the ground between Gomamon and its target and five fish, blue and orange, leap out
    of it one after another, turn over in the air and smack into the target in a burst of spray."""
    fx = Fx(delay=8, cast_sound=36)
    fx.palette(SEA); fx.palette(REEF)
    fx.paint(0, fish()); fx.paint(1, crown()); fx.paint(2, droplet()); fx.paint(3, ring(13, 1.6))
    fx.paint(4, glow(15, 1.3)); fx.paint(5, puff(5)); fx.paint(6, fish(1.35)); fx.paint(7, round_shot())
    tint = fx.colour(128, 128, 128)
    path, place, n = fx.vec(), fx.vec(), fx.var()
    kind = iv(FREE + 12)
    fx.particle('crown', 4, 6, 1, (128, 128, 128), 230, grow=40, fade=True, sy=20, blend='add')
    fx.particle('drop', 20, 10, 2, (128, 128, 128), (60, 100), speed=35, lift=60, gravity=12, spread=60)
    fx.particle('ripple', 4, 7, 3, (60, 100, 128), 110, grow=60, fade=True, sy=5)
    fx.particle('smack', 3, 6, 5, (128, 128, 128), 220, grow=60, fade=True)
    fx.particle('bubble', 8, 10, 7, (128, 128, 128), (60, 100), speed=12, lift=20, spread=100)
    fx.particle('drip', 10, 5, 2, (128, 128, 128), 60, gravity=8)
    fx.particle('flop', 3, 12, 0, (128, 128, 128), 210, grow=-8, speed=30, lift=60, gravity=14, spin=30, blend=None)
    fx.label('main'); fx.when(0, 'begin'); ticker(fx, 2, 14, 3, 'leap'); fx.when(10, 'blow'); fx.end(24)
    fx.label('begin')
    fx.vcopy(path, fx.TGT); fx.vsub(path, fx.SRC); fx.set(at(path, 1), 0); fx.set(n, 0); fx.ret()
    fx.label('leap')
    fx.aim(); fx.lin(fx.T3, n, 1, 2); fx.add(n, 1)
    fx.vcopy(place, path); fx.vmul(place, fx.T3); fx.vdiv(place, 7); fx.vadd(place, fx.SRC)
    fx.emit('ripple', place); fx.sub_(at(fx.AT, 1), 90); fx.call('crown'); fx.call('drop', 3)
    fx.vcopy(fx.AT, place); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('fish'); fx.sound(37); fx.ret()
    lob(fx, 'fish', 4, 7, 'fish_render', 'fish_arrive', gravity=50, every='fish_trail', fields=1,
        setup=lambda: fx.set(kind, n))
    fx.label('fish_trail'); fx.emit('drip', POS); fx.ret()
    fx.label('fish_render')
    fx.lin(fx.T2, FRAME, 26); fx.lin(fx.T, kind); fx.mod(fx.T, 2); fx.br(fx.T, '!=', 0, 'fish_other')
    fx.sprite(POS, tint, 340, cell=0, blend=None, rot=fx.T2); fx.ret()
    fx.label('fish_other'); fx.sprite(POS, tint, 340, cell=6, clut=1, blend=None, rot=fx.T2); fx.ret()
    fx.label('fish_arrive')
    fx.sound(40); fx.emit('smack', POS); fx.emit('drop', times=3); fx.emit('bubble', times=2); fx.emit('flop')
    fx.ret()
    blow(fx)
    return fx


# ----------------------------------------------------------------- LadyDevimon
def darkness_wave():
    """The light dims around LadyDevimon and dark wisps rise from it; ten black bats with lit eyes flap out of the
    dark one after another, weaving, bite the target in violet slashes and scatter upwards."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(NIGHT); fx.palette(VIOLET)
    fx.paint(0, bat(True)); fx.paint(1, bat(False)); fx.paint(2, glow(15, 1.3)); fx.paint(3, puff(7))
    fx.paint(4, slash(0.5)); fx.paint(5, ring(13, 1.6)); fx.paint(6, star(4, 2, 9, 6)); fx.paint(7, slash(-0.9))
    tint = fx.colour(128, 128, 128)
    phase = iv(FREE + 12)
    fx.particle('gloom', 3, 14, 2, (70, 110, 50), 420, grow=50, fade=True, blend='sub')
    fx.particle('wisp', 12, 9, 3, (90, 40, 110), (170, 270), grow=10, flat=((-15, 15), (-55, -25), (-15, 15)),
                spread=260, clut=1, fade=True)
    fx.particle('bite', 4, 5, 4, (128, 128, 128), (260, 340), spin=12, clut=1)
    fx.particle('gash', 4, 5, 7, (128, 128, 128), (260, 340), spin=-12, clut=1)
    fx.particle('fang', 12, 8, 6, (128, 128, 128), (70, 120), grow=-8, speed=50, gravity=4, clut=1)
    fx.particle('flee', 8, 12, 0, (128, 128, 128), 270, grow=-12, flat=((-60, 60), (-95, -45), (-60, 60)),
                blend=None)
    fx.label('main'); fx.when(0, 'begin')
    fx.br(fx.NOW, '>', 9, 'main_run'); fx.emit('wisp', fx.CHEST)
    fx.label('main_run')
    fx.when(5, 'begin'); ticker(fx, 3, 21, 2, 'loose'); fx.when(12, 'blow'); fx.end(32)
    fx.label('begin'); fx.emit('gloom', fx.CHEST); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.aim(); fx.vcopy(fx.AT, fx.CHEST); fx.scatter(fx.AT, 220)
    fx.vcopy(fx.DEST, fx.TCHEST); fx.scatter(fx.DEST, 130); fx.call('bat'); fx.sound(15); fx.ret()
    lob(fx, 'bat', 6, 8, 'bat_render', 'bat_arrive', every='bat_weave', fields=1,
        setup=lambda: fx.rnd(phase, 0, 4095))
    fx.label('bat_weave')
    fx.lin(fx.T2, FRAME, 1024); fx.add(fx.T2, phase)
    fx.sin(fx.T, fx.T2, 65); fx.add(at(POS, 1), fx.T); fx.cos(fx.T, fx.T2, 45); fx.add(at(POS, 0), fx.T); fx.ret()
    fx.label('bat_render'); flicker(fx, POS, tint, 350, (0, 1), blend=None, every=1); fx.ret()
    fx.label('bat_arrive')
    fx.sound(20); fx.lin(fx.T3, phase); fx.mod(fx.T3, 2); fx.br(fx.T3, '!=', 0, 'bat_gash')
    fx.emit('bite', POS); fx.jmp('bat_off')
    fx.label('bat_gash'); fx.emit('gash', POS)
    fx.label('bat_off'); fx.emit('fang', times=2); fx.emit('flee'); fx.ret()
    blow(fx)
    return fx


# ----------------------------------------------------------------- Baronmon
def dancing_meteor():
    """Flames whirl round Baronmon as it dances, and five burning rocks come down out of the sky in a spiral that
    closes on the spot where its target stands, each bursting there in fire. Whoever is still on the spot when
    the first lands is hit."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(STONE); fx.palette(FIRE)
    fx.paint(0, rock(3)); fx.paint(1, rock(11)); fx.paint(2, tongue()); fx.paint(3, fireball(5))
    fx.paint(4, glow(15, 1.3)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.0)); fx.paint(7, puff(9))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 70, 30)
    spot, n = fx.vec(), fx.var()
    pool = fx.pool('meteor', 5, 1)
    phase = iv(FREE)
    first, gap, flight = 4, 3, 10
    fx.particle('whirl', 12, 8, 2, (128, 100, 50), (150, 230), grow=-8, lift=35, clut=1, fade=True)
    fx.particle('flame', 14, 5, 3, (128, 90, 50), 220, grow=-32, lift=10, clut=1, fade=True)
    fx.particle('ember', 16, 10, 5, (128, 110, 60), (60, 110), grow=-4, speed=22, gravity=4, clut=1)
    fx.particle('boom', 3, 8, 3, (128, 128, 128), 240, grow=85, fade=True, clut=1)
    fx.particle('lick', 10, 9, 2, (128, 100, 50), (170, 270), grow=-12, flat=((-25, 25), (-70, -30), (-25, 25)),
                spread=150, clut=1)
    fx.particle('rubble', 10, 12, 1, (128, 128, 128), (60, 100), grow=-3, speed=45, lift=55, gravity=11, spin=25,
                blend=None)
    fx.label('main'); fx.when(0, 'begin')
    fx.br(fx.NOW, '>', 7, 'main_run')
    fx.lin(fx.T3, fx.NOW, 680); fx.circle(fx.TV, fx.T3, 270, 0); fx.vadd(fx.TV, fx.SRC); fx.emit('whirl', fx.TV)
    fx.lin(fx.T3, fx.NOW, 680, 2048); fx.circle(fx.TV, fx.T3, 270, 0); fx.vadd(fx.TV, fx.SRC); fx.emit('whirl', fx.TV)
    fx.label('main_run')
    ticker(fx, first, first + 4 * gap, gap, 'call_down'); fx.when(first + flight + 1, 'impact')
    fx.end(first + 4 * gap + flight + 3)
    fx.label('begin'); fx.vcopy(spot, fx.TGT); fx.set(n, 0); fx.sound(-55); fx.ret()
    fx.label('call_down'); fx.call('meteor'); fx.add(n, 1); fx.sound(34); fx.ret()
    fx.label('helix')                       # the rock's place on its spiral now
    fx.lin(fx.T, FRAME, 380); fx.add(fx.T, phase)
    fx.lin(fx.T2, FRAME, -46, 460); fx.br(fx.T2, '>=', 0, 'helix_ok'); fx.set(fx.T2, 0)
    fx.label('helix_ok')
    fx.circle(POS, fx.T, fx.T2, 0); fx.vadd(POS, spot)
    fx.lin(fx.T2, FRAME, 115, -1150); fx.br(fx.T2, '<=', 0, 'helix_up'); fx.set(fx.T2, 0)
    fx.label('helix_up'); fx.add(at(POS, 1), fx.T2); fx.sub_(at(POS, 1), 60); fx.ret()
    fx.begin('meteor', pool, 'meteor_render', inherit=False)
    fx.lin(phase, n, 819); fx.call('helix'); fx.ret()
    fx.label('meteor_tick')
    fx.br(FRAME, '>=', flight, 'meteor_land'); fx.call('helix'); fx.emit('flame', POS); fx.emit('ember'); fx.ret()
    fx.label('meteor_land')
    fx.call('helix'); fx.sound(7); fx.emit('boom', POS); fx.emit('lick', times=2); fx.emit('ember', times=2)
    fx.emit('rubble', times=2); fx.set(FRAME, -1); fx.ret()
    fx.label('meteor_render')
    fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), 190); fx.sprite(fx.TV2, soft, 250, 420, cell=2, clut=1)
    fx.sprite(POS, soft, 420, cell=4, clut=1)
    fx.lin(fx.T2, FRAME, 30); fx.sprite(POS, tint, 260, cell=0, blend=None, rot=fx.T2); fx.ret()
    fx.label('impact'); fx.strike(spot, 250); fx.ret()
    return fx


# ----------------------------------------------------------------- Starmon
def meteor_stream():
    """Starmon's star flares and sends a spark up into the sky, where a ring-star opens; out of it pours a slanting
    stream of sixteen small burning stars, each with a tail of fire, that pop on the target one after another."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(PLASMA); fx.palette(GOLD)
    fx.paint(0, five_star()); fx.paint(1, five_star(hollow=True)); fx.paint(2, glow(15, 1.3)); fx.paint(3, streak(6))
    fx.paint(4, star(5, 2, 13, 5)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.0))
    fx.paint(7, five_star(0.0, 9.0, 4.0))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 80, 40)
    gate = fx.vec()
    door = fx.pool('gate', 1, 0)
    fx.particle('crest', 2, 7, 1, (128, 128, 128), 220, grow=65, fade=True, spin=12, clut=1)
    fx.particle('pop', 6, 5, 4, (128, 128, 128), (200, 280), grow=30, fade=True, spin=20)
    fx.particle('spark', 16, 8, 5, (128, 128, 128), (70, 120), grow=-6, speed=50, lift=20, gravity=7)
    fx.particle('cinder', 8, 12, 7, (128, 128, 128), (80, 120), speed=35, lift=50, gravity=11, spin=30, clut=1)
    fx.particle('shock', 2, 8, 4, (128, 128, 128), 320, grow=95, fade=True, spin=14)
    fx.label('main'); fx.when(0, 'begin'); fx.when(2, 'send'); ticker(fx, 7, 22, 1, 'pour'); fx.when(13, 'blow')
    fx.when(27, 'closing'); fx.end(29)
    fx.label('begin')
    fx.emit('crest', fx.CHEST); fx.vcopy(gate, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), 1, 420)
    fx.sub_(at(gate, 1), fx.T3); forward(fx, fx.TV2, 120); fx.vadd(gate, fx.TV2); fx.sound(-55); fx.ret()
    fx.label('send'); fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, gate); fx.call('signal'); fx.sound(3); fx.ret()
    lob(fx, 'signal', 1, 4, 'signal_render', 'signal_arrive')
    fx.label('signal_render'); fx.sprite(POS, soft, 300, cell=2); fx.sprite(POS, tint, 200, cell=5); fx.ret()
    fx.label('signal_arrive'); fx.emit('gate', POS); fx.sound(34); fx.ret()
    fx.begin('gate', door, 'gate_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('gate_tick'); fx.life(18); fx.ret()
    fx.label('gate_render')
    fx.sprite(POS, soft, 560, cell=2); fx.lin(fx.T2, FRAME, 25)
    fx.sprite(POS, tint, 400, cell=1, clut=1, rot=fx.T2); fx.ret()
    fx.label('pour')
    fx.aim(); fx.vcopy(fx.AT, gate); fx.scatter(fx.AT, 120)
    fx.vcopy(fx.DEST, fx.TCHEST); fx.scatter(fx.DEST, 180); fx.call('bolt'); fx.ret()
    lob(fx, 'bolt', 7, 5, 'bolt_render', 'bolt_arrive')
    fx.label('bolt_render')
    tail(fx, 2); band(fx, fx.TV, POS, 95, soft, 3)
    fx.lin(fx.T2, FRAME, 50); fx.sprite(POS, tint, 270, cell=0, rot=fx.T2); fx.ret()
    fx.label('bolt_arrive'); fx.sound(20); fx.emit('pop', POS); fx.emit('spark', times=2); fx.emit('cinder'); fx.ret()
    fx.label('closing'); fx.aim(); fx.emit('shock', fx.TCHEST); fx.sound(7); fx.ret()
    blow(fx)
    return fx


# ----------------------------------------------------------------- SuperStarmon
def comet_cluster():
    """The sky darkens and six cold lights kindle in a cluster high over the target; they fall together as blue
    comets with long tails onto the spot where it stands and burst there in ice and a white flash. Whoever is
    still on the spot when the first lands is hit."""
    fx = Fx(delay=8, cast_sound=2, draw=True)
    fx.palette(BLUEFIRE); fx.palette(ICE)
    fx.paint(0, comet(3)); fx.paint(1, fall_tail(4)); fx.paint(2, glow(15, 1.3)); fx.paint(3, star(4, 1.2, 15, 14))
    fx.paint(4, ring(13, 2.0)); fx.paint(5, shard()); fx.paint(6, fireball(7)); fx.paint(7, dome())
    tint, soft, wash = fx.colour(128, 128, 128), fx.colour(50, 100, 128), fx.vec()
    spot, sky = fx.vec(), fx.vec()
    first, flight = 8, 7
    fin = first + 5 + flight + 1
    fx.particle('twinkle', 6, 9, 3, (128, 128, 128), 130, grow=14, spin=10, clut=1)
    fx.particle('burst', 6, 7, 6, (128, 128, 128), 220, grow=70, fade=True)
    fx.particle('chip', 18, 12, 5, (128, 128, 128), (70, 130), grow=-5, speed=60, lift=50, gravity=10, spin=20,
                clut=1)
    fx.particle('swell', 3, 9, 6, (128, 128, 128), 340, grow=70, fade=True, lift=14)
    fx.particle('nova', 1, 9, 3, (128, 128, 128), 420, grow=110, fade=True, clut=1, spin=24, rot=45)
    fx.particle('mist', 12, 6, 2, (40, 80, 128), 220, grow=-30, fade=True)
    fx.label('main'); fx.when(0, 'begin'); ticker(fx, 1, 6, 1, 'kindle'); ticker(fx, first, first + 5, 1, 'drop')
    fx.when(first + flight + 1, 'impact'); fx.when(fin, 'finale'); fx.end(fin + 3)
    fx.label('draw')
    fx.br(fx.NOW, '<', 2, 'noop'); fx.br(fx.NOW, '>=', fin, 'draw_flash')
    fx.lin(fx.T, fx.NOW, 7, -14); fx.br(fx.T, '<', 60, 'draw_dim'); fx.set(fx.T, 60)
    fx.label('draw_dim'); fx.vset(wash, fx.T, fx.T, fx.T); fx.overlay(wash, blend='sub'); fx.ret()
    fx.label('draw_flash')
    fx.br(fx.NOW, '>', fin + 5, 'noop')
    fx.lin(fx.T, fx.NOW, -16, 16 * (fin + 6)); fx.lin(fx.T2, fx.T, 1, 0, 2)
    fx.vset(wash, fx.T2, fx.T, fx.T); fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    fx.vcopy(spot, fx.TGT); fx.vcopy(sky, fx.TGT); fx.sub_(at(sky, 1), 1250); fx.sound(-55); fx.ret()
    fx.label('kindle'); fx.vcopy(fx.AT, sky); fx.scatter(fx.AT, 380); fx.call('twinkle'); fx.sound(34); fx.ret()
    fx.label('drop')
    fx.vcopy(fx.AT, sky); fx.scatter(fx.AT, 380)
    fx.vcopy(fx.DEST, spot); fx.scatter(fx.DEST, 320); fx.lin(at(fx.DEST, 1), at(spot, 1), 1, -40)
    fx.call('comet'); fx.sound(3); fx.ret()
    lob(fx, 'comet', 6, flight, 'comet_render', 'comet_arrive', every='comet_trail')
    fx.label('comet_trail'); fx.emit('mist', POS); fx.ret()
    fx.label('comet_render')
    above(fx, soft, 280, 820, 1); fx.sprite(POS, soft, 460, cell=2); fx.sprite(POS, tint, 320, cell=0); fx.ret()
    fx.label('comet_arrive'); fx.sound(7); fx.emit('burst', POS); fx.emit('chip', times=3); fx.ret()
    fx.label('impact'); fx.strike(spot, 250); fx.emit('swell', spot); fx.ret()
    fx.label('finale'); fx.emit('nova', spot); fx.emit('swell', spot); fx.sound(48); fx.ret()
    return fx


# ----------------------------------------------------------------- Assaultmon
def justice_strike():
    """Assaultmon's gatling rattles, a flash at its muzzle and a row of tracers kicking sparks off the target,
    while three rockets climb from its back on smoke, tip over and come down on it in three explosions."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(FIRE); fx.palette(STEEL); fx.palette(SMOKE)
    fx.paint(0, streak(8, 1.0)); fx.paint(1, star(6, 2, 13, 5)); fx.paint(2, missile()); fx.paint(3, glow(15, 1.3))
    fx.paint(4, fireball(13)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.0)); fx.paint(7, puff(15))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 90, 40)
    gun, pod, side = fx.vec(), fx.vec(), fx.vec()
    step = iv(FREE)
    fx.particle('flash', 3, 2, 1, (128, 128, 128), (240, 340), spin=70)
    fx.particle('kick', 10, 6, 5, (128, 110, 60), (120, 190), grow=-10, speed=40, lift=20, gravity=6)
    fx.particle('smoke', 22, 9, 7, (80, 80, 84), (150, 210), grow=14, lift=5, spread=30, clut=2, fade=True)
    fx.particle('blast', 3, 9, 4, (128, 128, 128), 260, grow=95, fade=True)
    fx.particle('shock', 3, 8, 6, (128, 90, 40), 150, grow=105, fade=True)
    fx.particle('shrap', 15, 10, 5, (128, 120, 80), (70, 130), grow=-6, speed=70, lift=30, gravity=8)
    fx.label('main'); fx.when(0, 'begin'); ticker(fx, 1, 11, 1, 'rattle'); ticker(fx, 8, 14, 3, 'launch')
    fx.when(5, 'blow'); fx.end(27)
    fx.label('begin')
    forward(fx, fx.TV2, 110); sideways(fx, side, fx.TV2)
    fx.vcopy(gun, fx.CHEST); fx.vadd(gun, side); ahead(fx, gun, gun, 40)
    fx.vcopy(pod, fx.CHEST); fx.vsub(pod, side); fx.lin(fx.T3, at(fx.SSIZE, 1), 4, 0, 10)
    fx.sub_(at(pod, 1), fx.T3); fx.ret()
    fx.label('rattle')
    fx.aim(); fx.emit('flash', gun); fx.vcopy(fx.DEST, fx.TCHEST); fx.scatter(fx.DEST, 230); fx.call('round')
    fx.lin(fx.T3, fx.NOW); fx.mod(fx.T3, 2); fx.br(fx.T3, '!=', 0, 'noop'); fx.sound(4); fx.ret()
    lob(fx, 'round', 4, 3, 'round_render', 'round_arrive')
    fx.label('round_render'); tail(fx, 2); band(fx, fx.TV, POS, 60, tint, 0); fx.ret()
    fx.label('round_arrive'); fx.emit('kick', POS); fx.ret()
    fx.label('launch')
    fx.aim(); fx.emit('smoke', pod, 2); fx.vcopy(fx.DEST, fx.TCHEST); fx.scatter(fx.DEST, 170); fx.call('rocket')
    fx.sound(3); fx.ret()
    lob(fx, 'rocket', 3, 10, 'rocket_render', 'rocket_arrive', gravity=30, every='rocket_trail')
    fx.label('rocket_trail'); fx.emit('smoke', POS); fx.ret()
    fx.label('rocket_render')
    fx.vcopy(fx.TV2, POS); fx.br(at(step, 1), '>', 0, 'rocket_down')
    fx.add(at(fx.TV2, 1), 150); fx.sprite(fx.TV2, soft, 230, cell=3)
    fx.sprite(POS, tint, 280, cell=2, clut=1, blend=None); fx.ret()
    fx.label('rocket_down')
    fx.sub_(at(fx.TV2, 1), 150); fx.sprite(fx.TV2, soft, 230, cell=3)
    fx.sprite(POS, tint, 280, cell=2, clut=1, blend=None, rot=180); fx.ret()
    fx.label('rocket_arrive')
    fx.sound(7); fx.emit('blast', POS); fx.emit('shock'); fx.emit('shrap', times=4); fx.emit('smoke', times=2)
    fx.ret()
    blow(fx)
    return fx


EFFECTS = {193: gold_rush, 197: plasma_shot, 199: desperado_blaster, 200: star_shower, 207: seventh_heaven,
           208: needle_spray, 217: marching_fishes, 223: darkness_wave, 228: dancing_meteor, 243: meteor_stream,
           244: comet_cluster, 310: justice_strike}
