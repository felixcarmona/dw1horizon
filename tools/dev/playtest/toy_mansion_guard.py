#!/usr/bin/env python3
"""Exercise the left ClearAgumon's touch encounter on Toy Mansion screen 150, with 2 MB RAM.

Boot a memory card on DISC with its own EXE. From the room entrance, walk
diagonally up-left into the guard using normal pad input. --expect-loop verifies
an unfixed disc:
confirming and trying to leave repeatedly returns to section 7 at the same spot.
The default requires battle entry, victory, field control and movement afterward.
Enemy HP is cleared after battle entry to shorten combat; loading and results run
normally. --patch-loaded demonstrates the script fix on an older disc in RAM;
its result is explicitly distinguished from testing a built disc.
"""
from pathlib import Path
import argparse
import json
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.dws import bytecode


def snapshot(e):
    ram = e.ram()
    assert len(ram) == 0x200000, 'requires original 2 MB RAM'
    return {name: e.peek(name, fmt, ram) for name, fmt in (
        ('CURRENT_SCREEN', 'h'), ('SCRIPT_SECTION', 'H'), ('IS_SCRIPT_PAUSED', 'i'),
        ('TAMER_STATE', 'b'), ('GAME_STATE', 'H'), ('TAMER_POSITION_DATA+0x78', '3i'))}


def approach_left(e):
    e.api('/api/v1/lua/press?button=LEFT')
    try:
        e.press('UP', 100)
    finally:
        e.api('/api/v1/lua/release?button=LEFT')


def patch_loaded(e):
    """Append battle() before section 7's first END_SECTION, leaving its line intact."""
    ram = e.ram()
    base = e.A('MAP_SCRIPT_BUFFER')
    data = ram[base - 0x80000000:base - 0x80000000 + 0x2000]
    _, sections = bytecode.parse_header(data)
    start = dict(sections)[7]
    # On the unfixed release section 7 is last, say(...), END_SECTION, END_SECTION.
    # No later section or jump target may be overwritten by this test-only patch.
    assert start == max(off for _, off in sections)
    end = data.index(b'\xfe\x00\xfe\x00', start)
    assert end % 2 == 0 and data[end + 4:end + 16] == bytes(12)
    e.poke(f'MAP_SCRIPT_BUFFER+{end}', bytes.fromhex('27 00 67 00 01 00 66 00 fe 00 fe 00'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True); ap.add_argument('--card', required=True)
    ap.add_argument('--port', type=int, default=38943)
    ap.add_argument('--out', type=Path, default=Path('build/toy-mansion-guard'))
    ap.add_argument('--expect-loop', action='store_true')
    ap.add_argument('--patch-loaded', action='store_true')
    ap.add_argument('--quick', type=int, choices=(0, 1), default=1)
    ap.add_argument('--state', help='same-disc arrival state to skip boot/warp; never reuse across executables')
    a = ap.parse_args()
    assert not (a.expect_loop and a.patch_loaded)
    a.out.mkdir(parents=True, exist_ok=True)
    e = Emu(a.disc, a.exe, a.port, str(a.out / 'emu'))
    e.ram = lambda: e.api('/api/v1/cpu/ram/raw')
    result = dict(expect_loop=a.expect_loop, patched_ram=a.patch_loaded, quick=a.quick, samples=[])
    def sample(label):
        s = snapshot(e); result['samples'].append(dict(label=label, **s))
        print(label, s, flush=True)
        return s
    try:
        e.start(a.card)
        if a.state:
            e.run('load', str(Path(a.state).resolve()))
        else:
            assert e.continue_game() == 0, 'Continue failed'
            assert e.in_control(), 'no control after Continue'
        e.gs('set', 'hour=10', 'gametime_running=0', 'partner.para.condition=0',
             'partner.para.foodLevel=100', 'partner.para.energyLevel=100', 'partner.para.poopLevel=0',
             'partner.para.tiredness=0', 'partner.para.sleepyHour=23', 'partner.para.nextHungerHour=23',
             'partner.stats.hp=9000', 'partner.stats.mp=9000', 'partner.stats.currentHP=9000',
             'partner.stats.currentMP=9000', 'partner.stats.off=900', 'partner.stats.def=900')
        e.poke('MOD_OPT_QUICK_BATTLE', struct.pack('<i', a.quick))
        if not a.state:
            assert e.warp(150), 'room did not load'
        assert snapshot(e)['CURRENT_SCREEN'] == 150
        if a.patch_loaded:
            patch_loaded(e)
        approach_left(e)
        e.wait(.5)
        s = sample('contact')
        assert s['SCRIPT_SECTION'] == 7 and s['IS_SCRIPT_PAUSED'] == 0, 'wrong guard'
        e.run('shot', str(a.out / 'contact.png'))
        initial = s['TAMER_POSITION_DATA+0x78']
        if a.expect_loop:
            for i in range(6):
                e.press('CONFIRM', 8); e.press('RIGHT', 30); e.wait(.5)
                s = sample(f'confirm-and-leave-{i}')
                assert s['CURRENT_SCREEN'] == 150 and s['SCRIPT_SECTION'] == 7
                assert s['GAME_STATE'] == 0 and s['IS_SCRIPT_PAUSED'] == 0
                assert s['TAMER_POSITION_DATA+0x78'] == initial
            e.run('shot', str(a.out / 'loop.png'))
        else:
            for _ in range(30):
                e.press('CONFIRM', 8); e.wait(.5)
                if snapshot(e)['GAME_STATE'] == 1:
                    break
            else:
                raise AssertionError('dialogue did not start a battle')
            sample('battle-entry'); e.wait(8)
            e.run('shot', str(a.out / 'battle.png'))
            # Preserve normal loading, combat teardown, result boxes and script return.
            for i in range(8):
                e.poke(f'NPC_ENTITIES+{i * 0x68 + 0x4c}', b'\0\0')
            for _ in range(90):
                e.press('CONFIRM', 8); e.wait(.5)
                s = snapshot(e)
                if s['GAME_STATE'] == 0 and s['IS_SCRIPT_PAUSED'] == 1 and s['TAMER_STATE'] == 0:
                    break
            else:
                raise AssertionError('victory did not return field control')
            sample('field-control')
            assert s['CURRENT_SCREEN'] == 150
            before = s['TAMER_POSITION_DATA+0x78']
            e.press('RIGHT', 20)
            s = sample('walk-after-victory')
            assert s['TAMER_POSITION_DATA+0x78'] != before, 'tamer cannot move after victory'
            assert s['GAME_STATE'] == 0 and s['IS_SCRIPT_PAUSED'] == 1 and s['TAMER_STATE'] == 0
            e.run('shot', str(a.out / 'walking.png'))
        result['passed'] = True
    finally:
        (a.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
