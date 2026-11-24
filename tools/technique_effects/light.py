"""The Light row's effects."""
from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, fbm, glow, grid, iv, polar, ring, star
import numpy as np

GOLD = ['#000000', '#3a2000', '#a06808', '#f0b828', '#fff090', '#ffffff']
DAWN = ['#000000', '#102050', '#3070c8', '#90d0ff', '#e8f8ff', '#ffffff']


def beam():
    """A column of light: full at its foot, thinning into the sky."""
    x, y = grid()
    return clip(1 - np.abs(x - 16) / (4 + 7 * (y / 31))) ** 0.8 * (0.75 + 0.35 * fbm(9)) * clip(y / 6.0)


def bar():
    """A band of light across the cell."""
    x, y = grid()
    return clip(1 - np.abs(y - 16) / 7.0) ** 0.8 * (0.8 + 0.3 * fbm(4))


def cross():
    """A tall cross with flared ends."""
    x, y = grid()
    up = clip(1.3 - np.abs(x - 16) / (2.2 + 1.6 * np.abs(y - 16) / 15)) * (np.abs(y - 16) < 15)
    arm = clip(1.3 - np.abs(y - 11) / (2.0 + 1.4 * np.abs(x - 16) / 10)) * (np.abs(x - 16) < 10.5)
    return clip(np.maximum(up, arm))


def hexagon():
    """A six-sided pane: a bright rim round a faint face."""
    r, ang = polar()
    edge = 13.5 * np.cos(np.pi / 6) / np.cos((ang % (np.pi / 3)) - np.pi / 6)
    return clip(clip(1 - np.abs(r - edge + 1.5) / 1.8) + 0.3 * (r < edge - 1.5) * (0.6 + 0.6 * fbm(12)))


def feather():
    x, y = grid()
    t = (y - 3) / 26
    w = 5.5 * np.sin(np.pi * np.clip(t, 0, 1)) ** 0.7
    cx = 16 + 3 * np.sin(t * 2.2)
    vane = clip(1.2 - np.abs(x - cx) / np.maximum(w, 0.3)) * (t > 0) * (t < 1)
    return clip(vane * (0.7 + 0.3 * np.cos((x - cx + y) * 1.6)) + clip(1 - np.abs(x - cx) / 1.0) * (t > 0) * (t < 1.1))


def sunburst(turn=0.0):
    """A disc with eight short rays."""
    r, ang = polar()
    rays = clip(1 - r / (7 + 8 * np.abs(np.cos((ang + turn) * 4)) ** 5)) ** 0.5
    return clip(np.maximum(rays, clip((8.5 - r) / 2)))


def halo_ring():
    """A ring of light with beads on it."""
    r, ang = polar()
    return clip(ring(13, 1.7) + clip(np.cos(ang * 8) * 2 - 1.0) * clip(1 - np.abs(r - 13) / 2.8))


