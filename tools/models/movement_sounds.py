"""Select native locomotion sounds without changing pose or texture programs."""
import copy
import hashlib

import animsheet
import mmd
import motionstorage
from motioncyclelayer import share_identical_streams
from motiondiscidentity import changed_programs


def apply(data, skeleton, sid, note, replace_notes=()):
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = sid
    new = copy.deepcopy(old)
    rows = []
    for slot in (2, 3, 4, 27, 35, 36):
        if slot >= len(old.anims.table) or old.anims.table[slot] is None:
            continue
        original = old.anims.anims[old.anims.table[slot]]
        authored = copy.deepcopy(original)
        sounds = [i for i in authored.instrs if i['op'] == 'sound']
        if sounds:
            for sound in sounds:
                sound.update(bank=1, note=note)
        else:
            frames, loop, _ = animsheet.slot_frames(old, len(skeleton), slot)
            period = len(frames) - 1
            if loop != 0:
                raise ValueError(f'movement slot {slot} must be a closed loop')
            # Native Seadramon pulses once per body cycle. Long source loops
            # repeat at the native 20-tick cadence rather than remaining silent.
            sounds = [dict(op='sound', frame=t + 1, bank=1, note=note)
                      for t in range(min(7, period - 1), period, 20)]
            for sound in sounds:
                at = next((i for i,k in enumerate(authored.instrs)
                           if k.get('frame', -1) > sound['frame']), len(authored.instrs) - 1)
                authored.instrs.insert(at, sound)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        # Poses, momentum, texture events and control flow stay byte-exact.
        strip = lambda a: [i for i in a.instrs if i['op'] != 'sound']
        assert authored.pose == original.pose and strip(authored) == strip(original)
        rows.append(dict(slot=slot, frames=[i['frame'] for i in sounds], bank=1, note=note))
    # A landing in a care or attack clip can carry the same donor footstep.
    # Replace only the explicitly selected SL cues; voices and impact effects stay.
    for slot, index in enumerate(old.anims.table):
        if slot in (2, 3, 4, 27, 35, 36) or index is None:
            continue
        original = old.anims.anims[index]
        authored = copy.deepcopy(original)
        sounds = [i for i in authored.instrs
                  if i['op'] == 'sound' and i['bank'] == 1 and i['note'] in replace_notes]
        if not sounds:
            continue
        for sound in sounds:
            sound['note'] = note
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        strip = lambda a: [i for i in a.instrs if i['op'] != 'sound']
        assert authored.pose == original.pose and strip(authored) == strip(original)
        rows.append(dict(slot=slot, frames=[i['frame'] for i in sounds], bank=1, note=note))
    new.anims.anims, new.anims.table = share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    storage = motionstorage.require(result, len(skeleton))
    return result, dict(species=sid, source_sha256=hashlib.sha256(data).hexdigest(),
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=changed_programs(old, mmd.MMD.parse(result, len(skeleton))),
                        sounds=rows, storage=storage)
