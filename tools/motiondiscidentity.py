#!/usr/bin/env python3
"""Verify selected source models, staged aliases, cold streams and actual ISO bytes.

The source-file SHA and the SHA after applying staged aliases are distinct pins.
This proof does not grant visual approval or execution coverage for any clip.
"""
import argparse
import copy
import importlib.util
import json
import re
import struct
from pathlib import Path
import coldsplit
import isolist
import motionlab as M
import species


def program(animation):
    # Unreferenced streams can become a preceding stream's unused parse tail
    # after aliasing. Compare the program consumed through END, excluding tail.
    result = copy.copy(animation)
    result.tail = b''
    return result.build()


def changed_programs(source, effective):
    def slot(model, index):
        if index >= len(model.anims.table) or model.anims.table[index] is None:
            return None
        return program(model.anims.anims[model.anims.table[index]])
    return [i for i in range(max(len(source.anims.table), len(effective.anims.table)))
            if slot(source, i) != slot(effective, i)]


def verify(models, stem):
    module = importlib.util.spec_from_file_location('motion_build_disc', M.HERE/'build-disc.py')
    disc = importlib.util.module_from_spec(module)
    module.loader.exec_module(disc)
    image = isolist.Img(str(stem)+'.bin')
    try:
        files = {r['path'].split('/')[-1]: r for r in disc.iso_files(str(stem)+'.bin')}
        def read(name):
            record = files[name]
            return b''.join(image.data(record['lba']+i) for i in range(record['sectors']))[:record['size']]
        archive = read('DIGI.DAT')
        actual_exe = read('SLUS_010.32')
    finally:
        image.f.close()
    if archive != (stem/'DIGI.DAT').read_bytes():
        raise ValueError('ISO archive differs from staging')
    staged_exe = (stem/'exe/SLUS_010.32').read_bytes()
    text = (stem/'exe/SLUS_010.32.elf.map').read_text()
    address = int(re.search(r'\s+(0x[0-9a-f]+)\s+FILE_OFFSET_TABLE\s*$', text, re.M)[1], 16)-0x80090000
    masked = bytearray(actual_exe)
    count = 0
    # the entries' names: a pointer (12-byte entries) or, since patch 0210, in the entry (20 bytes, char[12])
    inline = not 0x80090000 <= struct.unpack_from('<I', staged_exe, address+8)[0] < 0x80200000
    while True:
        offset = address+count*(20 if inline else 12)
        if inline:
            name = staged_exe[offset+8:offset+20].split(b'\0')[0]
        else:
            ptr = struct.unpack_from('<I', staged_exe, offset+8)[0]
            if not 0x80090000 <= ptr < 0x80200000:
                break
            name = staged_exe[ptr-0x80090000:staged_exe.index(b'\0', ptr-0x80090000)]
        if not re.fullmatch(rb'[A-Z0-9_.]{1,16}', name):
            break
        masked[offset:offset+8] = staged_exe[offset:offset+8]
        count += 1
        if inline and name == b'NULL':
            break
    if not count or bytes(masked) != staged_exe:
        raise ValueError('ISO executable differs beyond file sector/size entries')
    _, _, records = species.read_archive(str(stem/'DIGI.DAT'))
    results = []
    for selected in json.loads((models/'report.json').read_text())['results']:
        sid = selected['species']
        spec = json.loads(next((stem/'species').glob(f'{sid}-*.json')).read_text())
        whole, path = species.species_model(spec)
        source = Path(path).read_bytes()
        if M.digest(source) != selected['output_sha256']:
            raise ValueError(f'{sid}: selected source differs')
        record = records[sid]
        if list(map(tuple, record['bones'])) != list(map(tuple, spec['model']['skeleton'])):
            raise ValueError(f'{sid}: archive rig differs')
        resident, cold = coldsplit.split(whole, record['para']['boneCount'])
        start = record['modelSector']*2048
        cold_start = start+((len(resident)+2047)//2048)*2048
        if archive[start:start+record['modelSize']] != resident or archive[cold_start:cold_start+len(cold)] != cold:
            raise ValueError(f'{sid}: archive resident/cold bytes differ')
        before = M.mmd.MMD.parse(source, record['para']['boneCount'])
        after = M.mmd.MMD.parse(whole, record['para']['boneCount'])
        changes = changed_programs(before, after)
        aliases = {i for i, _ in spec['model'].get('slot_aliases', [])}
        if before.tmd.build() != after.tmd.build() or not set(changes) <= aliases or set(changes) & {0, 1, 2, 3, 4, 18, 33}:
            raise ValueError(f'{sid}: unexpected mesh/field/native-source program change')
        results.append(dict(species=sid, selected_model_sha256=M.digest(source),
            effective_archive_model_sha256=M.digest(whole), alias_changed_slots=changes,
            resident_bytes=len(resident), cold_bytes=len(cold), resident_exact=True,
            cold_exact=True, rig_exact=True, mesh_exact=True,
            every_nonaliased_consumed_program_exact=True, core_and_native_source_slots_exact=True))
    return dict(disc=str(stem)+'.cue', archive_sha256=M.digest(archive), iso_archive_exact=True,
        iso_executable_sha256=M.digest(actual_exe), staged_executable_sha256=M.digest(staged_exe),
        executable_exact_except_iso_file_sector_size_table=True, file_table_rows=count,
        program_comparison_excludes_unconsumed_parse_tails=True, results=results)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('models', 'disc-stem', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    proof = verify(a.models, a.disc_stem)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(proof, indent=2)+'\n')
    print('Verified ISO archive, executable, rig and models:', len(proof['results']))
