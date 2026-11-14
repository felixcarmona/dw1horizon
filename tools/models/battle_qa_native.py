#!/usr/bin/env python3
"""Measured QA of the source game's battle clips put on a native binding's donor rig (native_battle.py, the recipe's
`battle_originals`).

battle_qa.py compares a final clip with the importer's clip bone by bone; a natively bound species has another
skeleton (the donor's, plus riders), so this tool compares what the eye sees: the mesh pieces. Every source piece is
found in the final model (the binding concatenates the pieces of a bone in the recipe's order; the vertex counts are
checked) and its fitting (an affine map from the source's local vertices to the final's, least squares) is measured
from the vertices themselves, not taken from the generator. Per slot, on the FINAL model (the provider's output):

  fidelity   orientation: per piece and tick, the angle between the final piece's world orientation (fitting
             rotation taken out) and the source piece's (both with the root's turn and travel taken out), weighted
             by the piece's spread about its centroid: the mean over the clip (FID_MEAN) and each piece's 95th
             percentile (FID_PIECE)
             end effectors: the tips of the source's limb chains (legs, arms, wings, tails, head), their centroid
             relative to the body joint, in heights of each model's own field idle, its motion about the clip's mean
             (the two skeletons differ in proportions, the motion must agree): the largest difference (FID_TIP)
  liveness   a source chain whose tip moves (LIVE_FLOOR) keeps at least LIVE_KEEP of that motion
  retime     a one-shot clip (hits, victory, faint, get up, techniques) resampled by more than RETIME (slow motion or
             a rush); idles repeat whole cycles, movements follow battle_restore's rule
  mesh, posture, motion   battle_qa.py's checks and thresholds on the final rig against main's same slot (the donor's
             clip): vertex step, loop seam, a piece leaving the body, triangle crossings, scale, body bones tipped,
             under the floor, floating, movement length, root excursion, frantic speed, still legs in a movement
A slot with a fidelity, liveness or retime flag fails; a mesh, posture or motion flag fails unless main's same slot
is no better (battle_qa.worse_than_main). A failing slot stays the donor's clip.

  tools/models/battle_qa_native.py check ID FINAL.MMD SOURCE.MMD MAIN.MMD [--slots ...] [--json OUT]
            SOURCE is the binding's source (the species' model before the binding, `edit.py get`; for a model bound
            offline, content/models/imports/bound-battle.json, the battle source the imports step writes as
            imported-models/ID.battle.MMD), FINAL and MAIN the provider's final model of this tree and of origin/main;
            exits 1 when a slot fails

Not proven by these numbers: how a clip reads, contact with the opponent, what the engine interpolates at 60 fps,
technique effects' timing beyond the slot length. Uses numpy.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'tools'), os.path.join(ROOT, 'tools', 'models')]

import battle_qa as Q  # noqa: E402

HARD = ('fidelity', 'live_base', 'retime', 'finite', 'length')   # flags that fail a slot outright
FID_MEAN = 8.0       # weighted mean piece orientation error over the clip (degrees)
FID_PIECE = 25.0     # a piece's 95th percentile orientation error (degrees), pieces of 2 % of the weight or more
FID_TIP = 0.15       # end-effector motion difference (heights)
LIVE_FLOOR = Q.LIVE_FLOOR
LIVE_KEEP = Q.LIVE_KEEP
RETIME = 1.6         # one-shot clips: resampled by at most this factor either way


def recipe_of(sid):
    return json.load(open(os.path.join(ROOT, 'content/models/imports/native-bindings.json')))[str(sid)]


def source_skeleton(sid):
    return json.load(open(glob.glob(os.path.join(ROOT, f'content/species/{sid}-*.json'))[0]))['model']['skeleton']


def piece_blocks(recipe, skeleton, source, final_rig, final):
    """{source bone: (final bone, vertex slice)}: the binding's order of the pieces on each bone
    (native_binding.bind)."""
    mapping = {int(k): v for k, v in recipe['map'].items()}
    mirrors = {int(k) for k in recipe.get('mirror', {})}
    riders = recipe.get('riders', [])
    spun = [int(b) for b in recipe['spin']['bones']] if recipe.get('spin') else []
    first_rider = len(final_rig) - len(riders)
    rider_of = {sb: first_rider + i for i, r in enumerate(riders) for sb in r['pieces']}
    spin_of = {sb: first_rider - len(spun) + i for i, sb in enumerate(spun)}
    used = {}
    out = {}
    for sb, tb in sorted(mapping.items(), key=lambda item: item[0] in mirrors):
        dest = rider_of.get(sb, spin_of.get(sb, tb))
        n = source.tmd.objects[skeleton[sb][0]].nvert
        start = used.get(dest, 0)
        out[sb] = (dest, slice(start, start + n))
        used[dest] = start + n
    for dest, n in used.items():
        obj = final_rig[dest][0]
        if obj < 0 or final.tmd.objects[obj].nvert != n:
            raise ValueError(f'bone {dest}: the pieces do not account for its vertices')
    return out


def polar(a):
    u, _, vt = np.linalg.svd(a)
    r = u @ vt
    if np.linalg.det(r) < 0:
        u[:, -1] *= -1
        r = u @ vt
    return r


def fits(blocks, skeleton, source, final_rig, final):
    """{source bone: (fitting rotation, weight, final local vertices, source local vertices)}."""
    out = {}
    for sb, (dest, sl) in blocks.items():
        x = np.array(source.tmd.obj_verts(skeleton[sb][0]), float)[:, :3]
        y = np.array(final.tmd.obj_verts(final_rig[dest][0]), float)[sl, :3]
        X = np.hstack([x, np.ones((len(x), 1))])
        A = np.linalg.lstsq(X, y, rcond=None)[0][:3].T
        out[sb] = (polar(A), float(((y - y.mean(0)) ** 2).sum()) + 1.0, y, x)
    return out


def body_world(frames, parents, yaw=None):
    """Rotations (F, nb, 3, 3) and joint positions (F, nb, 3) with the root's turn and travel taken out."""
    rig = Q.Rig(parents, {}, [], {})
    c = Q.Clip(rig, np.asarray(frames, float))
    R = c.Wb[..., :3, :3] / np.linalg.norm(c.Wb[..., :3, :3], axis=-2, keepdims=True)
    P = c.Wb[..., :3, 3]
    if yaw is not None:
        R = np.einsum('ij,fbjk->fbik', yaw, R)
        P = P @ yaw.T
    return R, P