def holy_spark():
    """A four-point star flares on the target and throws a ring of glints."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(GOLD)
    fx.paint(0, star(4, 2.5, 13, 10)); fx.paint(1, glow(15, 1.3)); fx.paint(2, star(4, 2, 9, 6))
    fx.paint(3, ring(13, 1.6)); fx.paint(4, star(4, 2.5, 13, 10, np.pi / 4))
    fx.particle('bloom', 2, 6, 1, (128, 118, 70), None, grow=45, fade=True)
    fx.particle('flare', 2, 8, 0, (128, 128, 128), None, grow=75, fade=True)
    fx.particle('flare2', 2, 6, 4, (128, 120, 90), None, grow=40, fade=True)
    fx.particle('halo', 2, 8, 3, (128, 110, 60), 140, grow=80, fade=True)
    fx.particle('glint', 14, 11, 2, (128, 128, 100), (100, 180), grow=-9, speed=75, spread=60)
    fx.label('main'); fx.when(0, 'gather'); fx.when(3, 'burst'); fx.end(4)
    fx.label('gather')
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 8, 160, 10); fx.emit('bloom', fx.TCHEST); fx.ret()
    fx.label('burst')
    fx.sound(7); fx.hit()
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 14, 300, 10)
    fx.emit('flare', fx.TCHEST); fx.emit('halo'); fx.emit('glint', times=12)
    fx.lin(fx.SZ, fx.SZ, 6, 0, 10); fx.emit('flare2'); fx.ret()
    return fx


def shining_arrow():
    """A bow of light is drawn before the caster and looses a comet that leaves a line of glints."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(GOLD)
    fx.paint(0, ring(13, 1.5)); fx.paint(1, star(4, 2.5, 13, 10)); fx.paint(2, glow(15, 1.4)); fx.paint(3, star(4, 2, 9, 6))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 110, 60)
    fx.particle('bow', 3, 9, 0, (128, 120, 80), 130, grow=22, sy=44, fade=True)
    fx.particle('tail', 16, 7, 2, (128, 104, 48), 170, grow=-18, fade=True)
    fx.particle('dust', 16, 12, 3, (128, 128, 110), (60, 110), speed=10, gravity=2, spread=90, fade=True)
    fx.particle('flare', 1, 8, 1, (128, 128, 128), None, grow=70, fade=True)
    fx.particle('halo', 1, 8, 0, (128, 110, 60), 140, grow=70, fade=True)
    fx.particle('glint', 12, 11, 3, (128, 128, 100), (100, 170), grow=-9, speed=70, spread=60)
    fx.label('main'); fx.when(0, 'draw_bow'); fx.when(3, 'draw_bow'); fx.when(7, 'loose'); fx.end(8)
    fx.label('draw_bow'); fx.emit('bow', fx.CHEST); fx.ret()
    fx.label('loose')
    fx.sound(3); fx.emit('bow', fx.CHEST); fx.aim()
    fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('arrow'); fx.ret()
    fx.shot('arrow', 1, 75, 24, 'arrow_render', 'arrow_arrive', miss='arrow_miss', every='arrow_trail')
    fx.label('arrow_miss'); fx.emit('glint', POS, 4); fx.ret()
    fx.label('arrow_trail'); fx.emit('tail', POS); fx.emit('dust', POS, 2); fx.ret()
    fx.label('arrow_render')
    fx.sprite(POS, soft, 330, cell=2); fx.sprite(POS, tint, 300, cell=1); fx.ret()
    fx.label('arrow_arrive')
    fx.sound(7)
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 280, 10)
    fx.emit('flare', POS); fx.emit('halo'); fx.emit('glint', times=12); fx.ret()
    return fx


