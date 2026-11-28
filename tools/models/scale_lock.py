#!/usr/bin/env python3
"""Audit animated bone scale and bake constant proportions into a reviewed model.

Scale keys are momentum, not absolute targets. Audit the decoded engine poses,
including differences between slots; deleting keys alone leaves their initial
scales inconsistent. The walk's first pose supplies one scale per bone. Mesh,
rotations, horizontal motion, events and control flow are retained. Reground
changed clips with the existing foot-aware grounding solver.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import chibi

THRESHOLD = 0.02


def measure(model, skeleton, threshold=THRESHOLD):
    """All occupied slots, including aliases; max/min are decoded scale units."""
    nb = len(skeleton)
    reference = animsheet.slot_frames(model, nb, 2)[0][0]
    overall = {}
    clips = []
    cache = {}
    for slot, index in enumerate(model.anims.table):
        if index is None:
            continue
        if index not in cache:
            player = mmd.AnimPlayer(model.anims.anims[index], nb, slot)
            ranges = {(b, c): [32768, -32768] for b in range(nb) for c in range(3)}
            for tick in range(65536):
                if not player.tick(stop_at_infinite_loop=True):
                    break
                for b, bone in enumerate(player.pose):
                    for c in range(3):
                        span = ranges[b, c]
                        value = bone[c]
                        if value < span[0]:
                            span[0] = value
                        if value > span[1]:
                            span[1] = value
            if player.running:
                raise ValueError(f'slot {slot}: audit exceeds 65536 decoded ticks')
            cache[index] = [(b, c, low, high) for (b, c), (low, high) in ranges.items()]
        changed = []
        for b, c, low, high in cache[index]:
            overall.setdefault((b, c), []).extend((low, high))
            if high - low > threshold * max(4096, abs(reference[b][c])):
                changed.append([b, mmd.CHANNELS[c], low, high])
        clips.append(dict(slot=slot, channels=changed))
    between = [[b, mmd.CHANNELS[c], min(v), max(v)] for (b, c), v in overall.items()
               if max(v) - min(v) > threshold * max(4096, abs(reference[b][c]))]
    return dict(threshold=threshold, occupied_slots=len(clips),
                animated=[r for r in clips if r['channels']], across_slots=between)


JUMP = 0.05


def body_scales(model, skeleton):
    """{slot: (first, low, high)} of each occupied slot's body scale: the bone scales multiplied down the skeleton and
    averaged over the mesh's vertices (1.0 = unscaled), over every decoded tick. A clip whose first pose differs from
    the walk's draws the Digimon at another size the moment the game switches to it."""
    nb = len(skeleton)
    weights = [len(model.tmd.obj_verts(obj)) if obj >= 0 else 0 for obj, _ in skeleton]
    total = sum(weights) or 1

    def size(pose):
        accumulated, s = [1.0] * nb, 0.0
        for b, (_, parent) in enumerate(skeleton):
            accumulated[b] = sum(pose[b][:3]) / 12288 * (accumulated[parent] if parent >= 0 else 1.0)
            s += weights[b] * accumulated[b]
        return s / total
    out, cache = {}, {}
    for slot, index in enumerate(model.anims.table):
        if index is None:
            continue
        if index not in cache:
            player, values = mmd.AnimPlayer(model.anims.anims[index], nb, slot), []
            while player.tick(stop_at_infinite_loop=True):
                values.append(size(player.pose))
                if len(values) > 65536:
                    raise ValueError(f'slot {slot}: audit exceeds 65536 decoded ticks')
            cache[index] = (round(values[0], 3), round(min(values), 3), round(max(values), 3)) if values else None
        if cache[index]:
            out[slot] = cache[index]
    return out


def scale_jumps(model, skeleton, original=None, threshold=JUMP, reference_slot=2):
    """Slots that start at another body size than the walk (more than `threshold` apart). `original`: the body scales
    of the native model the species' motion comes from (the player's disc); a start size one of its clips has is the
    original game's own (a baby's squash, Shellmon hiding in its shell) and is not reported."""
    scales = body_scales(model, skeleton)
    if reference_slot not in scales:
        return []
    reference = scales[reference_slot][0]
    own = {round(v[0], 2) for v in (original or {}).values()}
    return [dict(slot=s, scale=v[0], walk=reference) for s, v in scales.items()
            if abs(v[0] - reference) > threshold * reference and round(v[0], 2) not in own]


def _vertex_counts(model):
    return [len(model.tmd.obj_verts(o)) for o in range(len(model.tmd.objects))]


