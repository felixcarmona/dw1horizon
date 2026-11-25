"""Finishers written and painted here, one per species (keyed by species id): the beams of Tinmon, Hawkmon,
MetalGarurumon, Imperialdramon, ExVeemon, Halsemon, Lighdramon, Veedramon, MegaKabuterimon, MagnaAngemon, Lillymon,
MetalSeadramon, VenomMyotismon, AeroVeedramon, Magnadramon, Salamon and BlackGatomon."""
import math

import numpy as np

from tools.technique_effects.finishers import BLOOD, GOLD, VIOLET, ahead, arc, band, bar, bead, column, \
    fireball, flicker, gather, petal, puff, shard, tongue
from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, crescent, fbm, glow, grid, iv, polar, ring, \
    segment, star

FROST = ['#000000', '#103860', '#40a0d8', '#b0f0ff', '#ffffff']
RUBY = ['#000000', '#600010', '#e01030', '#ff8070', '#ffffff']
GLACIER = ['#000000', '#082070', '#2070e0', '#80d0ff', '#e8ffff', '#ffffff']
POSITRON = ['#000000', '#701000', '#f04000', '#ffa020', '#fff0a0', '#ffffff']
AMBER = ['#000000', '#703000', '#f08000', '#ffd040', '#ffffff']
GALE = ['#000000', '#0a4030', '#30b080', '#a0f0d0', '#ffffff']
BOLT = ['#000000', '#102070', '#3070ff', '#a0d8ff', '#ffffff']
VOLT = ['#000000', '#402070', '#a050f0', '#f0d060', '#ffffc0', '#ffffff']
LEAF = ['#000000', '#0a4010', '#30b030', '#b0f060', '#ffffc0']
PINK = ['#701040', '#c03078', '#f060a0', '#ffc0e0', '#ffffff']
DEEP = ['#000000', '#041860', '#1050d0', '#50b0ff', '#d0f8ff', '#ffffff']
ASH = ['#000000', '#404040', '#a0a0a0', '#ffffff']
SKY = ['#000000', '#104080', '#40a0f0', '#c0f0ff', '#ffffff']
ROSEFIRE = ['#000000', '#600828', '#e03060', '#ff9060', '#ffe8a0', '#ffffff']
HOWL = ['#000000', '#806020', '#f0c060', '#fff0b0', '#ffffff']
VBREATH = ['#000000', '#0a2a80', '#2878f0', '#90d8ff', '#f0ffff', '#ffffff']
EYE = ['#203000', '#607808', '#b8d010', '#f0ff60', '#ffffff']


# ----------------------------------------------------------------- paintings
def thin_bar(half=5.0, seed=4):
    """A narrow band across the cell."""
    x, y = grid()
    return clip(1 - np.abs(y - 16) / half) ** 0.8 * (0.85 + 0.2 * fbm(seed))


def snowflake():
    """Six arms, each with a pair of barbs."""
    lum = np.zeros((32, 32))
    for k in range(6):
        a = math.pi / 3 * k + math.pi / 6
        c, s = math.cos(a), math.sin(a)
        lum = np.maximum(lum, segment(16, 16, 16 + 13 * c, 16 + 13 * s, 1.3))
        for turn in (-1, 1):
            b = a + turn * math.pi / 3
            lum = np.maximum(lum, 0.85 * segment(16 + 8 * c, 16 + 8 * s, 16 + 8 * c + 4 * math.cos(b),
                                                 16 + 8 * s + 4 * math.sin(b), 1.0))
    return clip(lum + 0.5 * glow(5, 1.0))


def feather(flip=False):
    """A feather on the diagonal: a bright quill and barbs."""
    x, y = grid()
    if flip:
        x = 32 - x
    u, v = (x - 16) * 0.75 + (y - 16) * 0.66, -(x - 16) * 0.66 + (y - 16) * 0.75
    d = (u / 14.0) ** 2 + (v / (4.6 * clip(1.1 - (u / 15.0) ** 2) + 0.01)) ** 2
    body = clip((1 - d) * 3) * (0.5 + 0.25 * np.sin(u * 2.6 + np.abs(v)) ** 2)
    quill = clip(1 - np.abs(v) / 0.9) * (np.abs(u) < 15)
    return clip(np.maximum(body, 0.95 * quill))


def icicle(lean):
    """A spike of ice standing on the cell's foot, its point at the top."""
    x, y = grid()
    t = np.clip((y - 1) / 30, 0, 1)
    cx = 16 + lean * (1 - t) * 5
    w = 0.6 + 7.5 * t
    d = np.abs(x - cx) / w
    face = (d < 1) * (0.45 + 0.3 * (x < cx) + 0.2 * (1 - t))
    rim = clip(1 - np.abs(1 - d) * 4) * (d < 1.15)
    return clip(np.maximum(face, rim)) * (y > 1)


def xcross(width):
    """Two strokes crossed."""
    return clip(np.maximum(segment(4, 4, 28, 28, width), segment(28, 4, 4, 28, width)) + 0.3 * glow(9, 1.0))


def gust(seed):
    """A ragged ring of wind."""
    return clip(ring(11.5, 3.2) * (0.2 + 1.4 * fbm(seed)))


def zig(seed):
    """A bolt across the whole cell, entering and leaving at mid height."""
    r = np.random.default_rng(seed)
    pts = [(4.0 * k, 16 + (r.random() - 0.5) * 20 * (0 < k < 8)) for k in range(9)]
    lum = np.zeros((32, 32))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        lum = np.maximum(lum, segment(x0, y0, x1, y1, 2.0))
    k = 3 + seed % 3
    fork = segment(pts[k][0], pts[k][1], pts[k][0] + 6, pts[k][1] + (8 if pts[k][1] < 16 else -8), 1.3)
    return clip(np.maximum(lum, 0.7 * fork))


def breathbar(seed):
    """A band of light, bright along its middle, its edge barely stirring."""
    x, y = grid()
    edge = 9 + 3 * fbm(seed)
    return clip(1 - np.abs(y - 16) / edge) ** 1.5 * (0.75 + 0.35 * fbm(seed + 3))


def vee(width=2.6):
    return clip(np.maximum(segment(5, 5, 16, 27, width), segment(27, 5, 16, 27, width)))


def vblade():
    """A V of light: two keen edges and the glow between them."""
    x, y = grid()
    inside = clip(1 - np.abs(np.abs(x - 16) - (27 - y) * 0.5) / 5.0) * (y > 4) * (y < 28) * (np.abs(x - 16) < 12)
    return clip(vee(2.2) + 0.4 * inside)


def gate():
    """A round door: two rims, eight studs and the seam where its leaves meet."""
    r, ang = polar()
    studs = clip(np.cos(ang * 8) * 2 - 1.0) * clip(1 - np.abs(r - 12) / 1.7)
    seam = segment(16, 6, 16, 26, 0.9) * (r < 10)
    bars = np.maximum(segment(9, 12, 23, 12, 0.8), segment(9, 20, 23, 20, 0.8)) * (r < 10) * 0.7
    return clip(ring(13.6, 1.5) + ring(10.4, 1.0) + studs + seam + bars)


def flower():
    """Five petals round a heart."""
    r, ang = polar()
    edge = 4.5 + 9.5 * np.abs(np.cos(ang * 2.5)) ** 0.6
    body = clip((edge - r) / 1.4) * (0.45 + 0.4 * r / 14)
    vein = 0.15 * clip(1 - np.abs(np.sin(ang * 2.5)) * r / 1.5) * (r < edge)
    heart = clip((3.6 - r) / 1.2)
    return clip(np.maximum(body + vein, heart))


def torrent(seed):
    """A band of rushing water: streaks along it."""
    x, y = grid()
    rows = fbm(seed)[:, (seed * 7) % 32][:, None] * np.ones((1, 32))
    return clip(1 - np.abs(y - 16) / 14.5) ** 0.6 * (0.45 + 0.55 * rows + 0.25 * fbm(seed + 2))


def drop():
    x, y = grid()
    return clip(clip(1 - np.hypot(x - 16, y - 20) / 6.5) ** 0.7 + 0.9 * segment(16, 6, 16, 19, 2.4) * (y < 20))


def maw():
    """A ring of teeth round an open throat."""
    r, ang = polar()
    inner = 6.0 + 4.6 * np.abs(np.sin(ang * 5))
    return clip(clip((14 - r) / 1.2) * clip((r - inner) / 1.0) * (0.55 + 0.45 * clip((r - inner) / 6)))


def wavy(waves=8, depth=1.6):
    """A ring that ripples."""
    r, ang = polar()
    return clip(1 - np.abs(r - (11 + depth * np.sin(ang * waves))) / 1.8)


def note():
    """A quaver."""
    x, y = grid()
    head = clip((4.4 - np.hypot((x - 12) * 0.85, y - 23)) / 1.2)
    return clip(head + segment(15.5, 23, 15.5, 7, 1.2) + segment(15.5, 7, 22, 11, 1.5))


