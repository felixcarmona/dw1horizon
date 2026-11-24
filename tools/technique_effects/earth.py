"""The Earth row's effects."""
from tools.technique_effects.kit import (FRAME, FREE, POS, Fx, at, clip, fbm, glow, grid, iv, noise, polar, ring,
                                         segment)
import numpy as np

BROWN = ['#000000', '#2c1808', '#5c3414', '#9c6428', '#d09c50', '#f4e0b0']
ROCK = ['#000000', '#1c1c20', '#44464c', '#74767c', '#a8aab0', '#dcdcdc']
SHADE = (96, 112, 128)   # what a crack takes from the ground: a little less red, so it darkens to brown


def rock(seed=3, radius=13.0, lump=0.55):
    """A lumpy boulder lit from the upper left: faceted, darker at its rim and its lower right."""
    x, y = grid()
    r, ang = polar(15.5, 15.5)
    # an uneven polygon of six sides (lobes of low order read as a heart at this size)
    side = np.mod(ang + 0.5 * seed, np.pi / 3) - np.pi / 6
    edge = radius * 0.9 / np.cos(side) * (1 + lump * (0.10 * np.sin(2 * ang + seed) + 0.05 * np.sin(5 * ang + 2 * seed)))
    mask = clip((edge - r) / 1.2)
    nx, ny = (x - 15.5) / edge, (y - 15.5) / edge
    nz = np.sqrt(clip(1 - nx * nx - ny * ny))
    lam = clip(-0.5 * nx - 0.6 * ny + 0.62 * nz)
    facet = np.floor(fbm(seed + 9) * 4) / 4
    lum = 0.22 + 0.62 * lam
    lum = lum * 0.72 + 0.38 * facet * lam + 0.1
    lum = lum * (0.55 + 0.45 * clip((edge - r) / 4.0))
    return clip(mask * lum)


def dust(seed=2):
    """A soft cloud of dust, lumpy, brightest in the middle."""
    x, y = grid()
    lum = np.zeros((32, 32))
    for cx, cy, rr in ((16, 16, 10), (9, 18, 7), (23, 18, 7), (13, 11, 7), (21, 12, 6)):
        lum = np.maximum(lum, clip(1.2 - np.hypot(x - cx, (y - cy) * 1.2) / rr) ** 0.7)
    return clip(lum * (0.55 + 0.6 * fbm(seed)))


def crack(seed=4):
    """The shadow of a jagged crack running straight across the cell, level at both ends, so cells run on into one
    another. It is drawn subtracted from the ground: soft at its edges, with nothing lighter than the ground."""
    x, y = grid()
    r = np.random.RandomState(seed)
    xs = np.linspace(0, 32, 9)
    ys = 16 + r.uniform(-4.5, 4.5, 9) * np.sin(np.pi * xs / 32)
    yc = np.interp(x[0], xs, ys)[None, :] + 0 * y
    width = 0.7 + 1.5 * noise(32, 32, 8, seed)
    return clip(1.1 - (np.abs(y - yc) - width) / 2.2) ** 1.4 * (np.abs(y - yc) < width + 2.4)


def star_crack(seed=6):
    """The shadow of cracks fanning out from a hole in the middle, each thinning to nothing; drawn subtracted."""
    x, y = grid()
    r = np.random.RandomState(seed)
    dark = np.zeros((32, 32))
    for k in range(6):
        a = k * np.pi / 3 + r.uniform(-0.25, 0.25)
        px, py = 16.0, 16.0
        for step in range(4):
            a2 = a + r.uniform(-0.5, 0.5)
            ln = r.uniform(3.0, 4.6)
            qx, qy = px + ln * np.cos(a2), py + ln * np.sin(a2)
            t = np.clip(((x - px) * (qx - px) + (y - py) * (qy - py)) / (ln * ln), 0, 1)
            d = np.hypot(x - (px + t * (qx - px)), y - (py + t * (qy - py)))
            w = 1.5 - 0.42 * (step + t)
            dark = np.maximum(dark, clip(1.0 - (d - w) / 1.8) * (0.95 - 0.16 * (step + t)))
            px, py = qx, qy
    hole = clip(1.25 - np.hypot(x - 16, y - 16) / 4.6)
    return clip(np.maximum(dark, hole)) ** 1.3


