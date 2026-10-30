"""ShogunGekomon's partner animation set (slot -> clip), authored as per-tick poses.

TONO.MMD (type 119) is a seated giant frog: 28 bones on a skeleton no other model uses.
  1 hips   2 belly   3 chest   4 head (the mouth opens when the head tips back over the
  chest)   5 topknot   6 -> 7, 8 the two trumpets on its back   9 -> 10-13 arm (+x),
  14-17 arm (-x) and 18 the folding fan (scaled to almost nothing when it is put away)
  19 -> 20-23 leg (+x), 24-27 leg (-x), folded under the belly
Poses are offsets from the rest pose (slot 0, first tick) applied about each joint in
MODEL axes (partner_rig.layer): Y down, facing -Z. Measured with probe renders:
  belly/chest/head rx > 0 lean forward; head rx < 0 opens the mouth; topknot rx < 0
  leans back; trumpets rz +/- (7 +, 8 -) splay out; arm rx < 0 lifts it to the face,
  plus rz (-x arm +, +x arm -) opens it wide; leg rz (20 +, 24 -) splays the legs, rx > 0
  swings the feet down.
Eye frames (texture moves, the NPC animations' own rectangles): x 42 open, 36 half,
30 closed, 24 squeezed shut (the fan dance), 6x24 words to (10, 88).

Lengths and sound ticks follow Whamon (its previous form) for the everyday slots and the
techniques (Whamon has the same Ice techniques, timed to the same effects). Bank 4 is
the voice: ShogunGekomon gets Gekomon's (DIGIMON_VBALL_SOUND_ID), whose notes 53-55 are
the ones these animations use; bank 3 is the partner voice (Whamon's VLALL).
"""
import os as _partner_os
import sys as _partner_sys
_partner_repo_root = _partner_os.path.abspath(_partner_os.path.join(_partner_os.path.dirname(__file__), '../../../..'))
_partner_sys.path[:0] = [_partner_repo_root, _partner_os.path.join(_partner_repo_root, "tools")]
import math

from tools.models.partners import rig as partner_rig  # noqa: E402
from tools.models.partners.rig import smooth, bump, wave, clamp  # noqa: E402

TYPE = 119
NB = 28
FAN = 18
STEP = (1, 4)
THUD = (1, 3)
WHOOSH = (1, 15)
SPLASH = (1, 12)
VOICE = 4
EYES = {'open': 42, 'half': 36, 'closed': 30, 'squeeze': 24}


def eyes(state):
    return ('tex', dict(src=(EYES[state], 16), size=(6, 24), dst=(10, 88)))


def sound(bank, note):
    return ('sound', dict(bank=bank, note=note))


def keys(t, ks):
    if t <= ks[0][0]:
        return ks[0][1]
    for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
        if t <= t1:
            u = smooth((t - t0) / (t1 - t0)) if t1 > t0 else 1.0
            return v0 + (v1 - v0) * u
    return ks[-1][1]


def env(t, t_in, t_out, n):
    if t < t_in:
        return smooth(t / t_in) if t_in else 1.0
    if t > t_out:
        return 1.0 - smooth((t - t_out) / (n - t_out)) if n > t_out else 0.0
    return 1.0


