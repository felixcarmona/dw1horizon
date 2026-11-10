"""Salamon's (species 221) field clips: a small dog's gait and a blinking face.

Offline authoring script (the model it makes is stored with `tools/models/edit.py put 221 MMD TIM`, like Raidramon's).
The earlier gait was a retarget from a larger wolf whose feet ended up on the midline (the front paws crossed, 9-11 units
apart where the rest stance is 54), which read as a cat. This one is built with quadruped.py from the rest stance:

  walk   lateral sequence (LH, LF, RH, RF), 9 ticks, 10 units a tick
  tired  the same sequence, 9 ticks, 8 units a tick
  run    diagonal trot (LF+RH, RF+LH), 8 ticks, 28 units a tick, a flight phase of about 2 ticks and a bounding body

Every foot stays on its own side of the midline and swings straight forward and back; the planted feet do not slide. The
ears and the head follow the body with a lag. The walk, tired walk and run play three, three and four cycles in one clip so
that a blink (salamon_face.py) is not repeated every few ticks; each clip opens and closes with the eyes open. The idle
keeps its motion and only gains its blinks. All other slots stay as they are.

    python tools/models/field_animations/salamon.py --source SRC.MMD --tex SRC.TIM --out-dir DIR
where SRC is the previously stored model (sha256 below).
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import quadruped, salamon_face  # noqa: E402

SPECIES = 221
SOURCE = '136c1c8aafffec151fd9ad83d281056cde4601a9cc4463a8ad4e1513e0f864fa'
PARENTS = [-1, 13, 1, 2, 3, 2, 5, 1, 7, 8, 1, 10, 11, 0, 13, 14, 15, 13, 17, 18, 2]
LEGS = ('LH', 'LF', 'RH', 'RF')


def _all(v):
    return {k: v for k in LEGS}


_BASE = dict(snap=False, slip=0.05, height=0, tilt=0, chest_up=0, neck=0, nod=2, bob=2, pitch=1.5, flex=0.5, roll=2, yaw=2,
             head=0.9, tail=0, loose=4, lag=(0.05, 0.1), side=0.3, breath=0.5, settle=2, jerk=0.3,
             lift={'front': 9, 'hind': 8}, curl={'front': 15, 'hind': 10}, peel={'front': 8, 'hind': 8},
             reach={'front': 0, 'hind': 0}, out={'front': 3, 'hind': 3}, steps=LEGS)

PROFILE = dict(
    species=SPECIES, name='Salamon', source=SOURCE, parents=PARENTS,
    pelvis=13, chest=1, neck=None, head=2,
    legs={'RF': (7, 8, 9, 1, True), 'LF': (10, 11, 12, -1, True), 'RH': (14, 15, 16, 1, False), 'LH': (17, 18, 19, -1, False)},
    tail=(), loose=((3, 1), (5, -1), (4, 1), (6, -1)), pole_world=True, rest_plane=True,
    pole={True: [0.1, 0, 1], False: [0.3, 0, -1]},
    sole={True: [0, 23, -8], False: [0, 25, -6]},       # the underside of each boot (paw bone space)
    reach={'front': -8, 'hind': -6}, fold={True: 16, False: 16}, clear=2,
    paw_flat={'RF': [0, -18.6, 0], 'LF': [0, 18.2, 0], 'RH': [0, -3.5, 0], 'LH': [0, 4.2, 0]},
    speed_range={2: (9, 31), 3: (7, 20), 4: (27, 52)},
    gaits={
        2: dict(_BASE, name='walk', kind='walk', ticks=9, cycles=3, speed=10, bob=0.5, pitch=2, flex=0.8, roll=2.5, yaw=3, nod=2,
                loose=3.5, touchdown={'LH': 0, 'LF': .25, 'RH': .5, 'RF': .75}, duty=_all(.5)),
        3: dict(_BASE, name='condition walk', kind='walk', ticks=9, cycles=3, speed=8, bob=0, pitch=1.5, flex=0.8, roll=3, yaw=2,
                nod=2.5, loose=2, touchdown={'LH': 0, 'LF': .25, 'RH': .5, 'RF': .75}, duty=_all(.62),
                lift={'front': 10, 'hind': 10}, curl={'front': 3, 'hind': 3}, peel={'front': 0, 'hind': 0}, settle=0),
        4: dict(_BASE, name='run', kind='trot', ticks=8, cycles=4, speed=28, snap=True, jerk=0, bob=5, pitch=3.5, flex=1.5,
                nod=3, settle=2, loose=5, touchdown={'LF': 0, 'RH': 0, 'RF': .5, 'LH': .5}, duty=_all(.17),
                steps=('LF', 'RF'), lift={'front': 9, 'hind': 9}),
    },
)

# eye states over each clip: (tick, 0 open | 1 half | 2 shut), ending open
EYES = {
    0: salamon_face.blink(20) + salamon_face.blink(26) + salamon_face.blink(68, slow=True),
    2: salamon_face.blink(11),
    3: salamon_face.blink(10, slow=True),
    4: salamon_face.blink(13),
}


def _events(slot, ticks):
    return salamon_face.events(EYES[slot], ticks)


PROFILE['events'] = _events


def _idle(old, n):
    """Slot 0 with the same motion and sound, plus the blinks."""
    frames, loop, events = animsheet.slot_frames(old, n, 0)
    assert loop == 0
    events = [e for e in events if e[1] != 'tex'] + _events(0, len(frames))
    events.sort(key=lambda e: e[0])
    anim = mmd.encode_anim(frames, n, loop_sample=0, events=events, tol=0)
    same = mmd.AnimPlayer(anim, n, 0), mmd.AnimPlayer(old.anims.anims[old.anims.table[0]], n, 0)
    for _ in range(len(frames) * 2):
        same[0].tick(), same[1].tick()
        assert [list(v) for v in same[0].pose] == [list(v) for v in same[1].pose] and same[0].root == same[1].root, 'idle moved'
    return anim


def build(data, tex, skeleton):
    result, report = quadruped.build(data, skeleton, PROFILE)
    n = len(skeleton)
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    new = mmd.MMD.parse(result, n)
    new.type = SPECIES
    index = old.anims.table[0]
    assert sum(1 for i in old.anims.table if i == index) == 1, 'the idle is shared with another slot'
    new.anims.anims[new.anims.table[0]] = _idle(old, n)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = SPECIES
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == [0, 2, 3, 4], changed_programs(old, actual)
    face = mmd.Tim4(tex)
    salamon_face.stamp(face)
    new_tex = face.to_bytes()
    used = 8 + face.clen + 12 + 128 * salamon_face.FRAME_Y
    assert new_tex[:used] == tex[:used] and len(new_tex) == len(tex), 'the used rows of the texture stay'
    report['changed_slots'] = [0, 2, 3, 4]
    report['storage'] = motionstorage.require(result, n)
    report['output_sha256'] = hashlib.sha256(result).hexdigest()
    return result, new_tex, report


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--tex', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/221-salamon.json').read_text())['model']['skeleton']
    data, tex, proof = build(a.source.read_bytes(), a.tex.read_bytes(), [tuple(b) for b in skeleton])
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / '221.MMD').write_bytes(data)
    (a.out_dir / '221.TIM').write_bytes(tex)
    print(json.dumps(proof, indent=2, default=str))


if __name__ == '__main__':
    main()
