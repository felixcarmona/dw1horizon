"""Developer-only canonical field origin pass, run by babies.encode before storing plain deltas.

The engine's shadow follows the entity origin, not a body bone. The calm hop authors split travel between a steady
root and a planted body; inherited clips and asymmetric meshes can have an offset too. Move the horizontal vertex
centroid onto the origin every tick and transfer its motion to the root. World-space vertex trajectories, including
ground contact, are unchanged up to a constant translation per clip. No acting, height, scale or event is changed.
The player's builder still only decodes the resulting deltas (no NumPy dependency).
"""
import numpy as np


def center(data, bones, sid):
    import animsheet
    import mmd
    import motioncyclelayer
    import motionstorage
    from tools.models import battle_qa as qa

    rig = qa.Rig.from_mmd(data, bones, sid)
    # All eight rigs hang their mesh from bone 1 directly under an unmeshed root.
    assert bones[0][0] == -1 and bones[1][1] == 0
    assert all(p >= 1 for _, p in bones[2:])
    model = mmd.MMD.parse(data, len(bones))
    programs = {model.anims.table[s]: s for s in range(5) if model.anims.table[s] is not None}
    for idx, slot in programs.items():
        frames, loop, events = animsheet.slot_frames(model, len(bones), slot)
        f = np.asarray(frames, float)
        assert not f[:, 0, 3:6].any(), 'centering requires field clips without root turns'
        assert np.all(f[:, 0, :3] == 4096), 'centering requires an unscaled root'
        shift = np.rint(qa.horizontal_centroids(qa.Clip(rig, f, loop))).astype(int)
        for t, pose in enumerate(frames):
            for j, axis in enumerate((0, 2)):
                pose[1][6 + axis] -= int(shift[t, j])
                pose[0][6 + axis] += int(shift[t, j] - shift[0, j])
            frames[t] = [[int(round(x)) for x in b] for b in pose]
        mmd.close_loop(frames, loop)
        # Replace in place: native battle/condition aliases keep sharing the same program.
        model.anims.anims[idx] = mmd.encode_anim(frames, len(bones), loop, events, tol=0)
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    output = model.build()
    motionstorage.require(output, len(bones))
    rows = qa.check_field_origin(output, bones, sid=sid)
    if any(row['verdict'] == 'fail' for row in rows.values()):
        raise ValueError(f'{sid}: field-origin round trip failed: {rows}')
    return output