def cateyes():
    """A cat's two eyes side by side: almonds, each with a slit pupil (the dark of the palette). The cell is drawn
    twice as wide as it is tall."""
    x, y = grid()
    u = (np.where(x < 16, x - 8, x - 24)) * 2.0
    h = 10.0 * (1 - (u / 14.0) ** 2) + 0.25 * u * np.where(x < 16, 1, -1)
    inside = np.abs(u) < 14.0
    almond = clip((h - np.abs(y - 16)) / 1.2) * inside
    slit = clip(1.4 - np.abs(u) / (0.5 + 1.1 * clip(1 - (np.abs(y - 16) / 10.0) ** 2)))
    rim = clip(1 - np.abs(h - np.abs(y - 16)) / 1.4) * inside
    return np.where(almond > 0.06, clip(0.12 + (0.55 + 0.3 * clip(1 - np.hypot(u, y - 16) / 10)) * (1 - slit)
                                         + 0.3 * rim), 0.0)


def orb(seed):
    """A ball of lightning: a white heart in a crawling skin."""
    r, _ = polar()
    skin = clip(1 - np.abs(r - 10.5 - 2.5 * fbm(seed)) / 2.0)
    return clip(skin + clip(1 - r / 8.0) ** 0.8 + (r < 11) * 0.35 * fbm(seed + 4))


# ----------------------------------------------------------------- shared pieces
def muzzle_at(fx, out, tenths, reach):
    """out = the point that many tenths of the caster's height up, `reach` past its radius towards the target."""
    fx.vcopy(out, fx.SRC); fx.lin(fx.T3, at(fx.SSIZE, 1), tenths, 0, 10); fx.sub_(at(out, 1), fx.T3)
    ahead(fx, out, out, reach)


def across(fx, side, width):
    """side = the ground vector of that length square to the line from the caster to the target."""
    ok = fx.label()
    fx.vcopy(fx.TV, fx.TGT); fx.vsub(fx.TV, fx.SRC); fx.set(at(fx.TV, 1), 0)
    fx.vlen(fx.T, fx.TV); fx.br(fx.T, '>', 0, ok); fx.set(fx.T, 1)
    fx.label(ok)
    fx.lin(at(side, 0), at(fx.TV, 2), width, 0, fx.T); fx.set(at(side, 1), 0)
    fx.lin(at(side, 2), at(fx.TV, 0), -width, 0, fx.T)


def along(fx, out, src):
    """out = a random point of the line from src to the target's chest."""
    fx.rnd(fx.T, 1, 15); fx.vcopy(out, fx.TCHEST); fx.vsub(out, src); fx.vmul(out, fx.T); fx.vdiv(out, 16)
    fx.vadd(out, src)


def helix(fx, out, side, turn, phase, lift):
    """out = the running instance's place, moved round the line it flies along: `side` across it and `lift` up and
    down, at the angle FRAME * turn + phase."""
    fx.lin(fx.T3, FRAME, turn, phase)
    fx.cos(fx.T, fx.T3, 100); fx.vcopy(out, side); fx.vmul(out, fx.T); fx.vdiv(out, 100)
    fx.sin(at(out, 1), fx.T3, lift); fx.vadd(out, POS)


