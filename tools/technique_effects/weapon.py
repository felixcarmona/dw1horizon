"""The Weapon row's effects."""
from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, glow, grid, iv, ring, star
import numpy as np

STEEL = ['#000000', '#141c2c', '#34486c', '#6c88b0', '#c4d8ec', '#ffffff']
EMBER = ['#000000', '#400800', '#a02800', '#f06010', '#ffc040', '#fff4c0']
DULL = ['#000000', '#201a1a', '#483c3c', '#706460', '#a09088', '#d0c4bc']


def slash_arc():
    """A bright crescent cut, thick in the middle and tapering to a point at both ends."""
    x, y = grid()
    lum = np.zeros((32, 32))
    for t in np.linspace(0, 1, 60):
        cx = 3 + 26 * t
        cy = 28 - 24 * t - 6 * np.sin(np.pi * t)
        w = 0.4 + 3.4 * np.sin(np.pi * t) ** 0.9
        d = np.hypot(x - cx, y - cy)
        lum = np.maximum(lum, clip(1.5 - d / w) * 0.9 + 0.35 * clip(1 - d / (w * 2.4)))
    return clip(lum)


def knife():
    """A throwing blade, point up: a ridged blade, a guard and a wrapped grip."""
    x, y = grid()
    dx = np.abs(x - 16)
    hw = 0.3 + 4.4 * clip((y - 2) / 9) ** 0.6
    blade = clip((hw - dx) / 1.0) * (y > 2) * (y < 21)
    shade = np.where(x >= 16, 0.95, 0.5) + 0.2 * clip(1 - dx / 1.0) + 0.3 * clip(1 - (hw - dx) / 1.4)
    guard = clip((7.5 - dx) / 1.0) * (y > 20.5) * (y < 23.5)
    grip = clip((1.9 - dx) / 0.8) * (y > 23) * (y < 29.5)
    wrap = 0.5 + 0.15 * np.sin(y * 2.2)
    pommel = clip((2.8 - np.hypot(x - 16, y - 30)) / 1.0)
    return clip(blade * shade * 0.9 + guard * 0.65 + grip * wrap + pommel * 0.7)


def poly(points, soft=1.0):
    """A convex polygon's mask (1 inside) and its distance to the nearest edge."""
    x, y = grid()
    ds = []
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
        ln = np.hypot(x1 - x0, y1 - y0)
        ds.append(((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)) / ln)
    d = np.min(ds, axis=0)
    return clip(d / soft + 0.5), d


def plate():
    """A shard of armour: a bent plate, lit on one side, with a bright edge."""
    m, d = poly([(5, 9), (20, 3), (29, 14), (22, 28), (8, 23)])
    x, y = grid()
    lit = 0.45 + 0.4 * clip((x - y + 10) / 28) + 0.25 * (x + y > 36)
    return clip(m * (lit + 0.5 * clip(1 - d / 2.0)))


def tall_blade():
    """A long straight blade, point up, with a central ridge and a crossguard at its foot."""
    x, y = grid()
    dx = np.abs(x - 16)
    hw = 0.6 + 6.0 * clip(y / 9) ** 0.55
    blade = clip((hw - dx) / 1.0) * (y < 25.5)
    shade = np.where(x >= 16, 1.0, 0.55) + 0.3 * clip(1 - dx / 1.0)
    guard = clip((11 - dx) / 1.0) * (y > 25) * (y < 28.5)
    grip = clip((2.2 - dx) / 0.8) * (y >= 28.5)
    return clip(blade * shade * 0.85 + guard * 0.7 + grip * 0.5)


def streak():
    """A straight line of light, tapering to a point at both ends."""
    x, y = grid()
    w = 3.4 * np.sin(np.pi * x / 32) ** 0.8
    return clip(clip(1.5 - np.abs(y - 16) / np.maximum(w, 0.2)) * (w > 0.25) + 0.4 * clip(1 - np.abs(y - 16) / 0.9))


def spark():
    return clip(star(4, 1.5, 12, 9) + 0.5 * glow(6, 1.0))


def paint_all(fx, cells):
    for cell, lum in cells.items():
        fx.paint(cell, lum)


