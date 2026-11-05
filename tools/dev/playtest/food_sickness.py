#!/usr/bin/env python3
"""Exercise Happymushrm through both menus on a 2 MB disc.

Fixture evolution loads each species' real model. Only care values, inventory,
name and sickness probability are set up; pad input selects and gives the item.
--before expects the translated sickness stack corruption on the unfixed disc.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.ogre_tunnel import place
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols


def emulator(disc, exe, port, out):
    e = ProofEmu(disc, exe, port, str(out))
    for name, (addr, _, _) in elf_symbols(exe + '.elf').items():
        e.table.setdefault(name, addr)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    return e


def fixture(e, state, species):
    e.run('load', str(state))
    e.run('resume')
    if e.peek('PARTNER_ENTITY', 'i') != species:
        e.run('pause')
        for name, data in (('EVOLUTION_TARGET', struct.pack('<h', species)), ('HAS_USED_EVOITEM', b'\1'),
                           ('TAMER_STATE', b'\6'), ('TAMER_SUB_STATE', b'\0'),
                           ('PARTNER_STATE', b'\15'), ('PARTNER_SUB_STATE', b'\0')):
            e.poke(name, data)
        e.run('resume')
        for _ in range(120):
            ram = e.ram()
            if e.peek('PARTNER_ENTITY', 'i', ram) == species and e.peek('PARTNER_STATE', 'b', ram) == 1:
                break
            if e.peek('MOD_EVO_SKIP', 'b') == 3:
                e.press('START', 8)
            elif e.peek('TAMER_STATE', 'b') == 20:
                e.press('CONFIRM', 8)
            e.poke('PAUSE_STATE', b'\0')
            e.wait(.25)
        else:
            raise AssertionError(f'fixture species {species} did not finish loading')
    e.poke('PAUSE_STATE', b'\0')
    assert e.in_control(), 'fixture evolution did not return control'
    for _ in range(6):
        if not e.peek('IS_IN_MENU', 'b'):
            break
        e.press('CANCEL', 12)
        e.wait(.2)
    assert e.peek('IS_IN_MENU', 'b') == 0, 'fixture left a menu open'
    # Checkpoints must not retain an unfinished CD transfer.
    for _ in range(100):
        busy = call(e, 'isFileReadQueueBusy')
        e.run('resume')
        if not busy:
            break
        e.wait(.2)
    assert not busy, 'fixture CD queue did not settle'
    e.gs('set', 'gametime_running=0', 'partner.para.evoTimer=0', 'partner.para.remainingLifetime=1000')
    assert e.peek('PARTNER_ENTITY', 'i') == species


def setup_food(e, enabled):
    e.run('pause')
    e.poke('MOD_OPT_NEW_DIGIMON', struct.pack('<i', enabled))
    e.gs('set', 'gametime_running=0', 'partner.para.evoTimer=0', 'partner.para.condition=4',
         'partner.para.energyLevel=0', 'partner.para.foodLevel=0', 'partner.para.happiness=30',
         'partner.para.discipline=100', 'partner.para.tiredness=50',
         'inventory.types=[69' + ',-1' * 29 + ']', 'inventory.amounts=[3' + ',0' * 29 + ']',
         'inventory.names=[0' + ',255' * 29 + ']')
    # Nine full-width keyboard letters occupy 18 bytes in the 20-byte name field.
    e.poke('PARTNER_ENTITY+0x68', bytes.fromhex('826082618262826382648265826682678268') + b'\0')
    e.poke('INVENTORY_POINTER', b'\0')
    place(e, 1500, -1450)
    pos = e.peek('PARTNER_ENTITY+4', 'I')
    e.run('poke', hex(pos + 0x78), struct.pack('<3i', 1400, 0, -1450).hex())
    e.poke('PARTNER_ENTITY+0x10', struct.pack('<3i', 1400 << 15, 0, -1450 << 15))
    e.run('resume')


def watch_food(e, sick):
    a = e.A
    e.run('lua', f'''
if FOOD then for _,b in ipairs(FOOD.bp) do b:remove() end end
FOOD={{bp={{}},sickness=0,returned=0,eat=false}}
local function hook(a,f) local b=PCSX.addBreakpoint(a,'Exec',4,'food-proof',f);FOOD.bp[#FOOD.bp+1]=b;return b end
hook({a('handleItemSickness')},function()
 FOOD.sickness=FOOD.sickness+1;PCSX.getRegisters().GPR.n.a0={100 if sick else 0}
end)
hook({a('handleFood')},function()
 local ra=PCSX.getRegisters().GPR.n.ra
 local b; b=hook(ra,function() FOOD.returned=FOOD.returned+1;b:remove() end)
end)
hook({a('startAnimation')},function()
 local r=PCSX.getRegisters();if r.GPR.n.a0=={a('PARTNER_ENTITY')} and r.GPR.n.a1==8 then FOOD.eat=true end
end)
''')


def trace(e, name):
    return e.run('lua', 'return FOOD.' + name).strip()


def open_menu(e, route, path):
    if route == 'item':
        e.press('TRIANGLE', 12)
        for k in range(16):
            ram = e.ram()
            if e.peek('PARTNER_STATE', 'b', ram) == 5:
                return
            if k < 4:
                e.run('shot', str(path.with_name(path.stem + f'-step{k}.png')))
            e.press('CONFIRM', 12)
            e.wait(.2)
        raise AssertionError('inventory did not start feeding')
    call(e, 'entityLookAtLocation', e.A('TAMER_ENTITY'), e.peek('PARTNER_ENTITY+4', 'I') + 0x78)
    e.run('resume')
    for _ in range(4):
        if e.peek('IS_IN_MENU', 'i'):
            break
        e.press('CONFIRM', 12)
        e.wait(.5)
    assert e.peek('IS_IN_MENU', 'i') == 1, 'care menu did not open'
    # Opening boxes ignore input; wait for the actual interactive menu state.
    deadline = time.monotonic() + 60
    while e.peek('feedState', 'i') != 1 and time.monotonic() < deadline:
        e.wait(.2)
    assert e.peek('feedState', 'i') == 1, 'care menu never finished opening'
    e.run('shot', str(path.with_name(path.stem + '-menu.png')))
    for _ in range(8):
        if e.peek('feedState', 'i') != 1:
            return
        e.press('CONFIRM', 24)
        e.wait(.3)
    assert e.peek('feedState', 'i') != 1, 'care menu did not acknowledge giving the item'


def food_case(e, state, out, species, route, enabled, before, sick=True):
    fixture(e, state, species)
    assert e.peek('MOD_LANG', 'i') == 1, 'Spanish fixture language was lost'
    setup_food(e, enabled)
    watch_food(e, sick)
    label = f'{species}-{route}-new{enabled}-sick{int(sick)}'
    path = out / (label + '.png')
    open_menu(e, route, path)
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline and trace(e, 'sickness') == '0':
        e.wait(.25)
    e.run('shot', str(path.with_name(path.stem + '-effect.png')))
    assert trace(e, 'eat') == 'true', 'real eat clip was not started'
    assert trace(e, 'sickness') == '1', 'food effect was not reached'
    e.wait(1)
    returned = trace(e, 'returned') == '1'
    if sick and before:
        assert not returned, 'expected unfixed sickness crash'
    else:
        assert returned, 'food effect corrupted the return address'
        assert e.peek('INVENTORY+60', 'B') == 2, 'one mushroom was not consumed'
        if sick:
            e.press('CONFIRM', 12)
        assert e.in_control(), 'control did not return after feeding'
    e.run('shot', str(path))
    result = dict(species=species, route=route, new_digimon=enabled, sickness=sick,
                  eat_clip=True, food_returned=returned,
                  exception_pc=e.run('lua', 'return PCSX.getRegisters().pc').strip())
    print(json.dumps(result), flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--port', type=int, default=39342)
    p.add_argument('--species', default='1,2,3,470,180,195,224,373')
    p.add_argument('--before', action='store_true'); p.add_argument('--base', type=Path)
    a = p.parse_args(); out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    e = emulator(a.disc, a.exe, a.port, out)
    results = []
    try:
        if a.base:
            state = a.base.resolve()
            e.start(None)
            e.run('load', str(state))
            e.run('resume')
        else:
            card = field_card(str(ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd'), str(out / 'fixture.mcd'))
            e.start(card)
            assert e.continue_game() == 0
            call(e, 'modSetLanguage', 1)
            e.run('resume')
            e.gs('set', 'gametime_running=0')
            state = out / 'base.state'
            e.run('save', str(state))
        assert len(e.ram()) == 0x200000
        for species in map(int, a.species.split(',')):
            fixture(e, state, species)
            model_state = out / f'fixture-{species}.state'
            e.run('save', str(model_state))
            for route in ('item', 'care'):
                results.append(food_case(e, model_state, out, species, route, 1, a.before))
        for route in ('item', 'care'):
            results.append(food_case(e, state, out, 3, route, 0, a.before))
        results.append(food_case(e, state, out, 3, 'item', 1, False, sick=False))
    finally:
        (out / 'result.json').write_text(json.dumps(dict(ram_bytes=0x200000, before=a.before, cases=results), indent=2)+'\n')
        e.stop()


if __name__ == '__main__':
    main()
