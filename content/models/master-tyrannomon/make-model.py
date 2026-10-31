#!/usr/bin/env python3
"""MasterTyrannomon partner model: TIRS mesh + Tyrannomon's animations scaled by 1.5.

Field NPCs use disc-derived twins; this output supplies the partner only.

MasterTyrannomon (type 124, TIRS.MMD) and Tyrannomon (type 8, TYRA.MMD) share the
skeleton (DIGIMON_SKELETONS 0x8011c25c, 27 bones), but TIRS is built exactly 1.5 times
larger: every bone offset of its rest pose is 1.5 times Tyrannomon's (hips -330 vs -220).
A plain `mmd.py transplant` would pose the big pieces with Tyrannomon's short offsets.

So every distinct TYRA animation is played tick by tick like the engine (mmd.AnimPlayer),
all translations (bone offsets and bone 0's root motion) are multiplied by 1.5, and the
result is re-encoded exactly (tol 0, loops, sounds and texture moves kept) and checked by
playing it again. Rotations and scales are untouched, so the pose is Tyrannomon's motion
at MasterTyrannomon's size. TIRS's eye frames sit at the same texture rectangles as
TYRA's (open 11, narrowed 19, half-closed 27, closed 35; destination 52,8), so the
texture instructions are kept as they are.

Usage (from the repository root):
  python3 content/models/master-tyrannomon/make-model.py [OUT.MMD]
default OUT: build/models/TIRS-partner.MMD
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import mmd  # noqa: E402

SCALE = 1.5
MESH = os.path.join(ROOT, 'extracted/CHDAT/MMD4/TIRS.MMD')
ANIM = os.path.join(ROOT, 'extracted/CHDAT/MMD0/TYRA.MMD')
PARTNER_MODEL_BUFFER = 0x18800


def play(anim, nb, slot):
    """Per-tick samples like gltf_anim_samples: bone 0 tx..tz = root motion accumulated in
    bone 0's own frame (integers), other bones their pose. Returns (samples, loop, events)."""
    p = mmd.AnimPlayer(anim, nb, slot)
    out, root = [], [0, 0, 0]
    while len(out) < 6000 and p.tick(stop_at_infinite_loop=True):
        root = [r + b for r, b in zip(root, p.base)]
        snap = [list(v) for v in p.pose]
        snap[0][6:9] = list(root)
        out.append(snap)
    if any(r != 0 for r in p.pose[0][3:6]):
        raise SystemExit(f'slot {slot:#x}: bone 0 rotates; root motion would need its R·S')
    events = []
    for k, kind, c in p.events:
        if kind == 'sound':
            events.append((k, 'sound', dict(bank=c['bank'], note=c['note'])))
        elif kind == 'tex':
            events.append((k, 'tex', dict(src=c['src'], size=c['size'], dst=c['dst'])))
        else:
            raise SystemExit(f'slot {slot:#x}: {kind}')
    return out, p.loop_sample(), events


def evkey(ev):
    return sorted((k, kind, sorted(c.items())) for k, kind, c in ev)


def scaled(samples):
    return [[v[:6] + [round(x * SCALE) for x in v[6:9]] for v in s] for s in samples]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build/models/TIRS-partner.MMD')
    e = mmd.exe()
    mesh = mmd.MMD.load(MESH)
    anim = mmd.MMD.load(ANIM)
    assert e.skel_ptr[mesh.type] == e.skel_ptr[anim.type], 'different skeletons'
    nb = e.bone_count[anim.type]
    # check the premise: TIRS's rest pose is TYRA's at 1.5 times
    pa = mesh.anims.anims[mesh.anims.table[0]].pose
    pb = anim.anims.anims[anim.anims.table[0]].pose
    for b, (x, y) in enumerate(zip(pa, pb), 1):
        for u, v in zip(x[-3:], y[-3:]):
            assert abs(u - v * SCALE) <= 2, f'bone {b}: TIRS {x[-3:]} vs TYRA {y[-3:]}'
    # the slot through which each distinct animation is reached first (slots 0x23/0x24
    # cancel the root X motion; no animation is shared between them and another slot)
    first = {}
    for slot, idx in enumerate(anim.anims.table):
        if idx is not None:
            first.setdefault(idx, slot)
    sec = mmd.AnimSection()
    sec.table = list(anim.anims.table)
    for idx, a in enumerate(anim.anims.anims):
        slot = first.get(idx)
        if slot is None:
            sec.anims.append(a)
            continue
        smp, ls, ev = play(a, nb, slot)
        target = scaled(smp)
        mmd.close_loop(target, ls)
        new = mmd.encode_anim(target, nb, ls, ev, tol=0)
        back, ls2, ev2 = play(new, nb, slot)
        if slot in (0x23, 0x24):          # the engine drops root X there: compare without it
            for s in back + target:
                s[0][6] = 0
        if back != target or ls2 != ls or evkey(ev2) != evkey(ev):   # same-tick order is free
            bad = next(i for i, (x, y) in enumerate(zip(back, target)) if x != y) if back != target else '-'
            raise SystemExit(f'slot {slot:#x}: re-encoded animation differs (sample {bad}, '
                             f'{len(back)}/{len(target)} ticks, loop {ls2}/{ls})')
        sec.anims.append(new)
    out = mmd.MMD()
    out.tmd, out.anims = mesh.tmd, sec
    data = out.build()
    assert len(data) <= PARTNER_MODEL_BUFFER, f'{len(data)} bytes > PARTNER_MODEL_BUFFER'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, 'wb').write(data)
    print(f'{out_path}: TIRS mesh + {len(sec.anims)} TYRA animations x{SCALE} '
          f'({sum(x is not None for x in sec.table)} slots), {len(data)} bytes '
          f'(PARTNER_MODEL_BUFFER {PARTNER_MODEL_BUFFER}, {(len(data) + 2047) // 2048} sectors)')


if __name__ == '__main__':
    main()