def quick_slash():
    """One fast bright slash crescent cuts across the target and throws a few sparks."""
    fx = Fx(delay=8, cast_sound=19)
    fx.palette(STEEL); fx.palette(EMBER)
    paint_all(fx, {0: slash_arc(), 2: spark(), 5: glow(15, 1.2), 7: streak()})
    fx.particle('cut', 1, 8, 0, (128, 128, 128), 280, grow=70, sy=16, fade=True)
    fx.particle('flare', 1, 6, 5, (90, 110, 128), 200, grow=50, fade=True)
    fx.particle('spark', 8, 10, 2, (128, 128, 128), (60, 110), speed=50, lift=15, gravity=5, spread=60, clut=1,
                grow=-6, fade=True)
    fx.label('main'); fx.when(0, 'swing'); fx.when(2, 'land'); fx.end(3)
    fx.label('swing')
    fx.emit('cut', fx.TCHEST); fx.ret()
    fx.label('land')
    fx.sound(20); fx.hit(); fx.emit('flare', fx.TCHEST); fx.emit('spark', times=8); fx.ret()
    return fx


def blade_throw():
    """A spinning blade flies from the caster to the target, leaving a thin trail, and bursts into sparks on it."""
    fx = Fx(delay=8, cast_sound=19)
    fx.palette(STEEL); fx.palette(EMBER)
    paint_all(fx, {1: knife(), 2: spark(), 5: glow(15, 1.2), 7: streak()})
    tint, soft = fx.colour(128, 128, 128), fx.colour(34, 52, 100)
    fx.particle('trail', 20, 6, 5, (60, 90, 128), 150, grow=-22, fade=True)
    fx.particle('flash', 1, 6, 2, (128, 128, 128), 420, grow=90, fade=True)
    fx.particle('spark', 10, 10, 2, (128, 128, 128), (60, 110), speed=55, lift=20, gravity=5, spread=60, clut=1,
                grow=-6, fade=True)
    fx.label('main'); fx.when(0, 'throw'); fx.end(1)
    fx.label('throw')
    fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('blade'); fx.ret()
    fx.travel('blade', 1, 12, 'blade_render', 'blade_arrive', every='blade_trail')
    fx.label('blade_trail'); fx.emit('trail', POS); fx.ret()
    fx.label('blade_render')
    fx.lin(fx.T2, FRAME, 78)
    fx.sprite(POS, soft, 340, cell=5)
    fx.sprite(POS, tint, 300, cell=1, rot=fx.T2, blend=None); fx.ret()
    fx.label('blade_arrive')
    fx.sound(20); fx.hit(); fx.emit('flash', POS); fx.emit('spark', times=10); fx.ret()
    return fx


def armor_break():
    """A heavy downward strike on the target; plates of armour fly off and a dull ring drops down it: its Defense
    falls."""
    fx = Fx(delay=8, cast_sound=19)
    fx.palette(STEEL); fx.palette(EMBER); fx.palette(DULL)
    paint_all(fx, {0: slash_arc(), 2: spark(), 3: plate(), 5: glow(15, 1.2), 6: ring(13, 2.4), 7: streak()})
    fade = fx.vec()
    fx.particle('glint', 1, 4, 2, (128, 128, 128), 280, grow=40, fade=True)
    fx.particle('chop', 1, 8, 0, (128, 128, 128), 340, grow=90, sy=16, fade=True)
    fx.particle('line', 1, 6, 7, (128, 128, 128), 560, grow=150, sy=3, rot=90, fade=True)
    fx.particle('plate', 10, 15, 3, (128, 128, 128), (130, 210), speed=40, lift=45, gravity=8, spread=70, spin=18,
                blend=None)
    fx.particle('spark', 8, 10, 2, (128, 128, 128), (60, 110), speed=50, lift=15, gravity=5, spread=60, clut=1,
                grow=-6, fade=True)
    fx.label('main'); fx.when(0, 'raise'); fx.when(2, 'strike'); fx.when(4, 'land'); fx.when(8, 'again'); fx.end(9)
    fx.label('raise')
    fx.vcopy(fx.AT, fx.TCHEST); fx.lin(fx.T, at(fx.TSIZE, 1), 1, 150); fx.sub_(at(fx.AT, 1), fx.T)
    fx.call('glint'); fx.ret()
    fx.label('strike')
    fx.sound(4); fx.emit('chop', fx.TCHEST); fx.emit('line'); fx.ret()
    fx.label('land')
    fx.sound(20); fx.hit(); fx.emit('plate', fx.TCHEST, 10); fx.emit('spark', times=8); fx.call('drop'); fx.ret()
    fx.label('again'); fx.call('drop'); fx.ret()
    drop = fx.pool('drop', 2)
    fx.begin('drop', drop, 'drop_render', inherit=False); fx.ret()
    fx.label('drop_tick'); fx.life(15); fx.ret()
    fx.label('drop_render')
    # a dull ring slides from the target's head to its feet, dimming as it goes
    fx.vcopy(fx.TV, fx.TGT)
    fx.lin(fx.T, FRAME, -1, 15); fx.mul(fx.T, at(fx.TSIZE, 1)); fx.div(fx.T, 15); fx.sub_(at(fx.TV, 1), fx.T)
    fx.lin(fx.T3, at(fx.TSIZE, 0), 2, 300); fx.lin(fx.T2, FRAME, -8); fx.add(fx.T3, fx.T2)
    fx.lin(fx.T, FRAME, -6, 100); fx.vset(fade, fx.T, fx.T, fx.T)
    fx.lin(fx.T2, FRAME, 90)
    fx.flat(fx.TV, fx.T3, fade, cell=6, clut=2, angle=fx.T2); fx.ret()
    return fx


