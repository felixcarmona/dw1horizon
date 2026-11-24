"""The Water row's effects."""
from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, fbm, glow, grid, iv, polar, ring
import numpy as np

AQUA = ['#000000', '#041c58', '#1058b8', '#30a4e4', '#98e4ff', '#ffffff']
STORM = ['#000000', '#182030', '#384860', '#6880a0', '#a8c0d8', '#e8f4ff']


def bubble():
    """A thin shell with a highlight."""
    x, y = grid()
    return clip(ring(12, 2.4) * 0.9 + clip(1 - np.hypot(x - 11, y - 10) / 4.0) + 0.3 * glow(13, 0.6))


def blob(seed=6):
    """A ball of water: a bright rim, a darker body, a highlight."""
    x, y = grid()
    r, _ = polar()
    body = clip((13.5 - r) / 2) * (0.45 + 0.3 * fbm(seed))
    return clip(body + 0.7 * ring(12.5, 2.2) + clip(1 - np.hypot(x - 11, y - 10) / 4.0))


def drop():
    """A falling drop: round below, a point above."""
    x, y = grid()
    t = clip((y - 2) / 27)
    w = 10.5 * t ** 1.6 * clip((30 - y) / 5.0) ** 0.5 + 0.4
    body = clip(1.3 - np.abs(x - 16) / w)
    return clip(body * (0.55 + 0.45 * clip(np.abs(x - 16) / w)) + clip(1 - np.hypot(x - 13, y - 21) / 3.0))


def column(seed=5):
    """A standing column of water, wider at its foot."""
    x, y = grid()
    nx, n2 = fbm(seed), fbm(seed + 3)
    half = 4 + 8 * (y / 31) ** 0.8 + 1.5 * (nx - 0.5)
    core = clip(1 - np.abs(x - 16 - 1.5 * np.sin(y / 5.0)) / half) ** 1.3
    ends = clip(y / 5.0) * clip((31 - y) / 4.0)
    return clip(core * ends * (0.75 + 0.25 * np.sin(x * 1.7 + 8 * nx)) * (0.6 + 0.5 * n2) * 1.3)


def foam(seed=8):
    x, y = grid()
    lum = np.zeros((32, 32))
    for cx, cy, rr in ((16, 17, 9), (9, 19, 6), (23, 19, 6), (13, 11, 6), (20, 12, 5), (16, 23, 5)):
        lum = np.maximum(lum, clip(1 - np.hypot(x - cx, y - cy) / rr) ** 0.8)
    return clip(lum * (0.7 + 0.5 * fbm(seed)))


def spiral():
    """Three arms winding into the middle."""
    r, ang = polar()
    return clip(np.cos(ang * 3 + r * 0.55) * 1.6 - 0.3) * clip((15 - r) / 3) * clip(r / 3)


def rain():
    x, y = grid()
    return clip(1 - np.abs(x - 16) / 1.8) * clip(y / 20.0) * clip((32 - y) / 3.0)


def crown():
    """A splash seen from the side: a low bowl of water with fingers."""
    x, y = grid()
    fingers = 10 + 12 * np.abs(np.sin((x - 16) * 0.62)) * clip(np.abs(x - 16) / 5 + 0.35)
    top = 30 - fingers * clip(1 - ((x - 16) / 15) ** 2) ** 0.5
    depth = y - top                              # below the crest line: a bright rim, the body thinning out
    body = clip(depth / 1.5) * (0.1 + 0.9 * clip(1 - depth / 8)) * clip((30 - y) / 9)
    return clip(body * (0.7 + 0.5 * fbm(15)) * clip((15 - np.abs(x - 16)) / 4))


def cloud(seed=2):
    x, y = grid()
    lum = np.zeros((32, 32))
    for cx, cy, rr in ((16, 16, 10), (8, 18, 7), (24, 18, 7), (12, 12, 7), (21, 12, 6)):
        lum = np.maximum(lum, clip(1.2 - np.hypot(x - cx, (y - cy) * 1.3) / rr) ** 0.7)
    return clip(lum * (0.55 + 0.6 * fbm(seed)))


