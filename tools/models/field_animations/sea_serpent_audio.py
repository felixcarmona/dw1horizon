"""Route imported sea-serpent programs through native MegaSeadramon's cues.

The source import used Birdramon's event track. Keep the imported performance
and texture events, but take each technique's sound cues from its aquatic peer.
"""
import copy
import hashlib
import animsheet
import mmd
import motioncyclelayer
import motionstorage


def repair(data, skeleton, donor, techniques, donor_techniques):
    if hashlib.sha256(data).hexdigest() != '3230a3c7a4ae156b6dfe58880dd0cf3db7e310ae37ae3670b53d702de5e4ad8f':
        raise ValueError('Sea-serpent audio repair requires the reviewed import')
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = 211
    original = copy.deepcopy(model)
    changed = []
    for slot, index in enumerate(original.anims.table):
        if index is None:
            continue
        if slot >= 46 and slot-46 < len(techniques):
            technique = techniques[slot-46]
            # Machine techniques use the family's ranged-attack voice.
            source = 46 + (donor_techniques.index(technique)
                           if technique in donor_techniques else 0)
        elif slot < 46 and slot < len(donor.anims.table) and donor.anims.table[slot] is not None:
            source = slot
        else:
            continue
        own = copy.deepcopy(original.anims.anims[index])
        native = donor.anims.anims[donor.anims.table[source]]
        own.instrs = [i for i in own.instrs if i['op'] != 'sound']
        length = len(animsheet.slot_frames(original, len(skeleton), slot)[0])-1
        native_length = len(animsheet.slot_frames(donor, donor.nbones, source)[0])-1
        for cue in native.instrs:
            if cue['op'] != 'sound':
                continue
            event = dict(cue, frame=1+round((cue['frame']-1)*length/max(1,native_length)))
            at = next((j for j,i in enumerate(own.instrs)
                       if i.get('frame', 0) > event['frame']), len(own.instrs)-1)
            own.instrs.insert(at,event)
        if own.instrs != original.anims.anims[index].instrs:
            changed.append(slot)
            model.anims.table[slot] = len(model.anims.anims)
            model.anims.anims.append(own)
    # Remove the bird-only transition cues in slots the aquatic donor lacks.
    for slot,index in enumerate(model.anims.table):
        if index is None:
            continue
        anim=model.anims.anims[index]
        anim.instrs=[i for i in anim.instrs
                     if not(i['op']=='sound' and i['bank']==1 and i['note']==15)]
    for anim in model.anims.anims:
        anim.tail=b''
    model.anims.anims,model.anims.table=motioncyclelayer.share_identical_streams(model.anims.anims,model.anims.table)
    result=model.build()
    motionstorage.require(result,len(skeleton))
    assert original.tmd.build()==model.tmd.build()
    parsed=mmd.MMD.parse(result,len(skeleton))
    for slot,index in enumerate(original.anims.table):
        if index is None:
            assert parsed.anims.table[slot] is None
            continue
        before=original.anims.anims[index]
        after=parsed.anims.anims[parsed.anims.table[slot]]
        assert before.pose==after.pose and before.frame_count==after.frame_count
        assert [i for i in before.instrs if i['op']!='sound']==[i for i in after.instrs if i['op']!='sound']
        assert all(not(i['bank']==1 and i['note']==15) for i in after.instrs if i['op']=='sound')
    return result,dict(sound_donor=61,changed_slots=changed)


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    own = json.loads(Path('content/species/211-metalseadramon.json').read_text())
    family = json.loads(Path('content/species/61-megaseadramon.json').read_text())
    donor = mmd.MMD.load('extracted/CHDAT/MMD2/MGSD.MMD',61)
    result,proof = repair(args.source.read_bytes(),own['model']['skeleton'],donor,own['techniques'],family['techniques'])
    args.output.write_bytes(result)
    args.output.with_suffix('.json').write_text(json.dumps(proof,indent=2)+'\n')