def _source_chains(skeleton):
    rig = Q.Rig([p for _, p in skeleton], {b: [[0, 0, 0]] for b, (o, _) in enumerate(skeleton) if o >= 0}, [], {})
    return rig.chains()


def tips(skeleton):
    return [c['tip'] for c in _source_chains(skeleton)]


def limb_bones(skeleton):
    """{source bone: its limb chain (battle_qa.Rig.chains: legs, arms, tails, necks)} for the bones on one."""
    return {b: k for k, c in enumerate(_source_chains(skeleton)) for b in c['bones']}


def limb_carriers(carried, parents, limbs):
    """The final bones that hold only source limbs: every piece on the bone and on the bones below it that carry
    pieces comes from the same source limb chains (a donor hand holding an arm's head and its jaw; not a donor pelvis
    carrying a tail and the legs). `carried`: {final bone: source pieces}, `limbs`: limb_bones."""
    out = set()
    for b, pieces in carried.items():
        if not all(s in limbs for s in pieces):
            continue
        chains = {limbs[s] for s in pieces}
        below = [d for d in carried if b in _chain(parents, d)]
        if all(s in limbs and limbs[s] in chains for d in below for s in carried[d]):
            out.add(b)
    return out


def fidelity(F, S, fit, blocks, leads, tip_bones, hips, heights):
    """Numbers of one slot: orientation errors and end-effector motion differences, for the final clip F against the
    retimed source clip S ((rotations, positions) of each). Only lead pieces (the ones their bone follows) count; a
    piece carried rigidly on another's bone is the binding's limit, the same in every clip: its error is reported."""
    RF, PF = F
    RS, PS = S
    n = min(len(RF), len(RS))
    errs, weights, per_piece, carried = [], [], {}, {}
    for sb, (q, w, y, x) in fit.items():
        e = Q.angle(RF[:n, blocks[sb][0]] @ q, RS[:n, sb])
        if sb not in leads:
            carried[sb] = round(float(np.percentile(e, 95)), 1)
            continue
        per_piece[sb] = (float(np.percentile(e, 95)), w)
        errs.append(e)
        weights.append(w)
    W = np.array(weights) / sum(weights)
    mean = float((np.array([e.mean() for e in errs]) * W).sum())
    worst = max(((v, sb) for sb, (v, w) in per_piece.items() if w / sum(weights) >= 0.02), default=(0.0, -1))
    tip_err, amps = {}, {}
    for sb in tip_bones:
        if sb not in fit or sb not in leads:
            continue
        dest = blocks[sb][0]
        q, w, y, x = fit[sb]
        cf = np.einsum('fij,j->fi', RF[:n, dest], y.mean(0)) + PF[:n, dest] - PF[:n, hips[1]]
        cs = np.einsum('fij,j->fi', RS[:n, sb], x.mean(0)) + PS[:n, sb] - PS[:n, hips[0]]
        df, ds = (cf - cf.mean(0)) / heights[1], (cs - cs.mean(0)) / heights[0]
        tip_err[sb] = float(np.linalg.norm(df - ds, axis=1).max())
        amps[sb] = (float(np.linalg.norm(ds, axis=1).max()), float(np.linalg.norm(df, axis=1).max()))
    return dict(rot_mean=mean, rot_worst_piece=[round(worst[0], 1), worst[1]], carried=carried,
                tip=max(tip_err.values(), default=0.0), tip_bone=max(tip_err, key=tip_err.get) if tip_err else -1,
                amps=amps)


