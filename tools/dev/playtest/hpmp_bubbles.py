#!/usr/bin/env python3
"""Native 2 MB evidence for recovery needs, labels, menus and both fonts.

Boots the supplied disc; never imports another executable's state. Setup writes
only isolate stats, bag and care conditions. Square/Cancel use pad input. The
language patch runs are the same DWLP bytes installed by the game's switcher.
"""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.training_evolution import call
from tools.dev.playtest.quick_care import place_partner,position,wait
from tools.langpatch import elf_symbols
from tools.languages import CODES,PATCHES


def settle(e):
    e.run('resume')
    start=e.peek('MOD_RING_CLOCK','i')
    until=time.monotonic()+20
    while time.monotonic()<until:
        ram=e.ram()
        if e.peek('MOD_RING_CLOCK','i',ram)-start>=25 and e.peek('MOD_RING_T','i',ram)<0:
            return
        e.wait(.1)
    raise AssertionError('condition ring never settled')


def setup(e,hp,mp,hunger=False,bag=True):
    e.run('pause')
    e.gs('set','gametime_running=0','partner.para.evoTimer=0','partner.para.remainingLifetime=1000',
         'partner.stats.hp=1000','partner.stats.mp=1000',f'partner.stats.currentHP={hp}',
         f'partner.stats.currentMP={mp}',f'partner.para.condition={4 if hunger else 0}',
         'partner.para.tiredness=0','partner.para.poopLevel=1000','partner.para.virusBar=0')
    # Care close resumes the clock; freeze its rule too so repeated menu tours
    # cannot trigger unrelated evolution or death between captures.
    e.poke('MOD_CLOCK',struct.pack('<h',-1))
    e.poke('EVOLUTION_TARGET',struct.pack('<h',-1))
    e.poke('INVENTORY',struct.pack('<30h',*([0,4,38]+[-1]*27 if bag else [-1]*30)))
    e.poke('INVENTORY+60',bytes([5,5,5]+[0]*27 if bag else [0]*30))
    e.poke('INVENTORY+120',bytes([30]))
    e.poke('ITEM_SCOLD_FLAG',b'\0')
    e.poke('MOD_STATUS_BUBBLES',struct.pack('<i',1))
    settle(e)


def state(e):
    ram=e.ram();slots=e.peek('MOD_RING_FROM','9i',ram)
    return {'hp':e.peek('PARTNER_ENTITY+0x4c','H',ram),'mp':e.peek('PARTNER_ENTITY+0x4e','H',ram),
            'active':[i for i,slot in enumerate(slots) if slot!=0x10000],
            'badge':e.peek('MOD_RING_BADGE','i',ram),'slots':slots,
            'condition':e.peek('PARTNER_PARA','I',ram),
            'tamer_state':e.peek('TAMER_STATE','b',ram),'partner_state':e.peek('PARTNER_STATE','b',ram),
            'in_menu':e.peek('IS_IN_MENU','i',ram),'script_paused':e.peek('IS_SCRIPT_PAUSED','i',ram)}


