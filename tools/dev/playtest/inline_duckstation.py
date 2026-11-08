#!/usr/bin/env python3
"""Save and cold-reload one-block .mcd/.mcr cards in isolated 2 MB DuckStation.

Copies the emulator's portable files into the proof directory before changing
settings. No shared emulator configuration or player card is modified.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev import duckstation as ds, memory_card as mcd
from tools.dev.playtest.chart_card_roundtrip import save, NATIVE, IMPORTED, RECRUITED
from tools.dev.playtest.save_policy import filled
from tools.langpatch import elf_symbols

NAME='BASLUS-01032DMR0'


class Duck:
    def __init__(self, table): self.table=table
    def read(self,symbol,n):
        g=ds.GDB();g.s.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
        try:return g.read(self.table[symbol],n)
        finally:g.close()
    def peek(self,symbol,fmt='i'):return struct.unpack('<'+fmt,self.read(symbol,struct.calcsize(fmt)))[0]
    def poke(self,symbol,data):
        g=ds.GDB()
        try:g.write(self.table[symbol],data)
        finally:g.close()
    def wait(self,seconds):time.sleep(seconds)
    def press(self,button,frames=10):
        if button in ('CONFIRM','CANCEL'):
            japanese=self.peek('MOD_OPT_BUTTONS')!=0
            button=('CIRCLE' if japanese else 'CROSS') if button=='CONFIRM' else ('CROSS' if japanese else 'TRIANGLE')
        ds.press(button,max(frames,12));time.sleep(.2)
    def run(self,command,path):
        assert command=='shot';ds.main(['shot',str(path)])
    def continue_game(self):
        selected=False
        for _ in range(120):
            menu=self.peek('CURRENT_MENU');error=self.peek('MEMORY_CARD_ERROR')
            if selected and error>0:return error
            if selected and menu==-1:
                # The card loader restores flags before the world is initialized.
                # Stop at the actual field loop before claiming a playable reload.
                g=ds.GDB();g.s.settimeout(120);address=self.table['gameLoop']
                try:
                    assert g.cmd('Z0,%x,4'%address)=='OK'
                    g.cmd('c')
                    assert g.cmd('z0,%x,4'%address)=='OK'
                finally:g.close()
                time.sleep(3)
                for _ in range(80):
                    if self.peek('IS_SCRIPT_PAUSED')==1 and self.peek('TAMER_STATE','b')==0:
                        if self.peek('IS_GAMETIME_RUNNING','b')!=0:time.sleep(2);return 0
                    else:self.press('CONFIRM')
                    time.sleep(.5)
                raise AssertionError('no field control after Continue')
            if menu==0 and self.peek('MAIN_MENU_TICKS')>3:
                if self.peek('MOD_BOOT_LANGUAGE'):
                    self.press('START')
                elif self.peek('MENU_HIGHLIGHTS','b')!=1:self.press('DOWN')
                else:self.press('CONFIRM');selected=True
            elif selected and menu in (0x14,0x17,0x18):self.press('CONFIRM')
            elif not selected:self.press('START')
            time.sleep(.5)
        raise AssertionError(('Continue timed out',menu,error))
    def history(self):
        return dict(raised=self.read('SPECIES_RAISED_BITS',128).hex(),
                    recruited=self.read('SPECIES_RECRUITED_BITS',128).hex(),
                    native=self.read('SCRIPT_STATE',0x17c)[245:345].hex())
    def mark(self):
        for symbol,ids in [('SPECIES_RAISED_BITS',IMPORTED),('SPECIES_RECRUITED_BITS',RECRUITED)]:
            bits=bytearray(128)
            for n in ids:bits[n//8]|=1<<(n%8)
            self.poke(symbol,bits)
        script=bytearray(self.read('SCRIPT_STATE',0x17c))
        for n in NATIVE:script[245+(512+n)//8]|=1<<((512+n)%8)
        self.poke('SCRIPT_STATE',script)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--legacy-card',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--reload-card',type=Path,help='cold-load an existing game-written v5 card without saving again')
    p.add_argument('--port',type=int,default=39725);p.add_argument('--display',default=':149');a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    private=out/'duck';private.mkdir(exist_ok=True)
    seed=ROOT/'.tools/duckstation/squashfs-root'
    tree=private/'squashfs-root'
    if not tree.exists():shutil.copytree(seed,tree)
    ds.D=str(private);ds.BIN=str(tree/'usr/bin');ds.INI=str(Path(ds.BIN)/'settings.ini');ds.RUN=str(private/'run.json')
    ds.MAP=str(Path(a.exe+'.elf.map').resolve());ds.DISPLAY=a.display;ds.ENV['DISPLAY']=a.display;ds.GDB_PORT=a.port
    table={name:row[0] for name,row in elf_symbols(a.exe+'.elf').items()}
    ds.sym=lambda name:table[name]
    ds.setini('Console','Enable8MBRAM','false');ds.setini('MemoryCards','Card1Type','Shared')
    ds.setini('MemoryCards','Card2Type','None')
    e=Duck(table);result={}
    card=out/'game-card.mcd'
    if a.reload_card:shutil.copyfile(a.reload_card,card)
    else:filled(a.legacy_card,card,15)
    ds.setini('MemoryCards','Card1Path',str(card))
    try:
        if a.reload_card:
            records=dict(mcd.parse_records(mcd.extension(mcd.Card(card).read(NAME))))
            result['before']=dict(raised=records[7].hex(),recruited=records[8].hex())
        else:
            ds.main(['start',str(Path(a.disc).resolve())]);assert e.continue_game()==0
            e.mark();result['before']=e.history();assert save(e)==0
            e.wait(3);e.run('shot',out/'saved.png');ds.main(['stop'])
        data=mcd.Card(card).read(NAME);result['directory']=mcd.Card(card).find(NAME)
        assert len(data)==8192 and mcd.decode_save(data)['copy0']['version']==5
        for suffix in ('mcd','mcr'):
            target=out/f'per-game-{suffix}'/f'SLUS-01032.{suffix}';target.parent.mkdir(exist_ok=True)
            shutil.copyfile(card,target);ds.setini('MemoryCards','Card1Path',str(target))
            ds.main(['start',str(Path(a.disc).resolve())]);assert e.continue_game()==0
            got=e.history();result[suffix]=got
            for key in ('raised','recruited'):assert got[key]==result['before'][key],key
            flags=bytes.fromhex(got['native'])
            assert all(flags[(512+n)//8]&(1<<((512+n)%8)) for n in NATIVE)
            e.run('shot',out/f'reload-{suffix}.png');ds.main(['stop'])
        result['ok']=True
        print('PASS: DuckStation 2 MB full-card save, .mcd and raw .mcr cold reload')
    finally:
        ds.main(['stop']);(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
