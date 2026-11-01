#!/usr/bin/env python3
"""Trace the unmodified nest scene on original 2 MB RAM with a chosen partner.

The baseline mode records the blocked command; completion mode requires recruitment,
return to field control, and a second visit to the nest. Battles are shortened by
zeroing the opponent's HP after battle entry; this is a script regression, not a combat test.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.dev.playtest.airdramon_timeout import native_card
from tools.langpatch import elf_symbols


def place(e, x, z):
    e.poke('TAMER_POSITION_DATA+0x78', struct.pack('<3i', x, 0, z))
    e.poke('TAMER_ENTITY+0x10', struct.pack('<3i', x << 15, 0, z << 15))


def snapshot(e):
    ram = e.ram()
    result = {n: e.peek(n, fmt, ram) for n, fmt in (
        ('ACTIVE_INSTRUCTION', 'B'), ('WAIT_FOR_ENTITY_ID', 'B'), ('SCRIPT_SECTION', 'H'),
        ('SCRIPT_POINTER', 'I'), ('CURRENT_SCREEN', 'h'), ('IS_SCRIPT_PAUSED', 'i'), ('GAME_STATE', 'H'))}
    result['rotation_active'] = e.peek('HAS_ROTATION_DATA', '8B', ram)
    result['rotation_targets'] = e.peek('ROTATION_DATA', '8i', ram)
    result['movement'] = [list(struct.unpack_from('<4B4h', ram, e.A('SCRIPT_MOVEMENT') - 0x80000000 + i * 12)) for i in range(2)]
    for name in ('TAMER_ENTITY', 'PARTNER_ENTITY'):
        pos = e.peek(name + '+4', 'I', ram) - 0x80000000
        result[name] = dict(type=e.peek(name, 'i', ram), rotation=list(struct.unpack_from('<3h', ram, pos + 0x70)),
                            position=list(struct.unpack_from('<3i', ram, pos + 0x78)),
                            frame=e.peek(name + '+0x1c', 'h', ram), frames=e.peek(name + '+0x1e', 'h', ram),
                            animation=e.peek(name + '+0x2e', 'B', ram))
    result['birdramon_recruited'] = bool(ram[e.A('SCRIPT_STATE') - 0x80000000 + 245 + 221 // 8] & (1 << (221 % 8)))
    return result



def observe_half_turn(e):
    """Observe the real turn arguments without changing registers or game memory."""
    rotation = e.peek('TAMER_ENTITY+4', 'I') + 0x70
    e.run('lua', f"""