def shot(e,out,name,width=88,height=72):
    e.run('pause');path=out/(name+'.png');e.run('shot',str(path))
    from tools.image import Image
    im=Image.open(path);assert im.size==(320,240),im.size
    shown=e.peek('MOD_RING_SHOWN+16','I')
    xy=struct.unpack('<2h',struct.pack('<I',shown))
    x=xy[0]+e.peek('DRAWING_OFFSET_X','i');y=xy[1]+e.peek('DRAWING_OFFSET_Y','i')
    # The real rendered anchor, including bob and top clamp, determines the crop.
    im.crop((x-width//2,y-height//2-1,x+width//2,y+height//2-1)).resize((width*4,height*4),Image.Resampling.NEAREST).save(out/(name+'-4x.png'))
    e.run('resume')


def menu_press(e,button):
    # Input edges can fall between the UI's 20 Hz ticks; retry a released pad
    # press only while the same open menu still owns the input.
    for _ in range(8):
        if e.peek('feedState','i') != 1:
            return
        e.press(button,12);e.wait(.15)
    raise AssertionError(button+' never left the open care menu')


def open_menu(e):
    # A released Square edge can miss an ordinary-walking tick. Retry only
    # while the care menu is closed; never send a second action to an open UI.
    for _ in range(8):
        if e.peek('IS_IN_MENU','i') == 0:
            e.press('SQUARE',12)
        if e.peek('IS_IN_MENU','i') == 1:
            wait(e,'feedState',1,seconds=20)
            return
        e.wait(.15)
    raise AssertionError('Square never opened the care menu')


def menu(e,out,name):
    before=e.peek('INVENTORY+60','30B');open_menu(e)
    assert e.peek('IS_IN_MENU','i')==1
    count=e.peek('feedCount','i');slots=e.peek('feedSlots',str(count)+'B')
    ranks=e.peek('feedRanks',str(count)+'i')
    if count==1:slots=[slots];ranks=[ranks]
    assert list(ranks)==sorted(ranks),(slots,ranks)
    assert e.peek('INVENTORY+60','30B')==before,'opening consumed a recovery item'
    shot(e,out,name)
    menu_press(e,'CANCEL');wait(e,'TAMER_STATE',0,'b');assert e.peek('IS_IN_MENU','i')==0
    return {'count':count,'slots':slots,'ranks':ranks,'opening_consumed':False}


def language(e,folder,code):
    patch=next(folder.rglob(PATCHES[code]))
    b=patch.read_bytes();assert b[:4]==b'DWLP'
    e.run('pause');n=struct.unpack_from('<I',b,4)[0];p=8
    # A single Lua write per run avoids interpreting any asset as a text/font.
    import urllib.request
    for _ in range(n):
        address,size=struct.unpack_from('<II',b,p);p+=8
        request=urllib.request.Request(f'http://127.0.0.1:{e.port}/api/v1/cpu/ram/raw?offset={address&0x1fffff}&size={size}',data=b[p:p+size])
        urllib.request.urlopen(request).read();p+=(size+3)&~3
    e.poke('MOD_LANG',struct.pack('<i',CODES.index(code)))
    # MENU is loaded normally by Square, using the newly selected language.
    e.run('resume')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True);p.add_argument('--card',required=True)
    p.add_argument('--out',default='build/hpmp-proof');p.add_argument('--port',type=int,default=38864)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--smoke',action='store_true',help='threshold/menu smoke test; skip the language tour')
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out/'emu'));e.env['EMU_ARGS']='-interpreter -debugger'
    for name,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,addr)
    result={};base=out/'base.state';fixture=out/'fixture.json'
    exe_hash=hashlib.sha256(Path(a.exe).read_bytes()).hexdigest()
    def interrupted(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupted)
    try:
        e.start(a.card)
        if a.resume:
            assert json.loads(fixture.read_text())['exe_sha256']==exe_hash
            e.run('load',str(base));e.run('resume')
        else:
            assert e.continue_game()==0,'Continue failed';assert e.in_control()
            setup(e,1000,1000);assert e.in_control()
            assert e.warp(171),'File City did not load';assert e.in_control()
            e.press('DOWN',35);e.press('RIGHT',25);assert e.in_control()
            e.press('DOWN',90);assert e.in_control()
            x,y,z=position(e,'TAMER_ENTITY');place_partner(e,x-350,y,z+200)
            setup(e,1000,1000);e.run('save',str(base))
            fixture.write_text(json.dumps({'exe_sha256':exe_hash})+'\n')
        assert len(e.ram())==0x200000
        flow=json.loads(e.api('/api/v1/execution-flow'));assert not flow['8mb'],flow
        result['configuration']={'ram_bytes':0x200000,'eight_mb':False,'exe_sha256':exe_hash}
        for name,hp,mp,hunger,bag,want in (
            ('hp29',290,1000,False,True,[6]),('hp31',310,1000,False,True,[]),
            ('mp29',1000,290,False,True,[7]),('mp31',1000,310,False,True,[]),
            ('both30',300,300,False,True,[]),('both-hunger',290,290,True,True,[0,6,7]),
            ('no-items',290,290,False,False,[6,7]),('full',1000,1000,False,True,[])):
            e.run('load',str(base));e.run('resume');setup(e,hp,mp,hunger,bag)
            got=state(e);assert got['active']==want,(name,got)
            assert bool(got['badge'])==bool(want and bag),(name,got)
            shot(e,out,name);result[name]=got
            print(name,got,flush=True)
        setup(e,310,310);assert not e.peek('MOD_RING_BADGE','i')
        result['optional-menu']=menu(e,out,'optional-menu')
        assert all(rank==7*256 for rank in result['optional-menu']['ranks'])
        setup(e,310,290);result['urgency-menu']=menu(e,out,'urgency-menu')
        assert result['urgency-menu']['slots']==[1,0]
        e.run('load',str(base));e.run('resume');setup(e,290,1000)
        open_menu(e)
        menu_press(e,'CONFIRM')
        wait(e,'TAMER_STATE',0,'b',seconds=45);wait(e,'PARTNER_STATE',1,'b',seconds=45)
        settle(e);healed=state(e)
        assert healed['hp']>300 and 6 not in healed['active'],healed
        assert e.peek('INVENTORY+60','B')==4
        result['recovery-use']=healed;shot(e,out,'recovered')
        result['languages']={}
        folder=Path(a.exe).resolve().parent.parent
        for code in (() if a.smoke else CODES[:8]):
            e.run('load',str(base));e.run('resume')
            language(e,folder,code)
            result['languages'][code]={}
            for font in (0,1):
                call(e,'modSetFont',font);e.run('resume')
                setup(e,290,290,True)
                assert state(e)['active']==[0,6,7]
                name=f'{code}-font-{font}'
                shot(e,out,name+'-field')
                got=menu(e,out,name+'-menu');assert got['slots']==[2,0,1],(code,font,got)
                result['languages'][code][str(font)]=got
                print(name,'field + menu passed',flush=True)
        result['passed']=True
    except BaseException as error:
        result['error']=str(error)
        try:
            result['failure_state']=state(e)
            result['evolution_target']=e.peek('EVOLUTION_TARGET','h')
            (out/'failure.ram').write_bytes(e.ram())
        except Exception:
            pass
        raise
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        e.stop()


if __name__=='__main__':main()