def ray(fx, name, src, life, width, cell, edge, core, clut=0, jitter=30, tip=None, alt=None, core_cell=None,
        core_clut=None, core_blend='add'):
    """Define the routine `name`: a beam from src to the target's chest, which it follows, for `life` ticks: it
    swells, shivers and thins out. edge and core are its two colours; alt: a second cell it swaps with every tick;
    tip: the cell of the lights at its two ends."""
    pool = fx.pool(name, 1)
    draw = fx.label()
    core_cell = cell if core_cell is None else core_cell
    core_clut = clut if core_clut is None else core_clut
    fx.begin(name, pool, name + '_render', inherit=False); fx.vcopy(POS, src); fx.ret()
    fx.label(name + '_tick'); fx.life(life); fx.aim(); fx.ret()
    fx.label(name + '_render')
    fx.lin(fx.T3, FRAME, width // 3, width // 4); fx.br(FRAME, '<', 2, draw)
    fx.set(fx.T3, FRAME); fx.mod(fx.T3, 2); fx.mul(fx.T3, jitter); fx.add(fx.T3, width)
    fx.br(FRAME, '<', life - 3, draw)
    fx.lin(fx.T3, FRAME, -(width // 4), (width // 4) * life + 16)
    fx.label(draw)

    def body(c):
        band(fx, src, fx.TCHEST, fx.T3, edge, c, clut)
        fx.lin(fx.T2, fx.T3, 1, 0, 2); band(fx, src, fx.TCHEST, fx.T2, core, core_cell, core_clut, core_blend)
    if alt is None:
        body(cell)
    else:
        other, done = fx.label(), fx.label()
        fx.set(fx.F2, FRAME); fx.mod(fx.F2, 2); fx.br(fx.F2, '==', 1, other)
        body(cell); fx.jmp(done)
        fx.label(other); body(alt)
        fx.label(done)
    if tip is not None:
        fx.lin(fx.T2, fx.T3, 2); fx.sprite(fx.TCHEST, core, fx.T2, cell=tip, clut=clut)
        fx.sprite(src, edge, fx.T2, cell=tip, clut=clut)
    fx.ret()
    return pool


# ----------------------------------------------------------------- Tinmon
def recovery_power():
    """Snowflakes drift into a pale lamp on Tinmon's chest, which lets go a thin cold beam; hoops of frost run down it
    one after another, and a great snowflake opens on the target and sheds small ones."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(FROST)
    fx.paint(0, thin_bar(9, 31)); fx.paint(1, snowflake()); fx.paint(2, glow(15, 1.2)); fx.paint(3, ring(12, 1.8))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, puff(27))
    tint, edge = fx.colour(128, 128, 128), fx.colour(40, 96, 128)
    muzzle = fx.vec()
    charge, life = 7, 12
    gather(fx, 'flake', 12, 1, (110, 128, 128), 120, 560, 6)
    fx.particle('lamp', 1, charge, 2, (70, 110, 128), 60, grow=34)
    fx.particle('freeze', 2, 10, 1, (128, 128, 128), None, grow=55, fade=True, spin=9)
    fx.particle('mist', 8, 12, 5, (40, 70, 90), (200, 300), grow=16, speed=14, lift=6, spread=120, fade=True)
    fx.particle('fall', 14, 14, 1, (120, 128, 128), (80, 130), speed=30, lift=30, gravity=5, spread=140, spin=14)
    fx.particle('glint', 10, 6, 4, (128, 128, 128), (70, 120), grow=-8, spread=100)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'fire'); fx.when(charge + 3, 'smite')
    for k in range(4):
        fx.when(charge + 1 + 2 * k, 'send')
    fx.br(fx.NOW, '>', charge - 3, 'main_end'); fx.emit('flake', muzzle, 2)
    fx.label('main_end'); fx.end(charge + life + 1)
    fx.label('begin'); muzzle_at(fx, muzzle, 6, 30); fx.emit('lamp', muzzle); fx.sound(-55); fx.ret()
    fx.label('fire'); fx.sound(13); fx.call('ray'); fx.ret()
    fx.label('send'); fx.aim(); fx.vcopy(fx.AT, muzzle); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('hoop'); fx.ret()
    fx.label('smite')
    fx.sound(20); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 10, 280, 10)
    fx.emit('freeze', fx.TCHEST); fx.emit('mist', times=6); fx.emit('fall', times=12); fx.ret()
    ray(fx, 'ray', muzzle, life, 80, 0, edge, tint, tip=2)
    fx.travel('hoop', 4, 4, 'hoop_render', 'noop', every='hoop_trail')
    fx.label('hoop_trail'); fx.emit('glint', POS); fx.ret()
    fx.label('hoop_render'); fx.sprite(POS, tint, 140, 320, cell=3); fx.ret()
    return fx


# ----------------------------------------------------------------- Hawkmon
def hawk_beam():
    """A glint turns on the feather of Hawkmon's brow and a hair-thin red beam leaps from it to the target, stinging
    it with a star; red feathers are left tumbling at both ends."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(RUBY)
    fx.paint(0, thin_bar(4.5, 12)); fx.paint(1, feather()); fx.paint(2, glow(15, 1.2))
    fx.paint(3, star(4, 1.5, 14, 14)); fx.paint(4, ring(12, 1.6)); fx.paint(5, feather(True))
    tint, edge = fx.colour(128, 128, 128), fx.colour(128, 30, 40)
    brow = fx.vec()
    charge, life = 6, 8
    fx.particle('gleam', 1, charge, 3, (128, 128, 128), 60, grow=50, spin=12)
    fx.particle('sting', 2, 8, 3, (128, 128, 128), None, grow=45, fade=True, spin=16)
    fx.particle('ringlet', 2, 7, 4, (128, 50, 60), 100, grow=70, fade=True)
    fx.particle('plume', 8, 18, 1, (128, 128, 128), (130, 190), flat=((-14, 14), (-30, -8), (-14, 14)), gravity=4,
                spread=120, spin=10)
    fx.particle('plume2', 8, 18, 5, (128, 128, 128), (130, 190), flat=((-14, 14), (-30, -8), (-14, 14)), gravity=4,
                spread=120, spin=-10)
    fx.particle('spark', 10, 9, 2, (128, 70, 70), (50, 90), grow=-6, speed=60, lift=20, gravity=6, spread=40)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'fire'); fx.when(charge + 2, 'smite')
    fx.end(charge + life + 1)
    fx.label('begin')
    muzzle_at(fx, brow, 9, 20); fx.emit('gleam', brow); fx.emit('plume'); fx.emit('plume2'); fx.sound(-55); fx.ret()
    fx.label('fire'); fx.sound(13); fx.call('ray'); fx.ret()
    fx.label('smite')
    fx.sound(16); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 8, 260, 10)
    fx.emit('sting', fx.TCHEST); fx.emit('ringlet'); fx.emit('spark', times=8)
    fx.emit('plume', times=4); fx.emit('plume2', times=4); fx.ret()
    ray(fx, 'ray', brow, life, 36, 0, edge, tint, jitter=12, tip=2)
    return fx


# ----------------------------------------------------------------- MetalGarurumon
def metal_wolf_claw():
    """Cold breath gathers at MetalGarurumon's jaws and pours out as a broad freezing beam that sheds rime; where it
    lands, spikes of ice shoot up round the target one after another, stand a moment and shatter."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(GLACIER)
    fx.paint(0, thin_bar(13, 44)); fx.paint(1, icicle(-1)); fx.paint(2, icicle(1)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, puff(52)); fx.paint(5, shard()); fx.paint(6, star(4, 2, 9, 6))
    tint, edge = fx.colour(128, 128, 128), fx.colour(30, 70, 128)
    mouth = fx.vec()
    idx = fx.const(0)
    charge, life = 6, 14
    fx.particle('breath', 8, 8, 4, (40, 70, 100), (140, 220), grow=20, speed=10, spread=140, fade=True)
    fx.particle('rime', 16, 10, 6, (128, 128, 128), (70, 120), flat=((-6, 6), (8, 22), (-6, 6)), spread=140, grow=-5)
    fx.particle('frost', 2, 9, 3, (70, 110, 128), None, grow=45, fade=True)
    fx.particle('chip', 18, 12, 5, (120, 128, 128), (90, 150), grow=-5, speed=60, lift=50, gravity=10, spread=120,
                spin=20)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'fire'); fx.when(charge + 3, 'smite')
    for k in range(3):
        fx.when(charge + 3 + 2 * k, 'rise')
    fx.br(fx.NOW, '>=', charge, 'main_beam'); fx.emit('breath', mouth); fx.jmp('main_end')
    fx.label('main_beam'); fx.br(fx.NOW, '>', charge + life - 3, 'main_end')
    along(fx, fx.TV2, mouth); fx.emit('rime', fx.TV2)
    fx.label('main_end'); fx.end(charge + life + 1)
    fx.label('begin'); muzzle_at(fx, mouth, 8, 40); fx.sound(-55); fx.ret()
    fx.label('fire'); fx.sound(13); fx.call('ray'); fx.ret()
    fx.label('smite')
    fx.sound(20); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 300, 10)
    fx.emit('frost', fx.TCHEST); fx.emit('chip', times=4); fx.ret()
    fx.label('rise'); fx.aim(); fx.sound(34); fx.call('spike', 2); fx.ret()
    ray(fx, 'ray', mouth, life, 150, 0, edge, tint, tip=3)
    spike = fx.pool('spike', 6, 2)
    tall, kind = iv(FREE), iv(FREE + 4)
    fx.begin('spike', spike, 'spike_render', inherit=False)
    fx.lin(fx.T, idx, 683, 200); fx.circle(POS, fx.T, 170, 0); fx.vadd(POS, fx.TGT)
    fx.rnd(tall, 420, 760); fx.set(kind, idx); fx.mod(kind, 2); fx.add(idx, 1); fx.ret()
    fx.label('spike_tick'); fx.life(11); fx.after(10, 'spike_break'); fx.ret()
    fx.label('spike_break')
    fx.sound(20); fx.vcopy(fx.AT, POS); fx.lin(fx.T, tall, 1, 0, 2); fx.sub_(at(fx.AT, 1), fx.T)
    fx.call('chip', 3); fx.ret()
    fx.label('spike_render')
    fx.set(fx.T3, tall); fx.mul(fx.T3, FRAME); fx.div(fx.T3, 3); fx.br(FRAME, '<', 3, 'spike_draw')
    fx.set(fx.T3, tall)
    fx.label('spike_draw')
    fx.lin(fx.T2, fx.T3, 1, 70, 4)
    fx.br(kind, '==', 1, 'spike_other')
    fx.pillar(POS, fx.T2, fx.T3, tint, cell=1); fx.ret()
    fx.label('spike_other'); fx.pillar(POS, fx.T2, fx.T3, tint, cell=2); fx.ret()
    return fx


# ----------------------------------------------------------------- Imperialdramon
def positron_laser():
    """Three hoops of light close one after another on the mouth of Imperialdramon's cannon; then it lets go a beam as
    broad as the target, hoops racing down it, and the screen whitens as it bursts on the target in fire and smoke."""
    fx = Fx(delay=8, cast_sound=0, draw=True)
    fx.palette(POSITRON)
    fx.paint(0, bar(63)); fx.paint(1, glow(15, 1.2)); fx.paint(2, ring(13, 1.6)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, puff(61)); fx.paint(5, fireball(71))
    tint, edge, wash = fx.colour(128, 128, 128), fx.colour(128, 50, 16), fx.vec()
    muzzle = fx.vec()
    charge, life = 10, 14
    smite = charge + 2
    gather(fx, 'mote', 14, 3, (128, 110, 60), 90, 640, 5)
    fx.particle('coil', 3, 7, 2, (128, 90, 40), 580, grow=-72)
    fx.particle('lamp', 1, charge, 1, (128, 100, 60), 60, grow=36)
    fx.particle('blast', 2, 10, 5, (128, 128, 128), None, grow=80, fade=True)
    fx.particle('shock', 2, 9, 2, (128, 80, 30), 160, grow=110, fade=True)
    fx.particle('cinder', 16, 14, 3, (128, 100, 50), (60, 120), speed=60, lift=40, gravity=7, spread=100, fade=True)
    fx.particle('smoke', 8, 14, 4, (50, 28, 16), (200, 300), grow=16, lift=10, spread=140, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(3, 'wind'); fx.when(6, 'wind'); fx.when(charge, 'fire')
    fx.when(smite, 'smite')
    for k in range(5):
        fx.when(charge + 1 + 2 * k, 'send')
    fx.br(fx.NOW, '>', charge - 3, 'main_end'); fx.emit('mote', muzzle, 2)
    fx.label('main_end'); fx.end(charge + life + 1)
    fx.label('draw')
    fx.br(fx.NOW, '<', smite, 'noop'); fx.br(fx.NOW, '>', smite + 5, 'noop')
    fx.lin(fx.T, fx.NOW, -14, 14 * (smite + 6)); fx.lin(fx.T2, fx.T, 6, 0, 10); fx.vset(wash, fx.T, fx.T2, 0)
    fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    muzzle_at(fx, muzzle, 6, 70); fx.emit('lamp', muzzle); fx.emit('coil'); fx.sound(-55); fx.ret()
    fx.label('wind'); fx.emit('coil', muzzle); fx.sound(34); fx.ret()
    fx.label('fire'); fx.sound(13); fx.call('ray'); fx.ret()
    fx.label('send'); fx.aim(); fx.vcopy(fx.AT, muzzle); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('hoop'); fx.ret()
    fx.label('smite')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 14, 380, 10)
    fx.emit('blast', fx.TCHEST); fx.emit('shock'); fx.emit('cinder', times=14); fx.emit('smoke', times=5); fx.ret()
    ray(fx, 'ray', muzzle, life, 210, 0, edge, tint, jitter=40, tip=1)
    fx.travel('hoop', 5, 4, 'hoop_render', 'noop')
    fx.label('hoop_render'); fx.sprite(POS, edge, 240, 600, cell=2); fx.ret()
    return fx


# ----------------------------------------------------------------- ExVeemon
def ex_laser():
    """The X on ExVeemon's chest lights up and swells as sparks pour into it, then tears loose and flies at the target
    as a burning X that grows on the way and leaves its shape hanging behind it; it stamps the target with a blaze."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(AMBER)
    fx.paint(0, xcross(2.0)); fx.paint(1, xcross(3.6)); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 80, 20)
    chest = fx.vec()
    charge, flight = 8, 5
    gather(fx, 'mote', 12, 3, (128, 110, 60), 90, 560, 6)
    fx.particle('ghost', 8, 6, 0, (128, 100, 50), None, fade=True)
    fx.particle('brand', 2, 10, 1, (128, 128, 128), None, grow=70, fade=True)
    fx.particle('flare', 1, 8, 2, (128, 110, 60), None, grow=60, fade=True)
    fx.particle('spark', 16, 11, 3, (128, 120, 70), (80, 150), grow=-8, speed=80, lift=20, gravity=6, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose')
    fx.br(fx.NOW, '>', charge - 3, 'main_end'); fx.emit('mote', chest, 2)
    fx.label('main_end'); fx.end(charge + 1)
    fx.label('begin'); muzzle_at(fx, chest, 6, 30); fx.vcopy(fx.AT, chest); fx.call('crest'); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, chest); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('bolt'); fx.ret()
    crest = fx.pool('crest', 1)
    fx.begin('crest', crest, 'crest_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('crest_tick'); fx.life(charge); fx.ret()
    fx.label('crest_render')
    fx.lin(fx.T3, FRAME, 34, 50); fx.lin(fx.T2, fx.T3, 3, 0, 2)
    fx.sprite(POS, soft, fx.T2, cell=2); fx.sprite(POS, tint, fx.T3, cell=0); fx.ret()
    fx.travel('bolt', 1, flight, 'bolt_render', 'bolt_arrive', every='bolt_trail')
    fx.label('bolt_trail'); fx.lin(fx.SZ, FRAME, 50, 320); fx.emit('ghost', POS); fx.ret()
    fx.label('bolt_render')
    fx.lin(fx.T3, FRAME, 50, 320); fx.lin(fx.T2, fx.T3, 3, 0, 2)
    fx.sprite(POS, soft, fx.T2, cell=2); fx.sprite(POS, tint, fx.T3, cell=1); fx.ret()
    fx.label('bolt_arrive')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 560)
    fx.emit('brand', fx.TCHEST); fx.emit('flare'); fx.emit('spark', times=14); fx.ret()
    return fx


