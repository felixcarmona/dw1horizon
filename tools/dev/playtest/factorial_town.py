#!/usr/bin/env python3
"""Trace Factorial Town's real scene handlers on an original 2 MB disc.

Seed only the starting story state and partner on a private corpus card. Dispatch
NPC sections at a frame boundary; this tests their logic, not walking/contact.
Shorten battles by clearing enemy HP after loading. Never inject outcome flags.
--expect-bug checks the healthy Numemon's missing handoff on an unfixed disc.
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
from tools.dev.saves.releases import Emu
from tools.dev.playtest.airdramon_timeout import native_card
from tools.dev.playtest.birdramon_recruitment import call_section, free_heap
from tools.dev.playtest.story_convergence import Run
from tools.langpatch import elf_symbols


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--partner', type=int, default=475)
    p.add_argument('--root', type=int, choices=(0, 1), default=1)
    p.add_argument('--quick', type=int, choices=(0, 1), default=1)
    p.add_argument('--expect-bug', action='store_true')
    p.add_argument('--full', action='store_true')
    p.add_argument('--port', type=int, default=42371)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    card = native_card(ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd', a.out / 'test.mcd',
                       partner_type=a.partner, tamer_position=(1500, 0, -1450))
    e = Emu(a.disc, a.exe, a.port, str(a.out / 'emu'))
    for name, (addr, _, _) in elf_symbols(e.exe + '.elf').items(): e.table.setdefault(name, addr)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    e.ram = lambda: e.api('/api/v1/cpu/ram/raw')
    r = Run(e, a.out); result = dict(partner=a.partner, root=a.root, quick=a.quick, expect_bug=a.expect_bug, samples=[])
    result['disc'] = Path(a.disc).name
    result['exe_sha256'] = hashlib.sha256(Path(e.exe).read_bytes()).hexdigest()
    flags = ('sewer_fog_seen', 'sewer_numemon_met', 'factory_permit_required', 'factory_check_refused',
             'guard_shift_change_heard', 'factory_guards_passed', 'factory_giromon_beaten', 'factory_shut_down',
             'factorial_town_reopened', 'island_history_read', 'factory_asked', 'factory_kept_shut')
    def sample(label):
        ram = e.ram(); assert len(ram) == 0x200000
        row = dict(label=label, ram_bytes=len(ram), screen=e.peek('CURRENT_SCREEN', 'h', ram), partner=e.peek('PARTNER_ENTITY', 'i', ram),
                   flags={k: r.flag(k) for k in flags}, heap=free_heap(e, ram))
        result['samples'].append(row); print(json.dumps(row), flush=True)
    def settle(screen=None, deadline=100):
        end = time.monotonic() + deadline
        battle_since = None
        while time.monotonic() < end:
            ram = e.ram()
            if (screen is None or e.peek('CURRENT_SCREEN', 'h', ram) == screen) and e.peek('TAMER_STATE', 'b', ram) == 0 and e.peek('IS_SCRIPT_PAUSED', 'i', ram) == 1:
                e.wait(.5)
                if e.peek('IS_SCRIPT_PAUSED', 'i') == 1: return
            if e.peek('GAME_STATE', 'H', ram) == 1:
                result['battle_seen'] = True
                if battle_since is None: battle_since = time.monotonic()
                if time.monotonic() - battle_since > 10:
                    for i in range(8): e.poke(f'NPC_ENTITIES+{i * 104 + 76}', b'\0\0')
            e.press('CONFIRM', 6); e.wait(.4)
        raise AssertionError(f'not free on screen {screen}')
    r.settle = settle
    def talk(slot, label):
        e.poke('TALKED_TO_ENTITY', bytes([5 + slot]))
        call_section(e, e.peek('CURRENT_SCRIPT_ID', 'H'), 5 + slot)
        e.wait(1); r.shot(label); r.settle(deadline=100); sample(label)
    try:
        e.start(card); assert e.continue_game() == 0
        e.gs('set', 'hour=10', 'minute=0', 'gametime_running=0', 'partner.para.condition=0',
             'partner.para.foodLevel=100', 'partner.para.energyLevel=100', 'partner.para.poopLevel=0',
             'partner.para.tiredness=0', 'partner.para.nextHungerHour=23', 'partner.para.sleepyHour=23')
        e.poke('MOD_OPT_QUICK_BATTLE', struct.pack('<i', a.quick))
        r.set(**{k: False for k in flags}); r.set(root2=bool(a.root))
        r.recruit(Numemon=False, Andromon=False, Giromon=False, Whamon=True)
        e.gs('trigger', '329', '0')
        r.go(220); sample('sewer-arrival')
        talk(0, 'numemon-talk')
        assert r.flag('sewer_fog_seen')
        assert r.flag('sewer_numemon_met') == (not a.expect_bug)
        r.go(155); talk(6, 'guard-permit')
        assert r.flag('factory_permit_required') == (not a.expect_bug)
        r.go(157); talk(0, 'andromon-permission')
        assert r.flag('factory_check_refused') == (not a.expect_bug)
        if not a.expect_bug:
            # First option asks about shifts; second asks when they change.
            e.run('lua', f'''FT_CHOICE=PCSX.addBreakpoint({e.A('tickSelectionDialogue')},'Exec',4,'factory-choice',function()
local m=PCSX.getMemPtr();local n=tonumber(m[{e.A('DIALOGUE_SELECTION') + 8}-0x80000000]);m[{e.A('DIALOGUE_SELECTION') + 10}-0x80000000]=n==3 and 0 or 1
end)''')
            r.go(155); talk(6, 'guard-schedule')
            e.run('lua', 'FT_CHOICE:remove()')
            assert r.flag('guard_shift_change_heard')
        # Even an old affected save can bypass the guards by re-entering at noon.
        r.go(154); e.gs('set', 'hour=12', 'minute=0'); r.go(155, entry=1)
        assert r.npc(6) is None and r.npc(7) is None
        sample('noon-guards-absent'); r.shot('noon-guards-absent')
        # Cross the actual guard positions and map exit using the pad.
        for _ in range(60):
            if e.peek('CURRENT_SCREEN', 'h') == 161: break
            e.press('RIGHT', 20); e.wait(.1)
        else: raise AssertionError('could not walk through the unguarded gate')
        r.settle(161); assert r.flag('factory_guards_passed')
        sample('walked-through-gate'); r.shot('walked-through-gate')
        if a.full:
            r.go(161); assert r.flag('factory_guards_passed')
            result['battle_seen'] = False
            r.go(160)
            if not r.flag('factory_giromon_beaten'): call_section(e, e.peek('CURRENT_SCRIPT_ID', 'H'), 51)
            end = time.monotonic() + 180; battle = result.get('battle_seen', False)
            while not r.flag('factory_giromon_beaten') and time.monotonic() < end:
                if e.peek('GAME_STATE', 'H') == 1:
                    if not battle:
                        e.wait(10); r.shot('giromon-battle'); battle = True
                    for i in range(8): e.poke(f'NPC_ENTITIES+{i * 104 + 76}', b'\0\0')
                e.press('CONFIRM', 6); e.wait(.4)
            assert r.flag('factory_giromon_beaten'), 'Giromon never completed'
            r.settle(); result['battle_seen'] = battle; assert battle == (not a.root)
            sample('giromon-complete')
            r.go(157); talk(0, 'andromon-shutdown'); assert r.flag('factory_shut_down')
            # Numemon's arrival scene starts automatically once the factory stops.
            r.go(220, deadline=180)
            assert r.recruited('Numemon'); sample('numemon-recruited'); r.shot('numemon-recruited')
            r.go(157); talk(0, 'town-reopened'); assert r.flag('factorial_town_reopened')
        result['passed'] = True
    finally:
        (a.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        e.stop()


if __name__ == '__main__': main()