class P:
    """Offsets from the rest pose: rot[bone] degrees (model axes), off[bone] units."""

    def __init__(self):
        self.rot = {}
        self.off = {}
        self.fan = 0.0

    def r(self, b, x=0.0, y=0.0, z=0.0):
        v = self.rot.setdefault(b, [0.0, 0.0, 0.0])
        v[0] += x
        v[1] += y
        v[2] += z
        return self

    def t(self, b, x=0.0, y=0.0, z=0.0):
        v = self.off.setdefault(b, [0.0, 0.0, 0.0])
        v[0] += x
        v[1] += y
        v[2] += z
        return self

    # ---- body parts
    def hop(self, h, fwd=0.0):
        return self.t(1, 0, -h, -fwd)

    def body(self, lean=0.0, side=0.0, twist=0.0):
        """The whole frog tips about its seat (belly)."""
        return self.r(2, lean, twist, side)

    def chest(self, lean=0.0, side=0.0, twist=0.0):
        return self.r(3, lean, twist, side)

    def head(self, nod=0.0, turn=0.0, tilt=0.0, mouth=0.0):
        """mouth 0..1 opens the jaw (the head tips back over the chest)."""
        return self.r(4, nod - 28 * mouth, turn, tilt)

    def knot(self, back=0.0, side=0.0):
        return self.r(5, -back, 0, side)

    def horns(self, spread=0.0, fwd=0.0, sway=0.0):
        self.r(7, fwd, 0, spread + sway)
        self.r(8, fwd, 0, -spread + sway)
        return self

    def arm(self, side, up=0.0, out=0.0, fore=0.0, hand=0.0, fwd=0.0):
        """side 'r' = +x arm (10-13), 'l' = -x arm (14-17). up lifts it towards the face,
        out opens it wide, fore bends the forearm up, fwd swings it forward."""
        a, b, c, d = (10, 11, 12, 13) if side == 'r' else (14, 15, 16, 17)
        s = -1 if side == 'r' else 1
        self.r(a, -up, s * fwd, s * out)
        self.r(b, -fore, 0, 0)
        self.r(d, -hand, 0, 0)
        return self

    def arms(self, **kw):
        self.arm('r', **kw)
        self.arm('l', **kw)
        return self

    def leg(self, side, splay=0.0, down=0.0, kick=0.0):
        """splay opens the folded leg sideways, down swings the foot down (a hop's push
        or landing), kick swings it forward."""
        a, b = (20, 22) if side == 'r' else (24, 26)
        s = 1 if side == 'r' else -1
        self.r(a, down, s * kick, s * splay)
        self.r(b, -0.4 * down, 0, 0)
        return self

    def legs(self, **kw):
        self.leg('r', **kw)
        self.leg('l', **kw)
        return self


class Clip:
    """n ticks; fn(t) -> P. loop: periodic (fn(n) == fn(0)), a closing sample is added.
    root(t) -> (x, y, z) accumulated root motion (forward is -z). step: keys every
    `step` ticks, linear in between (the engine interpolates linearly anyway)."""

    def __init__(self, n, fn, loop=False, root=None, events=(), loop_from=0, step=3):
        self.n, self.fn, self.loop, self.root, self.events = n, fn, loop, root, list(events)
        self.loop_from, self.step = loop_from, step


def build_samples(clip, rest):
    ts = list(range(clip.n)) + ([clip.n] if clip.loop else [])
    last = ts[-1]
    ks = sorted(set([0, last, clip.loop_from] + list(range(0, last + 1, clip.step))))
    at, prev = {}, None
    for k in ks:
        p = clip.fn(k)
        pose = partner_rig.layer(TYPE, rest, p.rot, p.off, prev)
        if p.fan:
            v = round(40 + (4096 - 40) * clamp(p.fan))
            pose[FAN][0:3] = [v, v, v]
        at[k] = pose
        prev = pose
    out = []
    for t in ts:
        if t in at:
            pose = [list(v) for v in at[t]]
        else:
            a = max(k for k in ks if k < t)
            b = min(k for k in ks if k > t)
            u = (t - a) / (b - a)
            pose = [[round(x + (y - x) * u) for x, y in zip(va, vb)] for va, vb in zip(at[a], at[b])]
        if clip.root:
            if clip.loop and t == clip.n:
                x = [a + (b - c) for a, b, c in zip(clip.root(clip.n - 1), clip.root(clip.loop_from + 1),
                                                     clip.root(clip.loop_from))]
            else:
                x = clip.root(t)
            pose[0][6:9] = [round(v) for v in x]
        else:
            pose[0][6:9] = [0, 0, 0]
        out.append(pose)
    ev = [(k, kind, dict(c)) for k, (kind, c) in clip.events if k < len(out)]
    return out, (clip.loop_from if clip.loop else None), ev


def linear_root(dist, n):
    return lambda t: (0.0, 0.0, -dist * (t + 1) / n)


