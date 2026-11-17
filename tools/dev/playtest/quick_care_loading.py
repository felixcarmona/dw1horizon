#!/usr/bin/env python3
"""Square care after battle preload has replaced MENU, with both reported partners.

python3 tools/dev/playtest/quick_care_loading.py DISC --exe EXE --card CARD --out OUT
Boots its own fixture; no states from other executables. Defaults to 8 MB RAM.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.quick_care import need, wait, care_object
from tools.langpatch import elf_symbols


def evolve(e, species):
    e.run('pause')
    for name, fmt, value in (
        ('EVOLUTION_TARGET', 'h', species), ('HAS_USED_EVOITEM', 'B', 1),
        ('TAMER_STATE', 'B', 6), ('TAMER_SUB_STATE', 'B', 0),
        ('PARTNER_STATE', 'B', 13), ('PARTNER_SUB_STATE', 'B', 0),
    ):
        e.poke(name, struct.pack('<' + fmt, value))
    e.run('resume')
    for _ in range(240):
        if e.peek('PARTNER_ENTITY', 'i') == species and e.peek('PARTNER_STATE', 'b') == 1:
            break
        e.press('START', 8)
        e.wait(.25)
    else:
        raise AssertionError(f'fixture evolution to {species} failed')
    e.poke('PAUSE_STATE', b'\0')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disc')
    parser.add_argument('--exe', required=True)
    parser.add_argument('--card', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--port', type=int, default=42179)
    parser.add_argument('--ram', type=int, choices=(2, 8), default=8)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(args.disc, args.exe, args.port, str(out / 'emu'))
    # The save compatibility harness enforces 2 MB; this field test also uses 8 MB.
    e.ram = lambda: e.api('/api/v1/cpu/ram/raw')
    e.env['EMU_ARGS'] = '-interpreter -debugger' + (' -8mb' if args.ram == 8 else '')
    for name, (addr, _, _) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(name, addr)
    result = {'exe_sha256': hashlib.sha256(Path(args.exe).read_bytes()).hexdigest(),
              'ram_mb': args.ram, 'cases': []}
    species = None
    try:
        e.start(args.card)
        assert e.continue_game() == 0
        assert len(e.ram()) == args.ram * 1024 * 1024
        e.run('save', str(out / 'boot.state'))
        for species in (280, 373):
            e.run('load', str(out / 'boot.state'))
            evolve(e, species)
            e.poke('MOD_OPT_QUICK_BATTLE', struct.pack('<i', 1))
            assert e.warp(171)
            need(e)
            wait(e, 'MOD_BTL_PRELOAD', 2, 'b')
            # MENU must be absent: otherwise stale valid code masks the race.
            e.run('save', str(out / f'field-{species}.state'))
            flag = 'feedMenuReading' if e.has('feedMenuReading') else 'feedMenuRead'
            e.run('lua', f'''
                CARE_TICKS=0; CARE_EARLY=false
                CARE_TBP=PCSX.addBreakpoint({e.A('gameLoop')},'Exec',4,'care-frames',function()
                    CARE_TICKS=CARE_TICKS+1
                end)
                CARE_NBP=PCSX.addBreakpoint({e.A('feedNote')},'Exec',4,'care-overlay',function()
                    if PCSX.getMemPtr()[{e.A(flag) - 0x80000000}]~=0 then CARE_EARLY=true end
                end)
            ''')
            try:
                for opening in range(2):
                    e.press('SQUARE', 8)
                    wait(e, 'feedState', 1)
                    assert care_object(e)
                    assert e.run('lua', 'return CARE_EARLY').strip() == 'false', 'MENU executed during its read'
                    before = int(e.run('lua', 'return CARE_TICKS').strip())
                    time.sleep(.5)
                    assert int(e.run('lua', 'return CARE_TICKS').strip()) > before, 'game loop stopped'
                    e.run('shot', str(out / f'care-{species}-{opening}.png'))
                    e.press('CANCEL', 8)
                    wait(e, 'TAMER_STATE', 0, 'b')
                    assert not care_object(e)
            finally:
                e.run('lua', 'CARE_TBP:remove();CARE_NBP:remove()')
            result['cases'].append({'species': species, 'opens_and_closes': 2, 'no_early_MENU_execution': True})
            print(species, 'passed', flush=True)
    except BaseException as error:
        result['error'] = f'{species}: {error}'
        e.run('shot', str(out / 'failure.png'), check=False)
        e.run('save', str(out / 'failure.state'), check=False)
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
