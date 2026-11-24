"""The finishers that throw something, written and painted here, one per species (keyed by species id): a gear, stone
tablets, clay figures, a claw on a cable, shuriken, a club, a bomb, a syringe, swords, junk, an egg, a trident, muck
and two sickles. Each thing thrown is painted as itself and flies its own way."""
import math

import numpy as np

from tools.technique_effects.finishers import FIRE, GOLD, band, puff
from tools.technique_effects.kit import FRAME, FREE, POS, Fx, at, clip, crescent, fbm, glow, grid, iv, polar, ring, \
    segment, star

IRON = ['#08060c', '#2a2238', '#5c5078', '#a094c0', '#f0e8ff']
GLOOM = ['#000000', '#1c0830', '#5a1890', '#b050e0', '#f0c8ff']
SPARK = ['#000000', '#602000', '#e07010', '#ffd060', '#ffffff']
STONE = ['#2a2216', '#6a5a3c', '#a89466', '#dccb9c', '#fff6d8']
SUN = ['#000000', '#503000', '#c08818', '#ffe070', '#ffffff']
CLAY = ['#3a1808', '#8a4820', '#c47c40', '#eebc80', '#fff0d4']
DUST = ['#000000', '#3a2c1c', '#8a7050', '#d0b890', '#fff4e0']
STEEL = ['#0c1018', '#38445c', '#7c8cac', '#c8d8f0', '#ffffff']
LEAF = ['#000000', '#083410', '#289830', '#a0f060', '#ffffe0']
BONE = ['#30281c', '#80704c', '#c8b888', '#f4ecd0', '#ffffff']
BOMB = ['#06060a', '#1c1e28', '#484c60', '#9098b0', '#ffffff']
SMOKE = ['#000000', '#181818', '#484440', '#888078', '#c8c0b8']
SERUM = ['#141018', '#5a2480', '#a84cd0', '#e0bcf4', '#ffffff']
VENOM = ['#000000', '#1c0838', '#6a20a8', '#c060f0', '#f8d8ff']
MAGIC = ['#000000', '#48083c', '#c01890', '#ff70d0', '#ffe0f8']
JUNK = ['#1c1a14', '#544c38', '#8a8c70', '#c0c6ae', '#f2f2e2']
STINK = ['#000000', '#182808', '#587818', '#a8c838', '#f0ff90']
EGG = ['#5a4830', '#b09870', '#e8dcc0', '#fffaf0', '#ffffff']
YOLK = ['#000000', '#704000', '#f0a000', '#ffe060', '#ffffff']
SEASTEEL = ['#061018', '#184050', '#4890a0', '#a0e0e8', '#ffffff']
DEEP = ['#000000', '#04203c', '#1070a0', '#60d0e8', '#e8ffff']
MUCK = ['#0c0810', '#30203c', '#5c4274', '#9478b0', '#d8c8ec']
MANTIS = ['#000000', '#083818', '#20a040', '#a0ff80', '#ffffff']


# ----------------------------------------------------------------- paintings
def shade(mask, x, y, base=0.55, slope=0.3):
    """A solid shape lit from the upper left, with a dark edge left to the caller."""
    return mask * clip(base - slope * ((x - 16) + (y - 16)) / 22.0)


def gear(turn=0.0):
    """A cog: eight square teeth, a rim, a hub with a hole."""
    r, ang = polar()
    x, y = grid()
    edge = np.where(np.cos((ang + turn) * 8) > 0.1, 14.5, 11.0)
    body = (r < edge) & (r > 3.0)
    lum = shade(body, x, y, 0.6, 0.35)
    lum = np.where(body & (np.abs(r - 8.5) < 0.9), 0.12, lum)
    lum = np.where(body & (r > edge - 1.2), 0.14, lum)
    spokes = body & (r < 8) & (np.abs(np.sin((ang + turn) * 2)) < 0.25)
    return np.where(spokes, 0.9, lum)


def tablet(glyph=0):
    """A stone slab with an arched top and rows of carved signs."""
    x, y = grid()
    top = 3 + (1 - np.sqrt(clip(1 - ((x - 16) / 9.5) ** 2))) * 6
    body = (np.abs(x - 16) < 9.5) & (y > top) & (y < 30)
    lum = body * clip(0.62 - 0.2 * (x - 16) / 10 - 0.12 * (y - 16) / 14 + 0.25 * (fbm(51 + glyph) - 0.5))
    border = body & ((np.abs(x - 16) > 8) | (y > 28.3) | (y < top + 1.4))
    lum = np.where(border, 0.9, lum)
    r = np.random.default_rng(7 + glyph)
    carve = np.zeros_like(lum, dtype=bool)
    for row in (13, 18, 23):
        px = 9.5
        while px < 22:
            w = 1.5 + 2.5 * r.random()
            carve |= (np.abs(y - row) < 1.0) & (x > px) & (x < px + w)
            if r.random() < 0.5:
                carve |= (np.abs(x - px - w / 2) < 0.8) & (np.abs(y - row) < 2.2)
            px += w + 1.4
    eye = (np.abs(np.hypot(x - 16, (y - 8.5) * 1.5) - 2.6) < 0.8) | (np.hypot(x - 16, y - 8.5) < 0.9)
    return np.where(body & (carve | eye), 0.13, lum)


def dogu():
    """A clay figure: a round head with slit eyes, a wide body, stub arms and legs."""
    x, y = grid()
    parts = ((16, 8, 5.5, 5.5), (16, 19.5, 7.5, 8), (7, 16.5, 3.6, 4.4), (25, 16.5, 3.6, 4.4), (11.5, 28, 3.6, 3.4),
             (20.5, 28, 3.6, 3.4))
    d = np.min([np.hypot((x - cx) / rx, (y - cy) / ry) for cx, cy, rx, ry in parts], axis=0)
    body = d < 1
    lum = body * clip(0.6 - 0.22 * (x - 16) / 12 - 0.15 * (y - 16) / 14 + 0.2 * (fbm(61) - 0.5))
    lum = np.where(body & (d > 0.8), 0.2, lum)
    eyes = (np.abs(y - 8) < 0.9) & ((np.abs(x - 13.3) < 1.8) | (np.abs(x - 18.7) < 1.8))
    belt = (np.abs(y - 20) < 0.8) & (np.abs(x - 16) < 6.5) | (np.hypot(x - 16, y - 15) < 1.2)
    return np.where(body & (eyes | belt), 0.12, lum)


def shard_of(seed):
    """A broken piece: a crooked triangle."""
    x, y = grid()
    r = np.random.default_rng(seed)
    a = r.random() * 6.28
    d = np.max([(x - 16) * math.cos(a + k * 2.1 + 0.4 * r.random()) + (y - 16) * math.sin(a + k * 2.1) for k in
                range(3)], axis=0)
    return (d < 6) * clip(0.75 - 0.3 * (x - 16) / 8 + 0.2 * (y < 16))


def claw():
    """A metal hand, wrist on the left, three hooked fingers open to the right."""
    x, y = grid()
    wrist = (x > 1) & (x < 11) & (np.abs(y - 16) < 5.5)
    lum = wrist * clip(0.75 - 0.5 * np.abs(y - 16) / 5.5 + 0.2 * (np.abs(x - 6) < 0.8))
    for (y0, y1, y2, tone) in ((12, 4.5, 9.5, 0.95), (20, 27.5, 22.5, 0.6)):
        finger = np.maximum(segment(9, y0, 21, y1, 3.4), segment(21, y1, 31, y2, 2.8))
        lum = np.where(finger > 0.35, tone, np.where((finger > 0.08) & (lum == 0), 0.16, lum))
    thumb = segment(10, 16, 30.5, 16, 2.8)
    lum = np.where(thumb > 0.35, 0.8, np.where((thumb > 0.08) & (lum == 0), 0.16, lum))
    return lum


def cable():
    """A run of chain links along the cell's middle line."""
    x, y = grid()
    link = np.abs(np.hypot(((x % 8) - 4) / 3.6, (y - 16) / 3.0) - 0.8) < 0.3
    core = (np.abs(y - 16) < 0.9) * 0.45
    return np.where(link, 0.85, core)


def shuriken(turn=0.0):
    """A four-pointed throwing star with a hole, each blade ground to two faces."""
    r, ang = polar()
    a = ang + turn
    edge = 3.6 + 11.4 * np.abs(np.cos(a * 2)) ** 2.6
    body = (r < edge) & (r > 1.9)
    face = np.where(np.sin(a * 4) > 0, 0.88, 0.45)
    lum = body * face
    return np.where(body & ((r > edge - 1.0) | (r < 3.0)), 0.16, lum)


def leaf():
    x, y = grid()
    u, v = (x - 16) * 0.7 + (y - 16) * 0.7, -(x - 16) * 0.7 + (y - 16) * 0.7
    body = clip(1.2 - ((u / 12.0) ** 2 + (v / 4.5) ** 2))
    return clip(body * (0.55 + 0.45 * clip(1 - np.abs(v) / 1.2)))