def war_stance():
    """Blades of light rise from the ground in a ring round the caster and a red-orange aura climbs it and
    flashes: its Offense rises."""
    fx = Fx(delay=8, cast_sound=45)
    fx.palette(STEEL); fx.palette(EMBER)
    paint_all(fx, {2: spark(), 4: tall_blade(), 5: glow(15, 1.2), 6: ring(13, 2.2)})
    steel, haze, aura, lift = fx.colour(128, 128, 128), fx.colour(56, 70, 100), fx.colour(120, 100, 84), \
        fx.colour(110, 110, 110)
    reach, high, idx = fx.var(), fx.var(), fx.var()
    fx.particle('ember', 22, 11, 2, (128, 128, 128), (50, 90), speed=16, lift=34, spread=360, clut=1, grow=-4,
                fade=True)
    fx.particle('shine', 1, 9, 5, (128, 128, 128), None, grow=45, clut=1, fade=True)
    fx.particle('burst', 12, 12, 2, (128, 128, 128), (70, 120), speed=55, lift=30, gravity=5, spread=60, clut=1,
                grow=-6, fade=True)
    fx.label('main'); fx.when(0, 'gather'); fx.when(4, 'climb'); fx.when(10, 'climb'); fx.when(16, 'flash')
    fx.br(fx.NOW, '<', 5, 'noop'); fx.br(fx.NOW, '>', 15, 'done')
    fx.vcopy(fx.AT, fx.SRC); fx.call('ember', 2); fx.ret()
    fx.label('done'); fx.end(17)
    fx.label('gather')
    fx.lin(reach, at(fx.SSIZE, 0), 1, 330); fx.lin(high, at(fx.SSIZE, 1), 1, 520)
    fx.set(idx, 0); fx.call('blade', 8); fx.call('column'); fx.sound(-55); fx.ret()
    fx.label('climb'); fx.call('rise'); fx.ret()
    fx.label('flash')
    fx.sound(11); fx.hit_self()
    fx.lin(fx.SZ, at(fx.SSIZE, 1), 10, 300, 10); fx.emit('shine', fx.CHEST); fx.emit('burst', fx.SRC, 12); fx.ret()
    # the blades: staggered round the ring, each rising from the ground and sinking at the end
    blade = fx.pool('blade', 8, 1)
    fx.begin('blade', blade, 'blade_render', inherit=False)
    fx.lin(fx.T, idx, 512); fx.circle(fx.TV, fx.T, reach, 0)
    fx.vcopy(POS, fx.SRC); fx.vadd(POS, fx.TV)
    fx.set(iv(FREE), idx); fx.add(idx, 1); fx.ret()
    fx.label('blade_tick'); fx.life(24); fx.ret()
    fx.label('blade_render')
    fx.set(fx.T2, FRAME); fx.sub_(fx.T2, iv(FREE)); fx.br(fx.T2, '<', 1, 'noop')
    fx.set(fx.T3, fx.T2); fx.mul(fx.T3, high); fx.div(fx.T3, 5); fx.br(fx.T3, '<=', high, 'blade_up')
    fx.set(fx.T3, high)
    fx.label('blade_up')
    fx.br(FRAME, '<', 19, 'blade_draw')
    fx.set(fx.T3, high); fx.lin(fx.T, FRAME, -1, 24); fx.mul(fx.T3, fx.T); fx.div(fx.T3, 5)
    fx.label('blade_draw')
    fx.pillar(POS, 330, fx.T3, haze, cell=5)
    fx.pillar(POS, 160, fx.T3, steel, cell=4, blend=None); fx.ret()
    # the aura: a soft red-orange column that grows up the caster
    col = fx.pool('column', 1)
    fx.begin('column', col, 'column_render', inherit=False); fx.vcopy(POS, fx.SRC); fx.ret()
    fx.label('column_tick'); fx.life(26); fx.ret()
    fx.label('column_render')
    fx.lin(fx.T2, at(fx.SSIZE, 1), 1, 260); fx.lin(fx.T, FRAME, 1, 0)
    fx.br(FRAME, '<', 14, 'column_up'); fx.set(fx.T, 14)
    fx.label('column_up')
    fx.mul(fx.T2, fx.T); fx.div(fx.T2, 14)
    fx.lin(fx.T3, at(fx.SSIZE, 0), 2, 150)
    fx.br(FRAME, '<', 22, 'column_draw')
    fx.lin(fx.T, FRAME, -1, 26); fx.mul(fx.T3, fx.T); fx.div(fx.T3, 4)
    fx.label('column_draw')
    fx.pillar(POS, fx.T3, fx.T2, aura, cell=5, clut=1)
    fx.lin(fx.T3, fx.T3, 1, 0, 2)
    fx.pillar(POS, fx.T3, fx.T2, lift, cell=5, clut=1); fx.ret()
    # a ring of fire climbing the caster
    rise = fx.pool('rise', 2)
    fx.begin('rise', rise, 'rise_render', inherit=False); fx.vcopy(POS, fx.SRC); fx.ret()
    fx.label('rise_tick'); fx.life(10); fx.ret()
    fx.label('rise_render')
    fx.vcopy(fx.TV, POS)
    fx.lin(fx.T, at(fx.SSIZE, 1), 1, 100); fx.mul(fx.T, FRAME); fx.div(fx.T, 10); fx.sub_(at(fx.TV, 1), fx.T)
    fx.lin(fx.T3, at(fx.SSIZE, 0), 1, 280); fx.lin(fx.T2, FRAME, -12); fx.add(fx.T3, fx.T2)
    fx.lin(fx.T2, FRAME, 300)
    fx.flat(fx.TV, fx.T3, lift, cell=6, clut=1, angle=fx.T2); fx.ret()
    return fx