def audit_species(content, allowed):
    """scale_jumps of every species record with a model in a derive build's species folder. A native's motion is
    compared with its own model on the disc (only when the mesh is that model's: a record original made from another
    game has its own rig); content/modeldelta/scale-audit.json names the native whose motion a new species copies."""
    import species
    tables = json.loads((ROOT / 'content/tables/skeletons.json').read_text())
    motion_from = {int(k): v['native'] for k, v in allowed.get('motion_from', {}).items()}
    rows = []
    for path in sorted(Path(content).glob('*.json'), key=lambda p: int(p.name.split('-')[0])):
        record = json.loads(path.read_text())
        record['_path'] = str(path)
        model = record.get('model')
        if not model or not (model.get('skeleton') or model.get('bones')):
            continue
        source = model.get('from', record['id'])
        skeleton = model.get('skeleton') or tables['skeletons'][tables['species'][source]]
        shipped = mmd.MMD.parse(species.species_model(record)[0], len(skeleton))
        native = motion_from.get(record['id'], source if source < 180 else None)
        original = None
        if native is not None:
            disc = species.originals().model_path(native)
            try:
                rig = tables['skeletons'][tables['species'][native]]
                theirs = mmd.MMD.parse(Path(disc).read_bytes(), len(rig))
                if record['id'] in motion_from or _vertex_counts(theirs) == _vertex_counts(shipped):
                    original = body_scales(theirs, rig)
            except Exception:
                original = None
        rows.append(dict(id=record['id'], name=record['name'], jumps=scale_jumps(shipped, skeleton, original)))
    return rows


def supporting_parts(model, skeleton):
    """Use reviewed anatomical groups when present, else walking contact pieces.

    Remove ancestors of another contact piece: a low chest vertex must not
    replace the sole underneath it. Walking samples include both stance sides.
    """
    rig = chibi.Rig(model, skeleton)
    manifest = json.loads((ROOT / 'content/models/imports/chibi.json').read_text())
    profile = manifest.get(str(model.type), {})
    feet = {int(b) for b, group in profile.get('groups', {}).items() if group == 'foot'}
    if feet:
        for b in range(1, len(skeleton)):
            parent = skeleton[b][1]
            while parent > 0:
                if parent in feet and b in rig.verts:
                    feet.add(b)
                    break
                parent = skeleton[parent][1]
        return sorted(feet & rig.verts.keys())
    frames = animsheet.slot_frames(model, len(skeleton), 2)[0]
    candidates = set()
    for pose in frames:
        pose = copy.deepcopy(pose)
        pose[0] = [4096] * 3 + [0] * 6
        lows = chibi.bone_lows(model, rig.verts, pose)
        low = max(lows.values())
        candidates.update(b for b, y in lows.items() if y >= low - 12)
    ancestors = set()
    for b in candidates:
        parent = skeleton[b][1]
        while parent > 0:
            ancestors.add(parent)
            parent = skeleton[parent][1]
    return sorted(candidates - ancestors)


