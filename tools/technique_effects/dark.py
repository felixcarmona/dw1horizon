"""The Darkness row's effects."""
from tools.technique_effects.kit import (FRAME, FREE, POS, Fx, at, clip, crescent, fbm, glow, grid, iv, polar, ring,
                                         segment, star)
import numpy as np

VIOLET = ['#000000', '#1c0038', '#5010a0', '#9030e0', '#c070ff', '#e8b8ff']


def bolt_links(seed):
    """Two cells of jagged lightning, end to end across the cell."""
    rs = np.random.RandomState(seed)
    out = []
    for _ in range(2):
        pts = [(2, 16)] + [(2 + 28 * (i + 1) / 5, 6 + rs.rand() * 20) for i in range(4)] + [(30, 16)]
        lum = np.zeros((32, 32))
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            lum = np.maximum(lum, segment(x0, y0, x1, y1, 2.0) + 0.5 * segment(x0, y0, x1, y1, 5.5))
        out.append(clip(lum))
    return out


def dark_orb(seed=23):
    """A dark heart inside a bright, ragged rim."""
    r, _ = polar(15.5, 15.5)
    return clip(ring(10.5, 3.5) ** 0.8 * (0.75 + 0.5 * fbm(seed)) + 0.18 * (r < 10))


def dark_bolt():
    """A dark orb gathers motes over the caster and marks the spot where the target stands; a moment later a jagged
    bolt strikes that spot and throws shards."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(VIOLET)
    a, b = bolt_links(7)
    fx.paint(0, a); fx.paint(1, b); fx.paint(2, dark_orb()); fx.paint(3, star(4, 3, 10, 6) ** 1.2)
    rim, core = fx.colour(72, 22, 128), fx.colour(90, 40, 128)
    step, idx = fx.vec(), fx.var()
    charge, links = 16, 12
    fx.particle('shard', 12, 11, 3, (90, 40, 128), 200, grow=-14, speed=55, spread=60)
    fx.particle('mark', 1, 9, 2, (60, 20, 110), 60, grow=30, fade=True)

    fx.label('main'); fx.when(0, 'open'); fx.end(1)
    fx.label('open')
    fx.vcopy(fx.AT, fx.SRC)
    fx.lin(fx.T, at(fx.SSIZE, 1), 1, 120); fx.sub_(at(fx.AT, 1), fx.T)        # over the caster's head
    fx.call('orb'); fx.ret()

    orb = fx.pool('orb', 1)
    fx.begin('orb', orb, 'orb_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.sound(-55); fx.ret()
    fx.label('orb_tick')
    fx.br(FRAME, '>=', charge, 'orb_fire')
    fx.after(charge - 6, 'orb_aim')
    fx.call('mote', 2); fx.ret()
    fx.label('orb_aim'); fx.aim(); fx.emit('mark', fx.TCHEST); fx.ret()
    fx.label('orb_fire')
    fx.br(FRAME, '!=', charge, 'orb_after')
    fx.vcopy(step, fx.TCHEST); fx.vsub(step, POS); fx.vdiv(step, links)
    fx.set(idx, 0); fx.call('link', links)
    fx.sound(13); fx.ret()
    fx.label('orb_after')
    fx.br(FRAME, '==', charge + 3, 'orb_hit')
    fx.life(charge + 8); fx.ret()
    fx.label('orb_hit')
    fx.sound(16); fx.strike(fx.TGT, 120); fx.emit('shard', fx.TCHEST, 12); fx.ret()
    fx.label('orb_render')
    fx.br(FRAME, '>', charge + 2, 'noop')
    fx.lin(fx.T, FRAME, 13, 50)
    fx.sprite(POS, rim, fx.T, cell=2); fx.ret()

    # motes of darkness drawn into the orb
    mote = fx.pool('mote', 14, 3)
    fx.begin('mote', mote, 'mote_render', inherit=False)
    fx.from_parent(iv(FREE), 4)
    fx.vcopy(POS, iv(FREE)); fx.scatter(POS, 700)
    fx.vsub(iv(FREE), POS); fx.vdiv(iv(FREE), 7); fx.ret()
    fx.label('mote_tick'); fx.life(6); fx.vadd(POS, iv(FREE)); fx.ret()
    fx.label('mote_render'); fx.sprite(POS, core, 70, cell=3); fx.ret()

    # one link of the bolt: placed along the line, redrawn with a new jitter every tick
    link = fx.pool('link', links, 0)
    fx.begin('link', link, 'link_render', inherit=False)
    fx.from_parent(POS, 4)
    fx.vcopy(fx.TV, step); fx.vmul(fx.TV, idx); fx.vadd(POS, fx.TV)
    fx.add(idx, 1); fx.ret()
    fx.label('link_tick'); fx.life(6); fx.ret()
    fx.label('link_render')
    fx.vcopy(fx.TV, POS); fx.scatter(fx.TV, 140)
    fx.rnd(fx.T2, 0, 1); fx.mul(fx.T2, 32)
    a_ = fx.a
    a_.pusha(*fx.TV); a_.pusha(*rim); a_.push(260); a_.push(260); a_.pushv(*fx.T2); a_.push(0); a_.push(31)
    a_.push(31); a_.sub('renderCenteredSprite'); fx.ret()
    return fx


SHADE = ['#000000', '#202020', '#606060', '#a0a0a0', '#e0e0e0']
VENOM = ['#000000', '#1a0830', '#3c1a5c', '#4a5a2a', '#78b030', '#c8f060']


def claw_marks():
    """Three curved slashes, tapering at both ends."""
    x, y = grid()
    lum = np.zeros((32, 32))
    for i in (-1, 0, 1):
        for t in np.linspace(0, 1, 40):
            cx = 24 - 17 * t + 7.5 * i + 4 * np.sin(np.pi * t)
            cy = 3 + 26 * t + 2.5 * i
            w = 0.5 + 2.0 * np.sin(np.pi * t) ** 0.7
            lum = np.maximum(lum, clip(1.25 - np.hypot(x - cx, y - cy) / w))
    return clip(lum)


def eye():
    """An almond eye with a slit pupil."""
    x, y = grid()
    lid = 9.5 * np.cos(np.clip((x - 16) / 15, -1, 1) * np.pi / 2) ** 0.8
    d = np.abs(y - 16)
    rim = clip(1 - np.abs(d - lid) / 1.6) * (np.abs(x - 16) < 15)
    iris = clip(1 - np.abs(np.hypot(x - 16, y - 16) - 6) / 1.5) * (d < lid)
    slit = clip(1 - np.abs(x - 16) / 1.4) * (d < 5.5)
    return clip(rim + 0.7 * iris + slit)


def ghost():
    """A small wisp with two eyes and a tail."""
    x, y = grid()
    head = clip((9 - np.hypot(x - 16, y - 12)) / 2)
    tail = clip(1 - np.abs(x - 16 - 3 * np.sin(y / 3.0)) / np.maximum(0.6, (30 - y) * 0.45)) * (y > 12) * (y < 30)
    eyes = (np.hypot(x - 12.5, y - 11) < 2.2) | (np.hypot(x - 19.5, y - 11) < 2.2)
    return clip(np.maximum(head, tail) * (0.55 + 0.45 * fbm(5))) * ~eyes


def talon():
    """A curved fang standing on its base."""
    x, y = grid()
    t = (31 - y) / 31
    cx = 16 + 7 * t * t
    w = 6.5 * (1 - t) ** 0.8 + 0.4
    return clip(1.3 - np.abs(x - cx) / w) * (0.6 + 0.4 * t)


def cloud(seed):
    r, _ = polar()
    return clip((1 - r / 15) * 1.6) * (0.35 + 0.9 * fbm(seed))


def streak():
    x, y = grid()
    return clip(1 - np.abs(x - 16) / 3.0) * clip(np.sin(np.pi * y / 32) * 1.4)


def rune_ring():
    r, ang = polar()
    spokes = clip(np.cos(ang * 6) * 3 - 1.8) * (np.abs(r - 9) < 3)
    return clip(ring(13.5, 1.6) + ring(6, 1.2) + 0.8 * spokes)


def shadow_claw():
    """Three claw marks tear across the target, then cross it, out of a patch of darkness."""
    fx = Fx(delay=8, cast_sound=19)
    fx.palette(VIOLET); fx.palette(SHADE)
    fx.paint(0, claw_marks()); fx.paint(1, glow(15, 0.8)); fx.paint(2, star(4, 3, 10, 6) ** 1.2)
    fx.paint(3, claw_marks()[:, ::-1])
    fx.particle('gloom', 2, 10, 1, (128, 128, 128), None, grow=40, clut=1, blend='sub', fade=True)
    fx.particle('rake', 1, 6, 0, (128, 128, 128), None, grow=45, fade=True)
    fx.particle('cross', 1, 7, 3, (128, 128, 128), None, grow=45, fade=True)
    fx.particle('shard', 10, 10, 2, (90, 40, 128), 170, grow=-15, speed=60, lift=20, gravity=8, spread=80)
    fx.label('main'); fx.when(0, 'first'); fx.when(4, 'second'); fx.end(5)
    fx.label('first')
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 15, 320, 10)
    fx.emit('gloom', fx.TCHEST); fx.emit('rake'); fx.ret()
    fx.label('second')
    fx.sound(20); fx.hit()
    fx.emit('cross', fx.TCHEST); fx.emit('gloom'); fx.emit('shard', times=10); fx.ret()
    return fx


def nightmare():
    """An eye opens over the target and stares rings of sleep down into it."""
    fx = Fx(delay=8, cast_sound=31)
    fx.palette(VIOLET); fx.palette(SHADE)
    fx.paint(0, eye()); fx.paint(1, ring(12, 2.2)); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 8))
    tint = fx.colour(128, 128, 128)
    dim, open_ = fx.vec(), fx.var()
    fx.particle('stare', 8, 9, 1, (80, 40, 128), 420, grow=-36, flat=((0, 0), (40, 40), (0, 0)))
    fx.particle('dream', 10, 12, 3, (128, 128, 128), (60, 120), speed=25, lift=18, spread=200, fade=True)
    fx.label('main'); fx.when(0, 'open'); fx.end(1)
    fx.label('open')
    fx.vcopy(fx.AT, fx.TGT)
    fx.lin(fx.T, at(fx.TSIZE, 1), 1, 300); fx.sub_(at(fx.AT, 1), fx.T)
    fx.call('eye'); fx.ret()
    eye_ = fx.pool('eye', 1)
    fx.begin('eye', eye_, 'eye_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('eye_tick')
    fx.life(34)
    fx.br(FRAME, '<', 8, 'noop'); fx.br(FRAME, '>', 24, 'noop')
    fx.vcopy(fx.AT, POS)
    fx.set(fx.T2, FRAME); fx.mod(fx.T2, 2); fx.br(fx.T2, '!=', 0, 'eye_hit')
    fx.call('stare')
    fx.label('eye_hit')
    fx.br(FRAME, '!=', 18, 'noop')
    fx.sound(34); fx.hit(); fx.emit('dream', fx.TCHEST, 10); fx.ret()
    fx.label('eye_render')
    # the lids part over eight ticks and close over the last eight
    fx.lin(open_, FRAME, 1); fx.br(FRAME, '<=', 8, 'eye_draw')
    fx.set(open_, 8); fx.br(FRAME, '<=', 26, 'eye_draw')
    fx.lin(open_, FRAME, -1, 34)
    fx.label('eye_draw')
    fx.lin(fx.T, open_, 14); fx.vset(dim, fx.T, fx.T, fx.T)
    fx.sprite(POS, dim, 620, cell=2, clut=1, blend='sub')
    fx.lin(fx.T2, open_, 52, 4)
    fx.sprite(POS, tint, 440, fx.T2, cell=0); fx.ret()
    return fx


def evil_whisper():
    """Three wisps snake from the caster to the target and sink through it as closing rings: its guard falls."""
    fx = Fx(delay=8, cast_sound=31)
    fx.palette(VIOLET)
    fx.paint(0, ghost()); fx.paint(1, glow(13, 1.4)); fx.paint(2, ring(13, 1.8))
    tint, low = fx.colour(110, 70, 128), fx.colour(96, 48, 128)
    fx.particle('trail', 18, 6, 1, (70, 30, 110), 210, grow=-20, fade=True)
    fx.label('main')
    for t in (0, 5, 10):
        fx.when(t, 'send')
    fx.end(11)
    fx.label('send'); fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('wisp'); fx.ret()
    fx.travel('wisp', 3, 14, 'wisp_render', 'wisp_arrive', every='wisp_trail')
    fx.label('wisp_wave')                     # TV: where the wisp is drawn, swaying about its line
    fx.vcopy(fx.TV, POS)
    fx.lin(fx.T, FRAME, 520); fx.sin(fx.T2, fx.T, 110); fx.add(at(fx.TV, 1), fx.T2)
    fx.cos(fx.T2, fx.T, 110); fx.add(at(fx.TV, 0), fx.T2); fx.ret()
    fx.label('wisp_trail'); fx.call('wisp_wave'); fx.emit('trail', fx.TV); fx.ret()
    fx.label('wisp_render'); fx.call('wisp_wave'); fx.sprite(fx.TV, tint, 340, cell=0); fx.ret()
    fx.label('wisp_arrive'); fx.sound(34); fx.hit(); fx.call('sink'); fx.ret()
    sink = fx.pool('sink', 3)
    fx.begin('sink', sink, 'sink_render', inherit=False); fx.ret()
    fx.label('sink_tick'); fx.life(12); fx.ret()
    fx.label('sink_render')
    fx.vcopy(fx.TV, fx.TGT)
    fx.lin(fx.T, FRAME, -1, 13); fx.mul(fx.T, at(fx.TSIZE, 1)); fx.div(fx.T, 12); fx.sub_(at(fx.TV, 1), fx.T)
    fx.lin(fx.T3, at(fx.TSIZE, 0), 2, 260); fx.lin(fx.T2, FRAME, -12, 0); fx.add(fx.T3, fx.T2)
    fx.lin(fx.T2, FRAME, 170)
    fx.flat(fx.TV, fx.T3, low, cell=2, angle=fx.T2); fx.ret()
    return fx


def death_grip():
    """Five talons rise out of a pit under the target and close on it."""
    fx = Fx(delay=8, cast_sound=21)
    fx.palette(VIOLET); fx.palette(SHADE)
    fx.paint(0, talon()); fx.paint(1, glow(15, 1.0)); fx.paint(2, star(4, 3, 10, 6) ** 1.2)
    tint, dark = fx.colour(120, 90, 128), fx.colour(120, 120, 120)
    idx = fx.var()
    fx.particle('shard', 12, 12, 2, (90, 40, 128), 190, grow=-13, speed=45, lift=60, gravity=9, spread=120)
    fx.particle('crush', 1, 7, 1, (128, 128, 128), None, grow=60, clut=1, blend='sub', fade=True)
    fx.label('main'); fx.when(0, 'rise'); fx.when(9, 'close'); fx.end(10)
    fx.label('rise')
    fx.vcopy(fx.AT, fx.TGT); fx.call('pit')
    fx.set(idx, 0); fx.call('talon', 5); fx.ret()
    fx.label('close')
    fx.sound(20); fx.hit()
    fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 200)
    fx.emit('crush', fx.TCHEST); fx.emit('shard', times=12); fx.ret()
    pit = fx.pool('pit', 1)
    fx.begin('pit', pit, 'pit_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('pit_tick'); fx.life(18); fx.ret()
    fx.label('pit_render')
    fx.lin(fx.T3, FRAME, 60, 120); fx.br(FRAME, '<', 6, 'pit_draw'); fx.set(fx.T3, 480)
    fx.label('pit_draw'); fx.flat(POS, fx.T3, dark, cell=1, clut=1, blend='sub'); fx.ret()
    tal = fx.pool('talon', 5, 1)
    fx.begin('talon', tal, 'talon_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.lin(iv(FREE), idx, 819, 300); fx.add(idx, 1); fx.ret()
    fx.label('talon_tick'); fx.life(16); fx.ret()
    fx.label('talon_render')
    # the ring of talons closes from tick 5 to 9; each rises over the first five ticks and sinks at the end
    fx.set(fx.T3, 340); fx.br(FRAME, '<', 5, 'talon_at')
    fx.lin(fx.T3, FRAME, -55, 615); fx.br(FRAME, '<', 9, 'talon_at'); fx.set(fx.T3, 120)
    fx.label('talon_at')
    fx.circle(fx.TV, iv(FREE), fx.T3, 0); fx.vadd(fx.TV, POS)
    fx.lin(fx.T2, at(fx.TSIZE, 1), 15, 260, 10)
    fx.lin(fx.T3, FRAME, 1, 1); fx.br(FRAME, '<', 5, 'talon_h')
    fx.set(fx.T3, 6); fx.br(FRAME, '<', 12, 'talon_h')
    fx.lin(fx.T3, FRAME, -1, 17)
    fx.label('talon_h'); fx.mul(fx.T2, fx.T3); fx.div(fx.T2, 6)
    fx.pillar(fx.TV, 280, fx.T2, tint, cell=0); fx.ret()
    return fx


def venom_mist():
    """A rolling bank of poison drifts from the caster over every enemy and hangs there, bubbling."""
    fx = Fx(delay=8, cast_sound=32)
    fx.palette(VENOM)
    fx.paint(0, cloud(3)); fx.paint(1, cloud(11)); fx.paint(2, ring(8, 2.0) + 0.5 * glow(5, 1))
    drift = fx.vec()
    fx.particle('puff', 14, 16, 0, (128, 128, 128), (220, 320), grow=22, speed=14, spread=140, blend='half',
                drift=drift, spin=3)
    fx.particle('hang', 12, 22, 1, (128, 128, 128), (260, 380), grow=10, speed=10, spread=260, blend='half', spin=-2)
    fx.particle('bubble', 12, 14, 2, (128, 128, 128), (50, 110), speed=10, lift=22, spread=300)
    fx.label('main')
    fx.when(0, 'aimed')
    fx.br(fx.NOW, '>', 11, 'settle')
    fx.emit('puff', fx.CHEST); fx.ret()
    fx.label('settle'); fx.when(13, 'poison'); fx.end(14)
    fx.label('aimed'); fx.vcopy(drift, fx.TCHEST); fx.vsub(drift, fx.CHEST); fx.vdiv(drift, 15); fx.ret()
    fx.label('poison')
    fx.sound(33)

    def one():
        fx.hit(); fx.emit('hang', fx.TCHEST, 4); fx.emit('bubble', times=4)
    fx.each_target(one); fx.ret()
    return fx


def black_gate():
    """A gate opens on the ground under the target: lances of darkness shoot up through it, then a black column."""
    fx = Fx(delay=8, cast_sound=46)
    fx.palette(VIOLET); fx.palette(SHADE)
    fx.paint(0, rune_ring()); fx.paint(1, glow(15, 1.0)); fx.paint(2, streak()); fx.paint(3, star(4, 3, 10, 6) ** 1.2)
    tint, dark = fx.colour(110, 60, 128), fx.vec()
    fx.particle('lance', 12, 9, 2, (120, 70, 128), (220, 320), flat=((0, 0), (-150, -90), (0, 0)), spread=420,
                sy=56, fade=True)
    fx.particle('shard', 10, 12, 3, (90, 40, 128), 190, grow=-13, speed=60, lift=40, gravity=8, spread=120)
    fx.label('main'); fx.when(0, 'open')
    fx.br(fx.NOW, '<', 8, 'noop'); fx.br(fx.NOW, '>', 20, 'die')
    fx.vcopy(fx.AT, fx.TGT); fx.sub_(at(fx.AT, 1), 40); fx.call('lance')
    fx.when(11, 'strike'); fx.ret()
    fx.label('open'); fx.vcopy(fx.AT, fx.TGT); fx.call('gate'); fx.ret()
    fx.label('strike'); fx.sound(47); fx.strike(fx.TGT, 300); fx.emit('shard', fx.TCHEST, 10); fx.ret()
    gate = fx.pool('gate', 1)
    fx.begin('gate', gate, 'gate_render', inherit=False); fx.vcopy(POS, fx.AT); fx.sub_(at(POS, 1), 12); fx.ret()
    fx.label('gate_tick'); fx.life(30); fx.ret()
    fx.label('gate_render')
    fx.lin(fx.T3, FRAME, 90, 60); fx.br(FRAME, '<', 6, 'gate_out')
    fx.set(fx.T3, 600); fx.br(FRAME, '<', 24, 'gate_out')
    fx.lin(fx.T3, FRAME, -95, 2880)
    fx.label('gate_out')
    fx.set(fx.T, 100); fx.vset(dark, fx.T, fx.T, fx.T)
    fx.set(fx.SZ, fx.T3)
    fx.flat(POS, fx.SZ, dark, cell=1, clut=1, blend='sub')
    fx.lin(fx.T2, FRAME, 60)
    fx.flat(POS, fx.SZ, tint, cell=0, angle=fx.T2)
    # the column: from tick 14 to 22, as wide as the gate at its peak
    fx.br(FRAME, '<', 14, 'noop'); fx.br(FRAME, '>', 22, 'noop')
    fx.lin(fx.T3, FRAME, -1, 18); fx.br(fx.T3, '>=', 0, 'gate_col'); fx.mul(fx.T3, -1)
    fx.label('gate_col'); fx.lin(fx.T3, fx.T3, -90, 520)
    fx.lin(fx.T2, at(fx.TSIZE, 1), 2, 500)
    fx.pillar(POS, fx.T3, fx.T2, dark, cell=2, clut=1, blend='sub')
    fx.lin(fx.T3, fx.T3, 1, 0, 2)
    fx.pillar(POS, fx.T3, fx.T2, tint, cell=2); fx.ret()
    return fx


def abyss_requiem():
    """The sky dims; a black sun swells over the enemies, drinking in the light, and breaks over all of them."""
    fx = Fx(delay=8, cast_sound=48, draw=True)
    fx.palette(VIOLET); fx.palette(SHADE)
    fx.paint(0, dark_orb(31)); fx.paint(1, glow(15, 0.8)); fx.paint(2, star(4, 3, 10, 6) ** 1.2)
    fx.paint(3, ring(13.5, 1.8)); fx.paint(4, streak())
    rim, shade, dark = fx.colour(110, 50, 128), fx.vec(), fx.colour(128, 128, 128)
    spot = fx.vec()
    swell = 22
    fx.particle('shard', 16, 14, 2, (100, 50, 128), 220, grow=-13, speed=70, lift=50, gravity=9, spread=150)
    fx.particle('pyre', 4, 10, 4, (128, 80, 128), 520, grow=50, sy=40, fade=True)
    fx.label('main'); fx.when(0, 'rise'); fx.end(swell + 16)
    fx.label('draw')
    # the screen dims as the sun swells and clears after it breaks
    fx.lin(fx.T, fx.NOW, 6); fx.br(fx.NOW, '<', 12, 'draw_dim')
    fx.set(fx.T, 72); fx.br(fx.NOW, '<', swell + 4, 'draw_dim')
    fx.lin(fx.T, fx.NOW, -6, 6 * (swell + 16))
    fx.label('draw_dim'); fx.vset(shade, fx.T, fx.T, fx.T); fx.overlay(shade); fx.ret()
    fx.label('rise')
    fx.vcopy(spot, fx.TGT); fx.vcopy(fx.AT, fx.TGT); fx.lin(fx.T, at(fx.TSIZE, 1), 1, 420); fx.sub_(at(fx.AT, 1), fx.T); fx.call('sun'); fx.ret()
    sun = fx.pool('sun', 1)
    fx.begin('sun', sun, 'sun_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('sun_tick')
    fx.br(FRAME, '>=', swell, 'sun_break')
    fx.call('mote', 2); fx.ret()
    fx.label('sun_break')
    fx.br(FRAME, '!=', swell, 'sun_after')
    fx.sound(15); fx.call('wave')

    def one():
        fx.hit(); fx.vcopy(fx.AT, fx.TGT); fx.sub_(at(fx.AT, 1), 500); fx.call('pyre'); fx.emit('shard', fx.TCHEST, 5)
    fx.each_within(spot, 900, one); fx.ret()
    fx.label('sun_after'); fx.life(swell + 5); fx.ret()
    fx.label('sun_render')
    fx.lin(fx.T, FRAME, 26, 100); fx.br(FRAME, '<=', swell, 'sun_draw')
    fx.lin(fx.T, FRAME, -130, 130 * (swell + 6))
    fx.label('sun_draw')
    fx.lin(fx.T2, fx.T, 5, 0, 4)
    fx.sprite(POS, dark, fx.T2, cell=1, clut=1, blend='sub')
    fx.lin(fx.T2, FRAME, 9)
    fx.sprite(POS, rim, fx.T, cell=0, rot=fx.T2); fx.ret()
    mote = fx.pool('mote', 16, 3)
    fx.begin('mote', mote, 'mote_render', inherit=False)
    fx.from_parent(iv(FREE), 4)
    fx.vcopy(POS, iv(FREE)); fx.scatter(POS, 1900)
    fx.vsub(iv(FREE), POS); fx.vdiv(iv(FREE), 8); fx.ret()
    fx.label('mote_tick'); fx.life(7); fx.vadd(POS, iv(FREE)); fx.ret()
    fx.label('mote_render'); fx.sprite(POS, rim, 110, cell=2); fx.ret()
    # the shock of the break: a ring racing out over the ground
    wave = fx.pool('wave', 1)
    fx.begin('wave', wave, 'wave_render', inherit=False); fx.vcopy(POS, spot); fx.sub_(at(POS, 1), 20); fx.ret()
    fx.label('wave_tick'); fx.life(12); fx.ret()
    fx.label('wave_render')
    fx.lin(fx.T3, FRAME, 150, 200)
    fx.lin(fx.T, FRAME, -9, 120); fx.vset(shade, fx.T, fx.T, fx.T)
    fx.flat(POS, fx.T3, shade, cell=3); fx.ret()
    return fx


EFFECTS = {122: shadow_claw, 123: dark_bolt, 124: nightmare, 125: evil_whisper, 126: death_grip, 127: venom_mist,
           128: black_gate, 129: abyss_requiem}
