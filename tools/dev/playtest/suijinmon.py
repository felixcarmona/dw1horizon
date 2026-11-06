#!/usr/bin/env python3
"""Load Suijinmon's real model and capture running and food through the game.

The run plays in place (the engine's no-root-travel flag) for visual comparison.
Feeding is selected through the inventory and consumes one Digiseabass.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.playtest.frigimon_recruitment import fixture_partner
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.training_evolution import call
from tools.dev.playtest.ogre_tunnel import place
from tools.langpatch import elf_symbols


def settle_notices(e):
    """Close queued evolution/knowledge notices and require stable field control."""
    stable=0
    for _ in range(80):
        if e.peek('TAMER_STATE','b')==0 and e.peek('IS_SCRIPT_PAUSED','i')==1:
            stable+=1
            if stable==4:return
        else:
            stable=0;e.press('CONFIRM',12)
        e.wait(.5)
    raise AssertionError('queued field notices did not settle')


def stage(e):
    e.run('pause')
    e.gs('set','gametime_running=0','partner.para.evoTimer=0','partner.para.remainingLifetime=1000',
         'partner.para.condition=4','partner.para.energyLevel=0','partner.para.discipline=100',
         'partner.para.foodLevel=0','partner.para.happiness=50',
         'inventory.types=[67'+',-1'*29+']','inventory.amounts=[2'+',0'*29+']',
         'inventory.names=[0'+',255'*29+']')
    x,y,z=e.peek('TAMER_POSITION_DATA+0x78','3i')
    x-=300;z+=50
    pos=e.peek('PARTNER_ENTITY+4','I')
    e.run('poke',hex(pos+0x78),struct.pack('<3i',x,0,z).hex())
    e.poke('PARTNER_ENTITY+0x10',struct.pack('<3i',x<<15,0,z<<15))
    e.run('resume')
    return pos


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--base',type=Path)
    p.add_argument('--port',type=int,default=42549)
    p.add_argument('--expect-upgrade',action='store_true')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out))
    for n,(addr,_,_) in elf_symbols(e.exe+'.elf').items():e.table.setdefault(n,addr)
    e.env['EMU_ARGS']='-interpreter -debugger'
    record=None;results={}
    try:
        e.start(field_card(str(ROOT/'tools/dev/saves/corpus/20261027-d2796814.mcd'),str(out/'fixture.mcd')))
        if a.base:e.run('load',str(a.base.resolve()));e.run('resume');assert e.in_control()
        else:
            e.run('lua',f"PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'skip-intro',function() PCSX.getRegisters().GPR.n.a1=0 end)")
            assert e.continue_game()==0
        e.gs('set','gametime_running=0','partner.para.evoTimer=0','partner.para.remainingLifetime=1000')
        fixture_partner(e,408)
        settle_notices(e)
        print('Loaded Suijinmon on 2 MB',flush=True)
        e.run('save',str(out/'model-loaded.state'))
        assert len(e.ram())==0x200000
        results['emulator_flow']=json.loads(e.api('/api/v1/execution-flow'))
        assert not results['emulator_flow']['8mb'],'proof requires original 2 MB RAM'
        ptr=call(e,'getSpeciesPara',408)
        ram=e.ram();off=ptr-0x80000000
        moves=list(ram[off+35:off+51]);specialties=list(ram[off+30:off+33])
        predecessor=e.A('DIGIMON_DATA')-0x80000000+112*52
        previous=list(ram[predecessor+35:predecessor+51])
        results['moveset']=dict(moves=moves,specialties=specialties,predecessor_moves=previous,
                                retained=sorted(set(moves)&set(previous)-{255}))
        if a.expect_upgrade:
            assert 255 not in moves and 8 in moves and 30 in moves,(moves,specialties)
            assert specialties==[4,5,2],specialties
        e.run('resume')
        stage(e)
        e.run('save',str(out/'suijinmon.state'))
        e.poke('PARTNER_STATE',b'\14')
        call(e,'startAnimation',e.A('PARTNER_ENTITY'),4)
        e.poke('PARTNER_ENTITY+0x30',b'\3');e.run('resume')
        e.wait(1);e.run('shot',str(out/'run.png'))
        before=e.peek('PARTNER_ENTITY+0x1c','h')
        e.run('record',str(out/'run.mp4'),'6','20')
        after=e.peek('PARTNER_ENTITY+0x1c','h')
        results['run']=dict(frame_before=before,frame_after=after)
        print('Recorded run',flush=True)
        e.run('load',str(out/'suijinmon.state'));e.run('resume');stage(e)
        e.poke('INVENTORY_POINTER',b'\0')
        e.run('lua',f'''
SJ={{eating=false,returned=false}}
SJ.bp=PCSX.addBreakpoint({e.A('startAnimation')},'Exec',4,'suijinmon-eat',function()
 local r=PCSX.getRegisters()
 if r.GPR.n.a0=={e.A('PARTNER_ENTITY')} and r.GPR.n.a1==8 then SJ.eating=true end
end)
SJ.food=PCSX.addBreakpoint({e.A('handleFood')},'Exec',4,'suijinmon-food',function() SJ.returned=true end)
''')
        e.press('TRIANGLE',12)
        for _ in range(12):
            if e.peek('PARTNER_STATE','b')==5:break
            e.press('CONFIRM',12);e.wait(.3)
        for i in range(120):
            if record is None and e.run('lua','return SJ.eating').strip()=='true':
                e.run('pause')
                record=subprocess.Popen([sys.executable,'tools/dev/emulator.py','record',str(out/'feed.mp4'),'15','20'],env=e.env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                e.run('resume')
            if i%3==0:e.run('shot',str(out/f'feeding-{i}.png'))
            if e.run('lua','return SJ.returned').strip()=='true':break
            e.wait(.3)
        assert e.run('lua','return SJ.eating').strip()=='true','real feeding clip was not played'
        assert e.run('lua','return SJ.returned').strip()=='true','food effect was not reached'
        assert e.peek('INVENTORY+60','B')==1,'one Digiseabass was not consumed'
        assert e.in_control(),'food did not finish'
        results['feeding']=dict(eating=True,consumed=1)
        if record:print(record.communicate(timeout=60)[0]);record=None
        e.run('shot',str(out/'fed.png'))
        e.run('load',str(out/'suijinmon.state'));e.run('resume')
        assert e.in_control(),'checkpoint still has a post-evolution message'
        e.poke('PARTNER_ENTITY+0x58',b'\xff'*8)
        settle_notices(e)
        for _ in range(12):
            if e.peek('IS_IN_MENU','i') and e.peek('UI_BOX_DATA+18','h')==1 and e.peek('TRIANGLE_MENU_STATE','i')==-1:break
            e.press('TRIANGLE',12);e.wait(.5)
        assert e.peek('IS_IN_MENU','i'),'triangle menu did not open'
        call(e,'handleGameMenuSelection',2);e.run('resume')
        for _ in range(80):
            if e.peek('UI_BOX_DATA+54','h')==1 and e.peek('MENU_STATE','b')==1 and e.peek('DIGIMON_MENU_STATE','b')==0:break
            e.wait(.3)
        else:raise AssertionError('status page did not become interactive')
        e.run('shot',str(out/'status.png'))
        for _ in range(8):
            if e.peek('DIGIMON_MENU_STATE','b')==1 and e.peek('MENU_STATE','b')==1:break
            e.press('RIGHT',12);e.wait(.5)
        else:raise AssertionError('technique page did not open')
        e.run('shot',str(out/'techniques.png'))
        results['status_and_technique_pages']=True
        e.press('CONFIRM',12)
        for _ in range(60):
            if e.peek('MENU_STATE','b')==6:break
            e.wait(.3)
        else:raise AssertionError('compatible technique grid did not open')
        e.run('shot',str(out/'available-techniques.png'))
        results['compatible_technique_grid']=True
        for _ in range(8):
            if not e.peek('IS_IN_MENU','i'):break
            e.press('CANCEL',12);e.wait(.3)
        results['ram_bytes']=len(e.ram())
        print(json.dumps(results),flush=True)
    finally:
        if record:
            record.terminate();record.communicate(timeout=10)
        (out/'result.json').write_text(json.dumps(results,indent=2)+'\n')
        e.stop()

if __name__=='__main__':main()
