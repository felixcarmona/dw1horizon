"""Cherrymon's partner animation set (slot -> Clip). See clips.py for the conventions.

Slot meanings come from the code that starts them (partner.c, partner_impl.c, evl.c,
btl/battle_main.c, trn/*) and from what the 64 partner models do in them; lengths and
the ticks of sounds follow Vegiemon (the previous form) and, for the techniques,
Piximon (same eight Earth techniques in the same order, and Bit Bomb), whose
animations are timed to the same effects.
"""
import math
import os
import sys

from clips import (Clip, Pose, NB, face, eyes, mouth, sound, keys, wave, bump, smooth, linear_root,
                   REQUIRED_SLOTS, ROOTS)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT_DIR, 'tools'))
import mmd  # noqa: E402
import retarget  # noqa: E402

STEP = (1, 4)            # Vegiemon's footstep
THUD = (1, 3)            # heavy landing / fall
WHOOSH = (1, 15)         # swing
VOICE = 4                # bank 4 = the Digimon's own voice (VBALL 0x17, Vegiemon's)
VEGI = 25
VEGI_MMD = os.path.join(ROOT_DIR, 'extracted/CHDAT/MMD0/VEGI.MMD')


# ---------------------------------------------------------------- shared poses
def idle_pose(t, period=40, amp=1.0, droop=0.0, p=None):
    """Breathing sway: trunk and canopy rock slowly, the four arms drift out of phase.
    droop 0..1 sags everything (tired, sick, sleepy)."""
    p = p or Pose()
    p.hop(2.5 * amp * (1 + wave(t, period / 2)) / 2 - droop * 6)
    p.body(lean=1.5 * amp * wave(t, period, 0.25) + droop * 7, side=2.0 * amp * wave(t, period))
    p.canopy(lean=1.5 * amp * wave(t, period, 0.1) + droop * 5, side=2.5 * amp * wave(t, period, 0.12))
    for k, name in enumerate(('fl', 'fr', 'ul', 'ur')):
        ph = k * 0.25
        p.arm(name, raise_=4 * amp * wave(t, period, ph) - droop * 16, fwd=5 * amp * wave(t, period, ph + 0.3),
              elbow=5 * amp * wave(t, period, ph + 0.15) - droop * 12, wrist=6 * amp * wave(t, period, ph + 0.4))
    if droop:
        settle_roots(p, -droop * 6)
    return p


def settle_roots(p, h):
    """The hips went down by h (h < 0: lower): splay the roots so their tips stay on the
    ground (about 1 degree per 2 units)."""
    for name in ROOTS:
        p.root(name, lift=h * 0.5, tip=-h * 0.3)


def crouch(p, h):
    p.hop(-h)
    settle_roots(p, -h)
    return p


def stance(t, period=16, tired=0.0):
    """Battle stance: low, leaning in, claws up and forward, upper arms spread wide."""
    p = Pose()
    b = wave(t, period)
    crouch(p, 10 + 4 * b + tired * 6)
    p.body(lean=7 + 2 * b + tired * 6, side=1.5 * wave(t, period, 0.25))
    p.canopy(lean=-2 * wave(t, period, 0.15) + tired * 4, side=2 * wave(t, period, 0.35))
    for name, s in (('fl', 1), ('fr', -1)):
        p.arm(name, raise_=22 - tired * 20 + 4 * b, fwd=38 - tired * 15, elbow=28 - tired * 15 + 6 * wave(t, period, 0.2 * s),
              wrist=20 + 6 * wave(t, period, 0.3 * s))
    for name in ('ul', 'ur'):
        p.arm(name, raise_=34 - tired * 25 + 5 * b, fwd=10, elbow=18 - tired * 10, wrist=10)
    return p


