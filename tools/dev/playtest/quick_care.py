#!/usr/bin/env python3
"""2 MB pad-input regression for Square care, NPC priority and contextual Square uses.

python3 tools/dev/playtest/quick_care.py DISC --exe EXE --card CARD --out build/care-proof
Boots the supplied disc/card, never imports a state from a different executable.
"""
from pathlib import Path
import argparse
import json
import hashlib
import os
import signal
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols


def wait(e, name, value, fmt='i', seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        actual = e.peek(name, fmt)
        if actual == value:
            return
        e.wait(.15)
    raise AssertionError(f'{name}: {actual}, expected {value}')


def care_object(e):
    ram = e.ram()
    a = e.A('WORLD_OBJECTS') - 0x80000000
    return any(struct.unpack_from('<h', ram, a + 12*i)[0] == 0x1f9b for i in range(128))


def badge_pixels(e):
    from tools.localize.systemw import CARE_BUTTON_RECTS
    vram=e.api('/api/v1/gpu/vram/raw')
    palette=struct.unpack_from('<16H',vram,(252*1024+352)*2)
    assert palette[12:14]==(0x621f,0x3d14),palette[12:14]
    for start in (27,39):
        for y in range(128+start,128+start+12):
            border=struct.unpack_from('<H',vram,(y*1024+379)*2)[0]>>12
            assert palette[border]==0, 'care UV guard became opaque'
    pixels=bytearray()
    for u,v,w,h in CARE_BUTTON_RECTS:
        x=320+u//4
        for y in range(v+128,v+128+h):
            offset=(y*1024+x)*2;pixels.extend(vram[offset:offset+w//2])
    return hashlib.sha256(pixels+struct.pack('<16H',*palette)).hexdigest()


def need(e):
    e.gs('set', 'partner.para.evoTimer=0', 'partner.para.condition=0',
         'partner.stats.hp=2000', 'partner.stats.mp=2000', 'partner.stats.currentHP=2000',
         'partner.stats.currentMP=500', 'partner.para.remainingLifetime=1000', 'gametime_running=0')
    e.poke('INVENTORY', struct.pack('<30h', 4, *([-1]*29)))
    e.poke('INVENTORY+60', bytes([10] + [0]*29))
    e.poke('ITEM_SCOLD_FLAG', b'\0')


def position(e, entity):
    ram = e.ram()
    ptr = e.peek(entity+'+4', 'I', ram)
    return list(struct.unpack_from('<3i', ram, ptr - 0x80000000 + 0x78))


def place_partner(e, x, y, z):
    ptr = e.peek('PARTNER_ENTITY+4', 'I')
    e.run('poke', hex(ptr+0x78), struct.pack('<3i', x, y, z).hex())
    e.poke('PARTNER_ENTITY+0x10', struct.pack('<3i', x << 15, y << 15, z << 15))


def restore(e, path, layout):
    e.run('load', str(path))
    e.run('resume')
    call(e, 'modSetButtons', layout)
    e.run('resume')
    e.wait(.3)


def field(e, base, out, layout, far):
    restore(e, base, layout)
    need(e)
    x,y,z = position(e, 'TAMER_ENTITY')
    # Move only the partner fixture, leaving the camera and tamer on a known walkable tile.
    place_partner(e, x + (4000 if far else 100), y, z + (4000 if far else 100))
    if far:
        e.poke('TAMER_POSITION_DATA+0x72', struct.pack('<h', 0x800))
    e.wait(.2)
    t = position(e, 'TAMER_ENTITY'); p = position(e, 'PARTNER_ENTITY')
    distance = round(((p[0]-t[0])**2 + (p[2]-t[2])**2)**.5)
    if far:
        assert distance > 3000, distance
    assert not care_object(e)
    badge_hash=badge_pixels(e)
    e.run('resume')
    if not far:
        e.run('shot',str(out/f'layout-{layout}-field-badge.png'))
    e.press('SQUARE', 8)
    wait(e, 'feedState', 1)
    assert care_object(e) and e.peek('IS_IN_MENU', 'i') == 1
    assert e.peek('INVENTORY+60', 'B') == 10, 'opening care consumed an item'
    e.run('shot', str(out/f'layout-{layout}-care-{ "far" if far else "near"}.png'))
    e.press('CANCEL', 8)
    wait(e, 'TAMER_STATE', 0, 'b')
    assert not care_object(e)
    return {'distance':distance, 'square_opened':True, 'opening_consumed':False, 'badge_sha256':badge_hash}


def npc(e, base, out, layout):
    restore(e, base, layout)
    assert e.warp(218), 'Jijimon house load'
    assert e.in_control()
    need(e)
    ram = e.ram(); table = e.A('NPC_ENTITIES')-0x80000000
    candidates=[]
    for slot in range(8):
        pd=struct.unpack_from('<I',ram,table+0x68*slot+4)[0]
        if 0x80000000 < pd < 0x80200000:
            candidates.append(slot)
    assert candidates, 'no house NPC'
    slot=candidates[0]
    # Isolate manual talk from touch-triggered talk in this fixture.
    e.poke(f'NPC_ENTITIES+{slot*0x68+0x66}', b'\0')
    e.gs('approach', str(slot), '100')
    x,y,z=position(e,'TAMER_ENTITY');place_partner(e,x+80,y,z+80)
    e.wait(.2)
    assert not care_object(e)
    e.press('CONFIRM',8)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and e.peek('IS_SCRIPT_PAUSED','i')==1:
        e.wait(.15)
    assert e.peek('IS_SCRIPT_PAUSED','i')==0, 'Confirm did not start NPC dialogue'
    assert not care_object(e), 'Confirm opened care'
    assert e.peek('INVENTORY+60','B')==10
    e.run('shot',str(out/f'layout-{layout}-npc.png'))
    return {'npc_slot':slot,'confirm_started_dialogue':True,'care_opened':False}


def menus(e, base, out, layout):
    restore(e,base,layout);need(e)
    e.press('TRIANGLE',8);e.wait(1)
    assert e.peek('IS_IN_MENU','i')==1
    e.press('SQUARE',8)
    assert not care_object(e), 'Square leaked into care from triangle menu'
    call(e,'handleGameMenuSelection',2);e.run('resume')
    wait(e,'MENU_STATE',1,'b')
    e.press('RIGHT',8);wait(e,'DIGIMON_MENU_STATE',1,'b')
    wait(e,'MENU_STATE',1,'b')
    e.press('CONFIRM',8);wait(e,'MENU_STATE',6,'b')
    e.press('SQUARE',8);e.wait(.5)
    assert e.peek('MENU_STATE','b') in (7,8), 'Square did not open technique help'
    assert not care_object(e)
    e.run('shot',str(out/f'layout-{layout}-technique-square.png'))
    return {'triangle_square_no_care':True,'technique_square_help':True}


def bank(e, base, out, layout):
    restore(e,base,layout);assert e.warp(211);assert e.in_control();need(e)
    e.gs('trigger','51','1')
    call(e,'callScriptSection',e.peek('CURRENT_SCRIPT_ID','H'),81,0)
    e.run('resume')
    for _ in range(35):
        if e.peek('ITEM_MENU_TYPE','B')==5 and e.peek('SCRIPT_STATE_2','H')==1:
            break
        e.press('CONFIRM',8);e.wait(.3)
    else:raise AssertionError('Item Bank window did not open')
    # SCRIPT_STATE_2 changes before the bank's two boxes finish opening.
    # Observe the selected pane to prove that menu input is actually accepted.
    for _ in range(10):
        e.press('RIGHT',16)
        if e.peek('MAIN_D_80134F90','B')==1:break
        e.wait(.2)
    else:raise AssertionError('Item Bank inventory pane did not become active')
    e.run('lua',f"CARE_BANK=false;CARE_BANK_BP=PCSX.addBreakpoint({e.A('keeperMoveStack')},'Exec',4,'care-bank-proof',function() CARE_BANK=true end)")
    try:
        for _ in range(3):
            e.press('SQUARE',30);e.wait(.2)
            if e.run('lua','return CARE_BANK').strip()=='true':break
        assert e.run('lua','return CARE_BANK').strip()=='true','Square did not select bank all'
        assert e.peek('INVENTORY+60','B')==0,'bank all did not transfer the full stack'
        assert not care_object(e)
        e.run('shot',str(out/f'layout-{layout}-bank-square.png'))
    finally:e.run('lua','CARE_BANK_BP:remove()')
    return {'square_moved_stack':True,'care_opened':False}


def chart(e, base, out, layout):
    restore(e,base,layout);need(e)
    e.poke('MOD_OPT_EVO_GUIDE', struct.pack('<i', 1))
    e.poke('MOD_OPT_NEW_DIGIMON', struct.pack('<i', 1))
    # This starter card has no raised flags. Mark Agumon through the game's
    # own flag writer, then reach its detail through the ordinary chart UI.
    call(e, 'setDigimonRaised', 3);e.run('resume')
    e.press('TRIANGLE',8);e.wait(1)
    call(e,'handleGameMenuSelection',3);e.run('resume');wait(e,'MENU_STATE',1,'b')
    e.press('RIGHT',8);wait(e,'PLAYER_MENU_STATE',1,'b');wait(e,'MENU_STATE',1,'b')
    e.press('CONFIRM',8);wait(e,'MENU_STATE',2,'b')
    e.press('R1', 8)
    wait(e, 'CHART_SELECTED_DIGIMON', 3, 'h')
    e.press('CONFIRM', 8);wait(e, 'MENU_STATE', 3, 'b')
    e.wait(1)
    # Select an evolution target using the existing detail navigation.
    for _ in range(12):
        e.press('SQUARE',8);e.wait(.15)
        if e.peek('CHART_POPUP','b')==1:break
        e.press('RIGHT',8)
    else:raise AssertionError('Square did not open evolution requirements')
    assert not care_object(e)
    e.run('shot',str(out/f'layout-{layout}-chart-square.png'))
    e.press('SQUARE',8);wait(e,'CHART_POPUP',0,'b')
    assert not care_object(e)
    return {'square_opened_and_closed_requirements':True,'care_opened':False}


def battle(e, base, out, layout, mem, variables, types):
    restore(e,base,layout);need(e)
    e.gs('set','partner.stats.off=1','partner.stats.def=900','partner.stats.brain=900')
    e.gs('trigger','1','1');assert e.warp(0)
    e.gs('approach','0','150')
    for _ in range(60):
        if e.peek('GAME_STATE','B')==1:break
        e.press('CONFIRM',8);e.wait(.3)
    else:raise AssertionError('battle did not start')
    e.wait(5)
    def address(expr):
        mem._ram=e.ram()
        return mem.resolve_expr(expr,variables,types)
    addr,t=address('COMBAT_DATA.fighter[0].finisherGoal')
    goal=int.from_bytes(e.ram()[addr-0x80000000:addr-0x80000000+t['size']],'little')
    assert goal>0,goal
    addr,t=address('COMBAT_DATA.fighter[0].finisherProgress')
    e.run('poke',hex(addr),goal.to_bytes(t['size'],'little').hex())
    e.run('lua',f'''CARE_FINISH=false;CARE_FINISH_TICKS=0;CARE_FINISH_POLL=false
      CARE_FINISH_TICK_BP=PCSX.addBreakpoint({e.A('handleCommands')},'Exec',4,'care-battle-input-proof',function()
        CARE_FINISH_TICKS=CARE_FINISH_TICKS+1
        local m=PCSX.getMemPtr()
        if tonumber(m[{e.A('POLLED_INPUT') & 0x1fffff}])>=128 and
           tonumber(m[{e.A('POLLED_INPUT_PREVIOUS') & 0x1fffff}])<128 then CARE_FINISH_POLL=true end
      end)
      CARE_FINISH_BP=PCSX.addBreakpoint({e.A('BTL_drawCommandShout')},'Exec',4,'care-finisher-proof',function()
        if tonumber(PCSX.getRegisters().GPR.n.a0)==11 then CARE_FINISH=true end
      end)''')
    try:
        for _ in range(100):
            if int(e.run('lua','return CARE_FINISH_TICKS').strip())>=4:break
            e.wait(.1)
        else:raise AssertionError('battle command loop did not become active')
        # Cold battle animation reads can span a short refresh-based pulse.
        # Keep the key down through a full half-second of emulated refreshes.
        e.press('SQUARE',30);e.wait(1)
        assert e.run('lua','return CARE_FINISH_POLL').strip()=='true','battle never polled the Square edge'
        assert e.run('lua','return CARE_FINISH').strip()=='true','Square did not request finisher'
        assert not care_object(e)
        e.run('shot',str(out/f'layout-{layout}-battle-square.png'))
    finally:e.run('lua','CARE_FINISH_BP:remove();CARE_FINISH_TICK_BP:remove()')
    return {'square_edge_polled_in_battle':True,'square_requested_finisher':True,'care_opened':False}


def fonts(e, base, out, layout, expected_badge):
    result = {}
    for font, name in ((0, 'new'), (1, 'original'), (2, 'classic')):
        restore(e, base, layout)
        need(e)
        call(e, 'modSetFont', font)
        e.run('resume')
        e.wait(.3)
        assert badge_pixels(e) == expected_badge, f'{name} changed the care artwork'
        e.run('resume')
        e.press('SQUARE', 8)
        wait(e, 'feedState', 1)
        assert care_object(e)
        e.run('shot', str(out / f'layout-{layout}-font-{name}.png'))
        result[name] = {'square_opened': True, 'badge_unchanged': True}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True);p.add_argument('--card',required=True)
    p.add_argument('--out',default='build/care-proof');p.add_argument('--port',type=int,default=41931)
    p.add_argument('--resume', action='store_true', help='resume unfinished cases from this executable\'s own fixture')
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out/'emu'));e.env['EMU_ARGS']='-interpreter -debugger'
    for name,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,addr)
    fixture = out / 'fixture.json'
    exe_hash = hashlib.sha256(Path(a.exe).read_bytes()).hexdigest()
    result = json.loads((out / 'result.json').read_text()) if a.resume else {}
    result.pop('error', None)
    def stop_on_signal(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, stop_on_signal)
    try:
        e.start(a.card)
        base = out / 'field.state'
        if a.resume:
            assert json.loads(fixture.read_text())['exe_sha256'] == exe_hash, 'fixture belongs to another executable'
            e.run('load', str(base));e.run('resume')
        else:
            assert e.continue_game()==0,'Continue failed'
            e.wait(5)
        assert e.in_control();assert len(e.ram())==0x200000
        assert call(e, 'modProbeRam') == 0, '8 MB RAM was detected'
        e.run('resume')
        result['configuration'] = {'ram_bytes': 0x200000, 'eight_mb_probe': False}
        # The inspector needs the running build's own object types and symbol addresses.
        os.environ.update(EMU_PORT=str(a.port),DW_SYMS=e.exe)
        from tools.dev import memory_inspector as mem
        from tools.dev import symbols
        mem._build=symbols.explicit_build(e.exe)
        variables,types=mem.build_index()
        if not a.resume:
            assert e.warp(171), 'File City load'
            need(e);e.run('save',str(base))
            fixture.write_text(json.dumps({'exe_sha256': exe_hash, 'ram_bytes': 0x200000}) + '\n')
        for layout in (0,1):
            result.setdefault(str(layout), {})
            for name,fn in [('near',lambda:field(e,base,out,layout,False)),
                            ('far',lambda:field(e,base,out,layout,True)),
                            ('npc',lambda:npc(e,base,out,layout)),
                            ('menus',lambda:menus(e,base,out,layout)),
                            ('bank',lambda:bank(e,base,out,layout)),
                            ('chart',lambda:chart(e,base,out,layout)),
                            ('battle',lambda:battle(e,base,out,layout,mem,variables,types))]:
                if name in result[str(layout)]:
                    continue
                result[str(layout)][name]=fn()
                (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
                print(layout,name,result[str(layout)][name],flush=True)
            if 'fonts' not in result[str(layout)]:
                result[str(layout)]['fonts'] = fonts(e, base, out, layout, result[str(layout)]['near']['badge_sha256'])
            (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            print(layout, 'fonts', result[str(layout)]['fonts'], flush=True)
        assert result['0']['near']['badge_sha256'] == result['1']['near']['badge_sha256'], 'layout changed the care artwork'
    except BaseException as error:
        result['error']=str(error)
        try:e.run('shot',str(out/'failure.png'));e.run('save',str(out/'failure.state'))
        except Exception:pass
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        raise
    finally:e.stop()


if __name__=='__main__':main()