def blessing():
    """Motes of light spiral up round the caster over a turning seal and close into a glow: it heals."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(GOLD)
    fx.paint(0, glow(14, 1.6)); fx.paint(1, star(4, 2.5, 12, 8)); fx.paint(2, star(4, 2, 7, 4)); fx.paint(3, halo_ring())
    gold, white, seal_c = fx.colour(128, 110, 50), fx.colour(110, 110, 90), fx.colour(120, 96, 40)
    idx = fx.var()
    fx.particle('spark', 24, 14, 2, (110, 110, 90), 140, grow=-7, flat=((0, 0), (-18, -8), (0, 0)), spread=420)
    fx.particle('swell', 1, 18, 0, (128, 118, 70), 140, grow=30, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(20, 'bless')
    fx.br(fx.NOW, '>', 26, 'late')
    fx.vcopy(fx.AT, fx.SRC); fx.rnd(fx.T, 0, 250); fx.sub_(at(fx.AT, 1), fx.T); fx.call('spark'); fx.ret()
    fx.label('late'); fx.end(30)
    fx.label('begin')
    fx.set(idx, 0); fx.call('mote', 8); fx.call('seal'); fx.sound(-55); fx.ret()
    fx.label('bless'); fx.sound(11); fx.hit_self(); fx.emit('swell', fx.CHEST); fx.ret()
    mote = fx.pool('mote', 8, 1)
    fx.begin('mote', mote, 'mote_render', inherit=False)
    fx.lin(iv(FREE), idx, 512); fx.add(idx, 1); fx.vcopy(POS, fx.SRC); fx.ret()
    fx.label('mote_tick'); fx.life(30)
    fx.add(iv(FREE), 170); fx.lin(fx.T3, FRAME, -9, 300)
    fx.vcopy(POS, fx.SRC); fx.circle(fx.TV, iv(FREE), fx.T3, 0); fx.vadd(POS, fx.TV)
    fx.lin(fx.T, FRAME, 12); fx.sub_(at(POS, 1), fx.T); fx.ret()
    fx.label('mote_render')
    fx.sprite(POS, gold, 110, cell=0); fx.sprite(POS, white, 150, cell=1); fx.ret()
    seal = fx.pool('seal', 1)
    fx.begin('seal', seal, 'seal_render', inherit=False); fx.vcopy(POS, fx.SRC); fx.sub_(at(POS, 1), 10); fx.ret()
    fx.label('seal_tick'); fx.life(30); fx.ret()
    fx.label('seal_render')
    fx.lin(fx.T3, FRAME, 60, 100); fx.br(FRAME, '<', 5, 'seal_draw')
    fx.set(fx.T3, 400); fx.br(FRAME, '<', 24, 'seal_draw')
    fx.lin(fx.T3, FRAME, -60, 1840)
    fx.label('seal_draw'); fx.lin(fx.T2, FRAME, 70)
    fx.flat(POS, fx.T3, seal_c, cell=3, angle=fx.T2); fx.ret()
    return fx


def sacred_shield():
    """Six panes of light fly in round the caster, lock into a wall and flash: its guard rises."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(DAWN); fx.palette(GOLD)
    fx.paint(0, hexagon()); fx.paint(1, glow(15, 1.2)); fx.paint(2, star(4, 2, 9, 6)); fx.paint(3, ring(13.5, 1.4))
    cool, hot, ring_c = fx.colour(70, 100, 128), fx.colour(128, 128, 128), fx.colour(60, 90, 128)
    idx, rad = fx.var(), fx.var()
    fx.particle('flash', 1, 8, 1, (128, 120, 90), None, grow=50, clut=1, fade=True)
    fx.particle('glint', 14, 12, 2, (110, 120, 128), (80, 150), grow=-7, speed=30, lift=14, spread=500)
    fx.label('main'); fx.when(0, 'begin'); fx.when(10, 'lock'); fx.end(11)
    fx.label('begin')
    fx.lin(rad, at(fx.SSIZE, 0), 1, 240)
    fx.set(idx, 0); fx.call('pane', 6); fx.call('floor'); fx.ret()
    fx.label('lock')
    fx.sound(11); fx.hit_self()
    fx.lin(fx.SZ, at(fx.SSIZE, 1), 12, 300, 10); fx.emit('flash', fx.CHEST); fx.emit('glint', times=12); fx.ret()
    pane = fx.pool('pane', 6, 1)
    fx.begin('pane', pane, 'pane_render', inherit=False)
    fx.lin(iv(FREE), idx, 683); fx.add(idx, 1); fx.vcopy(POS, fx.CHEST); fx.ret()
    fx.label('pane_tick'); fx.life(28); fx.add(iv(FREE), 36); fx.ret()
    fx.label('pane_render')
    # flies in over ten ticks, stands, then shrinks away over the last six
    fx.lin(fx.T3, FRAME, -70, 700); fx.br(FRAME, '<', 10, 'pane_at'); fx.set(fx.T3, 0)
    fx.label('pane_at'); fx.add(fx.T3, rad)
    fx.vcopy(fx.TV, POS); fx.circle(fx.TV2, iv(FREE), fx.T3, 0); fx.vadd(fx.TV, fx.TV2)
    fx.lin(fx.T, FRAME, 22, 60); fx.br(FRAME, '<', 10, 'pane_draw')
    fx.set(fx.T, 290); fx.br(FRAME, '<', 22, 'pane_draw')
    fx.lin(fx.T, FRAME, -45, 1280)
    fx.label('pane_draw')
    fx.br(FRAME, '<', 10, 'pane_cool'); fx.br(FRAME, '>', 13, 'pane_cool')
    fx.lin(fx.T2, fx.T, 12, 0, 10); fx.sprite(fx.TV, hot, fx.T2, cell=0); fx.ret()
    fx.label('pane_cool'); fx.sprite(fx.TV, cool, fx.T, cell=0); fx.ret()
    floor = fx.pool('floor', 1)
    fx.begin('floor', floor, 'floor_render', inherit=False); fx.vcopy(POS, fx.SRC); fx.sub_(at(POS, 1), 10); fx.ret()
    fx.label('floor_tick'); fx.life(26); fx.ret()
    fx.label('floor_render')
    fx.lin(fx.T3, FRAME, -60, 800); fx.br(FRAME, '<', 10, 'floor_draw')
    fx.lin(fx.T3, rad, 1, 60)
    fx.label('floor_draw'); fx.lin(fx.T2, FRAME, -50)
    fx.flat(POS, fx.T3, ring_c, cell=3, angle=fx.T2); fx.ret()
    return fx