def hop_cycle(t, period, height, lean, arm_amp, root_amp, waddle, droop=0.0):
    """One step = one hop: the tree springs up on its roots and lands; two steps per
    cycle, alternating the side it waddles to and the diagonal pair of roots that kicks."""
    half = period / 2
    u = (t % half) / half
    side = 1 if (t % period) < half else -1
    p = Pose()
    p.hop(height * bump(u))
    p.body(lean=lean + 4 * math.cos(2 * math.pi * u) + droop * 6, side=waddle * side * bump(u),
           twist=3 * side * bump(u))
    p.canopy(lean=-3 * math.sin(2 * math.pi * u) + droop * 4, side=waddle * 1.3 * side * bump((u + 0.85) % 1))
    sw = wave(t, period)
    p.arm('fl', raise_=6 - droop * 14, fwd=arm_amp * sw, elbow=8 - droop * 10, wrist=6)
    p.arm('fr', raise_=6 - droop * 14, fwd=-arm_amp * sw, elbow=8 - droop * 10, wrist=6)
    p.arm('ul', raise_=10 - droop * 16, fwd=-arm_amp * 0.7 * sw, elbow=6)
    p.arm('ur', raise_=10 - droop * 16, fwd=arm_amp * 0.7 * sw, elbow=6)
    lead = ('fl', 'br') if side > 0 else ('fr', 'bl')
    for name in ('fl', 'fr', 'bl', 'br'):
        f = 1 if name in lead else -1
        p.root(name, lift=root_amp * 0.6 * bump(u), fwd=f * root_amp * math.cos(math.pi * u),
               tip=root_amp * 0.5 * bump(u))
    return p


def blend(t, t0, t1, a, b):
    """Pose a before t0, b after t1, smooth in between (both callables of t)."""
    u = smooth((t - t0) / (t1 - t0)) if t1 > t0 else 1.0
    pa, pb = a(t), b(t)
    p = Pose()
    for i in range(NB):
        p.rot[i] = [x + (y - x) * u for x, y in zip(pa.rot[i], pb.rot[i])]
        p.off[i] = [x + (y - x) * u for x, y in zip(pa.off[i], pb.off[i])]
    fa, fb = getattr(pa, 'follow', (0, 0, 0)), getattr(pb, 'follow', (0, 0, 0))
    p.follow = tuple(x + (y - x) * u for x, y in zip(fa, fb))
    for b_, v in pa.abs.items():
        w = pb.abs.get(b_)
        p.abs[b_] = v if w is None else tuple(x + (y - x) * u for x, y in zip(v, w))
    for b_, v in pb.abs.items():
        p.abs.setdefault(b_, v)
    return p


def rest(t=0):
    return Pose()


def env(t, t_in, t_out, n):
    """0 -> 1 over [0, t_in], 1 until t_out, -> 0 at n."""
    if t < t_in:
        return smooth(t / t_in) if t_in else 1.0
    if t > t_out:
        return 1.0 - smooth((t - t_out) / (n - t_out)) if n > t_out else 0.0
    return 1.0


# ---------------------------------------------------------------- retargeted techniques
_VEGI = None


def vegi():
    global _VEGI
    if _VEGI is None:
        _VEGI = mmd.MMD.load(VEGI_MMD)
    return _VEGI