def bubble_shot():
    """A string of wobbling bubbles drifts to the target and bursts on it one by one."""
    fx = Fx(delay=8, cast_sound=36)
    fx.palette(AQUA)
    fx.paint(0, bubble()); fx.paint(1, ring(12, 1.4)); fx.paint(2, glow(8, 1.0)); fx.paint(3, glow(15, 1.4))
    tint = fx.colour(128, 128, 128)
    fx.particle('pop', 6, 7, 1, (110, 128, 128), 200, grow=70, fade=True)
    fx.particle('bead', 18, 9, 2, (110, 128, 128), (50, 90), speed=45, lift=25, gravity=9, spread=50)
    fx.particle('puff', 4, 5, 3, (60, 90, 128), 160, grow=20, fade=True)
    fx.label('main')
    for t in range(0, 12, 2):
        fx.when(t, 'blow')
    fx.end(11)
    fx.label('blow')
    fx.emit('puff', fx.CHEST)
    fx.vcopy(fx.DEST, fx.TCHEST); fx.scatter(fx.DEST, 150); fx.call('bub'); fx.ret()
    fx.travel('bub', 6, 13, 'bub_render', 'bub_arrive', fields=1)
    fx.label('bub_wave')
    fx.vcopy(fx.TV, POS)
    fx.lin(fx.T, FRAME, 430); fx.sin(fx.T2, fx.T, 110); fx.add(at(fx.TV, 1), fx.T2)
    fx.lin(fx.T, FRAME, 310); fx.cos(fx.T2, fx.T, 80); fx.add(at(fx.TV, 0), fx.T2); fx.ret()
    fx.label('bub_render')
    fx.call('bub_wave')
    fx.lin(fx.T3, FRAME, 12, 210); fx.set(fx.T2, FRAME); fx.mod(fx.T2, 4); fx.mul(fx.T2, 8); fx.add(fx.T3, fx.T2)
    fx.sprite(fx.TV, tint, fx.T3, cell=0); fx.ret()
    fx.label('bub_arrive')
    fx.sound(37); fx.hit(); fx.emit('pop', POS); fx.emit('bead', times=3); fx.ret()
    return fx


def aqua_jet():
    """A hard jet of water: a stream of fast slugs from the caster that sprays off the target for as long as it
    lasts."""
    fx = Fx(delay=8, cast_sound=59)
    fx.palette(AQUA)
    fx.paint(0, blob()); fx.paint(1, glow(15, 1.2)); fx.paint(2, glow(8, 1.0)); fx.paint(3, foam())
    tint, soft = fx.colour(110, 128, 128), fx.colour(40, 80, 128)
    fx.particle('spray', 20, 9, 2, (120, 128, 128), (60, 110), speed=55, lift=35, gravity=9, spread=80)
    fx.particle('mist', 6, 8, 3, (70, 100, 128), 200, grow=30, speed=12, spread=120, fade=True)
    fx.particle('muzzle', 3, 4, 1, (60, 100, 128), 260, grow=30, fade=True)
    last = 14
    fx.label('main')
    fx.br(fx.NOW, '>', last, 'die')
    fx.vcopy(fx.DEST, fx.TCHEST)
    for _ in range(2):
        fx.vcopy(fx.AT, fx.CHEST); fx.scatter(fx.AT, 50); fx.call('slug')
    fx.emit('muzzle', fx.CHEST); fx.ret()
    fx.travel('slug', 16, 5, 'slug_render', 'slug_arrive')
    fx.label('slug_render')
    fx.lin(fx.T3, FRAME, 22, 150)
    fx.sprite(POS, soft, fx.T3, cell=1); fx.sprite(POS, tint, fx.T3, cell=0); fx.ret()
    fx.label('slug_arrive')
    fx.hit(); fx.emit('spray', POS, 2); fx.emit('mist'); fx.ret()
    return fx