def lead_pieces(blocks, skeleton, recipe, first_rider):
    """The source pieces their final bone follows (native_battle.context's rule)."""
    from tools.models.field_animations import native_battle
    pivots = {first_rider + i: r['pivot'] for i, r in enumerate(recipe.get('riders', []))}
    groups = {}
    for sb, (dest, _) in blocks.items():
        groups.setdefault(dest, set()).add(sb)
    fixed = native_battle.fixed_pieces(recipe)
    out = set()
    for dest, group in groups.items():
        out |= {pivots[dest]} if dest in pivots else set(native_battle.lead_tops(group, skeleton, fixed))
    return out


def bound(sid, final_data, source_data):
    """The pieces of a model bound offline (bound_battle.py, content/models/imports/bound-battle.json) -> (source
    skeleton, final rig, parsed final and source, blocks, fits, lead pieces, source-to-final map)."""
    import mmd
    from tools.models.field_animations import bound_battle
    recipe = bound_battle.rows()[str(sid)]
    spec = bound_battle.binding_spec(recipe)
    rig = [list(b) for b in json.load(open(glob.glob(os.path.join(ROOT, f'content/species/{sid}-*.json'))[0]))['model']['skeleton']]
    mmd.exe().add_type(int(sid), rig)
    final = mmd.MMD.parse(final_data, len(rig))
    source = bound_battle.source_model(source_data, spec)
    blocks, fit, leads, mapping, skeleton, _ = bound_battle.binding(recipe, spec, source, final, rig)
    blocks = {sb: (tb, slice(start, start + n)) for sb, (tb, start, n) in blocks.items()}
    fit = {sb: (np.array(q), w, np.array(y, float), np.array(x, float)) for sb, (q, w, y, x) in fit.items()}
    return skeleton, rig, final, source, blocks, fit, {s for group in leads.values() for s in group}, mapping


def source_frames(source, ns, slot, final_frames):
    """The source clip of a slot resampled tick for tick onto the final clip, whose length a binding may set
    (battle_originals.ticks): measured on main's length the two timelines would not line up."""
    from tools.models.field_animations import native_battle
    sfr, _, _, tile = native_battle.source_clip(source, ns, slot, len(final_frames[0]))
    return sfr, tile