def bone_club():
    """A club of bone, grip at the lower left, a knobbed head at the upper right."""
    x, y = grid()
    shaft = segment(6, 26, 21, 11, 2.7)
    knobs = ((23, 9, 5.6), (27.5, 7.5, 2.6), (24.5, 3.8, 2.6), (19.5, 5.2, 2.4), (27, 12.5, 2.4), (4.6, 27.4, 3.0))
    head = np.max([clip((rad - np.hypot(x - cx, y - cy)) / 1.2) for cx, cy, rad in knobs], axis=0)
    body = np.maximum(shaft > 0.25, head > 0.2)
    lum = body * clip(0.66 - 0.25 * ((x - 16) + (y - 16)) / 20 + 0.2 * (fbm(71) - 0.5))
    soft = np.maximum(shaft, head)
    return np.where(body & (soft < 0.55), 0.18, lum)


def round_bomb():
    """A round black bomb with a shine on it and a fuse cap on top."""
    x, y = grid()
    r = np.hypot(x - 16, y - 18.5)
    ball = r < 11.5
    lum = ball * clip(0.2 + 0.5 * clip(1 - np.hypot(x - 11.5, y - 13.5) / 9.0) ** 1.5)
    lum = np.where(ball & (np.hypot(x - 11, y - 13) < 2.0), 1.0, lum)
    lum = np.where(ball & (r > 10.3), 0.1, lum)
    cap = (np.abs(x - 16) < 3.2) & (y > 4.2) & (y < 8.2)
    fuse = segment(16, 5, 20, 1.5, 1.1) > 0.3
    return np.where(cap, 0.55, np.where(fuse & ~ball, 0.8, lum))


def syringe():
    """A syringe lying along the cell, its needle to the right: plunger, barrel with its dose, needle."""
    x, y = grid()
    barrel = (x > 9) & (x < 23) & (np.abs(y - 16) < 4.6)
    glass = barrel & ((np.abs(y - 16) > 3.3) | (x < 10.3) | (x > 21.7))
    dose = barrel & ~glass & (x < 18.5)
    lum = np.where(glass, 0.95, np.where(dose, 0.5, barrel * 0.2))
    lum = np.where(barrel & (np.abs(x % 3 - 1.5) < 0.5) & (y < 14) & ~glass, 0.8, lum)
    flange = (np.abs(x - 8.5) < 1.0) & (np.abs(y - 16) < 7)
    rod = (x > 2.5) & (x < 9) & (np.abs(y - 16) < 1.3)
    thumb = (np.abs(x - 2.4) < 1.1) & (np.abs(y - 16) < 5)
    needle = (x >= 23) & (x < 31.5) & (np.abs(y - 16) < 1.1 * clip((32.5 - x) / 6 + 0.35))
    hub = (x >= 23) & (x < 25) & (np.abs(y - 16) < 2.4)
    return np.where(flange | thumb | hub, 0.7, np.where(rod, 0.6, np.where(needle, 1.0, lum)))


def droplet():
    x, y = grid()
    w = 6.5 * np.sqrt(clip(1 - ((y - 20) / 8.0) ** 2)) * (y >= 20) + 6.5 * clip((y - 5) / 15.0) ** 1.3 * (y < 20)
    return clip(1.3 - np.abs(x - 16) / np.maximum(w, 0.2)) * (y > 5) * (0.6 + 0.4 * (x < 15))


def sword(up=False):
    """A sword along the cell, point to the right (or up): pommel, grip, a wide guard, a bevelled blade."""
    x, y = grid()
    if up:
        x, y = 32 - y, x
    w = 2.9 * clip((31.5 - x) / 5.0)
    blade = (x > 10) & (np.abs(y - 16) < w)
    lum = blade * np.where(y < 16, 0.95, 0.5)
    lum = np.where(blade & (np.abs(y - 16) < 0.5), 0.72, lum)
    guard = (np.abs(x - 9.3) < 1.3) & (np.abs(y - 16) < 6.5)
    grip = (x > 3) & (x < 8.2) & (np.abs(y - 16) < 1.5)
    pommel = np.hypot(x - 2.6, y - 16) < 2.3
    return np.where(guard | pommel, 0.3, np.where(grip, 0.15, lum))


def tin_can():
    """A dented tin: a lid pried open, a label band."""
    x, y = grid()
    body = (np.abs(x - 16) < 8) & (y > 8) & (y < 28)
    lum = body * clip(0.75 - 0.5 * np.abs(x - 13) / 9.0)
    lum = np.where(body & (np.abs(y - 18) < 4.2), 0.35 + 0.15 * (np.abs(x % 5 - 2.5) < 1), lum)
    lum = np.where(body & ((y < 9.4) | (y > 26.6)), 0.95, lum)
    lid = np.abs(np.hypot((x - 19) / 7.5, (y - 5.5) / 2.6) - 0.85) < 0.3
    dent = body & (np.hypot(x - 20, y - 23.5) < 2.3)
    return np.where(lid, 0.9, np.where(dent, 0.14, lum))


def fish_bone():
    """What is left of a fish: a head with an eye hole, a spine with ribs, a tail."""
    x, y = grid()
    spine = segment(9, 16, 27, 16, 1.1)
    ribs = np.max([segment(px, 16 - h, px + 1.5, 16 + h, 0.9) for px, h in ((12, 5.5), (15.5, 6), (19, 5), (22.5, 3.6))],
                  axis=0)
    tail = np.maximum(segment(27, 16, 31, 11, 1.2), segment(27, 16, 31, 21, 1.2))
    head = clip((5.2 - np.hypot((x - 6) / 1.0, (y - 16) / 1.05)) / 1.0)
    eye = np.hypot(x - 5.2, y - 14.8) < 1.3
    lum = clip(np.maximum.reduce([spine, ribs, tail, head]) * 1.3)
    return np.where(eye, 0.0, lum * 0.92)


def old_boot():
    x, y = grid()
    leg = (x > 9) & (x < 18) & (y > 4) & (y < 24)
    foot = (np.hypot((x - 18) / 10.0, (y - 23.5) / 4.8) < 1) & (y < 27)
    sole = (x > 8) & (x < 28.5) & (y >= 27) & (y < 29.5)
    body = leg | foot
    lum = body * clip(0.55 - 0.25 * (x - 14) / 10.0 + 0.2 * (fbm(81) - 0.5))
    lum = np.where(leg & (y < 6.2), 0.9, lum)
    laces = body & (np.abs(x - 15.5) < 2.2) & (np.abs(y % 4 - 2) < 0.7) & (y > 8) & (y < 22)
    return np.where(sole, 0.15, np.where(laces, 0.95, lum))


def egg():
    """An egg, narrow end up, with a shine and a few speckles."""
    x, y = grid()
    w = 9.5 * (1 + 0.16 * (y - 16) / 12.0)
    d = np.hypot((x - 16) / w, (y - 16.5) / 12.5)
    body = d < 1
    lum = body * clip(0.5 + 0.5 * clip(1 - np.hypot(x - 12, y - 11) / 13.0) ** 1.3)
    lum = np.where(body & (d > 0.88), 0.2, lum)
    spots = body & (fbm(91) > 0.68) & (d < 0.8)
    return np.where(spots, 0.3, lum)


def eggshell(seed):
    """A curved piece of shell with a jagged break."""
    x, y = grid()
    r = np.hypot(x - 16, y - 22)
    jag = 13 + 3.0 * np.sign(np.sin(x * 1.3 + seed))
    return ((np.abs(r - 10.5) < 2.0) & (y < jag) & (y > 9)) * clip(0.95 - 0.3 * (x - 10) / 12.0)


def trident():
    """A trident along the cell, points to the right: a shaft, a crossbar, three barbed prongs."""
    x, y = grid()
    shaft = (x > 0.5) & (x < 21) & (np.abs(y - 16) < 1.4)
    bar_ = (np.abs(x - 20.5) < 1.5) & (np.abs(y - 16) < 8.5)
    lum = np.where(shaft | bar_, 0.55, 0.0)
    lum = np.where(shaft & (y < 16), 0.85, lum)
    for cy, tip in ((8.2, 28.5), (16, 31.5), (23.8, 28.5)):
        w = 1.9 * clip((tip - x) / 4.0)
        prong = (x > 20) & (x < tip) & (np.abs(y - cy) < np.maximum(w, 0))
        barb = (segment(tip - 3.5, cy, tip - 6.5, cy + (2.6 if cy <= 16 else -2.6), 0.9) > 0.3)
        lum = np.where(prong | barb, np.where(y < cy, 1.0, 0.6), lum)
    return lum


def spout():
    """A column of thrown-up water: broad at the foot, torn at the top."""
    x, y = grid()
    t = clip((y - 1) / 30.0)
    w = 3.0 + 8.5 * t ** 0.7
    edge = clip(1.2 - np.abs(x - 16) / w)
    torn = clip((y - 1 - 9 * fbm(101)) / 4.0)
    return clip(edge * torn * (0.55 + 0.6 * fbm(103)))


def muck_lump():
    """A coiled heap, three turns and a tip."""
    x, y = grid()
    coils = ((16, 25.5, 12.0, 5.2), (16, 19, 8.6, 4.6), (16.3, 13.4, 5.6, 4.0), (17.2, 8.6, 2.8, 3.2))
    lum = np.zeros((32, 32))
    for cx, cy, rx, ry in coils:
        d = np.hypot((x - cx) / rx, (y - cy) / ry)
        part = clip(0.45 + 0.5 * clip(1 - np.hypot((x - cx + rx * 0.4) / rx, (y - cy + ry * 0.5) / ry)) - 0.1)
        lum = np.where(d < 1, np.where(d > 0.82, 0.14, part), lum)
    return lum