def flash_burst():
    """A small sun swells over the caster and bursts: the screen whites out and a ring of light sweeps the field."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(GOLD)
    fx.paint(0, sunburst()); fx.paint(1, sunburst(np.pi / 8)); fx.paint(2, glow(15, 1.1)); fx.paint(3, ring(13.5, 2.2))
    fx.paint(4, star(4, 2, 9, 6))
    tint, wash = fx.colour(128, 128, 128), fx.vec()
    swell = 12
    fx.particle('ray', 18, 10, 4, (128, 128, 100), (120, 200), grow=-10, flat=((-110, 110), (-30, 10), (-110, 110)))
    fx.particle('flare', 3, 8, 4, (128, 128, 128), None, grow=60, fade=True)
    fx.particle('halo', 3, 7, 2, (128, 110, 60), None, grow=50, fade=True)
    fx.label('main'); fx.when(0, 'rise'); fx.end(swell + 14)
    fx.label('draw')
    fx.br(fx.NOW, '<', swell, 'noop'); fx.br(fx.NOW, '>', swell + 8, 'noop')
    fx.lin(fx.T, fx.NOW, -14, 14 * (swell + 9)); fx.vset(wash, fx.T, fx.T, fx.T)
    fx.overlay(wash, blend='add'); fx.ret()
    fx.label('rise')
    fx.vcopy(fx.AT, fx.SRC); fx.lin(fx.T, at(fx.SSIZE, 1), 1, 260); fx.sub_(at(fx.AT, 1), fx.T)
    fx.call('sun'); fx.ret()
    sun = fx.pool('sun', 1)
    fx.begin('sun', sun, 'sun_render', inherit=False); fx.vcopy(POS, fx.AT); fx.sound(-55); fx.ret()
    fx.label('sun_tick')
    fx.br(FRAME, '!=', swell, 'sun_after')
    fx.sound(4); fx.call('sweep'); fx.emit('ray', POS, 18)

    def one():
        fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 10, 240, 10); fx.emit('flare', fx.TCHEST); fx.emit('halo')
    fx.each_target(one); fx.ret()
    fx.label('sun_after'); fx.life(swell + 4); fx.ret()
    fx.label('sun_render')
    fx.lin(fx.T, FRAME, 28, 90); fx.br(FRAME, '<=', swell, 'sun_draw')
    fx.lin(fx.T, FRAME, 260, -2700)
    fx.label('sun_draw')
    fx.lin(fx.T2, fx.T, 14, 0, 10); fx.sprite(POS, tint, fx.T2, cell=2)
    fx.set(fx.T3, FRAME); fx.mod(fx.T3, 4); fx.br(fx.T3, '<', 2, 'sun_a')
    fx.sprite(POS, tint, fx.T, cell=1); fx.ret()
    fx.label('sun_a'); fx.sprite(POS, tint, fx.T, cell=0); fx.ret()
    sweep = fx.pool('sweep', 1)
    fx.begin('sweep', sweep, 'sweep_render', inherit=False); fx.vcopy(POS, fx.SRC); fx.sub_(at(POS, 1), 20); fx.ret()
    fx.label('sweep_tick'); fx.life(12); fx.ret()
    fx.label('sweep_render')
    fx.lin(fx.T3, FRAME, 260, 200)
    fx.lin(fx.T, FRAME, -10, 128); fx.vset(wash, fx.T, fx.T, fx.T)
    fx.flat(POS, fx.T3, wash, cell=3); fx.ret()
    return fx


def judgment_ray():
    """A seal opens in the sky over the target and a pillar of light falls through it onto the ground."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(GOLD)
    fx.paint(0, halo_ring()); fx.paint(1, beam()); fx.paint(2, ring(13.5, 2.0)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, glow(15, 1.2))
    tint, soft, fade = fx.colour(128, 128, 128), fx.colour(128, 104, 50), fx.vec()
    high, fall = 1300, 10
    fx.particle('mote', 16, 12, 3, (128, 128, 100), (80, 150), grow=-6, speed=30, lift=40, spread=260)
    fx.particle('flare', 1, 8, 4, (128, 120, 80), None, grow=50, fade=True)
    fx.label('main'); fx.when(0, 'open')
    fx.when(fall, 'strike'); fx.when(fall + 3, 'ripples'); fx.when(fall + 7, 'ripples'); fx.end(fall + 8)
    fx.label('open'); fx.vcopy(fx.AT, fx.TGT); fx.call('seal'); fx.ret()
    fx.label('strike')
    fx.sound(6); fx.strike(fx.TGT, 240); fx.call('ripple')
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 10, 300, 10); fx.emit('flare', fx.TCHEST); fx.emit('mote', fx.TGT, 10); fx.ret()
    fx.label('ripples'); fx.call('ripple'); fx.emit('mote', fx.TGT, 3); fx.ret()
    seal = fx.pool('seal', 1)
    fx.begin('seal', seal, 'seal_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('seal_tick'); fx.life(fall + 16); fx.ret()
    fx.label('seal_render')
    fx.lin(fx.T3, FRAME, 45, 40); fx.br(FRAME, '<', 8, 'seal_draw')
    fx.set(fx.T3, 400); fx.br(FRAME, '<', fall + 11, 'seal_draw')
    fx.lin(fx.T3, FRAME, -80, 80 * (fall + 16))
    fx.label('seal_draw')
    fx.vcopy(fx.TV, POS); fx.sub_(at(fx.TV, 1), high)
    fx.lin(fx.T2, FRAME, 90)
    fx.flat(fx.TV, fx.T3, tint, cell=0, angle=fx.T2)
    fx.sprite(fx.TV, soft, fx.T3, cell=4)
    # the pillar: thin as it falls, then wide, then thinning out
    fx.br(FRAME, '<', fall - 3, 'noop'); fx.br(FRAME, '>', fall + 12, 'noop')
    fx.set(fx.T3, 70); fx.br(FRAME, '<', fall, 'seal_beam')
    fx.set(fx.T3, 460); fx.br(FRAME, '<', fall + 5, 'seal_beam')
    fx.lin(fx.T3, FRAME, -60, 60 * (fall + 13))
    fx.label('seal_beam')
    fx.pillar(POS, fx.T3, high, soft, cell=1)
    fx.lin(fx.T3, fx.T3, 1, 0, 2)
    fx.pillar(POS, fx.T3, high, tint, cell=1); fx.ret()
    rip = fx.pool('ripple', 3)
    fx.begin('ripple', rip, 'ripple_render', inherit=False); fx.vcopy(POS, fx.TGT); fx.sub_(at(POS, 1), 14); fx.ret()
    fx.label('ripple_tick'); fx.life(9); fx.ret()
    fx.label('ripple_render')
    fx.lin(fx.T3, FRAME, 75, 160)
    fx.lin(fx.T, FRAME, -12, 124); fx.vset(fade, fx.T, fx.T, fx.T)
    fx.flat(POS, fx.T3, fade, cell=2); fx.ret()
    return fx


def heavens_ring():
    """A great halo turns high over the enemies and comes down on them among falling feathers; where it lands, a
    column of light stands on each."""
    fx = Fx(delay=8, cast_sound=45)
    fx.palette(GOLD)
    fx.paint(0, halo_ring()); fx.paint(1, feather()); fx.paint(2, beam()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, feather()[:, ::-1])
    tint, fade = fx.colour(128, 120, 90), fx.vec()
    drop = 16
    fx.particle('plume', 12, 16, 1, (128, 128, 120), (110, 170), flat=((-14, 14), (22, 40), (-14, 14)), spread=1100)
    fx.particle('plume2', 12, 16, 5, (128, 128, 120), (110, 170), flat=((-14, 14), (22, 40), (-14, 14)), spread=1100)
    fx.particle('column', 4, 10, 2, (128, 116, 70), 260, grow=24, sy=56, fade=True)
    fx.particle('glint', 14, 12, 4, (128, 128, 100), (90, 160), grow=-8, speed=40, lift=45, gravity=4, spread=160)
    fx.label('main'); fx.when(0, 'open')
    fx.br(fx.NOW, '>', drop, 'landed')
    fx.vcopy(fx.AT, fx.DEST); fx.sub_(at(fx.AT, 1), 700); fx.call('plume'); fx.call('plume2'); fx.ret()
    fx.label('landed'); fx.end(drop + 1)
    fx.label('open'); fx.vcopy(fx.DEST, fx.TGT); fx.vcopy(fx.AT, fx.TGT); fx.call('halo'); fx.ret()
    halo = fx.pool('halo', 1)
    fx.begin('halo', halo, 'halo_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('halo_tick')
    fx.br(FRAME, '!=', drop, 'halo_after')
    fx.sound(4)

    def one():
        fx.hit()
        fx.vcopy(fx.AT, fx.TGT); fx.sub_(at(fx.AT, 1), 420); fx.call('column')
        fx.emit('glint', fx.TCHEST, 4)
    fx.each_within(fx.DEST, 760, one); fx.ret()
    fx.label('halo_after'); fx.life(drop + 10); fx.ret()
    fx.label('halo_render')
    # comes down from 1000 up to the ground while it widens, then races outwards and fades
    fx.vcopy(fx.TV, POS)
    fx.lin(fx.T, FRAME, -60, 60 * drop + 20); fx.br(FRAME, '<', drop, 'halo_y'); fx.set(fx.T, 20)
    fx.label('halo_y'); fx.sub_(at(fx.TV, 1), fx.T)
    fx.lin(fx.T3, FRAME, 22, 420); fx.set(fx.T, 128); fx.br(FRAME, '<=', drop, 'halo_draw')
    fx.lin(fx.T3, FRAME, 150, 772 - 150 * drop)
    fx.lin(fx.T, FRAME, -12, 128 + 12 * drop)
    fx.label('halo_draw')
    fx.vset(fade, fx.T, fx.T, fx.T)
    fx.lin(fx.T2, FRAME, 70)
    fx.flat(fx.TV, fx.T3, fade, cell=0, angle=fx.T2)
    fx.lin(fx.T2, FRAME, -50); fx.lin(fx.T3, fx.T3, 7, 0, 10)
    fx.flat(fx.TV, fx.T3, tint, cell=0, angle=fx.T2); fx.ret()
    return fx


def grand_cross():
    """Four stars take their places round the target, bands of light join them into a cross, and a great cross of
    light stands up out of the middle."""
    fx = Fx(delay=8, cast_sound=45, draw=True)
    fx.palette(GOLD)
    fx.paint(0, star(4, 2.5, 13, 10)); fx.paint(1, glow(15, 1.2)); fx.paint(2, bar()); fx.paint(3, cross())
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, ring(13.5, 2.0))
    tint, soft, wash = fx.colour(128, 128, 128), fx.colour(128, 104, 50), fx.vec()
    idx, rad = fx.var(), fx.var()
    join, stand = 14, 19
    fx.particle('glint', 16, 13, 4, (128, 128, 100), (100, 190), grow=-9, speed=80, lift=30, gravity=5, spread=120)
    fx.particle('halo', 1, 9, 5, (128, 110, 60), 200, grow=110, fade=True)
    fx.label('main')
    for k in range(4):
        fx.when(3 * k, 'place')
    fx.when(join, 'bands'); fx.when(stand, 'strike'); fx.end(stand + 12)
    fx.label('draw')
    fx.br(fx.NOW, '<', stand, 'noop'); fx.br(fx.NOW, '>', stand + 6, 'noop')
    fx.lin(fx.T, fx.NOW, -14, 14 * (stand + 7)); fx.vset(wash, fx.T, fx.T, fx.T)
    fx.overlay(wash, blend='add'); fx.ret()
    fx.label('place')
    fx.br(fx.NOW, '!=', 0, 'place_go')
    fx.set(idx, 0); fx.lin(rad, at(fx.TSIZE, 0), 1, 520)
    fx.label('place_go'); fx.sound(34); fx.call('orb'); fx.ret()
    fx.label('bands'); fx.sound(6); fx.call('band'); fx.ret()
    fx.label('strike')
    fx.sound(15); fx.strike(fx.TGT, 320); fx.vcopy(fx.AT, fx.TGT); fx.call('rood')
    fx.emit('halo', fx.TCHEST); fx.emit('glint', times=16); fx.ret()
    orb = fx.pool('orb', 4, 1)
    fx.begin('orb', orb, 'orb_render', inherit=False)
    fx.lin(iv(FREE), idx, 1024, 512); fx.add(idx, 1)
    fx.vcopy(POS, fx.TCHEST); fx.circle(fx.TV, iv(FREE), rad, 0); fx.vadd(POS, fx.TV); fx.ret()
    fx.label('orb_tick'); fx.set(fx.T, stand + 6); fx.lin(fx.T2, iv(FREE), 1, -512); fx.lin(fx.T2, fx.T2, 3, 0, 1024); fx.sub_(fx.T, fx.T2)
    fx.br(FRAME, '>', fx.T, 'die'); fx.ret()
    fx.label('orb_render')
    fx.lin(fx.T, FRAME, 40, 60); fx.br(FRAME, '<', 5, 'orb_draw'); fx.set(fx.T, 260)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.mul(fx.T2, 50); fx.add(fx.T, fx.T2)
    fx.label('orb_draw')
    fx.sprite(POS, soft, fx.T, cell=1); fx.sprite(POS, tint, fx.T, cell=0); fx.ret()
    # the two bands between opposite stars
    band = fx.pool('band', 1)
    fx.begin('band', band, 'band_render', inherit=False); fx.vcopy(POS, fx.TCHEST); fx.ret()
    fx.label('band_tick'); fx.life(stand - join + 6); fx.ret()
    fx.label('band_render')
    fx.lin(fx.T3, FRAME, 16, 30); fx.br(FRAME, '<', 5, 'band_draw'); fx.set(fx.T3, 110)
    fx.label('band_draw')
    for k in range(2):
        for end, q in ((0, (0, 2)), (2048, (1, 3))):
            fx.circle(fx.TV, 512 + 1024 * k + end, rad, 0); fx.vadd(fx.TV, POS)
            fx.vcopy(fx.Q[q[0]], fx.TV); fx.sub_(at(fx.Q[q[0]], 1), fx.T3)
            fx.vcopy(fx.Q[q[1]], fx.TV); fx.add(at(fx.Q[q[1]], 1), fx.T3)
        fx.quad(fx.Q[0], fx.Q[1], fx.Q[2], fx.Q[3], tint, cell=2)
    fx.ret()
    # the standing cross
    rood = fx.pool('rood', 1)
    fx.begin('rood', rood, 'rood_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('rood_tick'); fx.life(11); fx.ret()
    fx.label('rood_render')
    fx.lin(fx.T3, FRAME, 150, 300); fx.br(FRAME, '<', 4, 'rood_draw')
    fx.set(fx.T3, 900); fx.br(FRAME, '<', 7, 'rood_draw')
    fx.lin(fx.T3, FRAME, -90, 1530)
    fx.label('rood_draw')
    fx.lin(fx.T2, at(fx.TSIZE, 1), 2, 900)
    fx.pillar(POS, fx.T3, fx.T2, soft, cell=3)
    fx.lin(fx.T3, fx.T3, 7, 0, 10)
    fx.pillar(POS, fx.T3, fx.T2, tint, cell=3); fx.ret()
    return fx


EFFECTS = {130: holy_spark, 131: shining_arrow, 132: blessing, 133: sacred_shield, 134: flash_burst,
           135: judgment_ray, 136: heavens_ring, 137: grand_cross}
