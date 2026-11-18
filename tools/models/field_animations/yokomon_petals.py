"""Yokomon's (species 477) tired walk: the petals hang open instead of standing folded.

Yokomon keeps Tanemon's ten-bone rig and clips. The two blades per side sit on bones 4 and 5, which hinge about z.
Idle, walk and run swing them below their rest angle (rz of bone 4 from 0 to -728, bone 5 the mirror), so the flower
is open. Tanemon's tired walk holds them at about +340..+400 (30 to 35 degrees past the rest angle, the other way),
so the blades stand up against the neck and read as a closed bud. Only that one thing changes here:

  bones 4 and 5, rz, slot 3: a hang of -230 (heavier than the walk's -170, lighter than the idle's deepest -364) that
  follows the head's nod (bone 3, rx) three ticks late with a quarter of its swing, so the petals sag and come back
  slowly behind the body. Bone 5 is the exact mirror.

The key frames, their spans, every other channel, the events (eyes, sound), the root motion and the other slots are
the donor's, byte for byte: only the initial rz of the two bones and the rz values of their keys are rewritten.

    python -m tools.models.field_animations.yokomon_petals SRC.MMD OUT.MMD
where SRC is the baby as built by `tools.models.babies` before this change.
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
SLOT = 3
PETALS = (4, 5)          # right and left petal hinges (rz, mirrored)
NOD = 3                  # the head bone whose rx the petals follow
HANG = -230              # rz of bone 4 at rest in the tired walk
FOLLOW = 0.25            # fraction of the head's swing the petals take
LAG = 3                  # ticks the petals trail the head


def _parse(data):
    mmd.exe().skeleton[SPECIES] = mmd.exe().skeleton[DONOR]
    mmd.exe().bone_count[SPECIES] = NB
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    return model


def targets(frames):
    """rz of bone 4 per tick (the loop closes: tick N is tick 0) from the head's rx."""
    n = len(frames) - 1
    nod = [frames[t][NOD][3] for t in range(n)]
    mean = sum(nod) / n
    return [round(HANG + FOLLOW * (nod[(t - LAG) % n] - mean)) for t in range(n)] + [None]


def author(data):
    old = _parse(data)
    new = copy.deepcopy(old)
    anim = new.anims.anims[new.anims.table[SLOT]]
    frames, _, _ = animsheet.slot_frames(old, NB, SLOT)
    rz = targets(frames)
    n = len(frames) - 1
    rz[n] = rz[0]
    # tick time of every key: the frame field is the tick the key starts on, the loop is frame_count - 1 ticks long
    keys = [i for i in anim.instrs if i['op'] == 'key']
    where = {}
    for ins in keys:
        for bone in ins['bones']:
            if bone['bone'] == PETALS[0] and 'rz' in bone['vals']:
                where[ins['frame']] = bone
    frames_at = sorted(where)
    assert sum(where[f]['div'] for f in frames_at) == anim.frame_count - 1
    start = 0
    for f in frames_at:
        assert f - 1 == start, (f, start)
        div = where[f]['div']
        delta = rz[start + div] - rz[start]
        where[f]['vals']['rz'] = delta
        for ins in keys:
            if ins['frame'] == f:
                for bone in ins['bones']:
                    if bone['bone'] == PETALS[1]:
                        assert bone['div'] == div
                        bone['vals']['rz'] = -delta
        start += div
    anim.pose[PETALS[0] - 1][2] = rz[0]
    anim.pose[PETALS[1] - 1][2] = -rz[0]
    output = new.build()
    actual = _parse(output)
    assert actual.tmd.build() == old.tmd.build()
    assert changed_programs(old, actual) == [SLOT], changed_programs(old, actual)
    return output, dict(slot=SLOT, ticks=n, rz_range=(min(rz), max(rz)))


def build(data):
    output, report = author(data)
    return output, dict(species=SPECIES, clips=[report], storage=motionstorage.require(output, NB))


def main():
    out, proof = build(Path(sys.argv[1]).read_bytes())
    Path(sys.argv[2]).write_bytes(out)
    print(proof)


if __name__ == '__main__':
    main()