def vine_clip(rig, src_slot, events_extra=(), trunk_w=0.3, upper_w=0.55, hips_k=1.2, canopy_amp=1.0,
              extra=None, mouth_open_at=60):
    """A Vegiemon technique carried onto Cherrymon (tools/retarget.py): each vine's
    sweep drives a front arm (chords of two vine pieces per arm piece, the tip piece's
    rotation for the claw) and, damped, the upper arm on the same side; the trunk takes
    a fraction of Vegiemon's body motion, the hips its bounce. Layered on top: the
    canopy lagging the trunk, the roots planted, the mouth texture opening while
    Vegiemon's jaw is open (bone 6 more than `mouth_open_at` units from its rest)."""
    m = vegi()
    # the forearm and claw are damped (0.8, 0.7): Vegiemon's vines curl in front of its
    # mouth, and at full strength Cherrymon's claws would cross its face
    bone_map = {
        9: ((8, 10), 1.0), 10: ((10, 12), 0.8), 11: (12, 0.7),            # vine A (+x) -> front arm +x
        6: ((14, 16), 1.0), 7: ((16, 18), 0.8), 8: (18, 0.7),             # vine B (-x) -> front arm -x
        15: ((8, 10), upper_w), 16: ((10, 12), upper_w), 17: (12, upper_w),
        12: ((14, 16), upper_w), 13: ((16, 18), upper_w), 14: (18, upper_w),
        2: (3, trunk_w),
    }
    rest_list = rig.pose_list(Pose())
    r = retarget.transfer(m, VEGI, src_slot, 121, rest_list, bone_map, hips=(1, 1, hips_k))
    n = r['n']
    smp, _, ev = retarget.play(m.anims.anims[m.anims.table[src_slot]], 20, src_slot)
    ref = retarget.rest_pose(m, 20, 0)
    jaw = [abs(s[6][3] - ref[6][3]) for s in smp]
    trunk = r['rot'][2]

    def fn(t):
        p = Pose()
        for b, seq in r['rot'].items():
            if b != 2:
                p.abs[b] = seq[t]
        # trunk: keep it as a lean the arms' shoulders ride on
        lean, twist, side = (x * 360 / 4096 for x in trunk[t])
        p.body(lean=lean, side=side, twist=twist)
        p.t(1, *r['hips'][t])
        lag = trunk[max(0, t - 2)]
        p.canopy(lean=canopy_amp * 0.6 * lag[0] * 360 / 4096, side=canopy_amp * 0.6 * lag[2] * 360 / 4096)
        if extra:
            extra(p, t)
        return p

    events = face('narrow')
    state = False
    for t in range(n):
        o = jaw[t] > mouth_open_at
        if o != state:
            events.append((t, mouth('open' if o else 'closed')))
            state = o
    if state:
        events.append((n - 1, mouth('closed')))
    events += [(k, ('sound', dict(bank=c['bank'], note=c['note']))) for k, kind, c in ev if kind == 'sound']
    events += list(events_extra)
    events.append((n - 1, eyes('open')))
    return Clip(rig, n, fn, events=events)


