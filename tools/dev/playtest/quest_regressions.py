#!/usr/bin/env python3
"""Exercise the Ancient Region quest on original 2 MB hardware emulation.

Uses a disposable card, fixture evolutions, strong partner stats and map warps.
The battles, dialogue, NPC movement and recruitment run through the game. The
lookup monitor observes getEntityFromScriptId itself: a turn may safely finish
from a cached position after its target leaves.

DISPLAY=:120 python3 tools/dev/playtest/quest_regressions.py DISC.cue --exe EXE \
    --species 314 --language 2 --port 39930 --out build/quest-proof

Language 0 is English; 2 is Brazilian Portuguese. --strike chooses the second
Meteormon opening. --scene-only skips the earlier quest scenes.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu, test_card
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols
from tools.membudget import Ram, heap_walk


FLAGS = {'guard_beaten': 144, 'gate_open': 187, 'speedy_region': 188,
         'saberdramon_fought': 97, 'meteormon_checked': 313, 'tyrannomon_recruited': 208}


def flag(e, number, ram):
    return bool(ram[e.A('SCRIPT_STATE+245') - 0x80000000 + number // 8] & (1 << (number % 8)))


def capture(e, out, label):
    ram = e.ram()
    assert len(ram) == 0x200000
    flow = json.loads(e.api('/api/v1/execution-flow'))
    assert not flow['8mb'] and flow['running'], flow
    heap = heap_walk(Ram(ram, e.table))
    assert heap['corrupt'] is None, heap
    row = {'ram_bytes': len(ram), 'flow': flow,
           'screen': e.peek('CURRENT_SCREEN', 'h', ram),
           'partner': e.peek('PARTNER_ENTITY', 'i', ram),
           'flags': {name: flag(e, n, ram) for name, n in FLAGS.items()},
           'heap': {k: v for k, v in heap.items() if k != 'blocks'}}
    (out / f'{label}.json').write_text(json.dumps(row, indent=2) + '\n')
    e.run('shot', str(out / f'{label}.png'))
    return row


def evolve_fixture(e, species):
    if e.peek('PARTNER_ENTITY', 'i') == species:
        return
    e.run('pause')
    for name, fmt, value in [('EVOLUTION_TARGET', 'h', species), ('HAS_USED_EVOITEM', 'B', 1),
                             ('TAMER_STATE', 'B', 6), ('TAMER_SUB_STATE', 'B', 0),
                             ('PARTNER_STATE', 'B', 13), ('PARTNER_SUB_STATE', 'B', 0)]:
        e.poke(name, struct.pack('<' + fmt, value))
    e.run('resume')
    for _ in range(240):
        ram = e.ram()
        state = e.peek('TAMER_STATE', 'B', ram)
        if e.peek('PARTNER_ENTITY', 'i', ram) == species and state == 0:
            assert e.in_control()
            return
        if state == 6:
            e.press('START', 8)
        elif state == 20:
            e.press('CONFIRM', 8)
        e.wait(.25)
    raise AssertionError(f'fixture evolution to {species} did not finish')


def approach(e, slot):
    e.gs('approach', str(slot), '250')
    ram = e.ram()
    x, y, z = e.peek('TAMER_POSITION_DATA+0x78', '3i', ram)
    pd = e.peek(f'NPC_ENTITIES+{104 * slot + 4}', 'I', ram) - 0x80000000
    nx, _, nz = struct.unpack_from('<3i', ram, pd + 0x78)
    distance = ((x - nx) ** 2 + (z - nz) ** 2) ** .5 or 1
    call(e, 'setEntityPosition', 1, round(x + (x - nx) * 300 / distance), y,
         round(z + (z - nz) * 300 / distance))
    e.run('resume')
    call(e, 'setupEntityMatrix', 1)
    e.run('resume')
    for _ in range(100):
        done = call(e, 'tickCameraMoveToEntity', 0xfd, 15)
        e.run('resume')
        if done:
            e.wait(.5)
            return
        e.wait(.05)
    raise AssertionError('camera did not reach the fixture position')


def section(e, script, number, slot=0):
    # Entering the event tile or touching an auto-talk NPC may start it first.
    if e.peek('IS_SCRIPT_PAUSED', 'i') == 0:
        assert e.peek('CURRENT_SCRIPT_ID', 'H') == script
        return
    e.poke('TALKED_TO_ENTITY', bytes([slot + 2]))
    call(e, 'callScriptSection', script, number, 1)
    e.run('resume')


def arrive(e, screen, script):
    idle = e.warp(screen)
    # A map entry may immediately start its scene and take control. That is
    # an arrival too; the generic warp helper waits specifically for idle.
    if not idle:
        ram = e.ram()
        assert e.peek('CURRENT_SCREEN', 'h', ram) == screen
        assert e.peek('CURRENT_SCRIPT_ID', 'H', ram) == script
        assert e.peek('TAMER_STATE', 'B', ram) != 5, 'map is still loading'
    e.wait(2)


def pose(e, tamer, partner):
    for entity, (x, z) in enumerate((tamer, partner)):
        call(e, 'setEntityPosition', entity, x, 0, z)
        e.run('resume')
        call(e, 'setupEntityMatrix', entity)
        e.run('resume')
    for _ in range(100):
        done = call(e, 'tickCameraMoveToEntity', 0xfd, 15)
        e.run('resume')
        if done:
            return
        e.wait(.05)
    raise AssertionError('quest camera did not reach the event position')


def advance(e, ram, auto_selected):
    if e.peek('GAME_STATE', 'H', ram) != 1:
        e.press('CONFIRM', 8)
        return auto_selected
    if not auto_selected:
        e.press('CONFIRM', 8)
        return True
    # The finisher button only issues an order when its meter is full. Let
    # Auto handle ordinary attacks, and confirm results after the enemies die.
    e.press('CIRCLE', 8)
    for i in range(2, 10):
        ptr = e.peek(f'ENTITY_TABLE+{4 * i}', 'I', ram)
        if 0x80000000 < ptr < 0x80200000:
            if struct.unpack_from('<h', ram, ptr - 0x80000000 + 0x4c)[0] > 0:
                return auto_selected
    e.press('CONFIRM', 8)
    return auto_selected


def finish(e, out, label, number, *, battle=False, strike=False):
    deadline = time.monotonic() + 1800
    fought = auto_selected = chosen = False
    while time.monotonic() < deadline:
        ram = e.ram()
        fought |= e.peek('GAME_STATE', 'H', ram) == 1
        ready = (flag(e, number, ram) and e.peek('TAMER_STATE', 'B', ram) == 0
                 and e.peek('GAME_STATE', 'H', ram) == 0 and (fought or not battle))
        moved = False
        if ready and e.peek('IS_SCRIPT_PAUSED', 'i', ram) != 1:
            # A step trigger can run an immediate return every frame while the
            # player has control. Prove movement instead of waiting on its flag.
            before = e.peek('TAMER_POSITION_DATA+0x78', '3i', ram)
            e.press('RIGHT', 12)
            e.wait(.25)
            after = e.ram()
            moved = (e.peek('TAMER_STATE', 'B', after) == 0
                     and e.peek('CURRENT_SCREEN', 'h', after) == e.peek('CURRENT_SCREEN', 'h', ram)
                     and e.peek('TAMER_POSITION_DATA+0x78', '3i', after) != before)
        if ready and (e.peek('IS_SCRIPT_PAUSED', 'i', ram) == 1 or moved):
            row = capture(e, out, label)
            row['battle_observed'] = fought
            row['field_movement_verified'] = moved
            (out / f'{label}.json').write_text(json.dumps(row, indent=2) + '\n')
            print(f'PASS {label}: battle={fought}', flush=True)
            return row
        if strike and not chosen and e.peek('ACTIVE_INSTRUCTION', 'B', ram) == 0x10:
            e.press('DOWN', 16)
            chosen = True
        auto_selected = advance(e, ram, auto_selected)
        e.wait(.4)
    raise AssertionError(f'{label} did not return field control')


def monitor(e):
    e.run('lua', f'''
      QUEST_CHECK={{bad=0,lookups={{}},unloads={{}}}}
      local m=PCSX.getMemPtr()
      QUEST_CHECK.lookup=PCSX.addBreakpoint({e.A('getEntityFromScriptId')},'Exec',4,'quest-lookup',function()
        local r=PCSX.getRegisters()
        local id=m[tonumber(r.GPR.n.a0)%0x200000]
        if id<5 or id>12 then return end
        for i=0,7 do
          local p={e.A('ENTITY_TABLE') & 0x1fffff}+4*(i+2)
          if (m[p]~=0 or m[p+1]~=0 or m[p+2]~=0 or m[p+3]~=0)
             and m[{e.A('NPC_ENTITIES') & 0x1fffff}+104*i+101]==id then return end
        end
        QUEST_CHECK.bad=QUEST_CHECK.bad+1
        QUEST_CHECK.lookups[#QUEST_CHECK.lookups+1]=string.format('id=%d ra=%08x',id,tonumber(r.GPR.n.ra))
      end)
      QUEST_CHECK.unload=PCSX.addBreakpoint({e.A('scriptUnloadEntity')},'Exec',4,'quest-unload',function()
        local r=PCSX.getRegisters()
        QUEST_CHECK.unloads[#QUEST_CHECK.unloads+1]=tonumber(r.GPR.n.a0)
      end)
    ''')


def quest(e, out, args):
    evolve_fixture(e, args.species)
    e.gs('set', 'gametime_running=0', 'partner.para.age=1', 'partner.para.evoTimer=0',
         'partner.para.condition=0', 'partner.para.remainingLifetime=1000',
         *[f'partner.stats.{s}={9000 if s in ("hp", "mp", "currentHP", "currentMP") else 900}'
           for s in ('hp', 'mp', 'currentHP', 'currentMP', 'off', 'def', 'speed', 'brain')])
    for n in (144, 187, 188, 313, 208):
        e.gs('trigger', str(n), '0')
    e.gs('pstat', '101', '0')
    rows = {}
    if not args.scene_only:
        arrive(e, 79, 76)
        # These are the scene's own post-battle positions. Starting at the
        # distant map arrival can leave the battle outside the camera/path.
        if e.peek('IS_SCRIPT_PAUSED', 'i') == 1:
            pose(e, (-97, -448), (-597, -443))
        section(e, 76, 51)
        rows['guard'] = finish(e, out, 'guard', 144, battle=True)
        arrive(e, 82, 79)
        if e.peek('IS_SCRIPT_PAUSED', 'i') == 1:
            pose(e, (-326, 1203), (-626, 1203))
        section(e, 79, 51)
        rows['gate'] = finish(e, out, 'gate', 187)
        arrive(e, 83, 80)
        section(e, 80, 51)
        rows['speedy'] = finish(e, out, 'speedy', 188)
        arrive(e, 85, 81)
        approach(e, 0)
        section(e, 81, 5)
        rows['saberdramon'] = finish(e, out, 'saberdramon', 97, battle=True)
    arrive(e, 86, 82)
    approach(e, 0)
    capture(e, out, 'before-meteormon')
    e.run('save', str(out / 'before-meteormon.state'))
    monitor(e)
    section(e, 82, 5)
    rows['meteormon'] = finish(e, out, 'meteormon', 313, battle=True, strike=args.strike)
    if not args.scene_only:
        arrive(e, 82, 79)
        approach(e, 1)
        section(e, 79, 6, 1)
        rows['recruitment'] = finish(e, out, 'recruitment', 208)
        arrive(e, 86, 82)
        assert e.peek('ENTITY_TABLE+8', 'I') == 0, 'Meteormon reappeared'
        rows['revisit'] = capture(e, out, 'revisit')
    bad = int(e.run('lua', 'return QUEST_CHECK.bad').strip())
    assert bad == 0, e.run('lua', "return table.concat(QUEST_CHECK.lookups,'; ')")
    return {'passed': True, 'species': args.species, 'language': args.language,
            'full_chain': not args.scene_only, 'invalid_lookups': bad, 'milestones': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disc', type=Path)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--species', type=int, default=314)
    parser.add_argument('--language', type=int, choices=(0, 2), default=0)
    parser.add_argument('--port', type=int, default=39930)
    parser.add_argument('--out', type=Path, default=Path('build/quest-regressions'))
    parser.add_argument('--strike', action='store_true')
    parser.add_argument('--scene-only', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    exe = str(args.exe.resolve())
    e = ProofEmu(str(args.disc.resolve()), exe, args.port, str(out / 'emu'))
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for name, (addr, _, _) in elf_symbols(exe + '.elf').items():
        e.table.setdefault(name, addr)
    result = {}
    try:
        e.start(test_card(out, args.language))
        assert e.continue_game() == 0
        e.wait(5)
        assert e.in_control() and len(e.ram()) == 0x200000
        assert e.peek('MOD_LANG', 'i') == args.language
        result = quest(e, out, args)
    except BaseException as error:
        result['error'] = str(error)
        try:
            capture(e, out, 'failure')
            e.run('save', str(out / 'failure.state'))
        except Exception:
            pass
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
