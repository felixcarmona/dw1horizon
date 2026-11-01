#!/usr/bin/env python3
"""Whamon's dock return on original 2 MB RAM, from a disposable corpus card.

Run with xvfb-run -a python3 story/mods/what-the-island-forgot/test/playtest_whamon.py
--mode fixed --out build/whamon-fixed. Baseline mode records the invisible speaker.
The wait's final night uses the real partner sleep state; earlier days are setup
writes. Every conversation starts by walking onto the actual dock trigger tile.
"""
import argparse
import json
import struct
import sys
import time
import urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.dev.playtest.qol import ProofEmu, test_card

class WhamonEmu(ProofEmu):
    def ram(self):
        data = self.api('/api/v1/cpu/ram/raw')
        assert len(data) == 0x200000, 'Whamon proof requires original 2 MB RAM'
        return data

    def poke(self, expression, data):
        offset = self.A(expression) & 0x1fffff
        request = urllib.request.Request(
            f'http://127.0.0.1:{self.port}/api/v1/cpu/ram/raw?offset={offset}&size={len(data)}',
            data=data, method='POST')
        urllib.request.urlopen(request, timeout=15).read()


ap=argparse.ArgumentParser()
ap.add_argument('--disc', default='build/dev-everything.cue')
ap.add_argument('--exe', default='build/dev-everything/exe/SLUS_010.32')
ap.add_argument('--port', type=int, default=43167)
ap.add_argument('--all-layouts', action='store_true')
ap.add_argument('--mode', choices=['baseline','fixed'], required=True)
ap.add_argument('--out', type=Path, required=True)
a=ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
results=[]
e=WhamonEmu(a.disc, a.exe, a.port, str(a.out))
# This probe uses real pad input and collision tiles; no function breakpoints.

def pk(sym,fmt,v): e.poke(sym,struct.pack('<'+fmt,v))
def flag(n,v):
    b=e.peek(f'SCRIPT_STATE+{245+n//8}','B')
    pk(f'SCRIPT_STATE+{245+n//8}','B',(b | 1<<(n%8)) if v else (b & ~(1<<(n%8))))
def pst(n,v): pk(f'SCRIPT_STATE+{345+n}','B',v)
def present(): return e.peek('ENTITY_TABLE+36','I') != 0

def paused_shot(label):
    e.run('pause'); e.wait(.2)
    e.run('shot',str(a.out/(label+'.png'))); e.wait(.3)
    e.run('shot',str(a.out/(label+'-paused.png')))
    assert (a.out/(label+'.png')).read_bytes()==(a.out/(label+'-paused.png')).read_bytes()
    e.run('resume')

def waitfor(fn,secs=40,advance=False):
    end=time.monotonic()+secs
    while time.monotonic()<end:
        if fn(): return
        if advance and e.peek('ACTIVE_INSTRUCTION','B') in (0x1a,0x10): e.press('CONFIRM',10)
        e.wait(.25)
    raise AssertionError('timeout: '+str((e.peek('CURRENT_SCREEN','h'),e.peek('TAMER_STATE','b'),e.peek('ACTIVE_INSTRUCTION','B'))))

def control():
    return e.peek('IS_SCRIPT_PAUSED','i')==1 and e.peek('TAMER_STATE','b')==0

def place(x,z):
    e.run('pause')
    loc=struct.pack('<3i',x,0,z)
    e.poke('TAMER_POSITION_DATA+0x78',loc); e.poke('STORED_TAMER_POS',loc)
    e.poke('TAMER_ENTITY+0x10',struct.pack('<3i',x<<15,0,z<<15))
    e.run('resume')

