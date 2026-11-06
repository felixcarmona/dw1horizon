#!/usr/bin/env python3
"""Inspect shop/vending balances at digit boundaries across languages and fonts.

The real createShopBitsBox/tickShopBitsBox/renderShopBitsBox path is called
on a quiet field. The same shared box is used by shops and vending machines.
Money, merit and the shopkeeper fixture are set directly; text comes from disc.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--base',type=Path)
    p.add_argument('--port',type=int,default=42547)
    p.add_argument('--languages',default='0,1,2,3,4,5,6,7')
    p.add_argument('--fonts',default='0,1,2');p.add_argument('--amounts',default='99999,100000,119967,999999')
    p.add_argument('--eight-mb',action='store_true')
    p.add_argument('--coexist',action='store_true',help='redraw while another box owns the shared piece layout')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out))
    for n,(addr,_,_) in elf_symbols(e.exe+'.elf').items():e.table.setdefault(n,addr)
    e.env['EMU_ARGS']='-interpreter -debugger'+(' -8mb' if a.eight_mb else '')
    if a.eight_mb:
        e.ram=lambda:e.api('/api/v1/cpu/ram/raw')
    results=[]
    try:
        e.start(field_card(str(ROOT/'tools/dev/saves/corpus/20261027-d2796814.mcd'),str(out/'fixture.mcd')))
        if a.base:e.run('load',str(a.base.resolve()));e.run('resume')
        else:
            e.run('lua',f"PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'skip-intro',function() PCSX.getRegisters().GPR.n.a1=0 end)")
            assert e.continue_game()==0
        assert e.in_control()
        flow=json.loads(e.api('/api/v1/execution-flow'))
        assert flow['8mb']==a.eight_mb,'unexpected emulator RAM configuration'
        (out/'run.json').write_text(json.dumps(dict(emulator_flow=flow),indent=2)+'\n')
        e.gs('set','gametime_running=0')
        for language in map(int,a.languages.split(',')):
            call(e,'modSetLanguage',language);e.run('resume')
            assert e.peek('MOD_LANG','i')==language
            for font in map(int,a.fonts.split(',')):
                call(e,'modSetFont',font);e.run('resume')
                for amount in map(int,a.amounts.split(',')):
                    e.poke('MONEY',struct.pack('<i',amount))
                    call(e,'writePStat',254,255);e.run('resume')
                    call(e,'createShopBitsBox',1);e.run('resume')
                    e.poke('UPDATE_SHOP_BIT_BOX',struct.pack('<i',1))
                    call(e,'tickShopBitsBox');e.run('resume')
                    # A field fixture has no active script to tick these boxes.
                    e.poke('ACTIVE_INSTRUCTION',b'\x64')
                    call(e,'tickTextboxHandling',0);e.run('resume')
                    e.wait(2)
                    assert e.peek('UI_BOX_DATA+90','h')==1,'balance box did not open'
                    label=f'lang{language}-font{font}-bits{amount}'
                    e.run('shot',str(out/(label+'.png')))
                    results.append(dict(language=language,font=e.peek('MOD_FONT','b'),money=e.peek('MONEY','i'),shot=label+'.png'))
                    print(json.dumps(results[-1]),flush=True)
                if a.coexist:
                    # The card-shop answers use this shared layout while the balance stays open.
                    call(e,'textboxRowPieces',3,1,e.A('BALANCE_PIECES'));e.run('resume')
                    e.poke('MONEY',struct.pack('<i',119967))
                    e.poke('UPDATE_SHOP_BIT_BOX',struct.pack('<i',1))
                    call(e,'tickShopBitsBox');e.run('resume')
                    e.poke('ACTIVE_INSTRUCTION',b'\x64')
                    call(e,'tickTextboxHandling',0);e.run('resume');e.wait(1)
                    e.run('shot',str(out/f'lang{language}-font{font}-coexist.png'))
                    call(e,'textboxRowPieces',-1,0,0);e.run('resume')
                    results.append(dict(language=language,font=font,coexist=True))
                call(e,'closeTextbox',2,0);e.run('resume');e.wait(.5)
        (out/'result.json').write_text(json.dumps(results,indent=2)+'\n')
    finally:e.stop()

if __name__=='__main__':main()