# ---------------------------------------------------------------- shared poses
def breathe(t, period=40, amp=1.0, droop=0.0, p=None):
    p = p or P()
    b = wave(t, period)
    p.hop(-3 * amp * (1 + b) / 2 - droop * 8)
    p.body(lean=1.5 * amp * wave(t, period, 0.25) + droop * 10, side=1.2 * amp * wave(t, period * 2))
    p.chest(lean=1.2 * amp * b + droop * 5)
    p.head(nod=-1.5 * amp * b + droop * 14, tilt=2 * amp * wave(t, period * 2, 0.3))
    p.knot(back=3 * amp * wave(t, period, 0.4), side=4 * amp * wave(t, period * 2, 0.1))
    p.horns(spread=2.5 * amp * wave(t, period, 0.15) - droop * 6, fwd=droop * 8)
    p.arms(up=4 * amp * (1 + b) / 2 - droop * 6, fore=3 * amp * b)
    return p


def stance(t, period=16, tired=0.0):
    """Battle stance: up on its legs, leaning in, fists up, trumpets raised."""
    p = P()
    b = wave(t, period)
    p.hop(14 + 6 * b - tired * 12)
    p.legs(down=14 + 4 * b - tired * 10, splay=6)
    p.body(lean=10 + 2 * b + tired * 6, side=1.5 * wave(t, period, 0.25))
    p.chest(lean=3 * b)
    p.head(nod=-6 + 3 * b + tired * 12, mouth=tired * 0.4 * (1 + wave(t, period / 2)) / 2)
    p.horns(spread=10 - tired * 8, fwd=-6 + tired * 10, sway=2 * wave(t, period, 0.3))
    p.arms(up=45 - tired * 30 + 6 * b, out=20 - tired * 10, fore=30 - tired * 15)
    p.knot(back=4 * wave(t, period, 0.4))
    return p


def hop_cycle(t, period, height, dist_lean, arm_amp, droop=0.0):
    """One hop per cycle: crouch, push off with both legs, fly, land with a squash."""
    u = (t % period) / period
    p = P()
    # phases: 0-0.2 crouch, 0.2-0.7 air, 0.7-1 land/squash
    air = bump((u - 0.2) / 0.5)
    crouch = bump(u / 0.2) * 0.6 + bump((u - 0.7) / 0.3)
    p.hop(height * air - 10 * crouch)
    p.legs(down=35 * air - 6 * crouch, splay=-6 * air + 4 * crouch, kick=10 * air)
    p.body(lean=dist_lean + 6 * crouch - 6 * air + droop * 8)
    p.chest(lean=-4 * air + 3 * crouch)
    p.head(nod=-5 * air + 6 * crouch + droop * 12, mouth=0.25 * air * (1 - droop))
    p.knot(back=10 * air - 6 * crouch)
    p.horns(spread=4 * air - 3 * crouch, fwd=-8 * air + 6 * crouch)
    p.arms(up=arm_amp * air - droop * 8, out=arm_amp * 0.6 * air, fore=10 + 10 * air)
    return p


def blend(t, t0, t1, fa, fb):
    u = smooth((t - t0) / (t1 - t0)) if t1 > t0 else 1.0
    pa, pb = fa(t), fb(t)
    p = P()
    for b in set(pa.rot) | set(pb.rot):
        va, vb = pa.rot.get(b, [0, 0, 0]), pb.rot.get(b, [0, 0, 0])
        p.rot[b] = [x + (y - x) * u for x, y in zip(va, vb)]
    for b in set(pa.off) | set(pb.off):
        va, vb = pa.off.get(b, [0, 0, 0]), pb.off.get(b, [0, 0, 0])
        p.off[b] = [x + (y - x) * u for x, y in zip(va, vb)]
    p.fan = pa.fan + (pb.fan - pa.fan) * u
    return p


def face(e='open', at=0):
    return [(at, eyes(e))]


BLINK = [(26, eyes('half')), (27, eyes('closed')), (29, eyes('half')), (30, eyes('open'))]