# ----------------------------------------------------------------- Halsemon
def tempest_wing():
    """Wind whips round Halsemon, then drills across to the target as a whirlwind lying on its side: hoops of wind
    open behind its head and two streaks coil round its path. It blows apart on the target."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(GALE)
    fx.paint(0, gust(3)); fx.paint(1, gust(9)); fx.paint(2, glow(15, 1.2)); fx.paint(3, crescent(13, 12.5, 3.5, 0))
    fx.paint(4, crescent(13, 12.5, 3.5, np.pi)); fx.paint(5, puff(33)); fx.paint(6, star(4, 2, 9, 6))
    tint, soft = fx.colour(128, 128, 128), fx.colour(40, 110, 90)
    side, step = fx.vec(), fx.vec()
    spin, run = 7, 7
    fx.particle('hoop', 10, 7, 0, (100, 128, 120), None, grow=36, fade=True, sy=30)
    fx.particle('wisp', 18, 6, 3, (128, 128, 128), (170, 250), grow=-14, spin=40)
    fx.particle('burst', 2, 9, 1, (128, 128, 128), None, grow=90, fade=True)
    fx.particle('blow', 10, 12, 5, (50, 90, 80), (180, 260), grow=14, speed=50, spread=100, fade=True)
    fx.particle('fleck', 12, 11, 6, (110, 128, 120), (70, 130), grow=-7, speed=90, lift=20, gravity=4, spread=80)
    fx.label('main'); fx.when(0, 'begin'); fx.when(spin, 'loose')
    fx.br(fx.NOW, '>=', spin, 'main_end')
    fx.rnd(fx.T3, 0, 4095); fx.lin(fx.T2, fx.NOW, -30, 330); fx.circle(fx.AT, fx.T3, fx.T2, 0)
    fx.vadd(fx.AT, fx.CHEST); fx.call('wisp', 2)
    fx.label('main_end'); fx.end(spin + 1)
    fx.label('begin'); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.sound(13); fx.aim(); across(fx, side, 120)
    fx.vcopy(step, fx.TCHEST); fx.vsub(step, fx.CHEST); fx.vdiv(step, run)
    fx.vcopy(fx.AT, fx.CHEST); fx.call('drill'); fx.ret()
    drill = fx.pool('drill', 1)
    fx.begin('drill', drill, 'drill_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('drill_tick')
    fx.br(FRAME, '>=', run, 'drill_land')
    fx.vadd(POS, step)
    fx.lin(fx.SZ, FRAME, 34, 190); fx.emit('hoop', POS)
    for phase in (0, 2048):
        helix(fx, fx.TV2, side, 700, phase, 130); fx.emit('wisp', fx.TV2)
    fx.ret()
    fx.label('drill_land')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 440)
    fx.emit('burst', fx.TCHEST); fx.emit('blow', times=8); fx.emit('fleck', times=10)
    fx.set(FRAME, -1); fx.ret()
    fx.label('drill_render')
    fx.lin(fx.T3, FRAME, 70); fx.sprite(POS, soft, 440, cell=2)
    fx.sprite(POS, tint, 330, cell=3, rot=fx.T3); fx.sprite(POS, tint, 330, cell=4, rot=fx.T3); fx.ret()
    return fx


# ----------------------------------------------------------------- Lighdramon
def lightning_blast():
    """Sparks snap round Lighdramon's jaws, then a jagged bolt stands between them and the target, changing shape
    every instant and throwing forks off its length, while arcs crawl over whoever it holds."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(BOLT)
    fx.paint(0, zig(1)); fx.paint(1, zig(2)); fx.paint(2, zig(3)); fx.paint(3, glow(15, 1.2)); fx.paint(4, arc(5))
    fx.paint(5, arc(8)); fx.paint(6, star(4, 2, 9, 6))
    tint, edge = fx.colour(128, 128, 128), fx.colour(50, 80, 128)
    mouth = fx.vec()
    charge, life = 6, 10
    fx.particle('crackle', 8, 3, 4, (128, 128, 128), (180, 280), spread=280)
    fx.particle('crackle2', 8, 3, 5, (128, 128, 128), (180, 280), spread=280)
    fx.particle('flash', 2, 7, 3, (110, 120, 128), None, grow=50, fade=True)
    fx.particle('spark', 16, 10, 6, (128, 128, 128), (70, 130), grow=-7, speed=80, lift=20, gravity=7, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'fire'); fx.when(charge + 1, 'smite')
    fx.br(fx.NOW, '>=', charge, 'main_bolt'); fx.emit('crackle', mouth); fx.emit('crackle2'); fx.jmp('main_end')
    fx.label('main_bolt'); fx.br(fx.NOW, '>', charge + life, 'main_end')
    fx.aim(); fx.emit('crackle', fx.TCHEST); along(fx, fx.TV2, mouth); fx.emit('crackle2', fx.TV2)
    fx.label('main_end'); fx.end(charge + life + 4)
    fx.label('begin'); muzzle_at(fx, mouth, 8, 30); fx.sound(-55); fx.ret()
    fx.label('fire'); fx.sound(16); fx.call('bolt'); fx.ret()
    fx.label('smite')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 300, 10)
    fx.emit('flash', fx.TCHEST); fx.emit('spark', times=12); fx.ret()
    bolt = fx.pool('bolt', 1)
    fx.begin('bolt', bolt, 'bolt_render', inherit=False); fx.vcopy(POS, mouth); fx.ret()
    fx.label('bolt_tick'); fx.life(life); fx.aim(); fx.ret()
    fx.label('bolt_render')
    fx.set(fx.T3, FRAME); fx.mod(fx.T3, 2); fx.mul(fx.T3, 60); fx.add(fx.T3, 150)
    fx.br(FRAME, '<', life - 3, 'bolt_draw'); fx.lin(fx.T3, FRAME, -40, 40 * life + 20)
    fx.label('bolt_draw')
    fx.lin(fx.T, fx.T3, 1, 0, 2); fx.lin(fx.T2, fx.T3, 2)
    fx.sprite(mouth, edge, fx.T2, cell=3); fx.sprite(fx.TCHEST, edge, fx.T2, cell=3)
    fx.set(fx.F2, FRAME); fx.mod(fx.F2, 3)
    fx.br(fx.F2, '==', 1, 'bolt_b'); fx.br(fx.F2, '==', 2, 'bolt_c')
    band(fx, mouth, fx.TCHEST, fx.T3, edge, 0); band(fx, mouth, fx.TCHEST, fx.T, tint, 1); fx.ret()
    fx.label('bolt_b')
    band(fx, mouth, fx.TCHEST, fx.T3, edge, 1); band(fx, mouth, fx.TCHEST, fx.T, tint, 2); fx.ret()
    fx.label('bolt_c')
    band(fx, mouth, fx.TCHEST, fx.T3, edge, 2); band(fx, mouth, fx.TCHEST, fx.T, tint, 0); fx.ret()
    return fx