def check(sid, final_data, source_data, main_data, slots=None):
    import animsheet
    import mmd
    from tools.models.field_animations import bound_battle, native_battle
    if str(sid) in bound_battle.rows():
        recipe = {}
        skeleton, final_rig, final, source, blocks, fit, leads, mapping = bound(sid, final_data, source_data)
        ns, parents, rider_of = len(skeleton), [p for _, p in final_rig], {}
        main = mmd.MMD.parse(main_data, len(parents))
    else:
        recipe = recipe_of(sid)
        skeleton = source_skeleton(sid)
        ns = len(skeleton)
        # the final rig: the donor's (plus riders and spinning bones) as the binding writes it
        mmd.exe().add_type(int(sid), skeleton)
        donor_rig = list(mmd.exe().skeleton[recipe['donor']])
        extra = []
        if recipe.get('spin'):
            extra += [(-1, recipe['map'][b]) for b in recipe['spin']['bones']]
        names = {}
        for k, r in enumerate(recipe.get('riders', [])):
            names[r['name']] = len(donor_rig) + len(extra) + k
        for r in recipe.get('riders', []):
            extra.append((-1, names.get(r['parent'], r['parent'])))
        parents = [p for _, p in donor_rig] + [p for _, p in extra]
        final = mmd.MMD.parse(final_data, len(parents))
        main = mmd.MMD.parse(main_data, len(parents))
        source = mmd.MMD.parse(source_data, ns)
        # the object of each bone, as the final model's TMD numbers them (bones with pieces, in order)
        objs, k = [], 0
        counts = {}
        mapping = {int(a): b for a, b in recipe['map'].items()}
        riders = recipe.get('riders', [])
        first_rider = len(parents) - len(riders)
        rider_of = {sb: first_rider + i for i, r in enumerate(riders) for sb in r['pieces']}
        spun = [int(b) for b in recipe['spin']['bones']] if recipe.get('spin') else []
        spin_of = {sb: len(donor_rig) + i for i, sb in enumerate(spun)}    # spinning drums: bones of their own
        for sb, tb in mapping.items():
            counts[rider_of.get(sb, spin_of.get(sb, tb))] = 1
        for b in range(len(parents)):
            objs.append(k if b in counts else -1)
            k += b in counts
        final_rig = [[o, p] for o, p in zip(objs, parents)]
        blocks = piece_blocks(recipe, skeleton, source, final_rig, final)
        fit = fits(blocks, skeleton, source, final_rig, final)
        leads = lead_pieces(blocks, skeleton, recipe, first_rider)
    tip_bones = tips(skeleton)
    bones_final = final_rig
    Fr = Q.Rig.from_mmd(final_data, bones_final)
    Mr = Q.Rig.from_mmd(main_data, bones_final)
    Sr = Q.Rig.from_mmd(source_data, skeleton)
    ref, ref_s = Q.reference(Mr), Q.reference(Sr)
    # posture: only body bones that draw something or carry bones that do (a donor bone left without pieces is not
    # seen); the reference elevations are recomputed for them
    # nor bones that hold only source limbs, or lead only to such bones: a hand with fingers is no chain of the donor
    # rig (it branches) but holds what the source swings as a limb (an arm's head), whose clip the fidelity numbers
    # measure
    limbs = limb_bones(skeleton)
    carried = {}
    for sb, (dest, _) in blocks.items():
        carried.setdefault(dest, set()).add(sb)
    seen = set(Fr.meshed) - limb_carriers(carried, parents, limbs)
    shown = [b for b in ref['body'] if b in seen or any(b in _chain(parents, d) for d in seen)]
    idle = Q.Clip(Mr, *Mr.frames(0))
    ref['body'] = shown
    ref['body_elev'] = Q.elevation(idle.Wb[:, shown, :3, :3]).mean(0) if shown else np.zeros(0)
    yaw = None
    if recipe.get('source_yaw'):
        a = np.radians(recipe['source_yaw'])
        yaw = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    hips_source = min(mapping, key=lambda s: (_depth(skeleton, s), s))
    hips = (hips_source, rider_of.get(hips_source, mapping[hips_source]))
    field = {s: Q.measure(Q.Clip(Mr, *Mr.frames(s)), ref) for s in Q.FIELD_MOVES if Mr.frames(s) is not None}
    rows = {}
    slots = slots or [s for s in list(Q.BATTLE) + list(range(40, 45)) + list(range(46, 46 + 15))
                      if s < len(main.anims.table) and main.anims.table[s] is not None
                      and s < len(source.anims.table) and source.anims.table[s] is not None]
    for s in slots:
        fF, fM = Fr.frames(s), Mr.frames(s)
        same_main = np.array_equal(fF[0], fM[0]) if fF[0].shape == fM[0].shape else False
        sfr, tile = source_frames(source, ns, s, fF)
        sfr = np.array(sfr, float)
        src_len = len(animsheet.slot_frames(source, ns, s)[0])
        src = body_world(sfr, [p for _, p in skeleton], yaw)
        fidF = fidelity(body_world(fF[0], parents), src, fit, blocks, leads, tip_bones, hips, (ref_s['h'], ref['h']))
        fidM = fidelity(body_world(fM[0], parents), src, fit, blocks, leads, tip_bones, hips, (ref_s['h'], ref['h']))
        looping = s in Q.BATTLE
        mF, mM = Q.measure(Q.Clip(Fr, *fF), ref), Q.measure(Q.Clip(Mr, *fM), ref)
        mA = Q.measure(Q.Clip(Sr, *Sr.frames(s)), ref_s)
        g = 1 if s in Q.MOVES else 0
        flags = []

        def flag(key, msg):
            flags.append((key, msg))
        if not same_main:
            if fidF['rot_mean'] > FID_MEAN:
                flag('fidelity', f'pieces turned {fidF["rot_mean"]:.1f} deg off the source on average (main '
                                 f'{fidM["rot_mean"]:.1f})')
            if fidF['rot_worst_piece'][0] > FID_PIECE:
                flag('fidelity', f'piece {fidF["rot_worst_piece"][1]} {fidF["rot_worst_piece"][0]} deg off (95th pct)')
            if fidF['tip'] > FID_TIP:
                flag('fidelity', f'tip of {fidF["tip_bone"]} moves {fidF["tip"]:.3f} h off the source (main '
                                 f'{fidM["tip"]:.3f})')
            for sb, (a_s, a_f) in fidF['amps'].items():
                if a_s > LIVE_FLOOR and a_f < LIVE_KEEP * a_s:
                    flag('live_base', f'chain to {sb} still: {a_f:.3f} h, source {a_s:.3f}')
            if s not in Q.BATTLE and not (1 / RETIME <= len(fF[0]) / src_len <= RETIME):
                flag('retime', f'resampled from {src_len} to {len(fF[0])} ticks')
        if s in Q.MOVES and field:
            for ch in ref['chains']:
                t = ch['tip']
                fa = max(m['chain_amp'][t] for m in field.values())
                sib = [mF['chain_amp'][c['tip']] for c in ref['chains'] if c['tip'] != t and c['kind'] == ch['kind']]
                if (fa > Q.FIELD_SWING and mF['chain_amp'][t] < Q.STILL_RATIO * fa and sib
                        and mF['chain_amp'][t] < Q.SIBLING_RATIO * max(sib)):
                    flag('live_field', f'{ch["kind"]} {ch["bones"]} still: {mF["chain_amp"][t]:.3f} h')
        if not mF['finite']:
            flag('finite', 'non-finite numbers')
        if (looping and mF['jump'] > Q.JUMP_MAX[g]) or mF['jump'] > 1.25 * max(mA['jump'], mM['jump']) + 0.05:
            flag('jump', f'vertex step {mF["jump"]:.3f} h a tick (source {mA["jump"]:.3f}, main {mM["jump"]:.3f})')
        if looping and mF['seam'] > Q.SEAM_MAX and mF['seam'] > mM['seam'] + 0.01:
            flag('seam', f'loop seam {mF["seam"]:.3f} h')
        if mF['tear'][0] > Q.TEAR_MAX:
            flag('tear', f'piece {mF["tear"][1]} leaves the body by {mF["tear"][0]:.3f} h at tick {mF["tear"][2]}')
        if mF['cross'][0] > Q.CROSS_RATIO * ref['cross'] + Q.CROSS_ADD and mF['cross'][0] > mM['cross'][0] + Q.CROSS_ADD:
            flag('cross', f'crossings {mF["cross"][0]:.0f} a tick (field idle {ref["cross"]:.0f}, '
                          f'main {mM["cross"][0]:.0f})')
        tipped = mF['body_off'] > Q.BODY_MAX and mF['body_off'] > mM['body_off'] + Q.BODY_WORSE
        if mF['body_off'] > Q.BODY_ABS[g] or tipped:
            flag('body_off', f'body bone {mF["body_bone"]} tipped {mF["body_off"]:.0f} deg (main {mM["body_off"]:.0f})')
        if mF['sink'] > Q.SINK_MAX and mF['sink'] > mM['sink'] + Q.WORSE:
            flag('sink', f'under the floor {mF["sink"]:.3f} h (main {mM["sink"]:.3f})')
        if mF['lift_min'] > Q.FLOAT_MAX and mF['lift_min'] > mM['lift_min'] + Q.WORSE:
            flag('lift_min', f'floating {mF["lift_min"]:.3f} h (main {mM["lift_min"]:.3f})')
        if s in Q.MOVES and mF['n'] != mM['n']:
            flag('length', f'length {mF["n"]} ticks (main {mM["n"]})')
        if s in Q.MOVES and mF['root_exc'] > Q.LUNGE_MAX and mF['root_exc'] > mM['root_exc'] + Q.LUNGE_WORSE:
            flag('root_exc', f'root excursion {mF["root_exc"]:.2f} h (main {mM["root_exc"]:.2f})')
        if mF['speed'] > Q.SPEED_MAX[g] and mF['speed'] > Q.FRANTIC * mM['speed']:
            flag('speed', f'frantic: {mF["speed"]:.1f} deg a tick (main {mM["speed"]:.1f})')
        for m in (mF, mM, mA):
            m.pop('scale', None)
            m.pop('bone_range', None)
        row = dict(keys=[k for k, _ in flags], flags=[m for _, m in flags], own=[False]*len(flags), final=mF, main=mM,
                   source_clip=mA, fidelity=fidF, fidelity_main=fidM, same_main=same_main, source_ticks=src_len,
                   ticks=len(fF[0]), main_ticks=len(fM[0]))
        hard = [m for k, m in flags if k in HARD]
        others = [(k, m) for k, m in flags if k not in HARD]
        soft = Q.worse_than_main(dict(row, keys=[k for k, _ in others], flags=[m for _, m in others],
                                      own=[False] * len(others)))
        row['verdict'] = 'main' if same_main else ('fail' if hard or soft else ('kept' if flags else 'pass'))
        rows[s] = row
    return rows


def _chain(parents, b):
    out = set()
    while parents[b] >= 0:
        b = parents[b]
        out.add(b)
    return out


def _depth(skeleton, b):
    return 0 if skeleton[b][1] < 0 else 1 + _depth(skeleton, skeleton[b][1])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    c.add_argument('sid')
    c.add_argument('final')
    c.add_argument('source')
    c.add_argument('main')
    c.add_argument('--slots', nargs='*', type=int)
    c.add_argument('--json')
    a = ap.parse_args()
    rd = lambda p: open(p, 'rb').read()
    rows = check(a.sid, rd(a.final), rd(a.source), rd(a.main), a.slots)
    for s, r in rows.items():
        f = r['fidelity']
        print(f'slot {s:#x}: {r["verdict"]} rot {f["rot_mean"]:.1f} (main {r["fidelity_main"]["rot_mean"]:.1f}) tip '
              f'{f["tip"]:.3f} (main {r["fidelity_main"]["tip"]:.3f}) ticks {r["source_ticks"]}->{r["ticks"]} '
              + '; '.join(r['flags']))
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(rows, fh, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o))
    sys.exit(1 if any(r['verdict'] == 'fail' for r in rows.values()) else 0)


if __name__ == '__main__':
    main()