# ---------------------------------------------------------------- the set
def build_all():
    C = {}

    # ---- locomotion (the NPC idle, slot 0, is kept as it is)
    C[1] = Clip(48, lambda t: breathe(t, 48, 0.7, 1.0), loop=True,
                events=face('half') + [(30, eyes('closed')), (34, eyes('half'))])
    walk = Clip(20, lambda t: hop_cycle(t, 20, 70, 6, 25), loop=True, root=linear_root(330, 20),
                events=face() + [(4, sound(*STEP)), (15, sound(*THUD))])
    run = Clip(16, lambda t: hop_cycle(t, 16, 120, 12, 45), loop=True, root=linear_root(600, 16), step=2,
               events=face() + [(3, sound(*STEP)), (12, sound(*THUD))])
    C[2], C[4] = walk, run
    C[3] = Clip(24, lambda t: hop_cycle(t, 24, 35, 4, 8, droop=1.0), loop=True, root=linear_root(250, 24),
                events=face('half') + [(5, sound(*STEP)), (18, sound(*THUD))])
    C[0x1B], C[0x23], C[0x24] = run, walk, run

    # ---- care and moods (5 happy, 7 unhappy and 0xB joy are the NPC's own)
    def eat(t):
        p = P()
        e = env(t, 8, 34, 43)
        chew = sum(bump((t - c) / 6) for c in (12, 20, 28))
        p.body(lean=14 * e + 3 * chew)
        p.chest(lean=4 * e)
        p.head(nod=8 * e, mouth=0.9 * chew)
        p.arms(up=55 * e - 15 * chew, out=-10 * e, fore=35 * e)
        p.horns(spread=-4 * e)
        p.hop(-6 * e)
        return p
    C[8] = Clip(43, eat, events=face() + [(12, sound(1, 1)), (20, sound(1, 1)), (28, sound(1, 1)),
                                          (14, eyes('closed')), (32, eyes('open'))])

    def fall_asleep(t):
        e = smooth(t / 30)
        p = breathe(t, 40, 1 - e, 1.5 * e)
        p.head(nod=10 * e)
        p.knot(back=4 * e)
        return p
    C[9] = Clip(41, fall_asleep, events=face('half') + [(16, eyes('closed')), (8, sound(3, 48))])

    def poop(t):
        p = P()
        e = env(t, 6, 30, 39)
        strain = 3.0 * wave(t, 4) * (1 if 8 <= t <= 28 else 0)
        p.hop(-10 * e)
        p.legs(splay=12 * e)
        p.body(lean=6 * e, side=strain)
        p.head(nod=6 * e, tilt=strain * 1.5)
        p.arms(up=25 * e, fore=30 * e)
        p.horns(spread=-6 * e + strain)
        if t >= 32:
            p.hop(14 * bump((t - 32) / 7))
        return p
    C[0xA] = Clip(39, poop, events=face('squeeze') + [(18, sound(1, 8)), (32, eyes('open'))])

    def power(t):
        p = P()
        e = env(t, 6, 22, 31)
        p.hop(20 * e)
        p.legs(down=18 * e)
        p.body(lean=-8 * e)
        p.chest(lean=-4 * e)
        p.head(mouth=0.9 * e)
        p.horns(spread=16 * e, fwd=-10 * e)
        p.arms(up=80 * e, out=35 * e, fore=20 * e)
        p.knot(back=12 * e)
        return p
    C[0xC] = Clip(31, power, events=face('squeeze') + [(11, sound(3, 50)), (24, eyes('open'))])

    def refuse(t):
        p = P()
        e = env(t, 4, 26, 33)
        p.head(turn=24 * wave(t, 8) * e, tilt=4 * wave(t, 8, 0.25) * e)
        p.chest(twist=8 * wave(t, 8, 0.1) * e)
        p.arm('r', up=50 * e, out=10 * e, fore=30 * e, hand=20 * wave(t, 4) * e)
        p.arm('l', up=10 * e)
        p.knot(side=8 * wave(t, 8, 0.2) * e)
        return p
    C[0xD] = Clip(33, refuse, events=face('half') + [(16, sound(3, 51)), (30, eyes('open'))])

    def sick(t):
        p = breathe(t, 21, 0.6, 1.2)
        tr = 1.5 * wave(t, 3)
        p.body(side=tr)
        p.head(tilt=tr * 1.5)
        return p
    C[0xE] = Clip(21, sick, loop=True, events=face('half') + [(12, eyes('closed')), (15, eyes('half'))])

    def hungry(t):
        p = breathe(t, 21, 0.5, 0.4)
        r = wave(t, 10.5)
        p.arms(up=20, out=-25, fore=30 + 10 * r)
        p.head(mouth=0.35 * (1 + wave(t, 10.5)) / 2)
        return p
    C[0xF] = Clip(21, hungry, loop=True, events=face('half'))

    def needs_poop(t):
        p = breathe(t, 21, 0.4)
        p.body(side=4 * wave(t, 21))
        p.head(tilt=-5 * wave(t, 21))
        k = 'r' if (t % 21) < 10.5 else 'l'
        p.leg(k, splay=10 * bump((t % 10.5) / 10.5))
        p.hop(3 * bump((t % 10.5) / 10.5))
        return p
    C[0x10] = Clip(21, needs_poop, loop=True, events=face('squeeze'))

    def sleepy(t):
        u = t / 42
        nod = smooth(u / 0.75) if u < 0.75 else 1 - smooth((u - 0.75) / 0.125) if u < 0.875 else 0.0
        p = breathe(t, 42, 0.4, 0.8)
        p.head(nod=14 * nod)
        p.body(lean=5 * nod)
        return p
    C[0x11] = Clip(42, sleepy, loop=True, events=face('half') + [(18, eyes('closed')), (34, eyes('half'))])

    def tired(t):
        p = breathe(t, 21, 0.4, 1.0)
        b = wave(t, 10.5)
        p.hop(2 * b)
        p.head(mouth=0.35 * (1 + b) / 2)
        p.body(lean=2 * b)
        return p
    C[0x12] = Clip(21, tired, loop=True, events=face('half'))

    def sulk(t):
        e = smooth(t / 8)
        huff = bump(((t - 8) % 16) / 16) if t >= 8 else 0
        p = P()
        p.chest(twist=-20 * e)
        p.head(turn=-25 * e, nod=-4 * e + 3 * huff, tilt=4 * e)
        p.body(twist=-8 * e)
        p.arms(up=35 * e, out=-20 * e, fore=40 * e)
        p.knot(side=-6 * e)
        p.hop(2 * huff)
        return p
    C[0x13] = Clip(24, sulk, loop=True, loop_from=8, events=face('half') + [(8, sound(3, 52))])

    # ---- scripted reactions
    def startled(t):
        p = P()
        h = 70 * bump((t - 1) / 12)
        p.hop(h)
        p.legs(down=30 * bump((t - 1) / 12))
        e = env(t, 3, 14, 25)
        p.body(lean=-10 * e)
        p.head(mouth=0.8 * e)
        p.arms(up=60 * e, out=30 * e)
        p.horns(spread=18 * e)
        p.knot(back=14 * e)
        return p
    C[0x15] = Clip(25, startled, root=lambda t: (0, 0, 80 * smooth((t - 1) / 12)),
                   events=face('open') + [(13, sound(*THUD))])

    def think(t):
        p = breathe(t, 21, 0.3)
        e = env(t, 5, 16, 21)
        p.head(tilt=-10 * e, nod=-6 * e)
        p.arm('r', up=70 * e, fore=50 * e, hand=15 * wave(t, 5) * e)
        p.knot(side=-8 * e)
        return p
    C[0x16] = Clip(21, think, events=face('half') + [(14, eyes('open'))])

    def look_around(t):
        e = smooth(t / 12)
        p = breathe(t, 17, 0.3)
        tw = 22 * math.sin(2 * math.pi * (t - 12) / 17) if t >= 12 else 0
        p.head(turn=tw * e)
        p.chest(twist=0.4 * tw * e)
        return p
    C[0x17] = Clip(29, look_around, loop=True, loop_from=12, events=face())

    def look(nod):
        def f(t):
            e = smooth(t / 10)
            p = P()
            p.head(nod=nod * e)
            p.chest(lean=nod * 0.4 * e)
            p.knot(back=-nod * 0.4 * e)
            return p
        return f
    C[0x18] = Clip(12, look(-16), loop=True, loop_from=10, events=face('open'))
    C[0x19] = Clip(12, look(16), loop=True, loop_from=10, events=face('half'))

    # ---- battle
    C[0x21] = Clip(16, stance, loop=True, events=face())
    C[0x22] = Clip(16, lambda t: stance(t, 16, 1.0), loop=True, events=face('half'))

    def block(t):
        e = smooth((t + 1) / 4)
        p = stance(0)
        p.arms(up=25 * e, out=-30 * e, fore=50 * e)
        p.head(nod=10 * e)
        p.body(lean=-6 * e)
        return p
    C[0x25] = Clip(10, block, events=face('squeeze'), step=1)

    def hit(direction):
        def f(t):
            p = P()
            k = smooth(t / 3) if t < 3 else max(0.0, 1 - smooth((t - 3) / 26))
            p.body(lean=-direction * 22 * k, side=4 * k * wave(t, 6))
            p.head(nod=-direction * 12 * k, mouth=0.7 * k)
            p.arms(up=40 * k, out=35 * k)
            p.horns(spread=14 * k * (1 + 0.3 * wave(t, 5)))
            p.knot(back=direction * 16 * k)
            p.hop(25 * bump(t / 10))
            return p
        return f
    C[0x28] = Clip(41, hit(1), step=2, root=lambda t: (0, 0, 220 * smooth(t / 12)),
                   events=face('squeeze') + [(8, sound(*THUD)), (22, eyes('half')), (34, eyes('open'))])
    C[0x29] = Clip(41, hit(-1), step=2, root=lambda t: (0, 0, -220 * smooth(t / 12)),
                   events=face('squeeze') + [(8, sound(*THUD)), (22, eyes('half')), (34, eyes('open'))])

    def fainted(e):
        p = P()
        p.r(1, -72 * e, 0, 0)          # tips over onto its back, the round belly up
        p.t(1, 0, -45 * e, 60 * e)
        p.head(mouth=0.6 * e)
        p.arms(up=30 * e, out=40 * e)
        p.legs(splay=20 * e, kick=20 * e)
        p.horns(spread=-10 * e)
        return p

    def faint(t):
        e = (t / 13) ** 2 if t < 13 else 1.0 - 0.06 * bump((t - 13) / 6)
        p = fainted(min(1.0, e))
        if t < 5:
            p.arms(up=30 * bump(t / 5))
        return p
    C[0x2B] = Clip(25, faint, events=face('half') + [(13, sound(*THUD)), (13, eyes('closed'))])

    def get_up(t):
        e = 1.0 - smooth((t - 3) / 15)
        p = fainted(e)
        p.hop(25 * bump((t - 14) / 10))
        return p
    C[0x2C] = Clip(25, get_up, events=face('closed') + [(6, eyes('half')), (14, eyes('open')), (22, sound(*THUD))])

    # ---- techniques (0x2E + index in DIGIMON_DATA[119].moves; timing from Whamon's)
    def spit(n, release, hold=4, rise=0.0):
        """Draw a breath (chest out, head back), spit from the mouth at `release`."""
        def f(t):
            p = stance(0)
            draw = keys(t, [(0, 0.0), (release - 4, 1.0), (release, -1.0), (release + hold, -1.0), (n - 1, 0.0)])
            d, s = max(draw, 0.0), max(-draw, 0.0)
            p.body(lean=-8 * d + 14 * s)
            p.chest(lean=-6 * d + 8 * s)
            p.head(nod=-6 * d + 8 * s, mouth=0.5 * d + 1.0 * s)
            p.arms(up=-15 * d + 25 * s, out=30 * d - 10 * s, fwd=20 * s)
            p.horns(spread=8 * d, fwd=-6 * d)
            p.hop(rise * d + 10 * s)
            return p
        return f

    def trumpet(n, blows, length=8):
        """Blow its trumpets: lean back, trumpets swing forward over the shoulders."""
        def f(t):
            p = stance(0)
            k = max([bump((t - b + 3) / (length + 6)) for b in blows] + [0.0])
            e = env(t, 6, n - 8, n)
            p.body(lean=-10 * k)
            p.horns(fwd=30 * k, spread=-6 * k, sway=3 * wave(t, 3) * k)
            p.head(nod=-8 * k, mouth=0.8 * k)
            p.knot(back=10 * k)
            p.arms(up=40 * e + 20 * k, out=30 * e, fore=30 * e)
            p.hop(8 * k * (1 + wave(t, 2)) / 2)
            return p
        return f

    C[0x2E] = Clip(21, spit(21, 10), step=2, events=face() + [(10, sound(VOICE, 54)), (10, eyes('squeeze')),
                                                             (16, eyes('open'))])          # Tear Drop
    C[0x2F] = Clip(41, spit(41, 20, 8, 10), step=2, events=face() + [(20, sound(VOICE, 55)),
                                                                     (20, eyes('squeeze')), (30, eyes('open'))])  # Giga Freeze
    C[0x30] = Clip(31, spit(31, 20, 6), step=2, events=face() + [(20, sound(VOICE, 55)), (20, sound(*SPLASH))])  # Water Blit
    C[0x31] = Clip(51, trumpet(51, (10, 35), 10), step=2,
                   events=face() + [(10, sound(VOICE, 54)), (35, sound(VOICE, 54)), (10, eyes('squeeze')),
                                    (22, eyes('open')), (35, eyes('squeeze')), (46, eyes('open'))])  # Winter Blast
    C[0x32] = Clip(23, spit(23, 10, 3), step=2, events=face() + [(10, sound(VOICE, 54))])          # Ice Needle

    def ice_statue(t):
        p = stance(0)
        # slams both hands together over its head at 16
        w = keys(t, [(0, 0.0), (12, 1.0), (16, -1.0), (24, -1.0), (36, 0.0)])
        u, s = max(w, 0.0), max(-w, 0.0)
        p.arms(up=60 + 40 * u + 10 * s, out=50 * u - 20 * s, fore=20)
        p.body(lean=-8 * u + 12 * s)
        p.head(nod=-8 * u + 6 * s, mouth=0.6 * u)
        p.hop(25 * u - 6 * s)
        p.legs(down=20 * u)
        return p
    C[0x33] = Clip(37, ice_statue, step=2, events=face() + [(16, sound(VOICE, 55)), (16, sound(*WHOOSH)),
                                                           (16, eyes('squeeze')), (28, eyes('open'))])

    C[0x34] = Clip(63, trumpet(63, (4, 30, 44), 12), step=3,
                   events=face() + [(4, sound(VOICE, 54)), (30, sound(VOICE, 54)), (30, eyes('squeeze')),
                                    (54, eyes('open'))])                                          # Aurora Freeze

    def aqua_magic(t):
        p = P()
        e = env(t, 8, 44, 55)
        p.fan = env(t, 6, 46, 52)
        sway = wave(t, 16)
        p.body(side=6 * sway * e, lean=-4 * e)
        p.head(tilt=-8 * sway * e, mouth=0.5 * e)
        p.arm('l', up=70 * e, out=40 * e + 15 * sway * e, fore=25 * e, hand=20 * wave(t, 8) * e)
        p.arm('r', up=40 * e, out=20 * e, fore=30 * e)
        p.horns(sway=6 * sway * e)
        p.hop(10 * e * (1 + wave(t, 8)) / 2)
        return p
    C[0x35] = Clip(55, aqua_magic, step=3, events=face('squeeze') + [(12, sound(VOICE, 55)), (8, sound(*WHOOSH)),
                                                                     (24, sound(*WHOOSH)), (48, eyes('open'))])

    def blasting_spout(t):
        """Finisher: a huge breath, then both trumpets blast the water spout forward."""
        p = stance(0)
        draw = keys(t, [(0, 0.0), (10, 1.0), (14, -1.0), (30, -1.0), (40, 0.0)])
        d, s = max(draw, 0.0), max(-draw, 0.0)
        p.hop(30 * d + 10 * s * (1 + wave(t, 2)) / 2)
        p.legs(down=20 * d + 10 * s)
        p.body(lean=-14 * d + 10 * s)
        p.chest(lean=-6 * d)
        p.head(nod=-10 * d + 8 * s, mouth=0.7 * d + 0.4 * s)
        p.horns(fwd=-12 * d + 40 * s, spread=10 * d - 4 * s, sway=3 * wave(t, 2) * s)
        p.arms(up=50 + 20 * d, out=40 * d + 20 * s, fore=20)
        p.knot(back=14 * d - 6 * s)
        return p
    C[0x36] = Clip(41, blasting_spout, step=2, events=face() + [(10, sound(VOICE, 54)), (14, sound(VOICE, 55)),
                                                               (10, eyes('squeeze')), (32, eyes('open'))])
    return C