def crown():
    """A small crown: a band, three points with a bead on each."""
    x, y = grid()
    band_ = (np.abs(x - 16) < 9) & (y > 20) & (y < 26)
    peaks = (np.abs(x - 16) < 9) & (y <= 20) & (y > 20 - 9 * np.abs(np.cos((x - 16) / 9.0 * np.pi * 1.5)) ** 1.5)
    beads = np.min([np.hypot(x - cx, y - 10) for cx in (10, 16, 22)], axis=0) < 1.8
    lum = np.where(band_, 0.8 - 0.4 * (y > 23.5), np.where(peaks, 0.62 + 0.3 * (x < 16), 0.0))
    gem = band_ & (np.abs(x % 6 - 4) < 1.0) & (np.abs(y - 23) < 1.0)
    return np.where(beads | gem, 1.0, lum)


def splat(seed):
    """A burst of thick drops flung out from a middle."""
    r, ang = polar()
    arms = 5.5 + 8.5 * clip(fbm(seed) * 1.6 - 0.25) * (0.5 + 0.5 * np.cos(ang * 7 + seed)) ** 2
    return clip((arms - r) / 2.0) * (0.55 + 0.45 * clip(1 - r / 9.0))


def sickle(turn, seed=3):
    """A crescent of cut air: a keen outer edge, a streaked body."""
    body = crescent(14.5, 12.5, 5.5, turn)
    r, _ = polar()
    return clip(body * (0.45 + 0.6 * clip((r - 8) / 6.0)) * (0.8 + 0.4 * fbm(seed)))


def streak():
    """A hairline of speed along the cell."""
    x, y = grid()
    return clip(1 - np.abs(y - 16) / 1.6) * clip(x / 26.0) ** 1.5


# ----------------------------------------------------------------- shared pieces
def toward(fx):
    """TV = the ground-plane vector from the caster to the target, T its length (never 0)."""
    ok = fx.label()
    fx.vcopy(fx.TV, fx.TGT); fx.vsub(fx.TV, fx.SRC); fx.set(at(fx.TV, 1), 0)
    fx.vlen(fx.T, fx.TV); fx.br(fx.T, '>', 0, ok); fx.set(fx.T, 1)
    fx.label(ok)


def beside(fx, out, base, side, ahead_=0, up=0):
    """out = base moved `side` across the line to the target, `ahead_` along it and `up` higher."""
    toward(fx)
    fx.vcopy(fx.TV2, fx.TV); fx.vmul(fx.TV2, ahead_); fx.vdiv(fx.TV2, fx.T)
    fx.set(fx.T2, at(fx.TV, 0)); fx.set(at(fx.TV, 0), at(fx.TV, 2)); fx.lin(at(fx.TV, 2), fx.T2, -1)
    fx.vmul(fx.TV, side); fx.vdiv(fx.TV, fx.T)
    fx.vcopy(out, base); fx.vadd(out, fx.TV); fx.vadd(out, fx.TV2)
    if up:
        fx.sub_(at(out, 1), up)


def pointing(fx, tail, tip, length, half, colour, cell, clut=0, blend=None):
    """The cell drawn along the line from `tail` to `tip`, `length` long, its right edge at `tip`."""
    ok = fx.label()
    fx.vcopy(fx.TV, tip); fx.vsub(fx.TV, tail)
    fx.vlen(fx.T, fx.TV); fx.br(fx.T, '>', 0, ok); fx.set(fx.T, 1)
    fx.label(ok)
    fx.vmul(fx.TV, length); fx.vdiv(fx.TV, fx.T)
    fx.vcopy(fx.TV2, tip); fx.vsub(fx.TV2, fx.TV)
    band(fx, fx.TV2, tip, half, colour, cell, clut, blend)


def lance(fx, length, half, colour, cell, clut=0, blend=None):
    """In the render of a travel() or shot() instance: the cell drawn along its flight, its right edge leading."""
    fx.vcopy(fx.KEEP, POS); fx.vsub(fx.KEEP, iv(FREE))
    pointing(fx, fx.KEEP, POS, length, half, colour, cell, clut, blend)


