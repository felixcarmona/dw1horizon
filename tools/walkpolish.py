#!/usr/bin/env python3
"""Walk polish for every imported species: legs by their feet (legik.py) and feet flat (footfix.py), only where it measures better.

  walkpolish.py one ID [--out build/walkfix]       one species
  walkpolish.py all [--out build/walkfix] [--jobs 12]   every species of content/species with id >= 180
  walkpolish.py videos [--out build/walkfix] [--jobs 8]  one studio video per species: the model (the polished one when it was
                                                    accepted) above its donor, names in the picture and in the file name

Per species: the donor is the DW1 Digimon the import was built on (the spec of its model file, mods/experimental/batch-import/
specs/<model file stem>.json). The feet of the model and of the donor are found by geometry (the lowest bones that come in
mirrored pairs; 2 or 4 of each), paired by side and by front/back, each leg is hip, knee, ankle = the foot bone and its two
ancestors. For the walk and run slots, for each of three stride scales, the legs are solved by the donor's ankle path and the
feet planted; the best is kept when the stance slip (animstudio.py metrics) falls by 15 % or more and the file fits the partner
buffer. Written: OUT/<id>-<Name>.MMD (always: the polished model, or a copy of the original) and OUT/report.jsonl.
The model's own files are not touched, and nor is content/. Runs under the card-game venv.
"""
import argparse, glob, json, math, os, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
try:
    import numpy  # noqa: F401
except ImportError:
    py = os.path.join(os.environ.get('DCB_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'digimoncardbattle')), '.venv', 'bin', 'python')
    if os.path.exists(py) and not os.environ.get('WALKPOLISH_REEXEC'):
        os.environ['WALKPOLISH_REEXEC'] = '1'
        os.execv(py, [py, os.path.abspath(__file__)] + sys.argv[1:])
    raise SystemExit('walkpolish: needs numpy and OpenCV (the venv of the card-game project)')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'review'))      # limbmap.py
import animstudio as A  # re-executes under the venv when numpy/OpenCV are missing
import mmd, animsheet, retarget, footfix, legik, armswing, armmatch, armgesture, followthrough, armmirror, species

STEP = 8                   # the longest span between two keys of a rewritten bone (footfix.MAX_ERR keeps the orientation within a few degrees of the intended one)
WALK_SLOTS = [2, 3, 4, 0x1b, 0x23, 0x24]        # 0x22 is the battle idle variant: donors often share it with idle 2 (slot 1)
BUFFER = 0x18800
CUR_TYPE = [None]


def SZ(path):
    """What a model takes of the partner buffer: its resident part (the cold animations are read from the disc: tools/coldsplit.py,
    patch 0113), not the whole file."""
    import coldsplit
    data = open(path, 'rb').read()
    t = CUR_TYPE[0]
    if t is None or t < 180:
        return len(data)
    try:
        return len(coldsplit.split(data, mmd.exe().bone_count[t])[0])
    except Exception:
        return len(data)


EXTRAS = os.environ.get('POLISH_EXTRAS') == '1'     # animation the donor does not have: idle sway, follow-through, arm swing, hands to the mouth (off: the donor's own, on the right bones)
FOOT_LIFT = 0.5            # how much of the shin's pitch the foot follows while it is in the air (footfix.py)
EXPLICIT_SUPPORT_SLIP_MAX = 25.0  # maximum mean support-foot travel as % of root travel for an explicitly mapped rig


def all_species():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'content/species/*.json'))):
        s = json.load(open(f))
        if s['id'] >= 180:
            out.append(dict(id=s['id'], name=s['name'], model=os.path.join(ROOT, s['model']['file']), tex=os.path.join(ROOT, s['texture']['file']),
                            source=s.get('_source', '')))
    return out


EXPLICIT = {180: 'content/models/dcb-import/veemon.json', 181: 'content/models/dcb-import/puppetmon.json',
            182: 'content/models/dcb-import/kimeramon-dw2.json', 373: 'content/models/mega/wargreymon-dcb.json'}


def spec_of(sp):
    if sp['id'] in EXPLICIT:
        p = os.path.join(ROOT, EXPLICIT[sp['id']])
    else:
        p = os.path.join(ROOT, 'content/imports/specs', os.path.splitext(os.path.basename(sp['model']))[0] + '.json')
    if not os.path.exists(p):
        return None
    return json.load(open(p))


def feet_of(skel, pos):
    """Foot bones by geometry: the lowest mirrored pair of bones (x opposite, same height), and a second pair when it stands
    about as low (a quadruped); the topmost bone of each chain (a toe under a foot is not a foot)."""
    nb = len(skel)
    ys = [pos[b][1] for b in range(1, nb)]
    lo, hi = max(ys), min(ys); H = (lo - hi) or 1
    off = [b for b in range(1, nb) if abs(pos[b][0]) > 0.04 * H]
    pairs = []
    for a in off:
        if pos[a][0] <= 0:
            continue
        mates = [c for c in off if pos[c][0] < 0 and abs(pos[c][0] + pos[a][0]) < 0.1 * H + 0.2 * pos[a][0]
                 and abs(pos[c][1] - pos[a][1]) < 0.06 * H and abs(pos[c][2] - pos[a][2]) < 0.4 * H]
        if mates:
            c = min(mates, key=lambda c: abs(pos[c][0] + pos[a][0]) + abs(pos[c][1] - pos[a][1]))
            pairs.append((min(pos[a][1], pos[c][1]), a, c))
    if not pairs:
        return []
    pairs.sort(key=lambda p: -p[0])
    low = pairs[0][0]
    chosen = [p for p in pairs if p[0] >= low - 0.10 * H]
    # a pair that hangs from another chosen bone is its toes
    bones = {b for p in chosen for b in p[1:]}
    def under(b):
        a = skel[b][1]
        while a > 0:
            if a in bones:
                return True
            a = skel[a][1]
        return False
    chosen = [p for p in chosen if not (under(p[1]) or under(p[2]))]
    feet = [b for p in chosen for b in p[1:]]
    return sorted(feet, key=lambda b: (pos[b][0] > 0, pos[b][2]))


