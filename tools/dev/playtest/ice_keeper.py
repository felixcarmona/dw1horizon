#!/usr/bin/env python3
"""Walk the Wall of Hearts choice and keeper dialogue on an original-2-MB disc.

Fixture writes select a native Agumon card, language, care, recruited Angemon
and unplayed quest/hint flags. A normal warp enters screen 310; all subsequent
walking, dialogue, the choice, thaw and hints use the pad. No NPC, camera,
script pointer or heap writes are used. --expect-crash checks the old missing
speaker fault. Screenshots, checkpoints and JSON stay in the output folder.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.load_camera import card_fixture
from tools.dev.playtest.qol import ProofEmu
from tools.langpatch import elf_symbols


def sample(e):
    ram = e.ram()
    flow = json.loads(e.api('/api/v1/execution-flow'))
    assert not flow['8mb'] and len(ram) == 0x200000, flow
    return dict(screen=e.peek('CURRENT_SCREEN', 'h', ram),
                paused=e.peek('IS_SCRIPT_PAUSED', 'i', ram),
                state=e.peek('TAMER_STATE', 'B', ram),
                position=e.peek('TAMER_POSITION_DATA+0x78', '3i', ram),
                running=flow['running'],
                pc=e.run('lua', 'return string.format("%08x",PCSX.getRegisters().pc)').strip())


def free(row):
    return row['paused'] == 1 and row['state'] == 0 and row['running']


def flag(e, n):
    return (e.peek(f'SCRIPT_STATE+{245+n//8}', 'B') >> (n % 8)) & 1


def checkpoint(e, out, name):
    e.run('shot', str(out / (name + '.png')))
    e.run('save', str(out / (name + '.state')))


def walk_and_talk(e, out, name):
    # These two maps share the straight aisle from entry 0 to (0, 800).
    for _ in range(35):
        if e.peek('TAMER_POSITION_DATA+0x78', '3i')[2] >= 450:
            break
        e.press('UP', 24)
    else:
        raise AssertionError('walk did not reach Angemon')
    checkpoint(e, out, name + '-approach')
    e.api('/api/v1/lua/press?button=UP')
    try:
        for _ in range(8):
            e.press('CONFIRM', 8)
            if e.peek('IS_SCRIPT_PAUSED', 'i') == 0:
                break
        else:
            raise AssertionError('pad interaction did not start the talk')
    finally:
        e.api('/api/v1/lua/release?button=UP')
    checkpoint(e, out, name + '-talk')


def read_to_field(e, screen, rows, decline=False):
    selected = False
    for _ in range(120):
        row = sample(e)
        rows.append(row)
        if row['screen'] == screen and free(row):
            assert not decline or selected, 'the decline choice was not exercised'
            return
        if decline and not selected and e.peek('ACTIVE_INSTRUCTION', 'B') == 0x10:
            for _ in range(12):
                e.press('DOWN', 8)
                if e.peek('DIALOGUE_SELECTION+10', 'H') == 1:
                    selected = True
                    break
            assert selected, 'could not select Come to the city'
        e.press('CONFIRM', 8)
        e.wait(.1)
    raise AssertionError('dialogue did not return field control')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc', type=Path)
    p.add_argument('--exe', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=39612)
    p.add_argument('--language', type=int, choices=(0, 2), default=2)
    p.add_argument('--expect-crash', action='store_true')
    p.add_argument('--check-decline', action='store_true')
    args = p.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(str(args.disc.resolve()), str(args.exe.resolve()), args.port, str(out/'emu'))
    for name, (address, _, _) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    result = dict(language=args.language, expect_crash=args.expect_crash, rows=[],
                  disc_sha1=hashlib.sha1(args.disc.with_suffix('.bin').read_bytes()).hexdigest())
    try:
        e.start(str(card_fixture(out, 168, [0, 0, 0], 3, False, 1, args.language)))
        assert e.continue_game() == 0
        assert e.peek('MOD_LANG', 'i') == args.language
        e.gs('set', 'gametime_running=0', 'partner.para.remainingLifetime=1000',
             'partner.para.condition=0', 'partner.para.poopLevel=0', 'partner.para.foodLevel=100')
        e.gs('trigger', '220', '1')
        for n in (730, 731, 734, 81):
            e.gs('trigger', str(n), '0')
        for n in (1, 40, 41):
            e.gs('pstat', str(n), '0')
        assert e.warp(310)
        e.wait(4)
        checkpoint(e, out, 'arrival')
        print('walking to the wall', flush=True)
        if args.check_decline:
            walk_and_talk(e, out, 'decline')
            read_to_field(e, 310, result['rows'], decline=True)
            assert flag(e, 220) and not flag(e, 730) and flag(e, 731)
            result['decline'] = sample(e)
            assert e.warp(97) and e.warp(310)
            # The ordinary pedestal handler clears the declined-visit marker;
            # this fixture warp skips its tile, so clear just that marker.
            e.gs('trigger', '731', '0')
            assert e.warp(97) and e.warp(310)
            e.wait(4)
        walk_and_talk(e, out, 'wall')
        read_to_field(e, 311, result['rows'])
        assert flag(e, 730) and flag(e, 734) and not flag(e, 220)
        checkpoint(e, out, 'thawed')
        print('thaw complete; walking to the keeper', flush=True)
        e.run('lua', f'''
          ICE_KEEPER={{names={{}}}}
          ICE_KEEPER.bp=PCSX.addBreakpoint({e.A('getSpeakerName')},'Exec',4,'ice-keeper',function()
            local r=PCSX.getRegisters()
            ICE_KEEPER.names[#ICE_KEEPER.names+1]=r.GPR.n.a0
          end)
        ''')
        walk_and_talk(e, out, 'keeper')
        try:
            read_to_field(e, 311, result['rows'])
        except AssertionError:
            result['fault'] = sample(e)
            if not args.expect_crash or result['fault']['running'] or result['fault']['pc'] != '80000080':
                raise
        result['speakers'] = e.run('lua', 'return table.concat(ICE_KEEPER.names,",")').strip()
        if args.expect_crash:
            assert 'fault' in result, 'old crash was not observed'
        else:
            # Name expansion also calls getSpeakerName for {player} (253).
            npc_speakers = {int(n) for n in result['speakers'].split(',') if int(n) < 200}
            assert npc_speakers == {6}, result['speakers']
            checkpoint(e, out, 'intro-finished')
            # The actor remains beside the player after the first talk.
            walk_and_talk(e, out, 'repeat')
            read_to_field(e, 311, result['rows'])
            assert e.peek('SCRIPT_STATE+385', 'B') == 0  # p40: hint counter reset at the end
            before = e.peek('TAMER_POSITION_DATA+0x78', '3i')
            e.press('DOWN', 24)
            result['walk_after'] = sample(e)
            assert free(result['walk_after']) and result['walk_after']['position'] != before
        checkpoint(e, out, 'finished')
        result['ok'] = True
        print('PASS', result['speakers'], flush=True)
    finally:
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        e.stop()


if __name__ == '__main__':
    main()
