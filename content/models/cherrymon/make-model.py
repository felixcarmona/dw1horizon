#!/usr/bin/env python3
"""Cherrymon partner model: JURE mesh at 0.55 times + a full partner animation set.

Field NPCs use disc-derived twins; this output supplies the partner only.

Cherrymon (type 121, JURE.MMD) is an NPC: 26 bones on a skeleton no other model uses
(trunk, three canopy layers, four three-piece branch arms, four two-piece roots) and
only three animation slots (0 idle, 0x1D and 0x1E, used by its Misty Trees scripts).
This script builds the partner model:

  - the mesh and every bone offset scaled by SCALE (Cherrymon is 1000 high, twice the
    biggest partner; at 0.55 it is 550, a bit under MasterTyrannomon's 590);
  - slots 0x1D/0x1E: the NPC's own animations, replayed tick by tick and re-encoded
    with their translations scaled (for the partner animation set);
  - every slot a partner uses (the union over the 64 partner models: 0-5, 7-0x13,
    0x15-0x19, 0x1B, 0x21-0x25, 0x28-0x2C) plus 0x2E-0x36 (eight Earth techniques
    and Bit Bomb): authored here as per-tick poses (`clips.py`) and encoded with
    mmd.encode_anim; the technique arm swings come from Vegiemon's vines through
    tools/retarget.py.

Usage (from the repository root):
  python3 content/models/cherrymon/make-model.py [OUT.MMD] [--pad]
default OUT: build/models/JURE-partner.MMD. --pad (testing only) zero-pads the file to
PARTNER_MODEL_BUFFER so rebuilt discs keep the same layout and save states keep working.
Contact sheets: python3 tools/animsheet.py OUT.MMD sheet.png --type 121 --slots ...
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, HERE)
import mmd  # noqa: E402
import clips  # noqa: E402

TYPE = 121
SCALE = 0.55
MESH = os.path.join(ROOT, 'extracted/CHDAT/MMD4/JURE.MMD')
PARTNER_MODEL_BUFFER = 0x18800
NPC_SLOTS = (0x1D, 0x1E)


def play(anim, nb, slot):
    """Per-tick samples (bone 0 tx..tz = root motion accumulated in bone 0's frame)."""
    p = mmd.AnimPlayer(anim, nb, slot)
    out, root = [], [0, 0, 0]
    while len(out) < 6000 and p.tick(stop_at_infinite_loop=True):
        root = [r + b for r, b in zip(root, p.base)]
        snap = [list(v) for v in p.pose]
        snap[0][6:9] = list(root)
        out.append(snap)
    events = []
    for k, kind, c in p.events:
        if kind == 'sound':
            events.append((k, 'sound', dict(bank=c['bank'], note=c['note'])))
        elif kind == 'tex':
            events.append((k, 'tex', dict(src=c['src'], size=c['size'], dst=c['dst'])))
    return out, p.loop_sample(), events


def scale_mesh(m):
    for i, (x, y, z, p) in enumerate(m.tmd.verts):
        m.tmd.verts[i] = (round(x * SCALE), round(y * SCALE), round(z * SCALE), p)


def build(out_path, pad=False):
    e = mmd.exe()
    nb = e.bone_count[TYPE]
    src = mmd.MMD.load(MESH)
    rest = [list(v) for v in src.anims.anims[src.anims.table[0]].pose]   # bones 1..25
    for v in rest:
        v[-3:] = [round(c * SCALE) for c in v[-3:]]
    assert all(v[-6:-3] == [0, 0, 0] for v in rest), 'JURE rest pose has rotations'

    sec = mmd.AnimSection()
    sec.table = [None] * 0x37
    encoded = {}

    def put(slot, anim):
        key = anim.build()
        if key not in encoded:
            encoded[key] = len(sec.anims)
            sec.anims.append(anim)
        sec.table[slot] = encoded[key]

    # the NPC's animations, scaled
    for slot in NPC_SLOTS:
        smp, ls, ev = play(src.anims.anims[src.anims.table[slot]], nb, slot)
        smp = [[v[:6] + [round(x * SCALE) for x in v[6:9]] for v in s] for s in smp]
        mmd.close_loop(smp, ls)
        put(slot, mmd.encode_anim(smp, nb, ls, ev, tol=1))

    rig = clips.Rig(rest)
    for slot, clip in clips.partner_clips(rig).items():
        smp, ls, ev = clip.samples()
        put(slot, mmd.encode_anim(smp, nb, ls, ev, tol=1))

    missing = [s for s in clips.REQUIRED_SLOTS if sec.table[s] is None]
    assert not missing, f'slots without animation: {[hex(s) for s in missing]}'

    scale_mesh(src)
    out = mmd.MMD()
    out.tmd, out.anims = src.tmd, sec
    data = out.build()
    assert len(data) <= PARTNER_MODEL_BUFFER, f'{len(data)} bytes > PARTNER_MODEL_BUFFER'
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    size = len(data)
    if pad:
        # testing: a fixed size keeps every later file at the same sector across rebuilds
        # (--relayout), so save states stay valid and only the model changes
        data += bytes(PARTNER_MODEL_BUFFER - len(data))
    open(out_path, 'wb').write(data)
    used = sum(x is not None for x in sec.table)
    print(f'{out_path}: JURE mesh x{SCALE}, {len(sec.anims)} animations in {used} slots, '
          f'{size} bytes (PARTNER_MODEL_BUFFER {PARTNER_MODEL_BUFFER}){" padded" if pad else ""}')
    return out_path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = args[0] if args else os.path.join(ROOT, 'build/models/JURE-partner.MMD')
    build(out, '--pad' in sys.argv)


if __name__ == '__main__':
    main()
