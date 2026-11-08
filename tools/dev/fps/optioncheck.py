#!/usr/bin/env python3
"""Exercise FRAME RATE through title input, a native card save and cold Continue.

Usage: python3 tools/dev/fps/optioncheck.py DISC --exe EXE --out build/fps-option
--tour captures the eight 2-MB languages in NEW/CLASSIC/ORIGINAL.
--chinese checks Chinese separately with its required 8 MB and NEW font.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.saves.releases import Emu, read_card, card_ok
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.langpatch import elf_symbols


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,default=Path('build/fps-option'))
    p.add_argument('--port',type=int,default=44615)
    p.add_argument('--card',default='tools/dev/saves/corpus/20261027-d2796814.mcd')
    p.add_argument('--resume-card');p.add_argument('--capture-forced',action='store_true');p.add_argument('--tour',action='store_true');p.add_argument('--chinese',action='store_true')
    a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
    e=Emu(a.disc,a.exe,a.port,str(a.out/'emu'))
    if a.chinese:
        def expanded_ram():
            data=subprocess.run([sys.executable,str(ROOT/'tools/dev/emulator.py'),'ramdump'],env=e.env,capture_output=True,check=True).stdout
            assert len(data)==0x800000
            return data
        e.ram=expanded_ram
    for name,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,addr)
    bios=ROOT/'.tools/emu/pcsx-redux-zip/squashfs-root/usr/share/pcsx-redux/resources/openbios.bin'
    e.env['EMU_ARGS']='-interpreter -debugger -bios '+str(bios)+(' -8mb' if a.chinese else '')
    rows=json.loads((a.out/'results.json').read_text()) if a.resume_card and (a.out/'results.json').exists() else [];cursor='MENU_HIGHLIGHTS+'+str(22*16)
    def settle():
        start=e.peek('MAIN_MENU_TICKS','i');end=time.monotonic()+120
        while time.monotonic()<end:
            if e.peek('MAIN_MENU_TICKS','i')>=start+10:return
            e.wait(.1)
        raise AssertionError('OPTIONS did not become idle')
    def choose(row,key):
        symbol,fmt={6:('MOD_OPT_FPS','i'),7:('MOD_FONT','b'),8:('MOD_LANG','i')}[row]
        before=e.peek(symbol,fmt)
        for attempt in range(3):
            settle();e.poke(cursor,bytes([row]));e.press(key,12);settle()
            if e.peek(symbol,fmt)!=before:break
            # Saturating arrows deliberately leave the boundary unchanged.
            if row==6 and ((key=='LEFT' and before==0) or (key=='RIGHT' and before==2)):break
        ram=e.ram();print(json.dumps(dict(row=row,key=key,mode=e.peek('MOD_OPT_FPS','i',ram),effective=e.peek('MOD_FPS_MODE_RUN','i',ram),language=e.peek('MOD_LANG','i',ram),font=e.peek('MOD_FONT','b',ram),menu=e.peek('CURRENT_MENU','i',ram),cursor=e.peek(cursor,'B',ram))),flush=True)
    def opened():
        for _ in range(30):
            menu=e.peek('CURRENT_MENU','i')
            if menu==4:return
            if menu==0:
                e.poke('MENU_HIGHLIGHTS',bytes([4]));e.press('CONFIRM',12)
            e.wait(1)
        raise AssertionError('OPTIONS did not open')
    def shot(name):
        if not name.startswith('field-'):
            e.run('shot',str(a.out/(name+'.png')));return
        # Capture the displayed buffer immediately after swap, before the next
        # OT clears it. HTTP stills can catch a partially drawn field frame.
        raw=a.out/(name+'.raw')
        e.run('lua',f"""FPS_OPTION_SHOT={{done=false}}
