"""Local, eased joint limits while retaining each program's root and events."""
import math
import mmd


def smoothstep(x):
    x = max(0., min(1., x))
    return x*x*(3-2*x)


def elbow_pitch(value):
    """Mechanical elbow arc, continuous with its derivative across a full turn.

    Keep the ordinary 70-degree swing. Ease into a 90-degree limit; an imported
    full-turn windup opens the elbow through a smooth arc instead of folding
    the gun back into the shoulder. A signed clamp would jump at half a turn.
    """
    angle = ((value+2048) % 4096-2048)*360/4096
    a = abs(angle)
    if a <= 70:
        result = a
    elif a <= 110:
        result = 70+(a-70)-(a-70)**2/80
    else:
        result = 90*(1-smoothstep((a-110)/70))
    return round(math.copysign(result, angle)*4096/360)


def edit(model, bones, mapper, slots=None):
    """Replace only the selected rotation channels; preserve event/control code.

    mapper(slot, tick, poses) returns {(bone, axis): angle}, in engine units.
    Aliases are processed once, retaining the table and all original programs.
    """
    import animsheet
    from tools.models.field_animations.articulation import replace_channels
    done, report = set(), []
    for slot, index in enumerate(model.anims.table):
        if index is None or index in done or slots is not None and slot not in slots:
            continue
        done.add(index)
        poses, loop, _ = animsheet.slot_frames(model, len(bones), slot, max_ticks=6000)
        if len(poses) >= 6000:
            raise ValueError('joint repair exceeded the clip decode guard')
        changes = [mapper(slot, tick, poses) for tick in range(len(poses))]
        channels = {(b, 3+a) for values in changes for b, a in values}
        if not any(poses[t][b][3+a] != value for t, values in enumerate(changes)
                   for (b, a), value in values.items()):
            continue
        frames = [[list(b) for b in p] for p in poses]
        for t, values in enumerate(changes):
            for (b, axis), value in values.items():
                frames[t][b][3+axis] = value
        original = model.anims.anims[index]
        result = replace_channels(original, frames, loop, len(bones), channels, tolerance=0)
        before, info = mmd.simulate(original, len(bones), slot=slot)
        after, got = mmd.simulate(result, len(bones), slot=slot)
        if info != got or len(before) != len(after):
            raise ValueError(f'joint repair changed slot {slot} timing or events')
        for t, (a, b) in enumerate(zip(before, after)):
            for bone in range(len(bones)):
                for c in range(9):
                    expected = frames[t][bone][c] if (bone, c) in channels else a[bone][c]
                    if b[bone][c] != expected:
                        raise ValueError(f'joint repair changed slot {slot} tick {t} channel {bone}/{c}')
        model.anims.anims[index] = result
        report.append(slot)
    return report