if NEST and NEST.bp then NEST.bp:remove() end
NEST={{half_turn=false}}
local m=PCSX.getMemPtr()
local function u8(a) return tonumber(m[a-0x80000000]) end
local function u16(a) return u8(a)+256*u8(a+1) end
NEST.bp=PCSX.addBreakpoint({e.A('rotateEntity')},'Exec',4,'nest-turn',function()
 local r=PCSX.getRegisters()
 if tonumber(r.GPR.n.a0)~={rotation} then return end
 if u16({e.A('SCRIPT_SECTION')})~=51 or u8({e.A('TAMER_ENTITY')+0x2e})~=16 then return end
 if u16(tonumber(r.GPR.n.a2))==2048 and u16(tonumber(r.GPR.n.a3))==2048 then
  NEST.half_turn=true
 end
end)
return 'observing'
""")


def paused_shots(e, out):
    e.run('pause')
    try:
        e.run('shot', str(out / 'paused-a.png'))
        time.sleep(.2)
        e.run('shot', str(out / 'paused-b.png'))
        assert (out / 'paused-a.png').read_bytes() == (out / 'paused-b.png').read_bytes(), 'pause screenshots differ'
    finally:
        e.run('resume')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disc')
    parser.add_argument('--exe', required=True)
    parser.add_argument('--card', default='tools/dev/saves/corpus/20261027-d2796814.mcd')
    parser.add_argument('--partner', type=int, default=227)
    parser.add_argument('--port', type=int, default=40129)
    parser.add_argument('--out', type=Path, default=Path('build/nest-test'))
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--resume-before', type=Path, help='before-scene checkpoint from the same disc and partner')
    parser.add_argument('--start', type=int, nargs=2, default=(-192, -350), metavar=('X', 'Z'))
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    card = native_card(args.card, out / 'test.mcd', tamer_position=(1500, 0, -1450), partner_type=args.partner)
    e = Emu(args.disc, args.exe, args.port, str(out / 'emu'))
    for name, (address, _, _) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    result = dict(partner=args.partner, samples=[])
    def digest(path):
        digest = hashlib.sha256()
        with Path(path).open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()
    identity = dict(disc=digest(Path(args.disc).with_suffix('.bin')), exe=digest(e.exe), partner=args.partner)
    # Read RAM directly: retain the original-2-MB assertion without a subprocess per sample.
    def ram():
        data = e.api('/api/v1/cpu/ram/raw')
        assert len(data) == 0x200000, 'requires original 2 MB RAM'
        return data
    e.ram = ram
    try:
        e.start(card)
        if args.resume_before:
            assert json.loads(args.resume_before.with_suffix('.json').read_text()) == identity, 'checkpoint belongs to another build/partner'
            e.run('load', str(args.resume_before))
            e.run('resume')
        else:
            assert e.continue_game() == 0, 'Continue failed'
            e.wait(8)
            assert e.in_control(), 'no field control'
            e.gs('set', 'gametime_running=0')
            e.poke('MOD_OPT_STORY', struct.pack('<i', 0))   # the unmodified scene: the corpus card has the story on with the Motor broken
            e.gs('trigger', '221', '0')
            result['warp_returned_control'] = e.warp(129)
            e.run('save', str(out / 'before-scene.state'))
            (out / 'before-scene.json').write_text(json.dumps(identity, indent=2) + '\n')
        # Stand on an original step-0 tile, starting section 51 through the normal trigger.
        e.run('pause')
        try:
            observe_half_turn(e)
            partner_pos = e.peek('PARTNER_ENTITY+4', 'I')
            e.run('poke', hex(partner_pos + 0x78), struct.pack('<3i', -150, 0, -150).hex())
            e.poke('PARTNER_ENTITY+0x10', struct.pack('<3i', -150 << 15, 0, -150 << 15))
            place(e, *args.start)
        finally:
            e.run('resume')
        limit = 200 if args.baseline else 480
        battle_seen = False
        stable_turn = 0
        for tick in range(limit):
            row = snapshot(e)
            result['samples'].append(row)
            turn_wait = row['ACTIVE_INSTRUCTION'] == 0x4a and row['WAIT_FOR_ENTITY_ID'] in (0, 1) and row['movement'][row['WAIT_FOR_ENTITY_ID']][0] == 0
            stable_turn = stable_turn + 1 if turn_wait and tick and row['SCRIPT_POINTER'] == result['samples'][-2]['SCRIPT_POINTER'] else 0
            if args.baseline and stable_turn >= 12:
                result['stalled_turn'] = True
                break
            if tick % 10 == 0:
                print(tick, row, flush=True)
            if row['GAME_STATE'] == 1:
                battle_seen = True
                battle_ram = e.ram()
                for i in range(2, 10):
                    entity = e.peek(f'ENTITY_TABLE+{i * 4}', 'I', battle_ram)
                    if 0x80000000 <= entity < 0x801ffff0:
                        e.run('poke', hex(entity + 76), '0000')
            if row['birdramon_recruited'] and row['IS_SCRIPT_PAUSED'] == 1 and row['CURRENT_SCREEN'] != 129:
                break
            e.press('CONFIRM', 6)
            e.wait(.5)
        paused_shots(e, out)
        e.run('save', str(out / 'last.state'))
        result['battle_seen'] = battle_seen
        result['final'] = snapshot(e)
        result['half_turn_observed'] = e.run('lua', 'return NEST.half_turn').strip() == 'true'
        if args.partner == 227 and tuple(args.start) == (-192, -350):
            assert result['half_turn_observed'], 'the reproducing approach did not reach an exact half-turn'
        if args.baseline:
            assert result.get('stalled_turn'), 'baseline did not reproduce a stalled turn'
            assert result['final']['WAIT_FOR_ENTITY_ID'] == 0, 'expected the tamer turn wait'
            assert result['final']['TAMER_ENTITY']['animation'] == 16, 'expected the thinking animation'
            assert result['final']['PARTNER_ENTITY']['type'] == args.partner
        else:
            assert battle_seen, 'the nest fight never started'
            assert result['final']['birdramon_recruited'], 'Birdramon was not recruited'
            assert e.in_control(), 'no control after recruitment'
            assert e.warp(129), 'no control on return to the nest'
            e.wait(3)
            assert e.in_control(), 'the recruited nest scene restarted'
            result['revisit'] = snapshot(e)
            e.run('shot', str(out / 'revisited.png'))
        print('result', result['final'], flush=True)
    except BaseException as error:
        result['error'] = str(error)
        e.run('shot', str(out / 'failure.png'), check=False)
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
