#!/usr/bin/env python3
"""Compare built feline models: only locomotion sounds may change.

Usage: feline_sounds.py BEFORE_SPECIES_DIR AFTER_SPECIES_DIR --out REPORT.json
Checks every animation slot, geometry, poses, timing, texture/control events,
voice records and the resulting paw cues. Inputs are private derived models.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
import mmd
import species
from motiondiscidentity import changed_programs
from motionstorage import require

MOVEMENT = {2, 3, 4, 27, 35, 36}
PAWS = {198: 12, 221: 12, 222: 12, 234: 12, 258: 12, 293: 12, 323: 12, 432: 16}
REPLACE = {198: {13}, 258: {13, 20}, 323: {13}, 432: {21}, 293: {20}, 221: {20}}
AUDIT = [48, 166, 63, 198, 258, 306, 234, 222, 323, 276, 432, 476, 472, 215, 226, 221, 297, 293, 354, 409, 315, 316, 285, 18, 140, 256]


def check(before, after):
    old = species.load_content(str(before)); new = species.load_content(str(after))
    report = []
    for sid in AUDIT:
        a, b = old[sid], new[sid]
        raw_a, _ = species.species_model(a); raw_b, _ = species.species_model(b)
        bones = a['model'].get('skeleton')
        nb = len(bones) if bones else len(species.originals().rec[sid]['bones'])
        ma, mb = mmd.MMD.parse(raw_a, nb), mmd.MMD.parse(raw_b, nb)
        assert ma.tmd.build() == mb.tmd.build(), (sid, 'geometry')
        assert len(ma.anims.table) == len(mb.anims.table)
        strip = lambda anim: [i for i in anim.instrs if i['op'] != 'sound']
        cues = {}
        for slot, ai in enumerate(ma.anims.table):
            bi = mb.anims.table[slot]
            if ai is None:
                assert bi is None
                continue
            aa, ab = ma.anims.anims[ai], mb.anims.anims[bi]
            assert aa.pose == ab.pose and strip(aa) == strip(ab), (sid, slot, 'motion or texture/control events')
            sounds_a = [i for i in aa.instrs if i['op'] == 'sound']
            sounds_b = [i for i in ab.instrs if i['op'] == 'sound']
            if sid in PAWS and slot in MOVEMENT:
                assert sounds_b and len(sounds_a) == len(sounds_b), (sid, slot)
                assert [s['frame'] for s in sounds_a] == [s['frame'] for s in sounds_b], (sid, slot, 'cadence')
                assert all((s['bank'], s['note']) == (1, PAWS[sid]) for s in sounds_b), (sid, slot)
            else:
                expected = [dict(i, note=PAWS[sid])
                            if i['bank']==1 and i['note'] in REPLACE.get(sid, ()) else i
                            for i in sounds_a]
                assert expected == sounds_b, (sid, slot, 'unrelated sound or landing cue')
            if slot in MOVEMENT or sounds_a != sounds_b:
                cues[slot] = dict(before=sorted({(s['bank'], s['note']) for s in sounds_a}),
                                  after=sorted({(s['bank'], s['note']) for s in sounds_b}))
        changed = changed_programs(ma, mb)
        allowed = MOVEMENT | {slot for slot, ai in enumerate(ma.anims.table) if ai is not None
                              and any(i['op']=='sound' and i['bank']==1 and i['note'] in REPLACE.get(sid, ())
                                      for i in ma.anims.anims[ai].instrs)}
        assert set(changed) <= allowed
        if sid not in PAWS:
            assert raw_a == raw_b, (sid, 'unchanged model')
        voice = lambda s: [s.get('voice'), s.get('partner', {}).get('voice')]
        if sid in (293, 323):
            assert voice(b) == [42, 3]
        else:
            assert voice(a) == voice(b), (sid, 'voice')
        report.append(dict(id=sid, name=b['name'], bytes_before=len(raw_a), bytes_after=len(raw_b),
                           changed_slots=changed, voices_before=voice(a), voices_after=voice(b),
                           movement=cues, storage=require(raw_b, nb)))
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('before', type=Path); ap.add_argument('after', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    report = check(a.before, a.after)
    a.out.write_text(json.dumps(report, indent=2)+'\n')
    print(f'PASS: {len(report)} audited species; only eight footstep sets (including landings) and two voice pairs change')