def arms_of(skel, pos, leg_bones):
    """The arm of a biped by geometry: the mirrored pair of limbs (not legs) that hangs the furthest below its shoulder.
    Returns [(shoulder, elbow, side)] or []."""
    nb = len(skel)
    ys = [pos[b][1] for b in range(1, nb)]
    H = (max(ys) - min(ys)) or 1
    off = [b for b in range(1, nb) if abs(pos[b][0]) > 0.04 * H and b not in leg_bones]
    best = None
    for a in off:
        if pos[a][0] <= 0:
            continue
        mates = [c for c in off if pos[c][0] < 0 and abs(pos[c][0] + pos[a][0]) < 0.1 * H + 0.2 * pos[a][0]
                 and abs(pos[c][1] - pos[a][1]) < 0.12 * H and abs(pos[c][2] - pos[a][2]) < 0.4 * H]
        if not mates:
            continue
        c = min(mates, key=lambda c: abs(pos[c][0] + pos[a][0]) + abs(pos[c][1] - pos[a][1]))
        chains = []
        for x in (a, c):
            path = [x]
            while skel[path[-1]][1] > 0 and skel[path[-1]][1] not in leg_bones and abs(pos[skel[path[-1]][1]][0]) > 0.02 * H and len(path) < 4:
                path.append(skel[path[-1]][1])
            chains.append(path[::-1])                # shoulder first
        sa, sc = chains[0], chains[1]
        if len(sa) < 2 or len(sa) != len(sc):
            continue
        hang = pos[a][1] - pos[sa[0]][1]              # y down: positive when the hand is below the shoulder
        side = abs(pos[a][0] - pos[sa[0]][0])
        if hang < 0.12 * H or side > 1.2 * hang:
            continue
        if best is None or hang > best[0]:
            best = (hang, sa, sc)
    if not best:
        return []
    return [(best[1][0], best[1][1], pos[best[1][-1]][0]), (best[2][0], best[2][1], pos[best[2][-1]][0])]


def rest_of(m, nb, skel):
    idle, _, _ = animsheet.slot_frames(m, nb, 0)
    return retarget.world_pos(skel, idle[0])


# Foot bones feet_of does not find: Magnamon's rest pose stands staggered more than its pairing allows, Nefertimon's rear shin
# (15) takes the place of the foot under it. Monmon's roles were verified with
# isolated textured native parts: bare toes5/11, brown gloves14/19. In feet_of's order: left
# side first, front to back, then right.
# Kyukimon's reviewed biped has articulated ankle/toe pairs. Monmon has one
# short leg segment followed by a heel and toe, rather than a knee/ankle pair.
# Neither fits the generic two-link knee solver; keep their explicit foot roles
# for diagnostics while abstaining from automatic replacements.
FEET = {196: [14, 17, 21, 25], 197: [7, 11], 198: [9, 16, 6, 13], 352: [11, 5]}
ANATOMY_ABSTAIN = {
    196: 'four paws14/17/21/25; hind18-21/22-25 include hock20/24, not generic two-link legs',
    322: 'textured legs3-6/12-15 confirmed; four-bone sole dynamics and controller pending',
    352: 'single leg segments3/9, ankle heels4/10 and toes5/11; generic knee IK is anatomically invalid',
}


def leg_plan(sp, spec, m, nb, skel, donor_t, dm, dnb, dskel):
    tp, dp = rest_of(m, nb, skel), rest_of(dm, dnb, dskel)
    tf, df = FEET.get(sp['id']) or feet_of(skel, tp), feet_of(dskel, dp)
    if len(tf) not in (2, 4) or len(tf) != len(df):
        return None, f'feet: model {tf}, donor {df}'
    legs = []
    for a, da in zip(tf, df):
        k, h = skel[a][1], skel[skel[a][1]][1] if skel[a][1] > 0 else 0
        dk = dskel[da][1]; dh = dskel[dk][1] if dk > 0 else 0
        if k < 1 or h < 1 or dk < 1 or dh < 1:
            return None, f'leg of {a} has no hip/knee bones'
        path, b = [], da
        while b != dh and b > 0:
            path.append(b); b = dskel[b][1]
        tip = int(len([x for x in path if dskel[x][0] >= 0 and dm.tmd.obj_verts(dskel[x][0])]) == 1)      # a one-bone leg: its foot is the bone's mesh end
        legs.append((h, k, a, dh, da, tip))
    if len({l[0] for l in legs}) != len(legs):
        return None, 'legs share a hip bone'
    return legs, ''


def stance_slip(path, t, tex, slot=2, feet=None):
    """(stance slip, foot lift), averaged over the walk and the run when the model has both."""
    out = []
    m0 = mmd.MMD.load(path, t)
    for sl in ([slot, 3] if slot == 2 and len(m0.anims.table) > 3 and m0.anims.table[3] is not None else [slot]):
        mod = A.Model(f'{path}:{t}:{tex}', sl)
        # The legacy studio metric tracks the two bones lowest in the rest
        # pose. That can select hands, wings, or ornaments. Use reviewed
        # support endpoints when anatomy has an explicit role assignment.
        if feet:
            mod.lowest = list(feet)
        rs, res = A.metrics(mod)
        out.append(((sum(r[3] for r in res) / len(res)) if res else 0.0, max((r[5] for r in res), default=0)))
    return sum(x[0] for x in out) / len(out), sum(x[1] for x in out) / len(out)


def leg_swings(path, t, legs, slot=2):
    """How far each foot swings fore and aft of its hip in the walk (the smallest tells a leg that hardly walks)."""
    m = mmd.MMD.load(path, t); e = mmd.exe(); nb, skel = e.bone_count[t], e.skeleton[t]
    P = [retarget.world_pos(skel, f) for f in animsheet.slot_frames(m, nb, slot)[0]]
    return [max(p_[l[2]][2] - p_[l[0]][2] for p_ in P) - min(p_[l[2]][2] - p_[l[0]][2] for p_ in P) for l in legs]


