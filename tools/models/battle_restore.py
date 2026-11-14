#!/usr/bin/env python3
"""Put the source game's own battle clips back into an imported species' model (developer tool).

The battle slots 0x21 / 0x22 (battle idle, tired battle idle) and 0x23 / 0x24 (battle movement) of an imported species
are the source game's own animations (the importer's output, `edit.py sources`). A reviewed model delta or a generator
may have pointed them at the field clips (slots 0-4) instead; this takes the importer's clip back, for the slots asked,
and leaves every other slot, the mesh, the skeleton and the texture byte for byte as they were.

  tools/models/battle_restore.py restore B.MMD A.MMD BONES OUT.MMD SLOT[=TICKS] ...
  tools/models/battle_restore.py pitch B.MMD BONES TYPE OUT.MMD SLOT BONE=DEGREES ...
  tools/models/battle_restore.py copy B.MMD BONES TYPE OUT.MMD SLOT=FROM_SLOT
  tools/models/battle_restore.py rebuild B.MMD A.MMD TYPE OUT.MMD

B is the species' model (`edit.py get`), A the importer output of the same species, BONES the bone count, SLOT a slot
number (33-36) and TICKS the length (frames, as `animsheet.slot_frames` counts them) the slot has in the final model:
a clip of that length is copied unchanged; another length is retimed (a one-shot clip, such as a victory or a
technique, stays one-shot). Idles (33, 34) keep their own speed: the cycle
repeats a whole number of times and the speed is scaled by the small remainder (a clip more than 1.5 times longer than
asked keeps its own length). Movement clips (35, 36) are resampled in time as they are (the root's total travel stays).

`pitch` leans bones of one slot's clip by a constant angle about the model's side axis (the parent chain's rotation is
taken out, so the clip's own swing, timing and root travel are untouched): for an original whose torso or head sits far
off the species' natural stance. `copy` makes a slot share another slot's clip (a species whose source game had no clip
of its own for it). `rebuild` restores the slots of the species' row in content/models/imports/battle-rebuilds.json
(`{"SLOT": {"ticks": N or null, "ops": [...]}}`, SLOT a decimal slot number, `ticks` as SLOT=TICKS above; an optional
`"rig": SLOT` or `"rig": [SOURCE_SLOT, OUR_SLOT]` first gives the restored clip our rig's scale and offset channels,
`clip_repair.fit_rig`, for a species whose model was reshaped offline) and runs the
row's repair operations (tools/models/clip_repair.py) on each: the source's own clip kept as the reference of poses,
timing and arc, and repaired where it breaks on our rig (battle_qa.py counts these slots as documented polish). A slot's
optional `"compact": [SLOT, ...]` encodes those clips again exactly (`compact` below, tolerance 0) to pay for the restored
ones. A model already over the resident limit before the rebuild (a later provider stage makes the room: Beelzemon's
Buster Dive dash replaces a larger technique clip) may stay over it but must not grow; the provider checks its final model.

A restored clip is one more program in the resident model (the field idle used to serve as the battle idle), so a model
near the resident limit (motionstorage, 100352 B) makes room with `compact(data, nb, tol, slots)`: every resident clip is
encoded again from its own decoded ticks, kept only when smaller and decoded within `tol` units (1/4096 turn) of the
original, same length, loop and events. Tolerance 0 is exact (the same ticks in fewer bytes); the species that needed more
used 4-5 units (0.35-0.45 degrees) on clips other than the field slots 0-4 and the battle slots, which are never loosened. An idle that
would be repeated to the field idle's length (`SLOT=TICKS`) can instead keep its own length (`SLOT` alone): the repeats do not
fold (the clip's own loop uses the engine's one loop register), so the repeated clip costs several times the bytes.
"""
import copy
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]

import animsheet  # noqa: E402
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiontailspace import interpolate_pose  # noqa: E402

IDLES, MOVES = (33, 34), (35, 36)
MAX_SLOW = 1.5      # an idle longer than this many times the asked length keeps its own