def rain_dance():
    """A cloud gathers over the caster and rains on it; rings run over the ground and a ring of water climbs it: its
    speed rises."""
    fx = Fx(delay=8, cast_sound=36)
    fx.palette(AQUA); fx.palette(STORM)
    fx.paint(0, cloud()); fx.paint(1, rain()); fx.paint(2, ring(13, 1.6)); fx.paint(3, glow(8, 1.0))
    fx.paint(4, cloud(7)[:, ::-1]); fx.paint(5, glow(15, 1.3))
    grey, fade, lift = fx.colour(128, 128, 128), fx.vec(), fx.colour(90, 128, 128)
    high, idx = fx.var(), fx.var()
    fx.particle('streak', 28, 7, 1, (90, 120, 128), 110, flat=((0, 0), (80, 80), (0, 0)), spread=560, sy=40)
    fx.particle('bead', 12, 10, 3, (110, 128, 128), (50, 90), speed=20, lift=40, gravity=5, spread=300)
    fx.particle('shine', 1, 9, 5, (80, 120, 128), None, grow=40, fade=True)
    fx.label('main'); fx.when(0, 'gather'); fx.when(16, 'quicken')
    fx.br(fx.NOW, '<', 4, 'noop'); fx.br(fx.NOW, '>', 24, 'done')
    fx.vcopy(fx.AT, fx.SRC); fx.sub_(at(fx.AT, 1), high); fx.call('streak', 3)
    fx.set(fx.T2, fx.NOW); fx.mod(fx.T2, 3); fx.br(fx.T2, '!=', 0, 'noop')
    fx.call('ripple'); fx.ret()
    fx.label('done'); fx.end(30)
    fx.label('gather')
    fx.lin(high, at(fx.SSIZE, 1), 1, 520)
    fx.set(idx, 0); fx.call('cloud', 3); fx.sound(-55); fx.ret()
    fx.label('quicken')
    fx.sound(11); fx.hit_self(); fx.call('climb')
    fx.lin(fx.SZ, at(fx.SSIZE, 1), 10, 260, 10); fx.emit('shine', fx.CHEST); fx.emit('bead', fx.SRC, 10); fx.ret()
    cl = fx.pool('cloud', 3, 1)
    fx.begin('cloud', cl, 'cloud_render', inherit=False)
    fx.vcopy(POS, fx.SRC); fx.sub_(at(POS, 1), high)
    fx.lin(fx.T, idx, 230, -230); fx.add(at(POS, 0), fx.T)
    fx.set(iv(FREE), idx); fx.add(idx, 1); fx.ret()
    fx.label('cloud_tick'); fx.life(30); fx.ret()
    fx.label('cloud_render')
    fx.lin(fx.T3, FRAME, 60, 100); fx.br(FRAME, '<', 6, 'cloud_draw')
    fx.set(fx.T3, 460); fx.br(FRAME, '<', 25, 'cloud_draw')
    fx.lin(fx.T3, FRAME, -80, 2460)
    fx.label('cloud_draw')
    fx.lin(fx.T2, fx.T3, 10, 0, 16)
    fx.br(iv(FREE), '==', 1, 'cloud_mid')
    fx.sprite(POS, grey, fx.T3, fx.T2, cell=4, clut=1, blend='half'); fx.ret()
    fx.label('cloud_mid'); fx.lin(fx.T3, fx.T3, 12, 0, 10); fx.lin(fx.T2, fx.T2, 12, 0, 10)
    fx.sprite(POS, grey, fx.T3, fx.T2, cell=0, clut=1, blend='half'); fx.ret()
    rip = fx.pool('ripple', 8)
    fx.begin('ripple', rip, 'ripple_render', inherit=False)
    fx.vcopy(POS, fx.SRC); fx.scatter(POS, 560); fx.lin(at(POS, 1), at(fx.SRC, 1), 1, -10); fx.ret()
    fx.label('ripple_tick'); fx.life(8); fx.ret()
    fx.label('ripple_render')
    fx.lin(fx.T3, FRAME, 26, 40)
    fx.lin(fx.T, FRAME, -12, 110); fx.vset(fade, fx.T, fx.T, fx.T)
    fx.flat(POS, fx.T3, fade, cell=2); fx.ret()
    # the ring of water that climbs the caster
    climb = fx.pool('climb', 1)
    fx.begin('climb', climb, 'climb_render', inherit=False); fx.vcopy(POS, fx.SRC); fx.ret()
    fx.label('climb_tick'); fx.life(10); fx.ret()
    fx.label('climb_render')
    fx.vcopy(fx.TV, POS)
    fx.lin(fx.T, at(fx.SSIZE, 1), 1, 100); fx.mul(fx.T, FRAME); fx.div(fx.T, 10); fx.sub_(at(fx.TV, 1), fx.T)
    fx.lin(fx.T3, at(fx.SSIZE, 0), 1, 260); fx.lin(fx.T2, FRAME, -14); fx.add(fx.T3, fx.T2)
    fx.lin(fx.T2, FRAME, 300)
    fx.flat(fx.TV, fx.T3, lift, cell=2, angle=fx.T2); fx.ret()
    return fx


