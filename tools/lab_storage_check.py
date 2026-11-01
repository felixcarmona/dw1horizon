#!/usr/bin/env python3
"""Audit laboratory storage and every allocated object relocation into it.

Usage: python3 tools/lab_storage_check.py build/decomp-int
Run for each language's native tree after building patch 0293. Object relocations
cover anonymous literals that have no symbol in xref.py's linked address graph.
"""
import struct
import sys
from pathlib import Path

from xref import Elf


def check(tree):
    native = tree / 'build/us/psx/gcc'
    obj = Elf(native / 'src/main/mod_lab.c.o')
    linked = Elf(native / 'SLUS_010.32.elf')
    locations = {}
    for name, _, _, _, index in linked.syms:
        if 0 < index < len(linked.sh):
            locations.setdefault(name, set()).add(linked.sh[index]['name'])
    moved = {'.rodata', '.rodata.LAB_FIELDS', '.rodata.LAB_HOME_TEXT', '.bss.labText'}
    for name in sorted(moved):
        section = obj.sh[obj.byname[name]]
        if name != '.bss.labText':
            assert not section['flags'] & 1, (name, 'must be compiler read-only data')
        else:
            assert section['type'] == 8 and section['size'] == 960
        print(f'{name}: {section["size"]} bytes')
    for name in ('LAB_FIELDS', 'LAB_HOME_TEXT', 'labText'):
        assert locations[name] == {'.MENU'}, (name, locations[name])
    for name in ('modRosterTick', 'modRosterRenderCaption', 'modRosterTickCaption',
                 'MOD_LAB_EVO_TARGETS'):
        assert locations[name] == {'.main'}, (name, locations[name])
    assert locations['modRosterText'] == {'.bss'}
    captions = [name for name in locations if name.startswith(('ROSTER_', 'LEVEL_TEXT.'))]
    assert len(captions) == 7, captions
    for name in captions:
        assert locations[name] == {'.main'}, (name, locations[name])
    references = 0
    for rel in obj.sh:
        if rel['type'] != 9:
            continue
        source = obj.sh[rel['info']]
        if not source['flags'] & 2:
            continue  # Debug records do not execute or survive in the game.
        for offset in range(rel['off'], rel['off'] + rel['size'], rel['entsize']):
            site, info = struct.unpack_from('<II', obj.d, offset)
            symbol = obj.syms[info >> 8]
            if not 0 < symbol[4] < len(obj.sh):
                continue
            target = obj.sh[symbol[4]]['name']
            if target not in moved:
                continue
            origin = source['name']
            if origin.startswith('.text.'):
                function = origin[len('.text.'):]
                assert locations[function] == {'.MENU'}, (origin, target, locations[function])
            else:
                assert origin in moved, (origin, target, 'resident data retains a pointer')
            print(f'  {origin}+0x{site:x} -> {target} (reloc {info & 255})')
            references += 1
    assert references
    print(f'PASS: {references} allocated relocations; only MENU code/data reaches moved storage')


if __name__ == '__main__':
    check(Path(sys.argv[1]))