def lock(data, skeleton, feet=None, reference_slot=2, species_id=0):
    nb = len(skeleton)
    old = mmd.MMD.parse(data, nb)
    mmd.exe().add_type(species_id, skeleton)
    old.type = species_id
    new = copy.deepcopy(old)
    scales = [bone[:3] for bone in animsheet.slot_frames(old, nb, reference_slot)[0][0]]
    # Empty helper branches have no rendered descendants. Their zero scale is
    # inert; retaining it would force six extra pose bytes per bone per clip.
    visible = {b for b, (obj, _) in enumerate(skeleton) if obj >= 0 and old.tmd.obj_verts(obj)}
    for b in list(visible):
        parent = skeleton[b][1]
        while parent >= 0:
            visible.add(parent)
            parent = skeleton[parent][1]
    for b in range(nb):
        if b not in visible:
            scales[b] = [4096] * 3
    if scales[0] != [4096] * 3:
        raise ValueError('Root scale requires a separately reviewed reference')
    feet = feet or supporting_parts(old, skeleton)
    rig = chibi.Rig(new, skeleton)
    source_lows = chibi.lows(old, chibi.Rig(old, skeleton), feet)
    needs_scale = any(s != [4096] * 3 for s in scales[1:])
    changed = set()
    for index, slot in chibi.clips(old).items():
        frames = animsheet.slot_frames(old, nb, slot)[0]
        if all(f[b][:3] == scales[b] for f in frames for b in range(nb)):
            continue
        changed.add(index)
        animation = new.anims.anims[index]
        for b in range(1, nb):
            rotation_translation = animation.pose[b - 1][3:] if animation.has_scale else animation.pose[b - 1]
            animation.pose[b - 1] = (scales[b] if needs_scale else []) + rotation_translation
        animation.has_scale = needs_scale
        for instruction in animation.instrs:
            if instruction['op'] == 'key':
                for group in instruction['bones']:
                    for channel in ('sx', 'sy', 'sz'):
                        group['vals'].pop(channel, None)
                instruction['bones'] = [g for g in instruction['bones'] if g['vals']]
    # Keep unmodified programs byte exact, including their grounding and gait.
    table = new.anims.table[:]
    new.anims.table = [i if i in changed else None for i in table]
    grounding = chibi.ground(new, rig, source_lows, feet, tolerance=0)
    new.anims.table = table
    result = new.build()
    final = mmd.MMD.parse(result, nb)
    final.type = species_id
    assert final.tmd.build() == old.tmd.build()
    for index, slot in chibi.clips(old).items():
        before = mmd.AnimPlayer(old.anims.anims[index], nb, slot)
        after = mmd.AnimPlayer(final.anims.anims[final.anims.table[slot]], nb, slot)
        count = 0
        while before.tick(stop_at_infinite_loop=True):
            assert after.tick(stop_at_infinite_loop=True)
            assert before.base == after.base, (slot, count, 'root travel')
            assert before.events == after.events, (slot, count, 'events')
            for b in range(nb):
                assert after.pose[b][:3] == scales[b], (slot, count, b, 'scale')
                for c in range(3, 9):
                    if (b, c) != (rig.carrier, 7):
                        assert before.pose[b][c] == after.pose[b][c], (slot, count, b, c)
            count += 1
            if count >= 65536:
                raise ValueError(f'slot {slot}: replay exceeds audit limit')
        assert not after.tick(stop_at_infinite_loop=True)
    audit = measure(final, skeleton, 0)
    assert not audit['across_slots']
    return result, dict(source_sha256=hashlib.sha256(data).hexdigest(),
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        reference_slot=reference_slot, scales=scales, feet=feet,
                        changed_slots=[s for s, i in enumerate(table) if i in changed],
                        grounding=grounding, storage=motionstorage.require(result, nb),
                        audit=audit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    audit = sub.add_parser('audit')
    inputs = audit.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--models', type=Path, help='ID.MMD and ID.json effective species records')
    inputs.add_argument('--from', dest='derived', type=Path, help='derive output with imported-species records')
    audit.add_argument('--out', type=Path, required=True)
    audit.add_argument('--threshold', type=float, default=THRESHOLD)
    jumps = sub.add_parser('species', help='every species of a derive build: no clip may start at another body size '
                           'than the walk (the derive species check runs it)')
    jumps.add_argument('--content', type=Path, required=True, help="a derive build's species folder")
    jumps.add_argument('--out', type=Path)
    bake = sub.add_parser('bake')
    bake.add_argument('model', type=Path)
    bake.add_argument('record', type=Path)
    bake.add_argument('out', type=Path)
    bake.add_argument('--feet', type=int, nargs='+')
    args = parser.parse_args()
    if args.command == 'species':
        allowed = json.loads((ROOT / 'content/modeldelta/scale-audit.json').read_text())
        rows = audit_species(args.content, allowed)
        if args.out:
            args.out.write_text(json.dumps(rows, indent=1) + '\n')
        bad = [r for r in rows if r['jumps']]
        for r in bad:
            print(f"{r['id']} {r['name']}: " + ', '.join(f"slot {j['slot']} at {j['scale']:.3f} (walk {j['walk']:.3f})"
                                                       for j in r['jumps']), file=sys.stderr)
        print(f'{len(rows)} species; {len(bad)} change size between clips (more than {JUMP:.0%} from the walk)')
        if bad:
            sys.exit(1)
    elif args.command == 'audit':
        rows = []
        folder = args.derived / 'imported-species' if args.derived else args.models
        expected = {r['id'] for r in json.loads((ROOT / 'content/modeldelta/models.json').read_text())['models']}
        for path in sorted(folder.glob('*.json')):
            record = json.loads(path.read_text())
            if 'model' not in record or record.get('id') not in expected:
                continue
            sk = record['model']['skeleton']
            if args.derived:
                import species
                record['_path'] = str(path.resolve())
                data = species.species_model(record)[0]
            else:
                data = path.with_suffix('.MMD').read_bytes()
            row = measure(mmd.MMD.parse(data, len(sk)), sk, args.threshold)
            rows.append(dict(id=record['id'], name=record['name'], sha256=hashlib.sha256(data).hexdigest(), **row))
        missing = expected - {r['id'] for r in rows}
        if missing:
            raise ValueError(f'incomplete import audit: missing {sorted(missing)}')
        args.out.write_text(json.dumps(rows, indent=2) + '\n')
        print(f'{len(rows)} species; {sum(bool(r["across_slots"]) for r in rows)} exceed {args.threshold:.0%}')
    else:
        record = json.loads(args.record.read_text())
        data, report = lock(args.model.read_bytes(), record['model']['skeleton'], args.feet, species_id=record['id'])
        args.out.write_bytes(data)
        args.out.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'{record["name"]}: {len(report["changed_slots"])} slots; soles {report["feet"]}; {len(data)} bytes')


if __name__ == '__main__':
    main()