def whirlpool():
    """The ground under every enemy turns to a whirlpool that drags beads of water round and up."""
    fx = Fx(delay=8, cast_sound=36)
    fx.palette(AQUA)
    fx.paint(0, spiral()); fx.paint(1, blob()); fx.paint(2, glow(8, 1.0)); fx.paint(3, ring(13, 2.0))
    fx.paint(4, spiral()[:, ::-1])
    tint, soft, fade = fx.colour(100, 128, 128), fx.colour(50, 90, 128), fx.vec()
    fx.particle('spray', 20, 10, 2, (120, 128, 128), (50, 90), speed=35, lift=45, gravity=7, spread=300)
    fx.particle('wake', 2, 8, 3, (70, 110, 128), 200, grow=60, fade=True)
    fx.label('main'); fx.when(0, 'stir'); fx.when(5, 'open'); fx.end(6)
    fx.label('stir'); fx.vcopy(fx.AT, fx.SRC); fx.sub_(at(fx.AT, 1), 30); fx.call('wake'); fx.ret()
    fx.label('open')
    fx.sound(37)

    def one():
        fx.hit(); fx.vcopy(fx.AT, fx.TGT); fx.lin(fx.SZ, at(fx.TSIZE, 0), 1, 380); fx.call('vortex')
    fx.each_target(one); fx.ret()
    vortex = fx.pool('vortex', 3, 1)
    fx.begin('vortex', vortex, 'vortex_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.sub_(at(POS, 1), 14); fx.set(iv(FREE), fx.SZ); fx.ret()
    fx.label('vortex_tick'); fx.life(22)
    fx.br(FRAME, '>', 16, 'noop'); fx.emit('spray', POS); fx.ret()
    fx.label('vortex_render')
    fx.lin(fx.T3, FRAME, 1, 2); fx.br(FRAME, '<', 6, 'vortex_r')
    fx.set(fx.T3, 8); fx.br(FRAME, '<', 17, 'vortex_r')
    fx.lin(fx.T3, FRAME, -1, 24); fx.br(fx.T3, '>', 0, 'vortex_r'); fx.set(fx.T3, 1)
    fx.label('vortex_r'); fx.mul(fx.T3, iv(FREE)); fx.div(fx.T3, 8)
    fx.lin(fx.T2, FRAME, -330)
    fx.flat(POS, fx.T3, tint, cell=0, angle=fx.T2)
    fx.lin(fx.T2, FRAME, -210, 700); fx.lin(fx.SZ, fx.T3, 14, 0, 10)
    fx.flat(POS, fx.SZ, soft, cell=4, angle=fx.T2)
    # three beads dragged round the rim, climbing
    fx.lin(fx.SZ, fx.T3, 8, 0, 10)
    for k in range(3):
        fx.lin(fx.T2, FRAME, -420, 1365 * k)
        fx.circle(fx.TV, fx.T2, fx.SZ, 0); fx.vadd(fx.TV, POS)
        fx.lin(fx.T, FRAME, 16 + 5 * k, 30); fx.sub_(at(fx.TV, 1), fx.T)
        fx.sprite(fx.TV, tint, 150, cell=1)
    fx.ret()
    return fx


def hydro_cannon():
    """Water is drawn into a great ball before the caster; it fires, leaving rings in the air, and breaks on the
    target in a crown."""
    fx = Fx(delay=8, cast_sound=36)
    fx.palette(AQUA)
    fx.paint(0, blob()); fx.paint(1, glow(15, 1.2)); fx.paint(2, glow(8, 1.0)); fx.paint(3, ring(13, 1.8))
    fx.paint(4, crown()); fx.paint(5, foam())
    tint, soft = fx.colour(118, 128, 128), fx.colour(40, 84, 128)
    charge = 12
    fx.particle('shock', 6, 7, 3, (90, 120, 128), 160, grow=60, fade=True)
    fx.particle('burst', 1, 9, 4, (128, 128, 128), None, grow=45, fade=True)
    fx.particle('mist', 4, 10, 5, (80, 110, 128), 300, grow=40, speed=14, spread=160, fade=True)
    fx.particle('bead', 20, 12, 2, (120, 128, 128), (60, 120), speed=70, lift=55, gravity=10, spread=120)
    fx.label('main'); fx.when(0, 'open'); fx.end(1)
    fx.label('open'); fx.vcopy(fx.AT, fx.CHEST); fx.call('ball'); fx.ret()
    ball = fx.pool('ball', 1)
    fx.begin('ball', ball, 'ball_render', inherit=False); fx.vcopy(POS, fx.AT); fx.sound(-55); fx.ret()
    fx.label('ball_tick')
    fx.br(FRAME, '>=', charge, 'ball_fire')
    fx.call('mote', 2); fx.ret()
    fx.label('ball_fire')
    fx.sound(4); fx.vcopy(fx.AT, POS); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('shot')
    fx.emit('shock', POS); fx.jmp('die')
    fx.label('ball_render')
    fx.lin(fx.T, FRAME, 30, 80)
    fx.lin(fx.T2, fx.T, 15, 0, 10); fx.sprite(POS, soft, fx.T2, cell=1)
    fx.sprite(POS, tint, fx.T, cell=0); fx.ret()
    mote = fx.pool('mote', 14, 3)
    fx.begin('mote', mote, 'mote_render', inherit=False)
    fx.from_parent(iv(FREE), 4)
    fx.vcopy(POS, iv(FREE)); fx.scatter(POS, 800)
    fx.vsub(iv(FREE), POS); fx.vdiv(iv(FREE), 6); fx.ret()
    fx.label('mote_tick'); fx.life(5); fx.vadd(POS, iv(FREE)); fx.ret()
    fx.label('mote_render'); fx.sprite(POS, tint, 90, cell=2); fx.ret()
    fx.travel('shot', 1, 6, 'shot_render', 'shot_arrive', every='shot_trail')
    fx.label('shot_trail'); fx.emit('shock', POS); fx.ret()
    fx.label('shot_render')
    fx.sprite(POS, soft, 660, cell=1); fx.sprite(POS, tint, 440, cell=0); fx.ret()
    fx.label('shot_arrive')
    fx.sound(40); fx.hit()
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 14, 420, 10)
    fx.vcopy(fx.AT, fx.TGT); fx.lin(fx.T, fx.SZ, 1, 0, 3); fx.sub_(at(fx.AT, 1), fx.T); fx.call('burst')
    fx.emit('mist', fx.TCHEST, 4); fx.emit('bead', times=18); fx.ret()
    return fx