def arc_of(fx, name, ticks, height):
    """Define the label name_arc: TV = where a travel() instance is drawn, lifted on an arc that high."""
    fx.label(name + '_arc'); fx.vcopy(fx.TV, POS)
    fx.lin(fx.T, FRAME, 2048 // ticks); fx.sin(fx.T2, fx.T, height); fx.sub_(at(fx.TV, 1), fx.T2); fx.ret()


def turning(fx, pos, colour, size, cells, turn, clut=0, every=1, blend=None):
    """A solid sprite that turns: two cells swapped every few ticks, rotated `turn` a tick."""
    other, done = fx.label(), fx.label()
    fx.lin(fx.F1, FRAME, turn)
    fx.set(fx.F2, FRAME); fx.mod(fx.F2, 2 * every); fx.br(fx.F2, '>=', every, other)
    fx.sprite(pos, colour, size, cell=cells[0], clut=clut, blend=blend, rot=fx.F1); fx.jmp(done)
    fx.label(other); fx.sprite(pos, colour, size, cell=cells[1], clut=clut, blend=blend, rot=fx.F1)
    fx.label(done)


def near_target(fx, label, near=190):
    """In a shot's `every`: when the shot is that near the target's chest, call the label and end the shot."""
    fx.aim(); fx.vcopy(fx.TV, fx.TCHEST); fx.vsub(fx.TV, POS); fx.vlen(fx.T, fx.TV)
    fx.br(fx.T, '>', near, 'noop')
    fx.call(label); fx.set(FRAME, -1)


# ----------------------------------------------------------------- Hagurumon
def darkness_gear():
    """A black cog winds itself up before Hagurumon, shedding a dark haze, then rolls through the air into the target
    and grinds on it in a shower of sparks before it flies apart."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(IRON); fx.palette(GLOOM); fx.palette(SPARK)
    fx.paint(0, gear()); fx.paint(1, gear(np.pi / 8)); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, shard_of(4)); fx.paint(5, ring(13, 2.2)); fx.paint(6, glow(13, 0.7))
    tint, haze, dark = fx.colour(128, 128, 128), fx.colour(90, 40, 128), fx.colour(90, 90, 90)
    wind, fly, grind = 8, 6, 9
    fx.particle('murk', 14, 7, 2, (70, 24, 110), 220, grow=-22, clut=1, fade=True)
    fx.particle('spark', 22, 9, 3, (128, 120, 80), (70, 130), grow=-8, speed=75, lift=35, gravity=9, spread=50, clut=2)
    fx.particle('tooth', 8, 13, 4, (128, 128, 128), (90, 130), speed=60, lift=55, gravity=10, spin=40, blend=None)
    fx.particle('ringout', 2, 8, 5, (110, 50, 128), 160, grow=90, clut=1, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.end(1)
    fx.label('begin')
    beside(fx, fx.AT, fx.CHEST, 0, ahead_=180, up=60); fx.call('cog'); fx.sound(-55); fx.ret()
    cog = fx.pool('cog', 1, 3)
    step = iv(FREE)
    fx.begin('cog', cog, 'cog_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('cog_tick')
    fx.life(wind + fly + grind)
    fx.after(wind, 'cog_go'); fx.after(wind + fly, 'cog_bite'); fx.after(wind + fly + grind, 'cog_break')
    fx.br(FRAME, '<', wind, 'noop')
    fx.br(FRAME, '>=', wind + fly, 'cog_grind')
    fx.vadd(POS, step); fx.emit('murk', POS); fx.ret()
    fx.label('cog_grind'); fx.emit('spark', POS, 2); fx.ret()
    fx.label('cog_go')
    fx.sound(13); fx.aim(); fx.vcopy(step, fx.TCHEST); fx.vsub(step, POS); fx.vdiv(step, fly); fx.ret()
    fx.label('cog_bite'); fx.sound(20); fx.aim(); fx.hit(); fx.emit('spark', POS, 6); fx.ret()
    fx.label('cog_break')
    fx.sound(16); fx.emit('tooth', POS, 8); fx.emit('ringout', POS); fx.emit('spark', POS, 8); fx.ret()
    fx.label('cog_render')
    # it shakes while it grinds
    fx.vcopy(fx.TV2, POS); fx.br(FRAME, '<', wind + fly, 'cog_size'); fx.scatter(fx.TV2, 50)
    fx.label('cog_size')
    fx.lin(fx.T3, FRAME, 55, 80); fx.br(fx.T3, '<', 440, 'cog_draw'); fx.set(fx.T3, 440)
    fx.label('cog_draw')
    fx.lin(fx.T, fx.T3, 16, 0, 10)
    fx.sprite(fx.TV2, dark, fx.T, cell=6, blend='sub'); fx.sprite(fx.TV2, haze, fx.T, cell=2, clut=1)
    turning(fx, fx.TV2, tint, fx.T3, (0, 1), 330); fx.ret()
    return fx


# ----------------------------------------------------------------- Nefertimon
def rocking_stone():
    """Two carved tablets take shape in a shaft of sunlight high over the target and drop one after the other; the
    first staggers it, the second lands the blow, and dust and chips of stone fly out from under them."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(STONE); fx.palette(SUN); fx.palette(DUST)
    fx.paint(0, tablet(0)); fx.paint(1, tablet(3)); fx.paint(2, glow(15, 1.2)); fx.paint(3, shard_of(9))
    fx.paint(4, puff(5)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, ring(13, 2.0))
    tint, sun = fx.colour(128, 128, 128), fx.colour(128, 104, 50)
    which = fx.const(0)
    high, form, fall = 900, 7, 4
    fx.particle('mote', 14, 8, 5, (128, 120, 70), (60, 110), grow=-8, flat=((-8, 8), (20, 50), (-8, 8)), spread=260,
                clut=1)
    fx.particle('dust', 12, 11, 4, (120, 105, 84), 170, grow=30, flat=((-40, 40), (-14, 0), (-40, 40)), spread=120,
                clut=2, blend='half')
    fx.particle('chip', 14, 13, 3, (128, 128, 128), (60, 110), speed=55, lift=55, gravity=10, spin=30, blend=None)
    fx.particle('ringout', 2, 8, 6, (128, 104, 50), 200, grow=80, clut=1, fade=True, sy=6)
    fx.label('main'); fx.when(0, 'raise'); fx.when(8, 'raise'); fx.end(9)
    fx.label('raise')
    fx.aim(); fx.vcopy(fx.AT, fx.TGT); fx.sub_(at(fx.AT, 1), high)
    fx.set(fx.T, which); fx.mul(fx.T, 240); fx.add(fx.T, -120); fx.add(at(fx.AT, 0), fx.T)
    fx.call('slab'); fx.sound(34); fx.add(which, 1); fx.ret()
    slab = fx.pool('slab', 2, 2)
    turn, nth = iv(FREE), iv(FREE + 4)
    fx.begin('slab', slab, 'slab_render', inherit=False)
    fx.vcopy(POS, fx.AT); fx.set(nth, which); fx.lin(turn, which, 44, -22); fx.ret()
    fx.label('slab_tick')
    fx.life(form + fall + 9)
    fx.br(FRAME, '>=', form + fall, 'slab_rest')
    fx.br(FRAME, '>=', form, 'slab_fall')
    fx.emit('mote', POS); fx.ret()
    fx.label('slab_fall')
    # it falls onto wherever the target now stands
    fx.aim(); fx.vcopy(fx.TV, fx.TGT); fx.lin(fx.T, at(fx.TSIZE, 1), 1, 60); fx.sub_(at(fx.TV, 1), fx.T)
    fx.lin(fx.T, nth, 160, -80); fx.add(at(fx.TV, 0), fx.T)
    fx.vsub(fx.TV, POS); fx.lin(fx.T, FRAME, -1, form + fall); fx.vdiv(fx.TV, fx.T); fx.vadd(POS, fx.TV)
    fx.after(form + fall - 1, 'slab_land'); fx.ret()
    fx.label('slab_rest'); fx.ret()
    fx.label('slab_land')
    fx.sound(40); fx.emit('dust', POS, 6); fx.emit('chip', POS, 7); fx.emit('ringout', POS)
    fx.br(nth, '==', 0, 'noop'); fx.sound(16); fx.aim(); fx.hit(); fx.ret()
    fx.label('slab_render')
    fx.br(FRAME, '>=', form + fall, 'slab_solid')
    # the shaft of light it forms in, thinning as the stone hardens
    fx.lin(fx.T3, FRAME, -22, 330); fx.vcopy(fx.TV2, POS); fx.sub_(at(fx.TV2, 1), 200)
    fx.sprite(fx.TV2, sun, fx.T3, 900, cell=2, clut=1)
    fx.label('slab_solid')
    fx.lin(fx.T3, FRAME, 60, 60); fx.br(fx.T3, '<', 330, 'slab_draw'); fx.set(fx.T3, 330)
    fx.label('slab_draw')
    fx.lin(fx.T, fx.T3, 13, 0, 10); fx.br(nth, '!=', 0, 'slab_two')
    fx.sprite(POS, tint, fx.T3, fx.T, cell=0, blend=None, rot=turn); fx.ret()
    fx.label('slab_two'); fx.sprite(POS, tint, fx.T3, fx.T, cell=1, blend=None, rot=turn); fx.ret()
    return fx


# ----------------------------------------------------------------- Shakkoumon
def clay_bomb():
    """Three clay figures pop out of Shakkoumon one after another and tumble in high arcs onto the spot where the
    target stands; each goes off in a flash, potsherds and a cloud of red dust. Whoever is still there when the
    second lands is hit."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(CLAY); fx.palette(FIRE); fx.palette(DUST)
    fx.paint(0, dogu()); fx.paint(1, shard_of(13)); fx.paint(2, shard_of(17)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, puff(8)); fx.paint(5, star(6, 2, 10, 5)); fx.paint(6, ring(13, 2.2))
    tint = fx.colour(128, 128, 128)
    spot, nth = fx.vec(), fx.const(0)
    flight, gap = 11, 4
    fx.particle('pop', 3, 5, 6, (128, 100, 60), 80, grow=60, clut=1, fade=True)
    fx.particle('flash', 3, 6, 5, (128, 110, 70), 260, grow=70, clut=1, fade=True)
    fx.particle('sherd', 18, 13, 1, (128, 128, 128), (70, 120), speed=65, lift=60, gravity=10, spin=35, blend=None)
    fx.particle('sherd2', 12, 13, 2, (128, 128, 128), (60, 100), speed=65, lift=45, gravity=10, spin=-30, blend=None)
    fx.particle('cloud', 12, 12, 4, (128, 84, 60), 190, grow=34, speed=22, lift=8, spread=120, clut=2, blend='half')
    fx.label('main'); fx.when(0, 'begin')
    for k in range(3):
        fx.when(gap * k, 'lob')
    fx.end(2 * gap + 1)
    fx.label('begin'); fx.vcopy(spot, fx.TGT); fx.ret()
    fx.label('lob')
    fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, spot); fx.sub_(at(fx.DEST, 1), 120)
    fx.br(nth, '==', 1, 'lob_go'); fx.scatter(fx.DEST, 360); fx.lin(at(fx.DEST, 1), at(spot, 1), 1, -120)
    fx.label('lob_go')
    fx.emit('pop', fx.CHEST); fx.vcopy(fx.AT, fx.CHEST); fx.set(fx.SZ, nth); fx.call('idol'); fx.sound(4)
    fx.add(nth, 1); fx.ret()
    fx.travel('idol', 3, flight, 'idol_render', 'idol_land', fields=1, every='idol_know')
    mine = iv(FREE + 12)
    arc_of(fx, 'idol', flight, 560)
    fx.label('idol_know'); fx.br(FRAME, '!=', 1, 'noop'); fx.set(mine, fx.SZ); fx.ret()
    fx.label('idol_render')
    fx.call('idol_arc'); fx.lin(fx.T3, FRAME, 190)
    fx.sprite(fx.TV, tint, 300, cell=0, blend=None, rot=fx.T3); fx.ret()
    fx.label('idol_land')
    fx.sound(7)
    fx.emit('flash', POS); fx.emit('sherd', POS, 6); fx.emit('sherd2', POS, 4); fx.emit('cloud', POS, 4)
    fx.br(mine, '!=', 1, 'noop'); fx.strike(POS, 200); fx.ret()
    return fx


# ----------------------------------------------------------------- MetalGreymon (Vaccine)
def trident_arm():
    """The metal claw leaves MetalGreymon's arm on a rattling chain, shuts on the target in a burst of sparks, wrenches
    it, and is reeled back in."""
    fx = Fx(delay=8, cast_sound=19)
    fx.palette(STEEL); fx.palette(SPARK)
    fx.paint(0, claw()); fx.paint(1, cable()); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, ring(13, 2.2)); fx.paint(5, streak())
    tint, hot = fx.colour(128, 128, 128), fx.colour(128, 100, 50)
    hand = fx.vec()
    out, grip, back = 5, 7, 6
    fx.particle('spark', 22, 10, 3, (128, 120, 80), (70, 130), grow=-8, speed=70, lift=35, gravity=9, spread=50, clut=1)
    fx.particle('bang', 2, 6, 2, (128, 110, 70), 200, grow=70, clut=1, fade=True)
    fx.particle('ringout', 2, 8, 4, (128, 100, 50), 150, grow=80, clut=1, fade=True)
    fx.particle('puff_', 6, 6, 2, (70, 70, 80), 140, grow=30, fade=True, clut=1)
    fx.label('main'); fx.when(0, 'launch'); fx.end(1)
    fx.label('launch')
    beside(fx, hand, fx.CHEST, -90, ahead_=120)
    fx.vcopy(fx.AT, hand); fx.call('fist'); fx.emit('puff_', hand, 3); fx.sound(13); fx.ret()
    fist = fx.pool('fist', 1, 3)
    step = iv(FREE)
    fx.begin('fist', fist, 'fist_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('fist_tick')
    fx.life(out + grip + back)
    fx.after(out, 'fist_clamp'); fx.after(out + 4, 'fist_wrench')
    fx.br(FRAME, '>=', out + grip, 'fist_back')
    fx.br(FRAME, '>=', out, 'fist_hold')
    # out: a new aim every tick, so the claw finds the target wherever it went
    fx.aim(); fx.vcopy(step, fx.TCHEST); fx.vsub(step, POS); fx.lin(fx.T, FRAME, -1, out); fx.vdiv(step, fx.T)
    fx.vadd(POS, step); fx.ret()
    fx.label('fist_hold'); fx.aim(); fx.vcopy(POS, fx.TCHEST); fx.emit('spark', POS); fx.ret()
    fx.label('fist_back')
    fx.vcopy(step, hand); fx.vsub(step, POS); fx.lin(fx.T, FRAME, -1, out + grip + back + 1); fx.vdiv(step, fx.T)
    fx.vadd(POS, step); fx.ret()
    fx.label('fist_clamp'); fx.sound(20); fx.emit('spark', POS, 8); fx.emit('bang', POS); fx.ret()
    fx.label('fist_wrench')
    fx.sound(16); fx.aim(); fx.hit(); fx.emit('ringout', POS); fx.emit('bang', POS); fx.emit('spark', POS, 8); fx.ret()
    fx.label('fist_render')
    fx.vcopy(fx.TV2, POS); fx.br(FRAME, '<', out, 'fist_draw'); fx.br(FRAME, '>=', out + grip, 'fist_draw')
    fx.scatter(fx.TV2, 44)
    fx.label('fist_draw')
    fx.vcopy(fx.KEEP, fx.TV2)
    band(fx, hand, fx.KEEP, 55, tint, 1, blend=None)
    pointing(fx, hand, fx.KEEP, 460, 230, tint, 0, blend=None)
    fx.sprite(hand, hot, 150, cell=2, clut=1); fx.ret()
    return fx


# ----------------------------------------------------------------- Shurimon
def double_stars():
    """Shurimon's two great shuriken spin up at its sides in a swirl of leaves and are flung, one a beat after the
    other, straight at where the target stands. The first to connect deals the blow; a target that moved is missed."""
    fx = Fx(delay=8, cast_sound=19)
    fx.palette(STEEL); fx.palette(LEAF)
    fx.paint(0, shuriken()); fx.paint(1, shuriken(np.pi / 8)); fx.paint(2, leaf()); fx.paint(3, glow(15, 1.2))
    fx.paint(4, ring(13, 2.0)); fx.paint(5, star(4, 2, 9, 6)); fx.paint(6, streak())
    tint, green = fx.colour(128, 128, 128), fx.colour(60, 128, 50)
    left, right = fx.vec(), fx.vec()
    landed = fx.const(0)
    spin_up, gap = 8, 4
    fx.particle('swirl', 16, 8, 2, (90, 128, 70), (90, 150), grow=-6, speed=30, lift=18, spread=220, clut=1, spin=25)
    fx.particle('wake', 16, 5, 2, (70, 128, 60), 150, grow=-22, clut=1, spin=30)
    fx.particle('cut', 2, 6, 5, (128, 128, 128), 200, grow=90, clut=1, fade=True)
    fx.particle('ringout', 2, 8, 4, (70, 128, 60), 160, grow=80, clut=1, fade=True)
    fx.particle('fall', 14, 14, 2, (90, 128, 70), (80, 130), speed=45, lift=40, gravity=5, spread=80, clut=1, spin=20)
    fx.label('main'); fx.when(0, 'begin'); fx.when(spin_up, 'throw_l'); fx.when(spin_up + gap, 'throw_r')
    fx.br(fx.NOW, '>=', spin_up + gap, 'main_end')
    fx.emit('swirl', left); fx.br(fx.NOW, '>=', spin_up, 'main_r')
    fx.label('main_r'); fx.emit('swirl', right)
    fx.label('main_end'); fx.end(spin_up + gap + 1)
    fx.label('begin')
    beside(fx, left, fx.CHEST, -260, up=60); beside(fx, right, fx.CHEST, 260, up=60)
    fx.vcopy(fx.AT, left); fx.set(fx.SZ, 0); fx.call('held')
    fx.vcopy(fx.AT, right); fx.set(fx.SZ, gap); fx.call('held'); fx.sound(-55); fx.ret()
    held = fx.pool('held', 2, 1)
    extra = iv(FREE)
    fx.begin('held', held, 'held_render', inherit=False); fx.vcopy(POS, fx.AT); fx.set(extra, fx.SZ); fx.ret()
    fx.label('held_tick'); fx.lin(fx.T, extra, 1, spin_up - 1); fx.br(FRAME, '>', fx.T, 'die'); fx.ret()
    fx.label('held_render')
    fx.lin(fx.T3, FRAME, 40, 60); fx.br(fx.T3, '<', 330, 'held_draw'); fx.set(fx.T3, 330)
    fx.label('held_draw'); turning(fx, POS, tint, fx.T3, (0, 1), 400); fx.ret()
    for side, src in (('l', left), ('r', right)):
        fx.label('throw_' + side)
        fx.sound(13); fx.aim(); fx.vcopy(fx.AT, src); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('blade'); fx.ret()
    fx.shot('blade', 2, 100, 16, 'blade_render', 'blade_arrive', every='blade_trail', extent=(110, 170, 110))
    fx.label('blade_trail')
    fx.emit('wake', POS)
    fx.br(landed, '==', 0, 'noop')
    near_target(fx, 'blade_burst'); fx.ret()
    fx.label('blade_render')
    fx.sprite(POS, green, 460, cell=3, clut=1); lance(fx, 420, 40, green, 6, clut=1, blend='add')
    turning(fx, POS, tint, 340, (0, 1), 500); fx.ret()
    fx.label('blade_arrive'); fx.set(landed, 1)
    fx.label('blade_burst')
    fx.sound(20); fx.emit('cut', POS); fx.emit('ringout'); fx.emit('fall', times=7); fx.ret()
    return fx


# ----------------------------------------------------------------- Apemon
def angry_spike():
    """Apemon's bone club is hurled end over end in a high arc onto the spot where the target stands and comes down with
    a crack: a yellow jolt, flying splinters and a kick of dust. A target that has left the spot is missed."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(BONE); fx.palette(SUN); fx.palette(DUST)
    fx.paint(0, bone_club()); fx.paint(1, shard_of(23)); fx.paint(2, star(8, 2.5, 11, 5)); fx.paint(3, puff(12))
    fx.paint(4, ring(13, 2.4)); fx.paint(5, streak()); fx.paint(6, glow(15, 1.2))
    tint = fx.colour(128, 128, 128)
    flight = 12
    fx.particle('whoosh', 12, 4, 6, (70, 60, 40), 220, grow=-40, clut=1, fade=True)
    fx.particle('crack', 2, 6, 2, (128, 120, 70), 220, grow=90, clut=1, fade=True)
    fx.particle('ringout', 2, 8, 4, (128, 110, 60), 170, grow=90, clut=1, fade=True, sy=7)
    fx.particle('splinter', 16, 13, 1, (128, 128, 128), (60, 110), speed=70, lift=65, gravity=10, spin=40, blend=None)
    fx.particle('dust', 10, 11, 3, (120, 105, 84), 170, grow=32, flat=((-45, 45), (-16, 0), (-45, 45)), spread=100,
                clut=2, blend='half')
    fx.label('main'); fx.when(0, 'throw'); fx.end(1)
    fx.label('throw')
    fx.vcopy(fx.AT, fx.CHEST); fx.sub_(at(fx.AT, 1), 120); fx.vcopy(fx.DEST, fx.TGT); fx.sub_(at(fx.DEST, 1), 80)
    fx.call('club'); fx.sound(13); fx.ret()
    fx.travel('club', 1, flight, 'club_render', 'club_land', every='club_trail')
    arc_of(fx, 'club', flight, 620)
    fx.label('club_trail'); fx.call('club_arc'); fx.emit('whoosh', fx.TV); fx.ret()
    fx.label('club_render')
    fx.call('club_arc'); fx.lin(fx.T3, FRAME, 520)
    fx.sprite(fx.TV, tint, 480, cell=0, blend=None, rot=fx.T3); fx.ret()
    fx.label('club_land')
    fx.sound(40); fx.strike(POS, 230)
    fx.emit('crack', POS); fx.emit('ringout'); fx.emit('splinter', times=9); fx.emit('dust', times=6)
    fx.call('bounce'); fx.ret()
    # the club itself springs back up off the ground, still turning, and drops
    bounce = fx.pool('bounce', 1, 1)
    vy = iv(FREE)
    fx.begin('bounce', bounce, 'bounce_render', inherit=False); fx.vcopy(POS, fx.AT); fx.set(vy, -95); fx.ret()
    fx.label('bounce_tick'); fx.life(11); fx.add(at(POS, 1), vy); fx.add(vy, 17); fx.add(at(POS, 0), 22); fx.ret()
    fx.label('bounce_render')
    fx.lin(fx.T3, FRAME, -300, 1000); fx.sprite(POS, tint, 480, cell=0, blend=None, rot=fx.T3); fx.ret()
    return fx


# ----------------------------------------------------------------- BomberNanimon
def free_throw_bomb():
    """A big round bomb, fuse spitting, is lobbed high like a basketball onto the spot where the target stands. It goes
    up in a ball of fire, a ring of blast and rolling black smoke; a target that got off the spot is missed."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(BOMB); fx.palette(FIRE); fx.palette(SMOKE)
    fx.paint(0, round_bomb()); fx.paint(1, star(4, 2, 9, 6)); fx.paint(2, glow(15, 1.2)); fx.paint(3, puff(3))
    fx.paint(4, puff(17)); fx.paint(5, ring(13, 2.4)); fx.paint(6, star(7, 3, 12, 3))
    tint, fuse = fx.colour(128, 128, 128), fx.colour(128, 110, 60)
    flight = 14
    fx.particle('fizz', 14, 6, 1, (128, 110, 60), (50, 90), grow=-8, speed=18, lift=10, gravity=4, clut=1)
    fx.particle('fire', 4, 8, 3, (128, 120, 90), 240, grow=75, clut=1, fade=True)
    fx.particle('burst', 2, 6, 6, (128, 128, 110), 300, grow=110, clut=1, fade=True)
    fx.particle('ringout', 2, 9, 5, (128, 90, 40), 200, grow=110, clut=1, fade=True, sy=7)
    fx.particle('smoke', 12, 16, 4, (110, 104, 100), 220, grow=26, flat=((-30, 30), (-48, -20), (-30, 30)),
                spread=200, clut=2, blend='half')
    fx.particle('ember', 16, 13, 1, (128, 100, 50), (60, 110), grow=-5, speed=80, lift=50, gravity=9, clut=1)
    fx.label('main'); fx.when(0, 'throw'); fx.end(1)
    fx.label('throw')
    fx.vcopy(fx.AT, fx.CHEST); fx.sub_(at(fx.AT, 1), 160); fx.vcopy(fx.DEST, fx.TGT); fx.sub_(at(fx.DEST, 1), 110)
    fx.call('bomb'); fx.sound(4); fx.ret()
    fx.travel('bomb', 1, flight, 'bomb_render', 'bomb_land', every='bomb_trail')
    arc_of(fx, 'bomb', flight, 900)
    fx.label('bomb_trail')
    fx.call('bomb_arc'); fx.sub_(at(fx.TV, 1), 170); fx.add(at(fx.TV, 0), 60); fx.emit('fizz', fx.TV); fx.ret()
    fx.label('bomb_render')
    fx.call('bomb_arc'); fx.lin(fx.T3, FRAME, 60)
    fx.sprite(fx.TV, tint, 380, cell=0, blend=None, rot=fx.T3)
    fx.sub_(at(fx.TV, 1), 170); fx.add(at(fx.TV, 0), 60); fx.sprite(fx.TV, fuse, 170, cell=1, clut=1); fx.ret()
    fx.label('bomb_land')
    fx.sound(7); fx.strike(POS, 220); fx.sub_(at(POS, 1), 100)
    fx.emit('burst', POS); fx.emit('fire', POS, 3); fx.emit('ringout'); fx.emit('ember', times=12)
    fx.call('after_'); fx.ret()
    # the smoke goes on rolling up after the flash is gone
    after_ = fx.pool('after_', 1)
    fx.begin('after_', after_, 'noop', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('after__tick'); fx.life(5); fx.emit('smoke', POS, 2); fx.ret()
    return fx


# ----------------------------------------------------------------- DemiDevimon
def demi_dart():
    """A syringe as long as DemiDevimon itself, loaded with something violet, is thrown like a dart, straight and fast,
    dripping as it goes. Where it sticks, its dose bursts out in a violet spray. A target that moved is missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(SERUM); fx.palette(VENOM)
    fx.paint(0, syringe()); fx.paint(1, droplet()); fx.paint(2, glow(15, 1.2)); fx.paint(3, splat(4))
    fx.paint(4, splat(9)); fx.paint(5, ring(13, 2.0)); fx.paint(6, streak())
    tint, glint = fx.colour(128, 128, 128), fx.colour(110, 60, 128)
    hand = fx.vec()
    fx.particle('drip', 12, 9, 1, (110, 60, 128), (60, 90), grow=-5, flat=((-6, 6), (4, 14), (-6, 6)), gravity=6,
                clut=1)
    fx.particle('ready', 1, 6, 2, (110, 60, 128), 60, grow=50, clut=1, fade=True)
    fx.particle('gush', 3, 8, 3, (128, 100, 128), 240, grow=85, clut=1, fade=True)
    fx.particle('gush2', 2, 9, 4, (128, 80, 128), 200, grow=90, clut=1, fade=True, spin=12)
    fx.particle('bead', 18, 13, 1, (128, 80, 128), (70, 120), grow=-5, speed=60, lift=55, gravity=10, spread=50, clut=1)
    fx.particle('ringout', 2, 8, 5, (110, 50, 128), 120, grow=80, clut=1, fade=True)
    fx.label('main'); fx.when(0, 'begin'); fx.when(6, 'throw'); fx.end(7)
    fx.label('begin')
    beside(fx, hand, fx.CHEST, 0, ahead_=120, up=140); fx.emit('ready', hand); fx.sound(34); fx.ret()
    fx.label('throw')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, hand); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('dart'); fx.ret()
    fx.shot('dart', 1, 90, 20, 'dart_render', 'dart_arrive', miss='dart_miss', every='dart_trail')
    fx.label('dart_trail'); fx.emit('drip', POS); fx.ret()
    fx.label('dart_render')
    lance(fx, 760, 60, glint, 6, clut=1, blend='add')
    lance(fx, 540, 270, tint, 0, blend=None); fx.ret()
    fx.label('dart_miss'); fx.emit('bead', POS, 5); fx.ret()
    fx.label('dart_arrive')
    fx.sound(20); fx.emit('gush', POS, 2); fx.emit('gush2', POS, 2); fx.emit('ringout'); fx.emit('bead', times=14)
    fx.ret()
    return fx