# ----------------------------------------------------------------- Veedramon
def v_nova_blast():
    """Blue light gathers in Veedramon's jaws and it breathes a white-blue ray; V-shaped arrowheads of light race
    down the ray one after another, each larger than the last, and strike the target as a great V that bursts."""
    fx = Fx(delay=16, cast_sound=2)
    fx.palette(VBREATH)
    fx.paint(0, breathbar(5)); fx.paint(1, breathbar(15)); fx.paint(2, vblade()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, ring(13, 2.0))
    tint, edge = fx.colour(128, 128, 128), fx.colour(40, 90, 128)
    mouth = fx.vec()
    charge, life, steps = 4, 13, 5
    fx.particle('mote', 12, 5, 4, (110, 128, 128), (80, 130), grow=-12, spread=140)
    fx.particle('swell', 1, charge + 1, 3, (90, 120, 128), 60, grow=30)
    fx.particle('arrow', 8, 6, 2, (128, 128, 128), None, grow=30, fade=True)
    fx.particle('mark', 2, 11, 2, (128, 128, 128), None, grow=55, fade=True)
    fx.particle('burst', 2, 9, 3, (100, 120, 128), None, grow=70, fade=True)
    fx.particle('wave', 2, 8, 5, (70, 110, 128), 150, grow=90, fade=True)
    fx.particle('spark', 14, 11, 4, (128, 128, 128), (80, 140), grow=-7, speed=80, lift=25, gravity=6, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'fire'); fx.when(charge + 3, 'smite')
    fx.br(fx.NOW, '>=', charge, 'main_ray'); fx.emit('mote', mouth, 2); fx.jmp('main_end')
    fx.label('main_ray'); fx.br(fx.NOW, '>', charge + life - 3, 'main_end')
    fx.lin(fx.T, fx.NOW, 1, -charge); fx.mod(fx.T, steps); fx.add(fx.T, 1)
    fx.vcopy(fx.TV2, fx.TCHEST); fx.vsub(fx.TV2, mouth); fx.vmul(fx.TV2, fx.T); fx.vdiv(fx.TV2, steps)
    fx.vadd(fx.TV2, mouth)
    fx.lin(fx.SZ, fx.T, 70, 150); fx.emit('arrow', fx.TV2)
    fx.label('main_end'); fx.end(charge + life + 1)
    fx.label('begin')                 # the snout once the head has come down: half the body's radius ahead
    muzzle_at(fx, mouth, 8, 0); fx.vsub(mouth, fx.SRC); fx.lin(fx.T3, at(mouth, 1), 1, 0)
    fx.set(at(mouth, 1), 0); fx.vdiv(mouth, 2); fx.set(at(mouth, 1), fx.T3); fx.vadd(mouth, fx.SRC)
    fx.emit('swell', mouth); fx.sound(-55); fx.ret()
    fx.label('fire'); fx.sound(13); fx.call('ray'); fx.ret()
    fx.label('smite')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 420)
    fx.emit('mark', fx.TCHEST); fx.emit('burst'); fx.emit('wave'); fx.emit('spark', times=14); fx.ret()
    ray(fx, 'ray', mouth, life, 230, 0, edge, tint, jitter=40, alt=1, tip=3)
    return fx