def spike(seed=5):
    """A spire of rock standing on its base: an uneven outline, a lit face and a dark one either side of a ridge
    that wanders, facets, and a dark rim, as the boulders have. No outline lighter than the stone."""
    x, y = grid()
    t = y / 31
    r = np.random.RandomState(seed)
    rows = np.arange(32)
    jl = np.interp(rows, np.linspace(0, 31, 7), r.uniform(-1.6, 1.6, 7))[:, None] * t
    jr = np.interp(rows, np.linspace(0, 31, 7), r.uniform(-1.6, 1.6, 7))[:, None] * t
    hw = 0.7 + 11.0 * t ** 0.9
    left, right = 15.5 - hw + jl, 15.5 + hw + jr
    inside = np.minimum(x - left, right - x)
    ridge = 15.5 + (jl + jr) + 2.2 * np.sin(y * 0.33 + seed) * t - 1.5 * t
    lum = np.where(x < ridge, 0.76, 0.42)
    lum = lum + 0.16 * clip(1 - np.abs(ridge - 0.8 - x) / 1.2) * (x < ridge)
    lum = lum + 0.2 * (np.floor(fbm(seed + 3) * 4) / 4 - 0.4)
    lum = lum * (1.0 - 0.3 * t) * (0.62 + 0.38 * clip(inside / 2.6))
    return clip((inside > 0) * np.clip(lum, 0.16, 1))


def paint_all(fx, cells):
    for cell, lum in cells.items():
        fx.paint(cell, lum)


def tumbler(fx, name, count, life, cell, size, speed, lift, gravity, spread, spin, gnd, tint, drift=None):
    """Define the routine `name`: a solid stone born at AT, thrown at random, tumbling and bouncing on the ground
    (the height in the variable `gnd`), drawn opaque, and shrinking away over its last ticks."""
    pool = fx.pool(name, count, 5)
    vel, sz, ang = iv(FREE), iv(FREE + 12), iv(FREE + 16)
    air, keep = fx.label(), fx.label()
    fx.begin(name, pool, name + '_render', inherit=False)
    fx.vcopy(POS, fx.AT)
    if spread:
        fx.scatter(POS, spread)
    for k in range(3):
        fx.rnd(at(vel, k), -speed, speed)
    fx.sub_(at(vel, 1), lift)
    if drift:
        fx.vadd(vel, drift)
    if isinstance(size, tuple):
        fx.rnd(sz, *size)
    else:
        fx.set(sz, size)
    fx.rnd(ang, 0, 359)
    fx.ret()
    fx.label(name + '_tick')
    fx.life(life)
    fx.vadd(POS, vel); fx.add(at(vel, 1), gravity)
    fx.br(at(POS, 1), '<=', gnd, air)
    fx.set(at(POS, 1), gnd); fx.lin(at(vel, 1), at(vel, 1), -1, 0, 2)
    fx.label(air)
    fx.add(ang, spin)
    fx.br(FRAME, '<', life - 2, keep)
    fx.lin(sz, sz, 2, 0, 3)
    fx.label(keep)
    fx.ret()
    fx.label(name + '_render')
    fx.sprite(POS, tint, sz, cell=cell, clut=1 if cell == 0 else 0, blend=None, rot=ang)
    fx.ret()
    return pool