# ----------------------------------------------------------------- Piedmon
def trump_sword():
    """Four swords appear in a fan over Piedmon, points up, each with a wink of magic; then they tip over and fly at the
    target one after another, wherever it runs, and run it through. The first to arrive lands the blow."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(STEEL); fx.palette(MAGIC)
    fx.paint(0, sword()); fx.paint(1, sword(up=True)); fx.paint(2, glow(15, 1.2)); fx.paint(3, star(4, 2, 9, 6))
    fx.paint(4, ring(13, 2.0)); fx.paint(5, streak()); fx.paint(6, star(4, 1.5, 13, 14, np.pi / 4))
    tint, pink = fx.colour(128, 128, 128), fx.colour(128, 50, 110)
    slot = [fx.vec() for _ in range(4)]
    nth, landed = fx.var(), fx.const(0)
    hang, gap, flight = 10, 3, 5
    fx.particle('wink', 4, 6, 6, (128, 90, 128), 60, grow=60, clut=1, fade=True)
    fx.particle('trail', 20, 5, 2, (128, 40, 110), 170, grow=-28, clut=1, fade=True)
    fx.particle('stab', 4, 7, 3, (128, 128, 128), 300, grow=80, clut=1, fade=True)
    fx.particle('ringout', 2, 8, 4, (128, 50, 110), 150, grow=80, clut=1, fade=True)
    fx.particle('glitter', 20, 12, 3, (128, 80, 128), (90, 150), grow=-6, speed=60, lift=40, gravity=7, clut=1)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(4):
        fx.when(gap * k, 'draw_one'); fx.when(hang + gap * k, 'loose')
    fx.end(hang + 3 * gap + 1)
    fx.label('begin')
    for k in range(4):
        beside(fx, slot[k], fx.SRC, -390 + 260 * k)
        fx.lin(fx.T, at(fx.SSIZE, 1), 1, 60 + 150 * (k in (1, 2))); fx.sub_(at(slot[k], 1), fx.T)
    fx.set(nth, 0); fx.ret()
    fx.label('pick')                        # AT = the slot of the nth sword
    for k in range(4):
        skip = fx.label()
        fx.br(nth, '!=', k, skip); fx.vcopy(fx.AT, slot[k])
        fx.label(skip)
    fx.ret()
    fx.label('draw_one')
    fx.lin(nth, fx.NOW, 1, 0, gap); fx.call('pick'); fx.call('hung'); fx.call('wink'); fx.sound(34); fx.ret()
    hung = fx.pool('hung', 4)
    fx.begin('hung', hung, 'hung_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('hung_tick'); fx.life(hang - 1); fx.ret()
    fx.label('hung_render')
    fx.sprite(POS, pink, 420, cell=2, clut=1); fx.sprite(POS, tint, 420, cell=1, blend=None); fx.ret()
    fx.label('loose')
    fx.lin(nth, fx.NOW, 1, -hang, gap); fx.call('pick')
    fx.sound(13); fx.aim(); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('flown'); fx.ret()
    fx.travel('flown', 4, flight, 'flown_render', 'flown_arrive', every='flown_trail')
    fx.label('flown_trail'); fx.emit('trail', POS); fx.ret()
    fx.label('flown_render')
    lance(fx, 760, 70, pink, 5, clut=1, blend='add'); lance(fx, 480, 240, tint, 0, blend=None); fx.ret()
    fx.label('flown_arrive')
    fx.sound(20); fx.aim(); fx.vcopy(POS, fx.TCHEST)
    fx.emit('stab', POS); fx.emit('glitter', times=5)
    fx.br(landed, '!=', 0, 'noop'); fx.set(landed, 1); fx.sound(16); fx.hit(); fx.emit('ringout', POS); fx.ret()
    return fx


# ----------------------------------------------------------------- Garbagemon
def junk_chunker():
    """A tin, a fish bone and an old boot are slung out of Garbagemon's can one after another and tumble onto the spot
    where the target stands, each landing in a splat of green stench and a buzz of flies. Whoever is still there
    when the tin lands is hit."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(JUNK); fx.palette(STINK)
    fx.paint(0, tin_can()); fx.paint(1, fish_bone()); fx.paint(2, old_boot()); fx.paint(3, puff(21))
    fx.paint(4, splat(14)); fx.paint(5, glow(6, 0.6)); fx.paint(6, shard_of(31))
    tint = fx.colour(128, 128, 128)
    spot, nth = fx.vec(), fx.const(0)
    flight, gap = 10, 4
    fx.particle('whiff', 14, 5, 3, (60, 90, 30), 150, grow=-18, clut=1, fade=True)
    fx.particle('stench', 12, 14, 3, (96, 128, 60), 200, grow=30, flat=((-22, 22), (-34, -12), (-22, 22)),
                spread=160, clut=1, blend='half')
    fx.particle('goo', 3, 7, 4, (110, 128, 60), 160, grow=70, clut=1, fade=True, spin=10)
    fx.particle('fly', 16, 16, 5, (128, 128, 128), 70, speed=50, lift=30, spread=200, clut=1, blend='sub')
    fx.particle('scrap', 12, 13, 6, (128, 128, 128), (60, 100), speed=60, lift=55, gravity=10, spin=35, blend=None)
    fx.label('main'); fx.when(0, 'begin')
    for k in range(3):
        fx.when(gap * k, 'sling')
    fx.end(2 * gap + 1)
    fx.label('begin'); fx.vcopy(spot, fx.TGT); fx.ret()
    fx.label('sling')
    fx.vcopy(fx.AT, fx.SRC); fx.lin(fx.T, at(fx.SSIZE, 1), 1, 40); fx.sub_(at(fx.AT, 1), fx.T)
    fx.vcopy(fx.DEST, spot); fx.sub_(at(fx.DEST, 1), 120)
    fx.br(nth, '==', 0, 'sling_go'); fx.scatter(fx.DEST, 340); fx.lin(at(fx.DEST, 1), at(spot, 1), 1, -120)
    fx.label('sling_go')
    fx.set(fx.SZ, nth); fx.call('junk'); fx.sound(4); fx.add(nth, 1); fx.ret()
    fx.travel('junk', 3, flight, 'junk_render', 'junk_land', fields=1, every='junk_trail')
    what = iv(FREE + 12)
    arc_of(fx, 'junk', flight, 520)
    fx.label('junk_trail')
    fx.br(FRAME, '!=', 1, 'junk_reek'); fx.set(what, fx.SZ)
    fx.label('junk_reek'); fx.call('junk_arc'); fx.emit('whiff', fx.TV); fx.ret()
    fx.label('junk_render')
    fx.call('junk_arc'); fx.lin(fx.T3, FRAME, 260)
    for k in range(3):
        skip = fx.label()
        fx.br(what, '!=', k, skip); fx.sprite(fx.TV, tint, 320, cell=k, blend=None, rot=fx.T3)
        fx.label(skip)
    fx.ret()
    fx.label('junk_land')
    fx.sound(40); fx.emit('goo', POS); fx.emit('stench', POS, 4); fx.emit('fly', POS, 5); fx.emit('scrap', POS, 4)
    fx.br(what, '!=', 0, 'noop'); fx.sound(16); fx.strike(POS, 200); fx.ret()
    return fx


