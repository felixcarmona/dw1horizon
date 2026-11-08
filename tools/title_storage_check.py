#!/usr/bin/env python3
"""Check the title UI's overlay lifetime, sector bounds and language independence.

Usage: python3 tools/title_storage_check.py build/NAME/exe-*/SLUS_010.32.elf
The title loads EVL before MENU; world saves still load MENU alone. The appended
UI must survive MENU sector reads and contain no language-dependent bytes.
"""
import argparse
import hashlib
from pathlib import Path

from xref import Elf, graph


def check(path):
    elf = Elf(path)
    symbols = {name: (address, index) for name, address, _, _, index in elf.syms}
    evl = elf.sh[elf.byname['.EVL']]
    menu = elf.sh[elf.byname['.MENU']]
    start, end = (symbols[name][0] for name in ('title_ui_START', 'title_ui_END'))
    assert menu['size'] <= 55296 - 100, ('MENU spare', 55296 - menu['size'])
    read_end = menu['addr'] + ((menu['size'] + 2047) & ~2047)
    assert read_end <= start < end <= evl['addr'] + evl['size']
    assert evl['addr'] + ((evl['size'] + 2047) & ~2047) <= 0x80070000
    for name in ('modDrawLanguagePicker', 'modTickLanguagePicker',
                 'modRenderLanguagePicker', 'modDrawLanguageName',
                 'modShowLanguageError', 'modRenderLanguageError', 'modFlagRect',
                 'MOD_FLAG_PALETTE', 'MOD_FLAG_OFFSET', 'MOD_FLAG_RUNS',
                 'MOD_CHINESE_NAME', 'MOD_LANGUAGE_TITLES', 'MOD_LANGUAGE_TITLE_GLYPHS',
                 'drawOptionsText', 'renderOptionsMenu', 'modSetOption',
                 'modOptionValue', 'modOptionText', 'modOptionCount'):
        assert start <= symbols[name][0] < end, (name, symbols[name])
    for name in ('modOptionBytes',):
        assert elf.sh[symbols[name][1]]['name'] == '.MENU', name
    for name in ('loadMenuOverlay', 'loadTitleMenuOverlays', 'modMenuVsBattle', 'MOD_LANGUAGE_NAMES'):
        assert elf.sh[symbols[name][1]]['name'] == '.main', name
    # Enumerate actual linked references, including pointers and switch tables.
    # Only the title branches of these MENU functions may enter the EVL tail.
    callers = {'drawMainMenuStrings', 'drawOptionsText', 'tickMainMenu', 'renderMainMenu'}
    _, _, edges = graph(path)
    references = 0
    for (section, target), sites in edges.items():
        address = symbols.get(target, (0, 0))[0]
        if section != '.EVL' or not start <= address < end:
            continue
        for (origin, caller), _ in sites:
            if origin == '.EVL':
                # xref names anonymous switch-table words by their actual address.
                if caller in symbols:
                    address = symbols[caller][0]
                else:
                    assert caller.startswith('?'), caller
                    address = int(caller[1:], 16)
                assert start <= address < end, (caller, target)
            else:
                assert origin == '.MENU' and caller in callers, (origin, caller, target)
            references += 1
    assert references
    offset = evl['off'] + start - evl['addr']
    data = elf.d[offset:offset + end - start]
    print(f'{path.parent.name}: MENU {menu["size"]} B, spare {55296 - menu["size"]} B; '
          f'title {start:#x}..{end:#x}, {references} checked references; '
          f'sha256 {hashlib.sha256(data).hexdigest()}')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf', nargs='+', type=Path)
    args = parser.parse_args()
    blocks = [check(path) for path in args.elf]
    assert all(block == blocks[0] for block in blocks), 'Language switch would need to reload title storage'
    print(f'PASS: {len(blocks)} layouts; identical title bytes survive MENU reloads')


if __name__ == '__main__':
    main()
