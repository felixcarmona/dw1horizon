"""Yokomon's (species 477) neck stays on the bulb in every clip.

Tanemon's head bone (3) nods about a pivot 51 units above the base of the stem (the object's lowest ring, local y 51), so
a nod of 30 degrees or more swings the base of the stem 20 to 30 units forward or back of the bulb's top and the neck seems
to come off the trunk. The same nods are kept, but bone 3 is also translated each tick (ty, tz) by exactly the opposite of
that swing, so the nod turns about the base of the stem. Only the translation channels ty and tz of bone 3 are added (as
separate key entries, one per rx span, and the initial pose); its rx, the petals, the feet, the other bones, the root
motion, the events and the mesh are not touched.

    python -m tools.models.field_animations.yokomon_neck SRC.MMD OUT.MMD
where SRC is the baby as built by `tools.models.babies` before this change (petals already open).
"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES = 477
DONOR = 44
NB = 10
HEAD = 3
SLOTS = (0, 2, 3, 4)
ALIASES = (27, 33, 35, 36)      # slots that share the idle, walk and run programs


def _parse(data):
    mmd.exe().skeleton[SPECIES] = mmd.exe().skeleton[DONOR]
    mmd.exe().bone_count[SPECIES] = NB
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    return model


def base_ring(model):
    """Centre of the lowest ring of the head object, in its local space."""
    vs = [v[:3] for v in model.tmd.obj_verts(mmd.exe().skeleton[DONOR][HEAD][0])]
    low = max(v[1] for v in vs)
    ring = [v for v in vs if v[1] >= low - 1]
    return [sum(v[i] for v in ring) / len(ring) for i in range(3)]


def swing(pose, c):
    """Where the nod moves the ring centre (parent space), minus the rotation-free position."""
    R = mmd.rot_matrix(*pose[3:6])
    return [sum(R[i][j] * c[j] for j in range(3)) - c[i] for i in range(3)]


def author(data):
    old = _parse(data)
    new = copy.deepcopy(old)
    c = base_ring(old)
    report = []
    for slot in SLOTS:
        anim = new.anims.anims[new.anims.table[slot]]
        frames, _, _ = animsheet.slot_frames(old, NB, slot)
        n = len(frames) - 1
        fix = [[-round(x) for x in swing(f[HEAD], c)] for f in frames]
        fix[n] = fix[0]
        keys = [(ins, bone) for ins in anim.instrs if ins['op'] == 'key' for bone in ins['bones']
                if bone['bone'] == HEAD and 'rx' in bone['vals']]
        starts = [ins['frame'] for ins, _ in keys]
        ends = starts[1:] + [anim.frame_count]
        assert starts[0] == 1 and sum(e - s for s, e in zip(starts, ends)) == n, (slot, starts, n)
        for (ins, bone), s, e in zip(keys, starts, ends):
            vals = {ch: fix[e - 1][i] - fix[s - 1][i] for i, ch in ((1, 'ty'), (2, 'tz')) if fix[e - 1][i] != fix[s - 1][i]}
            if vals:
                ins['bones'].append(dict(bone=HEAD, div=e - s, vals=vals))
        anim.pose[HEAD - 1][4] += fix[0][1]
        anim.pose[HEAD - 1][5] += fix[0][2]
        report.append(dict(slot=slot, ticks=n, max_shift=max(max(abs(x) for x in f) for f in fix)))
    output = new.build()
    actual = _parse(output)
    assert actual.tmd.build() == old.tmd.build()
    assert changed_programs(old, actual) == sorted(SLOTS + ALIASES), changed_programs(old, actual)
    return output, report


def build(data):
    output, report = author(data)
    return output, dict(species=SPECIES, clips=report, storage=motionstorage.require(output, NB))


def main():
    out, proof = build(Path(sys.argv[1]).read_bytes())
    Path(sys.argv[2]).write_bytes(out)
    print(proof['clips'], proof['storage']['resident_bytes'])


if __name__ == '__main__':
    main()