def rock_throw():
    """A rock is thrown in an arc from the caster to where the target stands and breaks into pebbles and dust there."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(BROWN); fx.palette(ROCK)
    paint_all(fx, {0: rock(3), 1: rock(11, 10.0), 2: dust(2)})
    tint, gnd = fx.colour(128, 128, 128), fx.var()
    fx.particle('puff', 8, 9, 2, (128, 118, 100), 150, grow=34, speed=14, spread=80, blend='half')
    fx.particle('haze', 4, 8, 2, (70, 56, 36), 240, grow=30, fade=True)
    tumbler(fx, 'chip', 12, 13, 1, (70, 130), 40, 45, 8, 60, 16, gnd, tint)
    fx.label('main'); fx.when(0, 'throw'); fx.end(1)
    fx.label('throw')
    fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('rock'); fx.emit('puff', fx.CHEST); fx.ret()
    fx.travel('rock', 1, 12, 'rock_render', 'rock_land', every='rock_trail')
    fx.label('rock_arc')                      # TV: where the rock is drawn, up on its arc
    fx.vcopy(fx.TV, POS)
    fx.lin(fx.T, FRAME, 171); fx.sin(fx.T2, fx.T, 420); fx.sub_(at(fx.TV, 1), fx.T2); fx.ret()
    fx.label('rock_trail')
    fx.call('rock_arc'); fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '!=', 0, 'noop')
    fx.emit('puff', fx.TV); fx.ret()
    fx.label('rock_render')
    fx.call('rock_arc'); fx.lin(fx.T3, FRAME, 40)
    fx.sprite(fx.TV, tint, 270, cell=0, clut=1, rot=fx.T3, blend=None); fx.ret()
    fx.label('rock_land')
    fx.sound(40); fx.strike(POS, 140); fx.set(gnd, at(fx.TGT, 1))
    fx.emit('haze', POS); fx.emit('puff', times=3); fx.emit('chip', times=10); fx.ret()
    return fx


def sand_blast():
    """A wide stream of sand and dust is blown from the caster over every enemy and swirls round their heads:
    they are confused."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(BROWN); fx.palette(ROCK)
    paint_all(fx, {1: rock(11, 10.0), 2: dust(2), 6: ring(13, 2.0)})
    tint, drift = fx.colour(128, 128, 128), fx.vec()
    fx.particle('grain', 30, 10, 1, (128, 128, 128), (36, 70), speed=28, spread=260, drift=drift, spin=20,
                blend=None, clut=0)
    fx.particle('cloud', 10, 14, 2, (128, 118, 100), (200, 320), grow=22, speed=12, spread=240, drift=drift,
                blend='half', spin=3)
    fx.particle('hang', 12, 18, 2, (128, 118, 100), (240, 360), grow=10, speed=8, spread=300, blend='half',
                spin=-2)
    fx.particle('fine', 14, 14, 1, (128, 128, 128), (36, 70), speed=22, lift=20, gravity=2, spread=300,
                blend=None, clut=0, spin=14)
    fx.label('main'); fx.when(0, 'aimed'); fx.when(10, 'swirl')
    fx.br(fx.NOW, '>', 9, 'sand_end')
    fx.vcopy(fx.AT, fx.CHEST); fx.call('grain', 4)
    fx.set(fx.T2, fx.NOW); fx.mod(fx.T2, 2); fx.br(fx.T2, '!=', 0, 'sand_end')
    fx.call('cloud')
    fx.label('sand_end'); fx.end(12)
    fx.label('aimed')
    fx.vcopy(drift, fx.TCHEST); fx.vsub(drift, fx.CHEST); fx.vdiv(drift, 11); fx.ret()
    fx.label('swirl')
    fx.sound(38)

    def one():
        fx.hit(); fx.vcopy(fx.AT, fx.TCHEST); fx.emit('hang', fx.TCHEST, 4); fx.call('fine', 6); fx.call('dizzy')
    fx.each_target(one); fx.ret()
    dizzy = fx.pool('dizzy', 3)
    fx.begin('dizzy', dizzy, 'dizzy_render', inherit=False)
    fx.vcopy(POS, fx.TGT); fx.lin(fx.T, at(fx.TSIZE, 1), 1, 80); fx.sub_(at(POS, 1), fx.T); fx.ret()
    fx.label('dizzy_tick'); fx.life(16); fx.ret()
    fx.label('dizzy_render')
    for k in range(3):
        fx.lin(fx.T2, FRAME, 460, 1365 * k)
        fx.circle(fx.TV, fx.T2, 240, 0); fx.vadd(fx.TV, POS)
        fx.sprite(fx.TV, tint, 90, cell=1, blend=None)
    fx.ret()
    return fx


def stone_skin():
    """Rocks rise out of the ground round the caster, circle in and close on it, then a dull flash: its Defense
    rises."""
    fx = Fx(delay=8, cast_sound=45)
    fx.palette(BROWN); fx.palette(ROCK)
    paint_all(fx, {0: rock(3), 1: rock(11, 10.0), 2: dust(2)})
    tint, gnd = fx.colour(128, 128, 128), fx.var()
    reach, high, idx = fx.var(), fx.var(), fx.var()
    fx.particle('puff', 10, 9, 2, (128, 118, 100), (150, 230), grow=26, speed=12, lift=8, spread=520, blend='half')
    fx.particle('shine', 1, 9, 2, (128, 118, 96), None, grow=45, fade=True)
    tumbler(fx, 'chip', 12, 13, 1, (60, 110), 36, 40, 7, 400, 16, gnd, tint)
    fx.label('main'); fx.when(0, 'gather'); fx.when(14, 'flash')
    fx.br(fx.NOW, '>', 11, 'done')
    fx.vcopy(fx.AT, fx.SRC); fx.call('puff'); fx.ret()
    fx.label('done'); fx.end(16)
    fx.label('gather')
    fx.lin(reach, at(fx.SSIZE, 0), 1, 420); fx.lin(high, at(fx.SSIZE, 1), 6, 0, 10)
    fx.set(idx, 0); fx.call('stone', 7); fx.sound(-55); fx.ret()
    fx.label('flash')
    fx.sound(11); fx.hit_self(); fx.set(gnd, at(fx.SRC, 1))
    fx.lin(fx.SZ, at(fx.SSIZE, 1), 10, 300, 10)
    fx.emit('shine', fx.CHEST); fx.emit('chip', fx.CHEST, 10); fx.emit('puff', fx.SRC, 3); fx.ret()
    stone = fx.pool('stone', 7, 2)
    fx.begin('stone', stone, 'stone_render', inherit=False)
    fx.vcopy(POS, fx.SRC); fx.lin(iv(FREE), idx, 585); fx.set(iv(FREE + 4), idx); fx.add(idx, 1); fx.ret()
    fx.label('stone_tick'); fx.life(14); fx.ret()
    fx.label('stone_render')
    # each rock comes up out of the ground a tick after the one before, circles in as it climbs to the caster's
    # middle, and is gone into it as the flash comes
    fx.set(fx.T, FRAME); fx.sub_(fx.T, iv(FREE + 4)); fx.br(fx.T, '<', 0, 'noop')
    fx.br(fx.T, '<=', 7, 'stone_in'); fx.set(fx.T, 7)
    fx.label('stone_in')
    fx.lin(fx.T3, fx.T, -1, 7); fx.mul(fx.T3, reach); fx.div(fx.T3, 7)          # the radius, closing
    fx.lin(fx.T2, fx.T, 150); fx.add(fx.T2, iv(FREE))                           # the angle, turning
    fx.circle(fx.TV, fx.T2, fx.T3, 0); fx.vadd(fx.TV, POS)
    fx.set(fx.T2, fx.T); fx.mul(fx.T2, high); fx.div(fx.T2, 7); fx.add(fx.T2, -40); fx.sub_(at(fx.TV, 1), fx.T2)
    fx.lin(fx.T3, fx.T, -14, 250); fx.lin(fx.T2, FRAME, 22); fx.add(fx.T2, iv(FREE))
    fx.sprite(fx.TV, tint, fx.T3, cell=0, clut=1, rot=fx.T2, blend=None); fx.ret()
    return fx


