#!/usr/bin/env python3
"""Replay the reported rubble use, town corner and post-fight Saberdramon scene."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu, test_card
from tools.dev.playtest.training_evolution import call
from tools.dev.playtest.frigimon_recruitment import fixture_partner as fixture
from tools.dev.playtest.birdramon_recruitment import install, free_heap
from tools.langpatch import elf_symbols
from tools import dwmap


def section(e, number, entity=2, event=1):
    e.poke('TALKED_TO_ENTITY', bytes([entity]))
    call(e, 'callScriptSection', e.peek('CURRENT_SCRIPT_ID', 'H'), number, event)
    e.run('resume')


def place(e, x, z):
    # Position and animation coordinates must change in the same stopped frame.
    e.run('pause'); e.gs('move', str(x), str(z)); e.run('resume')


def focus(e):
    call(e, 'tickCameraMoveToEntity', 0xfd, 10)
    e.run('resume')
    for _ in range(80):
        done=call(e, 'tickCameraMoveToEntity', 0xfd, 10)
        e.run('resume')
        if done==1: break
        e.wait(.1)
    else: raise AssertionError('camera did not reach the fixture')
    e.wait(.5)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--port', type=int, default=39716)
    a = p.parse_args(); out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(a.disc, a.exe, a.port, str(out/'emu'))
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for name, (address, _, _) in elf_symbols(a.exe+'.elf').items(): e.table.setdefault(name, address)
    result = {}
    try:
        e.start(test_card(out, 2)); assert e.continue_game() == 0
        result['ram_bytes'] = len(e.ram()); assert result['ram_bytes'] == 2097152
        assert e.peek('MOD_LANG', 'i') == 2
        fixture(e, 224)
        e.gs('set', 'hour=12', 'gametime_running=0', 'partner.para.condition=0',
             'partner.stats.hp=9999', 'partner.stats.currentHP=9999', 'partner.stats.mp=9999',
             'partner.stats.currentMP=9999', 'partner.stats.off=9999', 'partner.stats.def=9999')
        assert e.warp(85)
        result['saber_heap'] = free_heap(e, e.ram())
        e.gs('approach', '0', '550'); focus(e)
        e.run('shot', str(out/'saber-before-fight.png')); e.run('vram', str(out/'saber-before.vram'))
        install(e, 'won'); section(e, 5)
        deadline = time.monotonic()+300
        while time.monotonic() < deadline:
            if e.run('lua', 'return BR.ended').strip() == 'true': break
            if e.peek('GAME_STATE', 'H') != 1: e.press('CONFIRM', 8)
            e.wait(.35)
        else: raise AssertionError('Saberdramon fight did not finish')
        assert e.in_control(100)
        result['saber_battle_events'] = e.run('lua', "return table.concat(BR.events,'\\n')").strip().splitlines()
        result['saber_heap_after'] = free_heap(e, e.ram())
        e.gs('approach', '0', '550'); focus(e); section(e, 5); e.wait(2)
        e.run('shot', str(out/'saber-post-fight-dialogue.png'))
        e.run('vram', str(out/'saber-post-fight.vram'))
        e.run('record', str(out/'saber-post-fight.mp4'), '8')
        assert e.in_control()
        for n in (147, 148): e.gs('trigger', str(n), '1')
        assert e.warp(119)
        native = dwmap.MapFile((ROOT/'extracted/MAP/MAP8/MIST05.MAP').read_bytes())
        actual = e.raw('MAP_COLLISION_DATA', 10000, e.ram())
        result['town_collision_matches_original'] = actual == bytes(native.collision)
        assert result['town_collision_matches_original']
        result['town_npc_type'] = e.peek('NPC_ENTITIES', 'i')
        place(e, -2600, 1350); focus(e)
        result['town_walk'] = [e.peek('TAMER_POSITION_DATA+0x78', '3i')]
        e.run('shot', str(out/'town-corner-before.png'))
        with ThreadPoolExecutor() as pool:
            video = pool.submit(e.run, 'record', str(out/'town-corner.mp4'), '8')
            for direction in ('UP', 'UP', 'UP', 'LEFT', 'LEFT'):
                e.press(direction, 12); e.wait(.2)
                result['town_walk'].append(e.peek('TAMER_POSITION_DATA+0x78', '3i'))
            video.result()
        assert len({tuple(v) for v in result['town_walk']}) > 3
        # Continue up the reported passage with the same gold partner.
        for _ in range(16):
            if e.peek('CURRENT_SCREEN', 'h') != 119: break
            e.press('UP', 12); e.wait(.25)
        result['town_end_screen'] = e.peek('CURRENT_SCREEN', 'h')
        assert result['town_end_screen'] == 144
        assert e.in_control()
        e.run('shot', str(out/'town-corner-after.png'))
        fixture(e, 3)
        e.gs('pstat', '30', '0')
        e.gs('pstat', '18', '6'); e.gs('pstat', '17', '2')
        assert e.warp(28)
        assert e.in_control(); e.wait(1)
        # Enter before the fourth delivery, then retain that visit's obstacle
        # with four delivered carts and the fifth pickup still to perform.
        e.gs('pstat', '18', '8')
        e.poke('DIRT_PILE_SIZE_COUNTER', b'\7')
        place(e, 1750, 850); focus(e)
        assert e.peek('TAMER_POSITION_DATA+0x78','3i')==[1750,0,850]
        cells = [y*100+x for y in range(41,43) for x in range(69,72)]
        before = e.raw('MAP_COLLISION_DATA', 10000, e.ram())
        assert all(before[i] == 128 for i in cells)
        e.run('shot', str(out/'rubble-before.png')); section(e, 81, event=0)
        for _ in range(60):
            if e.peek('DIRT_PILE_SIZE_COUNTER', 'b') == 5: break
            e.press('CONFIRM', 8); e.wait(.25)
        assert e.peek('DIRT_PILE_SIZE_COUNTER', 'b') == 5
        assert e.in_control()
        after = e.raw('MAP_COLLISION_DATA', 10000, e.ram())
        assert all(after[i] == 81 for i in cells)
        assert all(before[i] == after[i] for i in range(10000) if i not in cells)
        assert e.peek('CURRENT_SCREEN', 'h') == 28
        result['pile_work'] = e.peek('SCRIPT_STATE+363', 'B')
        result['cart_progress'] = e.peek('SCRIPT_STATE+362', 'B')
        assert result['pile_work'] == 8 and result['cart_progress'] == 3
        result['restored_tiles'] = [after[i] for i in cells]
        place(e,1750,850); focus(e)
        e.run('shot', str(out/'rubble-cleared-cart-full.png'))
        with ThreadPoolExecutor() as pool:
            video=pool.submit(e.run, 'record', str(out/'rubble-cleared.mp4'), '6')
            e.press('RIGHT', 48); video.result()
        result['pile_walk_end']=e.peek('TAMER_POSITION_DATA+0x78','3i')
        assert result['pile_walk_end'][0]>=2200
        assert e.peek('SCRIPT_STATE+362','B')==3
        e.run('shot', str(out/'rubble-walk-through.png'))
        result['ok'] = True
        print('PASS: actual post-fight scene, native town corner walk and live rubble collision', flush=True)
    finally:
        e.stop(); (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__': main()