# ----------------------------------------------------------------- Deramon
def royal_smasher():
    """Deramon fires an egg like a shell from a gun: a bang and a ring of smoke, the egg streaking flat and fast, and
    where it hits it cracks open in a burst of yolk and flying shell. A target that moved is missed."""
    fx = Fx(delay=8, cast_sound=0)
    fx.palette(EGG); fx.palette(YOLK); fx.palette(DUST)
    fx.paint(0, egg()); fx.paint(1, eggshell(1)); fx.paint(2, eggshell(4)); fx.paint(3, splat(6))
    fx.paint(4, ring(12, 3.0)); fx.paint(5, glow(15, 1.2)); fx.paint(6, streak()); fx.paint(7, puff(27))
    tint, warm = fx.colour(128, 128, 128), fx.colour(128, 110, 60)
    muzzle = fx.vec()
    fx.particle('bang', 2, 5, 5, (128, 120, 80), 160, grow=60, clut=1, fade=True)
    fx.particle('smokering', 2, 8, 4, (128, 124, 116), 90, grow=30, clut=2, blend='half')
    fx.particle('fluff', 6, 9, 7, (100, 96, 90), 130, grow=24, speed=16, clut=2, blend='half')
    fx.particle('yolk', 3, 9, 3, (128, 120, 70), 280, grow=95, clut=1, fade=True, spin=9)
    fx.particle('glob', 16, 13, 5, (128, 110, 40), (90, 160), grow=-5, speed=60, lift=50, gravity=10, clut=1)
    fx.particle('shell', 10, 14, 1, (128, 128, 128), (170, 250), speed=70, lift=65, gravity=10, spin=35, blend=None)
    fx.particle('shell2', 10, 14, 2, (128, 128, 128), (170, 250), speed=70, lift=55, gravity=10, spin=-35, blend=None)
    fx.label('main'); fx.when(0, 'begin'); fx.when(5, 'fire'); fx.end(6)
    fx.label('begin'); beside(fx, muzzle, fx.CHEST, 0, ahead_=140, up=40); fx.sound(-55); fx.ret()
    fx.label('fire')
    fx.sound(3); fx.aim(); fx.vcopy(fx.AT, muzzle); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('round')
    fx.emit('bang', muzzle); fx.emit('smokering', muzzle); fx.emit('fluff', muzzle, 4); fx.ret()
    fx.shot('round', 1, 85, 20, 'round_render', 'round_arrive', miss='round_miss')
    fx.label('round_render')
    lance(fx, 800, 120, warm, 6, clut=1, blend='add'); fx.lin(fx.T3, FRAME, 420)
    fx.sprite(POS, tint, 400, cell=0, blend=None, rot=fx.T3); fx.ret()
    fx.label('round_miss'); fx.emit('shell', POS, 3); fx.ret()
    fx.label('round_arrive')
    fx.sound(7); fx.emit('yolk', POS, 2); fx.emit('glob', times=12); fx.emit('shell', times=6)
    fx.emit('shell2', times=6); fx.ret()
    return fx


