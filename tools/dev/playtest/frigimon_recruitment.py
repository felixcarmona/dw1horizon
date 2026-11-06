#!/usr/bin/env python3
"""Feed a risky food, play Frigimon's rescue, then recruit him on 2 MB.

Care values and the food's random outcome are fixtures. Recruitment, rescue
flags and prosperity are produced by the real scripts. A fixture evolution
loads Gabumon's model for the cold-resistant partner used on the return visit.
--before documents the food handler failing to return on an unfixed disc.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.birdramon_recruitment import field_card, bit, call_section
from tools.dev.playtest.ogre_tunnel import place
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols


def fixture_partner(e, species):
    e.run('pause')
    for name,data in [('EVOLUTION_TARGET',struct.pack('<h',species)),('HAS_USED_EVOITEM',b'\1'),
                      ('TAMER_STATE',b'\6'),('TAMER_SUB_STATE',b'\0'),
                      ('PARTNER_STATE',b'\15'),('PARTNER_SUB_STATE',b'\0')]:
        e.poke(name,data)
    e.run('resume')
    for _ in range(180):
        ram=e.ram()
        if e.peek('PARTNER_ENTITY','i',ram)==species and e.peek('PARTNER_STATE','b',ram)==1:
            e.poke('PAUSE_STATE',b'\0')
            assert e.in_control()
            return
        if e.peek('MOD_EVO_SKIP','b',ram)==3:e.press('START',8)
        elif e.peek('TAMER_STATE','b',ram)==20:e.press('CONFIRM',8)
        e.wait(.3)
    raise AssertionError(f'fixture evolution to {species} did not finish')


def feed(e,out,before):
    e.run('pause')
    e.gs('set','gametime_running=0','partner.para.evoTimer=0','partner.para.remainingLifetime=1000',
         'partner.para.condition=4','partner.para.energyLevel=0','partner.para.foodLevel=0',
         'partner.para.discipline=100', 'partner.para.happiness=50',
         'inventory.types=[69'+',-1'*29+']','inventory.amounts=[3'+',0'*29+']',
         'inventory.names=[0'+',255'*29+']')
    e.poke('PARTNER_ENTITY+0x68',bytes.fromhex('826082618262826382648265826682678268')+b'\0')
    e.poke('INVENTORY_POINTER',b'\0')
    x,y,z=e.peek('TAMER_POSITION_DATA+0x78','3i')
    x-=250;z+=50
    pos=e.peek('PARTNER_ENTITY+4','I')
    e.run('poke',hex(pos+0x78),struct.pack('<3i',x,0,z).hex())
    e.poke('PARTNER_ENTITY+0x10',struct.pack('<3i',x<<15,0,z<<15))
    e.run('lua',f'''
FR={{bp={{}},sickness=0,returned=0}}
local function hook(a,f) FR.bp[#FR.bp+1]=PCSX.addBreakpoint(a,'Exec',4,'frigimon-proof',f) end
hook({e.A('handleItemSickness')},function()
 FR.sickness=FR.sickness+1;PCSX.getRegisters().GPR.n.a0=100
end)
hook({e.A('handleFood')},function()
 local ra=PCSX.getRegisters().GPR.n.ra
 local b;b=PCSX.addBreakpoint(ra,'Exec',4,'food-return',function() FR.returned=FR.returned+1;b:remove() end)
end)
''')
    e.run('resume')
    e.press('TRIANGLE',12)
    for _ in range(12):
        if e.peek('PARTNER_STATE','b')==5:break
        e.press('CONFIRM',12);e.wait(.3)
    limit=time.monotonic()+180
    while e.run('lua','return FR.sickness').strip()=='0' and time.monotonic()<limit:e.wait(.3)
    assert e.run('lua','return FR.sickness').strip()=='1','food sickness effect not reached'
    e.wait(1)
    returned=e.run('lua','return FR.returned').strip()=='1'
    e.run('shot',str(out/'food-result.png'))
    if before:
        assert not returned,'unfixed food handler unexpectedly returned'
    else:
        assert returned,'food handler failed to return'
        assert e.peek('PARTNER_PARA','I') & 64,'food did not cause sickness'
        assert e.peek('INVENTORY+60','B')==2,'food was not consumed once'
        e.press('CONFIRM',12)
        assert e.in_control(),'feeding did not return control'
    return dict(food_returned=returned,pc=e.run('lua','return PCSX.getRegisters().pc').strip())


def dialogue(e,out,done,label,limit=180):
    for i in range(limit):
        if done():return
        if i%10==0:e.run('shot',str(out/f'{label}-{i}.png'))
        e.press('CONFIRM',8);e.wait(.3)
    raise AssertionError(f'{label} did not finish')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--port',type=int,default=42546)
    p.add_argument('--base',type=Path);p.add_argument('--before',action='store_true')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out))
    for n,(addr,_,_) in elf_symbols(e.exe+'.elf').items():e.table.setdefault(n,addr)
    e.env['EMU_ARGS']='-interpreter -debugger'
    result={}
    try:
        e.start(field_card(str(ROOT/'tools/dev/saves/corpus/20261027-d2796814.mcd'),str(out/'fixture.mcd')))
        if a.base:
            e.run('load',str(a.base.resolve()));e.run('resume');assert e.in_control()
        else:
            e.run('lua',f"PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'skip-intro',function() PCSX.getRegisters().GPR.n.a1=0 end)")
            assert e.continue_game()==0
        assert len(e.ram())==0x200000
        result['emulator_flow']=json.loads(e.api('/api/v1/execution-flow'))
        assert not result['emulator_flow']['8mb'],'proof requires original 2 MB RAM'
        call(e,'modSetLanguage',1);e.run('resume')
        assert e.peek('MOD_LANG','i')==1
        for n,v in [(133,1),(223,0)]:e.gs('trigger',str(n),str(v))
        e.run('save',str(out/'base.state'))
        (out/'base.ready').write_text('ready\n')
        result['feeding']=feed(e,out,a.before)
        print(json.dumps(result),flush=True)
        if a.before:return
        assert e.warp(94)
        e.run('pause')
        e.gs('trigger','133','0')
        assert not bit(e,133) and not bit(e,223)
        call_section(e,90,51)
        e.run('resume')
        dialogue(e,out,lambda:bit(e,133) and e.peek('CURRENT_SCREEN','h')==94,'rescue')
        assert e.in_control()
        result['rescued']=True
        e.run('shot',str(out/'rescued.png'))
        fixture_partner(e,17)
        assert e.warp(137)
        call(e,'readPStat',1);prosperity=int(e.run('lua','return TE_CALL.result').strip());e.run('resume')
        call_section(e,132,5)
        dialogue(e,out,lambda:bit(e,223),'recruit')
        e.wait(2);e.run('shot',str(out/'recruit-announcement.png'))
        assert e.in_control()
        call(e,'readPStat',1);after=int(e.run('lua','return TE_CALL.result').strip());e.run('resume')
        assert after==prosperity+2,(prosperity,after)
        result.update(recruited=True,prosperity_before=prosperity,prosperity_after=after,ram_bytes=len(e.ram()))
        e.run('shot',str(out/'recruited.png'))
        print(json.dumps(result),flush=True)
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        e.stop()

if __name__=='__main__':main()