# ---------------------------------------------------------------- the set
def build_all(rig):
    C = {}

    def clip(n, fn, **kw):
        return Clip(rig, n, fn, **kw)

    blink = [(26, eyes('half')), (27, eyes('closed')), (29, eyes('half')), (30, eyes('open'))]

    # ---- locomotion
    C[0] = clip(40, lambda t: idle_pose(t), loop=True, events=face() + blink)
    C[1] = clip(48, lambda t: idle_pose(t, 48, 0.8, 1.0), loop=True,
                events=face('half') + [(30, eyes('closed')), (34, eyes('half'))])
    walk = clip(16, lambda t: hop_cycle(t, 16, 42, 6, 22, 24, 4), loop=True, root=linear_root(350, 16),
                events=face() + [(0, sound(*STEP)), (8, sound(*STEP))])
    run = clip(16, lambda t: hop_cycle(t, 16, 75, 13, 34, 36, 6), loop=True, root=linear_root(700, 16),
               events=face('narrow') + [(0, sound(*STEP)), (8, sound(*STEP))])
    C[2], C[4] = walk, run
    C[3] = clip(16, lambda t: hop_cycle(t, 16, 22, 8, 12, 14, 3, droop=1.0), loop=True, root=linear_root(300, 16),
                events=face('half') + [(0, sound(*STEP)), (8, sound(*STEP))])
    # training run (0x1B) and the battle walk/run (0x23/0x24, the engine drops their X root
    # motion) share the walk and the run: memory is tight (PARTNER_MODEL_BUFFER)
    C[0x1B], C[0x23], C[0x24] = walk, walk, run

    # ---- moods and care
    def happy(t):
        p = Pose()
        h = 75 * (bump((t - 4) / 11) + bump((t - 19) / 11))
        p.hop(h)
        e = env(t, 5, 32, 41)
        p.body(lean=-6 * e, side=5 * wave(t, 10) * e)
        p.canopy(side=7 * wave(t, 6) * e, lean=-4 * e)
        for name, ph in (('fl', 0), ('fr', 0.5), ('ul', 0.25), ('ur', 0.75)):
            up = 55 if name in ('ul', 'ur') else 45
            p.arm(name, raise_=up * e, fwd=18 * wave(t, 10, ph) * e, elbow=-10 * e + 15 * wave(t, 10, ph) * e,
                  wrist=20 * e)
        for name in ROOTS:
            p.root(name, lift=10 * (bump((t - 4) / 11) + bump((t - 19) / 11)))
        return p
    C[5] = clip(41, happy, events=face('open', 'open') + [(36, mouth('closed')), (8, sound(VOICE, 53)),
                                                           (15, sound(*STEP)), (30, sound(*STEP))])

    def unhappy(t):
        p = Pose()
        e = env(t, 6, 42, 51)
        p.body(lean=8 * e, twist=20 * wave(t, 10) * e, side=5 * wave(t, 5) * e)
        p.canopy(twist=-8 * wave(t, 10, 0.1) * e, side=5 * wave(t, 5, 0.2) * e, lean=3 * e)
        stomp = ('fl', 'fr')[int(t / 5) % 2]
        for name in ROOTS:
            p.root(name, lift=(24 * bump((t % 5) / 5) * e) if name == stomp else 0)
        for name, s in (('fl', 1), ('fr', -1)):
            p.arm(name, raise_=-12 * e + 15 * wave(t, 5, 0.5 * (s > 0)) * e, fwd=25 * e, elbow=-15 * e)
        for name in ('ul', 'ur'):
            p.arm(name, raise_=-15 * e, elbow=-10 * e)
        return p
    C[7] = clip(51, unhappy, events=face('narrow') + [(k, sound(3, 50)) for k in (10, 20, 30, 40)] +
                [(10, mouth('open')), (13, mouth('closed')), (30, mouth('open')), (33, mouth('closed')),
                 (50, eyes('open'))])

    def eat(t):
        p = Pose()
        e = env(t, 7, 33, 41)
        chew = sum(bump((t - c) / 6) for c in (11, 19, 27))
        p.body(lean=20 * e + 4 * chew, side=0)
        p.canopy(lean=6 * e + 3 * chew)
        for name in ('fl', 'fr'):
            p.arm(name, raise_=-8 * e, fwd=55 * e, elbow=35 * e + 10 * chew, wrist=25 * e, elbow_fwd=25 * e)
        for name in ('ul', 'ur'):
            p.arm(name, raise_=-6 * e, fwd=15 * e)
        crouch(p, 8 * e)
        return p
    C[8] = clip(41, eat, events=face() + [(11, mouth('open')), (14, mouth('closed')), (19, mouth('open')),
                                           (22, mouth('closed')), (27, mouth('open')), (30, mouth('closed')),
                                           (14, sound(1, 1)), (22, sound(1, 1)), (30, sound(1, 1)),
                                           (12, eyes('closed')), (32, eyes('open'))])

    def fall_asleep(t):
        e = smooth(t / 28)
        p = idle_pose(t, 40, 1 - e, 1.4 * e)
        crouch(p, 26 * e)
        p.body(lean=6 * e)
        return p
    C[9] = clip(41, fall_asleep, events=face('half') + [(16, eyes('closed')), (20, sound(VOICE, 54))])

    def poop(t):
        p = Pose()
        e = env(t, 6, 34, 40)
        crouch(p, 34 * e)
        strain = 3.5 * wave(t, 4) * (1 if 8 <= t <= 32 else 0)
        p.body(lean=7 * e, side=strain)
        p.canopy(side=strain * 1.6, lean=4 * e)
        for name in ('fl', 'fr', 'ul', 'ur'):
            p.arm(name, raise_=-10 * e, elbow=25 * e, wrist=15 * e)
        if t >= 36:
            p.hop(18 * bump((t - 36) / 10))
            p.canopy(side=5 * wave(t, 4))
        return p
    C[0xA] = clip(51, poop, events=face('closed') + [(5, sound(3, 48)), (36, sound(1, 7)), (36, eyes('open')),
                                                      (38, mouth('open')), (46, mouth('closed'))])

    def joy(t):
        p = Pose()
        e = env(t, 12, 36, 51)
        p.body(lean=-9 * e)
        p.canopy(lean=-5 * e, side=6 * wave(t, 8) * env(t, 20, 36, 51))
        for name in ('fl', 'fr'):
            p.arm(name, raise_=60 * e, fwd=10 * e, elbow=15 * e, wrist=20 * e)
        for name in ('ul', 'ur'):
            p.arm(name, raise_=70 * e, fwd=-10 * e, elbow=10 * e)
        p.hop(8 * e + 25 * bump((t - 38) / 10))
        return p
    C[0xB] = clip(51, joy, events=face() + [(10, eyes('closed')), (10, mouth('open')), (34, mouth('closed')),
                                             (34, eyes('open')), (12, sound(1, 12)), (16, sound(VOICE, 53)),
                                             (47, sound(*STEP))])

    def power(t):
        p = Pose()
        e = env(t, 7, 22, 31)
        p.body(lean=-11 * e + 6 * bump((t - 18) / 8))
        p.canopy(side=6 * wave(t, 4) * env(t, 8, 20, 26), lean=-4 * e)
        for name in ('fl', 'fr'):
            p.arm(name, raise_=35 * e, fwd=-12 * e, elbow=-10 * e, wrist=30 * e)
        for name in ('ul', 'ur'):
            p.arm(name, raise_=65 * e, fwd=-20 * e, elbow=-5 * e, wrist=25 * e)
        crouch(p, 6 * e)
        return p
    C[0xC] = clip(31, power, events=face() + [(7, mouth('open')), (24, mouth('closed')), (8, sound(VOICE, 54)),
                                               (11, sound(*WHOOSH)), (19, sound(*WHOOSH))])

    def refuse(t):
        p = Pose()
        e = env(t, 4, 24, 31)
        p.body(twist=20 * wave(t, 8) * e, lean=-5 * e)
        p.canopy(twist=-9 * wave(t, 8, 0.12) * e)
        for name in ('fl', 'fr'):
            p.arm(name, raise_=5 * e, fwd=45 * e, elbow=-10 * e, wrist=-25 * e + 12 * wave(t, 4) * e)
        return p
    C[0xD] = clip(31, refuse, events=face('narrow') + [(12, sound(3, 51)), (30, eyes('open'))])

    # condition loops (the partner shows them while the condition lasts)
    def sick(t):
        p = idle_pose(t, 32, 0.6, 1.2)
        tr = 1.4 * wave(t, 4)
        p.body(side=tr)
        p.canopy(side=tr * 1.5)
        return p
    C[0xE] = clip(32, sick, loop=True, events=face('half') + [(20, eyes('closed')), (24, eyes('half'))])

    def hungry(t):
        p = idle_pose(t, 32, 0.5, 0.5)
        r = wave(t, 16)
        for name in ('fl', 'fr'):
            p.arm(name, raise_=-10, fwd=45, elbow=30 + 12 * r, wrist=20, elbow_fwd=20)
        return p
    C[0xF] = clip(32, hungry, loop=True, events=face('narrow') + [(8, mouth('open')), (12, mouth('closed')),
                                                                   (24, mouth('open')), (28, mouth('closed'))])

    def needs_poop(t):
        p = idle_pose(t, 16, 0.4)
        p.body(side=5 * wave(t, 16))
        p.canopy(side=6 * wave(t, 16, 0.1))
        crouch(p, 4 + 3 * wave(t, 8))
        k = 'fl' if (t % 16) < 8 else 'fr'
        p.root(k, lift=8 * bump((t % 8) / 8))
        for name in ('fl', 'fr'):
            p.arm(name, raise_=-8, fwd=25, elbow=20)
        return p
    C[0x10] = clip(16, needs_poop, loop=True, events=face('narrow'))

    def sleepy(t):
        u = t / 48
        nod = smooth(u / 0.75) if u < 0.75 else 1 - smooth((u - 0.75) / 0.125) if u < 0.875 else 0.0
        p = idle_pose(t, 48, 0.4, 0.8)
        p.body(lean=10 * nod)
        p.canopy(lean=8 * nod)
        for name in ('fl', 'fr', 'ul', 'ur'):
            p.arm(name, raise_=-8 * nod)
        return p
    C[0x11] = clip(48, sleepy, loop=True, events=face('half') + [(20, eyes('closed')), (38, eyes('narrow')),
                                                                  (42, eyes('half'))])

    def tired(t):
        p = idle_pose(t, 16, 0.4, 1.1)
        b = wave(t, 8)
        p.hop(3 * b)
        p.body(lean=2 * b)
        for name in ('fl', 'fr', 'ul', 'ur'):
            p.arm(name, fwd=4 * wave(t, 16, 0.2), raise_=-4 * b)
        return p
    C[0x12] = clip(16, tired, loop=True, events=face('half') + [(0, mouth('open')), (4, mouth('closed')),
                                                                 (8, mouth('open')), (12, mouth('closed'))])

    def sulk(t):
        e = smooth(t / 8)
        p = Pose()
        huff = bump(((t - 8) % 16) / 16) if t >= 8 else 0
        p.body(twist=25 * e, lean=-3 * e + 2 * huff, side=-3 * e)
        p.canopy(twist=10 * e, lean=2 * huff)
        for name in ('fl', 'fr'):
            p.arm(name, raise_=-5 * e, fwd=55 * e, elbow=35 * e, elbow_fwd=30 * e, wrist=10 * e)
        for name in ('ul', 'ur'):
            p.arm(name, raise_=-12 * e)
        p.hop(2 * huff)
        return p
    C[0x13] = clip(24, sulk, loop=True, loop_from=8, events=face('narrow') + [(8, sound(3, 50))])

    # ---- scripted reactions
    def startled(t):
        p = Pose()
        h = 42 * bump((t - 1) / 11)
        p.hop(h)
        e = env(t, 3, 12, 21)
        p.body(lean=-10 * e)
        p.canopy(lean=-6 * e, side=4 * wave(t, 6) * e)
        for name in ('fl', 'fr', 'ul', 'ur'):
            p.arm(name, raise_=45 * e, fwd=-10 * e, wrist=30 * e)
        for name in ROOTS:
            p.root(name, lift=12 * bump((t - 1) / 11))
        return p
    C[0x15] = clip(21, startled, root=lambda t: (0, 0, 100 * smooth((t - 1) / 11)),
                   events=face('open', 'open') + [(12, sound(*STEP)), (16, mouth('closed'))])

    def think(t):
        p = idle_pose(t, 31, 0.3)
        e = env(t, 6, 24, 31)
        p.body(side=-6 * e, lean=3 * e)
        p.canopy(side=-7 * e)
        p.arm('fr', raise_=12 * e, fwd=50 * e, elbow=55 * e, wrist=25 * e + 8 * wave(t, 6) * e, elbow_fwd=20 * e)
        return p
    C[0x16] = clip(31, think, events=face('half') + [(14, eyes('open')), (18, eyes('narrow')), (24, eyes('open'))])

    def look_around(t):
        e = smooth(t / 10)
        p = idle_pose(t, 20, 0.3)
        tw = 18 * math.sin(2 * math.pi * (t - 10) / 20) if t >= 10 else 0
        p.body(twist=tw * e)
        p.canopy(twist=-0.5 * tw * e)
        return p
    C[0x17] = clip(30, look_around, loop=True, loop_from=10, events=face())

    def look(lean):
        def f(t):
            e = smooth(t / 7)
            p = idle_pose(t, 2, 0.0)
            p.body(lean=lean * e)
            p.canopy(lean=lean * 0.8 * e)
            for name in ('fl', 'fr'):
                p.arm(name, raise_=6 * e if lean < 0 else -6 * e)
            return p
        return f
    C[0x18] = clip(10, look(-11), loop=True, loop_from=8, events=face('open'))
    C[0x19] = clip(10, look(12), loop=True, loop_from=8, events=face('half'))

    # ---- battle
    C[0x21] = clip(16, stance, loop=True, events=face('narrow'))
    C[0x22] = clip(16, lambda t: stance(t, 16, 1.0), loop=True,
                   events=face('half') + [(0, mouth('open')), (6, mouth('closed')), (8, mouth('open')),
                                          (14, mouth('closed'))])

    def block(t):
        e = smooth((t + 1) / 4)
        p = stance(0)
        for name in ('fl', 'fr'):
            p.arm(name, raise_=-10 * e, fwd=40 * e, elbow=30 * e, elbow_fwd=30 * e)
        p.body(lean=-6 * e)
        return p
    C[0x25] = clip(5, block, events=face('closed'), step=1)

    def hit(direction):
        def f(t):
            p = Pose()
            k = bump(min(1.0, t / 4) * 0.5) if t < 4 else max(0.0, 1 - smooth((t - 4) / 24))
            p.body(lean=-direction * 22 * k, side=4 * k * wave(t, 6))
            p.canopy(lean=-direction * 14 * k * (1 + 0.4 * wave(t, 8)), side=6 * k * wave(t, 5))
            for name in ('fl', 'fr', 'ul', 'ur'):
                p.arm(name, raise_=35 * k, fwd=-direction * 30 * k, wrist=30 * k)
            p.hop(15 * bump(t / 10))
            settle_roots(p, 0)
            return p
        return f
    C[0x28] = clip(37, hit(1), step=2, root=lambda t: (0, 0, 260 * smooth(t / 12)),
                   events=face('closed', 'open') + [(10, sound(*THUD)), (14, eyes('narrow')), (16, mouth('closed')),
                                                    (30, eyes('open'))])
    C[0x29] = clip(37, hit(-1), step=2, root=lambda t: (0, 0, -260 * smooth(t / 12)),
                   events=face('closed', 'open') + [(10, sound(*THUD)), (14, eyes('narrow')), (16, mouth('closed')),
                                                    (30, eyes('open'))])

    def victory(t):
        p = Pose()
        spin = 360 * smooth((t - 6) / 18)
        p.r(1, ry=spin)
        p.hop(55 * bump((t - 6) / 18) + 20 * bump((t - 32) / 8))
        e = env(t, 8, 46, 53)
        p.body(lean=-8 * e)
        p.canopy(side=7 * wave(t, 6) * env(t, 24, 44, 50), lean=-5 * e)
        for name, ph in (('fl', 0), ('fr', 0.5), ('ul', 0.25), ('ur', 0.75)):
            up = 70 if name in ('ul', 'ur') else 55
            p.arm(name, raise_=up * e, fwd=15 * wave(t, 8, ph) * env(t, 26, 44, 50), wrist=25 * e)
        for name in ROOTS:
            p.root(name, lift=14 * bump((t - 6) / 18))
        return p
    C[0x2A] = clip(53, victory, events=face('open') + [(12, sound(VOICE, 53)), (24, sound(*STEP)),
                                                        (26, mouth('open')), (26, eyes('closed')),
                                                        (36, sound(VOICE, 53)), (40, sound(*STEP)),
                                                        (46, mouth('closed')), (46, eyes('open'))])

    def fainted_pose(e, t=0):
        """Toppled onto its back: the whole tree turns about the hips, which come down to
        the bark's radius above the ground; arms and roots go limp."""
        p = Pose()
        p.r(1, rx=-84 * e)
        p.t(1, dy=40 * e, dz=10 * e)
        p.canopy(lean=-8 * e)
        for name in ('fl', 'fr', 'ul', 'ur'):
            p.arm(name, raise_=-15 * e, fwd=-10 * e, elbow=-10 * e)
        for name in ROOTS:
            p.root(name, lift=10 * e, tip=10 * e)
        return p

    def faint(t):
        e = (t / 14) ** 2 if t < 14 else 1.0 - 0.06 * bump((t - 14) / 6)
        p = fainted_pose(min(1.0, e))
        if t < 6:
            p.arm('fl', raise_=20 * bump(t / 6))
            p.arm('fr', raise_=20 * bump(t / 6))
        return p
    C[0x2B] = clip(31, faint, events=face('half', 'open') + [(14, sound(*THUD)), (14, eyes('closed')),
                                                              (16, mouth('closed'))])

    def get_up(t):
        e = 1.0 - smooth((t - 4) / 16)
        p = fainted_pose(e)
        p.hop(18 * bump((t - 16) / 10))
        return p
    C[0x2C] = clip(31, get_up, events=face('closed') + [(6, eyes('half')), (14, eyes('open')), (26, sound(*STEP))])

    # ---- techniques (0x2E + index in DIGIMON_DATA[121].moves)
    def poison_claw(t):
        p = stance(0)
        w = keys(t, [(0, 0.0), (4, 1.0), (7, -1.0), (11, -1.0), (16, 0.0)])     # wind-up, slash
        p.body(lean=-6 * max(w, 0) + 16 * max(-w, 0), twist=-10 * w)
        p.canopy(lean=10 * max(-w, 0), twist=6 * w)
        p.arm('fr', raise_=40 * max(w, 0) - 10 * max(-w, 0), fwd=-30 * w + 40 * max(-w, 0), elbow=20 * max(w, 0),
              wrist=40 * max(w, 0) - 20 * max(-w, 0))
        p.arm('fl', raise_=25 * max(w, 0), fwd=-10 * w, elbow=15)
        return p
    C[0x2E] = clip(17, poison_claw, step=2, root=lambda t: (0, 0, -100 * smooth((t - 4) / 4)),
                   events=face('narrow') + [(5, mouth('open')), (11, mouth('closed')), (6, sound(VOICE, 55)),
                                            (5, sound(*WHOOSH))])

    C[0x2F] = vine_clip(rig, 0x2F)                     # Danger Sting
    C[0x30] = vine_clip(rig, 0x30)                     # Green Trap

    def insect_plague(t):
        p = stance(0)
        e = env(t, 6, 28, 39)
        sh = wave(t, 3) * env(t, 6, 26, 32)
        p.body(lean=-8 * e)
        p.canopy(side=9 * sh, lean=-6 * e + 3 * wave(t, 4))
        for name in ('fl', 'fr', 'ul', 'ur'):
            p.arm(name, raise_=55 * e, fwd=15 * e * wave(t, 6), wrist=30 * e)
        return p
    C[0x31] = clip(39, insect_plague, events=face('narrow') + [(7, mouth('open')), (28, mouth('closed')),
                                                                (6, sound(1, 25)), (7, sound(VOICE, 53))])

    def bug(t):
        p = stance(0)
        e = keys(t, [(0, 0.0), (14, 1.0), (19, -0.6), (30, -0.6), (40, 0.0)])
        p.body(lean=-10 * max(e, 0) + 18 * max(-e, 0))
        p.canopy(lean=-6 * max(e, 0) + 10 * max(-e, 0))
        for name in ('fl', 'fr'):
            p.arm(name, raise_=20 + 20 * max(e, 0), fwd=-25 * max(e, 0) + 30 * max(-e, 0), wrist=20)
        crouch(p, 10 * max(e, 0))
        return p
    C[0x32] = clip(41, bug, events=face('narrow') + [(18, mouth('open')), (31, mouth('closed')),
                                                      (20, sound(VOICE, 55)), (24, sound(*WHOOSH))])

    C[0x33] = vine_clip(rig, 0x31)                     # Charm Perfume

    def powder_extra(p, t):
        p.canopy(side=8 * wave(t, 3) * env(t, 6, 30, 38))
    C[0x34] = vine_clip(rig, 0x32, extra=powder_extra)  # Poison Powder: the canopy shakes the powder out
    C[0x35] = vine_clip(rig, 0x33)                     # Mass Morph

    def bit_bomb(t):
        p = stance(0)
        # pluck a cherry from the canopy (0-12), wind up (12-26), hop and hurl at 30, land
        reach = env(t, 8, 12, 18) if t < 18 else 0.0
        wind = keys(t, [(12, 0.0), (26, 1.0), (30, -1.0), (36, -1.0), (48, 0.0)])
        p.arm('fr', raise_=80 * reach + 70 * max(wind, 0) + 25 * max(-wind, 0),
              fwd=-20 * reach - 45 * max(wind, 0) + 75 * max(-wind, 0),
              elbow=45 * reach + 30 * max(wind, 0), wrist=30 * reach + 30 * max(wind, 0) - 20 * max(-wind, 0))
        p.body(lean=-4 * reach - 10 * max(wind, 0) + 18 * max(-wind, 0), twist=-14 * max(wind, 0) + 10 * max(-wind, 0))
        p.canopy(side=5 * wave(t, 3) * env(t, 6, 12, 16), lean=-6 * max(wind, 0) + 10 * max(-wind, 0))
        p.arm('fl', raise_=30 * max(wind, 0), fwd=20 * max(wind, 0) - 20 * max(-wind, 0))
        p.hop(40 * bump((t - 24) / 14))
        return p
    C[0x36] = clip(51, bit_bomb, step=2, events=face('narrow') + [(6, sound(*WHOOSH)), (18, sound(*WHOOSH)),
                                                           (28, mouth('open')), (36, mouth('closed')),
                                                           (30, sound(VOICE, 55)), (30, sound(*WHOOSH)),
                                                           (38, sound(*STEP)), (42, sound(1, 11))])

    missing = [s for s in REQUIRED_SLOTS if s not in C]
    assert not missing, [hex(s) for s in missing]
    return C
