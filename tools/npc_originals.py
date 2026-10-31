#!/usr/bin/env python3
"""Check field NPC sizes, slots and collision rows against the player's disc.

Run after a real disc build: python3 tools/npc_originals.py build/NAME.
The image is read independently of the derived model files. Native rows use
that build's linker map; archive rows and models come from its DIGI.DAT.
"""
import argparse
import glob
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import dwmap
import isolist
import mmd
import species as S

# Reviewed differences in field NPCs. Keep this list small and explain each.
EXCEPTIONS = {}


class Disc:
    def __init__(self, path):
        self.img = isolist.Img(str(path))
        root = self.img.data(16)[156:190]
        rows = []
        isolist.walk(self.img, struct.unpack_from('<I', root, 2)[0],
                     struct.unpack_from('<I', root, 10)[0], '', rows)
        self.files = {r['path'].lstrip('/'): r for r in rows}

    def read(self, name):
        r = self.files[name]
        return b''.join(self.img.data(r['lba'] + i) for i in range(r['sectors']))[:r['size']]


def posed_size(data, bones, source):
    model = mmd.MMD.parse(data, len(bones))
    model.type = source
    idle = model.anims.table[0]
    if idle is None:
        raise ValueError('no idle slot')
    player = mmd.AnimPlayer(model.anims.anims[idle], len(bones), 0)
    if not player.tick(stop_at_infinite_loop=True):
        raise ValueError('idle has no pose')
    e = mmd.exe()
    old = e.skeleton[source]
    try:
        e.skeleton[source] = bones
        mats = mmd.bone_matrices(model, player.pose)
    finally:
        e.skeleton[source] = old
    pts = []
    for b, (obj, _) in enumerate(bones):
        if obj < 0:
            continue
        mat = mats[b]
        for x, y, z, _ in model.tmd.obj_verts(obj):
            pts.append(tuple(mat[i][0]*x + mat[i][1]*y + mat[i][2]*z + mat[i][3] for i in range(3)))
    return tuple(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)), model


def check(out):
    out = Path(out)
    disc = Disc(Path(str(out) + '.bin'))
    data = disc.read('DIGI.DAT')
    _, _, _, count, _, rsec, *_ = struct.unpack_from(S.HEADER, data)
    recs = [S.unpack_record(data[rsec*S.SECTOR+t*S.RECORD_SIZE:rsec*S.SECTOR+(t+1)*S.RECORD_SIZE], t)
            for t in range(count)]
    twins = {s['_npc_original']: t for t, s in S.load_content(str(out / 'species')).items() if '_npc_original' in s}
    linkmap = (out / 'exe/SLUS_010.32.elf.map').read_text()
    address = int(re.search(r'0x([0-9a-fA-F]+)\s+DIGIMON_DATA\b', linkmap)[1], 16)
    exe = disc.read('SLUS_010.32')
    if twins:
        table = b''.join(struct.pack('<hh', original, twin) for original, twin in sorted(twins.items()))
        if not re.search(r'\bnpcSpeciesType\b', linkmap) or table not in exe:
            raise ValueError('NPC twin mapping is absent from the built executable')
    scale_address = int(re.search(r'0x([0-9a-fA-F]+)\s+MOD_MODEL_SCALE\b', linkmap)[1], 16)
    scales = dict(struct.unpack_from('<hh', exe, scale_address - S.EXE_BASE + 4*i) for i in range(8))
    # Every native type appearing in map data or a script spawn is an NPC input.
    types = set()
    for f in glob.glob(str(ROOT / 'extracted/MAP/**/*.MAP'), recursive=True):
        types.update(d['type'] for d in dwmap.MapFile(Path(f).read_bytes()).digimon)
    for f in (out / 'story' / 'dis').glob('*.txt'):
        types.update(int(x) for x in re.findall(r'\bSET_DIGIMON(?:16)?\s+(\d+)', f.read_text()))
    originals = S.originals()
    failed = []
    checked = 0
    for t in sorted(types & set(range(180))):
        original = originals.rec[t]
        path = originals.model_path(t)
        if path is None or not Path(path).exists():
            raise ValueError(f'{t}: missing original model')
        before = Path(path).read_bytes()
        actual_type = twins.get(t, t)
        r = recs[actual_type]
        if actual_type >= 180 or t in S.record_originals(data):
            after = data[r['modelSector']*S.SECTOR:r['modelSector']*S.SECTOR+r['modelSize']]
            para, bones = r['para'], r['bones']
        else:
            modelpath = str(Path(path).relative_to(ROOT / 'extracted'))
            after = disc.read(modelpath)
            para = S.unpack(S.PARA_FIELDS, exe, address - S.EXE_BASE + t*52)
            bones = original['bones']
        oldsize, oldmodel = posed_size(before, original['bones'], t)
        newsize, newmodel = posed_size(after, bones, t)
        # initializeDigimonObject: vanilla Meteormon is 150%; the build reads MOD_MODEL_SCALE.
        original_scale = 1.5 if t == 113 else 1.0
        actual_scale = (scales.get(actual_type, 100) * 4096 // 100) / 4096
        oldsize = tuple(x * original_scale for x in oldsize)
        newsize = tuple(x * actual_scale for x in newsize)
        reasons = []
        if any(abs(b-a) > max(abs(a)*.01, .001) for a, b in zip(oldsize, newsize)):
            reasons.append(f'posed size {oldsize} -> {newsize}')
        missing = [i for i, a in enumerate(oldmodel.anims.table) if a is not None and
                   (i >= len(newmodel.anims.table) or newmodel.anims.table[i] is None)]
        if missing:
            reasons.append(f'missing animation slots {missing}')
        for key in ('radius', 'height'):
            if para[key] != original['para'][key]:
                reasons.append(f'{key} {original["para"][key]} -> {para[key]}')
        if reasons:
            if t in EXCEPTIONS:
                print(f'exception {t}: {EXCEPTIONS[t]}: {"; ".join(reasons)}')
            else:
                failed.append(t)
                print(f'FAIL {t}: {"; ".join(reasons)}')
        checked += 1
    print(f'NPC originals: {checked} checked, {len(failed)} failed')
    return bool(failed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    raise SystemExit(check(parser.parse_args().out))