def thigh_swing(path, t, legs, slots=(2, 3)):
    """The highest a thigh goes in the walk and the run, as degrees from hanging straight down (90 = horizontal, over 90 = the knee above the hip)."""
    m = mmd.MMD.load(path, t); e = mmd.exe(); nb, skel = e.bone_count[t], e.skeleton[t]
    top = 0.0
    for sl in slots:
        if sl >= len(m.anims.table) or m.anims.table[sl] is None:
            continue
        for f in animsheet.slot_frames(m, nb, sl)[0]:
            p_ = retarget.world_pos(skel, f)
            for l in legs:
                v = [p_[l[1]][j] - p_[l[0]][j] for j in range(3)]
                top = max(top, math.degrees(math.atan2(math.hypot(v[0], v[2]), v[1])))
    return top


def scale_root(m, slots, r):
    """The ground travel of the walk and run clips times r (the keys of bone 0's tx and tz): a short-legged body walks slower."""
    footfix.unshare(m, slots)
    done = set()
    for s_ in slots:
        i = m.anims.table[s_] if s_ < len(m.anims.table) else None
        if i is None or i in done:
            continue
        done.add(i)
        for ins in m.anims.anims[i].instrs:
            if ins['op'] == 'key':
                for bb in ins['bones']:
                    if bb['bone'] == 0:
                        for ch in ('tx', 'tz'):
                            if ch in bb['vals']:
                                bb['vals'][ch] = int(round(bb['vals'][ch] * r))


def root_stage(sp, rep, cur, slots, tmp):
    """The root travel that plants the feet best (0.5..1 of the clip's): a body whose legs are short for its stride otherwise skates."""
    t = sp['id']; nb = mmd.exe().bone_count[t]
    best = (stance_slip(cur, t, sp['tex'])[0], 1.0, cur)
    base = best[0]
    for r in (0.85, 0.7, 0.55):
        m = mmd.MMD.load(cur, t)
        scale_root(m, slots, r)
        out = os.path.join(tmp, f'root{r}.MMD')
        data = m.build(); open(out, 'wb').write(data)
        sl = stance_slip(out, t, sp['tex'])[0]
        if sl < best[0]:
            best = (sl, r, out)
    if best[1] != 1.0 and best[0] <= 0.85 * base:
        rep['root_scale'] = best[1]; rep['slip_root'] = round(best[0], 1)
        return best[2]
    return cur


def real_arms(P, rep):
    """limbmap's arms without the chains that are legs (it takes Magnamon's staggered leg for an arm, twice) and without repeats."""
    legb = {b for l in (rep.get('legs') or []) for b in l[:3]} | {b for _, c in P['legs'] for b in c}
    seen, out = set(), []
    for k, c in P['arms']:
        if not set(c) & legb and tuple(c) not in seen:
            seen.add(tuple(c)); out.append((k, c))
    return out


def match_stage(sp, rep, cur, tmp, own, dt, dpath, step):
    """The arms take the donor's arm posture (armmatch.py): its idle holds them forward, its walk swings them forward and back."""
    import limbmap, import_batch as IB
    t = sp['id']
    cur = make_room(sp, cur, tmp, BUFFER - 5000)
    T = limbmap.shape_from_mmd(cur, t); S, _, _ = IB.donor_shape(dt)
    PT, PS = limbmap.parts(T), limbmap.parts(S)
    PT['arms'] = real_arms(PT, rep)
    side = lambda Sh, c: Sh.tip[c[-1]][0] > 0
    def by_side(Sh, P):
        out = {True: [], False: []}
        for _, c in P['arms']:
            c = [b for b in c if Sh.mass[b]]
            if c:
                out[side(Sh, c)].append(c)
        for k in out:
            out[k].sort(key=lambda c: Sh.joint[c[0]][1])        # from the shoulders down
        return out
    ta, sa = by_side(T, PT), by_side(S, PS)
    spec = []
    for sd in (True, False):
        if not ta[sd] or not sa[sd] or any(len(c) < 3 for c in ta[sd]):
            rep['armmatch'] = 'no arm pair'; return cur
        for i, ct in enumerate(ta[sd]):
            cs = sa[sd][min(i, len(sa[sd]) - 1)]                 # more arms than the donor: the extra pairs move like its arms
            spec.append(f"{','.join(map(str, ct[-3:]))}:{','.join(map(str, cs[-3:]))}")
    m = mmd.MMD.load(cur, t)
    slots = [s_ for s_ in range(0x2e) if s_ < len(m.anims.table) and m.anims.table[s_] is not None and s_ not in own]
    limit = max(BUFFER, SZ(cur))
    for st in (STEP, 4, 2):
        ns = argparse.Namespace(mmd=cur, out=os.path.join(tmp, 'match.MMD'), type=t, donor=dpath, dtype=dt, arms=spec, slots=slots, step=st)
        armmatch.run(ns)
        if SZ(ns.out) <= limit:
            rep['armmatch'] = f'arms follow the donor ({len(slots)} slots)'
            return ns.out
    rep['armmatch'] = 'does not fit the buffer'
    return cur


def eat_stage(sp, rep, cur, tmp, own, step):
    """The eating clip (slot 8): both hands go to the mouth (armgesture.py)."""
    import limbmap
    t = sp['id']; e = mmd.exe(); nb = e.bone_count[t]
    m = mmd.MMD.load(cur, t)
    if len(m.anims.table) <= 8 or m.anims.table[8] is None or 8 in own:
        return cur
    cur = make_room(sp, cur, tmp, BUFFER - 4000)
    T = limbmap.shape_from_mmd(cur, t)
    P = limbmap.parts(T)
    arms = [[b for b in c if T.mass[b]] for _, c in real_arms(P, rep)]
    arms = [c for c in arms if len(c) >= 3]
    head = [b for b in P['head'] if T.mass[b]]
    if len(arms) != 2 or not head:
        rep['eat'] = 'no arms or head'; return cur
    ns = argparse.Namespace(mmd=cur, out=os.path.join(tmp, 'eat.MMD'), type=t, arms=[','.join(map(str, c[-3:])) for c in arms], head=head[-1], slots=[8], step=step)
    for st in (STEP, 4, 2):
        ns.step = st; armgesture.run(ns)
        if SZ(ns.out) <= max(BUFFER, SZ(cur)):
            break
    else:
        rep['eat'] = 'does not fit the buffer'; return cur
    rep['eat'] = 'hands to the mouth'
    return ns.out