def sea_crush():
    """A drop the size of a boulder falls on the target; six spouts leap up round where it lands."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(AQUA)
    fx.paint(0, drop()); fx.paint(1, column()); fx.paint(2, glow(8, 1.0)); fx.paint(3, ring(13, 2.0))
    fx.paint(4, foam()); fx.paint(5, glow(15, 1.2))
    tint, soft, fade = fx.colour(118, 128, 128), fx.colour(60, 100, 128), fx.vec()
    idx, big = fx.var(), fx.var()
    fx.particle('bead', 18, 12, 2, (120, 128, 128), (60, 120), speed=65, lift=60, gravity=10, spread=160)
    fx.particle('mist', 3, 9, 4, (80, 110, 128), 320, grow=40, speed=10, spread=120, fade=True)
    fx.label('main'); fx.when(0, 'fall'); fx.end(1)
    fx.label('fall')
    fx.lin(big, at(fx.TSIZE, 1), 1, 380)
    fx.vcopy(fx.DEST, fx.TGT); fx.lin(fx.T, big, 1, 0, 2); fx.sub_(at(fx.DEST, 1), fx.T)
    fx.vcopy(fx.AT, fx.DEST); fx.sub_(at(fx.AT, 1), 1500); fx.call('boulder'); fx.ret()
    fx.travel('boulder', 1, 7, 'boulder_render', 'boulder_land')
    fx.label('boulder_render')
    fx.lin(fx.T2, big, 13, 0, 10)
    fx.sprite(POS, soft, fx.T2, cell=5); fx.sprite(POS, tint, big, fx.T2, cell=0); fx.ret()
    fx.label('boulder_land')
    fx.sound(40); fx.hit()
    fx.set(idx, 0); fx.call('spout', 6); fx.call('ripple')
    fx.emit('mist', fx.TCHEST, 3); fx.emit('bead', times=16); fx.ret()
    spout = fx.pool('spout', 6, 2)
    fx.begin('spout', spout, 'spout_render', inherit=False)
    fx.lin(fx.T, idx, 683, 200); fx.add(idx, 1)
    fx.lin(fx.T3, at(fx.TSIZE, 0), 1, 260)
    fx.vcopy(POS, fx.TGT); fx.circle(fx.TV, fx.T, fx.T3, 0); fx.vadd(POS, fx.TV)
    fx.rnd(iv(FREE), 380, 620); fx.ret()
    fx.label('spout_tick'); fx.life(12)
    fx.lin(fx.T, FRAME, 170); fx.sin(iv(FREE + 4), fx.T, iv(FREE)); fx.add(iv(FREE + 4), 30); fx.ret()
    fx.label('spout_render')
    fx.pillar(POS, 230, iv(FREE + 4), tint, cell=1)
    fx.vcopy(fx.TV, POS); fx.sub_(at(fx.TV, 1), iv(FREE + 4))
    fx.sprite(fx.TV, soft, 190, cell=4); fx.ret()
    rip = fx.pool('ripple', 1)
    fx.begin('ripple', rip, 'ripple_render', inherit=False); fx.vcopy(POS, fx.TGT); fx.sub_(at(POS, 1), 14); fx.ret()
    fx.label('ripple_tick'); fx.life(10); fx.ret()
    fx.label('ripple_render')
    fx.lin(fx.T3, FRAME, 90, 200)
    fx.lin(fx.T, FRAME, -11, 124); fx.vset(fade, fx.T, fx.T, fx.T)
    fx.flat(POS, fx.T3, fade, cell=3); fx.ret()
    return fx


def tidal_wave():
    """A wall of water rises at the caster's feet and runs at the enemies, growing as it goes, and breaks on all of
    them."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(AQUA)
    fx.paint(0, column()); fx.paint(1, foam()); fx.paint(2, glow(15, 1.0)); fx.paint(3, glow(8, 1.0))
    fx.paint(4, column(21))
    body, crest = fx.colour(40, 70, 118), fx.colour(70, 96, 120)
    run = 22
    step, wl, wf = fx.vec(), fx.var(), fx.var()
    fx.particle('splash', 16, 14, 2, (70, 96, 124), 130, grow=14, flat=((-20, 20), (-60, -25), (-20, 20)),
                gravity=5, spread=260)
    fx.particle('bead', 16, 12, 3, (120, 128, 128), (60, 110), speed=60, lift=50, gravity=9, spread=200)
    fx.label('main'); fx.when(0, 'rise'); fx.end(1)
    fx.label('rise')
    fx.vcopy(step, fx.TGT); fx.vsub(step, fx.SRC); fx.vdiv(step, run)
    fx.vlen(wl, step); fx.br(wl, '>=', 1, 'rise_go'); fx.set(wl, 1)
    fx.label('rise_go'); fx.vcopy(fx.AT, fx.SRC); fx.call('wall'); fx.ret()
    wall = fx.pool('wall', 1)
    fx.begin('wall', wall, 'noop', inherit=False); fx.vcopy(POS, fx.AT); fx.sound(38); fx.ret()
    fx.label('wall_tick')
    fx.br(FRAME, '>', run, 'wall_break')
    fx.vadd(POS, step); fx.set(wf, FRAME)
    fx.call('crest', 3); fx.ret()
    fx.label('wall_break')
    fx.br(FRAME, '!=', run + 1, 'wall_after')
    fx.sound(40)

    def one():
        fx.hit(); fx.emit('splash', fx.TCHEST, 5); fx.emit('bead', times=5)
    fx.each_target(one); fx.ret()
    fx.label('wall_after'); fx.life(run + 3); fx.ret()
    # one column of the wall: somewhere along a line across the wave's path, running with it, swelling and sinking
    cr = fx.pool('crest', 30, 3)
    lat, top, h = iv(FREE), iv(FREE + 4), iv(FREE + 8)
    fx.begin('crest', cr, 'crest_render', inherit=False)
    fx.from_parent(POS, 4)
    fx.rnd(lat, -620, 620)
    fx.lin(fx.T, at(step, 2), 1); fx.mul(fx.T, lat); fx.div(fx.T, wl); fx.sub_(at(POS, 0), fx.T)
    fx.lin(fx.T, at(step, 0), 1); fx.mul(fx.T, lat); fx.div(fx.T, wl); fx.add(at(POS, 2), fx.T)
    fx.rnd(top, 140, 240); fx.lin(fx.T, wf, 20); fx.add(top, fx.T)
    fx.set(h, 40); fx.ret()
    fx.label('crest_tick'); fx.life(10)
    fx.vadd(POS, step)
    fx.lin(fx.T, FRAME, 200); fx.sin(h, fx.T, top); fx.add(h, 40); fx.ret()
    fx.label('crest_render')
    fx.set(fx.T2, lat); fx.mod(fx.T2, 2); fx.br(fx.T2, '==', 0, 'crest_b')
    fx.pillar(POS, 260, h, body, cell=0); fx.jmp('crest_top')
    fx.label('crest_b'); fx.pillar(POS, 260, h, body, cell=4)
    fx.label('crest_top')
    fx.vcopy(fx.TV, POS); fx.sub_(at(fx.TV, 1), h)
    fx.sprite(fx.TV, crest, 200, cell=1); fx.ret()
    return fx


