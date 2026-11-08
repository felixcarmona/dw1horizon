#!/usr/bin/env python3
"""Capture before/after Status cameras with real partner models on original 2 MB.

Use the fixed disc and an audit.json from the repair pass. A fixture evolution
installs each model; only camera coordinates are temporarily restored for the
before image. The after image uses the camera read from the built disc. No
model, animation, UI or engine routine is replaced.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.frigimon_recruitment import fixture_partner
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.suijinmon import settle_notices
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols


def await_status(e):
    for _ in range(100):
        ram = e.ram()
        if (e.peek('UI_BOX_DATA+54', 'h', ram) == 1 and
                e.peek('MENU_STATE', 'b', ram) == 1 and
                e.peek('DIGIMON_MENU_STATE', 'b', ram) == 0):
            return
        e.wait(.2)
    raise AssertionError('Status page did not become interactive')


def camera_address(e, sid):
    if sid < 180:
        return e.A('RAISE_DATA') + sid * 28 + 22
    return call(e, 'getSpeciesRaise', sid) + 22


def capture(e, address, position, path):
    e.run('pause')
    e.run('poke', hex(address), struct.pack('<3h', *position).hex())
    e.run('resume')
    e.wait(.5)
    e.run('shot', str(path))
    ram = e.ram()
    assert list(struct.unpack_from('<3h', ram, address & 0x1fffff)) == position


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disc')
    parser.add_argument('--exe', required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--port', type=int, default=42637)
    parser.add_argument('--species', type=int, nargs='+')
    parser.add_argument('--field-state', type=Path, help='field checkpoint made by this harness on the same disc')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = {r['id']: r for r in json.loads(args.audit.read_text())}
    selected = args.species or sorted({r['id'] for r in rows.values() if r['fixed']} | {198, 216, 257})
    e = ProofEmu(args.disc, args.exe, args.port, str(out))
    for name, (address, _, _) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    results = []
    try:
        card = field_card(str(ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd'), str(out / 'fixture.mcd'))
        e.start(card)
        if args.field_state:
            e.run('load', str(args.field_state.resolve()))
            e.run('resume')
            assert e.in_control()
        else:
            e.run('lua', f"PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'skip-intro',function() PCSX.getRegisters().GPR.n.a1=0 end)")
            assert e.continue_game() == 0
        flow = json.loads(e.api('/api/v1/execution-flow'))
        assert not flow['8mb'] and len(e.ram()) == 0x200000
        e.gs('set', 'gametime_running=0', 'partner.para.evoTimer=0', 'partner.para.remainingLifetime=1000')
        settle_notices(e)
        checkpoint = out / 'field.state'
        e.run('save', str(checkpoint))
        for sid in selected:
            row = rows[sid]
            e.run('load', str(checkpoint))
            fixture_partner(e, sid)
            e.gs('set', 'partner.para.condition=0', 'partner.para.evoTimer=0',
                 'partner.para.remainingLifetime=1000')
            e.run('resume')
            settle_notices(e)
            assert e.peek('PARTNER_ENTITY', 'i') == sid
            for _ in range(6):
                if e.peek('IS_IN_MENU', 'i'):
                    break
                e.press('TRIANGLE', 12)
                e.wait(.3)
            assert e.peek('IS_IN_MENU', 'i')
            call(e, 'handleGameMenuSelection', 2)
            e.run('resume')
            await_status(e)
            address = camera_address(e, sid)
            built = list(struct.unpack_from('<3h', e.ram(), address & 0x1fffff))
            assert built == row['after'], (sid, built, row['after'])
            capture(e, address, row['before'], out / f'{sid}-before.png')
            capture(e, address, built, out / f'{sid}-after.png')
            e.gs('set', 'partner.para.condition=1')
            e.run('resume')
            e.wait(.5)
            e.run('shot', str(out / f'{sid}-sleep.png'))
            results.append(dict(id=sid, name=row['name'], before=row['before'], after=built,
                                original_2mb=True, built_camera_matches=True))
            (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
            print(f'{sid} {row["name"]}: captured on 2 MB', flush=True)
    finally:
        e.stop()


if __name__ == '__main__':
    main()