def boulder_crash():
    """A big boulder falls from high on the spot where the target stands, its shadow growing there, and lands in a
    ring of dust, throwing stones."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(BROWN); fx.palette(ROCK)
    paint_all(fx, {0: rock(3), 1: rock(11, 10.0), 2: dust(2), 6: ring(12.5, 3.4)})
    tint, gnd, fade, big = fx.colour(128, 128, 128), fx.var(), fx.vec(), fx.var()
    fx.particle('puff', 8, 11, 2, (128, 118, 100), (220, 340), grow=26, speed=22, spread=400, blend='half')
    fx.particle('haze', 4, 10, 2, (80, 64, 40), 380, grow=45, fade=True)
    tumbler(fx, 'chip', 20, 15, 1, (70, 160), 55, 70, 9, 200, 16, gnd, tint)
    tumbler(fx, 'stone', 4, 15, 0, (150, 240), 40, 80, 10, 100, 12, gnd, tint)
    fx.label('main'); fx.when(0, 'fall'); fx.end(1)
    fx.label('fall')
    fx.lin(big, at(fx.TSIZE, 1), 1, 380)
    fx.vcopy(fx.DEST, fx.TGT); fx.lin(fx.T, big, 1, 0, 2); fx.sub_(at(fx.DEST, 1), fx.T)
    fx.vcopy(fx.AT, fx.DEST); fx.sub_(at(fx.AT, 1), 1500); fx.call('boulder'); fx.call('shade'); fx.sound(-55)
    fx.ret()
    fx.travel('boulder', 1, 7, 'boulder_render', 'boulder_land')
    fx.label('boulder_render')
    fx.lin(fx.T3, FRAME, 14)
    fx.sprite(POS, tint, big, big, cell=0, clut=1, rot=fx.T3, blend=None); fx.ret()
    fx.label('boulder_land')
    fx.sound(40); fx.strike(fx.TGT, 250); fx.set(gnd, at(fx.TGT, 1))
    fx.call('rest'); fx.call('wave')
    fx.emit('haze', fx.TGT); fx.emit('puff', fx.TCHEST, 5); fx.emit('chip', times=16); fx.emit('stone', times=3)
    fx.ret()
    # the shadow it casts on the ground, growing as it comes down
    shade = fx.pool('shade', 1)
    fx.begin('shade', shade, 'shade_render', inherit=False); fx.vcopy(POS, fx.TGT); fx.ret()
    fx.label('shade_tick'); fx.life(8); fx.ret()
    fx.label('shade_render')
    fx.lin(fx.T3, FRAME, 55, 120); fx.lin(fx.T, FRAME, 9, 40); fx.vset(fade, fx.T, fx.T, fx.T)
    fx.flat(POS, fx.T3, fade, cell=2, clut=1, blend='sub'); fx.ret()
    # the boulder, split and left on the ground, sinking into it
    rest = fx.pool('rest', 1)
    fx.begin('rest', rest, 'rest_render', inherit=False); fx.vcopy(POS, fx.TGT); fx.ret()
    fx.label('rest_tick'); fx.life(7); fx.ret()
    fx.label('rest_render')
    fx.vcopy(fx.TV, POS); fx.lin(fx.T, big, 1, 0, 2); fx.sub_(at(fx.TV, 1), fx.T)
    fx.lin(fx.T3, FRAME, -1, 7); fx.mul(fx.T3, big); fx.div(fx.T3, 7)
    fx.sprite(fx.TV, tint, fx.T3, cell=0, clut=1, blend=None, rot=fx.T3); fx.ret()
    wave = fx.pool('wave', 1)
    fx.begin('wave', wave, 'wave_render', inherit=False); fx.vcopy(POS, fx.TGT); fx.sub_(at(POS, 1), 12); fx.ret()
    fx.label('wave_tick'); fx.life(10); fx.ret()
    fx.label('wave_render')
    fx.lin(fx.T3, FRAME, 100, 180)
    fx.lin(fx.T, FRAME, -7, 76); fx.vset(fade, fx.T, fx.T, fx.T)
    fx.flat(POS, fx.T3, fade, cell=6); fx.ret()
    return fx


def fissure():
    """A crack runs along the ground from the caster to where the target stood and bursts under whoever stands round
    its end, throwing up stones and dust."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(BROWN); fx.palette(ROCK)
    paint_all(fx, {0: rock(3), 1: rock(11, 10.0), 2: dust(2), 3: crack(4), 7: star_crack(6)})
    tint, gnd, pv, dark = fx.colour(128, 128, 128), fx.var(), fx.vec(), fx.colour(*SHADE)
    fx.particle('puff', 10, 10, 2, (128, 118, 100), (150, 250), grow=24, speed=18, spread=240, blend='half')
    fx.particle('haze', 4, 9, 2, (80, 64, 40), 320, grow=40, fade=True)
    tumbler(fx, 'chip', 30, 15, 1, (70, 150), 50, 80, 10, 160, 16, gnd, tint)
    tumbler(fx, 'stone', 6, 15, 0, (140, 220), 36, 90, 10, 100, 12, gnd, tint)
    fx.label('main'); fx.when(0, 'open'); fx.when(10, 'burst'); fx.end(11)
    fx.label('open')
    fx.vcopy(fx.AT, fx.SRC); fx.vcopy(fx.DEST, fx.TGT); fx.call('run'); fx.sound(-55); fx.ret()
    fx.label('burst')
    fx.sound(40)

    def one():
        fx.hit(); fx.set(gnd, at(fx.TGT, 1)); fx.vcopy(fx.AT, fx.TGT); fx.call('bloom')
        fx.emit('haze', fx.TGT); fx.emit('puff', fx.TCHEST, 3); fx.emit('chip', fx.TGT, 8); fx.call('stone')
    fx.each_within(fx.DEST, 520, one); fx.ret()
    # the head of the crack: it runs from the caster's feet to the first enemy, laying a piece of crack a tick
    fx.travel('run', 1, 10, 'noop', 'run_end', every='lay')
    fx.label('lay')
    fx.emit('puff', POS); fx.call('seg'); fx.ret()
    fx.label('run_end'); fx.ret()
    seg = fx.pool('seg', 12, 9)
    fx.begin('seg', seg, 'seg_render', inherit=False)
    fx.from_parent(iv(FREE), 4); fx.from_parent(iv(FREE + 12), FREE)
    fx.vlen(fx.T, iv(FREE + 12)); fx.br(fx.T, '>=', 1, 'seg_ok'); fx.set(fx.T, 1)
    fx.label('seg_ok')
    fx.set(iv(FREE + 24), at(iv(FREE + 12), 2)); fx.mul(iv(FREE + 24), -300); fx.div(iv(FREE + 24), fx.T)
    fx.set(iv(FREE + 28), at(iv(FREE + 12), 0)); fx.mul(iv(FREE + 28), 300); fx.div(iv(FREE + 28), fx.T)
    fx.rnd(iv(FREE + 32), 0, 1); fx.ret()
    fx.label('seg_tick'); fx.life(20); fx.ret()
    fx.label('seg_render')
    q = fx.Q
    fx.vset(pv, iv(FREE + 24), 0, iv(FREE + 28))
    fx.vcopy(q[0], iv(FREE)); fx.vsub(q[0], iv(FREE + 12)); fx.vcopy(q[1], iv(FREE))
    fx.vcopy(q[2], q[0]); fx.vsub(q[2], pv); fx.vcopy(q[3], q[1]); fx.vsub(q[3], pv)
    fx.vadd(q[0], pv); fx.vadd(q[1], pv)
    for p in q:
        fx.sub_(at(p, 1), 8)
    fx.br(iv(FREE + 32), '==', 0, 'seg_flip')
    fx.quad(q[0], q[1], q[2], q[3], dark, cell=3, clut=1, blend='sub'); fx.ret()
    fx.label('seg_flip')
    fx.quad(q[2], q[3], q[0], q[1], dark, cell=3, clut=1, blend='sub'); fx.ret()
    # the ground splits in a star under an enemy
    bloom = fx.pool('bloom', 3)
    fx.begin('bloom', bloom, 'bloom_render', inherit=False); fx.vcopy(POS, fx.AT); fx.sub_(at(POS, 1), 8); fx.ret()
    fx.label('bloom_tick'); fx.life(18); fx.ret()
    fx.label('bloom_render')
    fx.lin(fx.T3, FRAME, 70, 140); fx.br(FRAME, '<', 5, 'bloom_draw'); fx.set(fx.T3, 420)
    fx.label('bloom_draw')
    fx.flat(POS, fx.T3, dark, cell=7, clut=1, blend='sub'); fx.ret()
    return fx


