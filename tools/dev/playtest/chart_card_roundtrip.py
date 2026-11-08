#!/usr/bin/env python3
"""Save Chart history through the game, then Continue a raw 128 KiB .mcr copy.

The copied card's second file block is moved to a nonadjacent free block using
standard PS1 directory links. This exercises raw-card format and chain traversal;
it does not emulate ePSXe's CPU, BIOS or card timing.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.playtest.qol import ProofEmu,test_card,press_value
from tools.dev.playtest.training_evolution import call,await_value
from tools.dev import memory_card as mcd
from tools.langpatch import elf_symbols

NATIVE=(1,2,3,5,12)
IMPORTED=(180,190,203,237,407,470,476)
RECRUITED=(106,124,180,190,203,237,407)


def chart(e,out,label):
    call(e,'tamerSetState',1);e.poke('IS_IN_MENU',struct.pack('<i',1))
    call(e,'addGameMenu');e.run('resume')
    await_value(e,'TRIANGLE_MENU_STATE','i',lambda n:n==-1)
    call(e,'handleGameMenuSelection',3);e.run('resume')
    await_value(e,'MENU_STATE','b',lambda n:n==1)
    e.poke('PLAYER_MENU_STATE', b'\1')
    e.poke('MENU_STATE', b'\0')
    e.poke('MENU_SUB_STATE', b'\0')
    await_value(e,'MENU_STATE','b',lambda n:n==1)
    for _ in range(20):
        if e.peek('CHART_TAB','b')==0:break
        e.press('L1')
    e.wait(1);e.run('shot',str(out/(label+'-chart.png')))
    with ThreadPoolExecutor() as pool:
        video=pool.submit(e.run,'record',str(out/(label+'-chart.mp4')),'15')
        for tab in range(5):
            changed=e.peek('CHART_TAB','b')!=tab
            if changed:
                # The selected tab changes before its blocking icon reads end.
                # Wait for chartLoadPage to return before capturing the GPU frame.
                e.run('lua',f"""
