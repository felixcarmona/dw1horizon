#!/usr/bin/env python3
"""Partner buffer stress: real field loads, cold clips, battle and evolution.

Uses fixture state/stats to select models; engine loaders, animations, battle and
EVL run normally. A safe disc reserves the last sector for a checked canary.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
from tools.dev.playtest.cold_cache import ColdTest
from tools.dev.playtest.load_camera import card_fixture
from tools.dev.playtest.damage_curve_battles import arm_call
from tools.langpatch import elf_symbols


def run(a):
    t = ColdTest(a); e = t.e; out = t.out
    for name, (addr, _, _) in elf_symbols(e.exe+'.elf').items():
        e.table.setdefault(name, addr)
    report = dict(ram_mb=8 if a.ram8 else 2, disc=a.disc, cases=[])
    def save():
        (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    def check(label):
        flow=json.loads(e.api('/api/v1/execution-flow'))
        assert flow['8mb']==a.ram8, flow
        if not a.baseline:
            ram=e.ram();start=e.A('PARTNER_MODEL_BUFFER')-0x80000000+0x18000
            assert ram[start:start+2048]==bytes([0xa5])*2048, label+': buffer canary changed'
        assert t.lua('return HB.bad')=='false', label+': out-of-bounds CD read'
        report['cases'].append(dict(label=label,canary=not a.baseline));save()
        print(label,flush=True)
    def refreshes(n):
        t.lua(f'''HB.frames=0;HB.done=false
HB.v=PCSX.Events.createEventListener('GPU::Vsync',function()
 HB.frames=HB.frames+1
 if HB.frames=={n} then HB.done=true;HB.v:remove();PCSX.pauseEmulator() end
end)
PCSX.resumeEmulator();return true''')
        t.until('HB.done',120)
    def evolve(sid):
        e.run('pause')
        e.poke('EVOLUTION_TARGET',struct.pack('<h',sid));e.poke('HAS_USED_EVOITEM',b'\1')
        e.poke('TAMER_STATE',b'\6');e.poke('TAMER_SUB_STATE',b'\0')
        e.poke('PARTNER_STATE',b'\x0d');e.poke('PARTNER_SUB_STATE',b'\0')
        e.run('resume')
        for _ in range(180):
            ram=e.ram()
            if e.peek('PARTNER_ENTITY','I',ram)==sid and e.peek('PARTNER_STATE','B',ram)==1:break
            e.press('START',8);time.sleep(.15)
        else:raise AssertionError('evolution did not finish: '+str(sid))
        e.poke('PAUSE_STATE',b'\0');e.run('resume')
        assert e.in_control(), 'no control after evolution'
        e.run('pause');check('evolved-'+str(sid))
    try:
        e.start(str(card_fixture(out,44,[-800,0,-900],3,False,0,0)))
        if a.checkpoint:
            e.run('load',str(a.checkpoint.resolve()))
            e.run('resume')
            assert e.in_control()
        else:
            assert e.continue_game()==0 and e.in_control()
            e.wait(5)
        e.run('save',str(out/'boot.state'))
        e.run('pause')
        if not a.baseline:e.poke('PARTNER_MODEL_BUFFER+0x18000',bytes([0xa5])*2048)
        t.lua(f'''HB={{bad=false,reads={{}}}}
HB.b=PCSX.addBreakpoint({e.A('readFileSectors')},'Exec',4,'partner-capacity',function()
 local r=PCSX.getRegisters().GPR.n
 if r.a1=={e.A('PARTNER_MODEL_BUFFER')} then
  HB.reads[#HB.reads+1]=r.a3*2048
  if r.a3*2048>100352 then HB.bad=true;PCSX.pauseEmulator() end
 end
 return true
end);return true''')
        e.gs('set','gametime_running=0','hour=10','minute=0',
             'partner.para.condition=0','partner.para.remainingLifetime=1000',
             'partner.stats.hp=9999','partner.stats.mp=9999',
             'partner.stats.currentHP=9999','partner.stats.currentMP=9999')
        e.run('resume');e.wait(5);assert e.in_control();e.run('pause')
        for sid in a.species:
            t.switch(sid)
            check('direct-load-'+str(sid))
            # The scripted walk uses the real interpreter and partner arrival code.
            t.place('PARTNER_ENTITY',-1500,-900);t.place('TAMER_ENTITY',-800,-900)
            t.calls([('callScriptSection',(0,1250,0))])
            code=bytes([0x4e,0xfc])+struct.pack('<hh',-1200,-925)+bytes([1,0,0x4a,0xfc,0xfe])
            e.poke('MAP_SCRIPT_BUFFER',code);e.poke('SCRIPT_POINTER',struct.pack('<I',e.A('MAP_SCRIPT_BUFFER')))
            e.poke('ACTIVE_INSTRUCTION',b'\0');e.poke('PARTNER_STATE',b'\1')
            e.poke('PARTNER_SUB_STATE',b'\0');e.poke('TAMER_STATE',b'\0')
            e.poke('SOME_SCRIPT_SYNC_BIT',struct.pack('<i',1))
            a.npc='natural';a.target=[-1200,-925]
            rows,complete=t.trace(out/f'walk-{sid}.csv',600)
            assert complete,'scripted walk failed'
            check('walk-'+str(sid))
            e.run('save',str(out/f'field-{sid}.state'))
            # Test start/cancellation itself. A looping resident idle need not
            # complete the toilet state used by ColdTest's original fixture.
            ram=e.ram();table=e.peek('PARTNER_ENTITY+8','I',ram)-0x80000000
            from tools.coldsplit import COLD_SLOTS
            cold=[slot for slot in COLD_SLOTS if struct.unpack_from('<I',ram,table+slot*4)[0]&0x80000000]
            state=out/f'field-{sid}.state'
            clips={str(slot):t.start_clips(state,slot,training=True) for slot in cold}
            clips['cold replacement']=t.start_clips(state,cold[0],cold[-1],training=True)
            clips['resident replacement']=t.start_clips(state,cold[0],0,training=True)
            clips['restart']=t.start_clips(state,cold[0],0,cold[-1],training=True)
            report.setdefault('cold_clips',{})[str(sid)]=clips;save()
            assert all(clips.values()),clips
            check('cold-clips-'+str(sid))
            e.run('load',str(out/f'field-{sid}.state'));e.run('resume')
            assert e.warp(0) and e.in_control()
            e.run('pause')
            e.gs('set','partner.stats.moves=[46,47,48,60]',
                 'partner.stats.hp=9999','partner.stats.mp=9999',
                 'partner.stats.currentHP=9999','partner.stats.currentMP=9999',
                 'partner.stats.off=100','partner.stats.def=999',
                 'partner.stats.speed=300','partner.stats.brain=300',
                 'partner.learned_moves=[255,255,255,255,255,255,255,255,255,255,255,255,255,255,255,255]')
            # A real wild fight, selected by the same helper as moveset tests.
            e.poke('NPC_ENTITIES+0x48',struct.pack('<4h',9999,9999,9999,9999))
            arm_call(e,'startBattle',[2]);e.run('resume')
            for _ in range(180):
                if e.peek('GAME_STATE','B')==1:break
                time.sleep(.2)
            else:raise AssertionError('battle did not start')
            for _ in range(8):e.press('CONFIRM',8);time.sleep(.15)
            refreshes(600)
            assert e.peek('GAME_STATE','B')==1,'battle exited before sample'
            e.run('shot',str(out/f'battle-{sid}.png'));check('battle-'+str(sid))
            # Finish the fixture fight and require the ordinary return to field.
            e.run('resume')
            for _ in range(80):
                for slot in range(8):e.poke('NPC_ENTITIES+'+str(slot*0x68+0x4c),bytes(2))
                e.press('CONFIRM',8);time.sleep(.2)
                if e.peek('GAME_STATE','B')==0:break
            else:raise AssertionError('battle did not return')
            assert e.in_control();check('battle-return-'+str(sid))
            e.run('resume');assert e.warp(44)
            if not a.no_evolution:
                evolve(3);evolve(sid);evolve(3)
        report['reads']=json.loads(t.lua("return '['..table.concat(HB.reads,',')..']'"))
        report['ok']=True;save()
    finally:e.stop()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--port',type=int,default=41961)
    p.add_argument('--ram8',action='store_true');p.add_argument('--baseline',action='store_true')
    p.add_argument('--checkpoint',type=Path)
    p.add_argument('--no-evolution',action='store_true')
    p.add_argument('--species',type=int,nargs='+',default=[303,304])
    run(p.parse_args())