def make_room(sp, cur, tmp, target):
    """If the model is over `target` bytes, every animation is encoded again from its own samples with a coarser tolerance (8, 10, 12, 14,
    18, 24: the first that gets it under) so that the follow-through and the eating gesture fit the buffer. Smaller already: unchanged."""
    if SZ(cur) <= target:
        return cur
    t = sp['id']; e = mmd.exe(); nb = e.bone_count[t]
    m0 = mmd.MMD.load(cur, t)
    samples = {}
    for s_, i in enumerate(m0.anims.table):
        if i is None or i in samples:
            continue
        smp, lp, evs = animsheet.slot_frames(m0, nb, s_)
        ev = [(k, kind, c) for k, kind, c in evs if kind in ('sound', 'tex')]
        samples[i] = (smp, lp, ev)
    best = cur
    for tol in (8, 10, 12, 14, 18, 24):
        m = mmd.MMD.load(cur, t)
        try:
            for i, (smp, lp, ev) in samples.items():
                m.anims.anims[i] = mmd.encode_anim(smp, nb, lp, ev, tol=tol)
            data = m.build()
        except Exception:
            continue
        out = os.path.join(tmp, f'room{tol}.MMD'); open(out, 'wb').write(data)
        best = out
        if len(data) <= target:
            break
    return best


def posture_stage(sp, rep, cur, tmp, own, step):
    """The model keeps its own posture (its source game's idle, first frame) and the donor's motion goes on top of it: every bone but the legs
    and the hips they hang from gets local(t) = donor clip's local(t) * (its local at the idle's start)^-1 * the model's own local there.
    A donor that crouches, leans or looks down at rest no longer makes the model do so; its walk, run and gestures stay. Legs: legik
    already walks them from the model's own stance."""
    import limbmap
    if os.environ.get('POSTURE', '1') == '0':
        return cur
    t = sp['id']; e = mmd.exe(); nb, skel = e.bone_count[t], e.skeleton[t]
    T = limbmap.shape_from_mmd(cur, t); P = limbmap.parts(T)
    skip = {0, 1}
    for _, c in P['legs']:
        skip |= set(c)
    if P.get('legs_host'):
        skip.add(P['legs_host'])
    kids = {}
    for b in range(1, nb):
        kids.setdefault(skel[b][1], []).append(b)
    order, todo = [], [0]
    while todo:                                             # parents first
        b = todo.pop(0); order.append(b); todo += kids.get(b, [])
    bones = [b for b in order if b not in skip and b < nb]
    own_m = mmd.MMD.load(sp['model'], t)
    oid = retarget.world_rots(skel, animsheet.slot_frames(own_m, nb, 0)[0][0])
    limit = max(BUFFER, SZ(cur))
    cur = make_room(sp, cur, tmp, limit - 12000)
    m = mmd.MMD.load(cur, t)
    vid = retarget.world_rots(skel, animsheet.slot_frames(m, nb, 0)[0][0])
    Lrel = {}
    for b in bones:
        par = skel[b][1]
        L0 = retarget.m3mul(footfix.m3t(vid[par]), vid[b]); Lown = retarget.m3mul(footfix.m3t(oid[par]), oid[b])
        Lrel[b] = retarget.m3mul(footfix.m3t(L0), Lown)
    bones = [b for b in bones if retarget.axis_angle(Lrel[b])[1] > 0.03]       # already in the model's own pose: left alone
    if not bones:
        rep['posture'] = 'already the model\'s own'; return cur
    slots = footfix.drop_looped(m, [s_ for s_ in range(0x2e) if s_ < len(m.anims.table) and m.anims.table[s_] is not None and s_ not in own])
    footfix.unshare(m, slots)
    done = set()
    for s_ in slots:
        i = m.anims.table[s_]
        if i in done:
            continue
        done.add(i); an = m.anims.anims[i]
        for b in bones:
            par = skel[b][1]
            footfix.rewrite_bone(an, nb, skel, s_, b, lambda tt, pose, wr, b=b, par=par:
                                 retarget.m3mul(wr[par], retarget.m3mul(retarget.m3mul(footfix.m3t(wr[par]), wr[b]), Lrel[b])), max(step, STEP))
    data = m.build(); assert mmd.MMD.parse(data, nb).build() == data
    out = os.path.join(tmp, 'posture.MMD'); open(out, 'wb').write(data)
    if SZ(out) > limit:
        rep['posture'] = f'did not fit ({SZ(out)} > {limit})'; return cur
    rep['posture'] = f'{len(bones)} bones in the model\'s own posture'
    return out