def stalagmite():
    """Stone spikes burst out of the ground under the target, the one in the middle tallest, with debris flying."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(BROWN); fx.palette(ROCK)
    paint_all(fx, {1: rock(11, 10.0), 2: dust(2), 4: spike(), 7: star_crack(6)})
    tint, gnd, idx, high = fx.colour(128, 128, 128), fx.var(), fx.var(), fx.var()
    dark = fx.colour(*SHADE)
    fx.particle('puff', 10, 10, 2, (128, 118, 100), (160, 260), grow=24, speed=14, spread=320, blend='half')
    fx.particle('haze', 4, 9, 2, (80, 64, 40), 340, grow=40, fade=True)
    tumbler(fx, 'chip', 22, 15, 1, (70, 150), 46, 80, 9, 360, 16, gnd, tint)
    fx.label('main'); fx.when(0, 'crack'); fx.when(2, 'rise'); fx.when(5, 'strike'); fx.end(6)
    fx.label('crack')
    fx.sound(-55); fx.call('bloom'); fx.emit('haze', fx.TGT); fx.ret()
    fx.label('rise')
    fx.lin(high, at(fx.TSIZE, 1), 14, 420, 10)
    fx.set(idx, 0); fx.call('spike', 5); fx.set(gnd, at(fx.TGT, 1))
    fx.emit('puff', fx.TGT, 4); fx.emit('chip', fx.TCHEST, 10); fx.ret()
    fx.label('strike')
    fx.sound(40); fx.hit(); fx.emit('chip', fx.TCHEST, 12); fx.emit('puff', fx.TGT, 3); fx.ret()
    spike_ = fx.pool('spike', 5, 1)
    fx.begin('spike', spike_, 'spike_render', inherit=False)
    fx.set(iv(FREE), idx); fx.vcopy(POS, fx.TGT); fx.br(idx, '==', 0, 'spike_set')
    fx.lin(fx.T, idx, 1024, -512); fx.lin(fx.T3, at(fx.TSIZE, 0), 1, 230); fx.circle(fx.TV, fx.T, fx.T3, 0)
    fx.vadd(POS, fx.TV)
    fx.label('spike_set'); fx.add(idx, 1); fx.ret()
    fx.label('spike_tick'); fx.life(18); fx.ret()
    fx.label('spike_render')
    # the outer spikes burst out first and the middle one a little behind; all sink away at the end
    fx.set(fx.T2, 1); fx.br(iv(FREE), '==', 0, 'spike_late'); fx.set(fx.T2, 0)
    fx.label('spike_late')
    fx.set(fx.T, FRAME); fx.add(fx.T, fx.T2); fx.br(fx.T, '<', 1, 'noop')
    fx.set(fx.T2, high)
    fx.br(iv(FREE), '==', 0, 'spike_tall'); fx.mul(fx.T2, 62); fx.div(fx.T2, 100)
    fx.label('spike_tall')
    fx.mul(fx.T2, fx.T); fx.div(fx.T2, 3)
    fx.set(fx.T3, high); fx.br(iv(FREE), '==', 0, 'spike_cap'); fx.mul(fx.T3, 62); fx.div(fx.T3, 100)
    fx.label('spike_cap')
    fx.br(fx.T2, '<=', fx.T3, 'spike_sink'); fx.set(fx.T2, fx.T3)
    fx.label('spike_sink')
    fx.br(FRAME, '<', 13, 'spike_wide')
    fx.lin(fx.T, FRAME, -1, 18); fx.set(fx.T2, fx.T3); fx.mul(fx.T2, fx.T); fx.div(fx.T2, 5)
    fx.label('spike_wide')
    fx.lin(fx.T3, at(fx.TSIZE, 0), 1, 150); fx.br(iv(FREE), '==', 0, 'spike_draw'); fx.lin(fx.T3, fx.T3, 7, 0, 10)
    fx.label('spike_draw')
    fx.pillar(POS, fx.T3, fx.T2, tint, cell=4, blend=None); fx.ret()
    bloom = fx.pool('bloom', 1)
    fx.begin('bloom', bloom, 'bloom_render', inherit=False); fx.vcopy(POS, fx.TGT); fx.sub_(at(POS, 1), 8); fx.ret()
    fx.label('bloom_tick'); fx.life(20); fx.ret()
    fx.label('bloom_render')
    fx.lin(fx.T3, FRAME, 40, 160); fx.br(FRAME, '<', 6, 'bloom_draw'); fx.set(fx.T3, 380)
    fx.label('bloom_draw')
    fx.flat(POS, fx.T3, dark, cell=7, clut=1, blend='sub'); fx.ret()
    return fx


def landslide():
    """Rocks of every size tumble across from the caster's side to where the target stood, a cloud of dust running
    with them, and bury whoever is there."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(BROWN); fx.palette(ROCK)
    paint_all(fx, {0: rock(3), 1: rock(11, 10.0), 2: dust(2), 6: ring(12.5, 3.4)})
    tint, drift, gnd, spot = fx.colour(128, 128, 128), fx.vec(), fx.var(), fx.vec()
    fx.particle('cloud', 12, 14, 2, (128, 118, 100), (260, 400), grow=24, speed=14, spread=300, drift=drift,
                blend='half', spin=3)
    fx.particle('haze', 6, 12, 2, (80, 64, 40), (300, 420), grow=30, speed=12, spread=300, drift=drift, fade=True)
    fx.particle('hang', 12, 16, 2, (128, 118, 100), (280, 400), grow=10, speed=8, spread=320, blend='half',
                spin=-2)
    tumbler(fx, 'rock', 18, 15, 0, (160, 400), 26, 50, 6, 240, 14, gnd, tint, drift=drift)
    tumbler(fx, 'pebble', 16, 14, 1, (60, 130), 30, 40, 6, 300, 18, gnd, tint, drift=drift)
    tumbler(fx, 'chip', 14, 14, 1, (60, 130), 40, 60, 8, 160, 16, gnd, tint)
    fx.label('main'); fx.when(0, 'aimed'); fx.when(13, 'bury')
    fx.br(fx.NOW, '>', 12, 'done')
    fx.set(gnd, at(fx.SRC, 1))
    fx.vcopy(fx.AT, fx.SRC); fx.sub_(at(fx.AT, 1), 380); fx.call('rock', 2); fx.call('pebble', 2)
    fx.vcopy(fx.AT, fx.SRC); fx.sub_(at(fx.AT, 1), 120); fx.call('cloud'); fx.call('haze'); fx.ret()
    fx.label('done'); fx.end(15)
    fx.label('aimed')
    fx.vcopy(spot, fx.TGT); fx.vcopy(drift, fx.TGT); fx.vsub(drift, fx.SRC); fx.vdiv(drift, 15); fx.ret()
    fx.label('bury')
    fx.sound(40)

    def one():
        fx.hit(); fx.set(gnd, at(fx.TGT, 1)); fx.emit('hang', fx.TCHEST, 3); fx.emit('chip', fx.TGT, 7)
    fx.each_within(spot, 800, one); fx.ret()
    return fx