# ----------------------------------------------------------------- Dragomon
def tentacle_claw():
    """Dragomon's trident is thrown out of a swirl of black water and flies straight, dragging a wake of spray; where it
    strikes, the sea comes up in a spout around it. A target that moved is missed."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(SEASTEEL); fx.palette(DEEP)
    fx.paint(0, trident()); fx.paint(1, spout()); fx.paint(2, glow(15, 1.2)); fx.paint(3, droplet())
    fx.paint(4, ring(13, 2.4)); fx.paint(5, streak()); fx.paint(6, puff(33))
    tint, sea = fx.colour(128, 128, 128), fx.colour(40, 110, 128)
    hand = fx.vec()
    wind = 7
    fx.particle('eddy', 14, 7, 6, (30, 90, 128), (120, 200), grow=-14, speed=26, spread=320, clut=1, fade=True)
    fx.particle('spray', 20, 7, 3, (60, 120, 128), (70, 110), grow=-8, speed=22, lift=14, gravity=5, clut=1)
    fx.particle('ringout', 2, 9, 4, (60, 120, 128), 180, grow=95, clut=1, fade=True, sy=7)
    fx.particle('drop', 18, 14, 3, (80, 128, 128), (60, 110), grow=-4, speed=55, lift=75, gravity=10, spread=80, clut=1)
    fx.label('main'); fx.when(0, 'begin'); fx.when(wind, 'throw')
    fx.br(fx.NOW, '>=', wind, 'main_end'); fx.emit('eddy', hand, 2)
    fx.label('main_end'); fx.end(wind + 1)
    fx.label('begin'); beside(fx, hand, fx.CHEST, 110, ahead_=60, up=120); fx.sound(-55); fx.ret()
    fx.label('throw')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, hand); fx.vcopy(fx.DEST, fx.TCHEST); fx.call('spear'); fx.ret()
    fx.shot('spear', 1, 110, 17, 'spear_render', 'spear_arrive', miss='spear_miss', every='spear_trail')
    fx.label('spear_trail'); fx.emit('spray', POS, 2); fx.ret()
    fx.label('spear_render')
    fx.sprite(POS, sea, 300, cell=2, clut=1)
    lance(fx, 680, 200, tint, 0, blend=None); fx.ret()
    fx.label('spear_miss'); fx.emit('drop', POS, 5); fx.ret()
    fx.label('spear_arrive')
    fx.sound(11); fx.aim(); fx.vcopy(fx.AT, fx.TGT); fx.call('gout')
    fx.emit('ringout', fx.TGT); fx.emit('drop', fx.TGT, 12); fx.ret()
    # the spout: it shoots up, stands a moment and sinks
    gout = fx.pool('gout', 1)
    fx.begin('gout', gout, 'gout_render', inherit=False); fx.vcopy(POS, fx.AT); fx.ret()
    fx.label('gout_tick'); fx.life(10); fx.ret()
    fx.label('gout_render')
    fx.lin(fx.T3, FRAME, 260, 200); fx.br(FRAME, '<', 4, 'gout_draw')
    fx.set(fx.T3, 980); fx.br(FRAME, '<', 7, 'gout_draw'); fx.lin(fx.T3, FRAME, -230, 980 + 230 * 6)
    fx.label('gout_draw')
    fx.pillar(POS, 420, fx.T3, sea, cell=1, clut=1)
    fx.lin(fx.T2, fx.T3, 7, 0, 10); fx.pillar(POS, 260, fx.T2, tint, cell=1, clut=1); fx.ret()
    return fx


# ----------------------------------------------------------------- BlackKingNumemon
def royal_muck():
    """A great dark lump wearing a little gold crown is tossed in a lazy arc onto the spot where the target stands and
    lands with a splat: muck flies every way, a foul cloud rolls up, and the crown pops off and tumbles down after
    it. A target that left the spot is missed."""
    fx = Fx(delay=8, cast_sound=1)
    fx.palette(MUCK); fx.palette(GOLD); fx.palette(GLOOM)
    fx.paint(0, muck_lump()); fx.paint(1, crown()); fx.paint(2, splat(18)); fx.paint(3, splat(25))
    fx.paint(4, droplet()); fx.paint(5, puff(41)); fx.paint(6, star(4, 2, 9, 6))
    tint = fx.colour(128, 128, 128)
    flight = 14
    fx.particle('shine', 10, 6, 6, (128, 110, 50), (50, 90), grow=-8, spread=160, clut=1)
    fx.particle('spatter', 3, 8, 2, (128, 128, 128), 200, grow=70, blend=None, spin=8)
    fx.particle('spatter2', 2, 9, 3, (128, 128, 128), 150, grow=85, blend=None, spin=-8)
    fx.particle('blob', 20, 14, 4, (128, 128, 128), (70, 130), speed=70, lift=60, gravity=10, spread=60, blend=None)
    fx.particle('reek', 10, 15, 5, (100, 70, 128), 190, grow=28, flat=((-24, 24), (-32, -12), (-24, 24)), spread=180,
                clut=2, blend='half')
    fx.particle('lost', 1, 18, 1, (128, 128, 128), 190, flat=((18, 34), (-120, -100), (-10, 10)), gravity=14, spin=28,
                clut=1, blend=None)
    fx.label('main'); fx.when(0, 'toss'); fx.end(1)
    fx.label('toss')
    fx.vcopy(fx.AT, fx.CHEST); fx.sub_(at(fx.AT, 1), 180); fx.vcopy(fx.DEST, fx.TGT); fx.sub_(at(fx.DEST, 1), 90)
    fx.call('lump'); fx.sound(4); fx.ret()
    fx.travel('lump', 1, flight, 'lump_render', 'lump_land', every='lump_trail')
    arc_of(fx, 'lump', flight, 820)
    fx.label('lump_trail')
    fx.call('lump_arc'); fx.sub_(at(fx.TV, 1), 200); fx.emit('shine', fx.TV); fx.ret()
    fx.label('lump_render')
    # it wobbles as it flies: squashed and stretched in turn
    fx.call('lump_arc'); fx.lin(fx.T, FRAME, 700); fx.sin(fx.T3, fx.T, 50)
    fx.lin(fx.F1, fx.T3, 1, 420); fx.lin(fx.F2, fx.T3, -1, 420)
    fx.sprite(fx.TV, tint, fx.F1, fx.F2, cell=0, blend=None)
    fx.lin(fx.T, fx.F2, 1, 0, 2); fx.sub_(at(fx.TV, 1), fx.T); fx.sub_(at(fx.TV, 1), 40)
    fx.sprite(fx.TV, tint, 200, cell=1, clut=1, blend=None); fx.ret()
    fx.label('lump_land')
    fx.sound(40); fx.strike(POS, 220)
    fx.emit('spatter', POS, 2); fx.emit('spatter2', POS); fx.emit('blob', times=14); fx.emit('reek', times=6)
    fx.sub_(at(POS, 1), 120); fx.emit('lost', POS); fx.sound(34); fx.ret()
    return fx


# ----------------------------------------------------------------- Snimon
def twin_sickles():
    """Snimon's scythes cut the air twice: two green crescents peel away from its arms, sweep wide to either side and
    close on the target like shears, wherever it stands; the blow lands as they cross, in a white X and a scatter of
    cut wind."""
    fx = Fx(delay=8, cast_sound=19)
    fx.palette(MANTIS)
    fx.paint(0, sickle(0.0)); fx.paint(1, sickle(np.pi)); fx.paint(2, sickle(np.pi / 2, 8)); fx.paint(3, glow(15, 1.2))
    fx.paint(4, segment(3, 3, 29, 29, 3.4)); fx.paint(5, segment(29, 3, 3, 29, 3.4)); fx.paint(6, streak())
    fx.paint(7, star(4, 2, 9, 6))
    tint, pale = fx.colour(128, 128, 128), fx.colour(60, 128, 70)
    side = fx.const(0)
    flight, gap = 8, 3
    fx.particle('edge', 2, 4, 2, (128, 128, 128), 160, grow=60, fade=True, spin=30)
    fx.particle('wake', 20, 5, 3, (40, 128, 60), 240, grow=-36, fade=True)
    fx.particle('cross1', 1, 9, 4, (128, 128, 128), 340, grow=85, fade=True)
    fx.particle('cross2', 1, 9, 5, (128, 128, 128), 340, grow=85, fade=True)
    fx.particle('shred', 20, 11, 6, (110, 128, 110), (120, 220), grow=-12, speed=85, spread=80, spin=40)
    fx.particle('mote', 14, 12, 7, (110, 128, 100), (60, 100), grow=-6, speed=50, lift=30, gravity=5)
    fx.label('main'); fx.when(0, 'swing'); fx.when(gap, 'swing'); fx.end(gap + 1)
    fx.label('swing')
    fx.sound(13); fx.aim(); fx.vcopy(fx.AT, fx.CHEST); fx.vcopy(fx.DEST, fx.TCHEST)
    fx.emit('edge', fx.CHEST); fx.set(fx.SZ, side); fx.call('moon'); fx.add(side, 1); fx.ret()
    fx.travel('moon', 2, flight, 'moon_render', 'moon_arrive', fields=4, every='moon_trail')
    which, bow = iv(FREE + 12), iv(FREE + 16)
    fx.label('moon_place')                  # KEEP = where the crescent is: its straight flight bowed out to its side
    fx.lin(fx.T, FRAME, 2048 // flight); fx.sin(fx.T2, fx.T, 100)
    fx.vcopy(fx.KEEP, bow); fx.vmul(fx.KEEP, fx.T2); fx.vdiv(fx.KEEP, 100); fx.vadd(fx.KEEP, POS); fx.ret()
    fx.label('moon_trail')
    fx.br(FRAME, '!=', 1, 'moon_know')
    fx.set(which, fx.SZ); beside(fx, bow, POS, 420); fx.vsub(bow, POS)
    fx.br(which, '==', 0, 'moon_know'); fx.vmul(bow, -1)
    fx.label('moon_know'); fx.call('moon_place'); fx.emit('wake', fx.KEEP); fx.ret()
    fx.label('moon_render')
    fx.call('moon_place')
    fx.lin(fx.T3, FRAME, 30, 300)
    fx.sprite(fx.KEEP, pale, fx.T3, cell=3)
    fx.br(which, '!=', 0, 'moon_other')
    fx.sprite(fx.KEEP, tint, fx.T3, cell=0); fx.ret()
    fx.label('moon_other'); fx.sprite(fx.KEEP, tint, fx.T3, cell=1); fx.ret()
    fx.label('moon_arrive')
    fx.aim(); fx.vcopy(POS, fx.TCHEST); fx.emit('shred', POS, 6); fx.emit('mote', POS, 5)
    fx.br(which, '!=', 0, 'moon_second'); fx.sound(20); fx.emit('cross1', POS); fx.ret()
    fx.label('moon_second'); fx.sound(16); fx.hit(); fx.emit('cross2', POS); fx.emit('shred', POS, 6); fx.ret()
    return fx


EFFECTS = {122: darkness_gear, 198: rocking_stone, 214: clay_bomb, 224: trident_arm, 225: double_stars,
           227: angry_spike, 232: free_throw_bomb, 236: demi_dart, 245: trump_sword, 269: junk_chunker,
           286: royal_smasher, 291: tentacle_claw, 307: royal_muck, 328: twin_sickles}
