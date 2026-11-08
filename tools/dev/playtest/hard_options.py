#!/usr/bin/env python3
"""Tour real title OPTIONS in all 2-MB languages, all font styles, and saved HARD.

On a field fixture card, HARD uses the existing option byte in both saved
copies and header. Values change through UI input; the harness positions the
row cursor. The game also writes a new save for a cold-boot round trip.
"""
import argparse
import json
from pathlib import Path
import signal
import shutil
import struct
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.saves.releases import Emu, read_card, card_ok
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev import memory_card as mcd
from tools.langpatch import elf_symbols
CODES=('en','es','pt-br','fr','de','it','ja','ca')

def hard_card(source,target):
    field_card(source,target,partner_type=65)
    c=mcd.Card(target);name='BASLUS-01032DMR0';data=bytearray(c.read(name))
    data[0x5e]=2
    size=0x2000 if len(data)>=0x6000 else 0x1000
    for i in range(2):
        offset=0x2000+i*size;head=bytearray(data[offset:offset+size]);records=list(mcd.parse_records(head))
        records=[(t,v) for t,v in records if t!=9]
        records.append((9,bytes([0,1,20,1,0,1,1,0,1,1,2,1,0,0])))
        data[offset:offset+size]=mcd.build_extension(head,records,size)
    c.write(name,0,data)
    return target

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc');ap.add_argument('--exe',required=True)
    ap.add_argument('--card',default='tools/dev/saves/corpus/20261027-d2796814.mcd')
    ap.add_argument('--out',type=Path,default=Path('build/hard-options-proof'))
    ap.add_argument('--port',type=int,default=44380)
    ap.add_argument('--save-only',action='store_true',help='keep the completed language tour and run only its save round trip')
    ap.add_argument('--chinese',action='store_true',help='separate 8 MB Chinese title proof (its original font is unavailable by design)')
    a=ap.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
    e=Emu(a.disc,a.exe,a.port,str(a.out/'emu'))
    for n,(address,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(n,address)
    e.env['EMU_ARGS']='-interpreter -debugger -bios '+str(ROOT/'.tools/emu/pcsx-redux-zip/squashfs-root/usr/share/pcsx-redux/resources/openbios.bin')+(' -8mb' if a.chinese else '')
    def interrupted(n,f):raise SystemExit(128+n)
    signal.signal(signal.SIGTERM,interrupted)
    cursor='MENU_HIGHLIGHTS+'+str(22*16)
    rows=json.loads((a.out/'results.json').read_text()) if a.save_only else []
    def roundtrip():
        assert e.continue_game()==0
        assert e.peek('MOD_OPT_DIFFICULTY','i')==2
        e.gs('set','gametime_running=0','hour=10','minute=0')
        e.wait(5)
        arrived=False
        for _ in range(3):
            arrived=e.warp(218,2)
            if arrived:break
        print(json.dumps(dict(saveWarp=arrived,screen=e.peek('CURRENT_SCREEN','h'),state=e.peek('TAMER_STATE','b'),menu=e.peek('CURRENT_MENU','i'),paused=e.peek('IS_SCRIPT_PAUSED','i'))),flush=True)
        if not arrived and e.peek('CURRENT_SCREEN','h')==218:arrived=e.in_control(tries=160)
        e.run('shot',str(a.out/'save-arrival.png'))
        assert arrived
        menus=e.save_at_jijimon()
        e.stop()
        saved=a.out/'saved-hard.mcd';shutil.copy2(e.card_out(),saved)
        assert not card_ok(str(saved))
        decoded,_,records=read_card(str(saved))
        assert records[9][10]==2
        e.start(str(saved));e.to_title()
        assert e.peek('MOD_OPT_DIFFICULTY','i')==2
        assert e.continue_game()==0
        assert e.peek('MOD_OPT_DIFFICULTY','i')==2
        (a.out/'save-roundtrip.json').write_text(json.dumps(dict(savedDifficulty=2,coldTitleDifficulty=2,continuedDifficulty=2,menus=menus,validCard=True),indent=2)+'\n')
    try:
        card=hard_card(a.card,str(a.out/'hard.mcd'));e.start(card);e.to_title()
        assert e.peek('MOD_OPT_DIFFICULTY','i')==2,'title header lost saved HARD'
        if a.save_only:
            roundtrip();return
        e.poke('MENU_HIGHLIGHTS',bytes([4]));e.press('CONFIRM',4)
        for _ in range(30):
            if e.peek('CURRENT_MENU','i')==4:break
            e.wait(1)
        assert e.peek('CURRENT_MENU','i')==4
        def settle():
            # Language/font loads set their value before returning to the menu.
            # Wait for released-input menu ticks before moving its cursor again.
            first=e.peek('MAIN_MENU_TICKS','i');deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                if e.peek('MAIN_MENU_TICKS','i')>=first+3:return
                e.wait(.1)
            raise AssertionError('options did not return to idle menu ticks')
        def choose(row,key):
            settle();e.poke(cursor,bytes([row]));e.press(key,4);settle()
            print(json.dumps(dict(inputRow=row,key=key,language=e.peek('MOD_LANG','i'),font=e.peek('MOD_FONT','b'),difficulty=e.peek('MOD_OPT_DIFFICULTY','i'))),flush=True)
        # HARD confirm wraps to EASY, then NORMAL; right reaches HARD again.
        choose(4,'CONFIRM');assert e.peek('MOD_OPT_DIFFICULTY','i')==1
        choose(4,'CONFIRM');assert e.peek('MOD_OPT_DIFFICULTY','i')==0
        choose(4,'RIGHT');assert e.peek('MOD_OPT_DIFFICULTY','i')==2
        def font(want):
            for _ in range(6):
                current=e.peek('MOD_FONT','b')
                if current==want:return
                index={0:0,2:1,1:2}[current];target={0:0,2:1,1:2}[want]
                choose(6,'RIGHT' if index<target else 'LEFT')
            raise AssertionError(('font switch',want,e.peek('MOD_FONT','b')))
        for lang,code in ([] if a.save_only else enumerate(CODES+('zh-hans',) if a.chinese else CODES)):
            assert e.peek('MOD_LANG','i')==lang,(code,e.peek('MOD_LANG','i'))
            if a.chinese and lang<8:
                choose(7,'RIGHT');continue
            for face,want in [('new',0),('classic',2),('original',1)] if lang<8 else [('new',0)]:
                font(want);e.poke(cursor,bytes([4]));e.wait(.5)
                assert e.peek('MOD_OPT_DIFFICULTY','i')==2,(code,face,e.peek('MOD_OPT_DIFFICULTY','i'))
                width=e.peek('MOD_OPT_TEXT_W','h');assert 0<width<=304
                filename=code+'-'+face+'.png';e.run('shot',str(a.out/filename))
                row=dict(language=code,font=face,difficulty=2,menuWidth=width,shown=e.peek('MOD_OPT_SHOWN','h'),savedHeaderHonored=True,expandedRAM=a.chinese)
                rows.append(row);print(json.dumps(row),flush=True)
            if lang+1<(9 if a.chinese else 8):choose(7,'RIGHT')
        (a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
        if not a.chinese:
            # Save through the real machine, then cold-boot that card again.
            for _ in range(20):
                if e.peek('MOD_LANG','i')==0:break
                choose(7,'LEFT')
            assert e.peek('MOD_LANG','i')==0
            e.press('CANCEL',4);e.wait(1)
            roundtrip()


    finally:e.stop()
if __name__=='__main__':main()