def gaia_quake():
    """The screen takes a brown shade and the ground shakes, rings running out over it; pillars of rock burst under
    every enemy, boulders fly up and fall, and a last flash."""
    fx = Fx(delay=8, cast_sound=48, draw=True)
    fx.palette(BROWN); fx.palette(ROCK)
    paint_all(fx, {0: rock(3), 1: rock(11, 10.0), 2: dust(2), 4: spike(), 6: ring(12.5, 3.4), 7: star_crack(6)})
    tint, gnd, shade, fade, high = fx.colour(128, 128, 128), fx.var(), fx.vec(), fx.vec(), fx.var()
    dark = fx.colour(*SHADE)
    surge, burst = 14, 26
    fx.particle('pour', 20, 8, 1, (128, 128, 128), (60, 120), flat=((0, 0), (80, 105), (0, 0)), spread=1700,
                blend=None, clut=0, spin=18)
    fx.particle('puff', 12, 11, 2, (128, 118, 100), (220, 360), grow=26, speed=22, spread=420, blend='half')
    fx.particle('haze', 4, 10, 2, (80, 64, 40), 420, grow=50, fade=True)
    tumbler(fx, 'chip', 30, 15, 1, (70, 160), 55, 80, 10, 260, 16, gnd, tint)
    tumbler(fx, 'boulder', 9, 18, 0, (260, 460), 30, 125, 13, 160, 11, gnd, tint)
    fx.label('main'); fx.when(0, 'begin')
    for t in (2, 5, 8, 11):
        fx.when(t, 'tremor')
    fx.when(8, 'cracks'); fx.when(surge, 'rise'); fx.when(burst, 'flash')
    fx.br(fx.NOW, '>', burst, 'done')
    fx.br(fx.NOW, '<', 3, 'noop')
    fx.vcopy(fx.AT, fx.DEST); fx.sub_(at(fx.AT, 1), 950); fx.call('pour', 2)
    fx.set(fx.T2, fx.NOW); fx.mod(fx.T2, 2); fx.br(fx.T2, '!=', 0, 'noop')
    fx.vcopy(fx.AT, fx.DEST); fx.scatter(fx.AT, 1600); fx.call('puff'); fx.ret()
    fx.label('done'); fx.end(burst + 10)
    fx.label('draw')
    # the sky goes brown (blue and green drain out of it), then a flash
    fx.lin(fx.T, fx.NOW, 6); fx.br(fx.NOW, '<', 10, 'draw_shade')
    fx.set(fx.T, 60); fx.br(fx.NOW, '<', burst, 'draw_shade')
    fx.lin(fx.T, fx.NOW, -6, 6 * (burst + 10))
    fx.label('draw_shade')
    fx.lin(fx.T2, fx.T, 1, 0, 3); fx.lin(fx.T3, fx.T, 2, 0, 3)
    fx.vset(shade, fx.T2, fx.T3, fx.T); fx.overlay(shade)
    fx.br(fx.NOW, '<', burst, 'noop'); fx.br(fx.NOW, '>', burst + 6, 'noop')
    fx.lin(fx.T, fx.NOW, -14, 14 * (burst + 7)); fx.lin(fx.T2, fx.T, 9, 0, 10); fx.lin(fx.T3, fx.T, 7, 0, 10)
    fx.vset(shade, fx.T, fx.T2, fx.T3)
    fx.overlay(shade, blend='add'); fx.ret()
    fx.label('begin')
    fx.vcopy(fx.DEST, fx.TGT); fx.set(gnd, at(fx.SRC, 1)); fx.lin(high, at(fx.TSIZE, 1), 2, 640); fx.ret()
    fx.label('tremor')
    fx.sound(1); fx.call('shake'); fx.ret()
    fx.label('cracks')
    fx.sound(-55)

    def mark():
        fx.vcopy(fx.AT, fx.TGT); fx.call('bloom')
    fx.each_target(mark); fx.ret()
    fx.label('rise')
    fx.sound(40)

    def one():
        fx.hit(); fx.set(gnd, at(fx.TGT, 1)); fx.vcopy(fx.AT, fx.TGT); fx.call('column')
        fx.emit('haze', fx.TGT); fx.emit('puff', fx.TCHEST, 3); fx.emit('boulder', fx.TGT, 3)
        fx.emit('chip', fx.TCHEST, 8)
    fx.each_target(one); fx.ret()
    fx.label('flash'); fx.sound(15); fx.ret()
    # a ring of shock running out over the ground from the caster
    shake = fx.pool('shake', 4)
    fx.begin('shake', shake, 'shake_render', inherit=False); fx.vcopy(POS, fx.SRC); fx.sub_(at(POS, 1), 10); fx.ret()
    fx.label('shake_tick'); fx.life(12); fx.ret()
    fx.label('shake_render')
    fx.lin(fx.T3, FRAME, 210, 200)
    fx.lin(fx.T, FRAME, -6, 72); fx.vset(fade, fx.T, fx.T, fx.T)
    fx.flat(POS, fx.T3, fade, cell=6); fx.ret()
    bloom = fx.pool('bloom', 3)
    fx.begin('bloom', bloom, 'bloom_render', inherit=False); fx.vcopy(POS, fx.AT); fx.sub_(at(POS, 1), 8); fx.ret()
    fx.label('bloom_tick'); fx.life(10); fx.ret()
    fx.label('bloom_render')
    fx.lin(fx.T3, FRAME, 40, 160)
    fx.flat(POS, fx.T3, dark, cell=7, clut=1, blend='sub'); fx.ret()
    # a pillar of rock under an enemy: it bursts up, holds and sinks
    col = fx.pool('column', 3)
    fx.begin('column', col, 'column_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('column_tick'); fx.life(burst - surge + 6); fx.ret()
    fx.label('column_render')
    fx.set(fx.T2, high); fx.lin(fx.T, FRAME, 1, 1); fx.br(FRAME, '<', 3, 'column_up')
    fx.set(fx.T, 3); fx.br(FRAME, '<', burst - surge + 1, 'column_up')
    fx.lin(fx.T, FRAME, -1, burst - surge + 6)
    fx.label('column_up')
    fx.mul(fx.T2, fx.T); fx.div(fx.T2, 3)
    fx.lin(fx.T3, at(fx.TSIZE, 0), 2, 300)
    fx.pillar(POS, fx.T3, fx.T2, tint, cell=4, blend=None); fx.ret()
    return fx


EFFECTS = {154: rock_throw, 155: sand_blast, 156: stone_skin, 157: boulder_crash, 158: fissure, 159: stalagmite,
           160: landslide, 161: gaia_quake}