def fx_stage(sp, rep, cur, tmp, own, step, donor_t):
    """A body with more than the donor has: wings the donor lacks flap softly, and the extra pairs of arms (beyond the donor's) are held forward."""
    import limbmap, import_batch as IB
    t = sp['id']; e = mmd.exe(); nb, skel = e.bone_count[t], e.skeleton[t]
    T = limbmap.shape_from_mmd(cur, t); PT = limbmap.parts(T)
    S, _, _ = IB.donor_shape(donor_t); PS = limbmap.parts(S)
    wings = [c[0] for _, c in PT.get('wings', [])] if not PS.get('wings') else []
    arms = [[b for b in c if T.mass[b]] for _, c in real_arms(PT, rep)]
    extra = []
    if len(arms) > len(PS['arms']):
        order = sorted(arms, key=lambda c: T.joint[c[0]][1])          # from the shoulders down: the donor's pairs take the first ones
        extra = [c[0] for c in order[len(PS['arms']):] if c]
    lift = []                                # every arm keeps the model's own pose already (posture_stage)
    if lift:                                 # the start of the idle: the variant's and the model's own (the source game's)
        own_m = mmd.MMD.load(sp['model'], t); cur_m = mmd.MMD.load(cur, t)
        oid = retarget.world_rots(skel, animsheet.slot_frames(own_m, nb, 0)[0][0])
        vid = retarget.world_rots(skel, animsheet.slot_frames(cur_m, nb, 0)[0][0])
    if not wings and not extra:
        return cur
    limit = max(BUFFER, SZ(cur))
    cur = make_room(sp, cur, tmp, limit - 9000)            # room for the new keys: a little precision elsewhere first
    m = mmd.MMD.load(cur, t)
    slots = footfix.drop_looped(m, [s_ for s_ in range(0x2e) if s_ < len(m.anims.table) and m.anims.table[s_] is not None and s_ not in own])
    footfix.unshare(m, slots)
    done = set()
    for s_ in slots:
        i = m.anims.table[s_]
        if i in done:
            continue
        done.add(i); an = m.anims.anims[i]
        for k, b in enumerate(wings):
            sgn = 1 if T.tip[b][0] > 0 else -1; ph0 = 0.5 * (k // 2)
            p = mmd.AnimPlayer(an, nb, s_); N = 0
            while p.tick(stop_at_infinite_loop=True):
                N += 1
            footfix.rewrite_bone(an, nb, skel, s_, b,
                                 lambda tt, pose, wr, b=b, sgn=sgn, ph0=ph0, N=N: retarget.m3mul(footfix.rz(sgn * 0.3 * math.sin(2 * math.pi * tt / max(N, 1) + ph0)), wr[b]), max(step, STEP))
        for c in lift:                       # every arm in the model's own pose (its own idle, first frame), the donor's motion on top of it
            for b in c:
                par = skel[b][1]
                L0 = retarget.m3mul(footfix.m3t(vid[par]), vid[b])                 # this clip's arm at the idle's start, under its parent
                Lown = retarget.m3mul(footfix.m3t(oid[par]), oid[b])               # the model's own arm there
                footfix.rewrite_bone(an, nb, skel, s_, b, lambda tt, pose, wr, b=b, par=par, L0=L0, Lown=Lown:
                                     retarget.m3mul(wr[par], retarget.m3mul(retarget.m3mul(retarget.m3mul(footfix.m3t(wr[par]), wr[b]), footfix.m3t(L0)), Lown)), max(step, STEP))
    data = m.build(); assert mmd.MMD.parse(data, nb).build() == data
    out = os.path.join(tmp, 'fx.MMD'); open(out, 'wb').write(data)
    if SZ(out) > limit:
        rep['fx'] = f'did not fit ({SZ(out)} > {limit})'; return cur
    rep['fx'] = f'{len(wings)} wings flap, {len(lift)} arms in the model\'s own pose ({len(extra)} more than the donor)'
    return out


def follow_stage(sp, rep, cur, tmp, own, step, spec=None):
    """Arms and tail that are rigid with their parent trail behind it, in the slots the source game does not animate itself."""
    import limbmap
    t = sp['id']; e = mmd.exe(); nb, skel = e.bone_count[t], e.skeleton[t]
    T = limbmap.shape_from_mmd(cur, t)
    P = limbmap.parts(T)
    roled = [('armR' if T.tip[c[-1]][0] > 0 else 'armL', c) for _, c in P['arms']] + ([('tail', P['tail'])] if P['tail'] else [])
    roled = [(r, [b for b in c if T.mass[b]]) for r, c in roled]
    roled = [(r, c) for r, c in roled if c]
    # a leg is never an arm or a tail (limbmap takes Magnamon's staggered leg for an arm, and Nefertimon's rear leg for its tail): rigid, it would not walk
    legb = {b for l in (rep.get('legs') or []) for b in l[:3]} | {b for _, c in P['legs'] for b in c}
    seen, kept = set(), []
    for r, c in roled:
        if not set(c) & legb and tuple(c) not in seen:
            seen.add(tuple(c)); kept.append((r, c))
    roled = kept
    chains = [c for _, c in roled]
    if not chains:
        rep['follow'] = 'no limbs'; return cur
    m = mmd.MMD.load(cur, t)
    slots = [s_ for s_ in range(0x2e) if s_ < len(m.anims.table) and m.anims.table[s_] is not None and s_ not in own]
    limit = max(BUFFER, SZ(cur))
    cur = make_room(sp, cur, tmp, limit - 6000)            # a model at the buffer's limit gives up a little precision elsewhere first
    mapped = {int(k) for k in ((spec or spec_of(sp) or {}).get('map') or {})}
    force = [b for c in chains for b in c if b not in mapped]        # not in the donor map: the motion they have is a layered idle, replaced
    spec_of_chain = lambda rc: f"{rc[0]}={','.join(map(str, rc[1]))}"
    base = cur
    counter = [0]

    def run(sl, st, out=None, rc=None, rigid=False):
        counter[0] += 1
        chs = [spec_of_chain(x) + (':' + ','.join(['1'] * len(x[1])) if rigid else '') for x in (rc if rc is not None else roled)]
        ns = argparse.Namespace(mmd=base, out=os.path.join(tmp, out or f'follow{counter[0]}.MMD'), type=t, slots=sl, step=st, force=force,
                                chains=chs, sway=[] if rigid else [0, 1], rigid=rigid)
        followthrough.run(ns)
        return ns.out
    forced = [x for x in roled if set(x[1]) & set(force)]            # a tail that is not mapped: its layered idle goes, in every clip
    if not EXTRAS:
        if forced:
            f_out = run(slots, STEP, rc=forced, rigid=True)
            if SZ(f_out) <= limit:
                rep['follow'] = f'{len(forced)} unmapped chains made rigid'
                return f_out
        rep['follow'] = 'off'
        return base
    if forced:
        f_out = run(slots, STEP, rc=forced, rigid=True)                  # rigid with its parent: the old keys go, almost nothing is added
        if SZ(f_out) <= limit:
            base = f_out
            rep['follow_forced'] = f'{len(forced)} chains made rigid in {len(slots)} slots'
    out = run(slots, STEP)
    if SZ(out) > limit:
        out = run(slots, 4)
    if SZ(out) > limit:
        # the slots that matter most first, as many as the room allows (each one's cost measured alone, at keys every 3 ticks)
        order = [0, 1, 4, 5, 7, 8, 9, 10, 11, 12, 13, 2, 3] + [x for x in slots if x not in (0, 1, 4, 5, 7, 8, 9, 10, 11, 12, 13, 2, 3)]
        room = limit - SZ(base)
        chosen, used = [], 0
        for s_ in [x for x in order if x in slots]:
            c = SZ(run([s_], STEP, out='one.MMD')) - SZ(base)
            if used + max(c, 0) <= room * 0.95:
                chosen.append(s_); used += max(c, 0)
        while chosen:
            out = run(chosen, STEP)
            if SZ(out) <= limit:
                break
            chosen.pop()
        if not chosen:
            rep['follow'] = 'no room'; return base
        rep['follow_slots'] = f'{len(chosen)} of {len(slots)}'
    rep['follow'] = f'{len(chains)} chains'
    return out


# Arms the donor cannot drive and the model's own pose holds out of place: copied, mirrored, from the other arm (armmirror.py).
# "dst S,E,W : src S,E,W". limbmap does not find these arms (Stingmon's body is not mirrored in its rest pose: it takes the antennae for them).
MIRROR_ARMS = {187: ['13,14,15:13,14,15', '17,18,19:13,14,15']}       # Stingmon: the left arm is held back and up in its source idle, in every clip with any donor


ARM_FLAT = 0.2


def mirror_stage(sp, rep, cur, tmp, own, step, spec=None):
    """The arms in MIRROR_ARMS copy their partner, mirrored, in the slots the source game does not animate itself."""
    pairs = MIRROR_ARMS.get(sp['id'])
    if not pairs:
        return cur
    t = sp['id']; m = mmd.MMD.load(cur, t)
    limit = max(BUFFER, SZ(cur))
    slots = [s_ for s_ in range(0x2e) if s_ < len(m.anims.table) and m.anims.table[s_] is not None and s_ not in own]
    cur = make_room(sp, cur, tmp, limit - 9000)
    for st in (max(step, STEP), 4, 2):
        ns = argparse.Namespace(mmd=cur, out=os.path.join(tmp, 'mirror.MMD'), type=t, pairs=pairs, slots=slots, step=st, flat=ARM_FLAT)
        armmirror.run(ns)
        if SZ(ns.out) <= limit:
            rep['mirror'] = f'{len(pairs)} arm(s) copy the other, mirrored ({len(slots)} slots)'
            return ns.out
    rep['mirror'] = 'does not fit the buffer'
    return cur


def arm_stage(sp, rep, cur, m, nb, skel, legs, slots, tmp, step, size0):
    """Arms that do not move in the walk swing against the opposite leg (armswing.py)."""
    t = sp['id']
    if len(legs) != 2:
        return cur
    cm = mmd.MMD.load(cur, t)
    pos = rest_of(cm, nb, skel)
    leg_bones = set()
    for h, k, a, dh, da, *_ in legs:
        stack = [h]
        while stack:
            b = stack.pop(); leg_bones.add(b)
            stack += [c for c in range(1, nb) if skel[c][1] == b]
    arms = arms_of(skel, pos, leg_bones)
    if len(arms) != 2:
        rep['arms'] = 'none found'; return cur
    # already swinging? the hand's fore-aft travel against the shoulder over the walk cycle, as a share of the arm's length
    poses, _, _ = animsheet.slot_frames(cm, nb, 2)
    rng, series = [], []
    for sh, el, x in arms:
        hand = el                                    # the elbow: if the shoulder does not swing, it does not travel
        zs = []
        for p_ in poses:
            q = retarget.world_pos(skel, p_)
            zs.append(q[hand][2] - q[sh][2])
        L = math.sqrt(sum((pos[hand][i] - pos[sh][i]) ** 2 for i in range(3))) or 1
        rng.append((max(zs) - min(zs)) / L); series.append(zs)
    move = max(rng)
    za, zb = series
    ma, mb = sum(za) / len(za), sum(zb) / len(zb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(za, zb))
    corr = cov / (math.sqrt(sum((x - ma) ** 2 for x in za) * sum((y - mb) ** 2 for y in zb)) or 1)
    rep['arm_swing'] = round(move, 2); rep['arm_corr'] = round(corr, 2)
    if move > 0.45 and corr < -0.3:                   # both arms already swing, against each other
        rep['arms'] = 'already swing'; return cur
    legpos = {l[2]: pos[l[2]][0] for l in legs}
    spec = []
    for s_, e_, x in arms:
        opp = min(legs, key=lambda l: pos[l[2]][0] * (1 if x > 0 else -1))      # the leg on the other side
        spec.append(f'{s_},{e_}:{opp[0]},{opp[2]}')
    ns = argparse.Namespace(mmd=cur, out=os.path.join(tmp, 'arms.MMD'), type=t, arms=spec, slots=slots, amp=0.45, step=step)
    armswing.run(ns)
    if SZ(ns.out) > max(BUFFER, size0):
        ns.step = 2; armswing.run(ns)
        if SZ(ns.out) > max(BUFFER, size0):
            rep['arms'] = 'does not fit the buffer'; return cur
    rep['arms'] = f'swing {spec}'
    return ns.out


def own_legs(m, nb, skel):
    """When the donor pairing failed: the model's own two feet, with a hip above them, enough to time an arm swing."""
    pos = rest_of(m, nb, skel)
    f = feet_of(skel, pos)
    if len(f) != 2:
        return None
    legs = []
    for a in f:
        k = skel[a][1]; h = skel[k][1] if k > 0 and skel[k][1] > 0 else k
        if k < 1:
            return None
        legs.append((h, k, a, 0, 0, 0))
    return legs


def polish(sp, out, spec=None, final=None):
    rep = dict(id=sp['id'], name=sp['name'], model=os.path.relpath(sp['model'], ROOT), polished=False)
    e = mmd.exe(); t = sp['id']; CUR_TYPE[0] = t
    os.makedirs(os.path.join(out, 'tmp'), exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='wp-', dir=os.path.join(out, 'tmp'))
    final = final or os.path.join(out, f'{t}-{sp["name"]}.MMD')
    try:
        nb, skel = e.bone_count[t], e.skeleton[t]
        m = mmd.MMD.load(sp['model'], t)
        size0 = SZ(sp['model'])

        if t in ANATOMY_ABSTAIN:
            rep.update(polished=False, why=f'anatomy review required: {ANATOMY_ABSTAIN[t]}')
            shutil.copy(sp['model'], final)
            return rep

        donor = {}

        def finish(cur, legs, slots, step=1):
            has_walk = len(m.anims.table) > 2 and m.anims.table[2] is not None
            if has_walk and legs and rep.get('polished'):
                try:
                    cur = root_stage(sp, rep, cur, slots, tmp)
                except Exception as ex:
                    rep['root'] = f'error: {type(ex).__name__}: {ex}'
            if has_walk and donor.get('t'):
                try:
                    own_ = {int(x, 0) if isinstance(x, str) else int(x) for x in ((spec or {}).get('clips') or {})} | set((spec or {}).get('_own', [])) \
                        | {0x21, 0x28, 0x29, 0x2a, 0x2b, 0x2c}
                    cur = match_stage(sp, rep, cur, tmp, own_, donor['t'], donor['path'], step)
                except Exception as ex:
                    rep['armmatch'] = f'error: {type(ex).__name__}: {ex}'
            if EXTRAS and has_walk and legs:
                try:
                    cur = arm_stage(sp, rep, cur, m, nb, skel, legs, slots, tmp, step, size0)
                except Exception as ex:
                    rep['arms'] = f'error: {type(ex).__name__}: {ex}'
            if has_walk:
                try:
                    own = {int(x, 0) if isinstance(x, str) else int(x) for x in ((spec or {}).get('clips') or {})} | set((spec or {}).get('_own', [])) \
                        | {0x21, 0x28, 0x29, 0x2a, 0x2b, 0x2c}
                    if EXTRAS:
                        cur = eat_stage(sp, rep, cur, tmp, own, step)
                    cur = posture_stage(sp, rep, cur, tmp, own, step)
                    if donor.get('t'):
                        cur = fx_stage(sp, rep, cur, tmp, own, step, donor['t'])
                    cur = follow_stage(sp, rep, cur, tmp, own, step, spec)
                    cur = mirror_stage(sp, rep, cur, tmp, own, step, spec)
                except Exception as ex:
                    rep['follow'] = f'error: {type(ex).__name__}: {ex}'
            shutil.copy(cur, final)
            return rep

        spec = spec or spec_of(sp)
        if not spec:
            rep['why'] = 'no spec (donor unknown)'; return finish(sp['model'], own_legs(m, nb, skel), WALK_SLOTS)
        dt = int(spec['source']['type']); rep['donor'] = dt; rep['donor_name'] = species.originals().rec[dt]['para']['name']
        dnb, dskel = e.bone_count[dt], e.skeleton[dt]
        O = species.originals(); dpath = O.model_path(dt); dm = mmd.MMD.load(dpath, dt)
        donor.update(t=dt, path=dpath)
        rep['has_walk'] = len(m.anims.table) > 2 and m.anims.table[2] is not None
        slots = [s for s in WALK_SLOTS if s < len(m.anims.table) and m.anims.table[s] is not None and dm.anims.table[s] is not None]
        if not rep['has_walk']:
            rep['why'] = 'no walk slot'; return finish(sp['model'], None, slots)
        own_l = {int(x, 0) if isinstance(x, str) else int(x) for x in ((spec or {}).get('clips') or {})} | set((spec or {}).get('_own', [])) | {0x21, 0x28, 0x29, 0x2a, 0x2b, 0x2c}
        # the legs follow the donor's feet in every everyday clip, not only the walk: its stance (a puppet's legs together against an ogre's apart)
        leg_slots = [s_ for s_ in range(0x2e) if s_ < len(m.anims.table) and m.anims.table[s_] is not None and s_ < len(dm.anims.table)
                     and dm.anims.table[s_] is not None and s_ not in own_l]
        legs, why = leg_plan(sp, spec, m, nb, skel, dt, dm, dnb, dskel)
        if not legs:
            rep['why'] = why; return finish(sp['model'], own_legs(m, nb, skel), slots)
        rep['legs'] = legs
        support_feet = FEET.get(t)
        before, lift0 = stance_slip(sp['model'], t, sp['tex'], feet=support_feet)
        rep['slip_before'] = round(before, 1)
        best = None
        rs = float(spec.get('root_scale') or 1.0)
        for step in (STEP, 4, 2):                   # keys as far apart as the orientation allows; closer ones when the file does not fit
            for f in (1.0, 1.15, 1.3):
                ns = argparse.Namespace(mmd=sp['model'], out=os.path.join(tmp, 'ik.MMD'), type=t, donor=dpath, dtype=dt,
                                        legs=[f'{h},{k},{a}:{dh},{da},{tip}' for h, k, a, dh, da, tip in legs], slots=leg_slots, k=rs * f, neutral=True, stance=True, step=step, walk_slots=WALK_SLOTS,
                                        rest=os.path.join(ROOT, spec['native']) if spec.get('native') else None)
                legik.run(ns)
                fa = argparse.Namespace(mmd=ns.out, out=os.path.join(tmp, f'f{step}-{f}.MMD'), type=t, slots=leg_slots, feet=[l[2] for l in legs], step=step, lift=FOOT_LIFT, ref=sp['model'])
                footfix.plant(fa)
                size = SZ(fa.out)
                if size > max(BUFFER, size0):
                    continue
                slip, lift = stance_slip(fa.out, t, sp['tex'], feet=support_feet)
                if best is None or slip < best[0]:
                    best = (slip, f, fa.out, size, lift, step)
            if best is not None:
                break
        if best is None:
            rep['why'] = 'does not fit the buffer'; return finish(sp['model'], legs, slots)
        own_path = os.path.join(ROOT, spec['native']) if spec.get('native') else sp['model']
        t_own = thigh_swing(own_path, t, legs)
        if thigh_swing(best[2], t, legs) > t_own + 15:         # the knees rise far above the model's own: a shorter stride until they do not (or the least)
            tries = []
            for f in (0.85, 0.7, 0.55):
                ns = argparse.Namespace(mmd=sp['model'], out=os.path.join(tmp, 'ik.MMD'), type=t, donor=dpath, dtype=dt,
                                        legs=[f'{h},{k},{a}:{dh},{da},{tip}' for h, k, a, dh, da, tip in legs], slots=leg_slots, k=rs * f, neutral=True, stance=True, step=best[5], walk_slots=WALK_SLOTS,
                                        rest=os.path.join(ROOT, spec['native']) if spec.get('native') else None)
                legik.run(ns)
                fa = argparse.Namespace(mmd=ns.out, out=os.path.join(tmp, f'k{f}.MMD'), type=t, slots=leg_slots, feet=[l[2] for l in legs], step=best[5], lift=FOOT_LIFT, ref=sp['model'])
                footfix.plant(fa)
                if SZ(fa.out) > max(BUFFER, size0):
                    continue
                sl_, li_ = stance_slip(fa.out, t, sp['tex'], feet=support_feet)
                tries.append((thigh_swing(fa.out, t, legs), sl_, f, fa.out, SZ(fa.out), li_, best[5]))
                if tries[-1][0] <= t_own + 15:
                    break
            if tries:
                th, sl_, f_, o_, z_, li_, st_ = min(tries, key=lambda x: x[0])
                if th < thigh_swing(best[2], t, legs):
                    best = (sl_, f_, o_, z_, li_, st_); rep['knee_stride'] = f_
        slip, f, path, size, lift, step = best
        rep['step'] = step
        rep.update(slip_after=round(slip, 1), scale=round(rs * f, 3), size_before=size0, size_after=size, lift=round(lift))
        better = slip <= before or (lift >= 1.8 * lift0 and slip <= 1.1 * before)      # not sliding more (the legs follow the donor's feet and stance), or feet that hardly moved now lift
        t_before = thigh_swing(sp['model'], t, legs); t_after = thigh_swing(path, t, legs)
        rep.update(thigh_own=round(t_own), thigh_before=round(t_before), thigh_after=round(t_after))
        if not better and t_before - t_own > 25 and t_after < t_before - 15 and slip <= 2.0 * before:
            better = True; rep['why_ok'] = 'knees: the donor lifts the thigh much higher than the model does'     # (slip gives way to knees that rise above the hip)
        lb, la = leg_swings(sp['model'], t, legs), leg_swings(path, t, legs)
        rep.update(swing_before=[round(x) for x in lb], swing_after=[round(x) for x in la])
        if not better and min(lb) < 0.4 * max(lb) and min(la) > 1.5 * min(lb) and slip <= 2.0 * before:
            better = True; rep['why_ok'] = 'a leg that hardly walked now walks'
        anatomy_ok = support_feet is None or slip <= EXPLICIT_SUPPORT_SLIP_MAX
        ok = better and anatomy_ok and size <= max(BUFFER, size0)
        rep['polished'] = ok
        if not ok:
            rep['why'] = ('reviewed support feet still slide too far' if better and not anatomy_ok else
                          'not better' if not better else 'does not fit the buffer')
        return finish(path if ok else sp['model'], legs, slots, step if ok else 1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def work(args):
    sp, out = args
    try:
        r = polish(sp, out)
    except Exception as ex:
        r = dict(id=sp['id'], name=sp['name'], polished=False, why=f'error: {type(ex).__name__}: {ex}')
    if not os.path.exists(os.path.join(out, f'{sp["id"]}-{sp["name"]}.MMD')):      # an error before anything was written
        os.makedirs(out, exist_ok=True)
        shutil.copy(sp['model'], os.path.join(out, f'{sp["id"]}-{sp["name"]}.MMD'))
    return r


def DN(t):
    return species.originals().rec[t]['para']['name']


def source_game(sp):
    s = sp['source'].lower()
    if 'card battle' in s or s.startswith('dcb'):
        return 'Card Battle'
    if '2003' in s or s.startswith('dw3'):
        return 'DW2003'
    if 'world 2' in s or s.startswith('dw2'):
        return 'DW2'
    return 'import'


def video_job(args):
    sp, out, vids = args
    t = sp['id']; e = mmd.exe()
    spec = spec_of(sp)
    if not spec:
        return sp['id'], 'no spec'
    dt = int(spec['source']['type'])
    fixed = os.path.join(out, f'{t}-{sp["name"]}.MMD')
    rep = sp.get('rep', {})
    tag = ('legs fixed' if rep.get('polished') else 'original legs') + (', arms added' if str(rep.get('arms', '')).startswith('swing') else '')
    O = species.originals()
    a = f'{fixed}:{t}:{sp["tex"]}::{sp["name"]} ({source_game(sp)}, {tag})'
    b = f'{O.model_path(dt)}:{dt}:::{DN(dt)} (donor, DW1 #{dt})'
    name = f'{t:03d}-{sp["name"]}_vs_{DN(dt)}.mp4'
    subprocess.run([sys.executable, os.path.join(HERE, 'animstudio.py'), 'video', os.path.join(vids, name), a, b, '--slot', '2', '--size', '300',
                    '--cycles', '3', '--panels', 'mesh:side,mesh:front,skel:side,gait'], check=True, capture_output=True)
    return sp['id'], name


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['one', 'all', 'videos']); ap.add_argument('id', nargs='?', type=int)
    ap.add_argument('--out', default=os.path.join(ROOT, 'build/walkfix')); ap.add_argument('--jobs', type=int, default=12)
    a = ap.parse_args()
    sps = [s for s in all_species() if a.cmd == 'all' or a.id is None or s['id'] == a.id]
    if a.cmd in ('one', 'all'):
        from multiprocessing import Pool
        with Pool(a.jobs if a.cmd == 'all' else 1) as pool:
            reps = pool.map(work, [(s, a.out) for s in sps], chunksize=1)
        with open(os.path.join(a.out, 'report.jsonl'), 'w') as f:
            for r in reps:
                f.write(json.dumps(r) + '\n')
                print(r['id'], r['name'], 'POLISHED' if r['polished'] else '-', r.get('slip_before', ''), r.get('slip_after', ''), r.get('why', ''))
        print(sum(r['polished'] for r in reps), 'of', len(reps), 'polished')
    else:
        reps = {}
        rp = os.path.join(a.out, 'report.jsonl')
        if os.path.exists(rp):
            reps = {r['id']: r for r in map(json.loads, open(rp))}
        vids = os.path.join(a.out, 'videos'); os.makedirs(vids, exist_ok=True)
        for s in sps:
            s['rep'] = reps.get(s['id'], {})
        from multiprocessing import Pool
        with Pool(a.jobs) as pool:
            for i, n in pool.imap_unordered(video_job, [(s, a.out, vids) for s in sps]):
                print(i, n, flush=True)


if __name__ == '__main__':
    main()
