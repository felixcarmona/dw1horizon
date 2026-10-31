"""Restore native hidden equipment in donor clips; keep explicit native scale tracks."""
import copy
import hashlib
import json
from pathlib import Path

import mmd
import animsheet
import motionstorage
from motiondiscidentity import changed_programs
from motioncyclelayer import share_identical_streams

PROFILES = Path(__file__).resolve().parents[3] / 'content/models/imports/animation-repairs.json'


def repair(model, hidden, hit=False):
    """Only a clip without scale data inherits the native equipment visibility."""
    out = copy.deepcopy(model)
    for anim in out.anims.anims:
        if not anim.has_scale:
            anim.pose = [[4096, 4096, 4096] + p for p in anim.pose]
            anim.has_scale = True
            for bone in hidden:
                anim.pose[bone - 1][:3] = [0, 0, 0]
    if hit:
        # The old native hit holds its starting body pose for ten ticks.
        # Reach the same recoil early, then recover without changing its
        # duration or the original root program.
        for slot in (0x28, 0x29):
            original = out.anims.anims[out.anims.table[slot]]
            assert original.frame_count == 20
            frames, loop, _ = animsheet.slot_frames(out, len(original.pose) + 1, slot)
            assert loop is None and len(frames) == 20
            samples = []
            for tick, source in enumerate(frames):
                pose = copy.deepcopy(source)
                weight = min(1, tick / 3) if tick <= 5 else (19 - tick) / 14
                for bone in range(1, len(pose)):
                    for channel in range(3, 9):
                        delta = frames[-1][bone][channel] - frames[0][bone][channel]
                        if channel < 6:
                            delta = (delta + 2048) % 4096 - 2048
                        pose[bone][channel] = round(frames[0][bone][channel] + weight * delta)
                samples.append([[int(round(v)) for v in channels] for channels in pose])
            from tools.models.field_animations.articulation import replace_channels
            channels = {(b, c) for b in range(1, len(samples[0])) for c in range(3, 9)}
            anim = replace_channels(original, samples, None, len(samples[0]), channels, tolerance=0)
            for ins in anim.instrs:
                if ins['op'] == 'sound':
                    ins['frame'] = 1
            anim.instrs.sort(key=lambda ins: (ins.get('frame', anim.frame_count + 1), ins['op'] == 'sound'))
            assert anim.frame_count == original.frame_count
            out.anims.anims.append(anim)
            out.anims.table[slot] = len(out.anims.anims) - 1
    for anim in out.anims.anims:
        anim.tail = b''
    out.anims.anims, out.anims.table = share_identical_streams(out.anims.anims, out.anims.table)
    return out


def build(data, skeleton):
    digest = hashlib.sha256(data).hexdigest()
    profiles = json.loads(PROFILES.read_text())
    found = [(int(sid), p) for sid, p in profiles.items() if p['source_sha256'] == digest]
    if len(found) != 1:
        raise ValueError('equipment recipe requires its reviewed imported source')
    sid, profile = found[0]
    nb = len(skeleton)
    assert nb == profile['bones']
    mmd.exe().skeleton[sid] = skeleton
    mmd.exe().bone_count[sid] = nb
    original = mmd.MMD.parse(data, nb)
    base = original
    walking = None
    if sid == 351:
        from tools.models.field_animations import articulation
        data, walking = articulation.build(data, skeleton)
        base = mmd.MMD.parse(data, nb)
    result = repair(base, profile['hidden_bones'], profile.get('early_hit', False)).build()
    parsed = mmd.MMD.parse(result, nb)
    assert original.tmd.build() == parsed.tmd.build()
    changed = changed_programs(original, parsed)
    expected = profile['changed_slots']
    assert changed == expected, (changed, expected)
    storage = motionstorage.audit(result, nb)
    assert storage['fits'], storage
    return result, dict(species=sid, source_sha256=digest,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=changed, mesh_exact=True,
                        native_scale_tracks_preserved=True, hit_duration_preserved=True,
                        walking=walking, storage=storage)