def trigger():
    ram=e.ram(); off=e.A('MAP_COLLISION_DATA')-0x80000000
    cells=[(i%100,i//100) for i,b in enumerate(ram[off:off+10000]) if b==55]
    print('trigger cells',cells,flush=True)
    assert cells
    col,row=cells[len(cells)//2]
    place((col-50)*100+50,(49-row)*100+50)
    e.press('UP',8)
    waitfor(lambda: not control())

def setup(hurt, layout=168, chase=False):
    e.run('load',str((a.out/'fixture.state').resolve()))
    waitfor(control)
    e.run('pause')
    for n,v in [(224,1),(750,chase),(751,hurt),(753,hurt),(736,0),(83,1),(87,0),(354,0),(84,1),
                (220,layout>=174),(214,layout>=174),(221,(layout-168)%6>=3),(225,(layout-168)%3==2),(246,(layout-168)%3==1)]: flag(n,v)
    pst(10,0); pst(11,43)
    pk('YEAR','B',42); pk('DAY','h',0); pk('HOUR','h',10); pk('MINUTE','h',0)
    pk('CURRENT_FRAME','H',12000); pk('LAST_HANDLED_FRAME','H',12000)
    pk('IS_GAMETIME_RUNNING','B',0)
    pk('MOD_CLOCK','h',-1)
    e.run('resume')
    assert e.warp(layout), 'dock warp failed'
    waitfor(control); e.wait(1)
    assert e.peek('CURRENT_SCREEN','h')==layout

def case(hurt, reload, layout=168, use_sleep=False):
    setup(hurt,layout)
    label=f'{"hurt" if hurt else "chase"}-{layout}-{"reload" if reload else "stay"}'
    if not hurt:
        assert present()
        trigger()
        waitfor(lambda: not present(),advance=True)
        waitfor(control,advance=True)
    assert not present()
    if use_sleep:
        # Arrange the final night of the wait, then let the game's sleep transition advance the day.
        pk('DAY','h',9 if hurt else 4); pk('HOUR','h',23)
        pk('CURRENT_FRAME','H',23*1200); pk('LAST_HANDLED_FRAME','H',23*1200)
        e.gs('set','partner.para.wakeupHour=7','partner.para.wakeupMinute=0','partner.para.evoTimer=0',
             'partner.para.condition=1','partner.para.remainingLifetime=200')
        pk('MEMORY_CARD_ID','i',-1); pk('MEMORY_CARD_SLOT','i',-1)
        pk('PARTNER_SUB_STATE','B',0); pk('PARTNER_STATE','B',3)
        waitfor(lambda: e.peek('DAY','h')==(10 if hurt else 5),secs=80,advance=True)
        waitfor(control,secs=80,advance=True)
        pk('IS_GAMETIME_RUNNING','B',0)
        assert not present(), 'sleep unexpectedly reloaded the screen'
    else: pk('DAY','h',10 if hurt else 5)
    if reload:
        assert e.warp(218)
        assert e.warp(layout)
        waitfor(control)
        assert present()
    trigger()
    waitfor(lambda: e.peek('ACTIVE_INSTRUCTION','B')==0x1a)
    e.wait(1)
    paused_shot(label)
    row=dict(case=label, present=present(), day=e.peek('DAY','h'), ram_bytes=len(e.ram()), slept=use_sleep)
    results.append(row)
    (a.out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(row),flush=True)
    if a.mode=='baseline':
        assert not present()
        return
    assert present()
    # Decline the old shore and the repeated shore offer, then reach the game's ferry menu.
    for _ in range(50):
        op=e.peek('ACTIVE_INSTRUCTION','B')
        if op==0x10: break
        e.press('CONFIRM',10); e.wait(.3)
    else: raise AssertionError('shore menu missing')
    e.press('CANCEL',10); e.wait(.7)
    # Two guarded shore handlers may both run on the first visit.
    ferry_seen=False
    for _ in range(40):
        op=e.peek('ACTIVE_INSTRUCTION','B')
        if op==0x10:
            count=e.peek('DIALOGUE_SELECTION+8','H')
            if count==3:
                ferry_seen=True
                paused_shot(label+'-ferry')
            e.press('CANCEL',10)
        elif op==0x1a: e.press('CONFIRM',10)
        elif control(): break
        e.wait(.35)
    else: raise AssertionError('ferry did not return control')
    assert present()
    assert ferry_seen, 'original three-option ferry menu missing'
    assert e.peek('LOADED_DIGIMON_MODELS','8i').count(146)==1
    row['ferry_menu']=True
    (a.out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print('PASS',label,flush=True)

try:
    e.start(test_card(a.out))
    result=e.continue_game()
    print('continue',result,flush=True)
    assert result==0, result
    assert e.in_control()
    assert len(e.ram())==0x200000
    print('booted screen',e.peek('CURRENT_SCREEN','h'),flush=True)
    e.run('save',str((a.out/'fixture.state').resolve()))
    if a.mode=='baseline':
        for hurt in (False, True): case(hurt,False,use_sleep=True)
    else:
        for layout in (range(168,180) if a.all_layouts else (168,)):
            for hurt in (False,True):
                for reload in (False,True): case(hurt,reload,layout,use_sleep=not reload)
finally: e.stop()