# ----------------------------------------------------------------- MegaKabuterimon
def horn_buster():
    """Arcs leap to the tip of MegaKabuterimon's horn and feed a ball of lightning that swells there; it is flung in
    a straight line, dragging arcs, and bursts on whoever it meets, leaving current crawling over them. A target
    that moves away is missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(VOLT)
    fx.paint(0, orb(7)); fx.paint(1, orb(17)); fx.paint(2, arc(3)); fx.paint(3, arc(6)); fx.paint(4, glow(15, 1.2))
    fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.0))
    tint, soft = fx.colour(128, 128, 128), fx.colour(90, 50, 128)
    horn = fx.vec()
    charge = 10
    fx.particle('feed', 8, 3, 2, (128, 128, 110), (240, 360), spread=320)
    fx.particle('feed2', 8, 3, 3, (128, 128, 110), (240, 360), spread=320)
    fx.particle('swell', 1, charge + 1, 0, (128, 128, 128), 50, grow=27)
    fx.particle('tail', 10, 4, 2, (128, 120, 128), (220, 320), spread=120)
    fx.particle('burst', 2, 9, 1, (128, 128, 128), None, grow=75, fade=True)
    fx.particle('shock', 2, 8, 6, (110, 70, 128), 150, grow=100, fade=True)
    fx.particle('jolt', 8, 4, 3, (128, 128, 110), (260, 360), spread=300)
    fx.particle('spark', 14, 11, 5, (128, 128, 90), (70, 130), grow=-7, speed=80, lift=30, gravity=7, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose')
    fx.br(fx.NOW, '>=', charge, 'main_end'); fx.emit('feed', horn); fx.emit('feed2')
    fx.label('main_end'); fx.end(charge + 1)
    fx.label('begin'); muzzle_at(fx, horn, 11, 30); fx.emit('swell', horn); fx.sound(-55); fx.ret()
    fx.label('loose')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, horn); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('ball'); fx.ret()
    fx.shot('ball', 1, 85, 24, 'ball_render', 'ball_arrive', miss='ball_miss', every='ball_trail')
    fx.label('ball_trail'); fx.emit('tail', POS); fx.ret()
    fx.label('ball_miss'); fx.emit('spark', POS, 6); fx.ret()
    fx.label('ball_render')
    fx.sprite(POS, soft, 480, cell=4); flicker(fx, POS, tint, 340, (0, 1), every=1); fx.ret()
    fx.label('ball_arrive')
    fx.sound(7); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 300, 10)
    fx.emit('burst', POS); fx.emit('shock'); fx.emit('spark', times=10); fx.call('zap'); fx.ret()
    zap = fx.pool('zap', 1)
    fx.begin('zap', zap, 'noop', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('zap_tick'); fx.life(8); fx.emit('jolt', POS); fx.ret()
    return fx


# ----------------------------------------------------------------- MagnaAngemon
def gate_of_destiny():
    """A spark draws a golden round door in the air behind the target; the door turns, opens on a white light, and
    lights torn from the target stream into it. The target is hit as the light flares, and the gate closes."""
    fx = Fx(delay=8, cast_sound=45, draw=True)
    fx.palette(GOLD)
    fx.paint(0, gate()); fx.paint(1, glow(15, 1.2)); fx.paint(2, star(4, 2, 9, 6)); fx.paint(3, ring(13, 1.4))
    fx.paint(4, star(4, 2.5, 13, 10))
    tint, gold, wash = fx.colour(128, 128, 128), fx.colour(128, 104, 50), fx.vec()
    door = fx.vec()
    drawn, pull, shut = 8, 17, 23
    fx.particle('flare', 1, 9, 4, (128, 128, 128), None, grow=70, fade=True, spin=8)
    fx.particle('halo', 2, 9, 3, (128, 104, 50), 160, grow=90, fade=True)
    fx.particle('glint', 14, 12, 2, (128, 128, 100), (80, 150), grow=-7, speed=60, lift=30, gravity=4, spread=200)
    fx.label('main'); fx.when(0, 'begin'); fx.when(pull, 'smite')
    fx.br(fx.NOW, '<', drawn, 'main_end'); fx.br(fx.NOW, '>=', pull, 'main_end')
    fx.aim(); fx.vcopy(fx.AT, fx.TCHEST); fx.scatter(fx.AT, 320); fx.vcopy(fx.DEST, door); fx.call('soul')
    fx.label('main_end'); fx.end(pull + 1)
    fx.label('draw')
    fx.br(fx.NOW, '<', pull, 'noop'); fx.br(fx.NOW, '>', pull + 5, 'noop')
    fx.lin(fx.T, fx.NOW, -12, 12 * (pull + 6)); fx.lin(fx.T2, fx.T, 8, 0, 10); fx.lin(fx.T3, fx.T, 4, 0, 10)
    fx.vset(wash, fx.T, fx.T2, fx.T3); fx.overlay(wash, blend='add'); fx.ret()
    fx.label('begin')
    fx.vcopy(fx.TV, fx.TGT); fx.vsub(fx.TV, fx.SRC); fx.set(at(fx.TV, 1), 0)
    fx.vlen(fx.T, fx.TV); fx.br(fx.T, '>', 0, 'begin_ok'); fx.set(fx.T, 1)
    fx.label('begin_ok')
    fx.vmul(fx.TV, 220); fx.vdiv(fx.TV, fx.T)
    fx.vcopy(door, fx.TCHEST); fx.vadd(door, fx.TV); fx.sub_(at(door, 1), 200)
    fx.vcopy(fx.AT, door); fx.call('gate'); fx.sound(-55); fx.ret()
    fx.label('smite')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 320, 10)
    fx.emit('flare', fx.TCHEST); fx.emit('halo'); fx.emit('glint', times=8); fx.ret()
    fx.travel('soul', 10, 5, 'soul_render', 'noop')
    fx.label('soul_render'); fx.lin(fx.T3, FRAME, -16, 170); fx.sprite(POS, tint, fx.T3, cell=2); fx.ret()
    ring_ = fx.pool('gate', 1)
    fx.begin('gate', ring_, 'gate_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('gate_tick')
    fx.life(shut + 4); fx.after(drawn, 'gate_open'); fx.after(shut, 'gate_shut'); fx.ret()
    fx.label('gate_open'); fx.sound(15); fx.ret()
    fx.label('gate_shut'); fx.sound(20); fx.emit('glint', POS, 6); fx.ret()
    fx.label('gate_render')
    fx.lin(fx.T3, FRAME, 84, 80); fx.br(FRAME, '<', drawn, 'gate_draw')
    fx.set(fx.T3, 760); fx.br(FRAME, '<=', shut, 'gate_draw')
    fx.lin(fx.T3, FRAME, -180, 760 + 180 * shut)
    fx.label('gate_draw')
    fx.lin(fx.T2, FRAME, 7); fx.lin(fx.F1, fx.T3, 13, 0, 10)
    fx.sprite(POS, gold, fx.F1, cell=1); fx.sprite(POS, tint, fx.T3, cell=0, rot=fx.T2)
    fx.br(FRAME, '>=', drawn, 'gate_light')
    fx.lin(fx.T, FRAME, 4096 // drawn); fx.lin(fx.F1, fx.T3, 42, 0, 100)   # the spark that draws the rim
    fx.sin(at(fx.TV, 0), fx.T, fx.F1); fx.cos(at(fx.TV, 1), fx.T, fx.F1); fx.set(at(fx.TV, 2), 0)
    fx.vadd(fx.TV, POS); fx.sprite(fx.TV, tint, 260, cell=4); fx.ret()
    fx.label('gate_light')
    fx.br(FRAME, '>', shut, 'noop')
    fx.set(fx.F1, FRAME); fx.mod(fx.F1, 2); fx.mul(fx.F1, 60); fx.add(fx.F1, 430)
    fx.sprite(POS, tint, fx.F1, cell=1)
    fx.lin(fx.T2, FRAME, 31); fx.sprite(POS, tint, 520, cell=4, rot=fx.T2); fx.ret()
    return fx


# ----------------------------------------------------------------- Lillymon
def flower_cannon():
    """A pink flower opens between Lillymon's hands, turning, and fires a green beam from its heart; petals whirl off
    the beam's length and are thrown up where it bursts on the target."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(LEAF); fx.palette(PINK)
    fx.paint(0, flower()); fx.paint(1, bar(23)); fx.paint(2, glow(15, 1.2)); fx.paint(3, petal())
    fx.paint(4, petal(True)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.0))
    tint, green = fx.colour(128, 128, 128), fx.colour(50, 128, 40)
    hands = fx.vec()
    charge, life = 9, 9
    gather(fx, 'mote', 12, 5, (110, 128, 70), 90, 520, 6)
    fx.particle('drift', 10, 10, 3, (128, 128, 128), (120, 180), flat=((-12, 12), (-16, 6), (-12, 12)), spread=170,
                spin=14, clut=1, blend=None)
    fx.particle('drift2', 10, 10, 4, (128, 128, 128), (120, 180), flat=((-12, 12), (-16, 6), (-12, 12)), spread=170,
                spin=-14, clut=1, blend=None)
    fx.particle('pop', 2, 9, 2, (90, 128, 70), None, grow=70, fade=True)
    fx.particle('wave', 2, 8, 6, (70, 128, 50), 150, grow=90, fade=True)
    fx.particle('toss', 12, 14, 3, (128, 128, 128), (130, 190), speed=60, lift=55, gravity=7, spread=90, spin=18,
                clut=1, blend=None)
    fx.particle('dust', 10, 10, 5, (110, 128, 70), (70, 120), grow=-6, speed=50, lift=20, spread=100)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'fire'); fx.when(charge + 2, 'smite')
    fx.br(fx.NOW, '<', charge, 'main_gather'); fx.br(fx.NOW, '>', charge + life - 2, 'main_end')
    along(fx, fx.TV2, hands); fx.emit('drift', fx.TV2); fx.emit('drift2'); fx.jmp('main_end')
    fx.label('main_gather'); fx.br(fx.NOW, '>', charge - 3, 'main_end'); fx.emit('mote', hands, 2)
    fx.label('main_end'); fx.end(charge + life + 1)
    fx.label('begin'); muzzle_at(fx, hands, 6, 60); fx.vcopy(fx.AT, hands); fx.call('bloom'); fx.sound(-55); fx.ret()
    fx.label('fire'); fx.sound(13); fx.call('ray'); fx.ret()
    fx.label('smite')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 300, 10)
    fx.emit('pop', fx.TCHEST); fx.emit('wave'); fx.emit('toss', times=12); fx.emit('dust', times=8); fx.ret()
    bloom = fx.pool('bloom', 1)
    fx.begin('bloom', bloom, 'bloom_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('bloom_tick'); fx.life(charge + life + 2); fx.ret()
    fx.label('bloom_render')
    fx.lin(fx.T3, FRAME, 40, 30); fx.br(FRAME, '<', charge, 'bloom_draw')
    fx.set(fx.T3, 390); fx.br(FRAME, '<', charge + life - 1, 'bloom_draw')
    fx.lin(fx.T3, FRAME, -110, 110 * (charge + life + 2) + 30)
    fx.label('bloom_draw')
    fx.lin(fx.T2, FRAME, 6); fx.lin(fx.F1, fx.T3, 13, 0, 10)
    fx.sprite(POS, green, fx.F1, cell=2); fx.sprite(POS, tint, fx.T3, cell=0, clut=1, blend=None, rot=fx.T2); fx.ret()
    ray(fx, 'ray', hands, life, 150, 1, green, tint, tip=2)
    return fx


# ----------------------------------------------------------------- MetalSeadramon
def river_of_power():
    """Light swells at the cannon on MetalSeadramon's snout as hoops close on it; then a river of blue power roars
    out, spraying drops off its whole length, and where it strikes a column of water stands up and rains back down."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(DEEP)
    fx.paint(0, torrent(4)); fx.paint(1, torrent(14)); fx.paint(2, glow(15, 1.2)); fx.paint(3, drop())
    fx.paint(4, column(19)); fx.paint(5, puff(29)); fx.paint(6, ring(13, 2.0))
    tint, edge = fx.colour(128, 128, 128), fx.colour(20, 60, 128)
    nose = fx.vec()
    charge, life = 9, 16
    smite = charge + 3
    fx.particle('swell', 1, charge, 2, (60, 110, 128), 60, grow=44)
    fx.particle('coil', 2, 7, 6, (60, 110, 128), 540, grow=-66)
    fx.particle('spray', 20, 10, 3, (110, 128, 128), (80, 130), flat=((-14, 14), (-36, -12), (-14, 14)), gravity=8,
                spread=120)
    fx.particle('foam', 8, 12, 5, (60, 80, 100), (200, 300), grow=18, speed=30, lift=10, spread=160, fade=True)
    fx.particle('ripple', 2, 10, 6, (60, 110, 128), 200, grow=100, fade=True)
    fx.particle('rain', 14, 13, 3, (110, 128, 128), (90, 150), speed=50, lift=95, gravity=14, spread=160)
    fx.label('main'); fx.when(0, 'begin'); fx.when(4, 'wind'); fx.when(charge, 'fire'); fx.when(smite, 'smite')
    fx.br(fx.NOW, '<', charge, 'main_end'); fx.br(fx.NOW, '>', charge + life - 3, 'main_end')
    along(fx, fx.TV2, nose); fx.emit('spray', fx.TV2, 2)
    fx.label('main_end'); fx.end(charge + life + 1)
    fx.label('begin'); muzzle_at(fx, nose, 9, 60); fx.emit('swell', nose); fx.emit('coil'); fx.sound(-55); fx.ret()
    fx.label('wind'); fx.emit('coil', nose); fx.ret()
    fx.label('fire'); fx.sound(13); fx.call('ray'); fx.ret()
    fx.label('smite')
    fx.sound(7); fx.aim(); fx.hit()
    fx.vcopy(fx.AT, fx.TGT); fx.call('geyser'); fx.emit('ripple', fx.TCHEST)
    fx.emit('foam', times=6); fx.emit('rain', times=12); fx.ret()
    ray(fx, 'ray', nose, life, 250, 0, edge, tint, jitter=30, alt=1, tip=2)
    geyser = fx.pool('geyser', 1)
    fx.begin('geyser', geyser, 'geyser_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('geyser_tick'); fx.life(12); fx.ret()
    fx.label('geyser_render')
    fx.lin(fx.T3, FRAME, 220, 160); fx.br(FRAME, '<', 4, 'geyser_draw')
    fx.lin(fx.T3, FRAME, -90, 1040 + 360)
    fx.label('geyser_draw')
    fx.lin(fx.T2, FRAME, -22, 480)
    fx.pillar(POS, fx.T2, fx.T3, edge, cell=4)
    fx.lin(fx.T2, fx.T2, 6, 0, 10); fx.pillar(POS, fx.T2, fx.T3, tint, cell=4); fx.ret()
    return fx


# ----------------------------------------------------------------- VenomMyotismon
def venom_infusion():
    """A maw ringed with teeth opens on VenomMyotismon's belly and swallows the light round it; a crimson blast with a
    black heart pours out of it, and where it lands a blot of darkness spreads and red bubbles rise from it."""
    fx = Fx(delay=8, cast_sound=19)
    fx.palette(BLOOD); fx.palette(ASH)
    fx.paint(0, maw()); fx.paint(1, bar(37)); fx.paint(2, glow(15, 1.2)); fx.paint(3, bead()); fx.paint(4, puff(47))
    fx.paint(5, ring(13, 2.0)); fx.paint(6, thin_bar(8, 3))
    tint, red, dark = fx.colour(128, 128, 128), fx.colour(128, 24, 20), fx.colour(120, 120, 120)
    chest = fx.vec()
    charge, life = 9, 13
    smite = charge + 2
    gather(fx, 'mote', 12, 3, (128, 50, 40), 80, 600, 6)
    fx.particle('blot', 2, 11, 2, (128, 128, 128), None, grow=60, fade=True, clut=1, blend='sub')
    fx.particle('halo', 2, 9, 5, (128, 30, 24), 160, grow=95, fade=True)
    fx.particle('bubble', 14, 14, 3, (128, 60, 50), (70, 140), flat=((-10, 10), (-34, -14), (-10, 10)), spread=280)
    fx.particle('smoke', 8, 14, 4, (70, 70, 70), (200, 280), grow=14, lift=12, spread=140, fade=True, clut=1,
                blend='sub')
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'fire'); fx.when(smite, 'smite')
    fx.br(fx.NOW, '>', charge - 3, 'main_seethe'); fx.emit('mote', chest, 2); fx.jmp('main_end')
    fx.label('main_seethe')
    fx.br(fx.NOW, '<', smite, 'main_end'); fx.br(fx.NOW, '>', smite + 8, 'main_end')
    fx.aim(); fx.emit('bubble', fx.TCHEST)
    fx.label('main_end'); fx.end(charge + life + 1)
    fx.label('begin'); muzzle_at(fx, chest, 5, 40); fx.vcopy(fx.AT, chest); fx.call('jaws'); fx.sound(-55); fx.ret()
    fx.label('fire'); fx.sound(13); fx.call('ray'); fx.ret()
    fx.label('smite')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 12, 340, 10)
    fx.emit('blot', fx.TCHEST); fx.emit('halo'); fx.emit('bubble', times=5); fx.emit('smoke', times=5); fx.ret()
    jaws = fx.pool('jaws', 1)
    fx.begin('jaws', jaws, 'jaws_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('jaws_tick'); fx.life(charge + life); fx.ret()
    fx.label('jaws_render')
    fx.lin(fx.T3, FRAME, 40, 50); fx.br(FRAME, '<', charge, 'jaws_draw')
    fx.set(fx.T3, FRAME); fx.mod(fx.T3, 2); fx.mul(fx.T3, 40); fx.add(fx.T3, 410)
    fx.br(FRAME, '<', charge + life - 3, 'jaws_draw')
    fx.lin(fx.T3, FRAME, -120, 120 * (charge + life) + 40)
    fx.label('jaws_draw')
    fx.lin(fx.T2, fx.T3, 8, 0, 10); fx.sprite(POS, dark, fx.T2, cell=2, clut=1, blend='sub')
    fx.lin(fx.T2, FRAME, 5); fx.sprite(POS, tint, fx.T3, cell=0, rot=fx.T2); fx.ret()
    ray(fx, 'ray', chest, life, 190, 1, red, dark, jitter=36, core_cell=6, core_clut=1, core_blend='sub')
    return fx


# ----------------------------------------------------------------- AeroVeedramon
def v_wing_blade():
    """A light kindles on each of AeroVeedramon's wingtips; the two sweep together before its chest into a V of light
    that is flung straight ahead, growing, its shape echoing behind it. It cuts whoever it meets; a target that
    moves away is missed."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(SKY)
    fx.paint(0, vblade()); fx.paint(1, glow(15, 1.2)); fx.paint(2, star(4, 2, 9, 6)); fx.paint(3, ring(13, 2.0))
    fx.paint(4, star(4, 1.5, 14, 14)); fx.paint(5, vee(1.6))
    tint, soft = fx.colour(128, 128, 128), fx.colour(40, 90, 128)
    side, heart = fx.vec(), fx.vec()
    charge = 7
    fx.particle('mote', 12, 5, 2, (110, 128, 128), (80, 120), grow=-12, spread=60)
    fx.particle('echo', 6, 5, 5, (90, 120, 128), None, fade=True)
    fx.particle('cut', 2, 9, 0, (128, 128, 128), None, grow=60, fade=True)
    fx.particle('flare', 1, 8, 1, (90, 120, 128), None, grow=50, fade=True)
    fx.particle('wave', 2, 8, 3, (70, 110, 128), 150, grow=90, fade=True)
    fx.particle('spark', 14, 11, 2, (128, 128, 128), (80, 140), grow=-7, speed=80, lift=25, gravity=6, spread=60)
    fx.label('main'); fx.when(0, 'begin'); fx.when(charge, 'loose'); fx.end(charge + 1)
    fx.label('begin')
    across(fx, side, 300); muzzle_at(fx, heart, 6, 50); fx.vcopy(fx.DEST, heart)
    fx.vcopy(fx.AT, fx.CHEST); fx.vadd(fx.AT, side); fx.sub_(at(fx.AT, 1), 220); fx.call('tip')
    fx.vcopy(fx.AT, fx.CHEST); fx.vsub(fx.AT, side); fx.sub_(at(fx.AT, 1), 220); fx.call('tip')
    fx.sound(-55); fx.ret()
    fx.travel('tip', 2, charge, 'tip_render', 'noop', every='tip_trail')
    fx.label('tip_trail'); fx.emit('mote', POS); fx.ret()
    fx.label('tip_render')
    fx.lin(fx.T2, FRAME, 25); fx.lin(fx.T3, FRAME, 24, 200)
    fx.sprite(POS, soft, 360, cell=1); fx.sprite(POS, tint, fx.T3, cell=4, rot=fx.T2); fx.ret()
    fx.label('loose')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, heart); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('blade'); fx.ret()
    fx.shot('blade', 1, 90, 24, 'blade_render', 'blade_arrive', miss='blade_miss', every='blade_trail')
    fx.label('blade_size')
    fx.lin(fx.T3, FRAME, 45, 320); fx.br(fx.T3, '<', 640, 'noop'); fx.set(fx.T3, 640); fx.ret()
    fx.label('blade_trail'); fx.call('blade_size'); fx.set(fx.SZ, fx.T3); fx.emit('echo', POS); fx.ret()
    fx.label('blade_miss'); fx.emit('spark', POS, 6); fx.ret()
    fx.label('blade_render')
    fx.call('blade_size'); fx.lin(fx.T2, fx.T3, 13, 0, 10)
    fx.sprite(POS, soft, fx.T2, cell=1); fx.sprite(POS, tint, fx.T3, cell=0); fx.ret()
    fx.label('blade_arrive')
    fx.sound(16); fx.set(fx.SZ, 600)
    fx.emit('cut', POS); fx.emit('flare'); fx.emit('wave'); fx.emit('spark', times=12); fx.ret()
    return fx