def _sample(frames, ticks, source_ticks):
    """The pose of each tick 0..ticks of a clip of `source_ticks` ticks (frames), resampled."""
    out = []
    for t in range(ticks + 1):
        i, rest = divmod(t * source_ticks * 4096 // ticks, 4096)
        pose = list(map(list, frames[i])) if not rest else interpolate_pose(frames[i], frames[i + 1], rest)
        out.append([[int(v) for v in bone] for bone in pose])
    return out


def retimed(frames, events, ticks, tile):
    """(samples, events) of a clip of len(frames) - 1 ticks as a clip of `ticks` ticks, its cycle `tile` times."""
    n = len(frames) - 1
    if tile > 1:
        frames = [f for _ in range(tile) for f in frames[:-1]] + [frames[-1]]
        events = [(k + i * n, kind, c) for i in range(tile) for k, kind, c in events]
        n *= tile
        ticks = tile * max(1, round(ticks / tile))     # whole cycles of equal length: the encoder folds repeats
    samples = _sample(frames, ticks, n)
    events = [(min(ticks - 1, k * ticks // n), kind, c) for k, kind, c in events]
    return samples, events


def plan(slot, a_ticks, want):
    """(frames count, cycles) the restored clip of `slot` gets for a final clip of `want` frames (None: its own length)."""
    if want is None or want == a_ticks:
        return a_ticks, 1
    if slot in IDLES:
        tile = max(1, round((want - 1) / (a_ticks - 1)))
        if (a_ticks - 1) * tile > MAX_SLOW * (want - 1):
            return a_ticks, 1
        return want, tile
    return want, 1


def restore(b_data, a_data, nb, slots, budget=True):
    """B with the importer's clip of each slot in `slots` ({slot: asked frames or None}) -> (bytes, {slot: report}).
    `budget` False skips the animation storage check (rebuild checks the result itself)."""
    model = mmd.MMD.parse(b_data, nb)
    source = mmd.MMD.parse(a_data, nb)
    report = {}
    for slot, want in sorted(slots.items()):
        clip = source.anims.anims[source.anims.table[slot]]
        frames, loop, events = animsheet.slot_frames(source, nb, slot)
        count, tile = plan(slot, len(frames), want)
        if count == len(frames):
            clip = copy.deepcopy(clip)
            report[slot] = dict(frames=count, source_frames=len(frames), copied=True)
        else:
            if loop not in (0, None):
                raise ValueError(f'slot {slot}: a clip that loops from the middle cannot be retimed')
            samples, events = retimed(frames, events, count - 1, tile)
            # a one-shot clip (victory, faint, get up, a technique) stays one-shot: its last pose is held
            clip = mmd.encode_anim(samples, nb, 0 if loop == 0 else None, events, tol=1, repeats=loop == 0 and tile > 1)
            report[slot] = dict(frames=len(samples), source_frames=len(frames), cycles=tile, copied=False)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(clip)
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    out = model.build()
    if budget:
        motionstorage.require(out, nb)
    return out, report


def compact(data, nb, tol=0, slots=None):
    """B re-encoded where a clip gets smaller, the same animation: each resident clip of `slots` (default every slot
    outside the cold ones, which are not resident) is encoded again from its decoded ticks with tolerance `tol` (units of
    1/4096 turn; 0 is exact) and kept when it is smaller and decodes to the same ticks (within `tol`), loop and events.
    -> (bytes, {slot: (old bytes, new bytes)})"""
    import coldsplit
    model = mmd.MMD.parse(data, nb)
    cold = set(coldsplit.cold_set(model, coldsplit.COLD_SLOTS))
    done, report = {}, {}
    for slot, index in enumerate(list(model.anims.table)):
        if index is None or slot in cold or (slots is not None and any(
                s not in slots for s, i in enumerate(model.anims.table) if i == index)):
            continue
        if index in done:
            continue
        old = model.anims.anims[index]
        try:
            frames, loop, events = animsheet.slot_frames(model, nb, slot)
            samples = [[[int(v) for v in bone] for bone in pose] for pose in frames]
            new = mmd.encode_anim(samples, nb, loop, events, tol=tol, repeats=True)
            if len(new.build()) >= len(old.build()):
                done[index] = None
                continue
            model.anims.anims[index] = new
            again, loop2, events2 = animsheet.slot_frames(model, nb, slot)
            ok = len(again) == len(samples) and loop2 == loop and list(events2) == list(events) and all(
                abs(int(x) - y) <= tol for pa, pb in zip(again, samples) for ba, bb in zip(pa, pb) for x, y in zip(ba, bb))
        except (ValueError, TypeError, IndexError):
            ok = False
        if ok:
            report[slot] = (len(old.build()), len(new.build()))
            done[index] = new
        else:
            model.anims.anims[index] = old
            done[index] = None
    return model.build(), report


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _tr(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def pitched(frames, skeleton, lean):
    """`frames` (poses per tick) with each bone of `lean` ({bone: degrees}, positive: the bone's forward axis dips) pitched
    about the model's side axis by that angle in every pose; children follow."""
    out = []
    for pose in frames:
        pose = [list(v) for v in pose]
        world = {}

        def chain(b):               # the pure rotation of a bone's parent, as the pose has it (original angles)
            if b < 0:
                return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
            if b not in world:
                world[b] = _mul(chain(skeleton[b][1]), mmd.rot_matrix(*orig[b][3:6]))
            return world[b]
        orig = [list(v) for v in pose]
        for b, deg in lean.items():
            k = -math.radians(deg)
            c, s = math.cos(k), math.sin(k)
            pitch = [[1, 0, 0], [0, c, -s], [0, s, c]]
            parent = chain(skeleton[b][1])
            local = mmd.rot_matrix(*orig[b][3:6])
            new = _mul(_tr(parent), _mul(pitch, _mul(parent, local)))
            pose[b][3:6] = [int(round(v)) for v in mmd.matrix_euler(new, prev=orig[b][3:6])]
        out.append([[int(round(v)) for v in bone] for bone in pose])   # the root's travel reads as whole floats
    return out


def pitch(b_data, nb, slot, lean, type_id):
    """B (a species `type_id`, registered with mmd.exe()) with the clip of `slot` leaned ({bone: degrees}) -> bytes."""
    model = mmd.MMD.parse(b_data, nb)
    frames, loop, events = animsheet.slot_frames(model, nb, slot)
    if loop != 0:
        raise ValueError(f'slot {slot}: a clip that does not loop from its start cannot be leaned')
    samples = pitched(frames, mmd.exe().skeleton[type_id], lean)
    clip = mmd.encode_anim(samples, nb, 0, events, tol=1, repeats=False)
    model.anims.table[slot] = len(model.anims.anims)
    model.anims.anims.append(clip)
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    out = model.build()
    motionstorage.require(out, nb)
    return out


REBUILDS = ROOT / 'content/models/imports/battle-rebuilds.json'


def rebuilds():
    """{species id (text): {slot (text): {'ticks': N or None, 'ops': [...]}}} of content/models/imports/battle-rebuilds.json."""
    return json.loads(REBUILDS.read_text()) if REBUILDS.exists() else {}


def rebuild(b_data, a_data, nb, type_id, row):
    """B (a species `type_id`, registered with mmd.exe()) with each slot of `row` restored from A and repaired -> bytes."""
    from tools.models import clip_repair
    slots = {int(k): v.get('ticks') for k, v in row.items()}
    data, _ = restore(b_data, a_data, nb, slots, budget=False)
    model = mmd.MMD.parse(data, nb)
    source = mmd.MMD.parse(a_data, nb)
    parents = [p for _, p in mmd.exe().skeleton[type_id]]
    for slot in sorted(slots):
        frames, loop, events = animsheet.slot_frames(model, nb, slot)
        if loop not in (0, None):
            raise ValueError(f'slot {slot}: a clip that loops from the middle cannot be rebuilt')
        if 'rig' in row[str(slot)]:      # a species reshaped offline (its delta): the clip takes the rig's scales and offsets
            ref = row[str(slot)]['rig']      # a slot of both models, or [the source's slot, our slot]
            theirs, ours = ref if isinstance(ref, list) else (ref, ref)
            frames = clip_repair.fit_rig(frames, animsheet.slot_frames(source, nb, theirs)[0][0],
                                         animsheet.slot_frames(mmd.MMD.parse(b_data, nb), nb, ours)[0][0])
        samples = clip_repair.apply_ops(frames, parents, row[str(slot)]['ops'])
        events = clip_repair.events(row[str(slot)]['ops'], events, len(frames))
        clip = mmd.encode_anim(samples, nb, 0 if loop == 0 else None, events, tol=1, repeats=False)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(clip)
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {old: new for new, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    out = model.build()
    packed = {s for v in row.values() for s in v.get('compact', ())}
    if packed:     # a slot's "compact": [SLOT, ...]: those clips encoded again exactly (`compact`, tolerance 0) to pay for
        out, _ = compact(out, nb, 0, packed)           # the restored ones; a clip shared with a slot not listed stays
    if motionstorage.audit(b_data, nb)['fits']:
        motionstorage.require(out, nb)
    elif motionstorage.audit(out, nb)['resident_bytes'] > motionstorage.audit(b_data, nb)['resident_bytes']:
        # a B already over the budget (a later provider stage makes the room: Beelzemon's Buster Dive dash replaces a
        # larger technique clip) must not grow; the provider's final model is checked against the budget as always
        raise ValueError('rebuild grows a model that is over the animation storage budget')
    return out


def copy_slot(b_data, nb, slot, source):
    """B with `slot` sharing the clip of `source` -> bytes."""
    model = mmd.MMD.parse(b_data, nb)
    model.anims.table[slot] = model.anims.table[source]
    out = model.build()
    motionstorage.require(out, nb)
    return out


def main():
    if len(sys.argv) == 6 and sys.argv[1] == 'rebuild':
        b, a, kind, out = sys.argv[2:6]
        species = json.loads(next((ROOT / 'content/species').glob(f'{int(kind)}-*.json')).read_text())
        skeleton = species['model']['skeleton']
        mmd.exe().add_type(int(kind), skeleton, name=species['name'])
        row = rebuilds()[str(int(kind))]
        Path(out).write_bytes(rebuild(Path(b).read_bytes(), Path(a).read_bytes(), len(skeleton), int(kind), row))
        return
    if len(sys.argv) >= 7 and sys.argv[1] in ('pitch', 'copy'):
        cmd, b, nb, kind, out, slot = sys.argv[1:7]
        data = Path(b).read_bytes()
        if cmd == 'copy':
            slot, _, source = slot.partition('=')
            Path(out).write_bytes(copy_slot(data, int(nb), int(slot), int(source)))
        else:
            species = json.loads(next((ROOT / 'content/species').glob(f'{int(kind)}-*.json')).read_text())
            mmd.exe().add_type(int(kind), species['model']['skeleton'], name=species['name'])
            lean = {int(k): float(v) for k, _, v in (x.partition('=') for x in sys.argv[7:])}
            Path(out).write_bytes(pitch(data, int(nb), int(slot), lean, int(kind)))
        return
    if len(sys.argv) < 7 or sys.argv[1] != 'restore':
        raise SystemExit(__doc__)
    b, a, nb, out = sys.argv[2:6]
    slots = {}
    for item in sys.argv[6:]:
        slot, _, ticks = item.partition('=')
        slots[int(slot)] = int(ticks) if ticks else None
    data, report = restore(Path(b).read_bytes(), Path(a).read_bytes(), int(nb), slots)
    Path(out).write_bytes(data)
    print(report)


if __name__ == '__main__':
    main()