def cross_cutter():
    """Two slashes cut an X across the target, one after the other, and a burst flares where they cross."""
    fx = Fx(delay=8, cast_sound=19)
    fx.palette(STEEL); fx.palette(EMBER)
    paint_all(fx, {0: slash_arc(), 2: spark(), 5: glow(15, 1.2), 7: streak()})
    fx.particle('cutA', 1, 12, 0, (128, 128, 128), 340, grow=50, sy=16, fade=True)
    fx.particle('cutB', 1, 9, 0, (128, 128, 128), 340, grow=50, sy=16, rot=90, fade=True)
    fx.particle('flare', 1, 9, 2, (128, 128, 128), 360, grow=95, fade=True)
    fx.particle('glow', 1, 8, 5, (80, 110, 128), 300, grow=80, clut=1, fade=True)
    fx.particle('spark', 14, 11, 2, (128, 128, 128), (60, 120), speed=60, lift=20, gravity=5, spread=60, clut=1,
                grow=-6, fade=True)
    fx.label('main'); fx.when(0, 'first'); fx.when(4, 'second'); fx.when(8, 'cross'); fx.end(9)
    fx.label('first')
    fx.emit('cutA', fx.TCHEST); fx.ret()
    fx.label('second')
    fx.sound(20); fx.emit('cutB', fx.TCHEST); fx.ret()
    fx.label('cross')
    fx.sound(4); fx.hit()
    fx.emit('flare', fx.TCHEST); fx.emit('glow'); fx.emit('spark', times=14); fx.ret()
    return fx