CHART_CAPTURE={{done=false}}
CHART_CAPTURE.entry=PCSX.addBreakpoint({e.A('chartLoadPage')},'Exec',4,'chart-capture',function()
 if PCSX.getMemPtr()[{e.A('CHART_TAB') & 0x1fffff}]~={tab} then return end
 CHART_CAPTURE.entry:remove()
 local ra=PCSX.getRegisters().GPR.n.ra
 CHART_CAPTURE.finish=PCSX.addBreakpoint(ra,'Exec',4,'chart-capture-return',function()
  CHART_CAPTURE.done=true;CHART_CAPTURE.finish:remove()
 end)
end)
""")
            for _ in range(20):
                if e.peek('CHART_TAB','b')==tab:break
                e.press('R1');e.wait(.3)
            assert e.peek('CHART_TAB','b')==tab
            if changed:
                for _ in range(300):
                    if e.run('lua','return CHART_CAPTURE.done').strip()=='true':break
                    e.wait(.2)
                else:raise AssertionError('Chart page did not finish loading')
            e.wait(1)
            e.run('shot',str(out/(label+f'-tab-{tab}.png')))
            e.wait(1.5)

        video.result()
    for _ in range(12):
        if not e.peek('IS_IN_MENU','i'): break
        e.press('CANCEL');e.wait(.3)
    e.poke('PAUSE_STATE',b'\0');assert e.in_control()


def history(e):
    ram=e.ram();bits=e.raw('SPECIES_RAISED_BITS',128,ram)
    flags=e.raw('SCRIPT_STATE+245',100,ram)
    recruits=e.raw('SPECIES_RECRUITED_BITS',128,ram)
    return dict(native={str(n):bool(flags[(512+n)//8]&(1<<((512+n)%8))) for n in NATIVE},
                imported={str(n):bool(bits[n//8]&(1<<(n%8))) for n in IMPORTED},bits=bits.hex(),
                recruited={str(n):bool(recruits[n//8]&(1<<(n%8))) for n in RECRUITED},
                recruit_bits=recruits.hex(),ram_bytes=len(ram),expanded_ram=json.loads(e.api('/api/v1/execution-flow'))['8mb'])


def fragment(source,target):
    shutil.copyfile(source,target);c=mcd.Card(target);f=c.find('BASLUS-01032DMR0')
    assert len(f['blocks'])==2,f
    first,second=f['blocks'];free=next(i for i in range(15,0,-1) if i not in [b for x in c.files() for b in x['blocks']])
    c.d[free*mcd.BLOCK:(free+1)*mcd.BLOCK]=c.d[second*mcd.BLOCK:(second+1)*mcd.BLOCK]
    c.d[free*128:(free+1)*128]=c.d[second*128:(second+1)*128]
    struct.pack_into('<H',c.d,first*128+8,free-1)
    c.d[second*mcd.BLOCK:(second+1)*mcd.BLOCK]=bytes(mcd.BLOCK)
    c.d[second*128:(second+1)*128]=bytes(128)
    struct.pack_into('<IIH',c.d,second*128,0xa0,0,0xffff)
    for i in (first,second,free):
        x=0
        for b in c.d[i*128:i*128+127]:x^=b
        c.d[i*128+127]=x
    target.write_bytes(c.d)
    assert mcd.Card(target).read(f['name'])==mcd.Card(source).read(f['name'])
    return [first,free]


def save(e):
    e.poke('MOD_OPT_CHEATS', struct.pack('<i',1))
    for _ in range(12):
        if e.peek('MOD_LAB_ACTIVE','i'): break
        if not e.peek('PAUSE_STATE','b'): e.press('START');e.wait(.4)
        if e.peek('PAUSE_STATE','b'): e.press('SELECT');e.wait(.8)
    assert e.peek('MOD_LAB_ACTIVE','i')
    e.poke('MOD_LAB_CURSOR',struct.pack('<i',7))
    e.press('CONFIRM');e.wait(.5);e.press('CONFIRM')
    seen=[]
    for _ in range(100):
        menu=e.peek('CURRENT_MENU', 'i'); seen.append(menu)
        if e.peek('MEMORY_CARD_ERROR','i') > 0: return e.peek('MEMORY_CARD_ERROR','i')
        if 43 in seen and menu == -1: return 0
        e.press('CONFIRM',8);e.wait(.5)
    raise AssertionError(f'save did not finish: {seen}')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--port',type=int,default=39713)
    p.add_argument('--state',type=Path);p.add_argument('--card',type=Path,help='previous roundtrip card; require its marked history on Continue');a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out/'emu'));e.env['EMU_ARGS']='-interpreter -debugger'
    for name,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,addr)
    result={}
    try:
        e.start(str(a.card.resolve()) if a.card else test_card(out))
        if a.state:e.run('load',str(a.state.resolve()));e.run('resume')
        else:assert e.continue_game()==0
        if a.card:
            result['loaded']=history(e)
            assert all(result['loaded']['native'].values()) and all(result['loaded']['imported'].values()) and all(result['loaded']['recruited'].values()), result['loaded']
        e.poke('PAUSE_STATE',b'\0');e.wait(2);assert e.in_control()
        assert e.warp(218)
        e.gs('set','gametime_running=0')
        bits=bytearray(128)
        for n in IMPORTED:bits[n//8]|=1<<(n%8)
        e.poke('SPECIES_RAISED_BITS',bits)
        bits=bytearray(128)
        for n in RECRUITED:bits[n//8]|=1<<(n%8)
        e.poke('SPECIES_RECRUITED_BITS',bits)
        for n in NATIVE:e.gs('trigger',str(512+n),'1')
        result['before']=history(e);chart(e,out,'before')
        assert save(e)==0
        e.wait(2);e.stop()
        source=out/'written.mcd';shutil.copyfile(e.card_out(),source)
        raw=out/'fragmented.mcr';result['blocks']=fragment(source,raw)
        result['card_size']=raw.stat().st_size;result['card_sha256']=hashlib.sha256(raw.read_bytes()).hexdigest()
        e.start(raw);assert e.continue_game()==0
        result['after']=history(e)
        assert result['after']==result['before'],result
        chart(e,out,'after');result['ok']=True
        print('PASS: native/imported Chart history and recruits survive game save and fragmented raw .mcr Continue',flush=True)
    finally:
        e.stop();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