def ocean_fury():
    """The field sinks into deep water: great drops fall, a twisting spout rises under every enemy, and it all
    breaks in one flash."""
    fx = Fx(delay=8, cast_sound=48, draw=True)
    fx.palette(AQUA)
    fx.paint(0, blob()); fx.paint(1, drop()); fx.paint(2, glow(8, 1.0)); fx.paint(3, ring(13, 2.0))
    fx.paint(4, foam()); fx.paint(5, glow(15, 1.1)); fx.paint(6, spiral())
    tint, soft, shade, fade = fx.colour(118, 128, 128), fx.colour(40, 84, 128), fx.vec(), fx.vec()
    surge, burst = 12, 26
    fx.particle('fall', 24, 8, 1, (90, 120, 128), (150, 240), flat=((0, 0), (95, 120), (0, 0)), spread=1500, sy=24)
    fx.particle('bead', 20, 12, 2, (120, 128, 128), (60, 120), speed=70, lift=60, gravity=10, spread=200)
    fx.particle('mist', 6, 10, 4, (80, 110, 128), 340, grow=45, speed=12, spread=160, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(surge, 'rise'); fx.when(burst, 'break')
    fx.br(fx.NOW, '>', burst, 'done')
    fx.vcopy(fx.AT, fx.DEST); fx.sub_(at(fx.AT, 1), 950); fx.call('fall', 2); fx.ret()
    fx.label('done'); fx.end(burst + 10)
    fx.label('draw')
    # the deep: red and green drain out of the screen; then the flash
    fx.lin(fx.T, fx.NOW, 7); fx.br(fx.NOW, '<', 10, 'draw_deep')
    fx.set(fx.T, 70); fx.br(fx.NOW, '<', burst, 'draw_deep')
    fx.lin(fx.T, fx.NOW, -7, 7 * (burst + 10))
    fx.label('draw_deep')
    fx.lin(fx.T2, fx.T, 6, 0, 10); fx.lin(fx.T3, fx.T, 1, 0, 6)
    fx.vset(shade, fx.T, fx.T2, fx.T3); fx.overlay(shade)
    fx.br(fx.NOW, '<', burst, 'noop'); fx.br(fx.NOW, '>', burst + 6, 'noop')
    fx.lin(fx.T, fx.NOW, -12, 12 * (burst + 7)); fx.vset(shade, fx.T, fx.T, fx.T)
    fx.overlay(shade, blend='add'); fx.ret()
    fx.label('begin'); fx.vcopy(fx.DEST, fx.TGT); fx.ret()
    fx.label('rise')
    fx.sound(38)

    def one():
        fx.hit(); fx.vcopy(fx.AT, fx.TGT); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 300); fx.call('spout')
    fx.each_target(one); fx.ret()
    fx.label('break'); fx.sound(15); fx.ret()
    spout = fx.pool('spout', 3, 1)
    fx.begin('spout', spout, 'spout_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.set(iv(FREE), fx.SZ); fx.ret()
    fx.label('spout_tick')
    fx.br(FRAME, '!=', burst - surge, 'spout_on')
    fx.emit('mist', POS, 2); fx.vcopy(fx.AT, POS); fx.sub_(at(fx.AT, 1), iv(FREE)); fx.call('bead', 6); fx.ret()
    fx.label('spout_on'); fx.life(burst - surge + 6); fx.ret()
    fx.label('spout_render')
    # a whirl on the ground and eight balls of water wound round a rising axis
    fx.lin(fx.T2, FRAME, -300)
    fx.lin(fx.T3, FRAME, 40, 120); fx.br(FRAME, '<', 8, 'spout_floor'); fx.set(fx.T3, 440)
    fx.label('spout_floor')
    fx.vcopy(fx.TV, POS); fx.sub_(at(fx.TV, 1), 14)
    fx.flat(fx.TV, fx.T3, soft, cell=6, angle=fx.T2)
    for k in range(8):
        skip = fx.label()
        fx.br(FRAME, '<', k + 1, skip)
        fx.lin(fx.T2, FRAME, 380, 520 * k)
        fx.circle(fx.TV, fx.T2, 150 - 8 * k, 0); fx.vadd(fx.TV, POS)
        fx.lin(fx.T, iv(FREE), k + 1, 0, 8); fx.sub_(at(fx.TV, 1), fx.T)
        fx.sprite(fx.TV, tint if k % 2 else soft, 300 - 14 * k, cell=0)
        fx.label(skip)
    fx.ret()
    return fx


EFFECTS = {138: bubble_shot, 139: aqua_jet, 140: rain_dance, 141: whirlpool, 142: hydro_cannon, 143: sea_crush,
           144: tidal_wave, 145: ocean_fury}