FPS_OPTION_SHOT.bp=PCSX.addBreakpoint({e.A('GsSortClear')},'Exec',4,'fps-option-shot',function()
 local s=PCSX.GPU.takeScreenShot()
 local f=Support.File.open({json.dumps(str(raw))},'TRUNCATE')
 f:writeMoveSlice(s.data);f:close()
 FPS_OPTION_SHOT.done=true;FPS_OPTION_SHOT.bp:remove()
end)
return 1""")
        for _ in range(120):
            if e.run('lua','return FPS_OPTION_SHOT.done').strip()=='true':break
            e.wait(.1)
        else:raise AssertionError('no presented field frame')
        subprocess.run(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pixel_format','bgr555le','-video_size','320x240','-i',str(raw),'-frames:v','1',str(a.out/(name+'.png'))],check=True)

    def measure(name):
        before=e.ram();e.wait(5);after=e.ram()
        values={n:e.peek(n,'i',after)-e.peek(n,'i',before) for n in ('MOD_FPS_RENDERS','MOD_FPS_TICKS','MOD_PERF_XPASSES')}
        values.update(mode=e.peek('MOD_OPT_FPS','i',after),effective=e.peek('MOD_FPS_MODE_RUN','i',after),probe=e.peek('MOD_CPU_SPINS','i',after))
        if e.has('MOD_DIAG_FPS'):values.update(fps=e.peek('MOD_DIAG_FPS','i',after),missed=e.peek('MOD_DIAG_MISSED','i',after))
        rows.append(dict(scene=name,**values));print(json.dumps(rows[-1]),flush=True);shot(name)
    try:
        if a.resume_card:
            e.start(a.resume_card);e.to_title();assert e.peek('MOD_OPT_FPS','i')==1
            if a.capture_forced:
                assert e.raw('MOD_VERSION_TEXT',32,e.ram()).split(b'\0')[0]==b'v0.0.7-fpstest1'
                shot('title-forced60')
                assert e.continue_game()==0;measure('field-forced60')
                e.stop();e.start(a.resume_card);e.to_title();assert e.peek('MOD_OPT_FPS','i')==1
            decoded,_,records=read_card(a.resume_card)
            assert records[9][2]==0xA1 and bytes.fromhex(decoded['header_options']['bytes'])[2]==0xA1
            (a.out/'save-roundtrip.json').write_text(json.dumps(dict(taggedByte=161,headerByte=161,coldBootMode=1,validCard=not card_ok(a.resume_card)),indent=2)+'\n')
            opened();choose(6,'LEFT');assert e.peek('MOD_OPT_FPS','i')==0
            shot('options-auto');e.press('CANCEL',4)
            assert e.continue_game()==0;assert e.peek('MOD_OPT_FPS','i')==0
            e.wait(5);assert e.peek('MOD_FPS_MODE_RUN','i')==0;measure('field-auto')
            return
        card=field_card(a.card,str(a.out/'input.mcd'),partner_type=65)
        e.start(card);e.to_title();assert e.peek('MOD_OPT_FPS','i')==0
        opened()
        for key,want in [('RIGHT',1),('RIGHT',2),('CONFIRM',0),('LEFT',0),('CONFIRM',1),('LEFT',0)]:
            choose(6,key);assert e.peek('MOD_OPT_FPS','i')==want
            assert e.peek('MOD_FPS_MODE_RUN','i')==(2 if want==1 else 0)
        if a.tour or a.chinese:
            for lang,code in enumerate(('en','es','pt-br','fr','de','it','ja','ca','zh-hans') if a.chinese else ('en','es','pt-br','fr','de','it','ja','ca')):
                assert e.peek('MOD_LANG','i')==lang
                if a.chinese and lang<8:choose(8,'RIGHT');continue
                for face,want in [('new',0),('classic',2),('original',1)] if lang<8 else [('new',0)]:
                    while e.peek('MOD_FONT','b')!=want:choose(7,'CONFIRM')
                    e.poke(cursor,bytes([6]));e.wait(.3)
                    width=e.peek('MOD_OPT_TEXT_W','h');assert 0<width<=304
                    shot(code+'-'+face);rows.append(dict(language=code,font=face,width=width))
                if lang<7 or (a.chinese and lang<8):choose(8,'RIGHT')
            if a.chinese:return
            while e.peek('MOD_LANG','i')!=0:choose(8,'LEFT')
            while e.peek('MOD_FONT','b')!=0:choose(7,'CONFIRM')
        choose(6,'RIGHT');assert e.peek('MOD_OPT_FPS','i')==1
        shot('options-forced60');e.press('CANCEL',4)
        assert e.continue_game()==0;assert e.peek('MOD_OPT_FPS','i')==1
        assert len(e.ram())==0x200000
        measure('field-forced60');assert e.peek('MOD_FPS_MODE_RUN','i')==2
        # Save through the game, then inspect both its tagged copy and title header.
        if e.peek('CURRENT_SCREEN','h')!=218:assert e.warp(218,2)
        e.gs('set','gametime_running=0');e.save_at_jijimon();e.stop()
        saved=a.out/'forced60.mcd';shutil.copy2(e.card_out(),saved)
        assert not card_ok(str(saved));decoded,_,records=read_card(str(saved))
        assert records[9][2]==0xA1
        assert bytes.fromhex(decoded['header_options']['bytes'])[2]==0xA1
        e.start(str(saved));e.to_title();assert e.peek('MOD_OPT_FPS','i')==1
        opened();choose(6,'LEFT');assert e.peek('MOD_OPT_FPS','i')==0
        shot('options-auto');e.press('CANCEL',4)
        assert e.continue_game()==0;assert e.peek('MOD_OPT_FPS','i')==0
        e.wait(5);assert e.peek('MOD_FPS_MODE_RUN','i')==0;measure('field-auto')
        (a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
    finally:
        (a.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
        e.stop()

if __name__=='__main__':main()