def whirling_edge():
    """A ring of spinning blades flies out and through every enemy; a slash cuts each one as the ring passes."""
    fx = Fx(delay=8, cast_sound=19)
    fx.palette(STEEL); fx.palette(EMBER)
    paint_all(fx, {0: slash_arc(), 1: knife(), 2: spark(), 5: glow(15, 1.2), 6: ring(13, 2.2)})
    tint, soft, lit = fx.colour(128, 128, 128), fx.colour(30, 48, 96), fx.colour(70, 90, 128)
    fx.particle('trail', 24, 6, 5, (60, 90, 128), 200, grow=-26, fade=True)
    fx.particle('spark', 14, 10, 2, (128, 128, 128), (60, 110), speed=55, lift=20, gravity=5, spread=80, clut=1,
                grow=-6, fade=True)
    idx, far = fx.var(), fx.vec()
    fx.label('main'); fx.when(0, 'launch'); fx.when(8, 'sweep'); fx.end(9)
    fx.label('launch')
    fx.vcopy(far, fx.TCHEST); fx.vsub(far, fx.CHEST); fx.vdiv(far, 2); fx.vadd(far, fx.TCHEST)
    fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, far); fx.call('wheel'); fx.sound(-55); fx.ret()
    fx.travel('wheel', 1, 16, 'wheel_render', 'wheel_end', every='wheel_trail')
    fx.label('wheel_trail'); fx.emit('trail', POS); fx.ret()
    fx.label('wheel_end'); fx.ret()
    fx.label('wheel_render')
    fx.sprite(POS, soft, 980, cell=5)
    fx.lin(fx.T2, FRAME, -380)
    fx.flat(POS, 440, lit, cell=6, angle=fx.T2)
    for k in range(4):
        fx.lin(fx.T2, FRAME, 420, 1024 * k)
        fx.circle(fx.TV, fx.T2, 400, 0); fx.vadd(fx.TV, POS)
        fx.lin(fx.T, FRAME, 58, 90 * k)
        fx.sprite(fx.TV, tint, 380, cell=1, rot=fx.T, blend=None)
    fx.ret()
    fx.label('sweep')
    fx.sound(20); fx.set(idx, 0)

    def one():
        fx.hit(); fx.vcopy(fx.AT, fx.TCHEST); fx.lin(fx.SZ, at(fx.TSIZE, 1), 8, 150, 10)
        fx.call('cut'); fx.add(idx, 1)
    fx.each_target(one); fx.ret()
    # a slash that opens a little after the one before it, so the cuts run along the row
    cut = fx.pool('cut', 3, 2)
    fx.begin('cut', cut, 'cut_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.lin(iv(FREE), idx, 2); fx.set(iv(FREE + 4), fx.SZ); fx.ret()
    fx.label('cut_tick')
    fx.life(16)
    fx.set(fx.T, FRAME); fx.sub_(fx.T, iv(FREE)); fx.br(fx.T, '!=', 0, 'noop')
    fx.emit('spark', POS, 6); fx.ret()
    fx.label('cut_render')
    fx.set(fx.T2, FRAME); fx.sub_(fx.T2, iv(FREE)); fx.br(fx.T2, '<', 0, 'noop'); fx.br(fx.T2, '>', 6, 'noop')
    fx.lin(fx.T3, fx.T2, 30, 0); fx.add(fx.T3, iv(FREE + 4))
    fx.lin(fx.T, fx.T2, -18, 128); fx.vset(fx.TV2, fx.T, fx.T, fx.T)
    fx.lin(fx.T, fx.T3, 15, 0, 16)
    fx.sprite(POS, fx.TV2, fx.T3, fx.T, cell=0); fx.ret()
    return fx


def giant_cleave():
    """A huge blade of light is raised over the target and brought down: a vertical cut, a shock ring on the ground
    and sparks."""
    fx = Fx(delay=8, cast_sound=19)
    fx.palette(STEEL); fx.palette(EMBER); fx.palette(DULL)
    paint_all(fx, {2: spark(), 4: tall_blade(), 5: glow(15, 1.2), 6: ring(13, 2.4), 7: streak()})
    fade = fx.vec()
    steel, haze, lit = fx.colour(128, 128, 128), fx.colour(60, 76, 112), fx.colour(120, 128, 128)
    rise = fx.var()
    fx.particle('cutline', 1, 7, 7, (128, 128, 128), 1100, grow=80, sy=2, rot=90, fade=True)
    fx.particle('flash', 1, 9, 2, (128, 128, 128), 620, grow=110, fade=True)
    fx.particle('dust', 6, 12, 5, (60, 60, 60), 260, grow=40, speed=24, spread=360, clut=2, fade=True)
    fx.particle('spark', 18, 12, 2, (128, 128, 128), (70, 130), speed=70, lift=30, gravity=6, spread=100, clut=1,
                grow=-6, fade=True)
    fx.label('main'); fx.when(0, 'raise'); fx.when(15, 'land'); fx.end(16)
    fx.label('raise')
    fx.lin(rise, at(fx.TSIZE, 1), 1, 800); fx.call('sword'); fx.call('quake'); fx.sound(-55); fx.ret()
    fx.label('land')
    fx.sound(15); fx.hit()
    fx.emit('cutline', fx.TCHEST); fx.emit('flash'); fx.emit('dust', fx.TGT, 6); fx.emit('spark', fx.TCHEST, 18)
    fx.ret()
    sword = fx.pool('sword', 1)
    fx.begin('sword', sword, 'sword_render', inherit=False); fx.vcopy(POS, fx.TGT); fx.ret()
    fx.label('sword_tick'); fx.life(18); fx.ret()
    fx.label('sword_render')
    # lifted over the target (ticks 0-11, growing), held, then driven down over three ticks; gone as it lands
    fx.br(FRAME, '>', 15, 'noop')
    fx.vcopy(fx.TV, POS); fx.set(fx.T, rise)
    fx.br(FRAME, '<', 12, 'sword_hold')
    fx.lin(fx.T2, FRAME, -1, 15); fx.mul(fx.T, fx.T2); fx.div(fx.T, 3)
    fx.label('sword_hold')
    fx.lin(fx.T3, rise, 1, 0, 2); fx.sub_(at(fx.TV, 1), fx.T3); fx.sub_(at(fx.TV, 1), fx.T)
    fx.lin(fx.T3, FRAME, 18, 220); fx.br(FRAME, '<', 12, 'sword_draw'); fx.set(fx.T3, 436)
    fx.label('sword_draw')
    fx.lin(fx.T2, rise, 1, 0)
    fx.sprite(fx.TV, haze, fx.T3, fx.T2, cell=5)
    fx.lin(fx.T3, fx.T3, 3, 0, 5)
    fx.sprite(fx.TV, steel, fx.T3, fx.T2, cell=4, rot=180, blend=None); fx.ret()
    quake = fx.pool('quake', 1)
    fx.begin('quake', quake, 'quake_render', inherit=False); fx.vcopy(POS, fx.TGT); fx.sub_(at(POS, 1), 14); fx.ret()
    fx.label('quake_tick'); fx.life(26); fx.ret()
    fx.label('quake_render')
    fx.br(FRAME, '<', 15, 'noop')
    fx.lin(fx.T3, FRAME, 130, -1500)
    fx.lin(fx.T, FRAME, -9, 250); fx.vset(fade, fx.T, fx.T, fx.T)
    fx.flat(POS, fx.T3, fade, cell=6, clut=0)
    fx.lin(fx.T3, fx.T3, 2, 0, 3)
    fx.flat(POS, fx.T3, fade, cell=6, clut=2); fx.ret()
    return fx


def final_edge():
    """The screen darkens; slash lines cross the target one by one from different angles, then they all flash at
    once with the hit and a burst."""
    fx = Fx(delay=8, cast_sound=48, draw=True)
    fx.palette(STEEL); fx.palette(EMBER)
    paint_all(fx, {0: slash_arc(), 2: spark(), 5: glow(15, 1.2), 6: ring(13, 2.2), 7: streak()})
    shade, tint, soft = fx.vec(), fx.colour(128, 128, 128), fx.colour(40, 60, 110)
    idx = fx.var()
    first, gap, count = 10, 3, 6
    flash = first + gap * count
    fx.particle('spark', 10, 9, 2, (128, 128, 128), (60, 110), speed=50, lift=15, gravity=5, spread=60, clut=1,
                grow=-6, fade=True)
    fx.particle('glint', 1, 5, 2, (128, 128, 128), 260, grow=40, fade=True)
    fx.particle('burst', 1, 11, 2, (128, 128, 128), 900, grow=130, fade=True)
    fx.particle('core', 1, 9, 5, (128, 128, 128), 640, grow=120, fade=True)
    fx.particle('scatter', 24, 14, 2, (128, 128, 128), (70, 140), speed=85, lift=30, gravity=6, spread=100, clut=1,
                grow=-6, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(flash, 'break')
    for k in range(count):
        fx.when(first + gap * k, 'line')
    fx.end(flash + 10)
    fx.label('draw')
    # the field dims, holds, flashes white at the break and clears
    fx.lin(fx.T, fx.NOW, 8); fx.br(fx.NOW, '<', 8, 'draw_dim')
    fx.set(fx.T, 64); fx.br(fx.NOW, '<', flash, 'draw_dim')
    fx.lin(fx.T, fx.NOW, -8, 64 + 8 * flash); fx.br(fx.T, '>', 0, 'draw_dim'); fx.set(fx.T, 0)
    fx.label('draw_dim')
    fx.vset(shade, fx.T, fx.T, fx.T); fx.overlay(shade)
    fx.br(fx.NOW, '<', flash, 'noop'); fx.br(fx.NOW, '>', flash + 4, 'noop')
    fx.lin(fx.T, fx.NOW, -24, 24 * (flash + 5)); fx.vset(shade, fx.T, fx.T, fx.T)
    fx.overlay(shade, blend='add'); fx.ret()
    fx.label('begin')
    fx.set(idx, 0); fx.vcopy(fx.AT, fx.CHEST); fx.call('glint'); fx.ret()
    fx.label('line')
    fx.sound(20); fx.call('stroke'); fx.add(idx, 1)
    fx.vcopy(fx.AT, fx.TCHEST); fx.call('spark', 3); fx.ret()
    fx.label('break')
    fx.sound(15); fx.hit()
    fx.emit('burst', fx.TCHEST); fx.emit('core'); fx.emit('scatter', times=24); fx.ret()
    # a line: laid across the target at its own angle, bright when it opens, then holding until the flash
    stroke = fx.pool('stroke', count, 1)
    fx.begin('stroke', stroke, 'stroke_render', inherit=False)
    fx.vcopy(POS, fx.TCHEST)
    fx.lin(fx.T, idx, 67, 20); fx.mod(fx.T, 180); fx.set(iv(FREE), fx.T); fx.ret()
    fx.label('stroke_tick')
    fx.br(fx.NOW, '>', flash + 3, 'die'); fx.ret()
    fx.label('stroke_render')
    fx.lin(fx.T3, FRAME, 220, 500); fx.br(FRAME, '<', 4, 'stroke_len'); fx.set(fx.T3, 1380)
    fx.label('stroke_len')
    fx.set(fx.T2, 128); fx.br(FRAME, '<', 3, 'stroke_lit'); fx.set(fx.T2, 70)
    fx.br(fx.NOW, '<', flash, 'stroke_lit'); fx.set(fx.T2, 128)
    fx.label('stroke_lit')
    fx.vset(shade, fx.T2, fx.T2, fx.T2)
    fx.lin(fx.T, fx.T3, 3, 0, 16)
    fx.sprite(POS, soft, fx.T3, fx.T, cell=7, rot=iv(FREE))
    fx.lin(fx.T, fx.T3, 1, 0, 16)
    fx.sprite(POS, shade, fx.T3, fx.T, cell=7, rot=iv(FREE)); fx.ret()
    return fx


EFFECTS = {146: quick_slash, 147: blade_throw, 148: armor_break, 149: war_stance, 150: cross_cutter,
           151: whirling_edge, 152: giant_cleave, 153: final_edge}