# ----------------------------------------------------------------- Magnadramon
def fire_tornado():
    """Two ropes of rose flame coil round each other from Magnadramon to the target; there they wind up into a
    spinning funnel of fire, wider towards the top, that throws embers at the sky."""
    fx = Fx(delay=8, cast_sound=2)
    fx.palette(ROSEFIRE)
    fx.paint(0, fireball(3)); fx.paint(1, fireball(11)); fx.paint(2, tongue()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, tongue(9))
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 50, 60)
    side, step = fx.vec(), fx.vec()
    run, spin = 8, 15
    fx.particle('coil', 10, 8, 0, (128, 110, 110), 280, grow=-22)
    fx.particle('coil2', 10, 8, 1, (128, 110, 110), 280, grow=-22)
    fx.particle('ember', 16, 12, 4, (128, 90, 70), (60, 110), flat=((-20, 20), (-70, -25), (-20, 20)), spread=220,
                fade=True)
    fx.particle('roar', 2, 9, 3, (128, 80, 70), None, grow=60, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.end(1)
    fx.label('begin')
    fx.sound(13); fx.aim(); across(fx, side, 130)
    fx.vcopy(step, fx.TCHEST); fx.vsub(step, fx.CHEST); fx.vdiv(step, run)
    fx.vcopy(fx.AT, fx.CHEST); fx.call('twist'); fx.ret()
    twist = fx.pool('twist', 1)
    fx.begin('twist', twist, 'twist_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('twist_tick')
    fx.br(FRAME, '>=', run, 'twist_land')
    fx.vadd(POS, step)
    helix(fx, fx.TV2, side, 560, 0, 140); fx.emit('coil', fx.TV2)
    helix(fx, fx.TV2, side, 560, 2048, 140); fx.emit('coil2', fx.TV2)
    fx.ret()
    fx.label('twist_land')
    fx.sound(7); fx.aim(); fx.hit(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 420)
    fx.emit('roar', fx.TCHEST); fx.vcopy(fx.AT, fx.TGT); fx.call('funnel')
    fx.set(FRAME, -1); fx.ret()
    fx.label('twist_render')
    fx.sprite(POS, soft, 440, cell=3); flicker(fx, POS, tint, 300, (0, 1), every=1); fx.ret()
    funnel = fx.pool('funnel', 1)
    fx.begin('funnel', funnel, 'funnel_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('funnel_tick'); fx.life(spin); fx.emit('ember', POS); fx.after(6, 'funnel_roar'); fx.ret()
    fx.label('funnel_roar'); fx.sound(3); fx.ret()
    fx.label('funnel_render')
    fx.set(fx.F1, 100); fx.br(FRAME, '>=', 3, 'funnel_full'); fx.lin(fx.F1, FRAME, 25, 25)
    fx.label('funnel_full'); fx.br(FRAME, '<=', spin - 4, 'funnel_draw'); fx.lin(fx.F1, FRAME, -25, 25 * spin)
    fx.label('funnel_draw')
    for k in range(8):
        fx.lin(fx.T, FRAME, 560, 600 * k); fx.circle(fx.TV, fx.T, 50 + 36 * k, 0); fx.vadd(fx.TV, POS)
        fx.sub_(at(fx.TV, 1), 50 + 105 * k)
        fx.lin(fx.T3, fx.F1, 220 + 34 * k, 0, 100)
        fx.sprite(fx.TV, tint, fx.T3, cell=2 if k % 2 else 5)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Salamon
def puppy_howling():
    """Salamon howls four times: each howl leaves its mouth as a ring that widens on its way to the target, notes
    tumbling out with it. The rings ring on over the target, which is hit as the second one arrives."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(HOWL)
    fx.paint(0, ring(12.5, 1.5)); fx.paint(1, wavy()); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, note())
    tint, soft = fx.colour(128, 128, 128), fx.colour(128, 96, 50)
    mouth = fx.vec()
    fx.particle('yap', 4, 5, 2, (128, 110, 70), 120, grow=40, fade=True)
    fx.particle('ringout', 6, 7, 1, (128, 128, 128), None, grow=70, fade=True)
    fx.particle('tune', 12, 14, 4, (128, 128, 128), (130, 180), flat=((-16, 16), (-30, -12), (-16, 16)), spread=120)
    fx.particle('daze', 10, 10, 3, (128, 128, 110), (80, 140), grow=-7, speed=60, lift=30, gravity=5, spread=80)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(4):
        fx.when(3 * k, 'howl')
    fx.when(9, 'smite'); fx.when(11, 'echo'); fx.when(13, 'echo'); fx.when(15, 'echo'); fx.end(16)
    fx.label('begin'); muzzle_at(fx, mouth, 8, 30); fx.ret()
    fx.label('howl')
    fx.sound(34); fx.aim(); fx.emit('yap', mouth); fx.emit('tune', times=2)
    fx.vcopy(fx.DEST, fx.TCHEST); fx.call('wave'); fx.ret()
    fx.travel('wave', 4, 6, 'wave_render', 'wave_arrive')
    fx.label('wave_render')
    fx.lin(fx.T3, FRAME, 75, 150); fx.lin(fx.T2, fx.T3, 17, 0, 10); fx.lin(fx.F1, fx.T3, 6, 0, 10)
    fx.sprite(POS, soft, fx.F1, fx.T3, cell=0)
    fx.set(fx.F2, FRAME); fx.mod(fx.F2, 2); fx.br(fx.F2, '==', 1, 'wave_other')
    fx.sprite(POS, tint, fx.T3, fx.T2, cell=0); fx.ret()
    fx.label('wave_other'); fx.sprite(POS, tint, fx.T3, fx.T2, cell=1); fx.ret()
    fx.label('wave_arrive'); fx.set(fx.SZ, 420); fx.emit('ringout', POS); fx.ret()
    fx.label('smite')
    fx.sound(7); fx.aim(); fx.hit(); fx.emit('daze', fx.TCHEST, 10); fx.ret()
    fx.label('echo')
    fx.aim(); fx.lin(fx.SZ, at(fx.TSIZE, 1), 1, 200); fx.emit('ringout', fx.TCHEST); fx.emit('tune', times=2); fx.ret()
    return fx


# ----------------------------------------------------------------- BlackGatomon
def cats_eyes():
    """The light dims and two yellow eyes open before BlackGatomon's face; they flash, and two violet ripples cross
    to the target, over which the same eyes open huge for a moment before it is left in a violet haze."""
    fx = Fx(delay=8, cast_sound=19, draw=True)
    fx.palette(VIOLET); fx.palette(EYE)
    fx.paint(0, cateyes()); fx.paint(1, ring(12.5, 1.8)); fx.paint(2, glow(15, 1.2)); fx.paint(3, wavy(6, 2.2))
    fx.paint(4, star(4, 2, 9, 6)); fx.paint(5, puff(57))
    tint, soft, dim = fx.colour(128, 128, 128), fx.colour(90, 30, 128), fx.colour(44, 44, 30)
    face, shade = fx.vec(), fx.vec()
    flash, land = 6, 11
    fx.particle('haze', 8, 13, 5, (60, 24, 90), (200, 280), grow=14, speed=20, lift=8, spread=140, fade=True)
    fx.particle('spark', 12, 11, 4, (128, 90, 128), (70, 130), grow=-7, speed=70, lift=25, gravity=5, spread=80)
    fx.particle('wave', 2, 8, 1, (110, 50, 128), 150, grow=90, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(flash, 'pulse'); fx.when(flash + 2, 'pulse'); fx.when(land, 'smite')
    fx.end(land + 1)
    fx.label('draw'); fx.br(fx.NOW, '>', land + 1, 'noop'); fx.overlay(dim, blend='sub'); fx.ret()
    fx.label('begin')
    muzzle_at(fx, face, 9, 30); fx.vcopy(fx.AT, face); fx.set(fx.SZ, 0); fx.call('stare')
    fx.sound(-55); fx.ret()
    fx.label('pulse')
    fx.sound(34); fx.aim(); fx.vcopy(fx.AT, face); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('ripple'); fx.ret()
    fx.travel('ripple', 2, 5, 'ripple_render', 'noop')
    fx.label('ripple_render')
    fx.lin(fx.T3, FRAME, 110, 170); fx.lin(fx.T2, fx.T3, 17, 0, 10)
    fx.sprite(POS, soft, fx.T3, fx.T2, cell=3); fx.lin(fx.T3, fx.T3, 7, 0, 10); fx.lin(fx.T2, fx.T2, 7, 0, 10)
    fx.sprite(POS, tint, fx.T3, fx.T2, cell=1); fx.ret()
    fx.label('smite')
    fx.sound(7); fx.aim(); fx.hit()
    fx.vcopy(fx.AT, fx.TGT); fx.lin(fx.T, at(fx.TSIZE, 1), 1, 260); fx.sub_(at(fx.AT, 1), fx.T)
    fx.set(fx.SZ, 1); fx.call('stare')
    fx.emit('wave', fx.TCHEST); fx.emit('haze', times=6); fx.emit('spark', times=10); fx.ret()
    # a pair of eyes: SZ 0 the small ones that open before the caster and flash, 1 the huge ones over the target
    stare = fx.pool('stare', 2, 1)
    big = iv(FREE)
    fx.begin('stare', stare, 'stare_render', inherit=False); fx.vcopy(POS, fx.AT); fx.set(big, fx.SZ); fx.ret()
    fx.label('stare_tick'); fx.br(big, '==', 1, 'stare_big'); fx.life(flash + 4); fx.ret()
    fx.label('stare_big'); fx.life(8); fx.ret()
    fx.label('stare_render')
    fx.br(big, '==', 1, 'stare_huge')
    fx.lin(fx.T3, FRAME, 26, 10); fx.set(fx.F1, 210); fx.br(FRAME, '<', 5, 'stare_small')
    fx.set(fx.T3, 130); fx.br(FRAME, '<', flash, 'stare_small')
    fx.lin(fx.F1, FRAME, 36, 210 - 36 * flash); fx.lin(fx.T3, fx.F1, 6, 0, 10)
    fx.label('stare_small')
    fx.lin(fx.T2, fx.F1, 3); fx.lin(fx.T, fx.F1, 2); fx.sprite(POS, soft, fx.T2, fx.T, cell=2)
    fx.lin(fx.T3, fx.T3, 2); fx.sprite(POS, tint, fx.T2, fx.T3, cell=0, clut=1, blend=None); fx.ret()
    fx.label('stare_huge')
    fx.lin(fx.T, FRAME, -14, 128); fx.vset(shade, fx.T, fx.T, fx.T)
    fx.lin(fx.F1, FRAME, 60, 760); fx.lin(fx.T3, fx.F1, 4, 0, 10)
    fx.sprite(POS, shade, fx.F1, fx.T3, cell=0, clut=1); fx.ret()
    return fx


EFFECTS = {123: recovery_power, 184: hawk_beam, 191: metal_wolf_claw, 192: positron_laser, 194: ex_laser,
           196: tempest_wing, 201: lightning_blast, 203: v_nova_blast, 205: horn_buster, 206: gate_of_destiny,
           209: flower_cannon, 211: river_of_power, 212: venom_infusion, 213: v_wing_blade, 215: fire_tornado,
           221: puppy_howling, 222: cats_eyes}
