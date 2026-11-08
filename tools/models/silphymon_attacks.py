#!/usr/bin/env python3
"""Author Silphymon's grounded attacks, then bake its reviewed Ultimate size.

Offline only: store the output through models/edit.py. Native technique clips
supply the clocks and upper-body acting; Silphymon's boots retain their support
stance. Eased anticipation, delayed ears/tail and recovery replace the aliased
insect dive. The real Buster Dive retains Patamon's collision-window travel.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import mmd
import motioncyclelayer
import motionstorage
import retarget
import species
from tools.models.resize import resize_with_pace
from tools.models.buster_dive import native_dash

SOURCE = '8106a97592acaccfcbf58bde44ceb19290fca503f3701b793c7ddaf708243b1f'
OUTPUT = 'ac3609d32e82ec750182619b8be45b4191bb3df0fe2c76a5691f95233887adcc'
FACTOR = .80
# Technique order stays compatible with existing saves. Native references are
# selected by technique ID, never by the same numbered animation-table slot.
DONORS = [20, 20, 6, 20, 20, 20, 20, 20, 20, 31, 6, 20, 50, 6]
DONOR_PINS = {
    20: '4bbdf9a2763dab219bc599f0d9cfa44d93263fc5e00930d405ad055f68c22ed9',
    6: '92133a92320bb61053d93fe7d643c0a096a20966ff7bb7495ad897ac279b882c',
    31: 'b9e2d5adeffe04bc9020cbb612b36eac240c3fe56e953c36a3eb4f304b43c60e',
    50: '2adc3e18f0a322eef7f6d30b5bd22f6661bdf44820d3491dea0b9a67375902b2',
}
MAPS = {
    20: {2: 2, 3: 3, 6: 4, 7: 5, 8: 6, 9: 7, 10: 8, 11: 9},
    6: {2: 2, 3: 4, 6: 6, 7: 8, 8: 9, 9: 11, 10: 13, 11: 14},
    31: {2: 1, 3: 2},
    50: {2: 2, 3: 3},
}


def smooth(x):
    x = max(0., min(1., x))
    return x*x*(3-2*x)


def pulse(t, a, peak, end):
    peak = min(peak, end-2)
    a = min(a, peak-2)
    if t <= peak:
        return smooth((t-a)/max(1., peak-a))
    return 1-smooth((t-peak)/max(1., end-peak))


def author(data):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the pinned corrected-proportion, native-walk model')
    spec = json.loads((ROOT / 'content/species/226-silphymon.json').read_text())
    sk = spec['model']['skeleton']; nb = len(sk)
    mmd.exe().add_type(226, sk)
    model = mmd.MMD.parse(data, nb); model.type = 226
    rest = copy.deepcopy(animsheet.slot_frames(model, nb, 0)[0][0])
    rest[0] = [4096]*3+[0]*6
    out = copy.deepcopy(model)
    originals = species.originals()
    ids = species.techniques_from_json(spec['techniques'], 'Silphymon')
    checks = []
    roots, _ = mmd.simulate(native_dash(), len(native_dash().pose)+1)
    for index, donor_id in enumerate(DONORS):
        slot = 46+index
        donor_data = Path(originals.model_path(donor_id)).read_bytes()
        if hashlib.sha256(donor_data).hexdigest() != DONOR_PINS[donor_id]:
            raise ValueError(f'native donor {donor_id} differs from its reviewed input')
        donor = mmd.MMD.load(originals.model_path(donor_id), donor_id)
        native_slot = 46+originals.rec[donor_id]['para']['moves'].index(ids[index])
        mapped = {t: (s, .65 if t in (2, 3) else .85) for t, s in MAPS[donor_id].items()}
        transfer = retarget.transfer(donor, donor_id, native_slot, 226, rest, mapped)
        count = transfer['n']
        events = [e for e in transfer['events'] if e[1] == 'sound']
        # Native Patamon also fixes the exact duration and dash root trajectory.
        if index == 9:
            count = len(roots)
        release = next((e[0] for e in events if e[0] > 3), count//2)
        release = max(7, min(release, count-7))
        frames = []
        for tick in range(count):
            f = copy.deepcopy(rest)
            envelope = smooth(tick/4)*smooth((count-1-tick)/6)
            for bone, rotations in transfer['rot'].items():
                for j in range(3):
                    delta = (rotations[min(tick,len(rotations)-1)][j]-rest[bone][3+j]+2048)%4096-2048
                    f[bone][3+j] += round(delta*envelope)
            # Weight prepares backwards, releases forwards, then settles. The
            # distal response peaks later; it never locks to the torso curve.
            prep = pulse(tick, 0, release*.5, release+2)
            strike = pulse(tick, release-3, release+2, count-2)
            rebound = pulse(tick, release+3, release+6, count-1)
            f[2][3] += round((-5*prep+9*strike-2*rebound)*4096/360)
            f[2][4] += round((4*prep-7*strike)*4096/360)
            for bone, sign in [(4,1),(5,-1),(20,1)]:
                lag = pulse(tick, release-1, release+5, count-1)
                f[bone][3] += round(sign*(-3*prep+6*lag)*4096/360)
            if donor_id in (31, 50):
                # Dash: wings swept back. Tremar: open then drive both fists.
                for shoulder, sign in [(6,1),(9,-1)]:
                    f[shoulder][3] += round((-22 if donor_id == 31 else 32)*strike*4096/360)
                    f[shoulder][5] += round(sign*12*prep*4096/360)
            if index == 8:
                # A visible right-leg kick, with the opposite boot supporting.
                f[12][3] -= round(55*strike*4096/360)
                f[13][3] += round(25*pulse(tick,0,release-2,release+4)*4096/360)
            # Slight knee give, rather than borrowing the insect carrier lift.
            for thigh, shin in [(12,13),(16,17)]:
                if index == 8 and thigh == 12:
                    continue
                f[thigh][3] += round(2*prep*4096/360)
                f[shin][3] -= round(4*prep*4096/360)
            mats = mmd.bone_matrices(model,f)
            supports = (18,19) if index == 8 else (14,15,18,19)
            floor = max(sum(mats[b][1][j]*v[j] for j in range(3))+mats[b][1][3]
                        for b in supports for v in model.tmd.obj_verts(sk[b][0]))
            f[1][7] -= round(floor)
            if index == 9:
                f[0] = [round(v) for v in roots[tick][0]]
            frames.append(f)
        # Body fitting allows four angle units (0.35 degrees); the dash root
        # is restored exactly after the size bake.
        animation = mmd.encode_anim(frames, nb, events=events, tol=4, repeats=False)
        out.anims.table[slot] = len(out.anims.anims)
        out.anims.anims.append(animation)
        checks.append(dict(slot=slot, technique=spec['techniques'][index], donor=donor_id,
                           native_slot=native_slot, ticks=count-1,
                           donor_sha256=hashlib.sha256(donor_data).hexdigest()))
    for animation in out.anims.anims:
        animation.tail = b''
    out.anims.anims,out.anims.table = motioncyclelayer.share_identical_streams(out.anims.anims,out.anims.table)
    authored = out.build()
    # Save the authored full-size intermediate for independent regression checks.
    result = resize_with_pace(authored, sk, 226, FACTOR)
    # Restore Buster Dive's native root after uniform resizing. Only this attack
    # must retain full entity travel to cross the EFE collision window.
    final = mmd.MMD.parse(result, nb); final.type = 226
    frames, _, events = animsheet.slot_frames(final, nb, 55)
    for f, root in zip(frames, roots):
        f[0] = [round(v) for v in root[0]]
    final.anims.anims[final.anims.table[55]] = mmd.encode_anim(frames,nb,events=events,tol=0,repeats=False)
    from tools.models.field_animations.chibi import _close_loops
    if _close_loops(final, nb, 1):
        raise ValueError('integer resize left a carrier loop open')
    result = final.build()
    if hashlib.sha256(result).hexdigest() != OUTPUT:
        raise ValueError('authored output differs from the reviewed result')
    report = dict(source_sha256=SOURCE, output_sha256=OUTPUT,
                  factor=FACTOR, techniques=checks, storage=motionstorage.require(result,nb))
    return result, authored, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('out',type=Path)
    a=p.parse_args()
    result,authored,report=author(a.source.read_bytes())
    a.out.write_bytes(result)
    a.out.with_suffix('.full-size.MMD').write_bytes(authored)
    a.out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
